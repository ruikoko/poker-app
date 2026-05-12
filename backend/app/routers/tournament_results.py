"""POST /api/tournament-results/import — upload de SSs do backoffice GG."""
from __future__ import annotations
import io
import asyncio
import logging
import zipfile
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException

from app.auth import require_auth
from app.db import query
from app.services.image_utils import detect_image_mime
from app.services import tournament_result_vision as bv
from app.services import tournament_resolver, payouts_service

router = APIRouter(prefix="/api/tournament-results", tags=["tournament-results"])
logger = logging.getLogger("tournament_results")

_MAX_IMAGES = 20
_MAX_ZIP_FILES = 50
_IMG_EXTS = (".png", ".jpg", ".jpeg", ".webp")


def _is_image_filename(name: str) -> bool:
    return name.lower().endswith(_IMG_EXTS)


def _read_files_from_upload(file: UploadFile, content: bytes) -> list[tuple[str, bytes]]:
    """Devolve [(name, bytes), ...] de 1 imagem ou de um .zip."""
    fname = (file.filename or "upload").lower()
    if fname.endswith(".zip"):
        try:
            with zipfile.ZipFile(io.BytesIO(content)) as zf:
                items = [(n, zf.read(n)) for n in zf.namelist() if _is_image_filename(n)]
        except zipfile.BadZipFile:
            raise HTTPException(400, "ZIP corrompido")
        if len(items) > _MAX_ZIP_FILES:
            raise HTTPException(
                400, f"ZIP com {len(items)} imagens excede cap {_MAX_ZIP_FILES}"
            )
        return items
    if _is_image_filename(fname):
        return [(file.filename or "upload.png", content)]
    raise HTTPException(400, "Formato nao suportado (use .png/.jpg/.webp ou .zip)")


def _lookup_ts_meta(tournament_number: str) -> Optional[dict]:
    rows = query(
        """SELECT tournament_format, tournament_pko_ratio
             FROM tournament_summaries
            WHERE site = 'GGPoker' AND tournament_number = %s""",
        (tournament_number,),
    )
    if not rows:
        return None
    r = dict(rows[0])
    ratio = r.get("tournament_pko_ratio")
    return {
        "tournament_format": r.get("tournament_format"),
        "tournament_pko_ratio": float(ratio) if ratio is not None else None,
    }


