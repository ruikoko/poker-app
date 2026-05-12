"""hrc_jobs — schema + helpers para a tabela de jobs HRC.

Tabela popula-se em G2 (POST /api/queue/hrc/results) e é lida por
G6 (badge UI). G3 cria apenas o schema; helpers UPSERT/query ficam
para G2.
"""
from __future__ import annotations
import logging

from app.db import get_conn

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
