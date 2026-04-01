"""
Router para importação de mãos do HM3 (Holdem Manager 3).

Recebe um CSV exportado via SQLite com colunas:
  gamenumber, site_id, tag, handtimestamp, tournament_number, handhistory

Site IDs do HM3:
  22 = Winamax (hero: schadenfreud, thinvalium, Sapz)
  2  = PokerStars (hero: misterpoker1973)
  24 = WPN (hero: cringemeariver)

Cada mão pode ter múltiplas tags (rows repetidos com tags diferentes).
As mãos são importadas na tabela hands com study_state='new' e as tags do HM3.
"""
import re
import csv
import io
import logging
from datetime import datetime
from collections import defaultdict
from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from app.auth import require_auth
from app.db import get_conn, query

router = APIRouter(prefix="/api/hm3", tags=["hm3"])
logger = logging.getLogger("hm3")

# ── Site mapping ──────────────────────────────────────────────────────────────

SITE_MAP = {
    "22": "Winamax",
    "2": "PokerStars",
    "24": "WPN",
    "29": "GGPoker",
    "4": "888poker",
    "12": "iPoker",
}

HERO_NAMES = {
    "schadenfreud", "thinvalium", "sapz",
    "misterpoker1973",
    "cringemeariver",
    "flightrisk", "karluz",
    "koumpounophobia", "lauro dermio",
}


def _extract_showdown_villain_tags(raw_text: str) -> list[str]:
    """
    Extract villain nicks that went to showdown (excluding hero).
    Returns list of nick strings to be used as tags.
    Works for Winamax, GG, PokerStars, and WPN formats.
    """
    # Detect hero from "Dealt to X [cards]"
    dealt_m = re.search(r'Dealt to (.+?)\s+\[', raw_text)
    hero_from_dealt = dealt_m.group(1).strip().lower() if dealt_m else None

    villain_nicks = []
    for m in re.finditer(r'^(.+?)(?::)?\s+shows\s+\[(.+?)\]', raw_text, re.MULTILINE):
        name = m.group(1).strip()
        if name.lower().startswith('main pot') or name.startswith('***'):
            continue
        # Check cards are valid (2 chars each)
        cards = [c.strip() for c in m.group(2).split() if c.strip() and len(c.strip()) == 2]
        if not cards:
            continue
        # Skip hero
        if name.lower() in HERO_NAMES:
            continue
        if name.lower() == 'hero':
            continue
        if hero_from_dealt and name.lower() == hero_from_dealt:
            continue
        villain_nicks.append(name)

    return villain_nicks

# ── Position Logic ────────────────────────────────────────────────────────────

POSITION_MAPS = {
    2:  ["SB", "BB"],
    3:  ["BTN", "SB", "BB"],
    4:  ["CO", "BTN", "SB", "BB"],
    5:  ["UTG", "CO", "BTN", "SB", "BB"],
    6:  ["UTG", "MP", "CO", "BTN", "SB", "BB"],
    7:  ["UTG", "UTG1", "MP", "CO", "BTN", "SB", "BB"],
    8:  ["UTG", "UTG1", "MP", "MP1", "CO", "BTN", "SB", "BB"],
    9:  ["UTG", "UTG1", "MP", "MP1", "HJ", "CO", "BTN", "SB", "BB"],
    10: ["UTG", "UTG1", "UTG2", "MP", "MP1", "HJ", "CO", "BTN", "SB", "BB"],
}


def _get_position(seat_num, button_seat, all_seats, num_players):
    sorted_seats = sorted(all_seats)
    if num_players == 2:
        return "SB" if seat_num == button_seat else "BB"
    btn_idx = sorted_seats.index(button_seat)
    ordered = sorted_seats[btn_idx + 1:] + sorted_seats[:btn_idx + 1]
    pos_map = POSITION_MAPS.get(num_players)
    if not pos_map:
        return "?"
    try:
        player_idx = ordered.index(seat_num)
    except ValueError:
        return "?"
    if seat_num == button_seat:
        return "BTN"
    if player_idx == 0:
        return "SB"
    elif player_idx == 1:
        return "BB"
    else:
        middle = pos_map[:-3]
        mid_idx = player_idx - 2
        if mid_idx < len(middle):
            return middle[mid_idx]
        return "?"


def _normalise_position(pos):
    if not pos:
        return pos
    return pos.replace("+", "")


# ── Hand History Parser (multi-site) ─────────────────────────────────────────

