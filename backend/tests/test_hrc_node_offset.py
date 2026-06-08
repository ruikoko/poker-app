"""pt25e Bloco 2 piece 2 — tests para `compute_target_node_offset`.

Strategy Table HRC ordem validada empíricamente:
    UTG → (EP/MP/HJ consoante N) → CO → BU → SB
    (BB nunca aparece — não abre preflop.)

Cada non-blind expande para `len(SIZES_OPEN_*)` linhas (1 ou 2). SB tem
+1 linha de Complete antes das opens. Aggressor com `size_bb >= 95%`
da stack do raiser conta como all-in efectivo.
"""
from app.services.hrc_node_offset import (
    _ALL_IN_EFFECTIVE_THRESHOLD,
    _is_all_in_effective,
    compute_target_node_offset,
    count_lines_for_position,
    derive_aggressor_stack_bb,
    offset_within_bucket,
    strategy_table_positions,
)


# ── strategy_table_positions ────────────────────────────────────────────

def test_strategy_table_positions_drops_BB_for_all_N():
    """BB nunca está na Strategy Table — drop independente do N."""
    for n in range(2, 10):
        positions = strategy_table_positions(n)
        assert "BB" not in positions


def test_strategy_table_positions_keeps_other_labels_in_order():
    """Mantém a ordem do `_POSITION_LABELS_BY_N` (UTG primeiro, SB último)."""
    assert strategy_table_positions(2) == ["SB"]
    assert strategy_table_positions(3) == ["BTN", "SB"]
    assert strategy_table_positions(4) == ["CO", "BTN", "SB"]
    assert strategy_table_positions(5) == ["HJ", "CO", "BTN", "SB"]
    assert strategy_table_positions(6) == ["MP", "HJ", "CO", "BTN", "SB"]
    assert strategy_table_positions(8) == [
        "UTG", "UTG1", "MP", "HJ", "CO", "BTN", "SB",
    ]


def test_strategy_table_positions_invalid_n_returns_empty():
    assert strategy_table_positions(1) == []
    assert strategy_table_positions(10) == []
    assert strategy_table_positions(0) == []


# ── count_lines_for_position ───────────────────────────────────────────

def test_count_lines_for_position_default_2_entries():
    """Default do template: 2 entradas em qualquer SIZES_OPEN_*."""
    assert count_lines_for_position("UTG", {}) == 2
    assert count_lines_for_position("BU", {}) == 2
    assert count_lines_for_position("BB", {}) == 2


def test_count_lines_for_position_SB_default_has_extra_complete():
    """SB tem +1 linha de Complete prepended."""
    assert count_lines_for_position("SB", {}) == 3  # 2 opens + 1 Complete


def test_count_lines_for_position_override_1_entry_eff_above_25():
    """Override do Trabalho A com [size] (1 entrada) → 1 linha."""
    overrides = {"SIZES_OPEN_OTHERS": [2.5]}
    assert count_lines_for_position("UTG", overrides) == 1


def test_count_lines_for_position_SB_override_1_entry():
    """SB com override [3.5] (1 entrada) → 2 linhas (Complete + 1 raise)."""
    overrides = {"SIZES_OPEN_SB": [3.5]}
    assert count_lines_for_position("SB", overrides) == 2


def test_count_lines_for_position_BU_alias():
    """BTN / BU/SB tratados como BU bucket."""
    overrides = {"SIZES_OPEN_BU": [2.0]}
    assert count_lines_for_position("BTN", overrides) == 1
    assert count_lines_for_position("BU/SB", overrides) == 1


# ── _is_all_in_effective ───────────────────────────────────────────────

def test_is_all_in_effective_at_95_pct_threshold():
    """Default threshold 0.95."""
    assert _ALL_IN_EFFECTIVE_THRESHOLD == 0.95
    assert _is_all_in_effective(95.0, 100.0) is True
    assert _is_all_in_effective(94.9, 100.0) is False
    assert _is_all_in_effective(100.0, 100.0) is True
    assert _is_all_in_effective(50.0, 100.0) is False


def test_is_all_in_effective_handles_none_gracefully():
    assert _is_all_in_effective(None, 100.0) is False
    assert _is_all_in_effective(50.0, None) is False
    assert _is_all_in_effective(None, None) is False
    assert _is_all_in_effective(50.0, 0) is False  # division-by-zero guard


# ── offset_within_bucket ───────────────────────────────────────────────

def test_offset_within_bucket_non_sb_small_raise():
    action = {"type": "raise", "size_bb": 2.5, "position": "UTG"}
    assert offset_within_bucket(action, raiser_stack_bb=30.0) == 0


