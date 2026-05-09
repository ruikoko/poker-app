"""Import de Tournament Summaries da GGPoker (FASE B B1).

GG gera ficheiros TS quando torneios terminam, com tournament_number
explicito no header. Para torneios ja terminados, isto e fonte
autoritativa do tn — sem ambiguidade dos lobbys ou raw HH.

Schema: 1 row per (site, tournament_number). UPSERT idempotente.
B1 e GG-only — site hard-coded a 'GGPoker'.
"""
from __future__ import annotations
import io
import re
import zipfile
import logging
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Optional

from fastapi import APIRouter, UploadFile, File, Depends, HTTPException

from app.auth import require_auth
from app.db import get_conn
from app.ingest_filters import is_pre_2026

router = APIRouter(prefix="/api/tournament-summaries", tags=["tournament-summaries"])
logger = logging.getLogger("tournament_summaries")


# ── Schema ────────────────────────────────────────────────────────────

def ensure_tournament_summaries_schema():
    """Idempotente. Chamada no lifespan."""
    sql = """
    CREATE TABLE IF NOT EXISTS tournament_summaries (
        site               TEXT NOT NULL,
        tournament_number  TEXT NOT NULL,
        tournament_name    TEXT,
        buy_in_text        TEXT,
        buy_in_total       NUMERIC(10,2),
        buy_in_currency    TEXT,
        total_players      INTEGER,
        prize_pool         NUMERIC(12,2),
        start_time         TIMESTAMPTZ,
        hero_position      INTEGER,
        hero_payout        NUMERIC(10,2),
        hero_re_entries    INTEGER NOT NULL DEFAULT 0,
        raw_text           TEXT,
        source_filename    TEXT,
        imported_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        PRIMARY KEY (site, tournament_number)
    );
    """
    idx_start = ("CREATE INDEX IF NOT EXISTS idx_tournament_summaries_start_time "
                 "ON tournament_summaries (start_time DESC);")
    idx_name = ("CREATE INDEX IF NOT EXISTS idx_tournament_summaries_name "
                "ON tournament_summaries (tournament_name);")
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(sql)
            cur.execute(idx_start)
            cur.execute(idx_name)
        conn.commit()
    finally:
        conn.close()


# ── Parser ────────────────────────────────────────────────────────────

# Cada regex e isolada e tolerante a whitespace. Falhas individuais nao
# cascadeiam — campos opcionais ficam None; obrigatorios levantam.
_RE_TN_AND_NAME = re.compile(
    r"^Tournament\s+#(\d+),\s*(.+?),\s*Hold'em",
    re.MULTILINE,
)
_RE_BUY_IN = re.compile(r"^Buy-in:\s*(.+?)\s*$", re.MULTILINE)
_RE_TOTAL_PLAYERS = re.compile(r"^(\d+)\s+Players\s*$", re.MULTILINE)
_RE_PRIZE_POOL = re.compile(r"^Total Prize Pool:\s*[$€]([\d,\.]+)", re.MULTILINE)
_RE_START_TIME = re.compile(
    r"^Tournament started\s+(\d{4}/\d{2}/\d{2}\s+\d{2}:\d{2}:\d{2})",
    re.MULTILINE,
)
_RE_HERO_LINE = re.compile(
    r"^(\d+)(?:st|nd|rd|th)\s*:\s*Hero,\s*[$€]([\d,\.]+)",
    re.MULTILINE,
)
_RE_RE_ENTRIES = re.compile(r"You made\s+(\d+)\s+re-entries")

_RE_BUY_IN_TOKEN = re.compile(r"\$([\d,]+(?:\.\d+)?)")
_EUR_HINT = re.compile(r"€")


def _parse_decimal(s: Optional[str]) -> Optional[Decimal]:
    """Strip vírgulas de milhares + Decimal. None em InvalidOperation."""
    if s is None:
        return None
    cleaned = s.replace(",", "").strip()
    try:
        return Decimal(cleaned)
    except InvalidOperation:
        return None


