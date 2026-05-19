"""Tests para services/derive_max_players (pt23 fix Bug B)."""
from app.services.derive_max_players import derive_max_players


# Helpers para construir HHs PS-compat. Não usamos blinds/buttons reais —
# `derive_max_players` infere ordem do log de acções, não da posição de seats.

def _hh(seats: list[str], hero: str, preflop_actions: list[tuple[str, str]]) -> str:
    """Constrói uma HH minimal PS-compat com `seats` nicks, hero=`hero`,
    e acções preflop na ordem dada (lista de (nick, action_line)).
    """
    lines = [
        "Poker Hand #TM1: Tournament #100, Test Tourney - Level5 (200/400) - 2026/05/01 12:00:00",
        f"Table 'A' {len(seats)}-max Seat #1 is the button",
    ]
    for i, nick in enumerate(seats, start=1):
        lines.append(f"Seat {i}: {nick} (10000 in chips)")
    lines.append("*** HOLE CARDS ***")
    lines.append(f"Dealt to {hero} [As Kd]")
    for nick, action in preflop_actions:
        lines.append(f"{nick}: {action}")
    lines.append("*** SUMMARY ***")
    return "\n".join(lines) + "\n"


# ── Casos exigidos pelo spec ────────────────────────────────────────────────

def test_a_walk_to_BB_returns_2():
    """(a) UTG raise, fold até BB. Hero = BB, dobra. Vol={UTG}, atrás=0 → 2."""
    seats = ["UTG", "MP", "CO", "BTN", "SB", "Hero"]  # 6-max, Hero=BB
    hh = _hh(seats, "Hero", [
        ("UTG", "raises 800 to 1200"),
        ("MP",  "folds"),
        ("CO",  "folds"),
        ("BTN", "folds"),
        ("SB",  "folds"),
        ("Hero", "folds"),
    ])
    assert derive_max_players(hh) == 2


def test_b_UTG_raise_fold_to_hero_CO_with_3_behind_returns_5():
    """(b) UTG raise, foldados até hero CO + 3 atrás (BTN, SB, BB) → 5."""
    seats = ["UTG", "MP", "Hero", "BTN", "SB", "BB"]  # 6-max, Hero=CO
    hh = _hh(seats, "Hero", [
        ("UTG", "raises 800 to 1200"),
        ("MP",  "folds"),
        ("Hero", "calls 1200"),  # hero acts, 3 still to come (BTN/SB/BB)
    ])
    assert derive_max_players(hh) == 5


def test_c_open_call_call_hero_BTN_2_behind_returns_6():
    """(c) UTG raise, MP call, CO call, hero BTN + 2 atrás (SB/BB) → 6."""
    seats = ["UTG", "MP", "CO", "Hero", "SB", "BB"]  # 6-max, Hero=BTN
    hh = _hh(seats, "Hero", [
        ("UTG", "raises 800 to 1200"),
        ("MP",  "calls 1200"),
        ("CO",  "calls 1200"),
        ("Hero", "calls 1200"),
    ])
    assert derive_max_players(hh) == 6


def test_d_hero_UTG_raise_9max_returns_9():
    """(d) Hero UTG raise + 8 atrás 9-max → 9. Hero é primeiro a agir."""
    seats = ["Hero", "P2", "P3", "P4", "P5", "P6", "P7", "P8", "P9"]
    hh = _hh(seats, "Hero", [
        ("Hero", "raises 800 to 1200"),
        # restantes ainda não agiram → still_to_act = 8
    ])
    assert derive_max_players(hh) == 9


def test_e_UTG_raise_hero_BB_3bet_intermediate_folds_returns_2():
    """(e) UTG raise, MP/CO/BTN/SB fold, hero BB 3-bet → 2."""
    seats = ["UTG", "MP", "CO", "BTN", "SB", "Hero"]  # 6-max, Hero=BB
    hh = _hh(seats, "Hero", [
        ("UTG", "raises 800 to 1200"),
        ("MP",  "folds"),
        ("CO",  "folds"),
        ("BTN", "folds"),
        ("SB",  "folds"),
        ("Hero", "raises 3200 to 4400"),
    ])
    assert derive_max_players(hh) == 2


def test_f_UTG_limp_MP_limp_hero_CO_3_behind_returns_6():
    """(f) UTG limp, MP limp, hero CO + 3 atrás → 6 (2 vol + hero + 3 atrás)."""
    seats = ["UTG", "MP", "Hero", "BTN", "SB", "BB"]
    hh = _hh(seats, "Hero", [
        ("UTG", "calls 400"),   # limp
        ("MP",  "calls 400"),   # limp
        ("Hero", "calls 400"),  # hero limps too
    ])
    assert derive_max_players(hh) == 6


