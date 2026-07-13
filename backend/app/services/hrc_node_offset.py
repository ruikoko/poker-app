"""Compute `target_node_offset` for the watcher's arrow-nav step.

pt25e Bloco 2 piece 2 (#WATCHER-BUG-G-NAV-TO-RAISER-NODE). Após a 1ª run
do HRC terminar, a Strategy Table tem o cursor na 1ª linha (UTG, smallest
open). Para a 2ª run em Selected Subtree, o watcher precisa de premer
seta-para-baixo N vezes até o cursor pousar na linha do sizing real do
raiser inicial — calculado aqui.

Ordem das linhas na Strategy Table HRC (preflop opens), validada
empíricamente pelo Rui:
  UTG → (EP/MP/HJ consoante N) → CO → BU → SB
  (BB nunca aparece — BB não abre preflop.)

Cada posição expande para `len(SIZES_OPEN_<POS>)` linhas (1 ou 2, consoante
a regra dos 25BB do Trabalho A em `hrc_script_gen.build_sizings_overrides`).
SB tem +1 linha extra de Complete (limp) antes das suas opens — o template
`canFlatCallPreflop` permite SB-only complete em bets==1.

Algoritmo:
1. `positions = strategy_table_positions(seats_at_table)` — lista sem BB.
2. `raiser_idx = positions.index(aggressor.position)`.
3. Soma `count_lines_for_position` para todas as posições antes do raiser.
4. Adiciona `offset_within_bucket` da acção do raiser (all-in-dependent:
   small=0 / jam=1 non-SB; Complete=0 / small=1 / jam=2 SB).

pt67 (#HRC-NODE-OFFSET-OFFBY1-REVERT-PT61): `offset_within_bucket` voltou a
DEPENDER de all-in. O nó **ALLIN** (= stack) é o **maior** → o **último** do
bucket (ordem ascendente do HRC). Um jam aponta para esse último nó. O pt61
(#HRC-NODE-OFFSET-SB-JAM-OFFBY1) tinha colapsado o offset para "1º nó" (0/1),
assumindo o alvo no início — mas a 1ª smoke REAL da navegação (pt67, provas
visuais do Rui) mostrou o jam no **último** nó. O pt61 era "EM BUFFER", nunca
validado em smoke. `_is_all_in_effective` (threshold 0.95) volta a ser usado.
"""
from __future__ import annotations
import logging
from typing import Optional

from app.services.hrc_script_gen import _parse_seat_stacks, _canonical_3bet_position
from app.services.queue_export import (
    _POSITION_LABELS_BY_N,
    find_preflop_marker,
)
import re

logger = logging.getLogger("hrc_node_offset")


# Estratégia: tudo >= 95% da stack inicial do raiser conta como all-in
# efectivo. Cobre os casos shove/jam mesmo quando o sizing exacto que sai
# no HH é ligeiramente abaixo da stack total (ante a pagar antes do
# raise, dust pots, etc).
_ALL_IN_EFFECTIVE_THRESHOLD = 0.95

# Legacy (pré-pt86): contagem estrutural sem stack — usada no fallback defensivo
# (stack indisponível) e pelos testes estruturais. Mantida verbatim.
_TEMPLATE_DEFAULT_OPEN_COUNT = 2

# Linhas extra que existem na Strategy Table independentes dos opens.
_SB_COMPLETE_LINES = 1

# pt86 — defaults dos arrays de open do template canónico
# (`mtt_advanced_canonical_2026.js`): 1 sizing por bucket, SEM ALLIN (o ALLIN
# implícito é adicionado em runtime pelo template, por stack individual).
_TEMPLATE_DEFAULT_OPEN_ARRAY = {
    # pt89 (#GTO-OPEN-SIZE-NOT-PER-POSITION) — opens per-posição (era só OTHERS).
    "SIZES_OPEN_UTG1": [2.0],
    "SIZES_OPEN_UTG": [2.0],
    "SIZES_OPEN_MP": [2.0],
    "SIZES_OPEN_HJ": [2.0],
    "SIZES_OPEN_CO": [2.0],
    "SIZES_OPEN_OTHERS": [2.0],   # fallback defensivo
    "SIZES_OPEN_BU": [2.0],
    "SIZES_OPEN_SB": [3.5],
    "SIZES_OPEN_BB": [4.0],
}

