"""Endpoint POST /api/lobbys/sync-recent — re-processa SSs lobby
não persistidas em tournament_payouts."""
from __future__ import annotations
import hashlib
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Query, Body
from pydantic import BaseModel, Field, field_validator

from app.auth import require_auth
from app.db import query
from app.services.image_utils import detect_image_mime
from app.services.lobby_sync import run_sync, process_lobby_message, reconcile_lobby_logs

router = APIRouter(prefix="/api/lobbys", tags=["lobbys"])
logger = logging.getLogger("lobbys")

_MAX_MESSAGES_HARD_CAP = 500
_VALID_FAILURE_TYPES = frozenset({
    "vision_failed", "json_invalid", "site_undetected",
    "tm_not_found", "tm_ambiguous", "no_attachments", "upsert_error",
})

# Resultados que NÃO são lobby (Vision não leu um lobby de torneio). Tudo o resto
# é lobby (mesmo tm_not_found/tm_ambiguous: leu lobby, só não resolveu o número).
_NON_LOBBY = frozenset({"json_invalid", "site_undetected", "vision_failed", "pre_2026_skip"})


class SyncRecentBody(BaseModel):
    since: Optional[datetime] = None
    until: Optional[datetime] = None
    sites: Optional[list[str]] = None
    max_messages: int = Field(200, ge=1, le=_MAX_MESSAGES_HARD_CAP)
    dry_run: bool = False
    vision_throttle_seconds: float = Field(1.2, ge=0.0, le=30.0)
    failure_types: Optional[list[str]] = None
    retry_success: bool = False

    @field_validator("failure_types")
    @classmethod
    def _check_failure_types(cls, v):
        if v is None:
            return v
        bad = set(v) - _VALID_FAILURE_TYPES
        if bad:
            raise ValueError(f"invalid failure_types: {sorted(bad)}")
        return v


