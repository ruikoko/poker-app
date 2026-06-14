"""Fila de triagem "Marcadas por captura" (Estágio 4 desanon).

Mãos GG desanonimizadas pela SS de mesa (`match_method='table_ss'`) que ainda
NÃO têm tag de estudo → ficam aqui à espera de UMA tag de 1 clique do Rui. A
tag escolhida integra a mão no fluxo normal (Estudo/Vilões) **como se viesse do
Discord** (escreve em `discord_tags` + `apply_villain_rules`). `descartar` tira
da fila sem tag.

Decisão do Rui: fila de triagem própria (não tag automática). A condição
"pendente" é DERIVADA (sem estado próprio para 'pending'); só `resolved`/
`discarded` persistem em `hands.capture_triage` para não reaparecerem.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.auth import require_auth
from app.db import get_conn, query

router = APIRouter(prefix="/api/capture-triage", tags=["capture-triage"])
logger = logging.getLogger("capture_triage")

# Tags de 1 clique (nomes de canal Discord). 'nota' destina a Vilões; as outras
# a Estudo — via as transições canónicas, que já lêem discord_tags + match real.
# pt72 — pasta-como-tag do IT: + 'pos-nko' (NPKO pós-flop, canónica) e as
# variantes de fase '-ft' que o backend gera (mesa final). Tabela de tradução
# das pastas vive em tools/appimport/app_import.py:IT_FOLDER_TAGS.
ALLOWED_TRIAGE_TAGS = {
    "icm", "icm-pko", "pos-pko", "pos-nko", "nota",
    "icm-ft", "icm-pko-ft", "pos-pko-ft", "pos-nko-ft",
}
DISCARD = "__discard__"

# Predicado da fila (DERIVADO): mão GG desanonimizada por table-SS, SEM tag, SEM
# Discord (a de-anon já é gated GG-sem-Discord), por triar. play 2026, não-archive.
_PENDING_WHERE = (
    "h.site = 'GGPoker' "
    "AND h.context_table_ss_id IS NOT NULL "
    "AND (h.player_names->>'match_method') = 'table_ss' "
    "AND h.capture_triage IS NULL "
    "AND (h.discord_tags IS NULL OR h.discord_tags = '{}') "
    "AND (h.hm3_tags IS NULL OR h.hm3_tags = '{}') "
    "AND h.played_at >= '2026-01-01' "
    "AND h.study_state <> 'mtt_archive'"
)


def ensure_capture_triage_column():
    """Idempotente (lifespan). `hands.capture_triage` ∈ {NULL,'resolved','discarded'}.
    NULL = ainda na fila (se o predicado derivado bater); os outros = fora."""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "ALTER TABLE hands ADD COLUMN IF NOT EXISTS capture_triage TEXT"
            )
            cur.execute(
                "CREATE INDEX IF NOT EXISTS idx_hands_capture_triage "
                "ON hands (capture_triage) WHERE capture_triage IS NULL"
            )
        conn.commit()
    finally:
        conn.close()


class TagBody(BaseModel):
    tag: str


@router.get("")
def list_capture_triage(current_user=Depends(require_auth)):
    """Lista as mãos pendentes de triagem por captura (mais recentes primeiro)."""
    rows = query(
        f"""
        SELECT h.id, h.hand_id, h.tournament_name, h.played_at,
               h.context_table_ss_id, h.player_names
          FROM hands h
         WHERE {_PENDING_WHERE}
         ORDER BY h.played_at DESC NULLS LAST
        """
    )
    out = []
    for r in rows:
        pn = r.get("player_names") or {}
        players = [
            p.get("name") for p in (pn.get("players_list") or [])
            if isinstance(p, dict) and p.get("name")
        ]
        out.append({
            "id": r["id"],
            "hand_id": r["hand_id"],
            "tournament_name": r.get("tournament_name"),
            "played_at": r["played_at"].isoformat() if r.get("played_at") else None,
            "table_ss_id": r.get("context_table_ss_id"),
            "hero": pn.get("hero"),
            "players": players,
            "deanon_partial": bool(pn.get("deanon_partial")),
        })
    return {"count": len(out), "hands": out}


@router.get("/count")
def count_capture_triage(current_user=Depends(require_auth)):
    """Contador para o badge compacto do Dashboard."""
    rows = query(f"SELECT COUNT(*) AS n FROM hands h WHERE {_PENDING_WHERE}")
    return {"count": rows[0]["n"] if rows else 0}


@router.post("/{hand_id}/tag")
def tag_capture_triage(hand_id: str, body: TagBody, current_user=Depends(require_auth)):
    """Aplica UMA tag (integra no fluxo normal como se viesse do Discord) ou
    descarta (`tag='__discard__'`). Idempotente o suficiente: re-aplicar a mesma
    tag não duplica (union distinct); descartar marca `capture_triage`."""
    tag = (body.tag or "").strip()
    rows = query(
        "SELECT id, player_names FROM hands WHERE hand_id = %s LIMIT 1", (hand_id,)
    )
    if not rows:
        raise HTTPException(404, "Mão não encontrada")
    hand_db_id = rows[0]["id"]
    pn = rows[0].get("player_names") or {}
    if (pn.get("match_method")) != "table_ss":
        raise HTTPException(409, "Mão não é uma marcação por captura (table_ss)")

    if tag == DISCARD:
        conn = get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE hands SET capture_triage = 'discarded' WHERE id = %s",
                    (hand_db_id,),
                )
            conn.commit()
        finally:
            conn.close()
        logger.info("[capture_triage] hand %s (%s) descartada", hand_db_id, hand_id)
        return {"status": "discarded", "hand_id": hand_id}

    if tag not in ALLOWED_TRIAGE_TAGS:
        raise HTTPException(
            400, f"tag inválida: {tag!r} (permitidas: {sorted(ALLOWED_TRIAGE_TAGS)} ou {DISCARD})"
        )

    # Aplica a tag em discord_tags (semântica de canal, union distinct) + marca
    # resolved. apply_villain_rules a seguir (lê discord_tags actuais).
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE hands SET discord_tags = ARRAY(SELECT DISTINCT unnest("
                "COALESCE(discord_tags, '{}'::text[]) || %s::text[])), "
                "capture_triage = 'resolved' WHERE id = %s",
                ([tag], hand_db_id),
            )
        conn.commit()
    finally:
        conn.close()

    try:
        from app.services.villain_rules import apply_villain_rules
        vr = apply_villain_rules(hand_db_id)
    except Exception as e:  # pragma: no cover - defensivo
        logger.error("[capture_triage] apply_villain_rules hand %s: %s", hand_db_id, e)
        vr = {}

    logger.info("[capture_triage] hand %s (%s) -> tag %r (villains=%s)",
                hand_db_id, hand_id, tag, vr.get("n_villains_created"))
    return {"status": "tagged", "hand_id": hand_id, "tag": tag,
            "villains_created": vr.get("n_villains_created", 0)}
