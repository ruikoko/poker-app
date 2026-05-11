"""Endpoint POST /api/lobbys/sync-recent — re-processa SSs lobby
não persistidas em tournament_payouts."""
from __future__ import annotations
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, validator

from app.auth import require_auth
from app.services.lobby_sync import run_sync

router = APIRouter(prefix="/api/lobbys", tags=["lobbys"])
logger = logging.getLogger("lobbys")

_MAX_MESSAGES_HARD_CAP = 500
_VALID_FAILURE_TYPES = frozenset({
    "vision_failed", "json_invalid", "site_undetected",
    "tm_not_found", "tm_ambiguous", "no_attachments", "upsert_error",
})


class SyncRecentBody(BaseModel):
    since: Optional[datetime] = None
    until: Optional[datetime] = None
    sites: Optional[list[str]] = None
    max_messages: int = Field(200, ge=1, le=_MAX_MESSAGES_HARD_CAP)
    dry_run: bool = False
    vision_throttle_seconds: float = Field(1.2, ge=0.0, le=30.0)
    failure_types: Optional[list[str]] = None
    retry_success: bool = False

    @validator("failure_types")
    def _check_failure_types(cls, v):
        if v is None:
            return v
        bad = set(v) - _VALID_FAILURE_TYPES
        if bad:
            raise ValueError(f"invalid failure_types: {sorted(bad)}")
        return v


@router.post("/sync-recent")
async def sync_recent(
    body: SyncRecentBody,
    current_user=Depends(require_auth),
):
    now = datetime.now(timezone.utc)
    since = body.since or (now - timedelta(hours=24))
    until = body.until or now
    if since.tzinfo is None:
        since = since.replace(tzinfo=timezone.utc)
    if until.tzinfo is None:
        until = until.replace(tzinfo=timezone.utc)
    if since >= until:
        raise HTTPException(400, "since must be < until")

    try:
        result = await run_sync(
            since=since, until=until,
            sites=body.sites,
            max_messages=body.max_messages,
            dry_run=body.dry_run,
            throttle_seconds=body.vision_throttle_seconds,
            failure_types=body.failure_types,
            retry_success=body.retry_success,
        )
    except RuntimeError as e:
        msg = str(e)
        if msg == "bot_offline":
            raise HTTPException(503, "Discord bot is not online")
        if msg == "lobby_channel_not_found":
            raise HTTPException(404, "lobby channel not found in monitored guilds")
        raise

    logger.info(
        "sync-recent done: candidates=%d processed=%d success_new=%d still_failed=%d errors=%d",
        result["candidates"], result["processed"],
        result["results"]["success_new"],
        result["results"]["still_failed"],
        result["results"]["errors"],
    )
    return result
