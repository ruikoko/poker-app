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