# ── Defensivos ──────────────────────────────────────────────────────────────

def test_empty_hh_returns_2():
    assert derive_max_players("") == 2
    assert derive_max_players(None) == 2  # type: ignore[arg-type]


def test_no_hole_cards_marker_falls_back_to_seat_count():
    """Sem '*** HOLE CARDS ***' não há sinal de preflop. Fallback ao
    número de seats (clamped 2..9)."""
    hh = (
        "Poker Hand #TM1: Tournament #100 ...\n"
        "Table 'A' 6-max Seat #1 is the button\n"
        "Seat 1: UTG (10000 in chips)\n"
        "Seat 2: MP (10000 in chips)\n"
        "Seat 3: CO (10000 in chips)\n"
        "Seat 4: BTN (10000 in chips)\n"
        "Seat 5: SB (10000 in chips)\n"
        "Seat 6: Hero (10000 in chips)\n"
        "Dealt to Hero [As Kd]\n"
    )
    assert derive_max_players(hh) == 6


def test_clamp_over_9_caps_at_9():
    """11 seats (impossivel real, mas defensivo) → clamp a 9."""
    seats = [f"P{i}" for i in range(1, 12)]  # 11 nicks
    seats[0] = "Hero"
    hh = _hh(seats, "Hero", [("Hero", "raises 800 to 1200")])
    assert derive_max_players(hh) == 9


def test_clamp_under_2_floors_at_2():
    """1 seat (impossivel real) → clamp a 2."""
    seats = ["Hero"]
    hh = _hh(seats, "Hero", [])
    assert derive_max_players(hh) == 2


def test_gg_pos_convert_multiple_dealt_lines_picks_real_hero():
    """pt27 regressão: HH GG após `_replace_hashes` tem `Dealt to <nick>` em
    todos os seats (não só Hero). Antes do fix, `_HERO_RE` apanhava o
    primeiro `Dealt to` (Seat 1) em vez do Hero real, gerando
    `max_players=4` em vez de 6 para `GG-5944816316`.

    Reproduz a forma exacta do HH PS-compat para essa mão: 8-handed, 2
    folds, MP open, Hero (HJ) 3-bet jam, depois 3 folds pós-Hero.
    """
    hh = (
        "Poker Hand #TM5944816316: Tournament #283300918, "
        "97-H: $525 Bounty Hunters Daily Main [Deepstack] Hold'em No Limit"
        " - Level14 (1750/3500) - 2026/05/12 21:26:48\n"
        "Table '20' 8-max Seat #8 is the button\n"
        "Seat 1: P3054-5760 (63483 in chips, $250.00 bounty)\n"
        "Seat 2: malamirca (103130 in chips, $125.00 bounty)\n"
        "Seat 3: Qyl_SH (182677 in chips, $250.00 bounty)\n"
        "Seat 4: Vermejo20 (109824 in chips, $250.00 bounty)\n"
        "Seat 5: Pinduca77 (359522 in chips, $328.12 bounty)\n"
        "Seat 6: Hero (76360 in chips)\n"
        "Seat 7: Andrii Novak (130336 in chips, $250.00 bounty)\n"
        "Seat 8: l3_3l (412314 in chips, $515.62 bounty)\n"
        "P3054-5760: posts small blind 1750\n"
        "malamirca: posts big blind 3500\n"
        "*** HOLE CARDS ***\n"
        "Dealt to P3054-5760\n"
        "Dealt to malamirca\n"
        "Dealt to Qyl_SH\n"
        "Dealt to Vermejo20\n"
        "Dealt to Pinduca77\n"
        "Dealt to Hero [Th Ah]\n"
        "Dealt to Andrii Novak\n"
        "Dealt to l3_3l\n"
        "Qyl_SH: folds\n"
        "Vermejo20: folds\n"
        "Pinduca77: raises 3500 to 7000\n"
        "Hero: raises 68860 to 75860 and is all-in\n"
        "Andrii Novak: folds\n"
        "l3_3l: folds\n"
        "P3054-5760: folds\n"
        "malamirca: folds\n"
        "*** SUMMARY ***\n"
    )
    # Pre-Hero: 2 folds + 1 voluntary (Pinduca77). Hero=BB? Não — Hero=HJ no
    # seat 6, button=8 → ordem preflop UTG=Seat 3 ... HJ=Seat 6. Hero é o 4º
    # a agir. voluntary_before={Pinduca77}, still_to_act={CO,BU,SB,BB}=4.
    # Resultado esperado: 1 + 1 + 4 = 6.
    assert derive_max_players(hh) == 6
