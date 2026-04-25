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

from app.ingest_filters import is_pre_2026

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
# Processamento automático de mensagens (on_message listener + sync no arranque).
# Default: false — bot liga mas não faz extracção sozinho. Sync só via POST /api/discord/sync.
# Desligar extracção automática reduz risco de scraping contínuo em relação a ToS
# das salas de poker. Ligar extracção manual apenas após sessão terminada.
AUTO_SYNC = os.getenv("DISCORD_AUTO_SYNC", "false").lower() in ("true", "1", "yes")

# ── Regex para detecção de conteúdo ──────────────────────────────────────────

PATTERNS = {
    "gg_replayer": re.compile(
        r"https?://(?:gg\.gl/\w+|my\.pokercraft\.com/embedded/shared/client/\w+)",
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


def _resolve_channel_name_for_entry(entry_id: int) -> str | None:
    """
    Resolve raw channel_name de uma entry Discord via discord_sync_state.
    Devolve None se entry nao existe, nao e' source='discord', ou o canal
    nao esta em discord_sync_state. Usado pelos paths replayer_link/image
    que precisam popular hands.discord_tags na criacao/enriquecimento.
    """
    from app.db import query as _q
    rows = _q(
        """SELECT s.channel_name
           FROM entries e
           LEFT JOIN discord_sync_state s ON s.channel_id = e.discord_channel
           WHERE e.id = %s AND e.source = 'discord'""",
        (entry_id,)
    )
    return rows[0]["channel_name"] if rows and rows[0].get("channel_name") else None


def _detect_content_type(text: str, attachments: list) -> list[dict]:
    """
    Analisa o texto e attachments de uma mensagem Discord.
    Devolve uma lista de items encontrados, cada um com:
      - type: 'hh_text' | 'gg_replayer' | 'gyazo' | 'discord_image'
      - content: o texto ou URL
    """
    items = []

    # Hand History em texto (bloco completo)
    if PATTERNS["hand_history"].search(text or ""):
        items.append({"type": "hh_text", "content": text})

    # Links de replayers e imagens no texto
    for ptype in ["gg_replayer", "gyazo", "discord_image"]:
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
    # Barreira pre-2026: mensagem Discord anterior a 2026 não cria entry.
    if is_pre_2026(message_created_at):
        logger.warning(f"[discord] Mensagem rejeitada: msg_id={message_id} posted_at={message_created_at} (<2026)")
        return None

    from app.db import get_conn
    from app.services.entry_service import create_entry

    # Determinar site a partir do conteúdo
    site = None
    if content_type in ("gg_replayer",):
        site = "GGPoker"
    elif content_type == "hh_text":
        if "ggpoker" in content.lower() or content.strip().startswith("Poker Hand #"):
            site = "GGPoker"
        elif "winamax" in content.lower():
            site = "Winamax"

    # Mapear content_type para entry_type válido
    entry_type_map = {
        "hh_text": "hand_history",
        "gg_replayer": "replayer_link",
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
                _apply_channel_tags(entry_id, tags, channel_name)
        except Exception as e:
            logger.error(f"Erro ao parsear HH: {e}")
    # Para links e imagens: NÃO criar mão placeholder aqui.
    # O processamento (extract og:image + Vision + match + GGDiscord placeholder)
    # corre via POST /api/discord/process-replayer-links accionado pelo botão
    # "Sincronizar Agora" da página /discord. Caminho único e consistente.

    return entry_id


def _apply_channel_tags(entry_id: int, tags: list[str], channel_name: str | None):
    """Aplica metadata Discord as maos criadas a partir desta entry:

      - tags         (legacy): append de tags derivadas de _channel_to_tags,
                               ex: ['icm', 'pko'] (parts split por '-'). Preserva
                               retro-compat com consumers frontend (Hands.jsx,
                               Discord.jsx) que ainda agrupam por esta coluna.

      - discord_tags (canonical): append do NOME BRUTO do canal como single
                                   element, ex: ['icm-pko']. E' o que a regra C
                                   de villain-eligibility le (villains.py:79).
                                   Se channel_name e' falsy, nada e' acrescentado.

      - origin:     COALESCE(origin, 'discord') — so escreve se NULL, preserva
                    valores existentes (hm3/hh_import/etc.).

    Todos os writes sao idempotentes (DISTINCT unnest + COALESCE).
    """
    from app.db import get_conn

    channel_bruto_list = [channel_name] if channel_name else []

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE hands
                SET tags = ARRAY(
                        SELECT DISTINCT unnest(COALESCE(tags, '{}'::text[]) || %s::text[])
                    ),
                    discord_tags = ARRAY(
                        SELECT DISTINCT unnest(COALESCE(discord_tags, '{}'::text[]) || %s::text[])
                    ),
                    origin = COALESCE(origin, 'discord')
                WHERE entry_id = %s
                """,
                (tags, channel_bruto_list, entry_id),
            )
        conn.commit()
    except Exception as e:
        conn.rollback()
        logger.error(f"Erro ao aplicar tags Discord: {e}")
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
    """
    DEPRECATED. Mantido apenas por retro-compat.

    Esta função criava mãos com hand_id sintético tipo "discord_gg_replayer_<hash>"
    e SEM hm3_tags, levando a 21 mãos órfãs em estado limbo. Foi substituída pelo
    fluxo único: _save_to_db cria entry → POST /api/discord/process-replayer-links
    extrai og:image → Vision → cria mão GG-<tm> com hm3_tags=['GG Hands'] ou
    placeholder GGDiscord. Não chamar.
    """
    from app.db import execute_returning

    # Gerar um hand_id único baseado no tipo e conteúdo
    import hashlib
    content_hash = hashlib.sha256(content.encode()).hexdigest()[:12]
    hand_id = f"discord_{content_type}_{content_hash}"

    type_labels = {
        "gg_replayer": "Replayer GG",
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
        # Cloudflare em my.pokercraft.com bloqueia requests sem User-Agent (HTTP 403).
        # Usar UA de browser real.
        _HEADERS = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/*;q=0.8,*/*;q=0.7",
        }
        # Follow redirects to get the actual page
        with httpx.Client(follow_redirects=True, timeout=15, headers=_HEADERS) as client:
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

    _UA = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )

    try:
        req = urllib.request.Request(url, headers={"User-Agent": _UA})
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

        img_req = urllib.request.Request(img_url, headers={"User-Agent": _UA})
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
        logger.info(f"AUTO_SYNC: {AUTO_SYNC} (false = sync só manual via /api/discord/sync)")
        _ensure_sync_table()

        if not AUTO_SYNC:
            logger.info("Auto-sync desligado. Bot fica em standby. Usa POST /api/discord/sync para varrer mensagens.")
            return

        # Sync histórico na primeira ligação (só se AUTO_SYNC=true)
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
        """Processa mensagens em tempo real — desligado se AUTO_SYNC=false."""
        if not AUTO_SYNC:
            return  # standby

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
