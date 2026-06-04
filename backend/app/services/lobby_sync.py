"""Lógica core do pipeline lobby — extraída de discord_bot._handle_lobby_message
para reuso entre o handler real-time e o endpoint sync-recent.

Inclui:
- ensure_lobby_processing_log_schema() — chamada no main startup.
- process_lobby_message() — pipeline Vision → resolver → upsert + log.
- gather_candidates() — channel.history ∖ lobby_processing_log[success].
- run_sync() — orquestração do endpoint sync-recent.

Imports por módulo (não por símbolo) para que patches nos tests existentes
em app.services.lobby_vision.X / app.services.tournament_resolver.X /
app.services.payouts_service.X continuem a apanhar usos de dentro deste
módulo (o atributo é resolvido em runtime via módulo).
"""
from __future__ import annotations
import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Optional

from app.db import get_conn, query
from app.ingest_filters import is_pre_2026
from app.services import lobby_vision, tournament_resolver, payouts_service

logger = logging.getLogger("lobby_sync")

# Anthropic Tier 1 ~50 RPM ≈ 1.2s/req. Semáforo + sleep entre calls.
_anthropic_sem = asyncio.Semaphore(1)

_VALID_RESULTS = frozenset({
    "success", "vision_failed", "json_invalid", "site_undetected",
    "tm_not_found", "tm_ambiguous", "no_attachments", "pre_2026_skip",
    "upsert_error",
})


def ensure_lobby_processing_log_schema():
    """Idempotente. Chamada no lifespan."""
    sql = """
    CREATE TABLE IF NOT EXISTS lobby_processing_log (
        discord_message_id  TEXT PRIMARY KEY,
        channel_id          TEXT,
        attempted_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        attempt_count       INTEGER NOT NULL DEFAULT 1,
        result              TEXT NOT NULL,
        reason_detail       TEXT,
        site                TEXT,
        tournament_name     TEXT,
        tournament_number   TEXT,
        vision_json         JSONB,
        posted_at           TIMESTAMPTZ
    );
    """
    idx_attempted = (
        "CREATE INDEX IF NOT EXISTS idx_lobby_log_attempted_at "
        "ON lobby_processing_log (attempted_at DESC);"
    )
    idx_result = (
        "CREATE INDEX IF NOT EXISTS idx_lobby_log_result "
        "ON lobby_processing_log (result);"
    )
    # pt25: coluna players_left dedicada para o queue_export trigger do
    # prune-in-gap-downstream. Idempotente (IF NOT EXISTS). Permanece NULL
    # nos 18 rows historicos enquanto não houver backfill via Discord re-fetch.
    add_players_left = (
        "ALTER TABLE lobby_processing_log "
        "ADD COLUMN IF NOT EXISTS players_left INTEGER;"
    )
    # Index para o lookup BY tournament_number ORDER BY posted_at DESC
    idx_tn_posted = (
        "CREATE INDEX IF NOT EXISTS idx_lobby_log_tn_posted "
        "ON lobby_processing_log (tournament_number, posted_at DESC) "
        "WHERE tournament_number IS NOT NULL AND players_left IS NOT NULL;"
    )
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(sql)
            cur.execute(idx_attempted)
            cur.execute(idx_result)
            cur.execute(add_players_left)
            cur.execute(idx_tn_posted)
        conn.commit()
    finally:
        conn.close()


