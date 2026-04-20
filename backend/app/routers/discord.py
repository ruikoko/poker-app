"""
API endpoints para monitorização e controlo do bot Discord.
"""
import logging
from fastapi import APIRouter, Depends, HTTPException, Query
from app.auth import require_auth
from app.db import query

logger = logging.getLogger("discord_router")
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


@router.post("/sync-and-process")
async def sync_and_process(current_user=Depends(require_auth)):
    """
    Workflow completo de varrimento pós-sessão:
      1. Sync Discord (vai buscar mensagens novas e cria entries)
      2. Espera um período para _sync_guild_history processar mensagens
      3. Processa replayer_links pendentes (extract og:image + Vision + match)
      4. Cria placeholders GGDiscord para SS sem HH

    Uso: clicar uma vez após fechar as salas de poker no fim da sessão.
    """
    import asyncio
    from app.discord_bot import get_bot, MONITORED_SERVERS

    bot = get_bot()
    if not bot or not bot.is_ready():
        raise HTTPException(status_code=503, detail="Bot Discord não está online")

    # 1. Sync — dispara em background
    synced_servers = 0
    sync_tasks = []
    for guild in bot.guilds:
        if str(guild.id) in MONITORED_SERVERS:
            t = asyncio.create_task(bot._sync_guild_history(guild))
            sync_tasks.append(t)
            synced_servers += 1

    # 2. Esperar sync terminar (com timeout para não bloquear)
    if sync_tasks:
        try:
            await asyncio.wait_for(asyncio.gather(*sync_tasks), timeout=120)
        except asyncio.TimeoutError:
            logger.warning("[sync-and-process] sync timeout, continuando para processamento")

    # 3. Contar entries criados
    from app.db import query as _q
    new_entries = _q("""
        SELECT COUNT(*) AS n FROM entries
        WHERE source = 'discord'
          AND entry_type = 'replayer_link'
          AND site = 'GGPoker'
          AND (raw_json->>'img_b64') IS NULL
    """)[0]["n"]

    # 4. Processar replayer_links (extract + Vision em background)
    processed_response = None
    if new_entries > 0:
        try:
            processed_response = await process_replayer_links(confirm=True, limit=200, current_user=current_user)
        except HTTPException as e:
            processed_response = {"error": str(e.detail)}

    # 5. Backfill GGDiscord para os que não tiveram match
    #    Esperar um pouco para Vision correr em background antes de criar placeholders
    await asyncio.sleep(10)
    backfill_response = None
    try:
        backfill_response = backfill_ggdiscord(confirm=True, current_user=current_user)
    except HTTPException:
        pass

    return {
        "ok": True,
        "servers_synced": synced_servers,
        "new_replayer_entries": new_entries,
        "process_result": processed_response,
        "backfill_result": backfill_response,
        "note": "Vision corre em background. Actualizar a página daqui a ~30s para ver resultados finais.",
    }


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


