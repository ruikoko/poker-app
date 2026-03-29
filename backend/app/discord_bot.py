"""
Bot Discord para extracção automática de mãos de poker.
Lê mensagens dos canais configurados e extrai:
  - Hand Histories em texto (copy-paste)
  - Links de replayers GG (gg.gl, pokercraft)
  - Links de replayers Winamax
  - Screenshots Gyazo
  - Imagens directas do Discord CDN
O nome do canal serve como tag automática para a mão.
"""
import os
import re
import json
import logging
import asyncio
import discord
from discord import Intents
from datetime import datetime, timezone

logger = logging.getLogger("discord_bot")

# ── Configuração ──────────────────────────────────────────────────────────────

DISCORD_TOKEN = os.getenv("DISCORD_BOT_TOKEN", "")
MONITORED_SERVERS = [
    s.strip() for s in os.getenv("DISCORD_SERVER_IDS", "").split(",") if s.strip()
]
# Canais a ignorar (separados por vírgula). Se vazio, lê todos.
IGNORED_CHANNELS = [
    s.strip().lower()
    for s in os.getenv("DISCORD_IGNORED_CHANNELS", "general").split(",")
    if s.strip()
]

# ── Regex para detecção de conteúdo ──────────────────────────────────────────

PATTERNS = {
    "gg_replayer": re.compile(
        r"https?://(?:gg\.gl/\w+|my\.pokercraft\.com/embedded/shared/client/\w+)",
        re.IGNORECASE,
    ),
    "winamax_replayer": re.compile(
        r"https?://(?:www\.)?winamax\.fr/replayer/replayer\.html\S+",
        re.IGNORECASE,
    ),
    "gyazo": re.compile(
        r"https?://(?:i\.)?gyazo\.com/\w+(?:\.\w+)?",
        re.IGNORECASE,
    ),
    "discord_image": re.compile(
        r"https?://cdn\.discordapp\.com/attachments/\S+\.(?:png|jpg|jpeg|gif|webp)",
        re.IGNORECASE,
    ),
    "hand_history": re.compile(
        r"Poker Hand #\w+",
        re.IGNORECASE,
    ),
}


def _channel_to_tags(channel_name: str) -> list[str]:
    """
    Converte o nome do canal em tags.
    Ex: 'icm-pko' → ['icm', 'pko']
         'ip-vs-cbet' → ['ip', 'vs-cbet'] → ['ip', 'cbet']
         'cc3b-ip-pko' → ['cc3b', 'ip', 'pko']
    """
    if not channel_name:
        return []
    parts = channel_name.lower().replace("_", "-").split("-")
    # Remover palavras genéricas
    skip = {"vs", "and", "or", "de", "the", "general"}
    tags = [p for p in parts if p and p not in skip]
    return tags


def _detect_content_type(text: str, attachments: list) -> list[dict]:
    """
    Analisa o texto e attachments de uma mensagem Discord.
    Devolve uma lista de items encontrados, cada um com:
      - type: 'hh_text' | 'gg_replayer' | 'winamax_replayer' | 'gyazo' | 'discord_image'
      - content: o texto ou URL
    """
    items = []

    # Hand History em texto (bloco completo)
    if PATTERNS["hand_history"].search(text or ""):
        items.append({"type": "hh_text", "content": text})

    # Links de replayers e imagens no texto
    for ptype in ["gg_replayer", "winamax_replayer", "gyazo", "discord_image"]:
        for match in PATTERNS[ptype].finditer(text or ""):
            items.append({"type": ptype, "content": match.group(0)})

    # Attachments (imagens directas)
    for att in attachments:
        url = att.url if hasattr(att, "url") else str(att)
        if any(url.lower().endswith(ext) for ext in [".png", ".jpg", ".jpeg", ".gif", ".webp"]):
            items.append({"type": "discord_image", "content": url})

    return items


# ── Persistência ─────────────────────────────────────────────────────────────

