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