@router.post("/upload")
async def upload_lobby_ss(
    file: UploadFile = File(...),
    captured_at: Optional[str] = Form(None),
    site_hint: Optional[str] = Form(None),
    name_hint: Optional[str] = Form(None),
    force: bool = Form(False),
    current_user=Depends(require_auth),
):
    """2ª via de lobby (fora do Discord) — 1 SS da pasta de Capturas do Windows,
    misturada com outros screenshots. GATE 'é lobby?': corre a MESMA Vision de
    lobby; sem torneio (json_invalid/site_undetected/vision_failed) → NÃO é lobby
    → ignora, grava NADA. Lobby (Vision leu torneio) → reutiliza a pipeline
    `process_lobby_message` (→ tournament_payouts + lobby_processing_log), com
    `source=file_lobby_vision:`. Dedup server-side por hash(conteúdo). pt57.

    pt63 — `site_hint`/`name_hint` (opcionais): o appimport, ao rotear a pasta
    única do Intuitive Tables, deriva o site do NOME do ficheiro (e, no GG, o nome
    do torneio). Esses hints têm PRECEDÊNCIA sobre a Vision em
    `process_lobby_message` (rede de segurança p/ capturas cortadas). Sem os campos
    (Discord, LOBBY_DIR), o comportamento é o de sempre.

    #LOBBY-FORCE-REVISION — `force=true` FURA o dedup por conteúdo e re-corre a
    Vision no ficheiro fresco, mas em modo **refresh-only**: reescreve só o
    `vision_json` (open_tab/final_table_size/players_left) da row existente; NÃO
    resolve torneio nem toca `tournament_payouts`. Serve o FT (repor a leitura de um
    print já processado) sem risco nos prémios. A resolução do tn fica para o passo
    separado `POST /api/lobbys/reconcile`."""
    content = await file.read()
    if not content:
        raise HTTPException(400, "Ficheiro vazio")
    mime = detect_image_mime(content)
    # vazio → None (a precedência só dispara com hint real)
    site_hint = (site_hint or "").strip() or None
    name_hint = (name_hint or "").strip() or None

    # posted_at = captured_at (mtime do ficheiro = hora local de Lisboa, naive),
    # usado como âncora prestart do resolver. Fallback: agora (Lisboa naive).
    posted_at: Optional[datetime] = None
    if captured_at:
        try:
            posted_at = datetime.fromisoformat(captured_at)
        except (ValueError, TypeError):
            posted_at = None
    if posted_at is None:
        posted_at = datetime.now(ZoneInfo("Europe/Lisbon"))
    if posted_at.tzinfo is not None:  # convenção pt51: Lisboa naive
        posted_at = posted_at.replace(tzinfo=None)

    file_hash = hashlib.sha256(content).hexdigest()

    # Rede de segurança: este conteúdo já foi processado como lobby? (dedup).
    # Devolve o detalhe guardado no log para a página Lobbys o poder mostrar
    # (extração via vision_json; o import já está em BD, não se re-deriva).
    existing = query(
        "SELECT result, reason_detail, site, tournament_name, tournament_number, "
        "       vision_json, players_left, attempt_count "
        "FROM lobby_processing_log WHERE discord_message_id = %s",
        (file_hash,),
    )
    if existing and not force:
        e = existing[0]
        vj = e.get("vision_json") or {}
        return {
            "is_lobby": e.get("result") not in _NON_LOBBY, "dedup": True,
            "result": e.get("result"), "reason_detail": e.get("reason_detail"),
            "site": e.get("site"),
            "tournament_name": e.get("tournament_name"),
            "tournament_number": e.get("tournament_number"),
            "vision_json": vj, "players_left": e.get("players_left"),
            "prizes_count": len(vj.get("prizes") or {}),
            "attempt_count": e.get("attempt_count"),
            # import não re-derivado no dedup (já persistido):
            "resolver_tier": None, "candidates": [], "existing_source": None,
            "bounty_type": None, "progressive_factor": None,
            "payouts_blob": None, "action": None,
        }

    res = await process_lobby_message(
        content, mime, message_id=file_hash, channel_id=None,
        posted_at=posted_at, source_prefix="file_lobby_vision",
        log_on_failure=False,  # não-lobby (falha de Vision) → não persiste nada
        site_hint=site_hint, name_hint=name_hint,   # pt63 — precedência do filename
        refresh_vision_only=bool(existing) and force,  # force + já existia → só refresh
    )
    is_lobby = res.get("result") not in _NON_LOBBY
    return {
        "is_lobby": is_lobby, "dedup": False, "forced": bool(existing) and force,
        "result": res.get("result"), "reason_detail": res.get("reason_detail"),
        "site": res.get("site"),
        "tournament_name": res.get("tournament_name"),
        "tournament_number": res.get("tournament_number"),
        "action": res.get("action"),
        # extração (Vision)
        "vision_json": res.get("vision_json"),
        "players_left": res.get("players_left"),
        "prizes_count": res.get("prizes_count"),
        # import (backend)
        "resolver_tier": res.get("resolver_tier"),
        "candidates": res.get("candidates"),
        "existing_source": res.get("existing_source"),
        "bounty_type": res.get("bounty_type"),
        "progressive_factor": res.get("progressive_factor"),
        "payouts_blob": res.get("payouts_blob"),
    }


@router.post("/reconcile")
def reconcile_lobbys(
    dry_run: bool = Query(False, description="Calcula sem escrever (preview)"),
    message_ids: Optional[list[str]] = Body(
        None, embed=True,
        description="Limitar a estes discord_message_id (lote específico). "
                    "None/omisso = GLOBAL (todos os pendentes), como antes.",
    ),
    current_user=Depends(require_auth),
):
    """Re-corre o resolver sobre os lobbys pendentes (tm_not_found/tm_ambiguous)
    contra o estado ACTUAL da BD, usando o vision_json já guardado (sem Vision).
    Quando o torneio se tornou resolvível (chegaram mãos/TS), escreve o payout
    (respeitando precedência manual/backoffice) e marca o log success. Idempotente.
    dry_run=True devolve o preview por torneio sem escrever.

    `message_ids` (opcional): restringe a um LOTE específico — não toca nos
    restantes pendentes. Omisso = comportamento GLOBAL de sempre. Ver
    reconcile_lobby_logs (`message_ids=[]` curto-circuita → no-op)."""
    return reconcile_lobby_logs(message_ids=message_ids, dry_run=dry_run)


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
