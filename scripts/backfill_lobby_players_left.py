"""pt25-revisado — backfill `players_left` em `lobby_processing_log` históricos.

Estado actual: SHELL. O passo de fetch das image bytes está NotImplemented
porque `lobby_processing_log` NÃO persiste `img_b64`. Imagens lobby passam
in-memory por `process_lobby_message(image_bytes, ...)` e perdem-se. Para
backfill real é preciso re-fetch via Discord API (bot token + channel_id +
message_id) — código preparado mas comentado.

Cobertura actual: ~18 rows históricos em prod. Re-process não bloqueia o
smoke pt25 B5 (Rui pode postar SS fresca → real-time pipeline pega o prompt
novo). Backfill é nice-to-have para data hygiene retroactiva.

Usage (quando implementado):
  cd backend && railway run python ../scripts/backfill_lobby_players_left.py
"""
from __future__ import annotations
import asyncio
import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

# Resolver path: scripts/ corre fora do backend/, importar via injecção
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from app.db import get_conn  # noqa: E402
from app.services import lobby_vision  # noqa: E402

logger = logging.getLogger("backfill_lobby_players_left")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


def _fetch_candidates(conn) -> list[dict]:
    """Rows com discord_message_id + channel_id mas sem players_left,
    com result='success' (Vision correu OK no passado mas faltava o field)."""
    with conn.cursor() as cur:
        cur.execute("""
            SELECT discord_message_id, channel_id, tournament_number,
                   tournament_name, posted_at, attempted_at
              FROM lobby_processing_log
             WHERE result = 'success'
               AND players_left IS NULL
               AND discord_message_id IS NOT NULL
               AND channel_id IS NOT NULL
             ORDER BY posted_at DESC
        """)
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, r)) for r in cur.fetchall()]


async def _fetch_image_bytes_via_discord(message_id: str, channel_id: str) -> tuple[bytes, str]:
    """STUB: refetch da imagem via Discord API.

    Implementação necessária quando arrancar backfill real:
    1. `import discord` (já dep)
    2. Inicializar Client com DISCORD_TOKEN (env)
    3. `channel = await client.fetch_channel(int(channel_id))`
    4. `message = await channel.fetch_message(int(message_id))`
    5. Para cada attachment: `await att.read()` → bytes
    6. Filter por `att.content_type.startswith("image/")`
    7. Devolver primeira imagem válida + mime_type
    8. Tratar rate-limit + auth + permissions

    Sample skeleton (comentado para não correr inadvertidamente):

        import discord
        intents = discord.Intents.default()
        client = discord.Client(intents=intents)
        await client.login(os.environ["DISCORD_TOKEN"])
        try:
            channel = await client.fetch_channel(int(channel_id))
            message = await channel.fetch_message(int(message_id))
            for att in message.attachments:
                ct = (att.content_type or "").lower()
                if ct.startswith("image/"):
                    return await att.read(), ct
            raise RuntimeError("no image attachment in message")
        finally:
            await client.close()
    """
    raise NotImplementedError(
        "Discord re-fetch não implementado. Ver docstring desta função "
        "para skeleton. Custo aproximado: 1-2s por mão (rate-limit) + "
        "$0.01-0.02 por Vision call. ~18 rows actuais ≈ $0.18-0.36."
    )


def _update_row(conn, message_id: str, players_left: int | None, vision_json: dict) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """UPDATE lobby_processing_log
                  SET players_left = %s,
                      vision_json = %s,
                      attempted_at = NOW(),
                      attempt_count = attempt_count + 1
                WHERE discord_message_id = %s""",
            (players_left, json.dumps(vision_json), message_id),
        )
    conn.commit()


async def run(dry_run: bool = True) -> None:
    conn = get_conn()
    try:
        cands = _fetch_candidates(conn)
        logger.info("candidates: %d rows", len(cands))
        ok = 0
        skipped = 0
        for c in cands:
            mid = c["discord_message_id"]
            try:
                img_bytes, mime = await _fetch_image_bytes_via_discord(mid, c["channel_id"])
            except NotImplementedError:
                logger.error("ABORT: Discord re-fetch não implementado")
                return
            except Exception as e:
                logger.warning("skip msg=%s fetch failed: %s", mid, e)
                skipped += 1
                continue
            raw = await asyncio.to_thread(
                lobby_vision.extract_lobby_payout_json, img_bytes, mime,
            )
            vj = lobby_vision.parse_and_validate_lobby_json(raw)
            if vj is None:
                logger.warning("skip msg=%s parse failed", mid)
                skipped += 1
                continue
            pl = vj.get("players_left")
            pl_int = int(pl) if isinstance(pl, int) and pl > 0 else None
            if dry_run:
                logger.info("[DRY] msg=%s players_left=%s vj_keys=%s",
                            mid, pl_int, sorted(vj.keys()))
            else:
                _update_row(conn, mid, pl_int, vj)
                logger.info("[OK] msg=%s players_left=%s", mid, pl_int)
            ok += 1
        logger.info("done: ok=%d skipped=%d", ok, skipped)
    finally:
        conn.close()


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true",
                    help="actually write UPDATE; sem flag = dry-run")
    args = ap.parse_args()
    asyncio.run(run(dry_run=not args.apply))