def test_offset_within_bucket_non_sb_all_in_effective():
    # pt61 (#HRC-NODE-OFFSET-SB-JAM-OFFBY1): um open-jam non-SB é o 1º nó do
    # bucket (a acção original é sempre a 1ª opção do array) → within 0, NÃO 1.
    action = {"type": "raise", "size_bb": 30.0, "position": "UTG"}
    assert offset_within_bucket(action, raiser_stack_bb=30.0) == 0


def test_offset_within_bucket_sb_complete():
    action = {"type": "complete", "size_bb": 1.0, "position": "SB"}
    assert offset_within_bucket(action, raiser_stack_bb=30.0) == 0


def test_offset_within_bucket_sb_limp_treated_as_complete():
    action = {"type": "limp", "size_bb": 1.0, "position": "SB"}
    assert offset_within_bucket(action, raiser_stack_bb=30.0) == 0


def test_offset_within_bucket_sb_small_raise():
    action = {"type": "raise", "size_bb": 3.5, "position": "SB"}
    assert offset_within_bucket(action, raiser_stack_bb=30.0) == 1


def test_offset_within_bucket_sb_all_in_effective():
    # pt61 (#HRC-NODE-OFFSET-SB-JAM-OFFBY1): quando o raise SB É o jam não há
    # nó small-raise separado — a SB tem 2 nós (Complete + jam) → within 1, NÃO
    # 2. (A convenção antiga assumia Complete+small+all-in = 3 sub-nós.)
    action = {"type": "raise", "size_bb": 30.0, "position": "SB"}
    assert offset_within_bucket(action, raiser_stack_bb=30.0) == 1


# ── compute_target_node_offset: positions × N-max ──────────────────────

def test_compute_target_node_offset_5max_each_position_small_raise():
    """5-max default: HJ@0, CO@2, BTN@4, SB-complete@6, SB-raise@7.

    pt61: o alvo é sempre o 1º nó de raise da posição → SB-raise e SB-jam caem
    AMBOS @7 (o jam É o 1º raise quando é a acção original; não há nó @8)."""
    base = {"type": "raise", "size_bb": 2.0}
    assert compute_target_node_offset(
        {**base, "position": "HJ"}, 5, {}, raiser_stack_bb=50.0,
    ) == 0
    assert compute_target_node_offset(
        {**base, "position": "CO"}, 5, {}, raiser_stack_bb=50.0,
    ) == 2
    assert compute_target_node_offset(
        {**base, "position": "BTN"}, 5, {}, raiser_stack_bb=50.0,
    ) == 4
    assert compute_target_node_offset(
        {"type": "complete", "size_bb": 1.0, "position": "SB"}, 5, {},
        raiser_stack_bb=50.0,
    ) == 6
    assert compute_target_node_offset(
        {"type": "raise", "size_bb": 3.5, "position": "SB"}, 5, {},
        raiser_stack_bb=50.0,
    ) == 7
    # SB jam (size ≈ stack): o jam é o 1º (e único) nó de raise → @7, NÃO @8.
    assert compute_target_node_offset(
        {"type": "raise", "size_bb": 50.0, "position": "SB"}, 5, {},
        raiser_stack_bb=50.0,
    ) == 7


def test_compute_target_node_offset_GG6027751209_sb_jam_offby1_regression():
    """#HRC-NODE-OFFSET-SB-JAM-OFFBY1 — mão real pt61. SB-vs-BB, 5 seats reais
    (HJ/CO/BTN/SB/BB). Nível 600/1200, SB stack 5547 → jam 5397 ≈ 4.5bb ≈ stack
    (all-in efectivo). Strategy Table = 8 nós principais (HJ R2.0, HJ jam, CO
    R2.0, CO R4.32, BU R2.0, BU jam, SB C0.5, SB R4.5-jam); alvo = SB R4.5 = 8º
    nó = offset 7 (= 7 setas-baixo do 1º nó).

    O código ANTIGO devolvia 8 (convenção SB all-in = 2): preceding 6 + 2. O fix
    devolve 7 (within SB = 1). `raiser_stack_bb=4.5` (≈ size) garante que o ramo
    all-in antigo disparava — é a reprodução fiel do bug."""
    sb_jam = {"type": "raise", "size_bb": 4.5, "position": "SB"}
    assert compute_target_node_offset(sb_jam, 5, {}, raiser_stack_bb=4.5) == 7


