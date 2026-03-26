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
def discord_stats(current_user=Depends(require_auth)):
    """Estatísticas de extracção do Discord."""
    # Total de entries do Discord
    rows = query("""
        SELECT
            COUNT(*) AS total_entries,
            COUNT(*) FILTER (WHERE status = 'new') AS pending,
            COUNT(*) FILTER (WHERE status = 'processed') AS processed,
            COUNT(*) FILTER (WHERE status = 'error') AS errors
        FROM entries
        WHERE source = 'discord_bot'
    """)
    entry_stats = dict(rows[0]) if rows else {}

    # Por tipo de conteúdo
    type_rows = query("""
        SELECT
            entry_type,
            COUNT(*) AS count
        FROM entries
        WHERE source = 'discord_bot'
        GROUP BY entry_type
        ORDER BY count DESC
    """)

    # Por canal (do raw_json)
    channel_rows = query("""
        SELECT
            raw_json->>'channel_name' AS channel,
            COUNT(*) AS count
        FROM entries
        WHERE source = 'discord_bot' AND raw_json IS NOT NULL
        GROUP BY raw_json->>'channel_name'
        ORDER BY count DESC
        LIMIT 20
    """)

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