def _upsert_lobby_log(
    *,
    message_id: str,
    channel_id: Optional[str],
    result: str,
    reason_detail: Optional[str] = None,
    site: Optional[str] = None,
    tournament_name: Optional[str] = None,
    tournament_number: Optional[str] = None,
    vision_json: Optional[dict] = None,
    posted_at: Optional[datetime] = None,
    players_left: Optional[int] = None,
) -> None:
    """UPSERT por message_id. Incrementa attempt_count em conflito.

    Falhas BD são engolidas com logger.error — não devem partir o handler
    real-time ou o batch sync se a tabela estiver indisponível. ValueError
    em `result` inválido continua a propagar (caller bug).

    pt25: `players_left` (int|None) — extraído pelo Vision da SS lobby
    mid-tournament; usado como trigger do prune-in-gap-downstream em
    queue_export. Coluna dedicada (não apenas dentro de vision_json) para
    query simples por `tournament_number`.
    """
    if result not in _VALID_RESULTS:
        raise ValueError(f"invalid result {result!r}")
    try:
        conn = get_conn()
    except Exception as e:
        logger.error(f"[lobby_log] get_conn failed: {type(e).__name__}: {e}")
        return
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO lobby_processing_log (
                    discord_message_id, channel_id, attempted_at, attempt_count,
                    result, reason_detail, site, tournament_name,
                    tournament_number, vision_json, posted_at, players_left
                ) VALUES (
                    %s, %s, NOW(), 1, %s, %s, %s, %s, %s, %s, %s, %s
                )
                ON CONFLICT (discord_message_id) DO UPDATE SET
                    attempted_at      = NOW(),
                    attempt_count     = lobby_processing_log.attempt_count + 1,
                    result            = EXCLUDED.result,
                    reason_detail     = EXCLUDED.reason_detail,
                    site              = COALESCE(EXCLUDED.site, lobby_processing_log.site),
                    tournament_name   = COALESCE(EXCLUDED.tournament_name, lobby_processing_log.tournament_name),
                    tournament_number = COALESCE(EXCLUDED.tournament_number, lobby_processing_log.tournament_number),
                    vision_json       = COALESCE(EXCLUDED.vision_json, lobby_processing_log.vision_json),
                    posted_at         = COALESCE(EXCLUDED.posted_at, lobby_processing_log.posted_at),
                    players_left      = COALESCE(EXCLUDED.players_left, lobby_processing_log.players_left)
                """,
                (
                    message_id, channel_id, result, reason_detail,
                    site, tournament_name, tournament_number,
                    json.dumps(vision_json) if vision_json else None,
                    posted_at, players_left,
                ),
            )
        conn.commit()
    except Exception as e:
        logger.error(f"[lobby_log] insert failed msg_id={message_id}: {type(e).__name__}: {e}")
        try:
            conn.rollback()
        except Exception:
            pass
    finally:
        try:
            conn.close()
        except Exception:
            pass


async def process_lobby_message(
    image_bytes: bytes,
    mime_type: str,
    message_id: str,
    channel_id: Optional[str],
    posted_at: datetime,
    caption_text: str = "",
    tn_override: Optional[str] = None,
    *,
    throttle_seconds: float = 0.0,
    source_prefix: str = "discord_lobby_vision",
    log_on_failure: bool = True,
) -> dict:
    """Vision → parse → resolver → upsert payouts → log.

    Devolve dict com todas as keys necessárias ao caller construir reply:
    result, reason_detail, site, tournament_name, tournament_number,
    vision_json, prizes_count, candidates (list), bounty_type,
    progressive_factor, action ("inserted"/"updated"/None).
    """
    base = {
        "result": "", "reason_detail": None,
        "site": None, "tournament_name": None, "tournament_number": None,
        "vision_json": None, "prizes_count": 0, "players_left": None,
        "candidates": [], "bounty_type": None, "progressive_factor": None,
        "action": None,
        # detalhe de import (página Lobbys): como resolveu + precedência + o que
        # ficou escrito em tournament_payouts.
        "resolver_tier": None, "existing_source": None, "payouts_blob": None,
    }

    if is_pre_2026(posted_at):
        base["result"] = "pre_2026_skip"
        return base

    async with _anthropic_sem:
        raw = await asyncio.to_thread(
            lobby_vision.extract_lobby_payout_json, image_bytes, mime_type
        )
        if throttle_seconds > 0:
            await asyncio.sleep(throttle_seconds)

    if raw is None:
        if log_on_failure:
            _upsert_lobby_log(
                message_id=message_id, channel_id=channel_id,
                result="vision_failed",
                reason_detail="extract_lobby_payout_json returned None",
                posted_at=posted_at,
            )
        base["result"] = "vision_failed"
        base["reason_detail"] = "vision_returned_none"
        return base

    vj = lobby_vision.parse_and_validate_lobby_json(raw)
    if vj is None:
        if log_on_failure:
            _upsert_lobby_log(
                message_id=message_id, channel_id=channel_id,
                result="json_invalid",
                reason_detail=f"raw_head={raw[:200]!r}",
                posted_at=posted_at,
            )
        base["result"] = "json_invalid"
        base["reason_detail"] = f"raw_head={raw[:80]!r}"
        return base

    site = vj.get("site")
    name = vj.get("tournament_name")
    # pt25: players_left lido do prompt extension; pode ser None se Vision
    # não encontrou o número (e.g. campo invisível em alguns layouts).
    # Coerce defensiva: aceita só int positivo, descarta None/0/strings.
    _pl_raw = vj.get("players_left")
    players_left: Optional[int] = (
        int(_pl_raw) if isinstance(_pl_raw, int) and _pl_raw > 0 else None
    )
    base["site"] = site
    base["tournament_name"] = name
    base["vision_json"] = vj
    base["prizes_count"] = len(vj.get("prizes") or {})
    base["players_left"] = players_left

    if site not in ("GGPoker", "PokerStars", "Winamax"):
        if log_on_failure:
            _upsert_lobby_log(
                message_id=message_id, channel_id=channel_id,
                result="site_undetected",
                reason_detail=f"vision_site={site!r}",
                site=site, tournament_name=name,
                vision_json=vj, posted_at=posted_at,
                players_left=players_left,
            )
        base["result"] = "site_undetected"
        base["reason_detail"] = f"vision_site={site!r}"
        return base

    if tn_override:
        tn = tn_override
        candidates: list = []
        resolver_tier = "caption_override"  # bypass do resolver via caption #TM<n>
    else:
        tn, candidates, resolver_tier = await asyncio.to_thread(
            tournament_resolver.resolve_tournament_number,
            site, name, vj.get("start_time_iso"),
            posted_at_hint=posted_at,
            buy_in=vj.get("buy_in"),
            anchor_mode="prestart",  # pt41 Track A — lobby SS é pré-start
            return_tier=True,
        )
    base["resolver_tier"] = resolver_tier

    if tn is None:
        result = "tm_ambiguous" if candidates else "tm_not_found"
        reason = (f"n_candidates={len(candidates)}"
                  if candidates else f"start={vj.get('start_time_iso')!r}")
        _upsert_lobby_log(
            message_id=message_id, channel_id=channel_id,
            result=result, reason_detail=reason,
            site=site, tournament_name=name,
            vision_json=vj, posted_at=posted_at,
            players_left=players_left,
        )
        base["result"] = result
        base["reason_detail"] = reason
        base["candidates"] = candidates
        return base

    # #SYNC-RECENT-RESPECT-MANUAL (pt43) — guarda de precedência D11
    # (manual > backoffice_vision > discord_lobby_vision). O lobby é a fonte de
    # menor prioridade: NÃO sobrescreve manual/backoffice já presentes (dados
    # parciais do lobby = regressão de qualidade). Discord-sobre-Discord passa
    # (last-write-wins na mesma fonte). Espelha o skip_existing do backoffice
    # (routers/tournament_results.py:170-182). Ref: REGRAS_NEGOCIO.md §12.2.
    existing = await asyncio.to_thread(
        query,
        "SELECT source FROM tournament_payouts "
        "WHERE site = %s AND tournament_number = %s",
        (site, tn),
    )
    if existing:
        cur_src = existing[0].get("source") or ""
        if cur_src.startswith("manual:") or cur_src.startswith("backoffice_vision:"):
            _upsert_lobby_log(
                message_id=message_id, channel_id=channel_id,
                result="skipped_precedence",
                reason_detail=f"existing source={cur_src!r} >= discord_lobby_vision",
                site=site, tournament_name=name, tournament_number=tn,
                vision_json=vj, posted_at=posted_at,
                players_left=players_left,
            )
            base["result"] = "skipped_precedence"
            base["reason_detail"] = f"existing source={cur_src!r}"
            base["tournament_number"] = tn
            base["existing_source"] = cur_src
            return base

    blob = lobby_vision.build_hrc_payouts_blob(vj)
    try:
        upsert_res = await asyncio.to_thread(
            payouts_service.upsert_payout,
            site=site, tournament_number=tn,
            payouts_json=blob,
            source=f"{source_prefix}:{message_id}",
        )
        action = (upsert_res or {}).get("action")
    except Exception as e:
        _upsert_lobby_log(
            message_id=message_id, channel_id=channel_id,
            result="upsert_error",
            reason_detail=f"{type(e).__name__}: {e}",
            site=site, tournament_name=name, tournament_number=tn,
            vision_json=vj, posted_at=posted_at,
            players_left=players_left,
        )
        base["result"] = "upsert_error"
        base["reason_detail"] = str(e)
        base["tournament_number"] = tn
        return base

    # Extrai bounty_type + progressive_factor da structure[0] do blob.
    s0 = (blob.get("structures") or [{}])[0]
    bounty_type = s0.get("bountyType")
    progressive_factor = s0.get("progressiveFactor")

    _upsert_lobby_log(
        message_id=message_id, channel_id=channel_id,
        result="success",
        site=site, tournament_name=name, tournament_number=tn,
        vision_json=vj, posted_at=posted_at,
        players_left=players_left,
    )
    base["result"] = "success"
    base["tournament_number"] = tn
    base["bounty_type"] = bounty_type
    base["progressive_factor"] = progressive_factor
    base["action"] = action
    base["payouts_blob"] = blob   # o que ficou escrito em tournament_payouts
    # se o torneio já existia, regista a source anterior (overwrite same-source)
    base["existing_source"] = (existing[0].get("source") if existing else None)
    return base


async def gather_candidates(
    channel,
    since: datetime,
    until: datetime,
    max_messages: int,
    *,
    failure_types: Optional[list[str]] = None,
    retry_success: bool = False,
) -> list:
    """Visita channel.history(since..until) e devolve mensagens cuja
    discord_message_id (a) não está em lobby_processing_log, OU
    (b) está com result ∈ failure_types e retry_success=False, OU
    (c) está com result='success' mas retry_success=True.

    Limita a max_messages. Ignora mensagens do próprio bot e sem attachments.
    """
    existing_log = {
        row["discord_message_id"]: row["result"]
        for row in query(
            "SELECT discord_message_id, result FROM lobby_processing_log",
            (),
        )
    }
    filt = set(failure_types) if failure_types else None

    out = []
    bot_user = getattr(channel.guild, "me", None)
    bot_user_id = getattr(bot_user, "id", None) if bot_user else None

    # limit=None: o discord.py pagina internamente (lazy) toda a janela
    # after/before; o cap real é max_messages (break abaixo). Sem isto o default
    # 100 do discord.py cortava janelas largas em silêncio
    # (#LOBBY-SYNC-PAGINATION-LIMIT). NÃO toca os canais de estudo
    # (_sync_guild_history em discord_bot.py, que já passa limit=500).
    async for msg in channel.history(after=since, before=until, oldest_first=True, limit=None):
        if bot_user_id is not None and getattr(msg.author, "id", None) == bot_user_id:
            continue
        if not msg.attachments:
            continue
        mid = str(msg.id)
        prior = existing_log.get(mid)
        if prior == "success" and not retry_success:
            continue
        if prior and prior != "success":
            if filt is not None and prior not in filt:
                continue
        out.append(msg)
        if len(out) >= max_messages:
            break
    return out


async def run_sync(
    since: datetime,
    until: datetime,
    sites: Optional[list[str]] = None,
    max_messages: int = 200,
    dry_run: bool = False,
    throttle_seconds: float = 1.2,
    failure_types: Optional[list[str]] = None,
    retry_success: bool = False,
) -> dict:
    """Orquestra sync-recent. Retorna dict serializável."""
    from app.discord_bot import get_bot, LOBBY_CHANNEL_NAME

    bot = get_bot()
    if bot is None or not bot.is_ready():
        raise RuntimeError("bot_offline")

    channel = None
    for g in bot.guilds:
        for ch in g.text_channels:
            if ch.name.lower() == LOBBY_CHANNEL_NAME:
                channel = ch
                break
        if channel:
            break
    if channel is None:
        raise RuntimeError("lobby_channel_not_found")

    started = datetime.now(timezone.utc)
    candidates = await gather_candidates(
        channel, since, until, max_messages,
        failure_types=failure_types, retry_success=retry_success,
    )

    already_q = query(
        """SELECT COUNT(*) AS n
             FROM lobby_processing_log
            WHERE result = 'success'
              AND posted_at >= %s AND posted_at < %s""",
        (since, until),
    )
    already_success = already_q[0]["n"] if already_q else 0

    results = {"success_new": 0, "still_failed": 0, "errors": 0}
    successes: list[dict] = []
    failures: list[dict] = []
    rate_limit_pauses = 0

    for msg in candidates:
        if dry_run:
            failures.append({
                "message_id": str(msg.id), "reason": "dry_run",
                "site": None, "name": None,
                "posted_at": msg.created_at.isoformat(),
            })
            continue

        # Extrai bytes da 1ª attachment imagem.
        att = next(
            (a for a in msg.attachments
             if (getattr(a, "content_type", "") or "").startswith("image/")
                or (getattr(a, "filename", "") or "").lower().endswith(
                    (".png", ".jpg", ".jpeg", ".webp"))),
            None,
        )
        if att is None:
            _upsert_lobby_log(
                message_id=str(msg.id), channel_id=str(channel.id),
                result="no_attachments", posted_at=msg.created_at,
            )
            failures.append({
                "message_id": str(msg.id), "reason": "no_attachments",
                "site": None, "name": None,
                "posted_at": msg.created_at.isoformat(),
            })
            continue

        try:
            content_bytes = await att.read()
        except Exception as e:
            results["errors"] += 1
            failures.append({
                "message_id": str(msg.id),
                "reason": f"download_error:{type(e).__name__}",
                "site": None, "name": None,
                "posted_at": msg.created_at.isoformat(),
            })
            continue

        from app.services.image_utils import detect_image_mime
        from app.discord_bot import _extract_tn_from_caption
        mime = detect_image_mime(content_bytes)
        tn_override = _extract_tn_from_caption(msg.content or "")

        try:
            r = await process_lobby_message(
                content_bytes, mime, str(msg.id), str(channel.id),
                msg.created_at, msg.content or "", tn_override,
                throttle_seconds=throttle_seconds,
            )
        except Exception as e:
            results["errors"] += 1
            failures.append({
                "message_id": str(msg.id),
                "reason": f"process_error:{type(e).__name__}",
                "site": None, "name": None,
                "posted_at": msg.created_at.isoformat(),
            })
            continue

        if throttle_seconds > 0:
            rate_limit_pauses += 1

        if sites and r["site"] and r["site"] not in sites:
            continue

        if r["result"] == "success":
            results["success_new"] += 1
            successes.append({
                "message_id": str(msg.id),
                "site": r["site"],
                "tournament_number": r["tournament_number"],
                "tournament_name": r["tournament_name"],
            })
        else:
            results["still_failed"] += 1
            meta = query(
                """SELECT attempt_count, attempted_at
                     FROM lobby_processing_log
                    WHERE discord_message_id = %s""",
                (str(msg.id),),
            )
            m = dict(meta[0]) if meta else {}
            last_at = m.get("attempted_at")
            failures.append({
                "message_id": str(msg.id),
                "reason": r["result"],
                "reason_detail": r["reason_detail"],
                "site": r["site"],
                "name": r["tournament_name"],
                "posted_at": msg.created_at.isoformat(),
                "attempt_count": m.get("attempt_count"),
                "last_attempt_at": last_at.isoformat() if last_at else None,
            })

    finished = datetime.now(timezone.utc)
    return {
        "started_at": started.isoformat(),
        "finished_at": finished.isoformat(),
        "duration_seconds": (finished - started).total_seconds(),
        "dry_run": dry_run,
        "discord_history_count": len(candidates),
        "already_success_skipped_in_window": already_success,
        "candidates": len(candidates),
        "processed": len(candidates) if not dry_run else 0,
        "results": results,
        "successes": successes,
        "failures": failures,
        "rate_limit_pauses": rate_limit_pauses,
    }


# ── Reconcile: re-resolver lobbys pendentes contra o estado ACTUAL da BD ──────

def _coerce_players_left(vj: dict) -> Optional[int]:
    """Mesma coerção defensiva de process_lobby_message: só int positivo."""
    v = (vj or {}).get("players_left")
    return v if isinstance(v, int) and v > 0 else None


def reconcile_lobby_logs(message_ids: Optional[list] = None, dry_run: bool = False) -> dict:
    """Re-corre o resolver sobre lobbys que ficaram `tm_not_found`/`tm_ambiguous`,
    usando o `vision_json` JÁ GUARDADO no log — SEM chamar a Vision. Quando o
    torneio se tornou resolvível (chegaram mãos/TS), escreve o payout (respeitando
    a precedência D11 manual/backoffice) e actualiza o log para `success`
    (ou `skipped_precedence`).

    Idempotente: ao resolver, a row deixa de estar em ('tm_not_found','tm_ambiguous')
    e sai da selecção; `upsert_payout` é upsert; re-correr sem dados novos é no-op.
    Determinístico: só toca a BD quando o resolver passa a casar.

    Disparado fire-and-forget após os imports de HH/TS e on-demand via
    `POST /api/lobbys/reconcile`. `dry_run=True` → calcula e devolve o preview
    por torneio, sem escrever. `message_ids=[]` → curto-circuita.

    Devolve {scanned, resolved, written, skipped_precedence, still_unresolved,
    dry_run, items:[...]}.
    """
    if message_ids is not None and len(message_ids) == 0:
        return {"scanned": 0, "resolved": 0, "written": 0, "skipped_precedence": 0,
                "still_unresolved": 0, "dry_run": dry_run, "items": []}

    sql = (
        "SELECT discord_message_id, site, tournament_name, posted_at, "
        "       vision_json, result "
        "FROM lobby_processing_log "
        "WHERE result IN ('tm_not_found', 'tm_ambiguous') "
        "  AND vision_json IS NOT NULL"
    )
    if message_ids is not None:
        rows = query(sql + " AND discord_message_id = ANY(%s)", (list(message_ids),))
    else:
        rows = query(sql)

    scanned = resolved = written = skipped_prec = still = 0
    items: list[dict] = []

    for r in rows:
        scanned += 1
        vj = r.get("vision_json") or {}
        site = r.get("site") or vj.get("site")
        name = r.get("tournament_name") or vj.get("tournament_name")
        posted_at = r.get("posted_at")
        # anchor prestart, convenção pt51 (Lisboa naive) — descarta tz se vier
        anchor = posted_at
        if anchor is not None and getattr(anchor, "tzinfo", None) is not None:
            anchor = anchor.replace(tzinfo=None)

        tn, candidates, tier = tournament_resolver.resolve_tournament_number(
            site, name, vj.get("start_time_iso"),
            posted_at_hint=anchor, buy_in=vj.get("buy_in"),
            anchor_mode="prestart", return_tier=True,
        )

        item = {
            "message_id": r["discord_message_id"], "site": site,
            "tournament_name": name, "prev_result": r.get("result"),
            "resolved_tn": tn, "resolver_tier": tier, "n_candidates": len(candidates),
            # data da captura/post (Lisboa wall-clock) — deixa claro que um pendente
            # está à espera dos dados do PRÓPRIO dia, não avariado.
            "lobby_date": posted_at.date().isoformat() if posted_at else None,
        }

        if tn is None:
            still += 1
            item["action"] = "still_ambiguous" if candidates else "still_unresolved"
            items.append(item)
            continue

        resolved += 1
        # Precedência D11: lobby é a fonte de menor prioridade — NÃO sobrescreve
        # manual:/backoffice_vision: já presentes. Espelha process_lobby_message.
        existing = query(
            "SELECT source FROM tournament_payouts WHERE site = %s AND tournament_number = %s",
            (site, tn),
        )
        cur_src = (existing[0].get("source") or "") if existing else ""

        if cur_src.startswith("manual:") or cur_src.startswith("backoffice_vision:"):
            skipped_prec += 1
            item["action"] = "skipped_precedence"
            item["existing_source"] = cur_src
            if not dry_run:
                _upsert_lobby_log(
                    message_id=r["discord_message_id"], channel_id=None,
                    result="skipped_precedence",
                    reason_detail=f"reconcile: existing source={cur_src!r} >= lobby",
                    site=site, tournament_name=name, tournament_number=tn,
                    vision_json=vj, posted_at=posted_at,
                    players_left=_coerce_players_left(vj),
                )
            items.append(item)
            continue

        item["action"] = "written"
        item["existing_source"] = cur_src or None
        if not dry_run:
            blob = lobby_vision.build_hrc_payouts_blob(vj)
            upsert_res = payouts_service.upsert_payout(
                site=site, tournament_number=tn, payouts_json=blob,
                source=f"reconcile_lobby_vision:{r['discord_message_id']}",
            )
            item["payout_action"] = (upsert_res or {}).get("action")
            _upsert_lobby_log(
                message_id=r["discord_message_id"], channel_id=None,
                result="success",
                site=site, tournament_name=name, tournament_number=tn,
                vision_json=vj, posted_at=posted_at,
                players_left=_coerce_players_left(vj),
            )
        written += 1
        items.append(item)

    logger.info(
        "[lobby_reconcile] scanned=%d resolved=%d written=%d skipped_precedence=%d "
        "still_unresolved=%d dry_run=%s",
        scanned, resolved, written, skipped_prec, still, dry_run,
    )
    return {
        "scanned": scanned, "resolved": resolved, "written": written,
        "skipped_precedence": skipped_prec, "still_unresolved": still,
        "dry_run": dry_run, "items": items,
    }
