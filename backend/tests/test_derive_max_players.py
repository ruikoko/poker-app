"""Tests para services/derive_max_players — pt67: SPAN âncora→BB (LEI, REGRAS_NEGOCIO §15).

A derivação usa `derive_seats_in_preflop_order` (posições a partir do BOTÃO), por
isso o helper coloca o botão em `Seat #(N−2)` (n≥3) → seat `i` = posição preflop `i`
(seat 1 = UTG/first-to-act, seat N = BB). Assim os nicks podem ser nomeados pela
posição e a `hrc_idx` de cada um = (índice no `order` − 0).

Regra (Rui): `max = N − idx_âncora`, onde a âncora é (1) a posição do herói se ele
foldou antes de qualquer ação voluntária, ou (2) a 1ª ação voluntária (call/raise/bet).
"""
from app.services.derive_max_players import derive_max_players


def _hh(order: list[str], hero: str, actions: list[tuple[str, str]]) -> str:
    """HH minimal PS-compat. `order` = nicks em ORDEM PREFLOP (idx 0 = UTG/
    first-to-act, último = BB). Botão em Seat #(N−2) p/ que seat i = posição i.
    `actions` = [(nick, action_line)] na ordem em que aparecem.
    """
    n = len(order)
    btn_seat = (n - 2) if n >= 3 else 1
    lines = [
        "Poker Hand #TM1: Tournament #100, Test - Level5 (200/400) - 2026/05/01 12:00:00",
        f"Table 'A' {n}-max Seat #{btn_seat} is the button",
    ]
    for i, nick in enumerate(order, start=1):
        lines.append(f"Seat {i}: {nick} (10000 in chips)")
    lines.append("*** HOLE CARDS ***")
    lines.append(f"Dealt to {hero} [As Kd]")
    for nick, action in actions:
        lines.append(f"{nick}: {action}")
    lines.append("*** SUMMARY ***")
    return "\n".join(lines) + "\n"


# ── Regra 2 (âncora = 1ª ação voluntária) ───────────────────────────────────

def test_utg_opens_folds_to_bb_anchor_utg_6max_returns_6():
    """UTG abre, folda à volta até à BB. Âncora=UTG (idx0) → span UTG→BB = 6."""
    order = ["UTG", "MP", "CO", "BTN", "SB", "BB"]
    hh = _hh(order, "BB", [
        ("UTG", "raises 800 to 1200"),
        ("MP", "folds"), ("CO", "folds"), ("BTN", "folds"), ("SB", "folds"),
        ("BB", "folds"),
    ])
    assert derive_max_players(hh) == 6


def test_gg6029013400_shape_hero_bb_anchor_hj_8max_returns_5():
    """Cross-check GG-6029013400: 8-max, herói BB, 1ª ação no HJ (idx3).
    span HJ→BB = HJ,CO,BTN,SB,BB = 5. (O código antigo dava 2.)"""
    order = ["UTG", "UTG1", "MP", "HJ", "CO", "BTN", "SB", "BB"]
    hh = _hh(order, "BB", [
        ("UTG", "folds"), ("UTG1", "folds"), ("MP", "folds"),
        ("HJ", "raises 800 to 1200"),
        ("CO", "folds"), ("BTN", "folds"), ("SB", "folds"),
        ("BB", "calls 1200"),
    ])
    assert derive_max_players(hh) == 5


def test_gg6039094225_shape_hero_bb_anchor_sb_8max_returns_2():
    """Cross-check GG-6039094225: 8-max, herói BB, 1ª ação no SB (idx6).
    span SB→BB = 2."""
    order = ["UTG", "UTG1", "MP", "HJ", "CO", "BTN", "SB", "BB"]
    hh = _hh(order, "BB", [
        ("UTG", "folds"), ("UTG1", "folds"), ("MP", "folds"), ("HJ", "folds"),
        ("CO", "folds"), ("BTN", "folds"),
        ("SB", "raises 800 to 1200"),
        ("BB", "folds"),
    ])
    assert derive_max_players(hh) == 2


