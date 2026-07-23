"""Tournament payouts (HRC Structure Manager JSON) — opaque storage.

Cada row representa o blob JSON canónico que vai parar a `<hand>/payouts.json`
no zip exportado para o HRC watcher (rota `GET /api/queue/hrc`, COMMIT 3).

Schema do blob (validado em FASE 1 contra sample real, nao validado em INSERT):
    {"name": "/", "folders": [], "structures": [{name, chips, prizes,
                                                  bountyType, progressiveFactor}]}
"""
from __future__ import annotations
import logging
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app.auth import require_auth
from app.db import get_conn, query
from app.services.payouts_service import upsert_payout as _svc_upsert_payout

router = APIRouter(prefix="/api/payouts", tags=["payouts"])
logger = logging.getLogger("payouts")


def ensure_tournament_payouts_schema():
    """Idempotente. Chamada no lifespan."""
    sql = """
    CREATE TABLE IF NOT EXISTS tournament_payouts (
        site              TEXT NOT NULL,
        tournament_number TEXT NOT NULL,
        payouts_json      JSONB NOT NULL,
        source            TEXT,
        uploaded_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        PRIMARY KEY (site, tournament_number)
    );
    """
    idx_sql = (
        "CREATE INDEX IF NOT EXISTS idx_tournament_payouts_site "
        "ON tournament_payouts(site);"
    )
    # #WN-TOTAL-CHIPS-FROM-LOBBY (24 Jul 2026) — metadados da regra do total de
    # fichas WN (estado do print escolhido / provisórias / por-rever) +
    # `re_entries` INFO-ONLY (sem consumidores; não entra em contas).
    alter_sqls = [
        "ALTER TABLE tournament_payouts ADD COLUMN IF NOT EXISTS chips_rule_state TEXT;",
        "ALTER TABLE tournament_payouts ADD COLUMN IF NOT EXISTS chips_provisional BOOLEAN;",
        "ALTER TABLE tournament_payouts ADD COLUMN IF NOT EXISTS chips_review TEXT;",
        "ALTER TABLE tournament_payouts ADD COLUMN IF NOT EXISTS re_entries INTEGER;",
    ]
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(sql)
            cur.execute(idx_sql)
            for a in alter_sqls:
                cur.execute(a)
        conn.commit()
    finally:
        conn.close()


class PayoutUpsert(BaseModel):
    site: str
    tournament_number: str
    payouts_json: Any
    source: Optional[str] = None


@router.post("")
def upsert_payout(body: PayoutUpsert, current_user=Depends(require_auth)):
    """Upsert opaco. Sem schema validation em FASE 1 — má estrutura falha
    downstream no HRC."""
    try:
        result = _svc_upsert_payout(
            site=body.site,
            tournament_number=body.tournament_number,
            payouts_json=body.payouts_json,
            source=body.source,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {
        "status": "ok",
        "site": result["site"],
        "tournament_number": result["tournament_number"],
        "source": result["source"],
        "uploaded_at": result["uploaded_at"].isoformat(),
        "action": result["action"],
    }


@router.get("/{site}/{tournament_number}")
def get_payout(
    site: str, tournament_number: str, current_user=Depends(require_auth)
):
    rows = query(
        """SELECT site, tournament_number, payouts_json, source, uploaded_at
             FROM tournament_payouts
            WHERE site = %s AND tournament_number = %s""",
        (site, tournament_number),
    )
    if not rows:
        raise HTTPException(404, f"sem payout para {site}/{tournament_number}")
    r = dict(rows[0])
    r["uploaded_at"] = r["uploaded_at"].isoformat()
    return r


@router.get("")
def list_payouts(
    site: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    current_user=Depends(require_auth),
):
    where = "WHERE site = %s" if site else ""
    base_args = (site,) if site else ()
    rows = query(
        f"""SELECT site, tournament_number, source, uploaded_at,
                   jsonb_array_length(payouts_json->'structures')
                       AS structures_count
              FROM tournament_payouts
              {where}
             ORDER BY uploaded_at DESC LIMIT %s OFFSET %s""",
        base_args + (limit, offset),
    )
    total_rows = query(
        f"SELECT COUNT(*) AS n FROM tournament_payouts {where}", base_args
    )
    total = total_rows[0]["n"] if total_rows else 0
    items = []
    for r in rows:
        d = dict(r)
        d["uploaded_at"] = d["uploaded_at"].isoformat()
        items.append(d)
    return {"total": total, "limit": limit, "offset": offset, "items": items}