def _parse_buy_in(text: str) -> tuple[Optional[Decimal], Optional[str]]:
    """Soma todos os tokens $X.Y do texto (vanilla 2 partes / PKO 3 partes /
    Mystery 3 partes). Devolve (total, currency).

    Ex: "$73.6+$6.4"        -> (Decimal("80.0"), "USD")
        "$40.96+$7.04+$40"  -> (Decimal("88.00"), "USD")
        "Free"              -> (None, None)
    """
    tokens = _RE_BUY_IN_TOKEN.findall(text or "")
    if not tokens:
        return (None, None)
    total = Decimal(0)
    for t in tokens:
        d = _parse_decimal(t)
        if d is not None:
            total += d
    if total == 0:
        return (None, None)
    currency = "EUR" if _EUR_HINT.search(text) else "USD"
    return (total, currency)


def _parse_start_time_utc(s: str) -> Optional[datetime]:
    """Parse '2026/03/31 19:45:00' como UTC.

    Convenção: TS GG não indica timezone explícito. Assumimos UTC (consistente
    com o parser de raw HH GG). Smoke real (B2) cruza start_time com
    MIN(played_at) das hands do mesmo TM para confirmar.
    """
    try:
        dt = datetime.strptime(s.strip(), "%Y/%m/%d %H:%M:%S")
    except ValueError:
        return None
    return dt.replace(tzinfo=timezone.utc)


def parse_tournament_summary(text: str, filename: Optional[str] = None) -> dict:
    """Parseia 1 ficheiro TS GG.

    Levanta ValueError se tournament_number ou start_time ausentes/inválidos.
    Restantes campos None se ausentes.
    """
    m_header = _RE_TN_AND_NAME.search(text)
    if not m_header:
        raise ValueError("missing tournament_number / header malformed")
    tn = m_header.group(1)
    name = m_header.group(2).strip()

    m_start = _RE_START_TIME.search(text)
    if not m_start:
        raise ValueError(f"missing start_time for tn={tn}")
    start_time = _parse_start_time_utc(m_start.group(1))
    if start_time is None:
        raise ValueError(f"invalid start_time for tn={tn}: {m_start.group(1)!r}")

    m_buyin = _RE_BUY_IN.search(text)
    buy_in_text = m_buyin.group(1).strip() if m_buyin else None
    buy_in_total, buy_in_currency = _parse_buy_in(buy_in_text or "")
    # GG default: 'USD' aplicado mesmo se buy-in inteiro ausente (Free, ticket-only).
    # B1 e GG-only; quando expandirmos para Winamax/PS este default cai e infere-se
    # do site.
    if buy_in_currency is None:
        buy_in_currency = "USD"

    m_players = _RE_TOTAL_PLAYERS.search(text)
    total_players = int(m_players.group(1)) if m_players else None

    m_pool = _RE_PRIZE_POOL.search(text)
    prize_pool = _parse_decimal(m_pool.group(1)) if m_pool else None

    m_hero = _RE_HERO_LINE.search(text)
    hero_position = int(m_hero.group(1)) if m_hero else None
    hero_payout = _parse_decimal(m_hero.group(2)) if m_hero else None

    m_re_entries = _RE_RE_ENTRIES.search(text)
    hero_re_entries = int(m_re_entries.group(1)) if m_re_entries else 0

    return {
        "site": "GGPoker",
        "tournament_number": tn,
        "tournament_name": name,
        "buy_in_text": buy_in_text,
        "buy_in_total": buy_in_total,
        "buy_in_currency": buy_in_currency,
        "total_players": total_players,
        "prize_pool": prize_pool,
        "start_time": start_time,
        "hero_position": hero_position,
        "hero_payout": hero_payout,
        "hero_re_entries": hero_re_entries,
        "raw_text": text,
        "source_filename": filename,
    }


# ── Endpoint ──────────────────────────────────────────────────────────