# pt86 — limiar do ALLIN implícito em opens (espelha `shouldAddPreflopAllIn`):
# 25 BB geral; 30 BB só em blind-vs-blind (na tabela de opens = a SB).
_OPEN_ALLIN_THRESHOLD_BB = 25.0
_OPEN_ALLIN_THRESHOLD_BVB_BB = 30.0

# pt91 (Regras 1 e 3 do Rui) — espelham as consts do template canónico
# (mtt_advanced_canonical_2026.js): OPEN_ALLIN_ONLY_EFF_BB e PKO_SHORTIE_BB.
# Regra 1: open com EFETIVO <= 9 → só all-in (1 linha). Regra 3 (PKO): shortie
# <= 4 BB acrescenta all-in. Manter em sync com o JS.
_OPEN_ALLIN_ONLY_EFF_BB = 9.0
_PKO_SHORTIE_BB = 4.0
# LEI v3 §A — as blinds (SB na strategy table) fazem jam abaixo de 10 BB (<10);
# as não-blind mantêm o colapso ≤9. Espelha BLIND_OPEN_JAM_BELOW_BB do template.
_BLIND_OPEN_JAM_BELOW_BB = 10.0


def _is_allin_token(s) -> bool:
    """ALLIN nos arrays: string "ALLIN" (backend) ou 9999 (sentinela template)."""
    if isinstance(s, str):
        return s.strip().upper() == "ALLIN"
    if isinstance(s, (int, float)):
        return s >= 9000
    return False


def strategy_table_positions(seats_at_table: int) -> list:
    """Lista de positions que aparecem na Strategy Table preflop, na ordem
    de cima para baixo. BB nunca aparece (não abre preflop).

    `seats_at_table` é o nº de jogadores sentados na mesa real quando a mão
    começou (não a redução `max_players` para ICM). A Strategy Table HRC
    mostra uma linha por jogador real sentado, independentemente da
    redução ICM aplicada na página Edit Settings.

    Devolve `[]` se `seats_at_table` inválido (não em 2..9)."""
    labels = _POSITION_LABELS_BY_N.get(seats_at_table)
    if not labels:
        return []
    return [p for p in labels if p != "BB"]


def _bucket_open_for_position(position: str) -> str:
    """Position → nome do bucket SIZES_OPEN_* (idêntico a
    `hrc_script_gen._position_bucket_open` mas duplicado aqui para evitar
    acoplamento por privacidade)."""
    p = (position or "").upper()
    if p in ("BU", "BTN", "BU/SB"):
        return "SIZES_OPEN_BU"
    if p == "SB":
        return "SIZES_OPEN_SB"
    if p == "BB":
        return "SIZES_OPEN_BB"
    # pt89 (#GTO-OPEN-SIZE-NOT-PER-POSITION) — espelha o gerador: per-posição.
    canon = _canonical_3bet_position(position)
    if canon and canon != "BU":
        return f"SIZES_OPEN_{canon}"
    return "SIZES_OPEN_OTHERS"   # fallback defensivo


