-- poker-app schema
-- Executar: psql -U pokerapp -d pokerdb -f schema.sql

CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ── USERS ────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS users (
    id          SERIAL PRIMARY KEY,
    email       TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ── TOURNAMENTS ──────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS tournaments (
    id          SERIAL PRIMARY KEY,
    site        TEXT NOT NULL CHECK (site IN ('Winamax','GGPoker','PokerStars','WPN')),
    tid         TEXT,                          -- ID externo da sala (vazio no GGPoker)
    name        TEXT NOT NULL,
    date        DATE NOT NULL,
    buyin       NUMERIC(10,2) NOT NULL DEFAULT 0,
    cashout     NUMERIC(10,2) NOT NULL DEFAULT 0,
    result      NUMERIC(10,2) GENERATED ALWAYS AS (cashout - buyin) STORED,
    position    INTEGER,
    players     INTEGER,
    type        TEXT NOT NULL CHECK (type IN ('ko','nonko')),
    speed       TEXT NOT NULL CHECK (speed IN ('normal','turbo','hyper')),
    currency    TEXT NOT NULL CHECK (currency IN ('€','$')),
    import_id   INTEGER,                       -- FK para import_logs
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
    -- deduplicação: ver índices abaixo

CREATE INDEX IF NOT EXISTS idx_tournaments_site  ON tournaments(site);
CREATE INDEX IF NOT EXISTS idx_tournaments_date  ON tournaments(date);
CREATE INDEX IF NOT EXISTS idx_tournaments_type  ON tournaments(type);
CREATE INDEX IF NOT EXISTS idx_tournaments_speed ON tournaments(speed);

-- Deduplicação no re-import:
-- Winamax / Stars / WPN têm tid real → chave é (site, tid, date)
CREATE UNIQUE INDEX IF NOT EXISTS uniq_tournaments_with_tid
    ON tournaments (site, tid, date)
    WHERE tid IS NOT NULL AND tid != '';

-- GGPoker não tem tid fiável → usa (site, name, date, buyin, position)
-- position distingue re-entries no mesmo torneio
CREATE UNIQUE INDEX IF NOT EXISTS uniq_tournaments_no_tid
    ON tournaments (site, name, date, buyin, position)
    WHERE tid IS NULL OR tid = '';

-- ── HANDS ─────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS hands (
    id          SERIAL PRIMARY KEY,
    site        TEXT,
    hand_id     TEXT UNIQUE,
    played_at   TIMESTAMPTZ,
    stakes      TEXT,
    position    TEXT,
    hero_cards  TEXT[],
    board       TEXT[],
    result      NUMERIC(10,2),
    currency    TEXT,
    notes       TEXT,
    tags         TEXT[],
    discord_tags TEXT[] DEFAULT ARRAY[]::text[],  -- canais Discord onde a mão foi partilhada (ex: 'nota')
    origin       TEXT,                            -- fonte: 'hm3' | 'discord' | 'ss_upload' | 'hh_import'
    buy_in       NUMERIC(10,2),                   -- buy-in do torneio (unidades da moeda; NULL se desconhecido)
    raw          TEXT,                          -- HH original
    import_id    INTEGER,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_hands_played_at ON hands(played_at);
CREATE INDEX IF NOT EXISTS idx_hands_tags ON hands USING GIN(tags);
CREATE INDEX IF NOT EXISTS idx_hands_discord_tags ON hands USING GIN(discord_tags);
CREATE INDEX IF NOT EXISTS idx_hands_origin ON hands(origin);

-- ── VILLAIN_NOTES ────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS villain_notes (
    id          SERIAL PRIMARY KEY,
    site        TEXT,
    nick        TEXT NOT NULL,
    note        TEXT,
    tags        TEXT[],
    hands_seen  INTEGER DEFAULT 0,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (site, nick)
);

CREATE INDEX IF NOT EXISTS idx_villain_nick ON villain_notes(nick);

-- ── IMPORT_LOGS ──────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS import_logs (
    id              SERIAL PRIMARY KEY,
    site            TEXT,
    filename        TEXT,
    status          TEXT NOT NULL CHECK (status IN ('ok','partial','error')),
    records_ok      INTEGER DEFAULT 0,
    records_skipped INTEGER DEFAULT 0,
    records_error   INTEGER DEFAULT 0,
    records_found   INTEGER DEFAULT 0,
    log             TEXT,
    imported_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- FK deferred para evitar problemas na ordem de inserção
ALTER TABLE tournaments
    ADD CONSTRAINT fk_tournaments_import
    FOREIGN KEY (import_id) REFERENCES import_logs(id)
    ON DELETE SET NULL
    DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE hands
    ADD CONSTRAINT fk_hands_import
    FOREIGN KEY (import_id) REFERENCES import_logs(id)
    ON DELETE SET NULL
    DEFERRABLE INITIALLY DEFERRED;

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
);

CREATE INDEX IF NOT EXISTS idx_entries_source ON entries(source);
CREATE INDEX IF NOT EXISTS idx_entries_type ON entries(entry_type);
CREATE INDEX IF NOT EXISTS idx_entries_site ON entries(site);
CREATE INDEX IF NOT EXISTS idx_entries_status ON entries(status);
CREATE INDEX IF NOT EXISTS idx_entries_created_at ON entries(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_entries_discord_channel ON entries(discord_server, discord_channel);
CREATE INDEX IF NOT EXISTS idx_entries_external_id ON entries(external_id);

CREATE UNIQUE INDEX IF NOT EXISTS uniq_entries_discord_message
    ON entries(discord_message_id)
    WHERE discord_message_id IS NOT NULL;

ALTER TABLE hands
ADD COLUMN IF NOT EXISTS entry_id BIGINT REFERENCES entries(id) ON DELETE SET NULL;

ALTER TABLE hands
ADD COLUMN IF NOT EXISTS study_state TEXT NOT NULL DEFAULT 'new' CHECK (
    study_state IN ('new', 'review', 'studying', 'resolved')
);

ALTER TABLE hands
ADD COLUMN IF NOT EXISTS viewed_at TIMESTAMPTZ;

ALTER TABLE hands
ADD COLUMN IF NOT EXISTS studied_at TIMESTAMPTZ;

ALTER TABLE hands
ADD COLUMN IF NOT EXISTS confidence_level TEXT CHECK (
    confidence_level IN ('high', 'medium', 'low', 'inferred')
);

CREATE INDEX IF NOT EXISTS idx_hands_entry_id ON hands(entry_id);
CREATE INDEX IF NOT EXISTS idx_hands_study_state ON hands(study_state);
