import os
import asyncio
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from app.db import get_conn
from app.routers import health, auth, import_, tournaments, hands, villains
from app.routers.hands import (
    ensure_hm3_tags_column, ensure_has_showdown_column, ensure_discord_tags_column,
    ensure_origin_column, ensure_buy_in_column, ensure_tournament_format_column,
    ensure_tournament_name_and_number_columns, ensure_hand_attachments_schema,
    ensure_study_state_check_constraint, ensure_context_table_ss_column,
)
from app.routers.entries import router as entries_router
from app.routers.discord import router as discord_router
from app.routers.screenshot import router as screenshot_router
from app.routers.mtt import router as mtt_router, ensure_mtt_schema
from app.routers.hm3 import router as hm3_router
from app.routers.stats import router as stats_router
from app.routers.equity import router as equity_router
from app.routers.study import router as study_router, ensure_study_schema
from app.routers.attachments import router as attachments_router
from app.routers.images import router as images_router
from app.routers.gto import router as gto_router
from app.routers.tournaments_meta import router as tournaments_meta_router
from app.services.tournament_meta import ensure_tournaments_meta_schema
from app.routers.payouts import (
    router as payouts_router,
    ensure_tournament_payouts_schema,
)
from app.routers.tournament_summaries import (
    router as tournament_summaries_router,
    ensure_tournament_summaries_schema,
)
from app.routers.queue import router as queue_router
from app.routers.lobbys import router as lobbys_router
from app.routers.import_health import router as import_health_router
from app.services.lobby_sync import ensure_lobby_processing_log_schema
from app.services.hrc_jobs import ensure_hrc_jobs_schema
from app.services.ft_boundary import ensure_ft_boundary_review_schema
from app.routers.tournament_results import router as tournament_results_router
from app.routers.hrc import router as hrc_router, ensure_hrc_schema
from app.routers.hrc_results import router as hrc_results_router, ensure_hrc_results_schema
from app.routers.table_ss import (
    router as table_ss_router,
    ensure_table_ss_processing_log_schema,
)
from app.routers.suspicious import router as suspicious_router
from app.routers.gg_health import router as gg_health_router
from app.routers.capture_triage import (
    router as capture_triage_router,
    ensure_capture_triage_column,
)

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
            discord_posted_at TIMESTAMP,   -- pt51: Lisboa naive (convertido de UTC)

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
        # #ORFA-HM3-SYNTHETIC-ENTRIES Peça 1: idempotência hm3_synthetic.
        # Re-runs do .bat HM3 nao acumulam entries: ON CONFLICT DO NOTHING
        # em create_entry usa este index. Parcial (apenas WHERE source='hm3_synthetic')
        # para nao colidir com entries Discord/screenshot reais que podem ter
        # external_id colisivel.
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uniq_entries_hm3_synthetic_external
        ON entries(external_id)
        WHERE source = 'hm3_synthetic' AND external_id IS NOT NULL
        """,
        # #ORFA-HM3-SYNTHETIC-ENTRIES fix retroactivo: permitir 'hm3_synthetic'
        # no CHECK entries_source_check. Peça 1 introduziu o source mas o CHECK
        # ficou stale em prod — importer HM3 e backfill batiam em CheckViolation.
        # Preserva a lista actual de prod (inclui 'discord_bot', 'import',
        # 'screenshot' adicionados por migrações anteriores) + 'hm3_synthetic'.
        """
        ALTER TABLE entries DROP CONSTRAINT IF EXISTS entries_source_check
        """,
        """
        ALTER TABLE entries ADD CONSTRAINT entries_source_check
            CHECK (source IN (
                'discord', 'discord_bot', 'hm', 'gg_backoffice', 'hh_text',
                'summary', 'report', 'manual', 'import', 'screenshot',
                'hm3_synthetic'
            ))
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
        # Flag setada por _parse_hand (hm3.py) quando nao consegue deduzir BTN
        # nem via dedução por blinds nem via raw "Seat #X is the button". A mao
        # e importada na mesma (all_players esqueletico, so nicks). Default FALSE
        # preserva maos existentes como "parse OK" ate backfill explicito.
        """
        ALTER TABLE hands
        ADD COLUMN IF NOT EXISTS position_parse_failed BOOLEAN DEFAULT FALSE
        """,
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
        # Tech Debt #4: categoria + UNIQUE composto (hand_db_id, player_name, category).
        # 'sd' = showdown match SS↔HH valido + has_showdown + cards (regra B).
        # 'nota' = hm3_tags ~ 'nota%' (regra A) ou discord_tags ⊇ 'nota' + match real (regra C).
        # 'friend' = villain_nick em FRIEND_HEROES (regra D — Karluz/flightrisk).
        # Mesma mao+villain pode ter multiplas categorias (rows separados) — UNIQUE antigo
        # (hand_db_id, player_name) seria violado; substituido pelo composto + DROP.
        """
        ALTER TABLE hand_villains
        ADD COLUMN IF NOT EXISTS category TEXT NOT NULL DEFAULT 'sd'
        """,
        """
        DO $$ BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'hand_villains_category_check') THEN
                ALTER TABLE hand_villains ADD CONSTRAINT hand_villains_category_check
                    CHECK (category IN ('sd', 'nota', 'friend'));
            END IF;
        END $$
        """,
        "DROP INDEX IF EXISTS uq_hand_villains_hand_db_player",
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_hand_villains_hand_db_player_cat
            ON hand_villains(hand_db_id, player_name, category)
            WHERE hand_db_id IS NOT NULL
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
    ensure_tournament_name_and_number_columns()
    ensure_hand_attachments_schema()
    ensure_tournaments_meta_schema()
    ensure_tournament_payouts_schema()
    ensure_tournament_summaries_schema()
    ensure_lobby_processing_log_schema()
    ensure_table_ss_processing_log_schema()
    ensure_context_table_ss_column()
    ensure_capture_triage_column()
    ensure_hrc_jobs_schema()
    ensure_hrc_results_schema()
    ensure_ft_boundary_review_schema()
    from app.services.name_propagation import ensure_name_quarantine_schema
    ensure_name_quarantine_schema()
    ensure_hrc_schema()
    from app.routers.queue import ensure_hrc_queue_release_schema
    ensure_hrc_queue_release_schema()
    ensure_study_state_check_constraint()

    # Varredor independente de pendentes (#PENDING-SWEEP-GUARANTEED) — re-casa SS/
    # lobbys pendentes + re-Vision das SS falhadas, no arranque + tick periódico,
    # desacoplado do request de import (que pode dar timeout antes do seu trigger).
    from app.services.lobby_sync import start_pending_sweeper
    start_pending_sweeper()

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
app.include_router(attachments_router)
app.include_router(images_router)
app.include_router(gto_router)
app.include_router(tournaments_meta_router)
app.include_router(payouts_router)
app.include_router(tournament_summaries_router)
app.include_router(queue_router)
app.include_router(lobbys_router)
app.include_router(tournament_results_router)
app.include_router(hrc_router)
app.include_router(hrc_results_router)
app.include_router(table_ss_router)
app.include_router(import_health_router)
app.include_router(capture_triage_router)
app.include_router(suspicious_router)
app.include_router(gg_health_router)

# Serve uploaded screenshots as static files
import os
from fastapi.staticfiles import StaticFiles
os.makedirs("/tmp/poker_screenshots", exist_ok=True)
app.mount("/screenshots", StaticFiles(directory="/tmp/poker_screenshots"), name="screenshots")


@app.get("/")
def root():
    # `sizing_rules` exposto publicamente p/ confirmar qual a LEI de sizing que
    # o backend escreve neste deploy (etiqueta dos zips HRC). Read-only, inócuo.
    from app.services.queue_export import SIZING_RULES_VERSION
    return {"app": "poker-app", "version": "0.2.0",
            "sizing_rules": SIZING_RULES_VERSION}