def count_lines_for_position(
    position: str, script_overrides: dict = None, stack_bb=None,
    *, effective_bb=None, is_pko: bool = False, own_total_bb=None,
    yet_to_act_short_or_allin: bool = False,
) -> int:
    """Nº de linhas que `position` ocupa na Strategy Table HRC (open node).

    LEI v3 (15 Jul 2026) — os opens são **single-size** (a Regra de Ouro dá 1
    size real; senão 1 size base: IP 2 BB / SB e BB por eff). A linha de all-in
    é decidida por **EFETIVA** (§19 reformada — morre o "individual"). Logo o nº
    de linhas por posição-open =
        `1 (size base)` + `1 ALLIN se [eff ≤ limiar OU colapso ≤9 OU Regra 3]`
        + `1 Complete se SB`.
    Colapso `eff ≤ 9` → SÓ all-in (1 linha; + Complete se SB), exceto shortie
    próprio PKO. Limiar de all-in = **30** se SB (blind-vs-blind na tabela de
    opens), senão **25**.

    `effective_bb` = efetiva no nó de open desta posição (régua única, remaining;
    `min(remaining da posição, maior remaining vivo atrás)`), calculada pelo
    caller (`compute_target_node_offset`) a partir dos stacks REMAINING.
      - `None` → **legacy/defensivo**: 1 linha base (+ Complete SB). Sem efetiva
        não se pode decidir a linha de all-in → conta só a base (back-compat).

    `is_pko` + `own_total_bb` + `yet_to_act_short_or_allin`: Regra 3-em-open — em
    PKO, força a linha de all-in quando o próprio opener é shortie (<= 4 BB) OU há
    adversário por falar all-in / <= 4 BB.

    `script_overrides` e `stack_bb` ficam na assinatura por back-compat mas já
    **não** decidem as linhas (opens single-size na v3).
    """
    pos = (position or "").upper()
    shortie_own = (
        bool(is_pko) and own_total_bb is not None
        and float(own_total_bb) <= _PKO_SHORTIE_BB
    )

    # ── Sem efetiva (legacy/defensivo): 1 linha base (+ Complete SB) ──
    if effective_bb is None:
        lines = 1
        if pos == "SB":
            lines += _SB_COMPLETE_LINES
        return max(1, lines)

    eff = float(effective_bb)
    threshold = _OPEN_ALLIN_THRESHOLD_BVB_BB if pos == "SB" else _OPEN_ALLIN_THRESHOLD_BB

    # ── Colapso → SÓ all-in (1 linha), exceto shortie próprio PKO. A letra do
    #    quadro: SB (blind) faz jam abaixo de 10 (<10); não-blind mantém ≤9. ──
    collapse = (eff < _BLIND_OPEN_JAM_BELOW_BB) if pos == "SB" else (eff <= _OPEN_ALLIN_ONLY_EFF_BB)
    if collapse and not shortie_own:
        lines = 1
        if pos == "SB":
            lines += _SB_COMPLETE_LINES
        return max(1, lines)

    # ── Linha de all-in por EFETIVA (§19 v3) + Regra 3 (shortie PKO) ──
    add_allin = (
        eff <= threshold
        or shortie_own
        or (bool(is_pko) and yet_to_act_short_or_allin)
    )
    lines = 1 + (1 if add_allin else 0)
    if pos == "SB":
        lines += _SB_COMPLETE_LINES
    return max(1, lines)


def derive_position_stacks_bb(hh_text, level_sb, level_bb, seats=None) -> dict:
    """`{position_label: remaining_bb}` no nó de open de cada posição — stack
    inicial dos Seat lines MENOS o que já postou (antes/blinds), espelhando o
    `getChipsRemaining(player)/BB` do template. Usado por
    `compute_target_node_offset` para o limiar 25/30. `{}` defensivo."""
    if not hh_text or not isinstance(level_bb, (int, float)) or level_bb <= 0:
        return {}
    try:
        from app.services.hrc_script_gen import (
            _parse_seat_stacks, _init_pot_from_blinds_antes,
        )
        from app.services.queue_export import derive_seats_in_preflop_order
        if seats is None:
            seats = derive_seats_in_preflop_order(hh_text)
        initial = _parse_seat_stacks(hh_text)
        contributions, _pot, _ctc = _init_pot_from_blinds_antes(
            hh_text, seats, level_sb, level_bb,
        )
    except Exception:
        logger.exception("derive_position_stacks_bb falhou")
        return {}
    out: dict = {}
    for e in seats or []:
        nick, pos = e.get("nick"), e.get("position")
        ini = initial.get(nick) if nick else None
        if not pos or ini is None:
            continue
        remaining = float(ini) - float(contributions.get(nick, 0.0))
        out[pos] = round(remaining / float(level_bb), 2)
    return out


