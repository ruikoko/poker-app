"""
Parser de Hand Histories da GGPoker (v2 — melhorado).
Extrai mãos individuais de ficheiros .txt de HH.
Devolve lista de dicts prontos para inserção em hands.

Melhorias sobre v1:
- Posições correctas baseadas em seat/button (não em regex frágil)
- all_players_actions com acções de todos os jogadores por street
- Resultado em BB (net chips / bb_size)
- Cartas do showdown
"""
import re
import json
from datetime import datetime
from collections import defaultdict


# ── Position Logic ───────────────────────────────────────────────────────────

POSITION_MAPS = {
    2: ["SB", "BB"],
    3: ["BTN", "SB", "BB"],
    4: ["CO", "BTN", "SB", "BB"],
    5: ["UTG", "CO", "BTN", "SB", "BB"],
    6: ["UTG", "MP", "CO", "BTN", "SB", "BB"],
    7: ["UTG", "UTG1", "MP", "CO", "BTN", "SB", "BB"],
    8: ["UTG", "UTG1", "MP", "MP1", "CO", "BTN", "SB", "BB"],
    9: ["UTG", "UTG1", "MP", "MP1", "HJ", "CO", "BTN", "SB", "BB"],
    10: ["UTG", "UTG1", "UTG2", "MP", "MP1", "HJ", "CO", "BTN", "SB", "BB"],
}


def _get_position(seat_num: int, button_seat: int, all_seats: list[int], num_players: int) -> str:
    """Calcula a posição de um jogador baseado no seat number e button seat."""
    sorted_seats = sorted(all_seats)

    if num_players == 2:
        if seat_num == button_seat:
            return "SB"
        else:
            return "BB"

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
        middle_positions = pos_map[:-3]  # Remove BTN, SB, BB
        mid_idx = player_idx - 2
        if mid_idx < len(middle_positions):
            return middle_positions[mid_idx]
        else:
            return "?"


# ── Card Parser ──────────────────────────────────────────────────────────────

def _parse_cards(s: str) -> list[str]:
    """Extrai cartas de '[Ah Kd]' ou 'Ah Kd'."""
    if not s:
        return []
    s = s.strip().strip("[]")
    return [c.strip() for c in s.split() if c.strip()]


# ── Action Parser ────────────────────────────────────────────────────────────

def _normalize_action(action_text: str, bb_size: float) -> str | None:
    """Normaliza uma acção para formato legível."""
    action_text = action_text.strip()

    if action_text == "folds":
        return "Fold"
    elif action_text == "checks":
        return "Check"
    elif action_text.startswith("calls"):
        amount_m = re.search(r"calls\s+([\d,]+)", action_text)
        if amount_m:
            amount = float(amount_m.group(1).replace(",", ""))
            bb_amount = round(amount / bb_size, 1) if bb_size > 0 else amount
            suffix = " (All-In)" if "all-in" in action_text.lower() else ""
            return f"Call {bb_amount} BB{suffix}"
        return "Call"
    elif action_text.startswith("bets"):
        amount_m = re.search(r"bets\s+([\d,]+)", action_text)
        if amount_m:
            amount = float(amount_m.group(1).replace(",", ""))
            bb_amount = round(amount / bb_size, 1) if bb_size > 0 else amount
            suffix = " (All-In)" if "all-in" in action_text.lower() else ""
            return f"Bet {bb_amount} BB{suffix}"
        return "Bet"
    elif action_text.startswith("raises"):
        to_m = re.search(r"to\s+([\d,]+)", action_text)
        if to_m:
            amount = float(to_m.group(1).replace(",", ""))
            bb_amount = round(amount / bb_size, 1) if bb_size > 0 else amount
            suffix = " (All-In)" if "all-in" in action_text.lower() else ""
            return f"Raise {bb_amount} BB{suffix}"
        return "Raise"

    return None


