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
from app.services.lobby_vision import apply_ratio_lookup
from app.utils.timezones import utc_to_lisbon_naive

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
        start_time         TIMESTAMP,   -- pt51: Lisboa naive (TS GG é local)
        hero_position      INTEGER,
        hero_payout        NUMERIC(10,2),
        hero_re_entries    INTEGER NOT NULL DEFAULT 0,
        raw_text           TEXT,
        source_filename    TEXT,
        imported_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        PRIMARY KEY (site, tournament_number)
    );
    """
    # B1.x: 12 colunas novas (literais G1-G6 + heuristicas G7-G8 +
    # derivados G9-G10). Idempotente; rows existentes ficam com NULLs
    # ate backfill via re-upload.
    alter_sql = """
    ALTER TABLE tournament_summaries
        ADD COLUMN IF NOT EXISTS game_type                     TEXT,
        ADD COLUMN IF NOT EXISTS buy_in_entry                  NUMERIC(10,2),
        ADD COLUMN IF NOT EXISTS buy_in_rake                   NUMERIC(10,2),
        ADD COLUMN IF NOT EXISTS buy_in_bounty                 NUMERIC(10,2),
        ADD COLUMN IF NOT EXISTS hero_total_received           NUMERIC(10,2),
        ADD COLUMN IF NOT EXISTS hero_finish_phrase_position   INTEGER,
        ADD COLUMN IF NOT EXISTS tournament_modifiers          TEXT[],
        ADD COLUMN IF NOT EXISTS tournament_series             TEXT,
        ADD COLUMN IF NOT EXISTS tournament_speed              TEXT,
        ADD COLUMN IF NOT EXISTS tournament_schedule           TEXT,
        ADD COLUMN IF NOT EXISTS tournament_format             TEXT,
        ADD COLUMN IF NOT EXISTS tournament_pko_ratio          NUMERIC(4,2);
    """
    idx_start = ("CREATE INDEX IF NOT EXISTS idx_tournament_summaries_start_time "
                 "ON tournament_summaries (start_time DESC);")
    idx_name = ("CREATE INDEX IF NOT EXISTS idx_tournament_summaries_name "
                "ON tournament_summaries (tournament_name);")
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(sql)
            cur.execute(alter_sql)
            cur.execute(idx_start)
            cur.execute(idx_name)
        conn.commit()
    finally:
        conn.close()


# ── Parser ────────────────────────────────────────────────────────────

# Cada regex e isolada e tolerante a whitespace. Falhas individuais nao
# cascadeiam — campos opcionais ficam None; obrigatorios levantam.
_RE_TN_AND_NAME = re.compile(
    r"^Tournament\s+#(\d+),\s*(.+?),\s*(.+?)\s*$",
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

# B1.x — extracoes literais novas
_RE_HERO_TOTAL_RECEIVED = re.compile(
    r"received a total of\s*[$€]([\d,]+(?:\.\d+)?)"
)
_RE_FINISH_PHRASE = re.compile(
    r"You finished the tournament in (\d+)(?:st|nd|rd|th) place"
)
_RE_BRACKET = re.compile(r"\[([^\]]+)\]")
_RE_SERIES_PREFIX = re.compile(r"^([A-Z0-9-]+):\s+")


# B1.x — heuristicas (G7 + G8). Ordem importa em overlap.
_SPEED_KEYWORDS = [
    ("speed racer", "Hyper"),  # branded GG (10BB stack); trata como Hyper
    ("hyper",       "Hyper"),
    ("turbo",       "Turbo"),
    ("deepstack",   "Deepstack"),
]

_SCHEDULE_KEYWORDS = [
    ("daily",     "Daily"),
    ("weekly",    "Weekly"),
    ("monthly",   "Monthly"),
    ("sunday",    "Sunday"),
    ("monday",    "Monday"),
    ("tuesday",   "Tuesday"),
    ("wednesday", "Wednesday"),
    ("thursday",  "Thursday"),
    ("friday",    "Friday"),
    ("saturday",  "Saturday"),
]


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


def _split_buy_in_parts(text: str) -> tuple[Optional[Decimal], Optional[Decimal], Optional[Decimal]]:
    """Split dos tokens $X.Y por posicao.

    2 tokens: [entry, rake]                 -> (entry, rake, None)
    3 tokens: [entry, rake, bounty/mystery] -> (entry, rake, bounty)
    Outros (0, 1, 4+): graceful (None, None, None).
    """
    tokens = _RE_BUY_IN_TOKEN.findall(text or "")
    parsed = [_parse_decimal(t) for t in tokens]
    if len(parsed) == 2:
        return (parsed[0], parsed[1], None)
    if len(parsed) == 3:
        return (parsed[0], parsed[1], parsed[2])
    return (None, None, None)


def _detect_speed(name: str) -> str:
    """Heuristica: keyword no nome -> rotulo speed; default 'Slow'."""
    n = (name or "").lower()
    for kw, label in _SPEED_KEYWORDS:
        if kw in n:
            return label
    return "Slow"


def _detect_schedule(name: str) -> Optional[str]:
    """Heuristica: keyword no nome -> rotulo schedule; None se ausente."""
    n = (name or "").lower()
    for kw, label in _SCHEDULE_KEYWORDS:
        if kw in n:
            return label
    return None


def _parse_start_time_naive(s: str) -> Optional[datetime]:
    """Parse '2026/03/31 19:45:00' → datetime NAIVE (sem semântica de fuso). O
    CALLER decide: a TS GG é local de Lisboa → VERBATIM; a TS Winamax traz 'UTC'
    explícito → converter UTC→Lisboa (convenção pt51)."""
    try:
        return datetime.strptime(s.strip(), "%Y/%m/%d %H:%M:%S")
    except ValueError:
        return None


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
    game_type = m_header.group(3).strip()  # B1.x G1: "Hold'em No Limit"

    m_start = _RE_START_TIME.search(text)
    if not m_start:
        raise ValueError(f"missing start_time for tn={tn}")
    # TS GG: hora local de Lisboa → VERBATIM (naive).
    start_time = _parse_start_time_naive(m_start.group(1))
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

    # B1.x G2a/b/c: split do buy-in em entry/rake/bounty
    buy_in_entry, buy_in_rake, buy_in_bounty = _split_buy_in_parts(buy_in_text or "")

    m_players = _RE_TOTAL_PLAYERS.search(text)
    total_players = int(m_players.group(1)) if m_players else None

    m_pool = _RE_PRIZE_POOL.search(text)
    prize_pool = _parse_decimal(m_pool.group(1)) if m_pool else None

    m_hero = _RE_HERO_LINE.search(text)
    hero_position = int(m_hero.group(1)) if m_hero else None
    hero_payout = _parse_decimal(m_hero.group(2)) if m_hero else None

    m_re_entries = _RE_RE_ENTRIES.search(text)
    hero_re_entries = int(m_re_entries.group(1)) if m_re_entries else 0

    # B1.x G3: hero_total_received (cross-check com hero_payout)
    m_total = _RE_HERO_TOTAL_RECEIVED.search(text)
    hero_total_received = _parse_decimal(m_total.group(1)) if m_total else None

    # B1.x G4: hero_finish_phrase_position (audit cross-check com hero_position)
    m_finish = _RE_FINISH_PHRASE.search(text)
    hero_finish_phrase_position = int(m_finish.group(1)) if m_finish else None

    # B1.x G5: tournament_modifiers (lista de tokens em [...]; [] se sem brackets)
    tournament_modifiers = _RE_BRACKET.findall(name)

    # B1.x G6: tournament_series (prefixo antes de ":" no nome; None se ausente)
    m_series = _RE_SERIES_PREFIX.match(name)
    tournament_series = m_series.group(1) if m_series else None

    # B1.x G7+G8: heuristicas
    tournament_speed = _detect_speed(name)
    tournament_schedule = _detect_schedule(name)

    # B1.x G9+G10: derivados via apply_ratio_lookup (lobby_vision)
    bounty_type, pko_ratio = apply_ratio_lookup(name)
    tournament_format = bounty_type            # 'PKO' | 'KO' | 'None'
    tournament_pko_ratio = Decimal(str(pko_ratio)) if pko_ratio > 0 else None

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
        # B1.x — 12 campos novos
        "game_type": game_type,
        "buy_in_entry": buy_in_entry,
        "buy_in_rake": buy_in_rake,
        "buy_in_bounty": buy_in_bounty,
        "hero_total_received": hero_total_received,
        "hero_finish_phrase_position": hero_finish_phrase_position,
        "tournament_modifiers": tournament_modifiers,
        "tournament_series": tournament_series,
        "tournament_speed": tournament_speed,
        "tournament_schedule": tournament_schedule,
        "tournament_format": tournament_format,
        "tournament_pko_ratio": tournament_pko_ratio,
    }


# ── Winamax TS (#WINAMAX-TOURNAMENT-SUMMARIES-PIPELINE) ───────────────────────
# Formato Winamax = linhas etiquetadas, DIFERENTE do GG. Validado contra o
# ZENITH(1102500091) real (backend/tests/fixtures/winamax_ts_zenith.txt).
_WN_HEADER = re.compile(r"Winamax Poker - Tournament summary\s*:\s*(.+?)\((\d+)\)")
_WN_BUYIN = re.compile(r"^Buy-?In\s*:\s*(.+?)\s*$", re.MULTILINE)
_WN_EUR_TOKEN = re.compile(r"(\d+(?:[.,]\d+)?)\s*€")
_WN_PLAYERS = re.compile(r"^Registered players\s*:\s*(\d+)", re.MULTILINE)
_WN_PRIZEPOOL = re.compile(r"^Prizepool\s*:\s*([\d.,]+)\s*€", re.MULTILINE)
_WN_START = re.compile(
    r"^Tournament started\s+(\d{4}/\d{2}/\d{2}\s+\d{2}:\d{2}:\d{2})\s*UTC",
    re.MULTILINE,
)
_WN_FINISH = re.compile(r"You finished in\s+(\d+)(?:st|nd|rd|th)\s+place", re.IGNORECASE)
_WN_WON = re.compile(
    r"You won\s+([\d.,]+)\s*€(?:\s*\+\s*Bounty\s+([\d.,]+)\s*€)?", re.IGNORECASE
)
_WN_TYPE = re.compile(r"^Type\s*:\s*(.+?)\s*$", re.MULTILINE)
_WN_SPEED = re.compile(r"^Speed\s*:\s*(.+?)\s*$", re.MULTILINE)


def _parse_eur(s) -> Optional[Decimal]:
    """Decimal de um valor EUR Winamax (aceita vírgula ou ponto)."""
    if s is None:
        return None
    try:
        return Decimal(str(s).strip().replace(",", "."))
    except InvalidOperation:
        return None


def parse_winamax_tournament_summary(text: str, filename: Optional[str] = None) -> dict:
    """Parseia 1 TS Winamax. Mesma dict-shape do GG (reusa _INSERT_SQL).

    ⚠️ ORDEM do buy-in WN = [entry, bounty, rake] — confirmada via HH (bounty
    por seat = 2º componente). NÃO é a ordem GG [PP, rake, KOP]. 3 componentes
    = KO; 2 = sem bounty (não-KO). tournament_pko_ratio e game_type ficam None
    (decisão: não misturar semântica GG; o split carrega a info real do bounty).
    """
    m_h = _WN_HEADER.search(text)
    if not m_h:
        raise ValueError("missing Winamax TS header")
    name = m_h.group(1).strip()
    tn = m_h.group(2)

    m_s = _WN_START.search(text)
    if not m_s:
        raise ValueError(f"missing start_time for tn={tn}")
    # TS Winamax traz 'UTC' explícito → converter UTC→Lisboa naive (pt51).
    _st = _parse_start_time_naive(m_s.group(1))
    start_time = utc_to_lisbon_naive(_st) if _st is not None else None
    if start_time is None:
        raise ValueError(f"invalid start_time tn={tn}: {m_s.group(1)!r}")

    m_buy = _WN_BUYIN.search(text)
    buy_in_text = m_buy.group(1).strip() if m_buy else None
    comps = [_parse_eur(x) for x in _WN_EUR_TOKEN.findall(buy_in_text or "")]
    entry = bounty = rake = None
    if len(comps) == 3:
        entry, bounty, rake = comps          # [entry, bounty, rake]
    elif len(comps) == 2:
        entry, rake = comps                  # sem bounty (não-KO)
    parts = [c for c in (entry, bounty, rake) if c is not None]
    buy_in_total = sum(parts) if parts else None

    m_pool = _WN_PRIZEPOOL.search(text)
    prize_pool = _parse_eur(m_pool.group(1)) if m_pool else None
    m_pl = _WN_PLAYERS.search(text)
    total_players = int(m_pl.group(1)) if m_pl else None
    m_fin = _WN_FINISH.search(text)
    hero_position = int(m_fin.group(1)) if m_fin else None

    m_won = _WN_WON.search(text)
    hero_payout = _parse_eur(m_won.group(1)) if m_won else None
    hero_bounty = _parse_eur(m_won.group(2)) if (m_won and m_won.group(2)) else None
    if hero_payout is None and hero_bounty is None:
        hero_total_received = None
    else:
        hero_total_received = (hero_payout or Decimal(0)) + (hero_bounty or Decimal(0))

    m_type = _WN_TYPE.search(text)
    type_raw = m_type.group(1).strip().lower() if m_type else ""
    is_ko = ("knockout" in type_raw) or (bounty is not None)
    tournament_format = "PKO" if is_ko else "Vanilla"

    m_speed = _WN_SPEED.search(text)
    # Valor cru Winamax ('normal'/'turbo'/'semiturbo') — NÃO forçar o mapa GG
    # (Slow/Turbo/Hyper) para não introduzir semântica errada ('normal' ≠ slow).
    tournament_speed = m_speed.group(1).strip().lower() if m_speed else None

    return {
        "site": "Winamax",
        "tournament_number": tn,
        "tournament_name": name,
        "buy_in_text": buy_in_text,
        "buy_in_total": buy_in_total,
        "buy_in_currency": "EUR",
        "total_players": total_players,
        "prize_pool": prize_pool,
        "start_time": start_time,
        "hero_position": hero_position,
        "hero_payout": hero_payout,
        "hero_re_entries": 0,
        "raw_text": text,
        "source_filename": filename,
        "game_type": None,
        "buy_in_entry": entry,
        "buy_in_rake": rake,
        "buy_in_bounty": bounty,
        "hero_total_received": hero_total_received,
        "hero_finish_phrase_position": hero_position,
        "tournament_modifiers": [],
        "tournament_series": None,
        "tournament_speed": tournament_speed,
        "tournament_schedule": _detect_schedule(name),
        "tournament_format": tournament_format,
        "tournament_pko_ratio": None,
    }


def _parse_ts_by_site(text: str, filename: Optional[str] = None) -> dict:
    """Despacha o TS para o parser certo por sniff de conteúdo. Default GG
    (caminho legacy intocado)."""
    if text.lstrip().startswith("Winamax Poker"):
        return parse_winamax_tournament_summary(text, filename)
    return parse_tournament_summary(text, filename)


# ── Endpoint ──────────────────────────────────────────────────────────

_INSERT_SQL = """
INSERT INTO tournament_summaries (
    site, tournament_number, tournament_name,
    buy_in_text, buy_in_total, buy_in_currency,
    total_players, prize_pool, start_time,
    hero_position, hero_payout, hero_re_entries,
    raw_text, source_filename,
    game_type, buy_in_entry, buy_in_rake, buy_in_bounty,
    hero_total_received, hero_finish_phrase_position,
    tournament_modifiers, tournament_series,
    tournament_speed, tournament_schedule,
    tournament_format, tournament_pko_ratio
) VALUES (
    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
)
ON CONFLICT (site, tournament_number) DO UPDATE SET
    tournament_name             = EXCLUDED.tournament_name,
    buy_in_text                 = EXCLUDED.buy_in_text,
    buy_in_total                = EXCLUDED.buy_in_total,
    buy_in_currency             = EXCLUDED.buy_in_currency,
    total_players               = EXCLUDED.total_players,
    prize_pool                  = EXCLUDED.prize_pool,
    start_time                  = EXCLUDED.start_time,
    hero_position               = EXCLUDED.hero_position,
    hero_payout                 = EXCLUDED.hero_payout,
    hero_re_entries             = EXCLUDED.hero_re_entries,
    raw_text                    = EXCLUDED.raw_text,
    source_filename             = EXCLUDED.source_filename,
    game_type                   = EXCLUDED.game_type,
    buy_in_entry                = EXCLUDED.buy_in_entry,
    buy_in_rake                 = EXCLUDED.buy_in_rake,
    buy_in_bounty               = EXCLUDED.buy_in_bounty,
    hero_total_received         = EXCLUDED.hero_total_received,
    hero_finish_phrase_position = EXCLUDED.hero_finish_phrase_position,
    tournament_modifiers        = EXCLUDED.tournament_modifiers,
    tournament_series           = EXCLUDED.tournament_series,
    tournament_speed            = EXCLUDED.tournament_speed,
    tournament_schedule         = EXCLUDED.tournament_schedule,
    tournament_format           = EXCLUDED.tournament_format,
    tournament_pko_ratio        = EXCLUDED.tournament_pko_ratio,
    imported_at                 = NOW()