def test_gg6028190109_shape_hero_bu_anchor_hj_6max_returns_5():
    """Cross-check GG-6028190109: 6-max, herói BU(BTN), 1ª ação no HJ (idx1).
    span HJ→BB = HJ,CO,BTN,SB,BB = 5."""
    order = ["MP", "HJ", "CO", "BTN", "SB", "BB"]
    hh = _hh(order, "BTN", [
        ("MP", "folds"),
        ("HJ", "raises 800 to 1200"),
        ("CO", "folds"),
        ("BTN", "calls 1200"),
        ("SB", "folds"), ("BB", "folds"),
    ])
    assert derive_max_players(hh) == 5


def test_cap_at_6_hero_utg_opens_9max_returns_6():
    """TETO 6 (emenda Rui): herói abre de UTG (idx0) numa 9-max → span 9, mas
    `min(9, 6) = 6`."""
    order = ["UTG", "UTG1", "MP", "HJ", "CO", "BTN", "SB", "BB", "UTG2"]
    hh = _hh(order, "UTG", [("UTG", "raises 800 to 1200")])
    assert derive_max_players(hh) == 6


def test_fold_to_co_who_limps_anchor_co_6max_returns_4():
    """Foldado até ao CO (idx2) que faz limp (voluntário) → span CO→BB = 4."""
    order = ["UTG", "MP", "CO", "BTN", "SB", "BB"]
    hh = _hh(order, "BB", [
        ("UTG", "folds"), ("MP", "folds"),
        ("CO", "calls 400"),
        ("BTN", "folds"), ("SB", "folds"), ("BB", "checks"),
    ])
    assert derive_max_players(hh) == 4


def test_voluntary_before_hero_fold_is_rule2_not_rule1():
    """Herói folda, MAS o UTG já abriu antes → regra 2 (âncora UTG), NÃO regra 1.
    span UTG→BB = 6 (o herói foldar não muda a âncora)."""
    order = ["UTG", "MP", "CO", "BTN", "SB", "BB"]
    hh = _hh(order, "BB", [
        ("UTG", "raises 800 to 1200"),
        ("MP", "folds"), ("CO", "folds"), ("BTN", "folds"), ("SB", "folds"),
        ("BB", "raises 3200 to 4400"),
    ])
    assert derive_max_players(hh) == 6


# ── Regra 1 (herói foldou ANTES de qualquer ação voluntária) ─────────────────

def test_rule1_hero_folds_unopened_co_8max_returns_4():
    """Pote por abrir até ao herói (CO, idx4) que folda → âncora=herói.
    span CO→BB = CO,BTN,SB,BB = 4. (Regra 1 — antes nunca exercitada.)"""
    order = ["UTG", "UTG1", "MP", "HJ", "CO", "BTN", "SB", "BB"]
    hh = _hh(order, "CO", [
        ("UTG", "folds"), ("UTG1", "folds"), ("MP", "folds"), ("HJ", "folds"),
        ("CO", "folds"),
    ])
    assert derive_max_players(hh) == 4


def test_rule1_hero_folds_unopened_utg1_8max_capped_at_6():
    """Pote por abrir até ao herói UTG1 (idx1) que folda → span UTG1→BB = 7,
    mas o TETO 6 corta para 6."""
    order = ["UTG", "UTG1", "MP", "HJ", "CO", "BTN", "SB", "BB"]
    hh = _hh(order, "UTG1", [
        ("UTG", "folds"),
        ("UTG1", "folds"),
    ])
    assert derive_max_players(hh) == 6


# ── Degenerados / defensivos ────────────────────────────────────────────────

def test_walk_to_bb_no_voluntary_returns_2():
    """Foldado até à BB, sem ação voluntária e a BB não folda (walk) →
    convenção SB-vs-BB = 2."""
    order = ["UTG", "MP", "CO", "BTN", "SB", "BB"]
    hh = _hh(order, "BB", [
        ("UTG", "folds"), ("MP", "folds"), ("CO", "folds"), ("BTN", "folds"),
        ("SB", "folds"), ("BB", "checks"),
    ])
    assert derive_max_players(hh) == 2


def test_empty_hh_returns_2():
    assert derive_max_players("") == 2
    assert derive_max_players(None) == 2  # type: ignore[arg-type]


