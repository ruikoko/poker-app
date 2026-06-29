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
    _open_node_eff_and_shortie,
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
    assert strategy_table_positions(6) == ["UTG", "HJ", "CO", "BTN", "SB"]
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
    # pt89: open per-posição → a chave do UTG é SIZES_OPEN_UTG (era OTHERS).
    overrides = {"SIZES_OPEN_UTG": [2.5]}
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
    # pt67 (#HRC-NODE-OFFSET-OFFBY1-REVERT-PT61): um open-jam non-SB é o nó
    # ALLIN = o ÚLTIMO do bucket (ascending) → within 1, NÃO 0. (O pt61 dera 0.)
    action = {"type": "raise", "size_bb": 30.0, "position": "UTG"}
    assert offset_within_bucket(action, raiser_stack_bb=30.0) == 1


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
    # pt67 (#HRC-NODE-OFFSET-OFFBY1-REVERT-PT61): SB jam = o nó ALLIN, ÚLTIMO da
    # SB (Complete=0, small=1, ALLIN=2) → within 2. Confirmado visualmente em
    # GG-6039094225 (SB jam 6.35 → offset 14). O pt61 dera 1 (off-by-one curto).
    action = {"type": "raise", "size_bb": 30.0, "position": "SB"}
    assert offset_within_bucket(action, raiser_stack_bb=30.0) == 2


# ── compute_target_node_offset: positions × N-max ──────────────────────

def test_compute_target_node_offset_5max_small_and_jam():
    """5-max default (2 nós por posição + SB com Complete): HJ-small@0,
    CO-small@2, BTN-small@4, SB-complete@6, SB-small@7.

    pt67: o jam é o nó ALLIN = ÚLTIMO do bucket. SB-small@7 mas SB-jam@8
    (Complete=6, small=7, ALLIN=8); HJ-jam@1 (small=0, ALLIN=1)."""
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
    # SB jam (size ≈ stack): o nó ALLIN é o último → @8 (não @7).
    assert compute_target_node_offset(
        {"type": "raise", "size_bb": 50.0, "position": "SB"}, 5, {},
        raiser_stack_bb=50.0,
    ) == 8
    # HJ jam (1ª posição em 5-max): small@0, ALLIN@1.
    assert compute_target_node_offset(
        {"type": "raise", "size_bb": 50.0, "position": "HJ"}, 5, {},
        raiser_stack_bb=50.0,
    ) == 1


def test_compute_target_node_offset_GG6027751209_sb_jam():
    """SB-vs-BB, 5 seats reais. SB jam ≈ 4.5bb ≈ stack (all-in efectivo). O nó
    ALLIN é o ÚLTIMO da SB (Complete=6, small=7, ALLIN=8) → offset 8.

    pt67 (#HRC-NODE-OFFSET-OFFBY1-REVERT-PT61): o pt61 tinha forçado isto a 7
    (within SB=1), em TEORIA nunca validada em smoke. A 1ª smoke real (pt67,
    GG-6039094225 SB jam → 14) confirma within SB jam = 2 → aqui 6+2 = 8. O
    valor pré-pt61 (8) era o correcto."""
    sb_jam = {"type": "raise", "size_bb": 4.5, "position": "SB"}
    assert compute_target_node_offset(sb_jam, 5, {}, raiser_stack_bb=4.5) == 8