def _parse_hand(hh_text, site_name):
    if not hh_text or len(hh_text) < 50:
        return None

    result = {
        "site": site_name,
        "hand_id": None,
        "played_at": None,
        "stakes": None,
        "position": None,
        "hero_cards": [],
        "board": [],
        "result": None,
        "currency": "$",
        "raw": hh_text.strip(),
    }

    # ── Hand ID ──
    if site_name == "Winamax":
        m = re.search(r"HandId:\s*#(\S+)", hh_text)
        if m:
            result["hand_id"] = f"WN-{m.group(1)}"
        result["currency"] = "€"
    elif site_name == "PokerStars":
        m = re.search(r"Hand\s*#(\d+)", hh_text)
        if m:
            result["hand_id"] = f"PS-{m.group(1)}"
    elif site_name == "WPN":
        m = re.search(r"Hand\s*#(\d+)", hh_text)
        if m:
            result["hand_id"] = f"WPN-{m.group(1)}"
    else:
        m = re.search(r"Hand\s*#(\d+)", hh_text)
        if m:
            result["hand_id"] = f"{site_name[:3].upper()}-{m.group(1)}"

    # ── Date ──
    m = re.search(r"(\d{4})/(\d{2})/(\d{2})\s+(\d{1,2}):(\d{2}):(\d{2})", hh_text)
    if m:
        try:
            result["played_at"] = datetime(
                int(m.group(1)), int(m.group(2)), int(m.group(3)),
                int(m.group(4)), int(m.group(5)), int(m.group(6)),
            ).isoformat()
        except ValueError:
            pass

    # ── Tournament name / stakes ──
    if site_name == "Winamax":
        m = re.search(r'Tournament\s+"([^"]+)"', hh_text)
        if m:
            result["stakes"] = m.group(1).strip()
        buyin_m = re.search(r'buyIn:\s*([\d\u20ac$,.]+(?:\s*\+\s*[\d\u20ac$,.]+)?)', hh_text)
        if buyin_m and result["stakes"]:
            result["stakes"] += f" ({buyin_m.group(1).strip()})"
    elif site_name == "PokerStars":
        m = re.search(r"Tournament\s*#\d+,\s*(.+?)(?:Hold'em|Holdem)", hh_text)
        if m:
            result["stakes"] = m.group(1).strip().rstrip(",- ")
    elif site_name == "WPN":
        m = re.search(r"Tournament\s*#\d+\s*-\s*(.+?)(?:\s*-\s*Holdem)", hh_text)
        if m:
            result["stakes"] = m.group(1).strip()

    # ── Button seat ──
    table_m = re.search(r"Seat\s*#(\d+)\s+is the button", hh_text)
    button_seat = int(table_m.group(1)) if table_m else None

    # ── Seats + Bounties ──
    seats = {}
    all_seat_nums = []
    hero_seat = None
    hero_name = None

    if site_name == "Winamax":
        # Winamax: Seat 1: thinvalium (12379, 20€ bounty)  or  Seat 1: name (12379)
        for sm in re.finditer(r"Seat\s+(\d+):\s*(.+?)\s*\(([\d.]+)(?:,\s*([^)]+))?\)", hh_text):
            seat_num = int(sm.group(1))
            name = sm.group(2).strip()
            stack = float(sm.group(3).replace(",", ""))
            bounty = None
            extra = sm.group(4)
            if extra:
                bm = re.search(r"([\d.]+)\s*[€$]?\s*bounty", extra, re.I)
                if bm:
                    bounty = float(bm.group(1))
                else:
                    bm2 = re.search(r"[€$]([\d.]+)\s*bounty", extra, re.I)
                    if bm2:
                        bounty = float(bm2.group(1))
            seats[seat_num] = {"name": name, "stack": stack, "bounty": bounty}
            all_seat_nums.append(seat_num)
            if name.lower() in HERO_NAMES:
                hero_seat = seat_num
                hero_name = name
    else:
        # PokerStars/WPN: Seat 1: name (24500 in chips, $25 bounty)
        for sm in re.finditer(r"Seat\s+(\d+):\s*(.+?)\s*\(([\d,]+)\s+in chips(?:,\s*([^)]+))?\)", hh_text):
            seat_num = int(sm.group(1))
            name = sm.group(2).strip()
            stack = float(sm.group(3).replace(",", ""))
            bounty = None
            extra = sm.group(4)
            if extra:
                bm = re.search(r"\$([\d.]+)\s*bounty", extra, re.I)
                if bm:
                    bounty = float(bm.group(1))
            seats[seat_num] = {"name": name, "stack": stack, "bounty": bounty}
            all_seat_nums.append(seat_num)
            if name.lower() in HERO_NAMES:
                hero_seat = seat_num
                hero_name = name

    dealt_m = re.search(r"Dealt to (\S+)\s+\[(.+?)\]", hh_text)
    if dealt_m:
        dealt_name = dealt_m.group(1).strip()
        hero_cards_str = dealt_m.group(2).strip()
        result["hero_cards"] = [c.strip() for c in hero_cards_str.split() if c.strip()]
        if not hero_name:
            hero_name = dealt_name
            for sn, info in seats.items():
                if info["name"] == dealt_name:
                    hero_seat = sn
                    break

    num_players = len(all_seat_nums)

    # ── Hero position ──
    if button_seat and all_seat_nums and hero_seat:
        try:
            result["position"] = _normalise_position(
                _get_position(hero_seat, button_seat, all_seat_nums, num_players)
            )
        except (ValueError, IndexError):
            pass

    # ── Blinds for BB calculation ──
    bb_size = 0
    if site_name == "Winamax":
        level_m = re.search(r"\((\d+)/(\d+(?:\.\d+)?)/(\d+(?:\.\d+)?)\)", hh_text)
        if level_m:
            bb_size = float(level_m.group(3))
        else:
            level_m = re.search(r"\((\d+(?:\.\d+)?)/(\d+(?:\.\d+)?)\)", hh_text)
            if level_m:
                bb_size = float(level_m.group(2))
    else:
        level_m = re.search(r"Level\s+\S+\s*\(([\d,]+)/([\d,]+)\)", hh_text)
        if level_m:
            bb_size = float(level_m.group(2).replace(",", ""))
        else:
            level_m = re.search(r"\(([\d,]+(?:\.\d+)?)/([\d,]+(?:\.\d+)?)\)", hh_text)
            if level_m:
                bb_size = float(level_m.group(2).replace(",", ""))

    # ── Board ──
    if site_name == "Winamax":
        board_m = re.search(r"Board:\s*\[(.+?)\]", hh_text)
        if board_m:
            result["board"] = [c.strip() for c in board_m.group(1).split() if c.strip()]
    else:
        flop_m = re.search(r"\*\*\*\s*FLOP\s*\*\*\*\s*\[(.+?)\]", hh_text)
        if flop_m:
            result["board"].extend([c.strip() for c in flop_m.group(1).split() if c.strip()])
        turn_m = re.search(r"\*\*\*\s*TURN\s*\*\*\*\s*\[.+?\]\s*\[(.+?)\]", hh_text)
        if turn_m:
            result["board"].extend([c.strip() for c in turn_m.group(1).split() if c.strip()])
        river_m = re.search(r"\*\*\*\s*RIVER\s*\*\*\*\s*\[.+?\]\s*\[(.+?)\]", hh_text)
        if river_m:
            result["board"].extend([c.strip() for c in river_m.group(1).split() if c.strip()])

    # ── Hero result (in BB) ──
    if bb_size > 0 and hero_name:
        hero_invested = 0
        hero_won = 0

        for m in re.finditer(rf"{re.escape(hero_name)}(?::)?\s+posts\s+(?:the\s+)?(?:ante|small blind|big blind)\s+([\d,.]+)", hh_text):
            hero_invested += float(m.group(1).replace(",", ""))
        for m in re.finditer(rf"{re.escape(hero_name)}(?::)?\s+(?:calls|bets)\s+([\d,.]+)", hh_text):
            hero_invested += float(m.group(1).replace(",", ""))
        for m in re.finditer(rf"{re.escape(hero_name)}(?::)?\s+raises\s+[\d,.]+\s+to\s+([\d,.]+)", hh_text):
            hero_invested += float(m.group(1).replace(",", ""))

        uncalled_m = re.search(rf"Uncalled bet \(([\d,.]+)\) returned to {re.escape(hero_name)}", hh_text)
        if uncalled_m:
            hero_invested -= float(uncalled_m.group(1).replace(",", ""))

        for m in re.finditer(rf"{re.escape(hero_name)} collected ([\d,.]+)", hh_text):
            hero_won += float(m.group(1).replace(",", ""))
        for m in re.finditer(rf"{re.escape(hero_name)} wins ([\d,.]+)", hh_text):
            hero_won += float(m.group(1).replace(",", ""))

        result["result"] = round((hero_won - hero_invested) / bb_size, 2)

    # ── Build all_players_actions with stacks, positions, level, blinds ──
    all_players = {}
    if button_seat and all_seat_nums:
        for seat_num in all_seat_nums:
            try:
                pos = _normalise_position(
                    _get_position(seat_num, button_seat, all_seat_nums, num_players)
                )
            except (ValueError, IndexError):
                pos = "?"
            info = seats.get(seat_num, {})
            name = info.get("name", f"Seat{seat_num}")
            stack = info.get("stack", 0)
            stack_bb = round(stack / bb_size, 1) if bb_size > 0 else 0
            is_hero = (seat_num == hero_seat)
            all_players[name] = {
                "seat": seat_num,
                "position": pos,
                "stack": stack,
                "stack_bb": stack_bb,
                "is_hero": is_hero,
                "bounty": info.get("bounty"),
            }

    # Extract level number
    level_num = None
    if site_name == "Winamax":
        lm = re.search(r"level:\s*(\d+)", hh_text, re.I)
        if lm:
            level_num = int(lm.group(1))
    else:
        lm = re.search(r"Level\s+([IVXLCDM]+|\d+)", hh_text, re.I)
        if lm:
            v = lm.group(1)
            roman = {"I":1,"V":5,"X":10,"L":50,"C":100,"D":500,"M":1000}
            if re.match(r"^[IVXLCDM]+$", v, re.I):
                level_num = 0
                for ci in range(len(v)):
                    cur = roman.get(v[ci].upper(), 0)
                    nxt = roman.get(v[ci+1].upper(), 0) if ci+1 < len(v) else 0
                    level_num += -cur if cur < nxt else cur
            else:
                try:
                    level_num = int(v)
                except ValueError:
                    pass

    # Extract sb_size if not already found
    sb_size = 0
    if site_name == "Winamax":
        lm2 = re.search(r"\((\d+)/(\d+(?:\.\d+)?)/(\d+(?:\.\d+)?)\)", hh_text)
        if lm2:
            sb_size = float(lm2.group(2))
        else:
            lm2 = re.search(r"\((\d+(?:\.\d+)?)/(\d+(?:\.\d+)?)\)", hh_text)
            if lm2:
                sb_size = float(lm2.group(1))
    else:
        lm2 = re.search(r"Level\s+\S+\s*\(([\d,]+)/([\d,]+)\)", hh_text)
        if lm2:
            sb_size = float(lm2.group(1).replace(",", ""))

    # Ante
    ante_size = 0
    if site_name == "Winamax":
        ante_m = re.search(r"\((\d+)/(\d+(?:\.\d+)?)/(\d+(?:\.\d+)?)\)", hh_text)
        if ante_m:
            ante_size = float(ante_m.group(1))
    else:
        ante_m = re.search(r"posts the ante ([\d,]+)", hh_text)
        if ante_m:
            ante_size = float(ante_m.group(1).replace(",", ""))

    result["all_players"] = all_players
    result["level"] = level_num
    result["sb_size"] = sb_size
    result["bb_size"] = bb_size
    result["ante_size"] = ante_size
    result["num_players"] = num_players

    return result


# ── VPIP Detection for HM3 hands ──────────────────────────────────────────────

def _detect_vpip_hm3(raw_text, hero_name=None):
    """
    Detects players who made VPIP preflop from raw HH text.
    Returns { player_name: "action_desc", ... } excluding hero.
    Works for Winamax, PokerStars, and WPN formats.
    """
    vpip_players = {}
    if not raw_text:
        return vpip_players

    # Find preflop section
    preflop_start = -1
    for marker in ["*** HOLE CARDS ***", "*** PRE-FLOP ***"]:
        idx = raw_text.find(marker)
        if idx != -1:
            preflop_start = idx
            break
    if preflop_start == -1:
        return vpip_players

    preflop_end = len(raw_text)
    for marker in ["*** FLOP ***", "*** SUMMARY ***", "*** SHOW DOWN ***"]:
        idx = raw_text.find(marker, preflop_start)
        if idx != -1 and idx < preflop_end:
            preflop_end = idx

    preflop_section = raw_text[preflop_start:preflop_end]

    for line in preflop_section.split("\n"):
        line = line.strip()
        if not line or line.startswith("***") or line.startswith("Dealt"):
            continue

        m = re.match(r"^(.+?)(?::)?\s+(.+)$", line)
        if not m:
            continue

        actor = m.group(1).strip()
        action_text = m.group(2).strip().lower()

        # Skip posts (antes/blinds)
        if "posts" in action_text:
            continue

        # Skip hero
        if hero_name and actor == hero_name:
            continue
        if actor.lower() in HERO_NAMES:
            continue

        # Check VPIP
        is_vpip = False
        action_desc = ""
        if action_text.startswith("calls"):
            is_vpip = True
            action_desc = "call"
        elif action_text.startswith("raises"):
            is_vpip = True
            action_desc = "raise"
        elif action_text.startswith("bets"):
            is_vpip = True
            action_desc = "bet"
        elif "all-in" in action_text or "all in" in action_text:
            if not action_text.startswith("folds"):
                is_vpip = True
                action_desc = "all-in"

        if is_vpip and actor not in vpip_players:
            vpip_players[actor] = action_desc

    return vpip_players


# ── CSV Import ────────────────────────────────────────────────────────────────