def _parse_actions(block: str, seats: dict, hero_name: str, bb_size: float) -> dict:
    """Extrai acções de todos os jogadores, organizadas por street."""
    street = "preflop"
    lines = block.split("\n")

    actions_by_player = defaultdict(lambda: defaultdict(list))
    cards_by_player = {}

    for line in lines:
        line = line.strip()

        if "*** FLOP ***" in line:
            street = "flop"
            continue
        elif "*** TURN ***" in line:
            street = "turn"
            continue
        elif "*** RIVER ***" in line:
            street = "river"
            continue
        elif "*** SHOWDOWN ***" in line or "*** SUMMARY ***" in line:
            break

        if line.startswith("Dealt to") or line.startswith("Seat ") or line.startswith("Table "):
            continue
        if line.startswith("***") or line.startswith("Uncalled"):
            continue

        action_m = re.match(r"^(.+?):\s+(.+)$", line)
        if not action_m:
            continue

        player_name = action_m.group(1).strip()
        action_text = action_m.group(2).strip()

        if "posts the ante" in action_text or "posts small blind" in action_text or "posts big blind" in action_text:
            continue

        action_norm = _normalize_action(action_text, bb_size)
        if action_norm:
            actions_by_player[player_name][street].append(action_norm)

    # Cartas do showdown
    for m in re.finditer(r"(\S+):\s+shows\s+\[(.+?)\]", block):
        cards_by_player[m.group(1).strip()] = _parse_cards(m.group(2))

    return {
        "actions_by_player": dict(actions_by_player),
        "cards_by_player": cards_by_player,
    }


# ── Single Hand Parser ───────────────────────────────────────────────────────

