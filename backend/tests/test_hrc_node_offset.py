"""Tests para `compute_target_node_offset` — LEI de sizings v3 (15 Jul 2026).

Strategy Table HRC ordem validada empíricamente:
    UTG → (EP/MP/HJ consoante N) → CO → BU → SB
    (BB nunca aparece — não abre preflop.)

LEI v3: os opens são **single-size** (Regra de Ouro dá 1 size real; senão 1 size
base). A linha de all-in é decidida pela **EFETIVA** (régua única, remaining):
`eff = min(remaining da posição, maior remaining vivo atrás)`.
Nº de linhas por posição-open:
    1 (base) + 1 ALLIN se [eff ≤ 25 (SB: 30) OU colapso eff≤9 OU Regra 3 PKO]
    + 1 Complete se SB.
Aggressor com `size_bb >= 95%` da stack do raiser conta como all-in efectivo.
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


# ── count_lines_for_position (LEI v3: single-size + all-in por efetiva) ───

def test_count_lines_no_eff_is_base_only():
    """Sem efetiva (legacy/defensivo): 1 linha base; SB +1 Complete."""
    assert count_lines_for_position("UTG", {}) == 1
    assert count_lines_for_position("BU", {}) == 1
    assert count_lines_for_position("SB", {}) == 2


def test_count_lines_deep_above_25_is_1():
    """eff > 25 (não-blind) → sem linha de all-in → 1 linha."""
    assert count_lines_for_position("UTG", {}, effective_bb=88.0) == 1
    assert count_lines_for_position("UTG", {}, effective_bb=25.01) == 1


def test_count_lines_le_25_adds_allin_is_2():
    """eff ≤ 25 (não-blind) → base + ALLIN → 2 linhas (bordo inclusivo)."""
    assert count_lines_for_position("UTG", {}, effective_bb=20.0) == 2
    assert count_lines_for_position("UTG", {}, effective_bb=25.0) == 2


def test_count_lines_collapse_le_9_is_1():
    """eff ≤ 9 → colapso → SÓ all-in → 1 linha."""
    assert count_lines_for_position("UTG", {}, effective_bb=9.0) == 1
    assert count_lines_for_position("UTG", {}, effective_bb=8.0) == 1
    assert count_lines_for_position("UTG", {}, effective_bb=9.01) == 2  # >9 → normal


def test_count_lines_sb_threshold_30_and_complete():
    """SB: limiar de all-in = 30 (BvB); +1 Complete sempre."""
    assert count_lines_for_position("SB", {}, effective_bb=88.0) == 2   # >30 → base+complete
    assert count_lines_for_position("SB", {}, effective_bb=28.0) == 3   # ≤30 → base+allin+complete
    assert count_lines_for_position("SB", {}, effective_bb=30.0) == 3   # bordo
    assert count_lines_for_position("SB", {}, effective_bb=8.0) == 2    # colapso + complete


def test_count_lines_nonblind_25_not_30():
    """25 < eff ≤ 30 numa NÃO-blind → SEM all-in (limiar 25) → 1 linha."""
    assert count_lines_for_position("UTG", {}, effective_bb=28.0) == 1


def test_count_lines_bu_alias():
    """BTN / BU/SB tratados como não-blind (limiar 25)."""
    assert count_lines_for_position("BTN", {}, effective_bb=88.0) == 1
    assert count_lines_for_position("BU/SB", {}, effective_bb=20.0) == 2


# ── count_lines: Regra 3 (shortie PKO) ─────────────────────────────────

def test_count_lines_shortie_own_pko_keeps_min_plus_allin():
    """Regra 3 ganha ao colapso: em PKO, o próprio shortie (≤4 BB) a abrir leva
    min+allin (2 linhas), não só all-in (1)."""
    # Não-PKO: eff≤9 → colapso → 1 linha.
    assert count_lines_for_position("UTG", {}, effective_bb=3.5) == 1
    # PKO + own≤4 → exceção → min+allin = 2.
    assert count_lines_for_position(
        "UTG", {}, effective_bb=3.5, is_pko=True, own_total_bb=3.5) == 2


def test_count_lines_rule3_open_iso_adds_allin_when_deep():
    """Regra 3-em-open: PKO + adversário por falar ≤4 BB → +all-in mesmo com
    opener fundo (que normalmente daria 1 linha sem all-in)."""
    assert count_lines_for_position("UTG", {}, effective_bb=88.0) == 1
    assert count_lines_for_position(
        "UTG", {}, effective_bb=88.0,
        is_pko=True, own_total_bb=88.0, yet_to_act_short_or_allin=True) == 2
    # Sem PKO, o yet_short não acrescenta nada.
    assert count_lines_for_position(
        "UTG", {}, effective_bb=88.0,
        is_pko=False, own_total_bb=88.0, yet_to_act_short_or_allin=True) == 1


def test_count_lines_sb_collapse_keeps_complete():
    """SB com eff ≤ 9 → 1 (all-in) + 1 (Complete) = 2."""
    assert count_lines_for_position("SB", {}, effective_bb=8.0) == 2


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
    # open-jam non-SB é o nó ALLIN = o ÚLTIMO do bucket (ascending) → 1 no
    # layout cheio (small+allin).
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
    # SB jam = o nó ALLIN, ÚLTIMO da SB (Complete=0, small=1, ALLIN=2) → 2 no
    # layout cheio.
    action = {"type": "raise", "size_bb": 30.0, "position": "SB"}
    assert offset_within_bucket(action, raiser_stack_bb=30.0) == 2


# ── compute_target_node_offset: LEI v3 com stacks reais (eff dita as linhas) ─

# Helper de stacks: remaining ≈ total (aproximação; a régua usa remaining).
def _flat(n_map):
    return dict(n_map)


def test_offset_6max_deep_no_allin_lines():
    """6-max, todos deep (100 BB) → cada open = 1 linha (eff>25). SB = base+complete.
    UTG=0, HJ=1, CO=2, BTN=3, SB-complete=4, SB-small=5."""
    st = {"UTG": 100.0, "HJ": 100.0, "CO": 100.0, "BTN": 100.0,
          "SB": 100.0, "BB": 100.0}
    base = {"type": "raise", "size_bb": 2.0}
    for pos, exp in [("UTG", 0), ("HJ", 1), ("CO", 2), ("BTN", 3)]:
        assert compute_target_node_offset(
            {**base, "position": pos}, 6, {}, 100.0, st, position_total_bb=st,
        ) == exp
    assert compute_target_node_offset(
        {"type": "complete", "size_bb": 1.0, "position": "SB"}, 6, {}, 100.0,
        st, position_total_bb=st) == 4
    assert compute_target_node_offset(
        {"type": "raise", "size_bb": 3.5, "position": "SB"}, 6, {}, 100.0,
        st, position_total_bb=st) == 5


def test_offset_6max_short_adds_allin_lines():
    """6-max, todos 20 BB (≤25) → cada open = 2 linhas; SB = base+allin+complete=3.
    UTG small=0 / UTG jam=1; CO=4; BTN=6; SB-complete=8, SB-small=9, SB-jam=10."""
    st = {"UTG": 20.0, "HJ": 20.0, "CO": 20.0, "BTN": 20.0,
          "SB": 20.0, "BB": 20.0}
    assert compute_target_node_offset(
        {"type": "raise", "size_bb": 2.0, "position": "UTG"}, 6, {}, 20.0,
        st, position_total_bb=st) == 0
    assert compute_target_node_offset(
        {"type": "raise", "size_bb": 20.0, "position": "UTG"}, 6, {}, 20.0,
        st, position_total_bb=st) == 1   # jam → última linha do bucket (2)
    assert compute_target_node_offset(
        {"type": "raise", "size_bb": 2.0, "position": "CO"}, 6, {}, 20.0,
        st, position_total_bb=st) == 4
    assert compute_target_node_offset(
        {"type": "raise", "size_bb": 2.0, "position": "BTN"}, 6, {}, 20.0,
        st, position_total_bb=st) == 6
    assert compute_target_node_offset(
        {"type": "complete", "size_bb": 1.0, "position": "SB"}, 6, {}, 20.0,
        st, position_total_bb=st) == 8
    assert compute_target_node_offset(
        {"type": "raise", "size_bb": 3.5, "position": "SB"}, 6, {}, 20.0,
        st, position_total_bb=st) == 9
    assert compute_target_node_offset(
        {"type": "raise", "size_bb": 20.0, "position": "SB"}, 6, {}, 20.0,
        st, position_total_bb=st) == 10  # SB jam → última (Complete,small,ALLIN)


def test_offset_collapse_all_short_co_jam():
    """Mesa toda a 8 BB (≤9) → cada open colapsa a 1 linha. CO jam:
    UTG(1)+HJ(1)=2; bucket do CO colapsado (1 linha) → within jam=0 → 2."""
    st = {"UTG": 8.0, "HJ": 8.0, "CO": 8.0, "BTN": 8.0, "SB": 8.0, "BB": 8.0}
    agg = {"type": "raise", "size_bb": 8.0, "position": "CO"}
    assert compute_target_node_offset(
        agg, 6, {}, 8.0, st, position_total_bb=st) == 2


def test_offset_8max_mixed_eff_lands_on_CO():
    """8-max, stacks mistos, CO abre small. UTG=15/UTG1=11 (≤25 → 2 linhas cada);
    MP=74/HJ=71 (>25 → 1 cada) → CO em 2+2+1+1 = 6."""
    st = {"UTG": 15.0, "UTG1": 11.0, "MP": 74.0, "HJ": 71.0,
          "CO": 32.0, "BTN": 63.0, "SB": 12.0, "BB": 50.0}
    agg = {"type": "raise", "size_bb": 2.0, "position": "CO"}
    assert compute_target_node_offset(
        agg, 8, {}, 32.0, st, position_total_bb=st) == 6


def test_offset_sb_jam_short_blinds():
    """5-max, HJ/CO/BTN deep (50) mas SB/BB curtas (4.5). BTN cai a eff 4.5
    (capado pelos blinds) → colapso → 1 linha. SB jam:
    HJ(1)+CO(1)+BTN(1)=3; bucket SB = colapso+complete = 2 → within jam=1 → 4."""
    st = {"HJ": 50.0, "CO": 50.0, "BTN": 50.0, "SB": 4.5, "BB": 4.5}
    sb_jam = {"type": "raise", "size_bb": 4.5, "position": "SB"}
    assert compute_target_node_offset(
        sb_jam, 5, {}, 4.5, st, position_total_bb=st) == 4


def test_offset_8max_deep_utg1_mp_positions():
    """8-max deep (100) → 1 linha cada. UTG=0, UTG1=1, MP=2, HJ=3, CO=4, BTN=5."""
    st = {"UTG": 100.0, "UTG1": 100.0, "MP": 100.0, "HJ": 100.0,
          "CO": 100.0, "BTN": 100.0, "SB": 100.0, "BB": 100.0}
    base = {"type": "raise", "size_bb": 2.0}
    for pos, exp in [("UTG", 0), ("UTG1", 1), ("MP", 2), ("HJ", 3),
                     ("CO", 4), ("BTN", 5)]:
        assert compute_target_node_offset(
            {**base, "position": pos}, 8, {}, 100.0, st, position_total_bb=st,
        ) == exp


# ── PKO Regra 3 shift + colapso shift (end-to-end) ─────────────────────

def test_compute_offset_pko_iso_shifts_anchor():
    """PKO + shortie atrás (BB=3) → Regra 3 acrescenta a linha de all-in a cada
    posição anterior ao raiser → âncora sobe. CO: baseline 2 → PKO 4."""
    totals = {"UTG": 50.0, "HJ": 50.0, "CO": 50.0,
              "BTN": 50.0, "SB": 50.0, "BB": 3.0}
    agg = {"position": "CO", "type": "raise", "size_bb": 2.0}
    assert compute_target_node_offset(agg, 6, {}, 50.0, totals) == 2
    assert compute_target_node_offset(
        agg, 6, {}, 50.0, totals, is_pko=True, position_total_bb=totals) == 4


def test_compute_offset_rule1_collapse_shifts_anchor():
    """Mesa toda curta (8 BB): cada open colapsa a 1 linha (era 2 no layout cheio).
    CO jam → UTG(1)+HJ(1)+within(bucket 1 → 0) = 2."""
    totals = {"UTG": 8.0, "HJ": 8.0, "CO": 8.0,
              "BTN": 8.0, "SB": 8.0, "BB": 8.0}
    agg = {"position": "CO", "type": "raise", "size_bb": 8.0}
    assert compute_target_node_offset(
        agg, 6, {}, 8.0, totals, position_total_bb=totals) == 2


def test_open_node_eff_and_shortie_v3_remaining_and_shortie():
    """eff (régua v3) = min(remaining own, maior remaining atrás); yet_short usa
    os TOTAIS (≤4). Aqui remaining=total (mesmo dict)."""
    totals = {"UTG": 50.0, "HJ": 40.0, "CO": 30.0,
              "BTN": 25.0, "SB": 20.0, "BB": 3.0}
    eff, own, yet = _open_node_eff_and_shortie("UTG", 6, totals, totals)
    assert (eff, own, yet) == (40.0, 50.0, True)   # capado por HJ=40; BB=3≤4
    eff_sb, own_sb, yet_sb = _open_node_eff_and_shortie("SB", 6, totals, totals)
    assert (eff_sb, own_sb, yet_sb) == (3.0, 20.0, True)  # só BB atrás (3)


# ── within-bucket deriva do nº REAL de linhas (bucket_rows) ─────────────

def test_within_bucket_uses_real_rows_non_sb_jam_collapsed():
    """non-SB jam num bucket COLAPSADO a 1 linha → within 0 (não 1)."""
    action = {"position": "CO", "type": "raise", "size_bb": 7.0}
    assert offset_within_bucket(action, raiser_stack_bb=7.1, bucket_rows=1) == 0
    assert offset_within_bucket(action, raiser_stack_bb=7.1, bucket_rows=2) == 1


def test_within_bucket_uses_real_rows_sb_jam_collapsed():
    """SB jam: bucket [Complete, ALLIN] (2 linhas) → within 1; [Complete, small,
    ALLIN] (3) → 2."""
    action = {"position": "SB", "type": "raise", "size_bb": 4.24}
    assert offset_within_bucket(action, raiser_stack_bb=4.37, bucket_rows=2) == 1
    assert offset_within_bucket(action, raiser_stack_bb=4.37, bucket_rows=3) == 2


def test_within_bucket_legacy_fallback_without_bucket_rows():
    """Sem bucket_rows (chamadas directas/legacy) → layout cheio (non-SB jam=1,
    SB jam=2)."""
    assert offset_within_bucket({"position": "CO", "type": "raise", "size_bb": 7.0},
                                raiser_stack_bb=7.1) == 1
    assert offset_within_bucket({"position": "SB", "type": "raise", "size_bb": 6.35},
                                raiser_stack_bb=6.47) == 2


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


def test_compute_target_node_offset_no_stacks_base_only():
    """Sem stacks por posição → eff None → count_lines base-only (1 linha cada).
    8-max, MP open small: UTG(1)+UTG1(1) = 2."""
    action = {"type": "raise", "size_bb": 2.0, "position": "MP"}
    assert compute_target_node_offset(
        action, seats_at_table=8, script_overrides={}, raiser_stack_bb=102.72,
    ) == 2


def test_compute_target_node_offset_aggressor_not_a_dict_returns_none():
    """Defensivo: input não-dict → None com WARN."""
    assert compute_target_node_offset("not a dict", 5, {}, 50.0) is None
    assert compute_target_node_offset([], 5, {}, 50.0) is None


def test_compute_target_node_offset_unknown_position_returns_none():
    """Position válida mas não em strategy_table_positions(N) → None."""
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