@router.post("/import")
async def import_hm3(
    file: UploadFile = File(...),
    days_back: int | None = None,
    nota_only: bool = False,
    current_user=Depends(require_auth),
):
    content = await file.read()
    text = content.decode("utf-8", errors="replace")

    reader = csv.DictReader(io.StringIO(text))

    # Calculate cutoff date if days_back specified
    cutoff_date = None
    if days_back and days_back > 0:
        from datetime import timedelta
        cutoff_date = datetime.utcnow() - timedelta(days=days_back)
        logger.info(f"Import filter: only hands after {cutoff_date.isoformat()}")

    hands_map = {}
    skipped_date = 0
    skipped_nota = 0
    for row in reader:
        key = (row.get("gamenumber", ""), row.get("site_id", ""))
        if key not in hands_map:
            hands_map[key] = {"tags": [], "row": row}
        tag = row.get("tag", "").strip()
        if tag and tag not in hands_map[key]["tags"]:
            hands_map[key]["tags"].append(tag)

    # Filter by date and nota if requested
    if cutoff_date or nota_only:
        filtered = {}
        for key, data in hands_map.items():
            # Check nota filter
            if nota_only:
                if not any("nota" in t.lower() for t in data["tags"]):
                    skipped_nota += 1
                    continue
            # Check date filter
            if cutoff_date:
                ts = data["row"].get("handtimestamp", "")
                if ts:
                    try:
                        hand_date = datetime.strptime(ts[:19], "%Y-%m-%d %H:%M:%S")
                        if hand_date < cutoff_date:
                            skipped_date += 1
                            continue
                    except (ValueError, IndexError):
                        pass
            filtered[key] = data
        hands_map = filtered

    if not hands_map:
        return {"status": "error", "message": "Nenhuma mão encontrada no CSV"}

    inserted = 0
    skipped = 0
    errors = []
    villains_created = 0

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            for (gamenumber, site_id), data in hands_map.items():
                row = data["row"]
                tags = data["tags"]
                site_name = SITE_MAP.get(site_id, f"Site{site_id}")
                hh_text = row.get("handhistory", "")

                parsed = _parse_hand(hh_text, site_name)
                if not parsed or not parsed["hand_id"]:
                    errors.append(f"Parse failed: {gamenumber} ({site_name})")
                    continue

                tags_clean = [t.strip() for t in tags if t.strip()]

                # Auto-tag with showdown villain nicks
                raw_text = parsed.get("raw", "")
                sd_villain_nicks = _extract_showdown_villain_tags(raw_text)
                if sd_villain_nicks:
                    tags_clean.append("showdown")
                    for nick in sd_villain_nicks:
                        if nick not in tags_clean:
                            tags_clean.append(nick)

                # Extract actions + showdown cards from raw HH
                actions_by_player, cards_by_player = _parse_actions_from_raw(raw_text, site_name)

                cur.execute(
                    "SELECT id, tags FROM hands WHERE hand_id = %s",
                    (parsed["hand_id"],)
                )
                existing = cur.fetchone()

                if existing:
                    existing_tags = existing["tags"] or []
                    merged = list(set(existing_tags + tags_clean))

                    # Build all_players_actions for update
                    import json
                    all_players = parsed.get("all_players", {})
                    all_players["_meta"] = {
                        "level": parsed.get("level"),
                        "sb": parsed.get("sb_size", 0),
                        "bb": parsed.get("bb_size", 0),
                        "ante": parsed.get("ante_size", 0),
                        "num_players": parsed.get("num_players", 0),
                    }

                    # Merge actions + showdown cards
                    for player_name, actions in actions_by_player.items():
                        if player_name in all_players and isinstance(all_players[player_name], dict):
                            all_players[player_name]["actions"] = actions
                        elif player_name != "_meta":
                            all_players[player_name] = {"actions": actions}
                    for player_name, cards in cards_by_player.items():
                        if player_name in all_players and isinstance(all_players[player_name], dict):
                            all_players[player_name]["cards"] = cards
                        elif player_name != "_meta":
                            all_players[player_name] = {"cards": cards}

                    cur.execute(
                        "UPDATE hands SET tags = %s, all_players_actions = %s WHERE id = %s",
                        (merged, json.dumps(all_players), existing["id"])
                    )

                    # Extract villains for nota++ hands (existing too)
                    if any("nota" in t.lower() for t in tags_clean):
                        dealt_m = re.search(r"Dealt to (\S+)", parsed.get("raw", ""))
                        hero = dealt_m.group(1) if dealt_m else None
                        vpip_players = _detect_vpip_hm3(parsed.get("raw", ""), hero)
                        for vp_name in vpip_players:
                            cur.execute(
                                """INSERT INTO villain_notes (site, nick, hands_seen, updated_at)
                                   VALUES (%s, %s, 1, NOW())
                                   ON CONFLICT (site, nick) DO UPDATE SET
                                       hands_seen = villain_notes.hands_seen + 1,
                                       updated_at = NOW()""",
                                (site_name, vp_name)
                            )
                            villains_created += 1

                    skipped += 1
                    continue

                # Build all_players_actions JSON with blinds metadata
                import json
                all_players = parsed.get("all_players", {})
                all_players["_meta"] = {
                    "level": parsed.get("level"),
                    "sb": parsed.get("sb_size", 0),
                    "bb": parsed.get("bb_size", 0),
                    "ante": parsed.get("ante_size", 0),
                    "num_players": parsed.get("num_players", 0),
                }

                # Merge actions + showdown cards into all_players
                for player_name, actions in actions_by_player.items():
                    if player_name in all_players and isinstance(all_players[player_name], dict):
                        all_players[player_name]["actions"] = actions
                    elif player_name != "_meta":
                        all_players[player_name] = {"actions": actions}
                for player_name, cards in cards_by_player.items():
                    if player_name in all_players and isinstance(all_players[player_name], dict):
                        all_players[player_name]["cards"] = cards
                    elif player_name != "_meta":
                        all_players[player_name] = {"cards": cards}

                cur.execute(
                    """INSERT INTO hands
                       (site, hand_id, played_at, stakes, position,
                        hero_cards, board, result, currency,
                        notes, tags, raw, study_state, all_players_actions)
                    VALUES
                       (%s, %s, %s, %s, %s,
                        %s, %s, %s, %s,
                        %s, %s, %s, 'new', %s)
                    ON CONFLICT (hand_id) DO UPDATE SET
                        tags = EXCLUDED.tags,
                        all_players_actions = EXCLUDED.all_players_actions
                    RETURNING id""",
                    (
                        parsed["site"],
                        parsed["hand_id"],
                        parsed["played_at"],
                        parsed["stakes"],
                        parsed["position"],
                        parsed["hero_cards"],
                        parsed["board"],
                        parsed["result"],
                        parsed["currency"],
                        None,
                        tags_clean,
                        parsed["raw"],
                        json.dumps(all_players),
                    )
                )
                hand_db_id = cur.fetchone()["id"]
                inserted += 1

                # Extract villains for nota++ hands
                if any("nota" in t.lower() for t in tags_clean):
                    hero_name = parsed.get("raw", "")
                    dealt_m = re.search(r"Dealt to (\S+)", parsed.get("raw", ""))
                    hero = dealt_m.group(1) if dealt_m else None
                    vpip_players = _detect_vpip_hm3(parsed.get("raw", ""), hero)
                    for vp_name, vp_action in vpip_players.items():
                        # Get position from all_players
                        vp_info = all_players.get(vp_name, {})
                        vp_pos = vp_info.get("position", "?") if isinstance(vp_info, dict) else "?"
                        # Auto-populate villain_notes
                        cur.execute(
                            """INSERT INTO villain_notes (site, nick, hands_seen, updated_at)
                               VALUES (%s, %s, 1, NOW())
                               ON CONFLICT (site, nick) DO UPDATE SET
                                   hands_seen = villain_notes.hands_seen + 1,
                                   updated_at = NOW()""",
                            (site_name, vp_name)
                        )
                        villains_created += 1

        conn.commit()
    except Exception as e:
        conn.rollback()
        logger.error(f"HM3 import error: {e}")
        raise HTTPException(status_code=500, detail=f"Erro na importação: {e}")
    finally:
        conn.close()

    return {
        "status": "ok",
        "total_rows": len(hands_map),
        "inserted": inserted,
        "skipped_duplicates": skipped,
        "skipped_date_filter": skipped_date,
        "skipped_nota_filter": skipped_nota,
        "villains_created": villains_created,
        "errors": len(errors),
        "error_log": errors[:20],
        "sites": {
            SITE_MAP.get(sid, sid): sum(1 for (_, s) in hands_map if s == sid)
            for sid in set(s for _, s in hands_map)
        },
        "top_tags": sorted(
            {t: sum(1 for d in hands_map.values() if t in d["tags"])
             for t in set(t for d in hands_map.values() for t in d["tags"])}.items(),
            key=lambda x: -x[1]
        )[:15],
    }


@router.get("/stats")
def hm3_import_stats(current_user=Depends(require_auth)):
    rows = query("""
        SELECT site, COUNT(*) as total,
               COUNT(*) FILTER (WHERE study_state = 'new') as new,
               COUNT(*) FILTER (WHERE study_state = 'review') as review,
               COUNT(*) FILTER (WHERE study_state = 'studying') as studying,
               COUNT(*) FILTER (WHERE study_state = 'resolved') as resolved
        FROM hands
        WHERE site IN ('Winamax', 'PokerStars', 'WPN')
        GROUP BY site
    """)
    return {"by_site": [dict(r) for r in rows]}