def test_no_preflop_marker_returns_2():
    """Sem '*** HOLE CARDS ***'/'*** PRE-FLOP ***' não há bloco preflop → 2."""
    hh = (
        "Poker Hand #TM1: Tournament #100 ...\n"
        "Table 'A' 6-max Seat #4 is the button\n"
        "Seat 1: UTG (10000 in chips)\n"
        "Seat 2: MP (10000 in chips)\n"
        "Seat 6: BB (10000 in chips)\n"
    )
    assert derive_max_players(hh) == 2


def test_clamp_under_2_floors_at_2():
    """< 2 seats → 2."""
    hh = _hh(["Hero"], "Hero", [])
    assert derive_max_players(hh) == 2


def test_nicks_with_spaces_counted():
    """Nicks com espaços (nomes reais GG) são contados — `derive_seats` usa
    `.+?`, não `\\S+`. 6-max, foldado até ao HJ ('Andrii Novak', idx1) que abre
    → span HJ→BB = 5 (discrimina: se o nick com espaço fosse saltado, N e
    posições mudavam)."""
    order = ["MP", "Andrii Novak", "CO", "BTN", "SB", "Hero Two"]
    hh = _hh(order, "Hero Two", [
        ("MP", "folds"),
        ("Andrii Novak", "raises 800 to 1200"),
        ("CO", "folds"), ("BTN", "folds"), ("SB", "folds"), ("Hero Two", "folds"),
    ])
    assert derive_max_players(hh) == 5


# ── Regressão real (mantida de pt27) — bate com o SPAN: âncora MP → 6 ────────

def test_gg5944816316_real_8max_anchor_mp_returns_6():
    """GG-5944816316 real: 8-handed, button=Seat8. 2 folds (Qyl_SH, Vermejo20),
    MP open (Pinduca77, idx2), Hero=HJ 3-bet jam. span MP→BB = 6.
    (Coincide com o resultado pt27 antigo — mantém-se.)"""
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
    assert derive_max_players(hh) == 6


# ── Winamax (sem colon nas action lines) — #WN-COLON-BLIND-MAX-PLAYERS ───────
# Antes do fix, `_ACTION_RE` exigia ": " e cegava TODA a Winamax (linhas
# "nick folds", sem colon) → âncora nunca detectada → fallback max=2.

def _hh_winamax(order, hero, actions, button_seat=None):
    """HH minimal estilo Winamax: action lines SEM colon ("nick folds")."""
    n = len(order)
    btn_seat = button_seat if button_seat else ((n - 2) if n >= 3 else 1)
    lines = [
        'Winamax Poker - Tournament "GRAVITY" buyIn: 232€ level: 5 - HandId: '
        "#1-2-3 - Holdem no limit (200/400) - 2026/06/15 17:07:17 UTC",
        f"Table: 'T' {n}-max (real money) Seat #{btn_seat} is the button",
    ]
    for i, nick in enumerate(order, start=1):
        lines.append(f"Seat {i}: {nick} (10000)")
    lines.append("*** PRE-FLOP ***")
    lines.append(f"Dealt to {hero} [3s 8h]")
    for nick, action in actions:           # SEM colon (formato Winamax)
        lines.append(f"{nick} {action}")
    lines.append("*** SUMMARY ***")
    return "\n".join(lines) + "\n"


def test_winamax_hero_btn_fold_around_anchor_btn_returns_3():
    """GRAVITY real: Hero BTN, fold-around (Hero folda também). Âncora = BTN
    (regra 1, fold do herói) → span BTN→BB = 3. Antes do fix dava 2."""
    order = ["MP", "HJ", "CO", "BTN", "SB", "BB"]
    hh = _hh_winamax(order, "BTN", [
        ("MP", "folds"), ("HJ", "folds"), ("CO", "folds"),
        ("BTN", "folds"), ("SB", "folds"),
    ])
    assert derive_max_players(hh) == 3


def test_winamax_voluntary_open_anchor_at_opener():
    """Winamax sem colon, CO abre (1ª ação voluntária). Âncora=CO (idx2) →
    span CO→BB = 4. Confirma regra 2 com linhas sem colon."""
    order = ["MP", "HJ", "CO", "BTN", "SB", "BB"]
    hh = _hh_winamax(order, "BTN", [
        ("MP", "folds"), ("HJ", "folds"), ("CO", "raises 400 to 800"),
    ])
    assert derive_max_players(hh) == 4