async def _process_one(
    name: str,
    content: bytes,
    *,
    dry_run: bool,
    skip_existing: bool,
    throttle: float,
) -> dict:
    """Pipeline de 1 imagem. Devolve dict de result."""
    out = {
        "filename": name, "result": "", "tournament_number": None,
        "tournament_name": None, "prize_pool": None, "total_players": None,
        "n_prizes": 0, "source": None, "error": None,
        "ss_likely_truncated": False,
    }

    mime = detect_image_mime(content)

    raw = await asyncio.to_thread(bv.extract_backoffice_payout_json, content, mime)
    if throttle > 0:
        await asyncio.sleep(throttle)
    if raw is None:
        out["result"] = "vision_failed"
        out["error"] = "extract_backoffice_payout_json returned None"
        return out

    # 1ª pass — sem ts_pko_ratio (PKO devolve sentinela; vanilla resolve aqui).
    pre = bv.parse_and_validate_backoffice_json(raw, ts_pko_ratio=None)
    if pre is None:
        out["result"] = "validation_failed"
        out["error"] = "JSON inválido / soma off / prizes vazias"
        return out

    pending_pko = isinstance(pre, dict) and pre.get("_error") == "missing_pko_ratio"
    vj = pre["_raw"] if pending_pko else pre

    out["tournament_name"] = vj.get("tournament_name")
    out["prize_pool"] = vj.get("prize_pool")
    out["total_players"] = vj.get("total_players")
    out["n_prizes"] = len(vj.get("prizes") or {})

    # Resolver TS
    tn, candidates = await asyncio.to_thread(
        tournament_resolver.resolve_tournament_number,
        "GGPoker", vj["tournament_name"], None,
        posted_at_hint=None,
        prize_pool=vj.get("prize_pool"),
        total_players=vj.get("total_players"),
    )
    if tn is None:
        if candidates:
            out["result"] = "ambiguous_ts"
            out["error"] = (
                f"{len(candidates)} candidatos com prize_pool/players iguais"
            )
            out["candidates"] = [
                {"tournament_number": c.get("tournament_number"),
                 "tournament_name": c.get("tournament_name")}
                for c in candidates[:5]
            ]
        else:
            out["result"] = "missing_ts"
            out["error"] = (
                f"TS não importado para '{vj['tournament_name']}' "
                f"(pool={vj.get('prize_pool')}, players={vj.get('total_players')}). "
                "Importa o .txt primeiro."
            )
        return out

    out["tournament_number"] = tn
    ts_meta = _lookup_ts_meta(tn) or {}

    # Mystery KO fora de scope pt20 — fail fast.
    if ts_meta.get("tournament_format") == "KO":
        out["result"] = "mystery_unsupported"
        out["error"] = (
            "Mystery KO ainda não suportado no backoffice import "
            "(tech debt #BACKOFFICE-MYSTERY). Usa lobby SS ou INSERT manual."
        )
        return out

    # 2ª pass — com ratio do TS (para PKO).
    if pending_pko:
        ratio = ts_meta.get("tournament_pko_ratio")
        if ratio is None:
            out["result"] = "missing_pko_ratio"
            out["error"] = (
                "TS importado mas sem tournament_pko_ratio. "
                "Re-importa o TS (parser B1.x)."
            )
            return out
        vj_revalidated = bv.parse_and_validate_backoffice_json(raw, ts_pko_ratio=ratio)
        if vj_revalidated is None:
            out["result"] = "validation_failed"
            out["error"] = "PKO: drift sum(prize) vs regular_pool > 2%"
            return out
        if isinstance(vj_revalidated, dict) and vj_revalidated.get("_error"):
            out["result"] = "validation_failed"
            out["error"] = vj_revalidated["_error"]
            return out
        vj = vj_revalidated

    out["ss_likely_truncated"] = bool(vj.get("_ss_likely_truncated"))

    # skip_existing — D11 precedência manual > backoffice > lobby.
    if skip_existing:
        existing = query(
            """SELECT source FROM tournament_payouts
                WHERE site = 'GGPoker' AND tournament_number = %s""",
            (tn,),
        )
        if existing:
            src = existing[0].get("source") or ""
            if src.startswith("backoffice_vision:") or src.startswith("manual:"):
                out["result"] = "skipped_existing"
                out["error"] = f"existing source={src!r}; skip_existing=True"
                return out

    if dry_run:
        out["result"] = "success"
        out["source"] = f"backoffice_vision:{name} (dry_run)"
        return out

    blob = bv.build_backoffice_payouts_blob(
        vj,
        ts_meta.get("tournament_format") or "None",
        ts_meta.get("tournament_pko_ratio"),
    )
    src = f"backoffice_vision:{name}"
    try:
        await asyncio.to_thread(
            payouts_service.upsert_payout,
            site="GGPoker", tournament_number=tn,
            payouts_json=blob, source=src,
        )
    except Exception as e:
        out["result"] = "upsert_error"
        out["error"] = f"{type(e).__name__}: {e}"
        return out

    out["result"] = "success"
    out["source"] = src
    return out


@router.post("/import")
async def import_tournament_results(
    file: UploadFile = File(...),
    site: str = Form("GGPoker"),
    dry_run: bool = Form(False),
    vision_throttle_seconds: float = Form(1.2),
    skip_existing: bool = Form(False),
    current_user=Depends(require_auth),
):
    if site != "GGPoker":
        raise HTTPException(400, "Hoje apenas GGPoker é suportado")
    if vision_throttle_seconds < 0 or vision_throttle_seconds > 30:
        raise HTTPException(400, "vision_throttle_seconds fora de [0, 30]")

    content = await file.read()
    files = _read_files_from_upload(file, content)
    if len(files) > _MAX_IMAGES:
        raise HTTPException(400, f"{len(files)} imagens excede cap {_MAX_IMAGES}")
    if not files:
        return {"total": 0, "results": [], "summary": {}}

    started = datetime.now(timezone.utc)
    results = []
    for name, raw_bytes in files:
        r = await _process_one(
            name, raw_bytes,
            dry_run=dry_run, skip_existing=skip_existing,
            throttle=vision_throttle_seconds,
        )
        results.append(r)

    finished = datetime.now(timezone.utc)
    summary: dict = {}
    for r in results:
        summary[r["result"]] = summary.get(r["result"], 0) + 1

    return {
        "total": len(files),
        "started_at": started.isoformat(),
        "finished_at": finished.isoformat(),
        "duration_seconds": (finished - started).total_seconds(),
        "dry_run": dry_run,
        "results": results,
        "summary": summary,
    }
