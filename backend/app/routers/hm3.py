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
}

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

    # ── Seats ──
    seats = {}
    all_seat_nums = []
    hero_seat = None
    hero_name = None

    if site_name == "Winamax":
        for sm in re.finditer(r"Seat\s+(\d+):\s*(.+?)\s*\(([\d.]+)(?:,\s*[^)]+)?\)", hh_text):
            seat_num = int(sm.group(1))
            name = sm.group(2).strip()
            stack = float(sm.group(3).replace(",", ""))
            seats[seat_num] = {"name": name, "stack": stack}
            all_seat_nums.append(seat_num)
            if name.lower() in HERO_NAMES:
                hero_seat = seat_num
                hero_name = name
    else:
        for sm in re.finditer(r"Seat\s+(\d+):\s*(.+?)\s*\(([\d,]+)\s+in chips", hh_text):
            seat_num = int(sm.group(1))
            name = sm.group(2).strip()
            stack = float(sm.group(3).replace(",", ""))
            seats[seat_num] = {"name": name, "stack": stack}
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


# ── CSV Import ────────────────────────────────────────────────────────────────

@router.post("/import")
async def import_hm3(
    file: UploadFile = File(...),
    current_user=Depends(require_auth),
):
    content = await file.read()
    text = content.decode("utf-8", errors="replace")

    reader = csv.DictReader(io.StringIO(text))

    hands_map = {}
    for row in reader:
        key = (row.get("gamenumber", ""), row.get("site_id", ""))
        if key not in hands_map:
            hands_map[key] = {"tags": [], "row": row}
        tag = row.get("tag", "").strip()
        if tag and tag not in hands_map[key]["tags"]:
            hands_map[key]["tags"].append(tag)

    if not hands_map:
        return {"status": "error", "message": "Nenhuma mão encontrada no CSV"}

    inserted = 0
    skipped = 0
    errors = []

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

                cur.execute(
                    "SELECT id, tags FROM hands WHERE hand_id = %s",
                    (parsed["hand_id"],)
                )
                existing = cur.fetchone()

                if existing:
                    existing_tags = existing["tags"] or []
                    merged = list(set(existing_tags + tags_clean))
                    if set(merged) != set(existing_tags):
                        cur.execute(
                            "UPDATE hands SET tags = %s WHERE id = %s",
                            (merged, existing["id"])
                        )
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
                inserted += 1

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