def derive_position_total_stacks_bb(hh_text, level_bb, seats=None) -> dict:
    """pt91 — `{position_label: total_bb}` = stack INICIAL (Seat line) por posição,
    em BB. Espelha `totalStackChips(p)/BB` do template no nó de open (= inicial,
    porque o que já está no pote nessa street ainda é "stack do jogador a risco").

    Usado pela Regra 1 (efetivo = min(opener, maior vivo)) e Regra 3 (shortie).
    `{}` defensivo (HH/level inválidos ou parse falhado)."""
    if not hh_text or not isinstance(level_bb, (int, float)) or level_bb <= 0:
        return {}
    try:
        from app.services.queue_export import derive_seats_in_preflop_order
        if seats is None:
            seats = derive_seats_in_preflop_order(hh_text)
        initial = _parse_seat_stacks(hh_text)
    except Exception:
        logger.exception("derive_position_total_stacks_bb falhou")
        return {}
    out: dict = {}
    for e in seats or []:
        nick, pos = e.get("nick"), e.get("position")
        ini = initial.get(nick) if nick else None
        if not pos or ini is None:
            continue
        out[pos] = round(float(ini) / float(level_bb), 2)
    return out


def _open_node_eff_and_shortie(
    position: str, seats_at_table: int, position_remaining_bb: dict,
    position_total_bb: dict = None,
):
    """LEI v3 — para o nó de open de `position` (cenário fold-to-position):
    devolve `(effective_bb, own_total_bb, yet_to_act_short_or_allin)`.

    - opponents = posições que actuam DEPOIS na ordem de _POSITION_LABELS_BY_N
      (incl. blinds; em fold-to-position todos os de trás estão vivos e por falar).
    - **effective = régua única = min(REMAINING da posição, MAIOR REMAINING vivo
      atrás)** — espelha `effVsFieldBB` do template.
    - Regra 3 (shortie) usa os stacks **TOTAIS**: `own_total` e `yet_short` =
      algum opp com TOTAL <= 4 BB. `position_total_bb=None` → usa o remaining.
    Falta de dados → `(None, own_total, False)` (linha de all-in inerte nessa
    posição → count_lines cai na base).
    """
    labels = _POSITION_LABELS_BY_N.get(seats_at_table) or []
    if position_total_bb is None:
        position_total_bb = position_remaining_bb
    own_rem = position_remaining_bb.get(position)
    own_tot = position_total_bb.get(position)
    if not labels or position not in labels or own_rem is None:
        return None, own_tot, False
    after = labels[labels.index(position) + 1:]
    opp_rem = [
        position_remaining_bb[p] for p in after if p in position_remaining_bb
    ]
    if not opp_rem:
        return None, own_tot, False
    effective = min(own_rem, max(opp_rem))
    opp_tot = [position_total_bb[p] for p in after if p in position_total_bb]
    yet_short = any(t <= _PKO_SHORTIE_BB for t in opp_tot)
    return round(effective, 2), own_tot, yet_short


def _is_all_in_effective(
    size_bb: Optional[float], raiser_stack_bb: Optional[float]
) -> bool:
    """True sse `size_bb >= raiser_stack_bb * _ALL_IN_EFFECTIVE_THRESHOLD`.

    `None` em qualquer input → False (graceful: trata como small raise).
    """
    if size_bb is None or raiser_stack_bb is None or raiser_stack_bb <= 0:
        return False
    return float(size_bb) >= raiser_stack_bb * _ALL_IN_EFFECTIVE_THRESHOLD