def _save_to_db(
    server_id: str,
    server_name: str,
    channel_id: str,
    channel_name: str,
    message_id: str,
    author: str,
    content_type: str,
    content: str,
    tags: list[str],
    message_created_at: datetime,
):
    """Guarda um item extraído na tabela entries e, se for HH texto, tenta parsear para hands."""
    from app.db import get_conn
    from app.services.entry_service import create_entry

    # Determinar site a partir do conteúdo
    site = None
    if content_type in ("gg_replayer",):
        site = "GGPoker"
    elif content_type in ("winamax_replayer",):
        site = "Winamax"
    elif content_type == "hh_text":
        if "ggpoker" in content.lower() or content.strip().startswith("Poker Hand #"):
            site = "GGPoker"
        elif "winamax" in content.lower():
            site = "Winamax"

    # Mapear content_type para entry_type válido
    entry_type_map = {
        "hh_text": "hand_history",
        "gg_replayer": "replayer_link",
        "winamax_replayer": "replayer_link",
        "gyazo": "image",
        "discord_image": "image",
    }

    # Criar entry
    entry = create_entry(
        source="discord",
        entry_type=entry_type_map.get(content_type, "text"),
        site=site,
        file_name=None,
        external_id=message_id,
        raw_text=content,
        raw_json={
            "content_type": content_type,
            "tags_from_channel": tags,
        },
        status="new",
        notes=f"Discord #{channel_name} by {author}",
        import_log_id=None,
        discord_server=server_id,
        discord_channel=channel_id,
        discord_message_id=message_id,
        discord_author=author,
        discord_posted_at=message_created_at,
    )

    entry_id = entry["id"]

    # Se for HH texto, tentar parsear directamente para hands
    if content_type == "hh_text":
        try:
            from app.services.hand_service import process_entry_to_hands
            result = process_entry_to_hands(entry_id)
            logger.info(
                f"HH parsed: {result['inserted']} inserted, {result['skipped']} skipped, "
                f"{len(result['errors'])} errors"
            )
            # Aplicar tags do canal às mãos criadas
            if tags and result["inserted"] > 0:
                _apply_channel_tags(entry_id, tags)
        except Exception as e:
            logger.error(f"Erro ao parsear HH: {e}")
    else:
        # Para links e imagens, criar uma mão placeholder com os dados que temos
        _create_placeholder_hand(entry_id, content_type, content, tags, site, channel_name, message_created_at)

    return entry_id


