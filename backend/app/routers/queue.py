"""HRC export queue endpoint — packages hands+payouts num zip para HRC watcher.

GET /api/queue/hrc — query params filtram hands; resposta e application/zip.
"""
from __future__ import annotations
import io
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse

from app.auth import require_auth_or_api_key
from app.db import query
from app.services.hrc_jobs import (
    extract_meta_from_result_zip,
    upsert_hrc_job_result,
)
from app.services.queue_export import build_queue_zip

router = APIRouter(prefix="/api/queue", tags=["queue"])
logger = logging.getLogger("queue")


# ICM aparece como tag HM3 (capitalizada) E como canal Discord (lowercase).
# _expand_icm_case (abaixo) garante que pedir uma forma traz a outra,
# sem afectar outras tags (escopo cirurgico, sem mudar SQL).
_DEFAULT_TAGS = ["icm-pko", "PKO SS", "sqz-pko", "ICM"]
_DEFAULT_STUDY_STATES = ["new"]
_ALLOWED_SITES = ["GGPoker", "PokerStars", "Winamax"]

# Cap de upload do zip de resultados (D-G2-4: 50 MB defensivo). Samples reais
# do HRC Complete Export ficam tipicamente em KB-MB; cap protege contra
# accident/abuse sem rejeitar uso legítimo.
_MAX_RESULT_ZIP_BYTES = 50 * 1024 * 1024  # 50 MB


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
    current_user=Depends(require_auth_or_api_key),
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


@router.post("/hrc/results")
async def upload_hrc_result(
    hand_id: str = Query(..., description="hand_id TEXT (ex: 'GG-281416137')"),
    status: str = Query("done", description="'done' ou 'failed'"),
    error: Optional[str] = Query(None, description="motivo (obrigatório se status='failed')"),
    file: Optional[UploadFile] = File(None),
    current_user=Depends(require_auth_or_api_key),
):
    """Recebe resultado HRC para uma mão (do watcher Beelink).

    - `status='done'`: `file` obrigatório (zip Complete Export do HRC).
      O zip deve conter `meta.json` no root com pelo menos
      `{rank, players_left, stage, ci}`.
    - `status='failed'`: `error` obrigatório, `file` ignorado se vier.

    UPSERT em `hrc_jobs` por `hand_db_id`. Re-upload sobrescreve
    (preserva `submitted_at` original).

    Auth: cookie (UI) OU `Authorization: Bearer <HRC_WATCHER_API_KEY>` (G4).

    Returns: `{hand_db_id, status, action, meta}`.
    """
    if status not in ("done", "failed"):
        raise HTTPException(400, f"status inválido: '{status}' (use 'done' ou 'failed')")
    if status == "failed" and not error:
        raise HTTPException(400, "error obrigatório quando status='failed'")
    if error and len(error) > 500:
        raise HTTPException(400, "error excede 500 chars")

    rows = query(
        "SELECT id FROM hands WHERE hand_id = %s LIMIT 1", (hand_id,)
    )
    if not rows:
        raise HTTPException(404, f"hand_id '{hand_id}' não encontrado")
    hand_db_id = rows[0]["id"]

    now_iso = datetime.now(timezone.utc).isoformat()
    base_meta = {
        "hand_id": hand_id,
        "received_at": now_iso,
        "received_from": "watcher",
    }

    if status == "failed":
        if file is not None:
            logger.warning(
                "hrc_jobs: file ignored on failed upload hand_id=%s", hand_id
            )
        meta_aug = {**base_meta, "failure_reported_by": "watcher"}
        row = upsert_hrc_job_result(
            hand_db_id=hand_db_id,
            status="failed",
            result_zip=None,
            meta_json=meta_aug,
            error=error,
        )
        size = 0
    else:  # done
        if file is None:
            raise HTTPException(400, "file obrigatório quando status='done'")
        content = await file.read()
        size = len(content)
        if size == 0:
            raise HTTPException(400, "file vazio")
        if size > _MAX_RESULT_ZIP_BYTES:
            raise HTTPException(
                413, f"file excede {_MAX_RESULT_ZIP_BYTES // 1024 // 1024} MB"
            )
        try:
            meta = extract_meta_from_result_zip(content)
        except ValueError as e:
            raise HTTPException(400, str(e))
        # base_meta DEPOIS de meta para que server-side sobrescreva
        # eventuais campos homónimos no meta.json do zip (D-G2-EXTRA-3).
        meta_aug = {**meta, **base_meta}
        row = upsert_hrc_job_result(
            hand_db_id=hand_db_id,
            status="done",
            result_zip=content,
            meta_json=meta_aug,
            error=None,
        )

    action = "inserted" if row.get("inserted") else "updated"
    logger.info(
        "hrc_jobs: upsert hand_id=%s db_id=%d status=%s size=%d action=%s",
        hand_id, hand_db_id, status, size, action,
    )
    return {
        "hand_db_id": hand_db_id,
        "status": status,
        "action": action,
        "meta": meta_aug,
    }
