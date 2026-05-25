"""Router HRC: import de Complete Export do HRC + listagem/detalhe.

Endpoints:
- POST /api/hrc/import                    — multipart upload de zip; cria session + nodes.
- GET  /api/hrc/sessions                  — lista sessions (id, name, total_nodes, ...).
- GET  /api/hrc/sessions/{id}             — detalhe (settings + equity + total_nodes).
- GET  /api/hrc/sessions/{id}/nodes/{idx} — node completo (player/street/actions/hands).

Schema: 2 tabelas novas, idempotentes via `ensure_hrc_schema()` no lifespan.
v1 e additive (nao toca tabelas existentes); FK opcional para mtt_hands(id).
"""
from __future__ import annotations

import logging
from typing import Optional

import psycopg2.extras
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from app.auth import require_auth
from app.db import get_conn
from app.services.hrc_import import (
    HRCImportError,
    iter_nodes,
    open_hrc_zip,
    read_equity,
    read_settings,
    list_node_indices,
)
from app.services.hrc_queue import eligible_hands, pending_ts_hands

router = APIRouter(prefix="/api/hrc", tags=["hrc"])
logger = logging.getLogger("hrc")


# ── Schema ────────────────────────────────────────────────────────────

_HRC_SESSIONS_SQL = """
CREATE TABLE IF NOT EXISTS hrc_sessions (
    id            SERIAL PRIMARY KEY,
    name          TEXT NOT NULL,
    settings      JSONB NOT NULL,
    equity        JSONB NOT NULL,
    total_nodes   INT NOT NULL,
    uploaded_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    source        TEXT NOT NULL CHECK (source IN ('manual', 'watcher')),
    related_hand_id BIGINT REFERENCES mtt_hands(id) ON DELETE SET NULL,
    UNIQUE (name)
);
"""

_HRC_NODES_SQL = """
CREATE TABLE IF NOT EXISTS hrc_nodes (
    id                SERIAL PRIMARY KEY,
    session_id        INT NOT NULL REFERENCES hrc_sessions(id) ON DELETE CASCADE,
    node_index        INT NOT NULL,
    player            INT NOT NULL,
    street            INT NOT NULL,
    sequence_path     JSONB NOT NULL,
    actions           JSONB NOT NULL,
    hands_strategies  JSONB NOT NULL,
    UNIQUE (session_id, node_index)
);
"""

_HRC_NODES_IDX_SESSION = (
    "CREATE INDEX IF NOT EXISTS idx_hrc_nodes_session "
    "ON hrc_nodes(session_id, node_index);"
)
_HRC_NODES_IDX_SEQ_PATH = (
    "CREATE INDEX IF NOT EXISTS idx_hrc_nodes_seq_path "
    "ON hrc_nodes USING GIN(sequence_path);"
)


def ensure_hrc_schema():
    """Idempotente. Chamada no lifespan do FastAPI."""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(_HRC_SESSIONS_SQL)
            cur.execute(_HRC_NODES_SQL)
            cur.execute(_HRC_NODES_IDX_SESSION)
            cur.execute(_HRC_NODES_IDX_SEQ_PATH)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ── Helpers ────────────────────────────────────────────────────────────

# Batch size para psycopg2.execute_values na insercao de nodes.
# 500 nodes × ~12KB JSON = ~6MB por batch; conservador para evitar
# memory spikes em paralelo com outros requests.
_NODE_INSERT_BATCH = 500


def _insert_session(
    conn,
    name: str,
    settings: dict,
    equity: dict,
    total_nodes: int,
    source: str,
    related_hand_id: Optional[int],
) -> int:
    """Insere a row de session e devolve o id. Lança HTTPException 409
    se houver colisao no UNIQUE(name)."""
    sql = """
    INSERT INTO hrc_sessions
        (name, settings, equity, total_nodes, source, related_hand_id)
    VALUES (%s, %s, %s, %s, %s, %s)
    RETURNING id;
    """
    try:
        with conn.cursor() as cur:
            cur.execute(
                sql,
                (name, settings, equity, total_nodes, source, related_hand_id),
            )
            row = cur.fetchone()
            return row["id"]
    except psycopg2.errors.UniqueViolation as exc:
        conn.rollback()
        raise HTTPException(
            status_code=409,
            detail=f"Ja existe uma session com name='{name}'",
        ) from exc