def test_compute_target_node_offset_6max():
    """6-max default: UTG=0, HJ=2, CO=4, BTN=6, SB-complete=8.

    (pt92 #POSITION-LABELS-PYTHON-JS-DRIFT: o 1º a agir em 6-max é UTG,
    não MP — alinhado com a convenção do HRC/script.)"""
    base = {"type": "raise", "size_bb": 2.0}
    assert compute_target_node_offset(
        {**base, "position": "UTG"}, 6, {}, raiser_stack_bb=50.0,
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


def test_compute_target_node_offset_non_sb_jam_within_bucket():
    """pt67: HJ jam @ stack 50 (1ª posição em 5-max) → 0 + 1 = 1. O open-jam é
    o nó ALLIN = ÚLTIMO do bucket HJ (small@0, ALLIN@1). (O pt61 dera 0.)"""
    assert compute_target_node_offset(
        {"type": "raise", "size_bb": 50.0, "position": "HJ"}, 5, {},
        raiser_stack_bb=50.0,
    ) == 1


# ── Cross-check pt67: as 3 mãos reais (offsets confirmados visualmente) ─────

def test_offset_GG6029013400_8max_HJ_jam_returns_7():
    """GG-6029013400: 8-max, HJ jam 9.01bb (stack 9.16). OTHERS=['ALLIN',2.0]
    (2 nós). UTG/UTG1/MP = 3×2 = 6; HJ jam = ALLIN (within 1) → 7. (Prod dava 6.)"""
    overrides = {"SIZES_OPEN_OTHERS": ["ALLIN", 2.0]}
    agg = {"type": "raise", "size_bb": 9.01, "position": "HJ"}
    assert compute_target_node_offset(agg, 8, overrides, raiser_stack_bb=9.16) == 7


def test_offset_GG6039094225_8max_SB_jam_returns_14():
    """GG-6039094225: 8-max, SB jam 6.35bb (stack 6.47). Só SIZES_OPEN_SB
    overridden; OTHERS/BU caem no default 2. UTG..BTN = 6×2 = 12; SB jam = ALLIN
    (within 2) → 14. (Prod dava 13.)"""
    overrides = {"SIZES_OPEN_SB": ["ALLIN"]}
    agg = {"type": "raise", "size_bb": 6.35, "position": "SB"}
    assert compute_target_node_offset(agg, 8, overrides, raiser_stack_bb=6.47) == 14


def test_offset_GG6028190109_6max_HJ_small_returns_2():
    """GG-6028190109: 6-max, HJ small-raise 2.0bb (stack 34.5, NÃO jam).
    OTHERS=[2.0,'ALLIN'] (2 nós). MP = 1×2 = 2; HJ small = 1º nó (within 0) → 2.
    Não afectado pelo bug (small raise = 1º nó em ambas as convenções)."""
    overrides = {"SIZES_OPEN_OTHERS": [2.0, "ALLIN"]}
    agg = {"type": "raise", "size_bb": 2.0, "position": "HJ"}
    assert compute_target_node_offset(agg, 6, overrides, raiser_stack_bb=34.5) == 2


def test_compute_target_node_offset_override_eff_above_25_collapses_buckets():
    """Eff > 25BB → Trabalho A devolve [size] (1 entrada). 5-max com
    HJ/CO/BTN override [2.5]: HJ=0, CO=1, BTN=2, SB-complete=3."""
    # pt89: open per-posição → HJ/CO levam a sua própria var (era OTHERS partilhado).
    overrides = {
        "SIZES_OPEN_HJ": [2.5],
        "SIZES_OPEN_CO": [2.5],
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


# ── pt86 (#HRC-NODE-OFFSET-IMPLICIT-LINES) — count_lines com stack individual ──
# Espelha o template: ALLIN implícito por stack individual ≤ 25 (geral) / ≤ 30
# (SB, blind-vs-blind na tabela de opens); colapso (size≥stack → 1 linha);
# Complete da SB. stack_bb=None → legacy (coberto pelos testes acima).

# pt89: open per-posição — os testes abaixo usam a posição "UTG", logo a var é
# SIZES_OPEN_UTG (era o partilhado SIZES_OPEN_OTHERS).
_OTH = {"SIZES_OPEN_UTG": [2.0]}           # array [size] (opener eff>25, sem ALLIN)
_OTH_ALLIN = {"SIZES_OPEN_UTG": [2.0, "ALLIN"]}  # array [size, ALLIN]


def test_count_lines_nonblind_deep_above_25_is_1():
    # stack > 25 → sem ALLIN implícito → 1 linha (só o size).
    assert count_lines_for_position("UTG", _OTH, stack_bb=88.0) == 1


def test_count_lines_nonblind_size_lt_stack_le_25_is_2():
    # 2 < stack ≤ 25 → size + ALLIN implícito → 2 linhas.
    assert count_lines_for_position("UTG", _OTH, stack_bb=20.0) == 2
    assert count_lines_for_position("UTG", _OTH, stack_bb=25.0) == 2   # bordo inclusivo


def test_count_lines_nonblind_ultrashort_collapse_is_1():
    # stack ≤ size → o size colapsa para ALLIN → 1 linha.
    assert count_lines_for_position("UTG", _OTH, stack_bb=1.5) == 1


def test_count_lines_nonblind_25_threshold_not_30():
    # 25 < stack ≤ 30 numa NÃO-blind → SEM ALLIN (limiar 25, não 30) → 1 linha.
    assert count_lines_for_position("UTG", _OTH, stack_bb=28.0) == 1


def test_count_lines_array_with_explicit_allin_is_2():
    # [size, ALLIN] com stack > size → 2 linhas (ALLIN explícito sempre presente).
    assert count_lines_for_position("UTG", _OTH_ALLIN, stack_bb=88.0) == 2


def test_count_lines_array_with_allin_collapsed_is_1():
    # [size, ALLIN] mas stack ≤ size → size colapsa, dedup com ALLIN → 1 linha.
    assert count_lines_for_position("UTG", _OTH_ALLIN, stack_bb=1.5) == 1


def test_count_lines_sb_comfortable_above_30_is_2():
    # SB default [3.5]; stack > 30 (BvB) → Complete + size, SEM ALLIN → 2 linhas.
    assert count_lines_for_position("SB", {}, stack_bb=88.0) == 2


def test_count_lines_sb_size_lt_stack_le_30_is_3():
    # SB, 3.5 < stack ≤ 30 → Complete + size + ALLIN → 3 linhas (limiar BvB = 30).
    assert count_lines_for_position("SB", {}, stack_bb=20.0) == 3
    assert count_lines_for_position("SB", {}, stack_bb=28.0) == 3   # 28>25 mas ≤30 (BvB)


def test_count_lines_sb_ultrashort_collapse_is_2():
    # SB, stack ≤ size(3.5) → Complete + ALLIN (size colapsa) → 2 linhas.
    assert count_lines_for_position("SB", {}, stack_bb=3.0) == 2


def test_count_lines_legacy_none_unchanged():
    # stack_bb=None → comportamento legacy (len + Complete SB) intacto.
    assert count_lines_for_position("UTG", {}, None) == 2
    assert count_lines_for_position("SB", {}, None) == 3
    assert count_lines_for_position("UTG", _OTH, None) == 1


# ── pt86 — recálculo do offset na mão REAL GG-6084189514 (8-max, agg CO) ──────
# UTG=15.95bb, UTG1=10.96bb (≤25 → 2 linhas cada), MP/HJ deep (>25 → 1). Old
# (sem stacks) subconta → offset 4 (cai em MP). New (com stacks) → offset 6 (CO).

_GG6084189514 = {
    "agg": {"type": "raise", "position": "CO", "size_bb": 2.0},
    # pt89: open per-posição — cada posição antes do CO leva a sua própria var
    # (era o partilhado SIZES_OPEN_OTHERS). Valores [2.0] inalterados.
    "overrides": {
        "SIZES_OPEN_UTG": [2.0], "SIZES_OPEN_UTG1": [2.0],
        "SIZES_OPEN_MP": [2.0], "SIZES_OPEN_HJ": [2.0], "SIZES_OPEN_CO": [2.0],
    },
    "raiser_stack_bb": 32.43,
    "stacks": {"UTG": 15.95, "UTG1": 10.96, "MP": 74.67, "HJ": 71.84,
               "CO": 32.43, "BTN": 63.2, "SB": 12.54},
}


def test_offset_gg6084189514_old_undercounts_to_MP():
    # Sem stacks (legacy): UTG/UTG1/MP/HJ contam 1 cada → offset 4 (= linha do MP).
    c = _GG6084189514
    assert compute_target_node_offset(
        c["agg"], 8, c["overrides"], c["raiser_stack_bb"]) == 4


def test_offset_gg6084189514_new_lands_on_CO():
    # Com stacks: UTG/UTG1 (≤25)=2, MP/HJ (>25)=1 → 6 (= linha do CO, o agressor).
    c = _GG6084189514
    assert compute_target_node_offset(
        c["agg"], 8, c["overrides"], c["raiser_stack_bb"], c["stacks"]) == 6


# ── pt89 (#GTO-OPEN-SIZE-NOT-PER-POSITION) — split per-posição não contamina ──
# O bug antigo: SIZES_OPEN_OTHERS partilhado → um ALLIN injectado no open de UMA
# posição contava +1 linha em TODAS as posições antes do agressor (âncora a saltar).
# Com o split per-posição, cada open vive na sua var e não vaza para as outras.

def test_count_lines_per_position_no_contamination_pt89():
    # CO tem [2.0, ALLIN] na SUA var; UTG fundo (>25) NÃO herda esse ALLIN.
    ov = {"SIZES_OPEN_CO": [2.0, "ALLIN"]}
    assert count_lines_for_position("UTG", ov, stack_bb=88.0) == 1   # só o size
    # E a própria CO conta as 2 linhas (size + ALLIN explícito).
    assert count_lines_for_position("CO", ov, stack_bb=88.0) == 2


def test_anchor_offset_consistent_after_split_pt89():
    # Prova de que a âncora NÃO se re-parte com o split per-posição.
    # GG-6084189514 (8-max, agg CO, stacks reais): âncora pousa no nó do CO (6).
    agg = {"type": "raise", "size_bb": 2.0, "position": "CO"}
    stacks = {"UTG": 15.95, "UTG1": 10.96, "MP": 74.67, "HJ": 71.84,
              "CO": 32.43, "BTN": 63.2, "SB": 12.54}
    base = compute_target_node_offset(agg, 8, {}, 32.43, stacks)
    assert base == 6   # UTG/UTG1 (≤25)=2 cada, MP/HJ (>25)=1 cada → 6
    # Contaminar o OPEN do BTN (posterior ao CO) NÃO desloca a âncora do CO:
    # só as posições ANTES do agressor contam, e cada uma na sua própria var.
    contaminated = compute_target_node_offset(
        agg, 8, {"SIZES_OPEN_BU": [2.0, "ALLIN"]}, 32.43, stacks)
    assert contaminated == base
    # Contaminar o OPEN de UMA posição anterior (HJ) com ALLIN explícito só muda
    # a linha do HJ (deep>25 ignora o ALLIN implícito, mas o explícito conta) —
    # e nunca contamina UTG/UTG1/MP. HJ passa de 1→2 → âncora desce 1 (7).
    hj_allin = compute_target_node_offset(
        agg, 8, {"SIZES_OPEN_HJ": [2.0, "ALLIN"]}, 32.43, stacks)
    assert hj_allin == base + 1


# ── pt91 (Regra 1 do Rui) — open efetivo <= 9 → só all-in ──────────────────

def test_count_lines_rule1_effective_collapse_to_allin():
    """eff <= 9 → 1 linha (só all-in), mesmo que a stack individual desse 2.
    Sem effective_bb (back-compat) com 20 BB individual → 2 linhas (pt86)."""
    assert count_lines_for_position("UTG", {}, stack_bb=20.0) == 2
    assert count_lines_for_position(
        "UTG", {}, stack_bb=20.0, effective_bb=8.0) == 1
    assert count_lines_for_position(
        "UTG", {}, stack_bb=20.0, effective_bb=9.0) == 1   # 9 incluído
    assert count_lines_for_position(
        "UTG", {}, stack_bb=20.0, effective_bb=9.01) == 2  # > 9 → normal


def test_count_lines_rule1_collapse_SB_keeps_complete():
    """SB com eff <= 9 → 1 (all-in) + 1 (Complete) = 2."""
    assert count_lines_for_position(
        "SB", {}, stack_bb=20.0, effective_bb=8.0) == 2


def test_count_lines_rule1_shortie_own_pko_keeps_min_plus_allin():
    """Regra 3 ganha à Regra 1: em PKO, o próprio shortie (<=4 BB) a abrir
    leva min+allin (2 linhas), não só all-in (1)."""
    # Não-PKO: eff<=9 → 1 linha.
    assert count_lines_for_position(
        "UTG", {}, stack_bb=3.5, effective_bb=3.5) == 1
    # PKO + own<=4 → exceção → min+allin = 2.
    assert count_lines_for_position(
        "UTG", {}, stack_bb=3.5, effective_bb=3.5,
        is_pko=True, own_total_bb=3.5) == 2


def test_count_lines_rule3_open_iso_adds_allin_when_deep():
    """Regra 3-em-open: PKO + adversário por falar <=4 BB → +all-in mesmo
    com opener fundo (que normalmente daria 1 linha sem all-in)."""
    assert count_lines_for_position("UTG", {}, stack_bb=88.0) == 1
    assert count_lines_for_position(
        "UTG", {}, stack_bb=88.0, effective_bb=88.0,
        is_pko=True, own_total_bb=88.0,
        yet_to_act_short_or_allin=True) == 2
    # Sem PKO, o yet_short não acrescenta nada.
    assert count_lines_for_position(
        "UTG", {}, stack_bb=88.0, effective_bb=88.0,
        is_pko=False, own_total_bb=88.0,
        yet_to_act_short_or_allin=True) == 1


def test_offset_within_bucket_unchanged_by_rule1_preservation():
    """pt91: a ação real é sempre preservada → o within NÃO colapsa por Regra 1
    (lógica pt67 intacta: small→0, jam→último nó). O índice exacto fica para o
    smoke visual (#IMPLICIT-LINES)."""
    nonsb = {"position": "UTG", "type": "raise", "size_bb": 8.0}
    assert offset_within_bucket(nonsb, 8.0) == 1          # jam → nó ALLIN (idx 1)
    small = {"position": "UTG", "type": "raise", "size_bb": 2.0}
    assert offset_within_bucket(small, 30.0) == 0         # small → idx 0
    sb = {"position": "SB", "type": "raise", "size_bb": 8.0}
    assert offset_within_bucket(sb, 8.0) == 2             # SB jam → idx 2
    sb_complete = {"position": "SB", "type": "complete", "size_bb": 0.0}
    assert offset_within_bucket(sb_complete, 8.0) == 0


def test_open_node_eff_and_shortie_caps_by_biggest_live():
    """eff = min(own, maior vivo atrás); yet_short = algum atrás <= 4 BB."""
    totals = {"UTG": 50.0, "HJ": 40.0, "CO": 30.0,
              "BTN": 25.0, "SB": 20.0, "BB": 3.0}
    eff, own, yet = _open_node_eff_and_shortie("UTG", 6, totals)
    assert (eff, own, yet) == (40.0, 50.0, True)   # capado por HJ=40; BB=3<=4
    eff_sb, own_sb, yet_sb = _open_node_eff_and_shortie("SB", 6, totals)
    assert (eff_sb, own_sb, yet_sb) == (3.0, 20.0, True)  # só BB atrás (3)


def test_compute_offset_pko_iso_shifts_anchor():
    """End-to-end: PKO + shortie atrás (BB=3) → Regra 3 acrescenta linha de
    all-in a cada posição anterior ao raiser → âncora sobe."""
    totals = {"UTG": 50.0, "HJ": 50.0, "CO": 50.0,
              "BTN": 50.0, "SB": 50.0, "BB": 3.0}
    agg = {"position": "CO", "type": "raise", "size_bb": 2.0}
    # Baseline sem totais/PKO: UTG(1)+HJ(1)+within(0) = 2.
    assert compute_target_node_offset(agg, 6, {}, 50.0, totals) == 2
    # PKO + totais: UTG(2)+HJ(2)+within(0) = 4.
    assert compute_target_node_offset(
        agg, 6, {}, 50.0, totals,
        is_pko=True, position_total_bb=totals) == 4


def test_compute_offset_rule1_collapse_shifts_anchor():
    """Rule 1 (format-agnóstico) nas FOLDADAS antes do raiser: mesa toda curta
    (8 BB) → cada open hipotético colapsa para 1 linha (era 2). O within do
    raiser NÃO colapsa (ação real preservada → lógica pt67, jam=1).

    Nota: o efetivo é capado pelo MAIOR vivo atrás — um único curto numa mesa
    funda NÃO colapsa uma posição cedo (ela ainda joga deep vs as fundas)."""
    totals = {"UTG": 8.0, "HJ": 8.0, "CO": 8.0,
              "BTN": 8.0, "SB": 8.0, "BB": 8.0}
    agg = {"position": "CO", "type": "raise", "size_bb": 8.0}  # jam (~stack)
    # Sem totais: UTG(2)+HJ(2)+within(jam=1) = 5.
    assert compute_target_node_offset(agg, 6, {}, 8.0, totals) == 5
    # Com totais (Rule 1 nas foldadas): UTG(1)+HJ(1)+within(jam=1) = 3.
    assert compute_target_node_offset(
        agg, 6, {}, 8.0, totals, position_total_bb=totals) == 3