RETURNING (xmax = 0) AS inserted
"""


@router.post("/import")
async def import_tournament_summaries(
    file: UploadFile = File(...),
    current_user=Depends(require_auth),
):
    """Aceita .txt (single) ou .zip (batch). GG + Winamax (dispatch por
    conteúdo em _parse_ts_by_site).

    Resposta:
      {total, inserted, updated, skipped_pre_2026, failed: [{filename, error}]}

    Parse failure num TS NÃO aborta batch (registado em failed). DB error
    num row faz ROLLBACK TO SAVEPOINT (rebobina só a row); inserts
    anteriores ficam preservados até ao commit final.
    """
    content = await file.read()
    filename = file.filename or "upload"
    try:
        files = _extract_txt_files(content, filename)
    except zipfile.BadZipFile:
        raise HTTPException(400, "ZIP corrompido")
    result = persist_tournament_summaries(files)

    # ── Trigger reconcile de lobbys pendentes (tm_not_found/tm_ambiguous) ──
    # Os TS recém-importados (TIER 0) podem tornar resolvível um lobby que ficou
    # por resolver. Re-corre o resolver sobre o vision_json guardado e escreve o
    # payout (precedência respeitada). Sem Vision; idempotente. Fire-and-forget.
    import asyncio
    from app.services.lobby_sync import reconcile_lobby_logs

    async def _lobby_reconcile_async():
        try:
            res = await asyncio.to_thread(reconcile_lobby_logs)
            logger.info(
                "[ts_import] lobby reconcile: resolved=%d written=%d skipped_prec=%d "
                "still=%d (scanned=%d)",
                res["resolved"], res["written"], res["skipped_precedence"],
                res["still_unresolved"], res["scanned"],
            )
        except Exception as exc:
            logger.error(f"[ts_import] lobby reconcile falhou: {exc}")

    asyncio.create_task(_lobby_reconcile_async())
    return result


def _extract_txt_files(content: bytes, filename: str) -> list[tuple[str, bytes]]:
    """Extrai (name, bytes) dos .txt de um .zip ou de um único .txt. Partilhado
    pelo handler HTTP e por /api/import (anti-drift). Raises HTTPException(400)
    para formato não suportado; BadZipFile propaga para o caller tratar."""
    lower = (filename or "upload").lower()
    if lower.endswith(".zip"):
        with zipfile.ZipFile(io.BytesIO(content)) as zf:
            return [
                (name, zf.read(name))
                for name in zf.namelist()
                if name.lower().endswith(".txt")
            ]
    if lower.endswith(".txt"):
        return [(filename, content)]
    raise HTTPException(400, "Formato nao suportado (use .txt ou .zip)")


def persist_tournament_summaries(files: list[tuple[str, bytes]]) -> dict:
    """Núcleo operacional: parse + upsert em tournament_summaries (GG-only).
    Gere a própria conn/txn (SAVEPOINT por row). Consumido pelo handler HTTP
    `/api/tournament-summaries/import` e por `/api/import` (TS detectado num
    ZIP largado no ImportModal — #IMPORT-MODAL-MISROUTES-TS-RESULTS).
    Devolve {total, inserted, updated, skipped_pre_2026, failed}."""
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
                    parsed = _parse_ts_by_site(text, name)
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
                            parsed["game_type"],
                            parsed["buy_in_entry"], parsed["buy_in_rake"], parsed["buy_in_bounty"],
                            parsed["hero_total_received"],
                            parsed["hero_finish_phrase_position"],
                            parsed["tournament_modifiers"],
                            parsed["tournament_series"],
                            parsed["tournament_speed"],
                            parsed["tournament_schedule"],
                            parsed["tournament_format"],
                            parsed["tournament_pko_ratio"],
                        ),
                    )
                    row = cur.fetchone()
                    if row["inserted"]:
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
