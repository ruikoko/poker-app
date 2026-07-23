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
    wn_chips_meta: Optional[dict] = None,
) -> dict:
    """Upsert opaco do blob HRC. Validacao basica, sem schema do JSON.

    `wn_chips_meta` (#WN-TOTAL-CHIPS-FROM-LOBBY, 24 Jul 2026): metadados da
    regra do total de fichas Winamax ({state, provisional, review, re_entries})
    — quando presente, escreve tambem as 4 colunas da regra. None (defeito) =
    caminho legado byte-a-byte (GG e restantes salas intocadas).

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
    if wn_chips_meta is not None:
        review = ",".join(wn_chips_meta.get("review") or []) or None
        row = execute_returning(
            """
            INSERT INTO tournament_payouts
                (site, tournament_number, payouts_json, source, uploaded_at,
                 chips_rule_state, chips_provisional, chips_review, re_entries)
            VALUES (%s, %s, %s, %s, NOW(), %s, %s, %s, %s)
            ON CONFLICT (site, tournament_number) DO UPDATE SET
                payouts_json = EXCLUDED.payouts_json,
                source       = EXCLUDED.source,
                uploaded_at  = NOW(),
                chips_rule_state  = EXCLUDED.chips_rule_state,
                chips_provisional = EXCLUDED.chips_provisional,
                chips_review      = EXCLUDED.chips_review,
                re_entries        = EXCLUDED.re_entries
            RETURNING site, tournament_number, source, uploaded_at,
                      (xmax = 0) AS inserted
            """,
            (site, tournament_number, payouts_json, source,
             wn_chips_meta.get("state"), wn_chips_meta.get("provisional"),
             review, wn_chips_meta.get("re_entries")),
        )
        return {
            "site": row["site"],
            "tournament_number": row["tournament_number"],
            "source": row["source"],
            "uploaded_at": row["uploaded_at"],
            "action": "inserted" if row["inserted"] else "updated",
        }

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
