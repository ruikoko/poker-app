"""Resultados HRC — secção nova (arranque 16 Jul 2026, por fases).

**Fase 1 (esta):** landing read-only com agregados das mãos resolvidas (`hrc_jobs`
`status='done'`) — Cartão 1 (totais · por sala · por formato) + Cartão 3 (top torneios
por INSTÂNCIA = `tournament_number`) + lista "últimas resolvidas" colapsável por instância
de torneio. Tudo SQL barato sobre `hands` + `hrc_jobs` (não abre zips).

**Fase 1b (a seguir):** Cartão 2 "Top EV perdido" — precisa do motor de EV (lê `evs[]` por
ação dos nós do `result_zip`, em `TABLE_EQUITY_PERCENT`), partilhado com a página da mão
(Fase 2). Até lá, `ev_ready=false` e `top_ev_loss=[]`.

Caderno + protótipo validados 14 Jul (`_local_only/proto_hrc_resultados/`, `JOURNAL_2026-07-14`).
"""
from __future__ import annotations

from collections import Counter, OrderedDict

from fastapi import APIRouter, Depends

from app.auth import require_auth
from app.db import query

router = APIRouter(prefix="/api/hrc/results", tags=["hrc-results"])

_PKO_FORMATS = {"pko", "super ko", "ko", "superko", "bounty"}


def _fmt_label(fmt) -> str:
    """Formato normalizado para os agregados: PKO (qualquer KO) vs Vanilla."""
    return "PKO" if (fmt or "").strip().lower() in _PKO_FORMATS else "Vanilla"


def _played_str(dt) -> str | None:
    """played_at (timestamp naive Lisboa, pt51) -> 'YYYY-MM-DD HH:MM:SS' | None."""
    if dt is None:
        return None
    try:
        return dt.isoformat(sep=" ")[:19]
    except (AttributeError, TypeError):
        return str(dt)[:19]


def _instance_label(name: str, played_s: str | None) -> str:
    """Rótulo da instância de torneio: nome + 'dd/mm HHh' (distingue os vários
    'Daily Hyper $60' do dia). played_s = 'YYYY-MM-DD HH:MM:SS'."""
    if played_s and len(played_s) >= 16:
        return f"{name} · {played_s[8:10]}/{played_s[5:7]} {played_s[11:13]}h"
    return name


@router.get("/summary")
def results_summary(current_user=Depends(require_auth)):
    """Agregados da landing dos Resultados HRC (Fase 1). Read-only."""
    rows = query(
        "SELECT h.id, h.hand_id, h.site, h.tournament_format, h.tournament_name, "
        "       h.tournament_number AS tn, h.buy_in, h.played_at, "
        "       j.result_zip_size AS zsize, j.completed_at "
        "FROM hrc_jobs j JOIN hands h ON h.id = j.hand_db_id "
        "WHERE j.status = 'done' AND j.result_zip IS NOT NULL "
        "ORDER BY j.completed_at DESC NULLS LAST"
    )

    by_site: Counter = Counter()
    by_format: Counter = Counter()
    recent: list[dict] = []
    inst: "OrderedDict[str, dict]" = OrderedDict()

    for r in rows:
        d = dict(r)
        site = d.get("site") or "—"
        fmt = _fmt_label(d.get("tournament_format"))
        played_s = _played_str(d.get("played_at"))
        tn = str(d.get("tn") or "")
        name = d.get("tournament_name") or "—"

        by_site[site] += 1
        by_format[fmt] += 1
        recent.append({
            "hand_id": d["hand_id"],
            "site": site,
            "format": fmt,
            "tn": tn,
            "tournament": name,
            "buy_in": (f'{d["buy_in"]:.2f}' if d.get("buy_in") is not None else None),
            "played_at": played_s,
            "zsize": d.get("zsize"),
        })

        if tn not in inst:
            inst[tn] = {"tn": tn, "name": name, "site": site, "format": fmt,
                        "count": 0, "played_at": played_s}
        inst[tn]["count"] += 1
        if played_s and (inst[tn]["played_at"] is None or played_s < inst[tn]["played_at"]):
            inst[tn]["played_at"] = played_s

    tourneys_inst = sorted(inst.values(), key=lambda x: (x["count"], x["played_at"] or ""),
                           reverse=True)
    for x in tourneys_inst:
        x["label"] = _instance_label(x["name"], x.get("played_at"))

    return {
        "total_resolved": len(rows),
        "by_site": dict(by_site),
        "by_format": dict(by_format),
        "instances_total": len(inst),
        "top_tourneys_inst": tourneys_inst[:5],
        "recent_by_tourney": recent,
        # Fase 1b — Cartão 2 "Top EV perdido" (motor de EV, partilhado c/ página da mão)
        "ev_ready": False,
        "top_ev_loss": [],
    }