def offset_within_bucket(
    action: dict,
    raiser_stack_bb: Optional[float] = None,
    *,
    bucket_rows: Optional[int] = None,
) -> int:
    """Offset do nó do raiser DENTRO do seu bucket na Strategy Table.

    A Strategy Table HRC mostra, por posição, os sizings por ordem ASCENDENTE
    de tamanho; o nó **ALLIN** (= stack) é o **maior** → a **ÚLTIMA** linha do
    bucket. O Complete da SB (limp) é a 1ª. O nó-alvo é a acção REAL do agressor:
      - Complete/limp da SB                       → 0 (1ª linha).
      - small-raise                               → 1ª linha de raise (SB:1 / non-SB:0).
      - **jam** (all-in efectivo)                 → **ÚLTIMA** linha = `bucket_rows - 1`.

    pt92 (#HRC-NODE-OFFSET-IMPLICIT-LINES, FIX): o jam deixa de assumir um layout
    FIXO (`non-SB→1` / `SB→2`, que pressupunha um nó small SEMPRE presente). O
    bucket do abridor pode ter **COLAPSADO para 1 linha** (Regra 1, eff≤9; ou o
    size É o all-in → array `[ALLIN]`), e aí o jam está no índice **0** (non-SB) /
    **1** (SB, depois do Complete), não 1/2. Agora o índice deriva do nº REAL de
    linhas — `bucket_rows`, calculado pelo caller via `count_lines_for_position`
    (a MESMA lógica de colapso das outras posições) → o jam aponta sempre para a
    última linha existente. Verificado tree-a-tree (pt92): GG-6113941263 SB jam
    (2 linhas) → 1; WN-…-13 CO jam (1 linha) → 0; GG-6114196293 CO jam (1) → 0.

    `bucket_rows` ausente → fallback legacy (assume o layout cheio: SB jam=2 /
    non-SB jam=1) — só para chamadas directas/testes que não o passam; o
    `compute_target_node_offset` passa-o SEMPRE.
    """
    pos = (action.get("position") or "").upper()
    action_type = (action.get("type") or "").lower()
    is_jam = _is_all_in_effective(action.get("size_bb"), raiser_stack_bb)

    if pos == "SB":
        # SB tem o nó Complete (limp) prepended antes dos raises.
        if action_type in ("complete", "limp", "call"):
            return 0
        if is_jam:
            return (bucket_rows - 1) if bucket_rows else 2  # última linha
        return 1   # 1º small-raise (a seguir ao Complete)
    if is_jam:
        return (bucket_rows - 1) if bucket_rows else 1      # última linha
    return 0       # 1º small-raise


# ── Aggressor stack derivation ──────────────────────────────────────────

_PREFLOP_OPEN_RE = re.compile(
    r"^([^\s:].*?)(?::)?\s+(raises|bets)\b",
    re.MULTILINE,
)


def _first_preflop_raiser_nick(hh_text: str) -> Optional[str]:
    """Nick do primeiro player a fazer raise/bet preflop. None se walk/limp."""
    if not hh_text:
        return None
    start = find_preflop_marker(hh_text)
    if start is None:
        return None
    end_flop = hh_text.find("*** FLOP ***", start)
    end_summary = hh_text.find("*** SUMMARY ***", start)
    ends = [e for e in (end_flop, end_summary) if e > 0]
    end = min(ends) if ends else len(hh_text)
    preflop = hh_text[start:end]
    m = _PREFLOP_OPEN_RE.search(preflop)
    if not m:
        return None
    return m.group(1).strip()


def derive_aggressor_stack_bb(
    hh_text: str, level_bb: Optional[int]
) -> Optional[float]:
    """Stack do primeiro raiser em BB, derivada das Seat lines do header.

    None se: HH vazio, level_bb inválido, nenhum raise preflop, ou nick
    do raiser não consta dos seats parseados."""
    if not hh_text or not isinstance(level_bb, (int, float)) or level_bb <= 0:
        return None
    nick = _first_preflop_raiser_nick(hh_text)
    if not nick:
        return None
    stacks = _parse_seat_stacks(hh_text)
    chips = stacks.get(nick)
    if chips is None:
        return None
    return round(float(chips) / float(level_bb), 2)


# ── Top-level: compute_target_node_offset ───────────────────────────────