@router.get("/nota-hands")
def list_nota_hands(
    page: int = 1,
    page_size: int = 200,
    current_user=Depends(require_auth),
):
    """Lista mãos HM3 que têm tag 'nota' (qualquer variante)."""
    from fastapi import Query as Q

    count_rows = query(
        """SELECT COUNT(*) as n FROM hands
           WHERE site IN ('Winamax', 'PokerStars', 'WPN')
             AND EXISTS (SELECT 1 FROM unnest(tags) t WHERE lower(t) LIKE '%%nota%%')"""
    )
    total = count_rows[0]["n"] if count_rows else 0

    offset = (page - 1) * page_size
    rows = query(
        """SELECT id, hand_id, played_at, stakes, position,
                  hero_cards, board, result, study_state, site, tags,
                  all_players_actions
           FROM hands
           WHERE site IN ('Winamax', 'PokerStars', 'WPN')
             AND EXISTS (SELECT 1 FROM unnest(tags) t WHERE lower(t) LIKE '%%nota%%')
           ORDER BY played_at DESC NULLS LAST
           LIMIT %s OFFSET %s""",
        (page_size, offset)
    )

    import json
    result = []
    for r in rows:
        hand = dict(r)
        # Extract blinds from meta
        apa = hand.get("all_players_actions") or {}
        if isinstance(apa, str):
            apa = json.loads(apa)
        meta = apa.get("_meta", {})
        hand["blinds"] = None
        if meta.get("sb") and meta.get("bb"):
            hand["blinds"] = f"{meta['sb']}/{meta['bb']}" + (f"({meta['ante']})" if meta.get("ante") else "")
        hand["num_players"] = meta.get("num_players", 0)
        hand["tournament_name"] = hand.get("stakes")
        hand["hero_position"] = hand.get("position")
        hand["hero_result"] = float(hand["result"]) if hand.get("result") is not None else None
        hand["has_screenshot"] = False
        hand["villain_count"] = 0
        hand["villains"] = []
        # Check showdown tags
        hand["has_showdown"] = "showdown" in (hand.get("tags") or [])
        hand["showdown_villains"] = [t for t in (hand.get("tags") or []) if t not in ("showdown", "nota", "nota+", "nota++", "nota ++", "notas") and not t.startswith("#")]
        hand.pop("all_players_actions", None)
        result.append(hand)

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "hands": result,
    }


@router.get("/nota-stats")
def nota_stats(current_user=Depends(require_auth)):
    """Estatísticas de mãos HM3 com tag nota."""
    rows = query("""
        SELECT
            COUNT(*) as total_hands,
            COUNT(*) FILTER (WHERE EXISTS (SELECT 1 FROM unnest(tags) t WHERE lower(t) = 'showdown')) as with_showdown,
            COUNT(DISTINCT stakes) as tournaments,
            COUNT(DISTINCT site) as sites
        FROM hands
        WHERE site IN ('Winamax', 'PokerStars', 'WPN')
          AND EXISTS (SELECT 1 FROM unnest(tags) t WHERE lower(t) LIKE '%%nota%%')
    """)
    if rows:
        return dict(rows[0])
    return {"total_hands": 0, "with_showdown": 0, "tournaments": 0, "sites": 0}


@router.post("/cleanup-old")
def cleanup_old_hands(
    before_date: str = "2026-01-01",
    dry_run: bool = True,
    site: str = "hm3",
    current_user=Depends(require_auth),
):
    """
    Apaga mãos anteriores a uma data.
    site: 'hm3' (Winamax/PS/WPN), 'gg' (GGPoker), 'all' (todas)
    dry_run=true: só conta, não apaga.
    """
    if site == 'hm3':
        site_filter = "site IN ('Winamax', 'PokerStars', 'WPN')"
    elif site == 'gg':
        site_filter = "site = 'GGPoker'"
    elif site == 'all':
        site_filter = "1=1"
    else:
        site_filter = f"site = '{site}'"

    before_counts = query(f"""
        SELECT
            COUNT(*) as total,
            COUNT(*) FILTER (WHERE played_at < %s) as to_delete,
            COUNT(*) FILTER (WHERE played_at >= %s OR played_at IS NULL) as to_keep
        FROM hands
        WHERE {site_filter}
    """, (before_date, before_date))
    
    before = dict(before_counts[0]) if before_counts else {"total": 0, "to_delete": 0, "to_keep": 0}
    
    if dry_run:
        return {
            "dry_run": True,
            "site_filter": site,
            "before_date": before_date,
            "total_hands": before["total"],
            "would_delete": before["to_delete"],
            "would_keep": before["to_keep"],
        }
    
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(f"""
                DELETE FROM hand_villains WHERE mtt_hand_id IN (
                    SELECT id FROM hands 
                    WHERE {site_filter}
                      AND played_at < %s
                )
            """, (before_date,))
            villains_deleted = cur.rowcount
            
            cur.execute(f"""
                DELETE FROM hands 
                WHERE {site_filter}
                  AND played_at < %s
            """, (before_date,))
            hands_deleted = cur.rowcount
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Erro ao apagar: {e}")
    finally:
        conn.close()
    
    after_counts = query(f"""
        SELECT COUNT(*) as total
        FROM hands
        WHERE {site_filter}
    """)
    after_total = after_counts[0]["total"] if after_counts else 0
    
    return {
        "dry_run": False,
        "site_filter": site,
        "before_date": before_date,
        "before_total": before["total"],
        "deleted": hands_deleted,
        "villains_deleted": villains_deleted,
        "after_total": after_total,
    }


# ── Parse actions from raw HH text (multi-site) ─────────────────────────────

def _parse_actions_from_raw(raw_text, site_name=""):
    """
    Extracts actions per street per player from raw HH text.
    Works for Winamax, PokerStars, WPN, and GG formats.
    Returns { player_name: { preflop: "raises 3200", flop: "bets 2500", ... }, ... }
    Also returns cards shown: { player_name: [card1, card2], ... }
    """
    actions_by_player = {}
    cards_by_player = {}

    if not raw_text:
        return actions_by_player, cards_by_player

    is_winamax = "*** PRE-FLOP ***" in raw_text

    street_markers = [
        ("preflop", "*** PRE-FLOP ***" if is_winamax else "*** HOLE CARDS ***"),
        ("flop", "*** FLOP ***"),
        ("turn", "*** TURN ***"),
        ("river", "*** RIVER ***"),
    ]

    for street_idx, (street_name, marker) in enumerate(street_markers):
        si = raw_text.find(marker)
        if si == -1:
            continue

        # Find end of this street
        ei = len(raw_text)
        for _, next_marker in street_markers[street_idx + 1:]:
            ni = raw_text.find(next_marker, si + len(marker))
            if ni != -1:
                ei = ni
                break
        # Also check showdown/summary
        for end_marker in ["*** SHOW DOWN ***", "*** SHOW  DOWN ***", "*** SUMMARY ***"]:
            ni = raw_text.find(end_marker, si + len(marker))
            if ni != -1 and ni < ei:
                ei = ni

        section = raw_text[si + len(marker):ei]

        for line in section.split("\n"):
            t = line.strip()
            if not t or t.startswith("***") or t.startswith("Dealt") or t.startswith("Main pot"):
                continue

            # Skip posts (antes/blinds)
            if "posts" in t.lower():
                continue

            # Parse action
            m = re.match(r"^(.+?)(?::)?\s+(folds|checks|calls|bets|raises)(.*)$", t, re.I)
            if m:
                actor = m.group(1).strip()
                act = m.group(2).lower()
                rest = m.group(3)
                amount = 0
                amt_m = re.search(r"([\d,]+(?:\.\d+)?)", rest)
                if amt_m:
                    amount = float(amt_m.group(1).replace(",", ""))
                to_m = re.search(r"to\s+([\d,]+(?:\.\d+)?)", rest)
                all_in = bool(re.search(r"all-in|all in", rest, re.I))

                label = act
                if act == "calls":
                    label = f"calls {amount:.0f}"
                elif act == "bets":
                    label = f"bets {amount:.0f}"
                elif act == "raises":
                    to_val = float(to_m.group(1).replace(",", "")) if to_m else amount
                    label = f"raises to {to_val:.0f}"
                if all_in:
                    label += " all-in"

                if actor not in actions_by_player:
                    actions_by_player[actor] = {}
                # Append to existing street action (multiple actions per street possible)
                existing = actions_by_player[actor].get(street_name, "")
                if existing:
                    actions_by_player[actor][street_name] = f"{existing}, {label}"
                else:
                    actions_by_player[actor][street_name] = label

    # Parse showdown cards — handle all formats:
    # Winamax/PS/WPN: cards appear AFTER "*** SHOW DOWN ***"
    # GG: cards appear BEFORE "*** SHOWDOWN ***" (no spaces)
    # Universal approach: scan entire text for "shows [cards]" pattern
    for line in raw_text.split("\n"):
        t = line.strip()
        sm = re.match(r"^(.+?)(?::)?\s+shows\s+\[(.+?)\]", t, re.I)
        if sm:
            actor = sm.group(1).strip()
            # Skip non-player lines (e.g. "Main pot 215400.00")
            if actor.lower().startswith("main pot") or actor.startswith("***"):
                continue
            cards = [c.strip() for c in sm.group(2).split() if c.strip() and len(c.strip()) == 2]
            if cards:
                cards_by_player[actor] = cards

    return actions_by_player, cards_by_player