def test_compute_target_node_offset_6max():
    """6-max default: MP=0, HJ=2, CO=4, BTN=6, SB-complete=8."""
    base = {"type": "raise", "size_bb": 2.0}
    assert compute_target_node_offset(
        {**base, "position": "MP"}, 6, {}, raiser_stack_bb=50.0,
    ) == 0
    assert compute_target_node_offset(
        {**base, "position": "CO"}, 6, {}, raiser_stack_bb=50.0,
    ) == 4
    assert compute_target_node_offset(
        {**base, "position": "BTN"}, 6, {}, raiser_stack_bb=50.0,
    ) == 6
    assert compute_target_node_offset(
        {"type": "complete", "size_bb": 1.0, "position": "SB"}, 6, {},
        raiser_stack_bb=50.0,
    ) == 8


def test_compute_target_node_offset_8max_UTG1_MP():
    """8-max default: UTG=0, UTG1=2, MP=4, HJ=6, CO=8, BTN=10."""
    base = {"type": "raise", "size_bb": 2.0}
    assert compute_target_node_offset(
        {**base, "position": "UTG"}, 8, {}, raiser_stack_bb=50.0,
    ) == 0
    assert compute_target_node_offset(
        {**base, "position": "UTG1"}, 8, {}, raiser_stack_bb=50.0,
    ) == 2
    assert compute_target_node_offset(
        {**base, "position": "MP"}, 8, {}, raiser_stack_bb=50.0,
    ) == 4
    assert compute_target_node_offset(
        {**base, "position": "HJ"}, 8, {}, raiser_stack_bb=50.0,
    ) == 6
    assert compute_target_node_offset(
        {**base, "position": "CO"}, 8, {}, raiser_stack_bb=50.0,
    ) == 8
    assert compute_target_node_offset(
        {**base, "position": "BTN"}, 8, {}, raiser_stack_bb=50.0,
    ) == 10


def test_compute_target_node_offset_all_in_effective_within_bucket():
    """pt61 (#HRC-NODE-OFFSET-SB-JAM-OFFBY1): HJ jam @ stack 50 (1ª posição em
    5-max) → 0 + 0 = 0. O open-jam é a acção original = 1º nó do bucket HJ
    (within 0). Antes do fix a convenção non-SB all-in devolvia 1 (off-by-one)."""
    assert compute_target_node_offset(
        {"type": "raise", "size_bb": 50.0, "position": "HJ"}, 5, {},
        raiser_stack_bb=50.0,
    ) == 0


def test_compute_target_node_offset_override_eff_above_25_collapses_buckets():
    """Eff > 25BB → Trabalho A devolve [size] (1 entrada). 5-max com
    HJ/CO/BTN override [2.5]: HJ=0, CO=1, BTN=2, SB-complete=3."""
    overrides = {
        "SIZES_OPEN_OTHERS": [2.5],
        "SIZES_OPEN_BU": [2.0],
        "SIZES_OPEN_SB": [3.5],
    }
    base = {"type": "raise", "size_bb": 2.5}
    assert compute_target_node_offset(
        {**base, "position": "HJ"}, 5, overrides, raiser_stack_bb=30.0,
    ) == 0
    assert compute_target_node_offset(
        {**base, "position": "CO"}, 5, overrides, raiser_stack_bb=30.0,
    ) == 1
    assert compute_target_node_offset(
        {**base, "position": "BTN"}, 5, overrides, raiser_stack_bb=30.0,
    ) == 2
    assert compute_target_node_offset(
        {"type": "complete", "size_bb": 1.0, "position": "SB"}, 5, overrides,
        raiser_stack_bb=30.0,
    ) == 3


# ── Edge cases ─────────────────────────────────────────────────────────

def test_compute_target_node_offset_none_aggressor_returns_none():
    assert compute_target_node_offset(None, 5, {}, 50.0) is None


def test_compute_target_node_offset_bb_aggressor_returns_none():
    """BB não está na Strategy Table de opens → None."""
    assert compute_target_node_offset(
        {"type": "raise", "size_bb": 3.0, "position": "BB"}, 5, {}, 50.0,
    ) is None


def test_compute_target_node_offset_position_none_returns_none():
    assert compute_target_node_offset(
        {"type": "raise", "size_bb": 2.0, "position": None}, 5, {}, 50.0,
    ) is None


