"""
Parser de Hand Histories da GGPoker.
Extrai mãos individuais de ficheiros .txt de HH.
Devolve lista de dicts prontos para inserção em hands.
"""
import re
from datetime import datetime


def _parse_cards(s: str) -> list[str]:
    """Extrai cartas de uma string como '[Ah Kd]' ou 'Ah Kd'."""
    if not s:
        return []
    s = s.strip().strip("[]")
    return [c.strip() for c in s.split() if c.strip()]


def _parse_single_hand(block: str) -> dict | None:
    """Parseia um bloco de texto de uma mão GG."""
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
        "players": [],
        "actions": [],
        "tournament_name": None,
        "tournament_id": None,
        "buyin": None,
    }

    # Hand ID e data
    hid_m = re.search(r"Hand\s*#(?:TM|RC)?(\d+)", block)
    if hid_m:
        result["hand_id"] = f"GG-{hid_m.group(1)}"

    # Data
    date_m = re.search(r"(\d{4})[/-](\d{2})[/-](\d{2})\s+(\d{1,2}):(\d{2}):(\d{2})", block)
    if date_m:
        try:
            result["played_at"] = datetime(
                int(date_m.group(1)), int(date_m.group(2)), int(date_m.group(3)),
                int(date_m.group(4)), int(date_m.group(5)), int(date_m.group(6)),
            ).isoformat()
        except ValueError:
            pass

    # Stakes / Blinds
    stakes_m = re.search(r"Level\s*\d+\s*\(([\d,.]+)/([\d,.]+)\)", block)
    if not stakes_m:
        stakes_m = re.search(r"\(([\d,.]+)/([\d,.]+)\)", block)
    if stakes_m:
        result["stakes"] = f"{stakes_m.group(1)}/{stakes_m.group(2)}"

    # Tournament info
    tourney_m = re.search(r"Tournament\s*#(\d+)", block)
    if tourney_m:
        result["tournament_id"] = tourney_m.group(1)

    name_m = re.search(r"Tournament\s*#\d+\s*,?\s*(.+?)(?:\s*-\s*Level|\s*$)", block, re.M)
    if name_m:
        result["tournament_name"] = name_m.group(1).strip().rstrip(",")

    buyin_m = re.search(r"Buy-[Ii]n(?:\s*:)?\s*\$?([\d,.]+)", block)
    if buyin_m:
        result["buyin"] = buyin_m.group(1).replace(",", "")

    # Hero e posição
    hero_m = re.search(r"Dealt to (.+?)\s*\[(.+?)\]", block)
    if hero_m:
        hero_name = hero_m.group(1).strip()
        result["hero_cards"] = _parse_cards(hero_m.group(2))

        # Encontrar posição do hero
        seat_m = re.search(
            rf"Seat\s+\d+:\s*{re.escape(hero_name)}\s*\(.*?\)\s*$",
            block, re.M
        )
        if seat_m:
            seat_line = seat_m.group(0)
        else:
            seat_m = re.search(rf"^.*{re.escape(hero_name)}.*$", block, re.M)
            seat_line = seat_m.group(0) if seat_m else ""

        # Posição a partir das linhas de acção
        pos_patterns = [
            (r"Small Blind", "SB"),
            (r"Big Blind", "BB"),
            (r"Dealer", "BTN"),
            (r"Button", "BTN"),
        ]
        for pat, pos in pos_patterns:
            if re.search(rf"{re.escape(hero_name)}.*{pat}", block, re.I):
                result["position"] = pos
                break

        if not result["position"]:
            # Tentar extrair de "Seat N: hero (pos)"
            pos_m = re.search(
                rf"Seat\s+\d+:\s*{re.escape(hero_name)}\s*\(([^)]+)\)",
                block
            )
            if pos_m:
                pos_raw = pos_m.group(1).strip().upper()
                pos_map = {
                    "SMALL BLIND": "SB", "BIG BLIND": "BB",
                    "BUTTON": "BTN", "DEALER": "BTN",
                    "UTG": "UTG", "UTG+1": "UTG+1", "UTG+2": "UTG+2",
                    "MP": "MP", "HJ": "HJ", "CO": "CO",
                    "LJ": "LJ",
                }
                for key, val in pos_map.items():
                    if key in pos_raw:
                        result["position"] = val
                        break

    # Board
    board_cards = []
    # Flop: *** FLOP *** [Ks 7h 2c]
    flop_m = re.search(r"\*\*\*\s*FLOP\s*\*\*\*\s*\[(.+?)\]", block)
    if flop_m:
        board_cards.extend(_parse_cards(flop_m.group(1)))
    # Turn: *** TURN *** [Ks 7h 2c] [Td]  — queremos só a última carta
    turn_m = re.search(r"\*\*\*\s*TURN\s*\*\*\*\s*\[.+?\]\s*\[(.+?)\]", block)
    if turn_m:
        board_cards.extend(_parse_cards(turn_m.group(1)))
    # River: *** RIVER *** [Ks 7h 2c Td] [Jh]  — queremos só a última carta
    river_m = re.search(r"\*\*\*\s*RIVER\s*\*\*\*\s*\[.+?\]\s*\[(.+?)\]", block)
    if river_m:
        board_cards.extend(_parse_cards(river_m.group(1)))
    result["board"] = board_cards

    # Jogadores envolvidos (todos os que têm seat)
    players = []
    for sm in re.finditer(r"Seat\s+(\d+):\s*(.+?)\s*\(", block):
        players.append(sm.group(2).strip())
    result["players"] = players

    # Resultado do hero
    if hero_m:
        hero_name = hero_m.group(1).strip()
        # Procurar "hero collected X"
        won_m = re.search(
            rf"{re.escape(hero_name)}\s+collected\s+\$?([\d,.]+)",
            block, re.I
        )
        if won_m:
            result["result"] = float(won_m.group(1).replace(",", ""))

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

    # Separar por blocos de mão (cada mão começa com "Poker Hand #" ou "Hand #")
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