@router.post("/re-parse")
async def re_parse_all_hands(
    current_user=Depends(require_auth),
):
    """
    Re-parseia TODAS as mãos HM3/Winamax/PokerStars/WPN existentes na BD.
    Actualiza all_players_actions com acções por street de todos os jogadores.
    """
    import json

    # Fetch all hands that have raw text and are from HM3 sites
    hand_rows = query(
        """SELECT id, raw, all_players_actions, site, tags
           FROM hands
           WHERE raw IS NOT NULL AND raw != ''
             AND site IN ('Winamax', 'PokerStars', 'WPN', 'GGPoker')
           ORDER BY id"""
    )

    if not hand_rows:
        return {"processed": 0, "updated": 0, "errors": 0}

    processed = 0
    updated = 0
    errors = 0

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            for hand in hand_rows:
                try:
                    raw = hand.get("raw", "")
                    if not raw or len(raw) < 50:
                        continue

                    existing_apa = hand.get("all_players_actions") or {}
                    if isinstance(existing_apa, str):
                        existing_apa = json.loads(existing_apa)

                    # Parse actions from raw HH
                    actions_by_player, cards_by_player = _parse_actions_from_raw(raw, hand.get("site", ""))

                    if not actions_by_player:
                        processed += 1
                        continue

                    # Merge actions into existing all_players_actions
                    changed = False
                    for player_name, actions in actions_by_player.items():
                        if player_name in existing_apa and isinstance(existing_apa[player_name], dict):
                            if existing_apa[player_name].get("actions") != actions:
                                existing_apa[player_name]["actions"] = actions
                                changed = True
                            # Add cards if shown
                            if player_name in cards_by_player:
                                existing_apa[player_name]["cards"] = cards_by_player[player_name]
                                changed = True
                        else:
                            # Player not in all_players_actions yet (edge case)
                            # Try to find by partial match (some names may differ)
                            pass

                    if changed:
                        cur.execute(
                            "UPDATE hands SET all_players_actions = %s WHERE id = %s",
                            (json.dumps(existing_apa), hand["id"])
                        )
                        updated += 1

                    # Auto-tag with showdown villain nicks
                    sd_villain_nicks = _extract_showdown_villain_tags(raw)
                    if sd_villain_nicks:
                        existing_tags = hand.get("tags") or []
                        new_tags = list(existing_tags)
                        tags_changed = False
                        if "showdown" not in new_tags:
                            new_tags.append("showdown")
                            tags_changed = True
                        for nick in sd_villain_nicks:
                            if nick not in new_tags:
                                new_tags.append(nick)
                                tags_changed = True
                        if tags_changed:
                            cur.execute(
                                "UPDATE hands SET tags = %s WHERE id = %s",
                                (new_tags, hand["id"])
                            )
                            if not changed:
                                updated += 1

                    processed += 1

                    # Commit every 500 hands to avoid long transactions
                    if processed % 500 == 0:
                        conn.commit()

                except Exception as e:
                    errors += 1
                    if errors < 10:
                        logger.warning(f"Re-parse error hand {hand.get('id')}: {e}")

        conn.commit()
    except Exception as e:
        conn.rollback()
        logger.error(f"Re-parse error: {e}")
        raise HTTPException(status_code=500, detail=f"Erro no re-parse: {e}")
    finally:
        conn.close()

    return {
        "processed": processed,
        "updated": updated,
        "errors": errors,
        "total_hands": len(hand_rows),
    }


# ── Auto-note generator ─────────────────────────────────────────────────────

