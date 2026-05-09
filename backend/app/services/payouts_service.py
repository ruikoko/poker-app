"""HTTP-agnostic upsert para tournament_payouts.

Single source of truth para o INSERT...ON CONFLICT do blob HRC Structure
Manager. Consumido pelo POST /api/payouts (HTTP, FASE 1) e pelo handler
Discord de lobbys (FASE A COMMIT 3) — ambos passam pelo mesmo path.
"""
from __future__ import annotations
import logging
from typing import Any, Optional

from app.db import execute_returning

logger = logging.getLogger("payouts_service")


def upsert_payout(
    site: str,
    tournament_number: str,
    payouts_json: Any,
    source: Optional[str] = None,
) -> dict:
    """Upsert opaco do blob HRC. Validacao basica, sem schema do JSON.

    Raises:
        ValueError: se site/tournament_number vazios, ou payouts_json None.

    Returns:
        dict com keys: site, tournament_number, source,
        uploaded_at (datetime, sem isoformat), action ('inserted' | 'updated').
        Caller decide se serializa o datetime para resposta HTTP.
    """
    site = (site or "").strip()
    tournament_number = (tournament_number or "").strip()
    if not site:
        raise ValueError("site obrigatorio")
    if not tournament_number:
        raise ValueError("tournament_number obrigatorio")
    if payouts_json is None:
        raise ValueError("payouts_json nao pode ser null")

    # `(xmax = 0)` distingue inserted (xmax=0) vs updated (xmax!=0). Postgres
    # trick standard para detectar o caminho do ON CONFLICT sem 2 queries.
    row = execute_returning(
        """
        INSERT INTO tournament_payouts
            (site, tournament_number, payouts_json, source, uploaded_at)
        VALUES (%s, %s, %s, %s, NOW())
        ON CONFLICT (site, tournament_number) DO UPDATE SET
            payouts_json = EXCLUDED.payouts_json,
            source       = EXCLUDED.source,
            uploaded_at  = NOW()
        RETURNING site, tournament_number, source, uploaded_at,
                  (xmax = 0) AS inserted
        """,
        (site, tournament_number, payouts_json, source),
    )
    return {
        "site": row["site"],
        "tournament_number": row["tournament_number"],
        "source": row["source"],
        "uploaded_at": row["uploaded_at"],
        "action": "inserted" if row["inserted"] else "updated",
    }
