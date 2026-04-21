"""
Parser de Hand Histories da GGPoker (v3 — nomes reais nas acções).

O HH da GGPoker usa dois identificadores distintos:
  - Seats:   "Seat 2: NomeReal (18100 in chips)"  → nome real
  - Acções:  "89ef4cba: raises 18100 to 18100"    → ID anónimo (hash)

Este parser constrói um mapa  id_anónimo → nome_real  a partir dos seats
e substitui os IDs nas acções pelos nomes reais antes de os guardar.
"""
import re
import json
from datetime import datetime
from collections import defaultdict


# ── Position Logic ───────────────────────────────────────────────────────────

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


def _get_position(seat_num: int, button_seat: int, all_seats: list[int], num_players: int) -> str:
    """Calcula a posição de um jogador baseado no seat number e button seat."""
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
        middle_positions = pos_map[:-3]  # Remove BTN, SB, BB
        mid_idx = player_idx - 2
        if mid_idx < len(middle_positions):
            return middle_positions[mid_idx]
        return "?"


# ── Card Parser ──────────────────────────────────────────────────────────────

def _parse_cards(s: str) -> list[str]:
    """Extrai cartas de '[Ah Kd]' ou 'Ah Kd'."""
    if not s:
        return []
    s = s.strip().strip("[]")
    return [c.strip() for c in s.split() if c.strip()]


# ── Action Normaliser ────────────────────────────────────────────────────────

def _normalize_action(action_text: str, bb_size: float) -> str | None:
    """Normaliza uma acção para formato legível."""
    action_text = action_text.strip()

    if action_text == "folds":
        return "Fold"
    elif action_text == "checks":
        return "Check"
    elif action_text.startswith("calls"):
        m = re.search(r"calls\s+([\d,]+)", action_text)
        if m:
            amount = float(m.group(1).replace(",", ""))
            bb_amount = round(amount / bb_size, 1) if bb_size > 0 else amount
            suffix = " (All-In)" if "all-in" in action_text.lower() else ""
            return f"Call {bb_amount} BB{suffix}"
        return "Call"
    elif action_text.startswith("bets"):
        m = re.search(r"bets\s+([\d,]+)", action_text)
        if m:
            amount = float(m.group(1).replace(",", ""))
            bb_amount = round(amount / bb_size, 1) if bb_size > 0 else amount
            suffix = " (All-In)" if "all-in" in action_text.lower() else ""
            return f"Bet {bb_amount} BB{suffix}"
        return "Bet"
    elif action_text.startswith("raises"):
        m = re.search(r"to\s+([\d,]+)", action_text)
        if m:
            amount = float(m.group(1).replace(",", ""))
            bb_amount = round(amount / bb_size, 1) if bb_size > 0 else amount
            suffix = " (All-In)" if "all-in" in action_text.lower() else ""
            return f"Raise {bb_amount} BB{suffix}"
        return "Raise"

    return None


# ── Buy-in extractor ─────────────────────────────────────────────────────────

def _extract_buyin_numeric(tournament_name: str | None) -> float | None:
    """
    Extrai buy-in numérico total (buy-in + rake + bounty) do tournament_name.
    Formatos aceites:
      '$10+$1 Gladiator'         → 11.0
      'Bounty Builder $5'        → 5.0
      '$25+$2+$3 Zodiac'         → 30.0
    Devolve None se não encontrar nenhum padrão $X.
    """
    if not tournament_name:
        return None
    m = re.search(
        r"\$(\d+(?:\.\d+)?)\s*\+\s*\$(\d+(?:\.\d+)?)(?:\s*\+\s*\$(\d+(?:\.\d+)?))?",
        tournament_name,
    )
    if m:
        return round(sum(float(x) for x in m.groups() if x), 2)
    m = re.search(r"\$(\d+(?:\.\d+)?)", tournament_name)
    if m:
        return round(float(m.group(1)), 2)
    return None


# ── Anonymous ID → Real Name Mapper ─────────────────────────────────────────

