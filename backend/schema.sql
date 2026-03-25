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
    tags        TEXT[],
    raw         TEXT,                          -- HH original
    import_id   INTEGER,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_hands_played_at ON hands(played_at);
CREATE INDEX IF NOT EXISTS idx_hands_tags ON hands USING GIN(tags);

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
