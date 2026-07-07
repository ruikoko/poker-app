"""#PAYOUT-COHERENCE — guarda de sanidade dos payouts lidos por Vision (7 Jul).

Segunda defesa, independente do gate do Info (`#LOBBY-INFO-NO-PAYOUT`): apanha
Vision ALUCINADA em QUALQUER aba/fonte (ex.: fichas dos jogadores lidas como
prémios — `269061 > 9494` — ou escada de prémios fora de ordem). Vale para TODAS
as fontes Vision que escrevem `tournament_payouts` (lobby live, reconcile, backoffice).

Regra (spec Rui, 7 Jul) — rejeita (não escreve + sinaliza `payout_incoherent`) se
falhar QUALQUER de:
  (a) prize_gt_pool  — algum prémio > prize_pool de referência.
  (b) sum_gt_pool    — Σ prémios > prize_pool × 1.05 (folga p/ arredondamentos).
  (c) non_monotonic  — a escada SOBE (prémio de rank posterior > anterior); empates
                       passam (patamares iguais são normais).

Referência de pool: `tournament_summaries.prize_pool` quando existir; senão o
`prize_pool` da própria Vision. Sem prémios ou sem referência → NÃO julga (passa):
não há base para bloquear. A monotonia corre sobre a lista FINAL EXPANDIDA (singles
`prizes` + `prize_ranges` desenrolados) — o que vai para o blob.
"""
from __future__ import annotations

from typing import Optional

from app.db import query
from app.services.lobby_vision import _expand_prize_ranges

# Folga da regra (b) para arredondamentos da Vision/rake.
_SUM_TOLERANCE = 1.05


def assert_payout_coherent(expanded_prizes, prize_pool_ref) -> tuple[bool, Optional[str]]:
    """(a)+(b)+(c) sobre a lista EXPANDIDA. (True, None) = coerente OU sem base para
    julgar (sem prémios / sem referência). (False, reason) caso contrário."""
    if not isinstance(expanded_prizes, dict) or not expanded_prizes:
        return True, None
    try:
        ref = float(prize_pool_ref) if prize_pool_ref is not None else None
    except (TypeError, ValueError):
        ref = None
    if not ref or ref <= 0:
        return True, None                       # sem referência fiável → não julga

    items: list[tuple[int, float]] = []
    for k, v in expanded_prizes.items():
        if isinstance(v, bool) or not isinstance(v, (int, float)):
            continue
        if not str(k).isdigit():
            continue
        items.append((int(k), float(v)))
    if not items:
        return True, None
    items.sort(key=lambda x: x[0])              # por rank ascendente
    vals = [v for _, v in items]

    if max(vals) > ref:                         # (a)
        return False, "prize_gt_pool"
    if sum(vals) > ref * _SUM_TOLERANCE:        # (b)
        return False, "sum_gt_pool"
    for (_, a), (_, b) in zip(items, items[1:]):
        if b > a:                               # (c) sobe → incoerente (empate passa)
            return False, "non_monotonic"
    return True, None


def _pool_ref(site: str, tn: str, vj: dict):
    """Melhor referência de pool: TS.prize_pool se existir e > 0; senão o da Vision."""
    try:
        r = query(
            "SELECT prize_pool FROM tournament_summaries "
            "WHERE site = %s AND tournament_number = %s",
            (site, tn),
        )
    except Exception:
        r = None
    ts_pool = r[0].get("prize_pool") if r else None
    if ts_pool and float(ts_pool) > 0:
        return ts_pool
    return (vj or {}).get("prize_pool")


def check_vj_payout_coherent(site: str, tn: str, vj: dict) -> tuple[bool, Optional[str]]:
    """Conveniência p/ os call-sites: expande os prémios do `vj` (o que vai para o
    blob) + lookup da referência + coerência. Devolve (ok, reason|None)."""
    expanded = _expand_prize_ranges(
        (vj or {}).get("prizes") or {}, (vj or {}).get("prize_ranges") or []
    )
    return assert_payout_coherent(expanded, _pool_ref(site, tn, vj))
