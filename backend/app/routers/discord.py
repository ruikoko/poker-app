"""
API endpoints para monitorização e controlo do bot Discord.
"""
from fastapi import APIRouter, Depends, HTTPException
from app.auth import require_auth
from app.db import query

router = APIRouter(prefix="/api/discord", tags=["discord"])


@router.get("/status")
def bot_status(current_user=Depends(require_auth)):
    """Estado actual do bot Discord."""
    from app.discord_bot import get_bot, MONITORED_SERVERS, IGNORED_CHANNELS

    bot = get_bot()
    if not bot or not bot.is_ready():
        return {
            "online": False,
            "user": None,
            "servers": [],
            "monitored_server_ids": MONITORED_SERVERS,
            "ignored_channels": IGNORED_CHANNELS,
        }

    servers = []
    for guild in bot.guilds:
        if str(guild.id) in MONITORED_SERVERS:
            channels = []
            for ch in guild.text_channels:
                monitored = ch.name.lower() not in IGNORED_CHANNELS
                channels.append({
                    "id": str(ch.id),
                    "name": ch.name,
                    "monitored": monitored,
                })
            servers.append({
                "id": str(guild.id),
                "name": guild.name,
                "channels": channels,
            })

    return {
        "online": True,
        "user": str(bot.user),
        "servers": servers,
        "monitored_server_ids": MONITORED_SERVERS,
        "ignored_channels": IGNORED_CHANNELS,
    }


@router.get("/sync-state")
def sync_state(current_user=Depends(require_auth)):
    """Estado de sincronização por canal."""
    rows = query("""
        SELECT
            channel_id, server_id, channel_name,
            last_message_id, last_sync_at, messages_synced
        FROM discord_sync_state
        ORDER BY last_sync_at DESC
    """)
    return [dict(r) for r in rows]


@router.post("/sync")
async def trigger_sync(current_user=Depends(require_auth)):
    """Dispara um sync manual do histórico de todos os servidores."""
    import asyncio
    from app.discord_bot import get_bot, MONITORED_SERVERS

    bot = get_bot()
    if not bot or not bot.is_ready():
        raise HTTPException(status_code=503, detail="Bot Discord não está online")

    synced = 0
    for guild in bot.guilds:
        if str(guild.id) in MONITORED_SERVERS:
            asyncio.create_task(bot._sync_guild_history(guild))
            synced += 1

    return {"status": "sync_started", "servers": synced}


@router.get("/stats")
def discord_stats(date_from: str = None, current_user=Depends(require_auth)):
    """Estatísticas de extracção do Discord."""
    date_filter = ""
    date_params = {}
    if date_from:
        date_filter = " AND created_at >= %(date_from)s"
        date_params = {"date_from": date_from}

    # Total de entries do Discord
    rows = query(f"""
        SELECT
            COUNT(*) AS total_entries,
            COUNT(*) FILTER (WHERE status = 'new') AS pending,
            COUNT(*) FILTER (WHERE status = 'processed') AS processed,
            COUNT(*) FILTER (WHERE status = 'error') AS errors
        FROM entries
        WHERE source = 'discord_bot'{date_filter}
    """, date_params)
    entry_stats = dict(rows[0]) if rows else {}

    # Por tipo de conteúdo
    type_rows = query(f"""
        SELECT
            entry_type,
            COUNT(*) AS count
        FROM entries
        WHERE source = 'discord_bot'{date_filter}
        GROUP BY entry_type
        ORDER BY count DESC
    """, date_params)

    # Por canal (do raw_json)
    channel_rows = query(f"""
        SELECT
            raw_json->>'channel_name' AS channel,
            COUNT(*) AS count
        FROM entries
        WHERE source = 'discord_bot' AND raw_json IS NOT NULL{date_filter}
        GROUP BY raw_json->>'channel_name'
        ORDER BY count DESC
        LIMIT 20
    """, date_params)

    # Sync state
    sync_rows = query("""
        SELECT
            COUNT(*) AS channels_synced,
            SUM(messages_synced) AS total_messages,
            MAX(last_sync_at) AS last_sync
        FROM discord_sync_state
    """)
    sync_stats = dict(sync_rows[0]) if sync_rows else {}

    return {
        "entries": entry_stats,
        "by_type": [dict(r) for r in type_rows],
        "by_channel": [dict(r) for r in channel_rows],
        "sync": sync_stats,
    }