def test_compute_target_node_offset_invalid_seats_at_table_returns_none():
    """seats_at_table fora de [2,9] ou tipo errado → None com WARN."""
    action = {"type": "raise", "size_bb": 2.0, "position": "UTG"}
    assert compute_target_node_offset(action, 12, {}, 50.0) is None
    assert compute_target_node_offset(action, None, {}, 50.0) is None
    assert compute_target_node_offset(action, "5", {}, 50.0) is None


def test_compute_target_node_offset_gg5944816316_8handed_MP_open():
    """pt27 regressão: GG-5944816316 — 8-handed, Pinduca77 (MP) raises 2.0bb,
    Hero (HJ) 3-bet jam. Antes do Fix 2, `max_players=6` (redução ICM via
    `derive_max_players`) era passado para `compute_target_node_offset`, e
    O bug pt27 era passar max_players=6 (redução ICM) em vez de seats_at_table=8:
    a position do agressor falhava o lookup na strategy table reduzida. Pós-fix
    passa-se `seats_at_table=8`; no vocab actual MP é a 3ª posição em 8-max
    (UTG, UTG1, MP, …), opens default = 2 entries → offset = 2*2 + 0 = 4.

    Eff stack do raiser: Pinduca77 359522 chips / BB 3500 = 102.72 BB
    → `is_all_in(2.0, 102.72) = False` → offset_within_bucket = 0.
    """
    overrides = {"SIZES_OPEN_OTHERS": [2.0, "ALLIN"]}
    action = {"type": "raise", "size_bb": 2.0, "position": "MP"}
    assert compute_target_node_offset(
        action, seats_at_table=8, script_overrides=overrides,
        raiser_stack_bb=102.72,
    ) == 4


def test_compute_target_node_offset_aggressor_not_a_dict_returns_none():
    """Defensivo: input não-dict → None com WARN."""
    assert compute_target_node_offset("not a dict", 5, {}, 50.0) is None
    assert compute_target_node_offset([], 5, {}, 50.0) is None


def test_compute_target_node_offset_unknown_position_returns_none():
    """Position válida mas não em strategy_table_positions(N) → None."""
    # Ex: position='LJ' em 5-max (não existe nesse N).
    assert compute_target_node_offset(
        {"type": "raise", "size_bb": 2.0, "position": "LJ"}, 5, {}, 50.0,
    ) is None


# ── derive_aggressor_stack_bb ──────────────────────────────────────────

_HH_5MAX_UTG_OPENS = """\
Winamax Poker - Tournament "GRAVITY" buyIn: 200€ level: 10 - HandId: #X - Holdem no limit (500/1000/2000) - 2026/05/01
Table 'T' 5-max Seat #3 is the button
Seat 1: AlphaPlayer (45000)
Seat 2: BetaPlayer (32000)
Seat 3: GammaPlayer (60000)
Seat 4: DeltaPlayer (50000)
Seat 5: EpsilonPlayer (40000)
*** ANTE/BLINDS ***
AlphaPlayer posts ante 500
BetaPlayer posts ante 500
GammaPlayer posts ante 500
DeltaPlayer posts small blind 1000
EpsilonPlayer posts big blind 2000
*** PRE-FLOP ***
AlphaPlayer raises 3000 to 5000
BetaPlayer folds
GammaPlayer folds
DeltaPlayer folds
EpsilonPlayer folds
*** SUMMARY ***
"""


def test_derive_aggressor_stack_bb_winamax_5max():
    """AlphaPlayer abre com stack 45000, BB=2000 → 22.5 BB."""
    out = derive_aggressor_stack_bb(_HH_5MAX_UTG_OPENS, level_bb=2000)
    assert out == 22.5


def test_derive_aggressor_stack_bb_no_raise_returns_none():
    """Walk-to-BB sem raise → None."""
    hh = """\
Hand #X: Test - Level1 (50/100) - 2026/01/01
Table 'T' 6-max Seat #1 is the button
Seat 1: A (10000 in chips)
Seat 2: B (10000 in chips)
B: posts small blind 50
A: posts big blind 100
*** HOLE CARDS ***
B: folds
*** SUMMARY ***
"""
    assert derive_aggressor_stack_bb(hh, level_bb=100) is None


def test_derive_aggressor_stack_bb_invalid_level_bb():
    assert derive_aggressor_stack_bb(_HH_5MAX_UTG_OPENS, level_bb=0) is None
    assert derive_aggressor_stack_bb(_HH_5MAX_UTG_OPENS, level_bb=None) is None


def test_derive_aggressor_stack_bb_empty_hh():
    assert derive_aggressor_stack_bb("", level_bb=100) is None
    assert derive_aggressor_stack_bb(None, level_bb=100) is None
