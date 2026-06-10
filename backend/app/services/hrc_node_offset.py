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

from app.services.hrc_script_gen import _parse_seat_stacks
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

# Cada bucket SIZES_OPEN_* no template canónico tem 2 entradas por
# defeito (size real + ALLIN). Override do Trabalho A pode reduzir para 1.
_TEMPLATE_DEFAULT_OPEN_COUNT = 2

# Linhas extra que existem na Strategy Table independentes dos opens.
_SB_COMPLETE_LINES = 1


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
    return "SIZES_OPEN_OTHERS"


def count_lines_for_position(
    position: str, script_overrides: dict
) -> int:
    """Nº de linhas que `position` ocupa na Strategy Table HRC.

    SB tem +1 linha de Complete (limp) prepended aos seus opens.
    """
    if not isinstance(script_overrides, dict):
        script_overrides = {}
    bucket = _bucket_open_for_position(position)
    overrides = script_overrides.get(bucket)
    count = (
        len(overrides) if isinstance(overrides, list) and overrides
        else _TEMPLATE_DEFAULT_OPEN_COUNT
    )
    if (position or "").upper() == "SB":
        count += _SB_COMPLETE_LINES
    return count


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
) -> int:
    """Offset do nó do raiser DENTRO do seu bucket na Strategy Table (0, 1 ou 2).

    A Strategy Table HRC mostra, por posição, os sizings por ordem ASCENDENTE
    de tamanho — e o nó **ALLIN** (= stack do jogador) é sempre o **maior**, logo
    o **ÚLTIMO** do bucket:
      - non-SB:  `[small/min-raise, ALLIN]`            → small=0 ; **jam=1**
      - SB:      `[Complete, small/min-raise, ALLIN]`  → Complete=0 ; small=1 ; **jam=2**
    O nó-alvo é a acção REAL do agressor: um small-raise é o 1º nó de raise; um
    **jam** (all-in efectivo, `_is_all_in_effective`) é o nó **ALLIN** (último).

    pt67 (#HRC-NODE-OFFSET-OFFBY1-REVERT-PT61): REVERTE o pt61
    (#HRC-NODE-OFFSET-SB-JAM-OFFBY1), que colapsara isto para `0` (non-SB) / `1`
    (SB raise) — assumindo que o alvo é sempre o 1º nó. A 1ª smoke REAL da
    navegação (3ª volta pt67, provas visuais do Rui) desmentiu-o: o jam é o
    **último** nó (ALLIN), não o primeiro. O pt61 era teoria "EM BUFFER" nunca
    validada em smoke. Cross-check (offsets confirmados visualmente / packs de
    6 Jun): GG-6029013400 (HJ jam 9.01/stack 9.16) → 7; GG-6039094225 (SB jam
    6.35/stack 6.47) → 14; GG-6028190109 (HJ small 2.0/stack 34.5) → 2.

    ⚠️ Latente (#HRC-NODE-OFFSET-IMPLICIT-LINES, LOW): a convenção assume 2 nós
    non-SB / 3 SB. Se um open-jam de stack muito curto não tiver nó small
    separado, o within podia ficar +1 comprido. A `count_lines_for_position`
    tem a assunção-irmã (linhas implícitas ALLIN/min do HRC). Por isso a
    confirmação VISUAL do nó é critério OBRIGATÓRIO de toda a smoke de navegação.
    """
    pos = (action.get("position") or "").upper()
    action_type = (action.get("type") or "").lower()
    is_jam = _is_all_in_effective(action.get("size_bb"), raiser_stack_bb)
    if pos == "SB":
        # SB tem o nó Complete (limp) prepended antes dos raises.
        if action_type in ("complete", "limp", "call"):
            return 0
        return 2 if is_jam else 1
    return 1 if is_jam else 0


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
    raiser_idx = positions.index(position)
    offset = 0
    for p in positions[:raiser_idx]:
        offset += count_lines_for_position(p, overrides)
    offset += offset_within_bucket(aggressor_real_action, raiser_stack_bb)
    return offset