def _bulk_insert_nodes(conn, session_id: int, nodes_iter) -> int:
    """Insere todos os nodes em batches via psycopg2.execute_values.

    `nodes_iter` produz (idx, node_dict) pares. Retorna total inserido.
    """
    insert_sql = """
    INSERT INTO hrc_nodes
        (session_id, node_index, player, street,
         sequence_path, actions, hands_strategies)
    VALUES %s
    """
    template = "(%s, %s, %s, %s, %s, %s, %s)"
    batch: list[tuple] = []
    total = 0

    with conn.cursor() as cur:
        for idx, node in nodes_iter:
            batch.append(
                (
                    session_id,
                    idx,
                    int(node["player"]),
                    int(node["street"]),
                    psycopg2.extras.Json(node.get("sequence") or []),
                    psycopg2.extras.Json(node.get("actions") or []),
                    psycopg2.extras.Json(node.get("hands") or {}),
                )
            )
            if len(batch) >= _NODE_INSERT_BATCH:
                psycopg2.extras.execute_values(cur, insert_sql, batch, template)
                total += len(batch)
                batch.clear()
        if batch:
            psycopg2.extras.execute_values(cur, insert_sql, batch, template)
            total += len(batch)
    return total


# ── Endpoints ────────────────────────────────────────────────────────────


@router.get("/eligible")
def list_eligible(
    tags: Optional[str] = None,
    study_state: Optional[str] = None,
    played_after: Optional[str] = None,
    played_before: Optional[str] = None,
    include_no_payout: bool = False,
    _user=Depends(require_auth),
):
    """Lista as mãos actualmente elegíveis para a queue HRC (painel HRC).

    Espelha exactamente os gates de `GET /api/queue/hrc` (mesma SQL Andar 1 +
    Andar 2 payout/raw/seats, via `services/hrc_queue.eligible_hands`), mas
    devolve JSON em vez de zip. Sem params usa os mesmos defaults do export —
    o `count` bate com o que o adapter puxaria agora. Read-only.
    """
    from datetime import datetime, timezone
    try:
        result = eligible_hands(
            tags=tags,
            study_state=study_state,
            played_after=played_after,
            played_before=played_before,
            include_no_payout=include_no_payout,
        )
    except ValueError:
        raise HTTPException(400, "played_after/played_before devem ser ISO date")
    result["generated_at"] = datetime.now(timezone.utc).isoformat()
    return result


@router.get("/pending-ts")
def list_pending_ts(
    tags: Optional[str] = None,
    study_state: Optional[str] = None,
    played_after: Optional[str] = None,
    played_before: Optional[str] = None,
    _user=Depends(require_auth),
):
    """pt41 — mãos GG bounty-format escondidas do /hrc por falta de TS-com-bounty.

    Alimenta o banner D1 no painel HRC. `reason` por grupo:
      - `needs_ts_import`     — PKO/SuperKO/KO → importar o TS desbloqueia.
      - `mystery_unsupported` — Mystery KO → #MYSTERY-KO-DUAL-SUPPORT (futuro).
    Read-only; mesma janela/tags/study_state do `/eligible`.
    """
    try:
        groups = pending_ts_hands(
            tags=tags,
            study_state=study_state,
            played_after=played_after,
            played_before=played_before,
        )
    except ValueError:
        raise HTTPException(400, "played_after/played_before devem ser ISO date")
    return {
        "count": len(groups),
        "total_hands": sum(g["n_hands"] for g in groups),
        "groups": groups,
    }


