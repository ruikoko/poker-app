"""hrc_jobs — schema + helpers para a tabela de jobs HRC.

Tabela popula-se em G2 (POST /api/queue/hrc/results) e é lida por
G6 (badge UI). G3 criou o schema; G2 adicionou helpers UPSERT
+ extract_meta.
"""
from __future__ import annotations
import io
import json
import logging
import zipfile
from typing import Optional

import psycopg2
import psycopg2.extras

from app.db import execute_returning, get_conn

logger = logging.getLogger("hrc_jobs")


def ensure_hrc_jobs_schema():
    """Idempotente. Chamada no lifespan."""
    sql = """
    CREATE TABLE IF NOT EXISTS hrc_jobs (
        id              BIGSERIAL PRIMARY KEY,
        hand_db_id      INTEGER NOT NULL REFERENCES hands(id) ON DELETE CASCADE,
        status          TEXT NOT NULL DEFAULT 'submitted'
                        CHECK (status IN ('submitted','running','done','failed','expired')),
        submitted_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        completed_at    TIMESTAMPTZ,
        result_zip      BYTEA,
        result_zip_size INTEGER,
        meta_json       JSONB,
        error           TEXT,
        UNIQUE (hand_db_id)
    );
    """
    idx_status = (
        "CREATE INDEX IF NOT EXISTS idx_hrc_jobs_status_submitted_at "
        "ON hrc_jobs (status, submitted_at);"
    )
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(sql)
            cur.execute(idx_status)
        conn.commit()
    finally:
        conn.close()


def extract_meta_from_result_zip(zip_bytes: bytes) -> dict:
    """Extrai e parsea meta.json do zip de resultados do watcher.

    Validação minimal (D-G2-5): zip parseable, contém meta.json no root,
    meta.json é JSON object. Campos do meta (rank, players_left, etc.)
    NÃO são validados — caller (watcher) é a autoridade.

    Args:
        zip_bytes: bytes do zip HRC Complete Export, com meta.json injectado
                   pelo watcher.

    Returns:
        dict com os campos do meta.json (tipicamente {rank, players_left,
        stage, ci}). Campos extra preservados.

    Raises:
        ValueError: zip inválido, sem meta.json, ou meta.json malformado.
    """
    try:
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            if "meta.json" not in zf.namelist():
                raise ValueError("meta.json missing in zip")
            meta_raw = zf.read("meta.json").decode("utf-8")
    except zipfile.BadZipFile:
        raise ValueError("invalid zip (BadZipFile)")
    except UnicodeDecodeError as e:
        raise ValueError(f"meta.json unreadable utf-8: {e}")

    try:
        meta = json.loads(meta_raw)
    except json.JSONDecodeError as e:
        raise ValueError(f"meta.json invalid JSON: {e}")

    if not isinstance(meta, dict):
        raise ValueError("meta.json root is not an object")

    return meta


def upsert_hrc_job_result(
    *,
    hand_db_id: int,
    status: str,
    result_zip: Optional[bytes],
    meta_json: dict,
    error: Optional[str],
) -> dict:
    """UPSERT em hrc_jobs por hand_db_id.

    UNIQUE (hand_db_id) → re-upload da mesma mão sobrescreve (D-G2-8).
    `submitted_at` é preservado em UPDATE (NÃO está em DO UPDATE SET) —
    semântica "1ª submissão". `completed_at` actualiza em cada UPSERT.

    Args:
        hand_db_id: FK para hands.id (INTEGER).
        status: 'done' ou 'failed'. CHECK constraint impede outros valores.
        result_zip: bytes (status='done') ou None (status='failed').
        meta_json: dict augmentado com hand_id/received_at/received_from.
        error: motivo da falha (status='failed') ou None.

    Returns:
        dict com keys: id (BIGSERIAL), inserted (True=row nova, False=UPDATE).
    """
    result_zip_size = len(result_zip) if result_zip is not None else None

    row = execute_returning(
        """
        INSERT INTO hrc_jobs
            (hand_db_id, status, submitted_at, completed_at,
             result_zip, result_zip_size, meta_json, error)
        VALUES (%s, %s, NOW(), NOW(), %s, %s, %s, %s)
        ON CONFLICT (hand_db_id) DO UPDATE SET
            status = EXCLUDED.status,
            completed_at = EXCLUDED.completed_at,
            result_zip = EXCLUDED.result_zip,
            result_zip_size = EXCLUDED.result_zip_size,
            meta_json = EXCLUDED.meta_json,
            error = EXCLUDED.error
        RETURNING id, (xmax = 0) AS inserted
        """,
        (
            hand_db_id,
            status,
            psycopg2.Binary(result_zip) if result_zip is not None else None,
            result_zip_size,
            psycopg2.extras.Json(meta_json),
            error,
        ),
    )
    return {"id": row["id"], "inserted": row["inserted"]}
