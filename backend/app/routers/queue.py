"""HRC export queue endpoint — packages hands+payouts num zip para HRC watcher.

GET /api/queue/hrc — query params filtram hands; resposta e application/zip.
"""
from __future__ import annotations
import io
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse

from app.auth import require_auth
from app.db import query
from app.services.queue_export import build_queue_zip

router = APIRouter(prefix="/api/queue", tags=["queue"])
logger = logging.getLogger("queue")


# ICM aparece como tag HM3 (capitalizada) E como canal Discord (lowercase).
# _expand_icm_case (abaixo) garante que pedir uma forma traz a outra,
# sem afectar outras tags (escopo cirurgico, sem mudar SQL).
_DEFAULT_TAGS = ["icm-pko", "PKO SS", "sqz-pko", "ICM"]
_DEFAULT_STUDY_STATES = ["new"]
_ALLOWED_SITES = ["GGPoker", "PokerStars", "Winamax"]


def _csv(value: Optional[str], default: list[str]) -> list[str]:
    if value is None:
        return default
    parts = [p.strip() for p in value.split(",") if p.strip()]
    return parts or default


def _expand_icm_case(tags: list[str]) -> list[str]:
    """Expande tag `ICM` (HM3) <-> `icm` (Discord channel) — referem-se ao
    mesmo conceito mas vivem em sistemas com case diferente.
    Outras tags ficam tal e qual (case-sensitive). Dedup preservando ordem."""
    out = []
    for t in tags:
        out.append(t)
        if t == "ICM":
            out.append("icm")
        elif t == "icm":
            out.append("ICM")
    return list(dict.fromkeys(out))


@router.get("/hrc")
def export_queue(
    tags: Optional[str] = Query(None, description="CSV de tags (hm3+discord)"),
    study_state: Optional[str] = Query(None, description="CSV de study_states"),
    played_after: Optional[str] = Query(None, description="ISO date YYYY-MM-DD"),
    played_before: Optional[str] = Query(None, description="ISO date YYYY-MM-DD"),
    include_no_payout: bool = Query(False),
    current_user=Depends(require_auth),
):
    tags_list = _expand_icm_case(_csv(tags, _DEFAULT_TAGS))
    states_list = _csv(study_state, _DEFAULT_STUDY_STATES)
    now = datetime.now(timezone.utc)
    after_str = played_after or (now - timedelta(days=30)).date().isoformat()
    before_str = played_before or now.date().isoformat()
    try:
        after_dt = datetime.fromisoformat(after_str).replace(tzinfo=timezone.utc)
        before_dt = (
            datetime.fromisoformat(before_str).replace(tzinfo=timezone.utc)
            + timedelta(days=1)
        )
    except ValueError:
        raise HTTPException(400, "played_after/played_before devem ser ISO date")

    rows = query(
        """
        SELECT id, hand_id, site, tournament_number, raw, player_names,
               played_at
          FROM hands
         WHERE played_at >= '2026-01-01'
           AND site = ANY(%s)
           AND played_at >= %s
           AND played_at < %s
           AND study_state = ANY(%s)
           AND (
                 EXISTS (SELECT 1 FROM unnest(COALESCE(hm3_tags, '{}'::text[]))
                                AS t WHERE t = ANY(%s))
              OR EXISTS (SELECT 1 FROM unnest(COALESCE(discord_tags, '{}'::text[]))
                                AS t WHERE t = ANY(%s))
               )
         ORDER BY played_at ASC
        """,
        (_ALLOWED_SITES, after_dt, before_dt, states_list, tags_list, tags_list),
    )
    hands = [dict(r) for r in rows]

    payouts_by_key: dict = {}
    sites = list({h["site"] for h in hands if h.get("site")})
    tnums = list({h["tournament_number"] for h in hands if h.get("tournament_number")})
    if sites and tnums:
        prows = query(
            """SELECT site, tournament_number, payouts_json
                 FROM tournament_payouts
                WHERE site = ANY(%s) AND tournament_number = ANY(%s)""",
            (sites, tnums),
        )
        payouts_by_key = {
            (r["site"], r["tournament_number"]): r["payouts_json"] for r in prows
        }

    filters_meta = {
        "tags": tags_list,
        "study_state": states_list,
        "played_after": after_str,
        "played_before": before_str,
        "include_no_payout": include_no_payout,
    }

    zip_bytes = build_queue_zip(
        hands, payouts_by_key,
        include_no_payout=include_no_payout,
        filters_meta=filters_meta,
    )
    ts = now.strftime("%Y%m%dT%H%M%SZ")
    fname = f"queue_{ts}.zip"
    logger.info(
        "queue/hrc exported: queried=%d filename=%s", len(hands), fname,
    )
    return StreamingResponse(
        io.BytesIO(zip_bytes),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{fname}"'},
    )
