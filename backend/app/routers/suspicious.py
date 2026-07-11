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
from app.hero_names import HERO_NAMES, HERO_NAMES_ALL
from app.services.queue_export import TS_GATED_FORMATS, detect_bounty_below_half

router = APIRouter(prefix="/api/suspicious-hands", tags=["suspicious-hands"])
logger = logging.getLogger("suspicious_hands")

_GG_2026 = "h.site = 'GGPoker' AND h.played_at >= '2026-01-01'"
_HERO_SET = {n.lower().strip() for n in HERO_NAMES}
# Inclui friend-heroes (Karluz/flightrisk são o Hero das SUAS mãos) — evita falsos
# positivos no veneno 3, que pergunta "o pn.hero é uma conta legítima de hero?".
_HERO_ALL_SET = {n.lower().strip() for n in HERO_NAMES_ALL}


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
            # #CROWN-VISIBLE-READ-ZERO (fix do filtro): distinguir estados/alarmes.
            #  - 'unread'    → TODAS as coroas em falta são $0 (por LER): âmbar, revisão.
            #  - 'impossible'→ há coroa >0 e <base÷2 (valor IMPOSSÍVEL gravado): vermelho.
            kind = "impossible" if any((b["value"] or 0) > 0 for b in below) else "unread"
            out.append({
                "id": r["id"], "hand_id": r["hand_id"],
                "tournament_name": r["tournament_name"], "played_at": r["played_at"],
                "kind": kind,
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


def _hero_alheio_hands() -> list[dict]:
    """Veneno 3 (#DESANON-HERO-ANCHOR-VALIDATION — ângulo cego do veneno 2). O `pn.hero`
    da mão NÃO é uma conta do Rui (HERO_NAMES_ALL). Aqui o nome do Rui está AUSENTE (não
    metido num vilão), logo o veneno 2 ("o teu nome num vilão") NÃO o apanha. Padrão: print
    PÓS-BUST / Vision marcou um vilão como is_hero → o Hero da mão ficou com o nick do vilão.

    Distingue o `apa['Hero']` (nomeação AUTORITÁRIA por lugar) do campo-resumo `pn.hero`:
    - `apa_hero` JÁ é o Rui → dano só no rótulo (COSMÉTICO — a propagação por hash curou o
      apa; basta sincronizar `pn.hero`, ex. via /set-anon-map com o mapa existente).
    - `apa_hero` também não é o Rui (ou ausente) → VENENO real: os nomes vieram de um print
      sem o Rui e não são fiáveis → reverter à anónima (`/api/table-ss/revert-to-anon`)."""
    rows = query(
        f"""SELECT h.id, h.hand_id, h.tournament_name,
                   h.played_at::text AS played_at,
                   h.player_names AS pn, h.all_players_actions AS apa
              FROM hands h
             WHERE {_GG_2026}
               AND (h.player_names->>'hero') IS NOT NULL
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
        hero = (pn.get("hero") or "").strip()
        if not hero or hero.lower() in _HERO_ALL_SET:
            continue                       # pn.hero é conta legítima → OK
        apa = r["apa"] or {}
        if isinstance(apa, str):
            try:
                apa = json.loads(apa)
            except (ValueError, TypeError):
                apa = {}
        he = apa.get("Hero") if isinstance(apa, dict) else None
        apa_hero = he.get("real_name") if isinstance(he, dict) else None
        data_ok = bool(apa_hero) and apa_hero.lower().strip() in _HERO_ALL_SET
        out.append({
            "id": r["id"], "hand_id": r["hand_id"],
            "tournament_name": r["tournament_name"], "played_at": r["played_at"],
            "detail": {
                "hero": hero,                       # o que o pn.hero diz (nick de vilão)
                "apa_hero": apa_hero,               # o que o apa diz (verdade por lugar)
                # cosmetic = só o rótulo desincronizou; poison = nomes de um print sem o Rui
                "kind": "cosmetic" if data_ok else "poison",
            },
        })
    return out


def _build_groups() -> tuple[list[dict], list[dict], list[dict]]:
    return (_bounty_below_half_hands(), _hero_name_on_villain_hands(),
            _hero_alheio_hands())


@router.get("")
def list_suspicious(current_user=Depends(require_auth)):
    """READ-ONLY. Fila viva das mãos GG 2026 apanhadas pelo veneno PURO restante.

    Consolidação 11 Jul (decisão do Rui — "um problema, um painel"): os problemas
    de COROA (`valor_impossivel`/`coroa_por_ler`) saíram daqui — vivem agora SÓ no
    painel **Coroas** da Saúde Import (`GET /api/gg-health/crowns`), onde se vê a
    imagem e se corrige. Ficam aqui **O teu nome num vilão** (veneno 2) + **Hero
    alheio** (veneno 3, 12 Jul — o pn.hero não é conta do Rui; ângulo cego do 2)."""
    g2 = _hero_name_on_villain_hands()
    g3 = _hero_alheio_hands()
    return {
        "counts": {"hero_name_on_villain": len(g2),
                   "hero_alheio": len(g3), "total": len(g2) + len(g3)},
        "groups": [
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
            {
                "key": "hero_alheio",
                "label": "Hero alheio (não és tu)",
                "description": (
                    "O Hero da mão ficou com um nick que NÃO é conta do Rui — o teu nome "
                    "está ausente (não num vilão), por isso o veneno acima não o apanha. "
                    "Típico de print pós-bust: a Vision marcou um vilão como is_hero. "
                    "'cosmético' = o apa já tem o Hero certo, só o rótulo desincronizou; "
                    "'veneno' = os nomes vieram de um print sem o Rui (reverter à anónima)."
                ),
                "count": len(g3),
                "hands": g3,
            },
        ],
    }


@router.get("/count")
def count_suspicious(current_user=Depends(require_auth)):
    """READ-ONLY. Só a contagem (badge). Venenos hero-num-vilão + hero-alheio (as
    coroas foram para o painel Coroas)."""
    g2 = _hero_name_on_villain_hands()
    g3 = _hero_alheio_hands()
    return {"hero_name_on_villain": len(g2), "hero_alheio": len(g3),
            "total": len(g2) + len(g3)}