@router.post("/import")
async def import_hrc_zip(
    file: UploadFile = File(...),
    name: Optional[str] = Form(None),
    source: str = Form("manual"),
    related_hand_id: Optional[int] = Form(None),
    _user=Depends(require_auth),
):
    """Importa um zip Complete Export do HRC.

    - `file`: zip multipart obrigatorio.
    - `name`: nome da session; default = nome do ficheiro (sem .zip).
    - `source`: 'manual' (default) ou 'watcher'.
    - `related_hand_id`: opcional, FK para mtt_hands.id.

    Retorna `{ session_id, total_nodes }`.
    """
    if source not in ("manual", "watcher"):
        raise HTTPException(400, "source deve ser 'manual' ou 'watcher'")

    raw = await file.read()
    if not raw:
        raise HTTPException(400, "ficheiro vazio")

    # Derivar nome default do filename.
    default_name = (file.filename or "session").rsplit(".", 1)[0].strip() or "session"
    final_name = (name or default_name).strip()
    if not final_name:
        raise HTTPException(400, "name nao pode ser vazio")

    # Parsing zip — validacao basica primeiro, antes de tocar na DB.
    try:
        zf = open_hrc_zip(raw)
    except HRCImportError as exc:
        raise HTTPException(400, str(exc))

    try:
        try:
            settings = read_settings(zf)
            equity = read_equity(zf)
            indices = list_node_indices(zf)
        except HRCImportError as exc:
            raise HTTPException(400, str(exc))

        if not indices:
            raise HTTPException(400, "zip nao contem nenhum nodes/N.json")
        if 0 not in indices:
            raise HTTPException(400, "zip nao contem nodes/0.json (root node)")

        total_nodes = len(indices)

        conn = get_conn()
        try:
            session_id = _insert_session(
                conn, final_name, settings, equity, total_nodes,
                source, related_hand_id,
            )
            try:
                inserted = _bulk_insert_nodes(
                    conn, session_id, iter_nodes(zf, indices)
                )
            except HRCImportError as exc:
                conn.rollback()
                raise HTTPException(400, f"Erro ao parsear nodes: {exc}")
            if inserted != total_nodes:
                conn.rollback()
                raise HTTPException(
                    500,
                    f"Inseridos {inserted} nodes mas esperavam {total_nodes}",
                )
            conn.commit()
        finally:
            conn.close()
    finally:
        zf.close()

    logger.info(
        "[hrc-import] session_id=%s name=%s total_nodes=%s source=%s",
        session_id, final_name, total_nodes, source,
    )
    return {"session_id": session_id, "total_nodes": total_nodes}


@router.get("/sessions")
def list_sessions(_user=Depends(require_auth)):
    """Lista sessions importadas, mais recentes primeiro."""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, name, total_nodes, uploaded_at, source, related_hand_id
                FROM hrc_sessions
                ORDER BY uploaded_at DESC
                """
            )
            rows = cur.fetchall()
    finally:
        conn.close()
    return [dict(r) for r in rows]


@router.get("/sessions/{session_id}")
def get_session(session_id: int, _user=Depends(require_auth)):
    """Detalhe da session com settings + equity completos."""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, name, total_nodes, uploaded_at, source,
                       related_hand_id, settings, equity
                FROM hrc_sessions
                WHERE id = %s
                """,
                (session_id,),
            )
            row = cur.fetchone()
    finally:
        conn.close()
    if not row:
        raise HTTPException(404, "session nao encontrada")
    return dict(row)


@router.get("/sessions/{session_id}/nodes/{node_index}")
def get_node(session_id: int, node_index: int, _user=Depends(require_auth)):
    """Devolve o JSON completo do node (com hands_strategies)."""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT node_index, player, street, sequence_path,
                       actions, hands_strategies
                FROM hrc_nodes
                WHERE session_id = %s AND node_index = %s
                """,
                (session_id, node_index),
            )
            row = cur.fetchone()
    finally:
        conn.close()
    if not row:
        raise HTTPException(404, "node nao encontrado")
    return dict(row)


@router.delete("/sessions/{session_id}")
def delete_session(session_id: int, _user=Depends(require_auth)):
    """Apaga a session. hrc_nodes faz cascade via ON DELETE CASCADE."""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM hrc_sessions WHERE id = %s RETURNING id, name",
                (session_id,),
            )
            row = cur.fetchone()
        if not row:
            conn.rollback()
            raise HTTPException(404, "session nao encontrada")
        conn.commit()
    finally:
        conn.close()
    logger.info("[hrc-delete] session_id=%s name=%s", row["id"], row["name"])
    return {"deleted": True, "session_id": row["id"], "name": row["name"]}