@router.post("/resolve-replayers")
async def resolve_replayers(current_user=Depends(require_auth)):
    """
    Re-processa entries de gg_replayer que não têm imagem extraída.
    Faz fetch dos links gg.gl e extrai as imagens PNG.
    """
    from app.db import get_conn
    from app.discord_bot import _extract_gg_replayer_image
    import json

    # Find entries with gg_replayer content that don't have image
    rows = query("""
        SELECT e.id, h.id as hand_id, h.raw as url
        FROM entries e
        JOIN hands h ON h.entry_id = e.id
        WHERE e.entry_type = 'replayer_link'
          AND e.site = 'GGPoker'
          AND (e.raw_json->>'gg_replayer_resolved' IS NULL OR e.raw_json->>'gg_replayer_resolved' = 'false')
          AND h.raw LIKE 'https://gg.gl/%'
    """)

    resolved = 0
    errors = []

    conn = get_conn()
    try:
        for row in rows:
            url = row["url"]
            entry_id = row["id"]
            hand_id = row["hand_id"]

            img_data = _extract_gg_replayer_image(url)
            if img_data:
                with conn.cursor() as cur:
                    cur.execute(
                        "UPDATE entries SET raw_json = COALESCE(raw_json, '{}'::jsonb) || %s WHERE id = %s",
                        (
                            json.dumps({
                                "img_url": img_data.get("img_url"),
                                "img_b64": img_data.get("img_b64"),
                                "mime_type": "image/png",
                                "gg_replayer_resolved": True,
                            }),
                            entry_id,
                        ),
                    )
                    cur.execute(
                        "UPDATE hands SET screenshot_url = %s WHERE id = %s",
                        (img_data.get("img_url"), hand_id),
                    )
                resolved += 1
            else:
                errors.append(f"Failed: {url}")

        conn.commit()
    except Exception as e:
        conn.rollback()
        errors.append(str(e))
    finally:
        conn.close()

    return {"ok": True, "resolved": resolved, "errors": errors[:10], "total_pending": len(rows)}


# ─── Processamento completo de replayer_links Discord ────────────────────────
# Versão mais robusta do /resolve-replayers que NÃO depende de a mão placeholder
# já existir em hands. Para cada entry replayer_link GG em status=new:
#   1. extrai og:image do URL (via _extract_gg_replayer_image)
#   2. dispara _run_vision_for_entry em background
#   3. Vision + match com mtt_hands acontecem automaticamente (mesmo caminho que
#      o upload manual de SS)

@router.get("/process-replayer-links/preview")
def process_replayer_links_preview(current_user=Depends(require_auth)):
    """
    DRY-RUN. Lista os entries replayer_link GG que seriam processados.
    Não modifica nada.
    """
    rows = query("""
        SELECT id, raw_text, status, discord_channel, discord_author,
               discord_posted_at, raw_json,
               (raw_json->>'img_b64' IS NOT NULL) AS has_image,
               (raw_json->>'vision_done')::boolean AS vision_done
        FROM entries
        WHERE entry_type = 'replayer_link'
          AND site = 'GGPoker'
          AND source = 'discord'
        ORDER BY id DESC
    """)

    pending = [r for r in rows if not r["has_image"] and not r["vision_done"]]
    has_image_no_vision = [r for r in rows if r["has_image"] and not r["vision_done"]]
    done = [r for r in rows if r["vision_done"]]

    sample = [
        {
            "id": r["id"],
            "url": r["raw_text"],
            "status": r["status"],
            "channel": r["discord_channel"],
            "posted_at": r["discord_posted_at"].isoformat() if r["discord_posted_at"] else None,
        }
        for r in pending[:5]
    ]

    return {
        "ok": True,
        "total": len(rows),
        "pending_extract": len(pending),
        "has_image_no_vision": len(has_image_no_vision),
        "done": len(done),
        "sample_pending": sample,
    }