_INSERT_SQL = """
INSERT INTO tournament_summaries (
    site, tournament_number, tournament_name,
    buy_in_text, buy_in_total, buy_in_currency,
    total_players, prize_pool, start_time,
    hero_position, hero_payout, hero_re_entries,
    raw_text, source_filename
) VALUES (
    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
)
ON CONFLICT (site, tournament_number) DO UPDATE SET
    tournament_name   = EXCLUDED.tournament_name,
    buy_in_text       = EXCLUDED.buy_in_text,
    buy_in_total      = EXCLUDED.buy_in_total,
    buy_in_currency   = EXCLUDED.buy_in_currency,
    total_players     = EXCLUDED.total_players,
    prize_pool        = EXCLUDED.prize_pool,
    start_time        = EXCLUDED.start_time,
    hero_position     = EXCLUDED.hero_position,
    hero_payout       = EXCLUDED.hero_payout,
    hero_re_entries   = EXCLUDED.hero_re_entries,
    raw_text          = EXCLUDED.raw_text,
    source_filename   = EXCLUDED.source_filename,
    imported_at       = NOW()
RETURNING (xmax = 0) AS inserted
"""


@router.post("/import")
async def import_tournament_summaries(
    file: UploadFile = File(...),
    current_user=Depends(require_auth),
):
    """Aceita .txt (single) ou .zip (batch). GG-only.

    Resposta:
      {total, inserted, updated, skipped_pre_2026, failed: [{filename, error}]}

    Parse failure num TS NÃO aborta batch (registado em failed). DB error
    num row faz ROLLBACK TO SAVEPOINT (rebobina só a row); inserts
    anteriores ficam preservados até ao commit final.
    """
    content = await file.read()
    filename = file.filename or "upload"
    lower = filename.lower()

    if lower.endswith(".zip"):
        try:
            with zipfile.ZipFile(io.BytesIO(content)) as zf:
                files = [
                    (name, zf.read(name))
                    for name in zf.namelist()
                    if name.lower().endswith(".txt")
                ]
        except zipfile.BadZipFile:
            raise HTTPException(400, "ZIP corrompido")
    elif lower.endswith(".txt"):
        files = [(filename, content)]
    else:
        raise HTTPException(400, "Formato nao suportado (use .txt ou .zip)")

    stats: dict = {
        "total": len(files),
        "inserted": 0,
        "updated": 0,
        "skipped_pre_2026": 0,
        "failed": [],
    }

    if not files:
        return stats

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            for name, raw_bytes in files:
                try:
                    text = raw_bytes.decode("utf-8", errors="replace")
                    parsed = parse_tournament_summary(text, name)
                except ValueError as e:
                    stats["failed"].append({"filename": name, "error": str(e)})
                    continue

                if is_pre_2026(parsed["start_time"]):
                    stats["skipped_pre_2026"] += 1
                    continue

                cur.execute("SAVEPOINT row_sp")
                try:
                    cur.execute(
                        _INSERT_SQL,
                        (
                            parsed["site"], parsed["tournament_number"], parsed["tournament_name"],
                            parsed["buy_in_text"], parsed["buy_in_total"], parsed["buy_in_currency"],
                            parsed["total_players"], parsed["prize_pool"], parsed["start_time"],
                            parsed["hero_position"], parsed["hero_payout"], parsed["hero_re_entries"],
                            parsed["raw_text"], parsed["source_filename"],
                        ),
                    )
                    row = cur.fetchone()
                    if row[0]:
                        stats["inserted"] += 1
                    else:
                        stats["updated"] += 1
                    cur.execute("RELEASE SAVEPOINT row_sp")
                except Exception as e:
                    cur.execute("ROLLBACK TO SAVEPOINT row_sp")
                    logger.exception(
                        f"[ts_import] db error tn={parsed['tournament_number']} "
                        f"type={type(e).__name__} repr={e!r} args={e.args!r}"
                    )
                    stats["failed"].append(
                        {"filename": name, "error": f"db: {type(e).__name__}: {e!r}"}
                    )
                    continue
        conn.commit()
    finally:
        conn.close()

    return stats