def _build_anon_map(block: str, seats: dict) -> dict[str, str]:
    """
    Constrói um mapa  id_anónimo → nome_real  a partir do bloco HH.

    O GGPoker usa IDs anónimos nas linhas de acção (ex: "89ef4cba: raises ...").
    Estes IDs aparecem também nas linhas de seat de forma implícita — o padrão
    é que cada jogador tem um ID único de 8 caracteres hex que aparece nas acções.

    Estratégia: para cada nome real dos seats, procurar no bloco qual ID anónimo
    está associado a ele. O GGPoker inclui uma linha de mapeamento no formato:
      "PlayerName [ME]" ou simplesmente o nome aparece junto ao ID em certas versões.

    Abordagem robusta: varrer todas as linhas de acção e tentar fazer match
    com os nomes reais dos seats por exclusão / contexto.
    """
    real_names = {info["name"] for info in seats.values()}
    anon_map = {}  # anon_id → real_name

    # Padrão 1: linha explícita de mapeamento (algumas versões do GGPoker)
    # "  89ef4cba (NomeReal)"  ou  "NomeReal: [89ef4cba]"
    for name in real_names:
        # Procurar padrão: ID hex seguido do nome entre parênteses ou vice-versa
        m = re.search(
            r"\b([0-9a-f]{6,12})\b.*?\b" + re.escape(name) + r"\b",
            block, re.IGNORECASE
        )
        if m:
            anon_map[m.group(1)] = name
            continue
        m = re.search(
            r"\b" + re.escape(name) + r"\b.*?\b([0-9a-f]{6,12})\b",
            block, re.IGNORECASE
        )
        if m:
            anon_map[m.group(1)] = name

    # Padrão 2: se não encontrou mapeamento explícito, tentar por processo de
    # eliminação — os nomes reais que aparecem directamente nas acções ficam
    # como estão; os que não aparecem são substituídos pelos IDs anónimos.
    # Recolher todos os "actores" únicos nas linhas de acção
    action_actors = set()
    for line in block.split("\n"):
        line = line.strip()
        if not line or line.startswith("***") or line.startswith("Table") or line.startswith("Seat"):
            continue
        m = re.match(r"^([^:]+):\s+(.+)$", line)
        if m:
            actor = m.group(1).strip()
            action_text = m.group(2).strip()
            # Só contar se for uma acção de jogo (não posts, dealt, etc.)
            if any(action_text.startswith(k) for k in
                   ["folds", "checks", "calls", "bets", "raises", "shows", "mucks"]):
                action_actors.add(actor)

    # Os actores que são nomes reais já estão correctos
    # Os actores que parecem IDs hex (8 chars hex) precisam de mapeamento
    hex_pattern = re.compile(r'^[0-9a-f]{6,12}$', re.IGNORECASE)
    anon_actors = {a for a in action_actors if hex_pattern.match(a)}
    real_actors = {a for a in action_actors if not hex_pattern.match(a)}

    # Nomes reais dos seats que NÃO aparecem directamente nas acções
    # são os que estão "escondidos" atrás de IDs anónimos
    unmapped_names = real_names - real_actors - {"Hero"}
    unmapped_anons = anon_actors - set(anon_map.keys())

    # Se só há um nome e um ID por mapear, é match directo
    if len(unmapped_names) == 1 and len(unmapped_anons) == 1:
        anon_map[unmapped_anons.pop()] = unmapped_names.pop()

    # Se há múltiplos, tentar por ordem de seat (os IDs anónimos aparecem
    # pela primeira vez na ordem dos seats)
    elif len(unmapped_names) > 1 and len(unmapped_anons) > 0:
        # Ordenar IDs pela primeira ocorrência no bloco
        def first_occurrence(anon_id):
            idx = block.find(anon_id + ":")
            return idx if idx >= 0 else len(block)

        sorted_anons = sorted(unmapped_anons, key=first_occurrence)
        # Ordenar nomes pela ordem dos seats
        seat_order = sorted(seats.keys())
        sorted_names = [
            seats[s]["name"] for s in seat_order
            if seats[s]["name"] in unmapped_names
        ]

        for anon_id, real_name in zip(sorted_anons, sorted_names):
            anon_map[anon_id] = real_name

    return anon_map


# ── Action Parser ────────────────────────────────────────────────────────────

def _parse_actions(block: str, seats: dict, hero_name: str, bb_size: float) -> dict:
    """
    Extrai acções de todos os jogadores, organizadas por street.
    Substitui IDs anónimos pelos nomes reais dos seats.
    """
    # Construir mapa de IDs anónimos → nomes reais
    anon_map = _build_anon_map(block, seats)

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

        raw_actor = action_m.group(1).strip()
        action_text = action_m.group(2).strip()

        if "posts the ante" in action_text or "posts small blind" in action_text or "posts big blind" in action_text:
            continue

        # Resolver nome real: se o actor é um ID anónimo, substituir
        player_name = anon_map.get(raw_actor, raw_actor)

        action_norm = _normalize_action(action_text, bb_size)
        if action_norm:
            actions_by_player[player_name][street].append(action_norm)

    # Cartas do showdown — também resolver IDs anónimos
    for m in re.finditer(r"(\S+):\s+shows\s+\[(.+?)\]", block):
        raw_actor = m.group(1).strip()
        player_name = anon_map.get(raw_actor, raw_actor)
        cards_by_player[player_name] = _parse_cards(m.group(2))

    return {
        "actions_by_player": dict(actions_by_player),
        "cards_by_player": cards_by_player,
        "anon_map": anon_map,  # guardar para debug
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
        "buy_in": None,
        "all_players_actions": None,
    }

    # ── Hand ID ──
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
        result["buy_in"] = _extract_buyin_numeric(result["tournament_name"])

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

    # ── Posições ──
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
        bb_m_r = re.search(r"Hero:\s+posts big blind\s+([\d,]+)", block)
        if bb_m_r:
            hero_invested += float(bb_m_r.group(1).replace(",", ""))

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

    # ── All players actions (com nomes reais) ──
    if bb_size > 0 and seats:
        actions_data = _parse_actions(block, seats, "Hero", bb_size)

        # Extract level number
        level_num = None
        lvl_m = re.search(r"Level\s*(\d+)", block)
        if lvl_m:
            level_num = int(lvl_m.group(1))

        # Extract SB size
        sb_size = 0
        if level_m:
            sb_size = float(level_m.group(1).replace(",", ""))

        # Extract ante
        ante_size = 0
        if level_m and level_m.group(3):
            ante_size = float(level_m.group(3).replace(",", ""))
        else:
            ante_m2 = re.search(r"posts the ante\s+([\d,]+)", block)
            if ante_m2:
                ante_size = float(ante_m2.group(1).replace(",", ""))

        all_players = {}
        for seat_num, seat_info in seats.items():
            name = seat_info["name"]
            pos = seat_info.get("position", "?")
            stack_bb = round(seat_info["stack"] / bb_size, 1)

            player_actions = dict(actions_data["actions_by_player"].get(name, {}))
            cards = actions_data["cards_by_player"].get(name)

            all_players[name] = {
                "seat": seat_num,
                "position": pos,
                "stack": seat_info["stack"],
                "stack_bb": stack_bb,
                "actions": player_actions,
                "cards": cards,
                "is_hero": name == "Hero",
            }

        all_players["_meta"] = {
            "level": level_num,
            "sb": sb_size,
            "bb": bb_size,
            "ante": ante_size,
            "num_players": num_players,
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