@router.post("/process-replayer-links")
async def process_replayer_links(
    confirm: bool = False,
    limit: int = 50,
    current_user=Depends(require_auth),
):
    """
    Reprocessa entries replayer_link GG Discord em status=new.

    Para cada um:
      1. Extrai og:image do URL (sincronamente — rápido, só fetch HTML + PNG)
      2. Guarda img_b64 no entry
      3. Dispara _run_vision_for_entry em background — Vision + match automático

    Requer ?confirm=true. Parâmetro ?limit=N limita quantos processa (default 50).
    Devolve relatório por entry (sucesso extract / falha + razão).
    Vision corre em background, pode demorar ~5s por entry.
    """
    if not confirm:
        raise HTTPException(
            status_code=400,
            detail="Adicionar ?confirm=true para executar. Corre /process-replayer-links/preview primeiro."
        )

    import base64
    import asyncio
    import json
    from app.db import get_conn
    from app.discord_bot import _extract_gg_replayer_image
    from app.routers.screenshot import _run_vision_for_entry

    rows = query("""
        SELECT id, raw_text, discord_posted_at, raw_json
        FROM entries
        WHERE entry_type = 'replayer_link'
          AND site = 'GGPoker'
          AND source = 'discord'
          AND (raw_json->>'img_b64') IS NULL
        ORDER BY id DESC
        LIMIT %s
    """, (limit,))

    report = []
    vision_queued = 0

    conn = get_conn()
    try:
        for r in rows:
            entry_id = r["id"]
            url = (r["raw_text"] or "").strip()
            entry_item = {"id": entry_id, "url": url}

            if not url.startswith("http"):
                entry_item["status"] = "skip"
                entry_item["reason"] = "sem URL válido"
                report.append(entry_item)
                continue

            # Extrair og:image
            try:
                img_data = _extract_gg_replayer_image(url)
            except Exception as e:
                entry_item["status"] = "error_extract"
                entry_item["reason"] = f"excepção: {e}"
                report.append(entry_item)
                continue

            if not img_data:
                entry_item["status"] = "error_extract"
                entry_item["reason"] = "og:image não encontrado ou download falhou"
                report.append(entry_item)
                continue

            img_b64 = img_data.get("img_b64")
            img_url = img_data.get("img_url")
            if not img_b64:
                entry_item["status"] = "error_extract"
                entry_item["reason"] = "img_b64 vazio"
                report.append(entry_item)
                continue

            # Guardar imagem no entry
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        "UPDATE entries SET raw_json = COALESCE(raw_json, '{}'::jsonb) || %s WHERE id = %s",
                        (
                            json.dumps({
                                "img_url": img_url,
                                "img_b64": img_b64,
                                "mime_type": "image/png",
                                "gg_replayer_resolved": True,
                            }),
                            entry_id,
                        ),
                    )
                conn.commit()
            except Exception as e:
                conn.rollback()
                entry_item["status"] = "error_db"
                entry_item["reason"] = f"DB update falhou: {e}"
                report.append(entry_item)
                continue

            # Disparar Vision + match em background (mesma função usada para uploads manuais)
            try:
                content = base64.b64decode(img_b64)
                file_meta = {
                    "source_url": url,
                    "og_image_url": img_url,
                    "via": "discord",
                    "posted_at": r["discord_posted_at"].isoformat() if r["discord_posted_at"] else None,
                }
                asyncio.create_task(
                    _run_vision_for_entry(
                        entry_id=entry_id,
                        content=content,
                        mime_type="image/png",
                        tm_number=None,   # Vision lê o TM da imagem
                        file_meta=file_meta,
                        img_b64=img_b64,
                    )
                )
                vision_queued += 1
                entry_item["status"] = "queued"
                entry_item["img_size_bytes"] = len(content)
                entry_item["img_url"] = img_url
            except Exception as e:
                entry_item["status"] = "error_vision_queue"
                entry_item["reason"] = f"fila Vision falhou: {e}"

            report.append(entry_item)

    finally:
        conn.close()

    return {
        "ok": True,
        "total_scanned": len(rows),
        "vision_queued": vision_queued,
        "report": report,
        "note": "Vision corre em background. Verifica /preview daqui a ~30s para veres quantos têm vision_done.",
    }

