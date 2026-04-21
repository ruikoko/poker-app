import os
import asyncio
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from app.db import get_conn
from app.routers import health, auth, import_, tournaments, hands, villains
from app.routers.hands import ensure_hm3_tags_column, ensure_has_showdown_column, ensure_discord_tags_column, ensure_origin_column, ensure_buy_in_column, ensure_tournament_format_column
from app.routers.entries import router as entries_router
from app.routers.discord import router as discord_router
from app.routers.screenshot import router as screenshot_router
from app.routers.mtt import router as mtt_router, ensure_mtt_schema
from app.routers.hm3 import router as hm3_router
from app.routers.stats import router as stats_router
from app.routers.equity import router as equity_router
from app.routers.study import router as study_router, ensure_study_schema

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)


def ensure_entries_schema():
    """
    Cria só a tabela entries e as novas colunas de hands.
    Não reaplica o schema inteiro, por isso não volta a rebentar
    com constraints antigas como fk_tournaments_import.
    """
    statements = [
        """
        CREATE TABLE IF NOT EXISTS entries (
            id BIGSERIAL PRIMARY KEY,

            source TEXT NOT NULL,
            entry_type TEXT NOT NULL,

            site TEXT,
            file_name TEXT,
            external_id TEXT,

            raw_text TEXT,
            raw_json JSONB,

            status TEXT NOT NULL DEFAULT 'new',

            notes TEXT,

            import_log_id BIGINT,

            discord_server TEXT,
            discord_channel TEXT,
            discord_message_id TEXT,
            discord_message_url TEXT,
            discord_author TEXT,
            discord_posted_at TIMESTAMPTZ,

            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """,
        "CREATE INDEX IF NOT EXISTS idx_entries_source ON entries(source)",
        "CREATE INDEX IF NOT EXISTS idx_entries_type ON entries(entry_type)",
        "CREATE INDEX IF NOT EXISTS idx_entries_site ON entries(site)",
        "CREATE INDEX IF NOT EXISTS idx_entries_status ON entries(status)",
        "CREATE INDEX IF NOT EXISTS idx_entries_created_at ON entries(created_at DESC)",
        "CREATE INDEX IF NOT EXISTS idx_entries_discord_channel ON entries(discord_server, discord_channel)",
        "CREATE INDEX IF NOT EXISTS idx_entries_external_id ON entries(external_id)",
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uniq_entries_discord_message
        ON entries(discord_message_id)
        WHERE discord_message_id IS NOT NULL
        """,
        """
        ALTER TABLE hands
        ADD COLUMN IF NOT EXISTS entry_id BIGINT
        """,
        """
        ALTER TABLE hands
        ADD COLUMN IF NOT EXISTS study_state TEXT NOT NULL DEFAULT 'new'
        """,
        """
        ALTER TABLE hands
        ADD COLUMN IF NOT EXISTS viewed_at TIMESTAMPTZ
        """,
        """
        ALTER TABLE hands
        ADD COLUMN IF NOT EXISTS studied_at TIMESTAMPTZ
        """,
        """
        ALTER TABLE hands
        ADD COLUMN IF NOT EXISTS confidence_level TEXT
        """,
        """
        ALTER TABLE hands
        ADD COLUMN IF NOT EXISTS screenshot_url TEXT
        """,
        """
        ALTER TABLE hands
        ADD COLUMN IF NOT EXISTS player_names JSONB
        """,
        """
        ALTER TABLE hands
        ADD COLUMN IF NOT EXISTS tournament_id BIGINT
        """,
        "CREATE INDEX IF NOT EXISTS idx_hands_entry_id ON hands(entry_id)",
        "CREATE INDEX IF NOT EXISTS idx_hands_study_state ON hands(study_state)",
        "CREATE INDEX IF NOT EXISTS idx_hands_tournament_id ON hands(tournament_id)",
        # hand_villains universal FK: hand_db_id points to hands.id
        """
        ALTER TABLE hand_villains
        ADD COLUMN IF NOT EXISTS hand_db_id BIGINT
        """,
        "CREATE INDEX IF NOT EXISTS idx_hand_villains_hand_db_id ON hand_villains(hand_db_id)",
        # Make mtt_hand_id nullable for new records that only use hand_db_id
        """
        ALTER TABLE hand_villains
        ALTER COLUMN mtt_hand_id DROP NOT NULL
        """,
    ]

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            for sql in statements:
                try:
                    cur.execute(sql)
                except Exception as e:
                    # Ignorar erros de "already exists" ou constraints
                    conn.rollback()
                    logging.getLogger("schema").warning(f"Schema statement skipped: {e}")
                    continue
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def ensure_discord_sync_table():
    """Cria a tabela de estado de sync do Discord."""
    from app.db import execute
    try:
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
    except Exception as e:
        logging.getLogger("schema").warning(f"discord_sync_state: {e}")


# ── Lifespan (startup + shutdown) ────────────────────────────────────────────

_bot_task = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _bot_task

    # Startup
    ensure_entries_schema()
    ensure_discord_sync_table()
    ensure_mtt_schema()
    ensure_study_schema()
    ensure_hm3_tags_column()
    ensure_has_showdown_column()
    ensure_discord_tags_column()
    ensure_origin_column()
    ensure_buy_in_column()
    ensure_tournament_format_column()

    # Arrancar bot Discord em background
    from app.discord_bot import start_bot, DISCORD_TOKEN, MONITORED_SERVERS
    if DISCORD_TOKEN and MONITORED_SERVERS:
        _bot_task = asyncio.create_task(start_bot())
        logging.getLogger("main").info("Bot Discord a arrancar em background...")
    else:
        logging.getLogger("main").info("Bot Discord desactivado (sem token ou server IDs)")

    yield

    # Shutdown
    from app.discord_bot import stop_bot
    await stop_bot()
    if _bot_task:
        _bot_task.cancel()


app = FastAPI(title="Poker App API", version="0.2.0", lifespan=lifespan)

allowed_origin = os.getenv("ALLOWED_ORIGIN", "http://localhost:5173")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[allowed_origin],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(auth.router)
app.include_router(import_.router)
app.include_router(tournaments.router)
app.include_router(hands.router)
app.include_router(villains.router)
app.include_router(entries_router)
app.include_router(discord_router)
app.include_router(screenshot_router)
app.include_router(mtt_router)
app.include_router(hm3_router)
app.include_router(stats_router)
app.include_router(equity_router)
app.include_router(study_router)

# Serve uploaded screenshots as static files
import os
from fastapi.staticfiles import StaticFiles
os.makedirs("/tmp/poker_screenshots", exist_ok=True)
app.mount("/screenshots", StaticFiles(directory="/tmp/poker_screenshots"), name="screenshots")


@app.get("/")
def root():
    return {"app": "poker-app", "version": "0.2.0"}
