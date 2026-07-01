"""Guardião de validação — "Mãos suspeitas" (fila de revisão viva, read-only).

Lista as mãos GG 2026 (`site='GGPoker'`, `played_at>='2026-01-01'`) apanhadas por
DOIS venenos PUROS e determinísticos. Consulta na hora → cobre o retroativo (varre
a BD atual) E o contínuo (mãos novas) no mesmo sítio. NÃO altera nada.

1. **Bounty abaixo de metade** — reusa `detect_bounty_below_half` (extraída de
   `queue_export`, fonte única com a guarda `bounty_below_half_base`). Gate à
   partida no SQL: só GG PKO/KO com `tournament_summaries.buy_in_bounty`.
2. **O teu nome num vilão** — par (chave, valor) no `player_names.anon_map` com
   chave != 'Hero' E valor ∈ HERO_NAMES. ⚠️ A chave 'Hero' é EXCLUÍDA sempre — o
   Hero mapeia-se a si próprio (senão dá centenas de falsos positivos).

O veneno 3 (`review_alarm`) fica FORA desta versão (não é persistido).
"""
from __future__ import annotations

import json
import logging

from fastapi import APIRouter, Depends

from app.auth import require_auth
from app.db import query
from app.hero_names import HERO_NAMES
from app.services.queue_export import TS_GATED_FORMATS, detect_bounty_below_half

router = APIRouter(prefix="/api/suspicious-hands", tags=["suspicious-hands"])
logger = logging.getLogger("suspicious_hands")

_GG_2026 = "h.site = 'GGPoker' AND h.played_at >= '2026-01-01'"
_HERO_SET = {n.lower().strip() for n in HERO_NAMES}


def _bounty_below_half_hands() -> list[dict]:
    """Veneno 1. Gate no SQL (GG PKO/KO com base do TS); detalhe em Python."""
    rows = query(
        f"""SELECT h.id, h.hand_id, h.tournament_name,
                   h.played_at::text AS played_at,
                   h.player_names AS pn, ts.buy_in_bounty AS base
              FROM hands h
              JOIN tournament_summaries ts
                ON ts.site = 'GGPoker'
               AND ts.tournament_number = h.tournament_number
             WHERE {_GG_2026}
               AND ts.buy_in_bounty IS NOT NULL
               AND lower(COALESCE(h.tournament_format, '')) = ANY(%s)
             ORDER BY h.played_at DESC""",
        (list(TS_GATED_FORMATS),),
    )
    out = []
    for r in rows:
        below = detect_bounty_below_half(r["pn"], r["base"])
        if below:
            out.append({
                "id": r["id"], "hand_id": r["hand_id"],
                "tournament_name": r["tournament_name"], "played_at": r["played_at"],
                "detail": {
                    "floor": below[0]["floor"],
                    "seats": [{"name": b["name"], "value": b["value"],
                               "min": b["floor"]} for b in below],
                },
            })
    return out


def _hero_name_on_villain_hands() -> list[dict]:
    """Veneno 2. anon_map com chave != 'Hero' cujo valor é conta do Rui."""
    rows = query(
        f"""SELECT h.id, h.hand_id, h.tournament_name,
                   h.played_at::text AS played_at, h.player_names AS pn
              FROM hands h
             WHERE {_GG_2026}
               AND h.player_names -> 'anon_map' IS NOT NULL
             ORDER BY h.played_at DESC"""
    )
    out = []
    for r in rows:
        pn = r["pn"] or {}
        if isinstance(pn, str):
            try:
                pn = json.loads(pn)
            except (ValueError, TypeError):
                pn = {}
        amap = pn.get("anon_map") or {}
        hits = [{"hash": k, "nick": v} for k, v in amap.items()
                if k != "Hero" and isinstance(v, str)
                and v.lower().strip() in _HERO_SET]
        if hits:
            out.append({
                "id": r["id"], "hand_id": r["hand_id"],
                "tournament_name": r["tournament_name"], "played_at": r["played_at"],
                "detail": {"hero": pn.get("hero"), "hits": hits},
            })
    return out


def _build_groups() -> tuple[list[dict], list[dict]]:
    return _bounty_below_half_hands(), _hero_name_on_villain_hands()


@router.get("")
def list_suspicious(current_user=Depends(require_auth)):
    """READ-ONLY. Fila viva das mãos GG 2026 apanhadas pelos 2 venenos puros,
    agrupadas por motivo, com detalhe por mão."""
    g1, g2 = _build_groups()
    return {
        "counts": {
            "bounty_below_half": len(g1),
            "hero_name_on_villain": len(g2),
            "total": len(g1) + len(g2),
        },
        "groups": [
            {
                "key": "bounty_below_half",
                "label": "Bounty abaixo de metade",
                "description": (
                    "A coroa ($ bounty) gravada é menor que metade do bounty base "
                    "do torneio. A coroa é o KO instantâneo = metade → nunca < base÷2; "
                    "provável leitura da chama (VPIP %) em vez da coroa ($)."
                ),
                "count": len(g1),
                "hands": g1,
            },
            {
                "key": "hero_name_on_villain",
                "label": "O teu nome num vilão",
                "description": (
                    "Um lugar não-Hero ficou gravado com um nick que é conta do Rui "
                    "(HERO_NAMES) — provável troca da desanon com um amigo à mesa."
                ),
                "count": len(g2),
                "hands": g2,
            },
        ],
    }


@router.get("/count")
def count_suspicious(current_user=Depends(require_auth)):
    """READ-ONLY. Só as contagens (badge da barra lateral)."""
    g1, g2 = _build_groups()
    return {
        "bounty_below_half": len(g1),
        "hero_name_on_villain": len(g2),
        "total": len(g1) + len(g2),
    }
