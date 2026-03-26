import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from app.db import get_conn
from app.routers import health, auth, import_, tournaments, hands, villains
from app.routers.entries import router as entries_router

load_dotenv()

app = FastAPI(title="Poker App API", version="0.1.0")

allowed_origin = os.getenv("ALLOWED_ORIGIN", "http://localhost:5173")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[allowed_origin],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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

            source TEXT NOT NULL CHECK (
                source IN (
                    'discord',
                    'hm',
                    'gg_backoffice',
                    'hh_text',
                    'summary',
                    'report',
                    'manual'
                )
            ),

            entry_type TEXT NOT NULL CHECK (
                entry_type IN (
                    'hand_history',
                    'tournament_summary',
                    'tabular_report',
                    'image',
                    'replayer_link',
                    'note',
                    'text'
                )
            ),

            site TEXT,
            file_name TEXT,
            external_id TEXT,

            raw_text TEXT,
            raw_json JSONB,

            status TEXT NOT NULL DEFAULT 'new' CHECK (
                status IN ('new', 'processed', 'partial', 'failed', 'archived')
            ),

            notes TEXT,

            import_log_id BIGINT REFERENCES import_logs(id) ON DELETE SET NULL,

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
        ADD COLUMN IF NOT EXISTS entry_id BIGINT REFERENCES entries(id) ON DELETE SET NULL
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
        "CREATE INDEX IF NOT EXISTS idx_hands_entry_id ON hands(entry_id)",
        "CREATE INDEX IF NOT EXISTS idx_hands_study_state ON hands(study_state)",
    ]

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            for sql in statements:
                cur.execute(sql)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


@app.on_event("startup")
def startup_event():
    ensure_entries_schema()


app.include_router(health.router)
app.include_router(auth.router)
app.include_router(import_.router)
app.include_router(tournaments.router)
app.include_router(hands.router)
app.include_router(villains.router)
app.include_router(entries_router)


@app.get("/")
def root():
    return {"app": "poker-app", "version": "0.1.0"}