def _parse_single_hand(block: str) -> dict | None:
    """Parseia um bloco de texto de uma mão GG com extracção completa."""
    if not block.strip():
        return None

    result = {
        "site": "GGPoker",
        "hand_id": None,
        "played_at": None,
        "stakes": None,
        "position": None,
        "hero_cards": [],
        "board": [],
        "result": None,
        "currency": "$",
        "raw": block.strip(),
        "tournament_name": None,
        "tournament_id": None,
        "all_players_actions": None,
    }

    # ── Hand ID (TM number) ──
    hid_m = re.search(r"Hand\s*#(?:TM|RC)?(\d+)", block)
    if hid_m:
        result["hand_id"] = f"GG-{hid_m.group(1)}"
    else:
        return None

    # ── Tournament info ──
    tourney_m = re.search(r"Tournament\s*#(\d+)", block)
    if tourney_m:
        result["tournament_id"] = tourney_m.group(1)

    name_m = re.search(r"Tournament\s*#\d+\s*,?\s*(.+?)(?:\s+Hold'em|\s*$)", block, re.M)
    if name_m:
        result["tournament_name"] = name_m.group(1).strip().rstrip(",")

    # ── Date ──
    date_m = re.search(r"(\d{4})[/-](\d{2})[/-](\d{2})\s+(\d{1,2}):(\d{2}):(\d{2})", block)
    if date_m:
        try:
            result["played_at"] = datetime(
                int(date_m.group(1)), int(date_m.group(2)), int(date_m.group(3)),
                int(date_m.group(4)), int(date_m.group(5)), int(date_m.group(6)),
            ).isoformat()
        except ValueError:
            pass

    # ── Blinds / Level ──
    level_m = re.search(r"Level\s*\d+\s*\(([\d,]+)/([\d,]+)(?:\(([\d,]+)\))?\)", block)
    sb_size = 0
    bb_size = 0
    if level_m:
        sb_size = float(level_m.group(1).replace(",", ""))
        bb_size = float(level_m.group(2).replace(",", ""))
        result["stakes"] = result["tournament_name"] or f"{sb_size}/{bb_size}"

    # ── Table info (button seat) ──
    table_m = re.search(r"Table\s+'[^']*'\s+(\d+)-max\s+Seat\s*#(\d+)\s+is the button", block)
    button_seat = None
    if table_m:
        button_seat = int(table_m.group(2))

    # ── Seats ──
    seats = {}
    all_seat_nums = []
    hero_seat = None

    for sm in re.finditer(r"Seat\s+(\d+):\s*(.+?)\s*\(([\d,]+)\s+in chips\)", block):
        seat_num = int(sm.group(1))
        name = sm.group(2).strip()
        stack = float(sm.group(3).replace(",", ""))
        seats[seat_num] = {"name": name, "stack": stack}
        all_seat_nums.append(seat_num)
        if name == "Hero":
            hero_seat = seat_num

    num_players = len(all_seat_nums)

    # ── Calcular posições ──
    if button_seat and all_seat_nums:
        for seat_num in all_seat_nums:
            pos = _get_position(seat_num, button_seat, all_seat_nums, num_players)
            seats[seat_num]["position"] = pos

        if hero_seat:
            result["position"] = seats[hero_seat].get("position", "?")

    # ── Hero cards ──
    hero_m = re.search(r"Dealt to Hero\s*\[(.+?)\]", block)
    if hero_m:
        result["hero_cards"] = _parse_cards(hero_m.group(1))

    # ── Board ──
    board_cards = []
    flop_m = re.search(r"\*\*\*\s*FLOP\s*\*\*\*\s*\[(.+?)\]", block)
    if flop_m:
        board_cards.extend(_parse_cards(flop_m.group(1)))
    turn_m = re.search(r"\*\*\*\s*TURN\s*\*\*\*\s*\[.+?\]\s*\[(.+?)\]", block)
    if turn_m:
        board_cards.extend(_parse_cards(turn_m.group(1)))
    river_m = re.search(r"\*\*\*\s*RIVER\s*\*\*\*\s*\[.+?\]\s*\[(.+?)\]", block)
    if river_m:
        board_cards.extend(_parse_cards(river_m.group(1)))
    result["board"] = board_cards

    # ── Result (em BB) ──
    if bb_size > 0:
        hero_invested = 0
        hero_won = 0

        ante_m = re.search(r"Hero:\s+posts the ante\s+([\d,]+)", block)
        if ante_m:
            hero_invested += float(ante_m.group(1).replace(",", ""))

        sb_m = re.search(r"Hero:\s+posts small blind\s+([\d,]+)", block)
        if sb_m:
            hero_invested += float(sb_m.group(1).replace(",", ""))
        bb_m = re.search(r"Hero:\s+posts big blind\s+([\d,]+)", block)
        if bb_m:
            hero_invested += float(bb_m.group(1).replace(",", ""))

        for am in re.finditer(r"Hero:\s+(?:calls|bets)\s+([\d,]+)", block):
            hero_invested += float(am.group(1).replace(",", ""))
        for am in re.finditer(r"Hero:\s+raises\s+[\d,]+\s+to\s+([\d,]+)", block):
            hero_invested += float(am.group(1).replace(",", ""))

        uncalled_m = re.search(r"Uncalled bet \(([\d,]+)\) returned to Hero", block)
        if uncalled_m:
            hero_invested -= float(uncalled_m.group(1).replace(",", ""))

        for wm in re.finditer(r"Hero collected ([\d,]+) from", block):
            hero_won += float(wm.group(1).replace(",", ""))

        net = hero_won - hero_invested
        result["result"] = round(net / bb_size, 2)

    # ── All players actions ──
    if bb_size > 0:
        actions_data = _parse_actions(block, seats, "Hero", bb_size)

        all_players = {}
        for seat_num, seat_info in seats.items():
            name = seat_info["name"]
            pos = seat_info.get("position", "?")
            stack_bb = round(seat_info["stack"] / bb_size, 1)

            player_actions = {}
            raw_actions = actions_data["actions_by_player"].get(name, {})
            for st, acts in raw_actions.items():
                player_actions[st] = acts

            cards = actions_data["cards_by_player"].get(name)

            all_players[name] = {
                "seat": seat_num,
                "position": pos,
                "stack_bb": stack_bb,
                "actions": player_actions,
                "cards": cards,
                "is_hero": name == "Hero",
            }

        result["all_players_actions"] = all_players

    return result


def parse_hands(content: bytes, filename: str) -> tuple[list[dict], list[str]]:
    """
    Parseia um ficheiro de HH da GG.
    Devolve (hands, errors).
    """
    hands = []
    errors = []

    try:
        text = content.decode("utf-8", errors="replace")
    except Exception as e:
        return [], [f"Erro a ler ficheiro: {e}"]

    blocks = re.split(r"(?=(?:Poker\s+)?Hand\s*#)", text)

    for i, block in enumerate(blocks):
        block = block.strip()
        if not block or len(block) < 50:
            continue
        try:
            hand = _parse_single_hand(block)
            if hand and hand["hand_id"]:
                hands.append(hand)
            elif block.strip():
                errors.append(f"Bloco {i}: não reconhecido como mão válida")
        except Exception as e:
            errors.append(f"Bloco {i}: {e}")

    return hands, errors