def _generate_villain_note(raw_text: str, villain_name: str, hero_name: str = None) -> str | None:
    """
    Gera nota automática compacta para um vilão com VPIP e showdown.
    Formato: [stack]BB KO[+/-/+-] LV[level] [cartas] [posição] [acções] vs [adversário] em [board]
    
    Só funciona para mãos com showdown.
    """
    if not raw_text or not villain_name:
        return None

    # ── Parse basic info ──
    is_winamax = "*** PRE-FLOP ***" in raw_text

    # Hero name
    if not hero_name:
        dm = re.search(r"Dealt to (\S+)", raw_text)
        hero_name = dm.group(1) if dm else None

    # Level
    level = "?"
    level_m = re.search(r"level:\s*(\d+)", raw_text, re.I)
    if level_m:
        level = level_m.group(1)
    else:
        level_m = re.search(r"Lv\s*(\d+)", raw_text, re.I)
        if level_m:
            level = level_m.group(1)
        else:
            # PokerStars uses Roman numerals: Level VII (400/800)
            roman_m = re.search(r"Level\s+([IVXLCDM]+)", raw_text)
            if roman_m:
                roman = roman_m.group(1).upper()
                roman_vals = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100}
                total = 0
                for i, ch in enumerate(roman):
                    val = roman_vals.get(ch, 0)
                    next_val = roman_vals.get(roman[i + 1], 0) if i + 1 < len(roman) else 0
                    total += -val if val < next_val else val
                level = str(total)
            else:
                level_m = re.search(r"Level\s+(\d+)", raw_text, re.I)
                if level_m:
                    level = level_m.group(1)

    # Blinds (BB value) — handle multiple formats
    bb_val = 1
    # Winamax: (ante/sb/bb) e.g. (60/250/500)
    blind_m = re.search(r"\((\d+)/(\d+(?:\.\d+)?)/(\d+(?:\.\d+)?)\)", raw_text)
    if blind_m:
        bb_val = float(blind_m.group(3))
    else:
        # PS: Level VII (400/800) — take second number
        ps_blind = re.search(r"Level\s+\S+\s*\(([\d,]+)/([\d,]+)\)", raw_text)
        if ps_blind:
            bb_val = float(ps_blind.group(2).replace(",", ""))
        else:
            # Generic: (sb/bb)
            blind_m2 = re.search(r"\((\d+(?:\.\d+)?)/(\d+(?:\.\d+)?)\)", raw_text)
            if blind_m2:
                bb_val = float(blind_m2.group(2))
    if bb_val == 0:
        bb_val = 1

    # Tournament format (PKO detection)
    is_pko = bool(re.search(r"bounty|PKO|KO|Progressive|Mystery", raw_text, re.I))

    # ── Parse seats: name → {stack, position, seat, bounty} ──
    seats = {}
    seat_lines = re.findall(r"Seat (\d+): (.+?) \(([\d,]+)(?:.*?(\d+(?:\.\d+)?)\s*€?\s*bounty)?\)", raw_text)
    for seat_num, name, chips, bounty in seat_lines:
        stack_chips = float(chips.replace(",", ""))
        seats[name] = {
            "stack": stack_chips,
            "stack_bb": round(stack_chips / bb_val, 1),
            "seat": int(seat_num),
            "bounty": float(bounty) if bounty else None,
        }

    # Determine button seat
    btn_m = re.search(r"Seat #(\d+) is the button", raw_text)
    btn_seat = int(btn_m.group(1)) if btn_m else 0

    # Assign positions
    player_order = sorted(seats.items(), key=lambda x: x[1]["seat"])
    num_players = len(player_order)
    
    # Find button index
    btn_idx = 0
    for i, (name, info) in enumerate(player_order):
        if info["seat"] == btn_seat:
            btn_idx = i
            break

    pos_labels_6 = ["BTN", "SB", "BB", "UTG", "MP", "CO"]
    pos_labels_8 = ["BTN", "SB", "BB", "UTG", "UTG+1", "MP", "HJ", "CO"]
    pos_labels_9 = ["BTN", "SB", "BB", "UTG", "UTG+1", "MP", "MP+1", "HJ", "CO"]
    
    if num_players <= 6:
        pos_labels = pos_labels_6[:num_players]
    elif num_players <= 8:
        pos_labels = pos_labels_8[:num_players]
    else:
        pos_labels = pos_labels_9[:num_players]

    for i, (name, info) in enumerate(player_order):
        offset = (i - btn_idx) % num_players
        if offset < len(pos_labels):
            seats[name]["position"] = pos_labels[offset]
        else:
            seats[name]["position"] = f"S{info['seat']}"

    if villain_name not in seats:
        return None

    villain = seats[villain_name]
    v_stack_bb = round(villain["stack_bb"])
    v_pos = villain["position"]

    # ── Showdown cards ──
    villain_cards = None
    for line in raw_text.split("\n"):
        sm = re.match(r"^" + re.escape(villain_name) + r"(?::)?\s+shows\s+\[(.+?)\]", line.strip(), re.I)
        if sm:
            villain_cards = sm.group(1).strip().split()
            break
    # Also check summary
    if not villain_cards:
        for line in raw_text.split("\n"):
            if villain_name in line and "showed" in line.lower():
                sm = re.search(r"\[(.+?)\]", line)
                if sm:
                    villain_cards = sm.group(1).strip().split()
                    break

    if not villain_cards or len(villain_cards) < 2:
        return None  # No showdown = no note

    # ── Board ──
    board = []
    fm = re.search(r"\*\*\* FLOP \*\*\* \[(.+?)\]", raw_text)
    if fm:
        board.extend(fm.group(1).split())
    tm = re.search(r"\*\*\* TURN \*\*\* \[.+?\]\s*\[(.+?)\]", raw_text)
    if tm:
        board.append(tm.group(1).strip())
    rm = re.search(r"\*\*\* RIVER \*\*\* \[.+?\]\s*\[(.+?)\]", raw_text)
    if rm:
        board.append(rm.group(1).strip())

    # ── Parse all actions by street ──
    streets = ["preflop", "flop", "turn", "river"]
    street_markers = [
        ("preflop", "*** PRE-FLOP ***" if is_winamax else "*** HOLE CARDS ***"),
        ("flop", "*** FLOP ***"),
        ("turn", "*** TURN ***"),
        ("river", "*** RIVER ***"),
    ]

    all_actions = {}  # street → [(actor, action, amount, all_in)]
    for st_idx, (st_name, marker) in enumerate(street_markers):
        si = raw_text.find(marker)
        if si == -1:
            continue
        ei = len(raw_text)
        for _, nm in street_markers[st_idx + 1:]:
            ni = raw_text.find(nm, si + len(marker))
            if ni != -1:
                ei = ni
                break
        for em in ["*** SHOW DOWN ***", "*** SHOW  DOWN ***", "*** SHOWDOWN ***", "*** SUMMARY ***"]:
            ni = raw_text.find(em, si + len(marker))
            if ni != -1 and ni < ei:
                ei = ni

        section = raw_text[si + len(marker):ei]
        acts = []
        for line in section.split("\n"):
            t = line.strip()
            if not t or t.startswith("***") or t.startswith("Dealt") or "posts" in t.lower() or t.startswith("Main pot"):
                continue
            m = re.match(r"^(.+?)(?::)?\s+(folds|checks|calls|bets|raises)(.*)$", t, re.I)
            if m:
                actor = m.group(1).strip()
                act = m.group(2).lower()
                rest = m.group(3)
                amount = 0
                amt_m = re.search(r"([\d,]+(?:\.\d+)?)", rest)
                if amt_m:
                    amount = float(amt_m.group(1).replace(",", ""))
                to_m = re.search(r"to\s+([\d,]+(?:\.\d+)?)", rest)
                to_val = float(to_m.group(1).replace(",", "")) if to_m else amount
                all_in = bool(re.search(r"all-in|all in", rest, re.I))
                acts.append({"actor": actor, "action": act, "amount": amount, "to": to_val, "all_in": all_in})
        all_actions[st_name] = acts

    # ── Determine pot at each street (accurate tracking) ──
    pot = 0
    # antes
    ante_m = re.findall(r"posts\s+ante\s+([\d,]+(?:\.\d+)?)", raw_text, re.I)
    for a in ante_m:
        pot += float(a.replace(",", ""))
    # blinds
    sb_m = re.search(r"posts\s+small blind\s+([\d,]+(?:\.\d+)?)", raw_text, re.I)
    sb_val = float(sb_m.group(1).replace(",", "")) if sb_m else 0
    pot += sb_val
    bb_m_pot = re.search(r"posts\s+(?:the\s+)?big blind\s+([\d,]+(?:\.\d+)?)", raw_text, re.I)
    bb_val_pot = float(bb_m_pot.group(1).replace(",", "")) if bb_m_pot else 0
    pot += bb_val_pot

    # Track pot per street, accounting for bets/calls/raises properly
    street_pots = {}  # pot BEFORE first action on this street
    player_invested = {}  # per street: how much each player has put in
    
    for st in streets:
        street_pots[st] = pot  # pot at start of street
        player_invested.clear()
        
        # For preflop, SB and BB already invested
        if st == "preflop":
            for name in seats:
                if seats[name]["position"] == "SB":
                    player_invested[name] = sb_val
                elif seats[name]["position"] == "BB":
                    player_invested[name] = bb_val_pot
        
        for a in all_actions.get(st, []):
            prev = player_invested.get(a["actor"], 0)
            if a["action"] == "calls":
                pot += a["amount"]
                player_invested[a["actor"]] = prev + a["amount"]
            elif a["action"] == "bets":
                pot += a["amount"]
                player_invested[a["actor"]] = prev + a["amount"]
            elif a["action"] == "raises":
                # "raises X to Y" — player puts in Y total this street
                # Additional cost = to_val - prev_invested
                to_val = a["to"]
                additional = to_val - prev
                if additional > 0:
                    pot += additional
                player_invested[a["actor"]] = to_val

    # ── Identify who's in the pot postflop ──
    preflop_acts = all_actions.get("preflop", [])
    players_in_pot = set()
    folded_pre = set()
    for a in preflop_acts:
        if a["action"] == "folds":
            folded_pre.add(a["actor"])
        elif a["action"] in ("calls", "raises", "bets"):
            players_in_pot.add(a["actor"])
    # BB is in pot if not folded
    for name in seats:
        if seats[name]["position"] == "BB" and name not in folded_pre:
            players_in_pot.add(name)
    # SB if called
    for name in seats:
        if seats[name]["position"] == "SB" and name not in folded_pre and name in players_in_pot:
            pass  # already added

    is_multiway = len(players_in_pot) > 2

    # ── KO +/- determination ──
    # Postflop HU: vs the opponent
    # Preflop only: vs players left to act
    # Multiway: vs all opponents in pot
    opponents_in_pot = [n for n in players_in_pot if n != villain_name]
    
    if not opponents_in_pot:
        ko_label = ""
    elif is_pko:
        covers_all = all(villain["stack"] >= seats.get(opp, {}).get("stack", 0) for opp in opponents_in_pot)
        covered_all = all(villain["stack"] <= seats.get(opp, {}).get("stack", 0) for opp in opponents_in_pot)
        if covers_all:
            ko_label = "KO+"
        elif covered_all:
            ko_label = "KO-"
        else:
            ko_label = "KO+-"
    else:
        ko_label = ""

    # ── Determine villain's key actions ──
    # Pre-flop action type
    pre_action = ""
    pre_actors_before_villain = []
    villain_pre_act = None
    first_raiser = None
    raise_count = 0

    for a in preflop_acts:
        if a["action"] == "raises":
            raise_count += 1
            if not first_raiser:
                first_raiser = a["actor"]
        if a["actor"] == villain_name:
            villain_pre_act = a
            break
        if a["action"] != "folds":
            pre_actors_before_villain.append(a)

    # Was villain preflop only (all-in pre)?
    villain_allin_pre = villain_pre_act and villain_pre_act.get("all_in", False)
    preflop_only = villain_allin_pre or len(board) == 0

    # Determine pre action label
    if villain_pre_act:
        if villain_pre_act["action"] == "raises":
            if raise_count == 1 or first_raiser == villain_name:
                if villain_pre_act.get("all_in"):
                    pre_action = "OS"  # Open Shove
                else:
                    pre_action = "OR"
            elif raise_count == 2:
                # Is it a squeeze? (OR + caller + villain raises)
                callers_before = [a for a in pre_actors_before_villain if a["action"] == "calls"]
                if callers_before:
                    pre_action = "SQZ"
                else:
                    pre_action = "3b"
                if villain_pre_act.get("all_in"):
                    pre_action += "s"  # 3bs, SQZs
            elif raise_count == 3:
                pre_action = "4b"
                if villain_pre_act.get("all_in"):
                    pre_action += "s"
            else:
                pre_action = f"{raise_count}b"
                if villain_pre_act.get("all_in"):
                    pre_action += "s"
        elif villain_pre_act["action"] == "calls":
            pre_action = "call"

    # ── Detect BvB (blind vs blind limp pot) ──
    is_bvb = False
    bvb_label = ""
    if not first_raiser and num_players >= 2:
        # No preflop raise = limp pot
        sb_name = None
        bb_name = None
        for name, info in seats.items():
            if info["position"] == "SB":
                sb_name = name
            elif info["position"] == "BB":
                bb_name = name
        if sb_name and bb_name and players_in_pot == {sb_name, bb_name}:
            is_bvb = True
            if villain_name == bb_name:
                bvb_label = "BvB"  # BB is subject
            else:
                bvb_label = "bvB"  # SB is subject

    # ── Track who's in the pot per street ──
    active_players = set(players_in_pot)  # copy
    players_in_pot_by_street = {"preflop": set(active_players)}
    
    for st in ["flop", "turn", "river"]:
        # Remove players who folded in previous streets
        for prev_st in ["preflop", "flop", "turn", "river"]:
            if prev_st == st:
                break
            for a in all_actions.get(prev_st, []):
                if a["action"] == "folds" and a["actor"] in active_players:
                    active_players.discard(a["actor"])
        # Also check folds in current street
        for a in all_actions.get(st, []):
            if a["action"] == "folds" and a["actor"] in active_players:
                active_players.discard(a["actor"])
        players_in_pot_by_street[st] = set(active_players)

    # ── Build postflop actions with full context per street ──
    postflop_parts = []
    aggressor_pre = first_raiser
    villain_was_aggressive = False
    first_street_done = False  # for MW/opponent context on first action
    
    for st in ["flop", "turn", "river"]:
        acts = all_actions.get(st, [])
        if not acts:
            continue
            
        pot_at_street = street_pots.get(st, pot)
        st_label = st[0].upper()
        
        # Who's in the pot this street?
        in_pot_this_street = players_in_pot_by_street.get(st, set())
        opponents_this_street = [n for n in in_pot_this_street if n != villain_name]
        is_mw_this_street = len(in_pot_this_street) > 2
        is_hu_this_street = len(in_pot_this_street) == 2
        
        # Get villain's actions this street
        villain_acts_this_street = [a for a in acts if a["actor"] == villain_name]
        if not villain_acts_this_street:
            continue

        for v_act in villain_acts_this_street:
            # Calculate running pot UP TO this action
            running_pot = pot_at_street
            street_invested = {}
            facing_bet_info = None  # track what villain faces
            
            for a in acts:
                if a is v_act:
                    break
                prev_inv = street_invested.get(a["actor"], 0)
                if a["action"] == "calls":
                    running_pot += a["amount"]
                    street_invested[a["actor"]] = prev_inv + a["amount"]
                elif a["action"] == "bets":
                    running_pot += a["amount"]
                    street_invested[a["actor"]] = prev_inv + a["amount"]
                    # Track facing bet for villain
                    bet_pct = round(a["amount"] / pot_at_street * 100) if pot_at_street > 0 else 0
                    actor_pos = seats.get(a["actor"], {}).get("position", "?")
                    facing_bet_info = {"actor": a["actor"], "pos": actor_pos, "pct": bet_pct, "type": "bet"}
                elif a["action"] == "raises":
                    additional = a["to"] - prev_inv
                    if additional > 0:
                        running_pot += additional
                    street_invested[a["actor"]] = a["to"]
                    # Calculate raise % relative to pot before raise
                    pot_before_raise = running_pot - additional
                    raise_pct = round(additional / pot_before_raise * 100) if pot_before_raise > 0 else 0
                    actor_pos = seats.get(a["actor"], {}).get("position", "?")
                    facing_bet_info = {"actor": a["actor"], "pos": actor_pos, "pct": raise_pct, "type": "raise"}

            # Street context suffix
            street_ctx = ""
            if first_street_done:
                if is_mw_this_street:
                    street_ctx = " MW"
                elif is_hu_this_street and opponents_this_street:
                    opp_pos = seats.get(opponents_this_street[0], {}).get("position", "?")
                    if not is_bvb:
                        street_ctx = f" vs {opp_pos}"

            if v_act["action"] == "folds":
                checks_before = [a for a in acts if a["actor"] == villain_name and a["action"] == "checks" and acts.index(a) < acts.index(v_act)]
                if checks_before:
                    postflop_parts.append(f"x/f {st_label}{street_ctx}")
                else:
                    postflop_parts.append(f"fold {st_label}{street_ctx}")

            elif v_act["action"] == "checks":
                if st == "river":
                    # GU if villain was aggressive on a previous street
                    if villain_was_aggressive:
                        postflop_parts.append(f"GU {st_label}{street_ctx}")

            elif v_act["action"] == "calls":
                # Passive but include with facing info
                if facing_bet_info:
                    fb = facing_bet_info
                    if fb["type"] == "bet":
                        if not is_bvb:
                            postflop_parts.append(f"call {st_label} {fb['pct']}% {fb['pos']}{street_ctx}")
                        else:
                            postflop_parts.append(f"call {st_label} {fb['pct']}%{street_ctx}")
                    elif fb["type"] == "raise":
                        if not is_bvb:
                            postflop_parts.append(f"call x/r {fb['pct']}% {fb['pos']}{street_ctx}")
                        else:
                            postflop_parts.append(f"call x/r {fb['pct']}%{street_ctx}")

            elif v_act["action"] in ("bets", "raises"):
                amount = v_act["amount"]
                if v_act["action"] == "raises":
                    v_prev = street_invested.get(villain_name, 0)
                    amount = v_act["to"] - v_prev
                
                pct = round(amount / running_pot * 100) if running_pot > 0 else 0
                
                # Was there a check before villain's action? (x/r)
                checks_before = [a for a in acts if a["actor"] == villain_name and a["action"] == "checks" and acts.index(a) < acts.index(v_act)]
                
                # Determine action type
                is_aggressor = (aggressor_pre == villain_name)
                
                if v_act["action"] == "raises" and checks_before:
                    # Check-raise — include facing bet info
                    if facing_bet_info and not is_bvb:
                        act_label = f"x/r {st_label} {pct}% vs bet {facing_bet_info['pct']}% {facing_bet_info['pos']}"
                    elif facing_bet_info:
                        act_label = f"x/r {st_label} {pct}% vs bet {facing_bet_info['pct']}%"
                    else:
                        act_label = f"x/r {st_label} {pct}%"
                    # Add MW context on first action
                    if not first_street_done and is_mw_this_street:
                        # Identify opponents
                        opp_descs = []
                        for opp in opponents_this_street:
                            opp_pos = seats.get(opp, {}).get("position", "?")
                            if opp != facing_bet_info.get("actor") if facing_bet_info else True:
                                # Describe what this opponent did
                                opp_acts = [a for a in acts if a["actor"] == opp]
                                if opp_acts and opp_acts[0]["action"] == "checks" and opp == aggressor_pre:
                                    opp_descs.append(f"vs mcbet {opp_pos}")
                        if opp_descs:
                            act_label += " " + " ".join(opp_descs)
                elif v_act["action"] == "bets":
                    if is_aggressor and st == "flop":
                        act_label = f"cbet {st_label} {pct}%"
                    elif is_aggressor and st == "turn":
                        # Check if cbet happened on flop
                        flop_bets = [a for a in all_actions.get("flop", []) if a["actor"] == villain_name and a["action"] in ("bets", "raises")]
                        if not flop_bets:
                            act_label = f"dcbet {st_label} {pct}%"
                        else:
                            act_label = f"bet {st_label} {pct}%"
                    elif is_aggressor:
                        act_label = f"bet {st_label} {pct}%"
                    elif not is_aggressor:
                        # Check if it's probe or donk
                        aggressor_checked = any(a["actor"] == aggressor_pre and a["action"] == "checks" for a in acts)
                        # Determine if villain is OP relative to aggressor
                        v_seat = villain.get("seat", 0)
                        agg_seat = seats.get(aggressor_pre, {}).get("seat", 0) if aggressor_pre else 0
                        
                        if aggressor_checked and st != "flop":
                            act_label = f"probe {st_label} {pct}%"
                        elif st == "flop" and not aggressor_checked:
                            act_label = f"donk {st_label} {pct}%"
                        elif st == "flop" and aggressor_checked:
                            act_label = f"bet {st_label} {pct}%"
                        else:
                            act_label = f"bet {st_label} {pct}%"
                    else:
                        act_label = f"bet {st_label} {pct}%"
                elif v_act["action"] == "raises":
                    act_label = f"raise {st_label} {pct}%"
                else:
                    act_label = f"bet {st_label} {pct}%"

                if v_act.get("all_in"):
                    act_label = f"shove {st_label} {pct}%"
                
                villain_was_aggressive = True
                
                # Add first-street MW context
                if not first_street_done:
                    if is_mw_this_street:
                        act_label = act_label  # MW added in assembly
                
                postflop_parts.append(act_label)
            
            first_street_done = True

    # ── Format cards ──
    RANK_ORDER = "AKQJT98765432"
    
    def rank_val(r):
        return RANK_ORDER.index(r) if r in RANK_ORDER else 99
    
    def format_villain_cards(cards, board_cards, preflop_only_flag):
        if not cards or len(cards) < 2:
            return "??"
        c1, c2 = cards[0], cards[1]
        r1, s1 = c1[0], c1[1] if len(c1) > 1 else ""
        r2, s2 = c2[0], c2[1] if len(c2) > 1 else ""
        
        # Sort by rank (higher first)
        if rank_val(r1) > rank_val(r2):
            r1, s1, r2, s2 = r2, s2, r1, s1
        
        # Pocket pair
        if r1 == r2:
            if preflop_only_flag:
                return f"{r1}{r2}"
            # Postflop: check if suit relevant
            board_suits = [c[1] for c in board_cards if len(c) > 1]
            suit_counts = {}
            for s in board_suits:
                suit_counts[s] = suit_counts.get(s, 0) + 1
            relevant_suits = {s for s, cnt in suit_counts.items() if cnt >= 2}
            if relevant_suits:
                s1_rel = s1 in relevant_suits
                s2_rel = s2 in relevant_suits
                if s1_rel and s2_rel:
                    return f"{r1}{s1}{r2}{s2}"
                elif s1_rel:
                    return f"{r1}{s1}{r2}x"
                elif s2_rel:
                    return f"{r1}x{r2}{s2}"
            return f"{r1}{r2}"
        
        if preflop_only_flag:
            if s1 == s2:
                return f"{r1}{r2}s"
            return f"{r1}{r2}"
        
        # Postflop: check if suits interact with board
        board_suits = [c[1] for c in board_cards if len(c) > 1]
        suit_counts = {}
        for s in board_suits:
            suit_counts[s] = suit_counts.get(s, 0) + 1
        
        relevant_suits = {s for s, cnt in suit_counts.items() if cnt >= 2}
        
        if not relevant_suits:
            if s1 == s2:
                return f"{r1}{r2}s"
            return f"{r1}{r2}"
        else:
            s1_relevant = s1 in relevant_suits
            s2_relevant = s2 in relevant_suits
            
            if s1 == s2 and s1_relevant:
                return f"{r1}{s1}{r2}{s1}"
            elif s1_relevant and s2_relevant:
                return f"{r1}{s1}{r2}{s2}"
            elif s1_relevant:
                return f"{r1}{s1}{r2}x"
            elif s2_relevant:
                return f"{r1}x{r2}{s2}"
            else:
                if s1 == s2:
                    return f"{r1}{r2}s"
                return f"{r1}{r2}"

    cards_str = format_villain_cards(villain_cards, board, preflop_only)

    # ── Format board ──
    def format_board(board_cards):
        if not board_cards:
            return ""
        
        flop = board_cards[:3] if len(board_cards) >= 3 else board_cards
        turn_card = board_cards[3] if len(board_cards) >= 4 else None
        river_card = board_cards[4] if len(board_cards) >= 5 else None

        # Flop: sort by rank descending
        rank_order = "AKQJT98765432"
        flop_sorted = sorted(flop, key=lambda c: rank_order.index(c[0]) if c[0] in rank_order else 99)
        
        # Determine flop texture
        flop_suits = [c[1] for c in flop_sorted if len(c) > 1]
        unique_suits = set(flop_suits)
        
        if len(unique_suits) == 1:
            # Monotone
            suit = flop_suits[0]
            suit_map = {"s": "S", "h": "H", "d": "D", "c": "C"}
            flop_str = "".join(c[0] for c in flop_sorted) + "m" + suit_map.get(suit, suit)
        elif len(unique_suits) == 3:
            # Rainbow
            flop_str = "".join(c[0] for c in flop_sorted) + "r"
        else:
            # Two-tone: show individual suits
            flop_str = "".join(f"{c[0]}{c[1]}" for c in flop_sorted)
        
        # Turn
        turn_str = ""
        if turn_card:
            tr = turn_card[0]
            ts = turn_card[1] if len(turn_card) > 1 else "x"
            # Is turn suit relevant? (creates flush draw or completes)
            if ts in [c[1] for c in flop if len(c) > 1]:
                turn_str = f" {tr}{ts}"
            else:
                turn_str = f" {tr}x"
        
        # River
        river_str = ""
        if river_card:
            rr = river_card[0]
            rs = river_card[1] if len(river_card) > 1 else "x"
            all_suits = [c[1] for c in board_cards[:4] if len(c) > 1]
            if rs in all_suits:
                river_str = f" {rr}{rs}"
            else:
                river_str = f" {rr}x"
        
        return flop_str + turn_str + river_str

    board_str = format_board(board)

    # ── Build opponent description ──
    # Who did villain play against?
    postflop_opponents = []
    for st in ["flop", "turn", "river"]:
        for a in all_actions.get(st, []):
            if a["actor"] != villain_name and a["actor"] not in folded_pre and a["actor"] in players_in_pot:
                opp_pos = seats.get(a["actor"], {}).get("position", a["actor"])
                if opp_pos not in postflop_opponents:
                    postflop_opponents.append(opp_pos)

    if not postflop_opponents:
        # Preflop only — list who was in the pot
        for opp in opponents_in_pot:
            opp_pos = seats.get(opp, {}).get("position", opp)
            if opp_pos not in postflop_opponents:
                postflop_opponents.append(opp_pos)

    vs_str = " e ".join(postflop_opponents) if postflop_opponents else "?"

    # ── Context: all-in players ──
    allin_others = []
    for st in streets:
        for a in all_actions.get(st, []):
            if a.get("all_in") and a["actor"] != villain_name and a["actor"] in players_in_pot:
                opp_info = seats.get(a["actor"], {})
                opp_pos = opp_info.get("position", a["actor"])
                opp_bb = round(opp_info.get("stack_bb", 0))
                allin_others.append(f"{opp_pos} {opp_bb}BB all-in")

    # ── Assemble note ──
    parts = [f"{v_stack_bb}BB"]
    if ko_label:
        parts.append(ko_label)
    if is_bvb:
        parts.append(bvb_label)
    if is_multiway and not is_bvb:
        parts.append("MW")
    parts.append(f"LV{level}")
    parts.append(cards_str)
    if not is_bvb:
        parts.append(v_pos)
    
    # Pre action — include for preflop-only OR all-in pre hands
    if pre_action and (preflop_only or villain_allin_pre):
        parts.append(pre_action)
    
    # Postflop: check if villain had NO aggressive or relevant passive actions → x ATW
    if not villain_allin_pre and not preflop_only and board:
        if not postflop_parts:
            villain_folded_post = False
            for st in ["flop", "turn", "river"]:
                for a in all_actions.get(st, []):
                    if a["actor"] == villain_name and a["action"] == "folds":
                        villain_folded_post = True
            if not villain_folded_post:
                postflop_parts.append("x ATW")
    
    # Postflop actions
    if postflop_parts:
        parts.append(", ".join(postflop_parts))
    
    # Vs — for non-BvB, non-MW first-street context
    if not is_bvb and not is_multiway:
        # Simple HU — identify opponent
        opponents = [n for n in players_in_pot if n != villain_name]
        if opponents:
            opp_pos = seats.get(opponents[0], {}).get("position", "?")
            # Describe opponent's pre-flop behavior if relevant
            if aggressor_pre and aggressor_pre in opponents:
                agg_pos = seats.get(aggressor_pre, {}).get("position", "?")
                hero_flop_bets = [a for a in all_actions.get("flop", []) if a["actor"] == aggressor_pre and a["action"] in ("bets", "raises")]
                hero_turn_bets = [a for a in all_actions.get("turn", []) if a["actor"] == aggressor_pre and a["action"] in ("bets", "raises")]
                if not hero_flop_bets and not hero_turn_bets:
                    parts.append(f"vs mcbet F+T {agg_pos}")
                elif hero_flop_bets and not hero_turn_bets:
                    parts.append(f"vs cbet F mcbet T {agg_pos}")
                elif not hero_flop_bets and hero_turn_bets:
                    parts.append(f"vs dcbet T {agg_pos}")
                else:
                    parts.append(f"vs {agg_pos}")
            else:
                parts.append(f"vs {opp_pos}")
    elif not is_bvb and is_multiway:
        # MW — opponents already described in postflop_parts per street
        # Add initial opponent list if not yet described
        if preflop_only or villain_allin_pre:
            opp_positions = []
            for opp in [n for n in players_in_pot if n != villain_name]:
                opp_pos = seats.get(opp, {}).get("position", "?")
                if opp_pos not in opp_positions:
                    opp_positions.append(opp_pos)
            parts.append(f"vs {' e '.join(opp_positions)}")
    
    # All-in context
    if allin_others:
        parts.append(f"com {', '.join(allin_others)}")
    
    # Board
    if board_str:
        parts.append(f"em {board_str}")

    note = " ".join(parts)
    note = re.sub(r"\s+", " ", note).strip()
    
    return note