def compute_target_node_offset(
    aggressor_real_action: Optional[dict],
    seats_at_table: Optional[int],
    script_overrides: Optional[dict],
    raiser_stack_bb: Optional[float],
    position_stacks_bb: Optional[dict] = None,
    *,
    is_pko: bool = False,
    position_total_bb: Optional[dict] = None,
) -> Optional[int]:
    """Posição (0-indexed) da linha do raiser real na Strategy Table HRC.

    `seats_at_table` é o nº de jogadores sentados na mesa real (não a
    redução `max_players` ICM). A Strategy Table HRC tem 1 linha-base por
    jogador sentado, expandida pelos sizes do script. pt27 fix: antes
    desta versão a função usava `max_players` (redução ICM), o que
    truncava `strategy_table_positions` e fazia o lookup da position do
    raiser falhar quando a redução escondia a posição real do agressor
    (e.g., 8-handed MP raise com max_players=6 → MP não está em
    strategy_table_positions(6)=[UTG,HJ,CO,BU,SB]).

    Devolve `None` em qualquer caso onde a navegação não faz sentido:
      - `aggressor_real_action is None` (walk-to-BB / limp-only).
      - `aggressor.position is None` (parsing de seats falhou).
      - `position == "BB"` (BB não aparece na Strategy Table de opens).
      - `seats_at_table` ausente ou fora de 2..9.

    Default `None` (vs `0`) escolhido para o watcher distinguir
    "não computei" de "computei e dá 0". Comportamento do watcher: skip
    arrow-nav em ambos os casos, mas log de None é mais informativo.
    """
    if aggressor_real_action is None:
        return None
    if not isinstance(aggressor_real_action, dict):
        logger.warning(
            "compute_target_node_offset: aggressor_real_action not a dict (%s)",
            type(aggressor_real_action).__name__,
        )
        return None
    position = aggressor_real_action.get("position")
    if not position:
        return None
    if (position or "").upper() == "BB":
        logger.info(
            "compute_target_node_offset: aggressor position is BB — "
            "not on Strategy Table opens view; returning None"
        )
        return None
    if (
        not isinstance(seats_at_table, int)
        or seats_at_table < 2
        or seats_at_table > 9
    ):
        logger.warning(
            "compute_target_node_offset: invalid seats_at_table=%s",
            seats_at_table,
        )
        return None
    positions = strategy_table_positions(seats_at_table)
    if position not in positions:
        logger.warning(
            "compute_target_node_offset: position %r not in "
            "strategy_table_positions(%d)=%s",
            position, seats_at_table, positions,
        )
        return None

    overrides = script_overrides or {}
    # LEI v3: efetiva (régua única) por posição = min(remaining da posição, maior
    # remaining vivo atrás). Usa os stacks REMAINING; fallback aos TOTAIS se só
    # esses vierem; `None` em ambos → count_lines cai na base (1 linha).
    remaining_map = position_stacks_bb or position_total_bb or {}
    totals_map = position_total_bb or position_stacks_bb or {}
    raiser_idx = positions.index(position)
    offset = 0
    for p in positions[:raiser_idx]:
        if remaining_map:
            eff_p, own_p, yet_short_p = _open_node_eff_and_shortie(
                p, seats_at_table, remaining_map, totals_map,
            )
        else:
            eff_p, own_p, yet_short_p = None, None, False
        offset += count_lines_for_position(
            p, overrides, None,
            effective_bb=eff_p, is_pko=is_pko, own_total_bb=own_p,
            yet_to_act_short_or_allin=yet_short_p,
        )
    # within-bucket do raiser: pt92 (#HRC-NODE-OFFSET-IMPLICIT-LINES FIX) — o
    # nº REAL de linhas do bucket do PRÓPRIO abridor vem do `count_lines_for_position`
    # (a MESMA lógica de colapso/limiar das outras posições), para o jam apontar
    # para a ÚLTIMA linha existente.
    if remaining_map:
        eff_a, own_a, yet_a = _open_node_eff_and_shortie(
            position, seats_at_table, remaining_map, totals_map,
        )
    else:
        eff_a, own_a, yet_a = None, None, False
    abridor_rows = count_lines_for_position(
        position, overrides, None,
        effective_bb=eff_a, is_pko=is_pko, own_total_bb=own_a,
        yet_to_act_short_or_allin=yet_a,
    )
    offset += offset_within_bucket(
        aggressor_real_action, raiser_stack_bb, bucket_rows=abridor_rows,
    )
    return offset