@router.get("/debug-fetch")
def debug_fetch(url: str, current_user=Depends(require_auth)):
    """
    DIAGNÓSTICO. Faz fetch de um URL e devolve metadata detalhada:
    status HTTP, tamanho HTML, URL final (após redirects), primeiras 2000 chars
    do HTML, se contém 'og:image', se contém URLs *.png do gg-global-cdn.

    Usar para investigar porque _extract_gg_replayer_image falha em URLs gg.gl.
    """
    import re
    try:
        import httpx
    except ImportError:
        raise HTTPException(status_code=500, detail="httpx não instalado")

    # 1º tentativa: sem User-Agent (como o código actual)
    results = {}
    for label, headers in [
        ("no_ua", {}),
        ("with_ua", {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"}),
    ]:
        try:
            with httpx.Client(follow_redirects=True, timeout=15, headers=headers) as client:
                resp = client.get(url)
                html = resp.text
                og_matches = re.findall(r'og:image[^>]{0,200}', html, re.IGNORECASE)
                cdn_matches = re.findall(r'https://user\.gg-global-cdn\.com/[^"\'<>\s]+\.png', html)
                any_png = re.findall(r'https?://[^\s"\'<>]+\.png', html)
                results[label] = {
                    "status_code": resp.status_code,
                    "final_url": str(resp.url),
                    "content_type": resp.headers.get("content-type"),
                    "html_length": len(html),
                    "og_image_matches": og_matches[:3],
                    "og_image_count": len(og_matches),
                    "gg_cdn_png_matches": cdn_matches[:3],
                    "any_png_matches": any_png[:5],
                    "html_first_2000": html[:2000],
                }
        except Exception as e:
            results[label] = {"error": str(e)}

    return {"ok": True, "url": url, "attempts": results}


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


# ─── Backfill GGDiscord para entries com Vision feito mas sem mão ───────────

@router.get("/backfill-ggdiscord/preview")
def backfill_ggdiscord_preview(current_user=Depends(require_auth)):
    """
    DRY-RUN. Lista entries Discord com vision_done=true que não têm mão associada.
    Estes são candidatos a receber uma mão placeholder com hm3_tags=['GGDiscord'].
    """
    rows = query("""
        SELECT e.id, e.raw_json->>'tm' AS tm,
               e.discord_posted_at,
               (e.raw_json->'players_list') AS players_list,
               e.raw_json->>'hero' AS hero,
               (SELECT COUNT(*) FROM hands h WHERE h.entry_id = e.id) AS hands_count
        FROM entries e
        WHERE e.source = 'discord'
          AND e.entry_type = 'replayer_link'
          AND e.site = 'GGPoker'
          AND (e.raw_json->>'vision_done')::boolean = true
        ORDER BY e.id DESC
    """)

    candidates = []
    for r in rows:
        if r["hands_count"] > 0:
            continue
        if not r["tm"]:
            continue
        # Verificar também se já existe mão GG-<tm> (de outro caminho)
        tm_digits = r["tm"].replace("TM", "")
        existing_hand = query(
            "SELECT id FROM hands WHERE hand_id = %s LIMIT 1",
            (f"GG-{tm_digits}",)
        )
        if existing_hand:
            continue
        candidates.append({
            "entry_id": r["id"],
            "tm": r["tm"],
            "hand_id_to_create": f"GG-{tm_digits}",
            "players_count": len(r["players_list"]) if r["players_list"] else 0,
            "hero": r["hero"],
            "posted_at": r["discord_posted_at"].isoformat() if r["discord_posted_at"] else None,
        })

    return {
        "ok": True,
        "total_vision_done": len(rows),
        "candidates_count": len(candidates),
        "candidates": candidates,
    }


@router.post("/backfill-ggdiscord")
def backfill_ggdiscord(
    confirm: bool = False,
    current_user=Depends(require_auth),
):
    """
    Para cada entry Discord com vision_done=true mas sem mão associada,
    cria uma mão placeholder com hm3_tags=['GGDiscord'].

    Quando a HH correspondente for importada via bulk, _promote_to_study
    fará DELETE FROM hands WHERE hand_id = %s e reinserirá com 'GG Hands'.
    """
    if not confirm:
        raise HTTPException(
            status_code=400,
            detail="Adicionar ?confirm=true para executar. Corre /backfill-ggdiscord/preview primeiro."
        )

    import json as _json
    from app.db import get_conn

    rows = query("""
        SELECT e.id, e.raw_json,
               e.discord_posted_at,
               e.discord_channel,
               (SELECT COUNT(*) FROM hands h WHERE h.entry_id = e.id) AS hands_count
        FROM entries e
        WHERE e.source = 'discord'
          AND e.entry_type = 'replayer_link'
          AND e.site = 'GGPoker'
          AND (e.raw_json->>'vision_done')::boolean = true
    """)

    created = 0
    skipped = []
    failed = []

    conn = get_conn()
    try:
        for r in rows:
            entry_id = r["id"]
            if r["hands_count"] > 0:
                skipped.append({"id": entry_id, "reason": "já tem mão associada"})
                continue

            rj = r["raw_json"] or {}
            tm = rj.get("tm")
            if not tm:
                skipped.append({"id": entry_id, "reason": "sem TM"})
                continue

            tm_digits = tm.replace("TM", "")
            hand_id = f"GG-{tm_digits}"

            existing_hand = query(
                "SELECT id FROM hands WHERE hand_id = %s LIMIT 1",
                (hand_id,)
            )
            if existing_hand:
                skipped.append({"id": entry_id, "reason": f"já existe mão {hand_id}"})
                continue

            apa = {
                "_meta": {
                    "num_players": len(rj.get("players_list") or []),
                    "from_discord_placeholder": True,
                }
            }

            pn = {
                "players_list": rj.get("players_list") or [],
                "hero": rj.get("hero"),
                "vision_sb": rj.get("vision_sb"),
                "vision_bb": rj.get("vision_bb"),
                "file_meta": rj.get("file_meta") or {},
                "match_method": "discord_placeholder_no_hh_backfill",
            }

            try:
                with conn.cursor() as cur:
                    cur.execute(
                        """INSERT INTO hands
                           (site, hand_id, played_at, notes, tags, hm3_tags,
                            entry_id, study_state, screenshot_url,
                            all_players_actions, player_names)
                           VALUES ('GGPoker', %s, %s, %s, %s, %s, %s, 'new', %s,
                                   %s::jsonb, %s::jsonb)
                           ON CONFLICT (hand_id) DO NOTHING
                           RETURNING id""",
                        (
                            hand_id,
                            r["discord_posted_at"],
                            f"Discord SS sem HH ainda. TM: {tm}",
                            [],
                            ["GGDiscord"],
                            entry_id,
                            (rj.get("file_meta") or {}).get("og_image_url"),
                            _json.dumps(apa),
                            _json.dumps(pn),
                        )
                    )
                    inserted = cur.fetchone()
                if inserted:
                    created += 1
                else:
                    skipped.append({"id": entry_id, "reason": "ON CONFLICT - mão já existia"})
            except Exception as e:
                failed.append({"id": entry_id, "error": str(e)})

        conn.commit()
        return {
            "ok": True,
            "total_scanned": len(rows),
            "created": created,
            "skipped_count": len(skipped),
            "skipped": skipped[:10],
            "failed_count": len(failed),
            "failed": failed[:10],
        }
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()


# ─── Migração: limpar mãos órfãs do caminho antigo ──────────────────────────

@router.get("/cleanup-old-discord-hands/preview")
def cleanup_old_discord_hands_preview(current_user=Depends(require_auth)):
    """
    DRY-RUN. Lista mãos com hand_id no formato antigo `discord_<type>_<hash>`
    e sem hm3_tags. Eram criadas pelo caminho antigo `_create_placeholder_hand`
    em discord_bot.py, agora desactivado. Estas mãos nunca tiveram Vision corrido.
    """
    rows = query("""
        SELECT h.id, h.hand_id, h.entry_id, h.tags, h.notes, h.screenshot_url,
               h.played_at, h.created_at,
               e.id IS NOT NULL AS entry_exists,
               e.raw_text AS entry_url,
               (e.raw_json->>'vision_done')::boolean AS vision_done
        FROM hands h
        LEFT JOIN entries e ON e.id = h.entry_id
        WHERE h.hand_id LIKE 'discord_%'
          AND (h.hm3_tags IS NULL OR array_length(h.hm3_tags, 1) IS NULL)
        ORDER BY h.id DESC
    """)

    sample = []
    can_reprocess = 0
    no_entry = 0
    for r in rows:
        if r["entry_exists"]:
            can_reprocess += 1
        else:
            no_entry += 1
        if len(sample) < 5:
            sample.append({
                "hand_id": r["hand_id"],
                "entry_id": r["entry_id"],
                "entry_exists": r["entry_exists"],
                "vision_done": r["vision_done"],
                "url": r["entry_url"],
                "tags": r["tags"],
            })

    return {
        "ok": True,
        "total_old_hands": len(rows),
        "can_reprocess_via_entry": can_reprocess,
        "orphan_no_entry": no_entry,
        "sample": sample,
        "note": "POST /cleanup-old-discord-hands?confirm=true apaga estas mãos. Depois usar /process-replayer-links para reprocessar via Vision.",
    }


@router.post("/cleanup-old-discord-hands")
def cleanup_old_discord_hands(
    confirm: bool = False,
    current_user=Depends(require_auth),
):
    """
    Apaga mãos com hand_id antigo `discord_<type>_<hash>` sem hm3_tags.

    Requer ?confirm=true. Antes de correr este endpoint, tomar nota dos entry_ids
    associados (via /preview). Os entries permanecem intactos — depois usar
    POST /api/discord/process-replayer-links?confirm=true para reprocessar via
    Vision e produzir mãos GG-<tm> com hm3_tags correctos.
    """
    if not confirm:
        raise HTTPException(
            status_code=400,
            detail="Adicionar ?confirm=true. Corre /cleanup-old-discord-hands/preview primeiro."
        )

    from app.db import get_conn

    rows = query("""
        SELECT id, hand_id, entry_id
        FROM hands
        WHERE hand_id LIKE 'discord_%'
          AND (hm3_tags IS NULL OR array_length(hm3_tags, 1) IS NULL)
    """)

    deleted = 0
    deleted_ids = []
    entry_ids_to_reprocess = []
    failed = []

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            for r in rows:
                try:
                    cur.execute("DELETE FROM hands WHERE id = %s", (r["id"],))
                    deleted += 1
                    deleted_ids.append(r["hand_id"])
                    if r["entry_id"]:
                        entry_ids_to_reprocess.append(r["entry_id"])
                except Exception as e:
                    failed.append({"hand_id": r["hand_id"], "error": str(e)})

            # Reset img_b64 nos entries para que process-replayer-links os apanhe
            # (filtro do endpoint é img_b64 IS NULL).
            if entry_ids_to_reprocess:
                cur.execute(
                    """UPDATE entries
                       SET raw_json = raw_json - 'img_b64' - 'img_url'
                                                 - 'gg_replayer_resolved' - 'mime_type'
                                                 - 'vision_done' - 'players_list'
                                                 - 'players_by_position' - 'hero'
                                                 - 'board' - 'vision_sb' - 'vision_bb'
                                                 - 'raw_vision' - 'tm' - 'file_meta'
                       WHERE id = ANY(%s)""",
                    (entry_ids_to_reprocess,)
                )

        conn.commit()
        return {
            "ok": True,
            "deleted_hands": deleted,
            "entries_reset_for_reprocessing": len(entry_ids_to_reprocess),
            "failed_count": len(failed),
            "failed": failed[:10],
            "next_step": "POST /api/discord/process-replayer-links?confirm=true&limit=100",
        }
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()