def _apply_channel_tags(entry_id: int, tags: list[str]):
    """Aplica as tags do canal às mãos que foram criadas a partir desta entry."""
    from app.db import get_conn

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE hands
                SET tags = ARRAY(
                    SELECT DISTINCT unnest(COALESCE(tags, '{}'::text[]) || %s::text[])
                )
                WHERE entry_id = %s
                """,
                (tags, entry_id),
            )
        conn.commit()
    except Exception as e:
        conn.rollback()
        logger.error(f"Erro ao aplicar tags: {e}")
    finally:
        conn.close()


def _create_placeholder_hand(
    entry_id: int,
    content_type: str,
    content: str,
    tags: list[str],
    site: str | None,
    channel_name: str,
    played_at: datetime | None,
):
    """Cria uma mão placeholder para links/imagens que ainda não foram parseados."""
    from app.db import execute_returning

    # Gerar um hand_id único baseado no tipo e conteúdo
    import hashlib
    content_hash = hashlib.sha256(content.encode()).hexdigest()[:12]
    hand_id = f"discord_{content_type}_{content_hash}"

    type_labels = {
        "gg_replayer": "Replayer GG",
        "winamax_replayer": "Replayer Winamax",
        "gyazo": "Screenshot Gyazo",
        "discord_image": "Imagem Discord",
    }

    notes = f"[{type_labels.get(content_type, content_type)}] #{channel_name}\n{content}"

    # For GG replayer links, try to extract the image
    screenshot_url = None
    if content_type == "gg_replayer":
        img_data = _extract_gg_replayer_image(content)
        if img_data:
            screenshot_url = img_data.get("screenshot_url")
            # Update the entry with the image data
            try:
                from app.db import get_conn
                conn = get_conn()
                with conn.cursor() as cur:
                    cur.execute(
                        "UPDATE entries SET raw_json = raw_json || %s WHERE id = %s",
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
                conn.commit()
                conn.close()
            except Exception as e:
                logger.error(f"Erro ao guardar imagem GG replayer: {e}")

    try:
        execute_returning(
            """
            INSERT INTO hands
                (site, hand_id, played_at, notes, tags, raw, entry_id, study_state, screenshot_url)
            VALUES
                (%s, %s, %s, %s, %s, %s, %s, 'new', %s)
            ON CONFLICT (hand_id) DO NOTHING
            RETURNING id
            """,
            (site, hand_id, played_at, notes, tags, content, entry_id, screenshot_url),
        )
    except Exception as e:
        logger.error(f"Erro ao criar placeholder hand: {e}")


def _extract_gg_replayer_image(url: str) -> dict | None:
    """
    Extrai a imagem PNG de um link do replayer GG.
    
    Fluxo:
    1. Fetch do link gg.gl/xxxxx → segue redirect → pokercraft page
    2. Extrai URL da imagem do HTML (og:image ou img tag)
    3. Download do PNG
    4. Retorna URL + base64
    """
    import base64
    try:
        import httpx
    except ImportError:
        try:
            import urllib.request
            # Fallback to urllib
            return _extract_gg_replayer_image_urllib(url)
        except Exception as e:
            logger.error(f"GG replayer extract failed (no httpx): {e}")
            return None

    try:
        # Follow redirects to get the actual page
        with httpx.Client(follow_redirects=True, timeout=15) as client:
            resp = client.get(url)
            if resp.status_code != 200:
                logger.warning(f"GG replayer fetch failed: {resp.status_code} for {url}")
                return None

            html = resp.text

            # Extract image URL from HTML
            # Look for og:image meta tag or direct img src to gg CDN
            img_url = None

            # Try og:image
            import re
            og_m = re.search(r'<meta\s+property=["\']og:image["\']\s+content=["\'](https://[^"\']+)["\']', html)
            if og_m:
                img_url = og_m.group(1)

            # Try direct img src to GG CDN
            if not img_url:
                cdn_m = re.search(r'(https://user\.gg-global-cdn\.com/[^"\'<>\s]+\.png)', html)
                if cdn_m:
                    img_url = cdn_m.group(1)

            # Try any img with TourneyResult
            if not img_url:
                tr_m = re.search(r'(https://[^"\'<>\s]*TourneyResult[^"\'<>\s]*\.png)', html)
                if tr_m:
                    img_url = tr_m.group(1)

            if not img_url:
                logger.warning(f"GG replayer: no image URL found in HTML for {url}")
                return None

            # Download the image
            img_resp = client.get(img_url)
            if img_resp.status_code != 200:
                logger.warning(f"GG replayer image download failed: {img_resp.status_code}")
                return None

            img_bytes = img_resp.content
            img_b64 = base64.b64encode(img_bytes).decode('ascii')

            logger.info(f"GG replayer image extracted: {len(img_bytes)} bytes from {url}")

            return {
                "img_url": img_url,
                "img_b64": img_b64,
                "screenshot_url": img_url,
            }

    except Exception as e:
        logger.error(f"GG replayer extract error: {e}")
        return None


def _extract_gg_replayer_image_urllib(url: str) -> dict | None:
    """Fallback using urllib for GG replayer image extraction."""
    import base64
    import re
    import urllib.request

    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            html = resp.read().decode('utf-8', errors='replace')

        img_url = None
        og_m = re.search(r'<meta\s+property=["\']og:image["\']\s+content=["\'](https://[^"\']+)["\']', html)
        if og_m:
            img_url = og_m.group(1)
        if not img_url:
            cdn_m = re.search(r'(https://user\.gg-global-cdn\.com/[^"\'<>\s]+\.png)', html)
            if cdn_m:
                img_url = cdn_m.group(1)

        if not img_url:
            return None

        img_req = urllib.request.Request(img_url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(img_req, timeout=15) as img_resp:
            img_bytes = img_resp.read()

        img_b64 = base64.b64encode(img_bytes).decode('ascii')
        return {"img_url": img_url, "img_b64": img_b64, "screenshot_url": img_url}

    except Exception as e:
        logger.error(f"GG replayer urllib extract error: {e}")
        return None


# ── Tabela de sync state ────────────────────────────────────────────────────

def _ensure_sync_table():
    """Cria a tabela de estado de sync se não existir."""
    from app.db import execute
    execute("""
        CREATE TABLE IF NOT EXISTS discord_sync_state (
            channel_id TEXT PRIMARY KEY,
            server_id TEXT NOT NULL,
            channel_name TEXT,
            last_message_id TEXT,
            last_sync_at TIMESTAMPTZ DEFAULT NOW(),
            messages_synced INTEGER DEFAULT 0
        )
    """)


def _get_last_message_id(channel_id: str) -> str | None:
    """Devolve o último message_id sincronizado para este canal."""
    from app.db import query
    rows = query(
        "SELECT last_message_id FROM discord_sync_state WHERE channel_id = %s",
        (channel_id,),
    )
    return rows[0]["last_message_id"] if rows else None


def _update_sync_state(channel_id: str, server_id: str, channel_name: str, last_msg_id: str, count: int):
    """Actualiza o estado de sync para este canal."""
    from app.db import execute
    execute(
        """
        INSERT INTO discord_sync_state (channel_id, server_id, channel_name, last_message_id, last_sync_at, messages_synced)
        VALUES (%s, %s, %s, %s, NOW(), %s)
        ON CONFLICT (channel_id) DO UPDATE SET
            last_message_id = EXCLUDED.last_message_id,
            last_sync_at = NOW(),
            messages_synced = discord_sync_state.messages_synced + EXCLUDED.messages_synced
        """,
        (channel_id, server_id, channel_name, last_msg_id, count),
    )


# ── Bot Discord ──────────────────────────────────────────────────────────────

class PokerBot(discord.Client):
    """Bot que monitoriza mensagens em tempo real e faz sync histórico."""

    def __init__(self):
        intents = Intents.default()
        intents.message_content = True
        intents.guilds = True
        super().__init__(intents=intents)
        self.synced_servers = set()

    async def on_ready(self):
        logger.info(f"Bot conectado como {self.user} (ID: {self.user.id})")
        logger.info(f"Servidores monitorizados: {MONITORED_SERVERS}")
        logger.info(f"Canais ignorados: {IGNORED_CHANNELS}")
        _ensure_sync_table()

        # Sync histórico na primeira ligação
        for guild in self.guilds:
            if str(guild.id) in MONITORED_SERVERS:
                logger.info(f"Servidor encontrado: {guild.name} ({guild.id})")
                asyncio.create_task(self._sync_guild_history(guild))

    def _should_monitor(self, channel) -> bool:
        """Verifica se o canal deve ser monitorizado."""
        if not hasattr(channel, "guild"):
            return False
        if str(channel.guild.id) not in MONITORED_SERVERS:
            return False
        if channel.name.lower() in IGNORED_CHANNELS:
            return False
        # Apenas canais de texto
        if not isinstance(channel, discord.TextChannel):
            return False
        return True

    async def on_message(self, message: discord.Message):
        """Processa mensagens em tempo real."""
        # Ignorar mensagens do próprio bot
        if message.author == self.user:
            return

        if not self._should_monitor(message.channel):
            return

        await self._process_message(message)

    async def _process_message(self, message: discord.Message):
        """Extrai conteúdo de uma mensagem e guarda na BD."""
        text = message.content or ""
        attachments = message.attachments or []

        items = _detect_content_type(text, attachments)
        if not items:
            return

        channel_name = message.channel.name
        tags = _channel_to_tags(channel_name)
        server_id = str(message.guild.id)
        server_name = message.guild.name
        channel_id = str(message.channel.id)
        message_id = str(message.id)
        author = str(message.author)

        for item in items:
            try:
                _save_to_db(
                    server_id=server_id,
                    server_name=server_name,
                    channel_id=channel_id,
                    channel_name=channel_name,
                    message_id=message_id,
                    author=author,
                    content_type=item["type"],
                    content=item["content"],
                    tags=tags,
                    message_created_at=message.created_at,
                )
                logger.info(
                    f"Extraído [{item['type']}] de #{channel_name} por {author}"
                )
            except Exception as e:
                logger.error(f"Erro ao guardar item de #{channel_name}: {e}")

    async def _sync_guild_history(self, guild: discord.Guild):
        """Sync incremental do histórico de mensagens de um servidor."""
        logger.info(f"A iniciar sync histórico de {guild.name}...")
        total_items = 0

        for channel in guild.text_channels:
            if not self._should_monitor(channel):
                continue

            # Verificar permissões
            perms = channel.permissions_for(guild.me)
            if not perms.read_messages or not perms.read_message_history:
                logger.warning(f"Sem permissão para ler #{channel.name}")
                continue

            last_msg_id = _get_last_message_id(str(channel.id))
            after = discord.Object(id=int(last_msg_id)) if last_msg_id else None

            count = 0
            latest_msg_id = last_msg_id

            try:
                async for message in channel.history(limit=500, after=after, oldest_first=True):
                    if message.author == self.user:
                        continue

                    text = message.content or ""
                    attachments = message.attachments or []
                    items = _detect_content_type(text, attachments)

                    if items:
                        tags = _channel_to_tags(channel.name)
                        for item in items:
                            try:
                                _save_to_db(
                                    server_id=str(guild.id),
                                    server_name=guild.name,
                                    channel_id=str(channel.id),
                                    channel_name=channel.name,
                                    message_id=str(message.id),
                                    author=str(message.author),
                                    content_type=item["type"],
                                    content=item["content"],
                                    tags=tags,
                                    message_created_at=message.created_at,
                                )
                                count += 1
                                total_items += 1
                            except Exception as e:
                                logger.error(f"Erro sync #{channel.name}: {e}")

                    latest_msg_id = str(message.id)

                if latest_msg_id and latest_msg_id != last_msg_id:
                    _update_sync_state(
                        str(channel.id), str(guild.id), channel.name, latest_msg_id, count
                    )

                if count > 0:
                    logger.info(f"  #{channel.name}: {count} items extraídos")

            except discord.Forbidden:
                logger.warning(f"  #{channel.name}: acesso negado")
            except Exception as e:
                logger.error(f"  #{channel.name}: erro - {e}")

            # Pequena pausa para não exceder rate limits
            await asyncio.sleep(0.5)

        logger.info(f"Sync de {guild.name} concluído: {total_items} items total")


# ── Arranque ─────────────────────────────────────────────────────────────────

_bot_instance = None


def get_bot() -> PokerBot | None:
    return _bot_instance


async def start_bot():
    """Arranca o bot Discord em background."""
    global _bot_instance

    if not DISCORD_TOKEN:
        logger.warning("DISCORD_BOT_TOKEN não definido — bot desactivado")
        return

    if not MONITORED_SERVERS:
        logger.warning("DISCORD_SERVER_IDS não definido — bot desactivado")
        return

    _bot_instance = PokerBot()
    logger.info("A arrancar bot Discord...")

    try:
        await _bot_instance.start(DISCORD_TOKEN)
    except Exception as e:
        logger.error(f"Erro ao arrancar bot: {e}")
        _bot_instance = None


async def stop_bot():
    """Para o bot Discord."""
    global _bot_instance
    if _bot_instance:
        await _bot_instance.close()
        _bot_instance = None
        logger.info("Bot Discord parado")