@router.post("/generate-notes")
def generate_auto_notes(
    limit: int = 100,
    dry_run: bool = True,
    current_user=Depends(require_auth),
):
    """
    Gera notas automáticas para mãos com showdown e tag nota.
    dry_run=true: mostra as notas sem guardar.
    """
    import json as json_mod

    rows = query(
        """SELECT id, raw, tags, all_players_actions, site, notes
           FROM hands
           WHERE raw IS NOT NULL AND raw != ''
             AND EXISTS (SELECT 1 FROM unnest(tags) t WHERE lower(t) = 'showdown')
             AND EXISTS (SELECT 1 FROM unnest(tags) t WHERE lower(t) LIKE '%%nota%%')
             AND site IN ('Winamax', 'PokerStars', 'WPN')
           ORDER BY played_at DESC NULLS LAST
           LIMIT %s""",
        (limit,)
    )

    if not rows:
        return {"processed": 0, "notes_generated": 0, "examples": []}

    examples = []
    notes_generated = 0
    errors = 0

    conn = None if dry_run else get_conn()
    cur = None if dry_run else conn.cursor()

    try:
        for hand in rows:
            try:
                raw = hand.get("raw", "")
                tags = hand.get("tags") or []

                # Find hero
                dm = re.search(r"Dealt to (\S+)", raw)
                hero = dm.group(1) if dm else None

                # Find showdown villain nicks from tags
                sd_nicks = [t for t in tags if t not in ("showdown",) and not t.startswith("#") and not any(k in t.lower() for k in ("nota", "icm", "pko", "review", "for ", "stats"))]

                for villain_nick in sd_nicks:
                    note = _generate_villain_note(raw, villain_nick, hero)
                    if note:
                        notes_generated += 1
                        if len(examples) < 20:
                            examples.append({
                                "hand_id": hand["id"],
                                "villain": villain_nick,
                                "note": note,
                            })

                        if not dry_run and cur:
                            # Save note to hand_villains or villain_notes
                            cur.execute(
                                """UPDATE hand_villains SET villain_note = %s
                                   WHERE hand_db_id = %s AND villain_nick = %s""",
                                (note, hand["id"], villain_nick)
                            )

            except Exception as e:
                errors += 1
                if errors < 5:
                    logger.warning(f"Note gen error hand {hand.get('id')}: {e}")

        if not dry_run and conn:
            conn.commit()
    except Exception as e:
        if conn:
            conn.rollback()
        raise HTTPException(status_code=500, detail=f"Erro: {e}")
    finally:
        if conn:
            conn.close()

    return {
        "processed": len(rows),
        "notes_generated": notes_generated,
        "errors": errors,
        "dry_run": dry_run,
        "examples": examples,
    }

