"""
Persiste metadata por torneio (1 row por (site, tournament_number)) em
tournaments_meta. Single source of truth para starting_stack, format,
buy_in, currency, start_time. Substitui calculos client-side.

NAO confundir com tabela `tournaments` (P&L de torneios pessoais via
SUMMARY upload — schema diferente, proposito diferente).
"""
from __future__ import annotations
import json
import logging
import re

from psycopg2.extras import RealDictCursor

from app.db import get_conn

logger = logging.getLogger(__name__)


def ensure_tournaments_meta_schema():
    """Idempotente. Chamada no lifespan."""
    sql = """
    CREATE TABLE IF NOT EXISTS tournaments_meta (
      tournament_number  TEXT NOT NULL,
      site               TEXT NOT NULL,
      tournament_name    TEXT,
      buy_in             NUMERIC,
      currency           TEXT,
      tournament_format  TEXT,
      starting_stack     NUMERIC,
      start_time         TIMESTAMPTZ,
      hand_count         INTEGER,
      updated_at         TIMESTAMPTZ DEFAULT NOW(),
      PRIMARY KEY (site, tournament_number)
    );
    """
    idx_sql = """
    CREATE INDEX IF NOT EXISTS idx_tournaments_meta_start_time
      ON tournaments_meta (start_time DESC);
    """
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(sql)
            cur.execute(idx_sql)
        conn.commit()
    finally:
        conn.close()


# Currency: heuristica via simbolo no nome (ganha sobre default-per-site).
_USD_RE = re.compile(r"\$")
_EUR_RE = re.compile(r"€")


def _detect_currency(tournament_name: str | None, site: str | None) -> str | None:
    if tournament_name:
        if _USD_RE.search(tournament_name): return "USD"
        if _EUR_RE.search(tournament_name): return "EUR"
    if site in ("GGPoker", "PokerStars", "WPN"):
        return "USD"
    if site == "Winamax":
        return "EUR"
    return None


def upsert_tournament_meta(
    tournament_number: str, site: str, *, conn=None
) -> dict:
    """
    Recalcula e persiste tournaments_meta para 1 (site, tournament_number).

    Le de hands:
      - 1a hand cronologica do TM -> apa[hero].stack -> starting_stack
      - tournament_name, buy_in, tournament_format (per-hand ja populado)
      - MIN(played_at) -> start_time
      - COUNT(*) -> hand_count

    Idempotente. Sobrescreve sempre (UPSERT). Retorna dict do estado
    pos-upsert.
    """
    own_conn = conn is None
    if own_conn:
        conn = get_conn()

    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT
                    MIN(played_at)              AS start_time,
                    COUNT(*)                    AS hand_count,
                    (ARRAY_AGG(tournament_name  ORDER BY played_at) FILTER
                     (WHERE tournament_name IS NOT NULL))[1]  AS tournament_name,
                    (ARRAY_AGG(buy_in           ORDER BY played_at) FILTER
                     (WHERE buy_in IS NOT NULL))[1]           AS buy_in,
                    (ARRAY_AGG(tournament_format ORDER BY played_at) FILTER
                     (WHERE tournament_format IS NOT NULL))[1] AS tournament_format
                  FROM hands
                 WHERE tournament_number = %s
                   AND site = %s
                   AND played_at >= '2026-01-01'
                """,
                (tournament_number, site),
            )
            agg = cur.fetchone()
            if not agg or agg["hand_count"] == 0:
                return {"status": "no_hands", "tm": tournament_number, "site": site}

            cur.execute(
                """
                SELECT all_players_actions
                  FROM hands
                 WHERE tournament_number = %s AND site = %s
                       AND played_at >= '2026-01-01'
                 ORDER BY played_at ASC LIMIT 1
                """,
                (tournament_number, site),
            )
            r = cur.fetchone()
            apa = r["all_players_actions"] if r else None
            if isinstance(apa, str):
                try: apa = json.loads(apa)
                except (ValueError, TypeError): apa = None
            starting_stack = None
            if isinstance(apa, dict):
                for k, v in apa.items():
                    if k == "_meta" or not isinstance(v, dict): continue
                    if v.get("is_hero"):
                        starting_stack = v.get("stack")
                        break

            currency = _detect_currency(agg["tournament_name"], site)

            cur.execute(
                """
                INSERT INTO tournaments_meta
                    (tournament_number, site, tournament_name, buy_in, currency,
                     tournament_format, starting_stack, start_time, hand_count,
                     updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
                ON CONFLICT (site, tournament_number) DO UPDATE SET
                    tournament_name   = EXCLUDED.tournament_name,
                    buy_in            = EXCLUDED.buy_in,
                    currency          = EXCLUDED.currency,
                    tournament_format = EXCLUDED.tournament_format,
                    starting_stack    = EXCLUDED.starting_stack,
                    start_time        = EXCLUDED.start_time,
                    hand_count        = EXCLUDED.hand_count,
                    updated_at        = NOW()
                """,
                (
                    tournament_number, site, agg["tournament_name"], agg["buy_in"],
                    currency, agg["tournament_format"], starting_stack,
                    agg["start_time"], agg["hand_count"],
                ),
            )

        if own_conn:
            conn.commit()

        return {
            "status": "ok",
            "tm": tournament_number,
            "site": site,
            "starting_stack": float(starting_stack) if starting_stack is not None else None,
            "tournament_name": agg["tournament_name"],
            "buy_in": float(agg["buy_in"]) if agg["buy_in"] is not None else None,
            "currency": currency,
            "tournament_format": agg["tournament_format"],
            "start_time": agg["start_time"].isoformat() if agg["start_time"] else None,
            "hand_count": agg["hand_count"],
        }

    except Exception:
        if own_conn:
            conn.rollback()
        raise
    finally:
        if own_conn:
            conn.close()
