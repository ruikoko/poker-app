"""Pipeline SS de mesa (pt38 Fase A).

POST /api/table-ss/upload  — multipart: imagem (PNG/JPG) + metadata opcional.
GET  /api/table-ss/recent  — últimas SSs processadas (para o painel UI da Fase B).

Pipeline (mirror de services/lobby_sync.process_lobby_message, mas a fonte é a
SS da MESA e o destino é ligar `players_left` granular à mão concreta):

  dedup(file_hash) → Vision Sonnet → site gate → MATCH temporal mão→resolver
  → UPSERT table_ss_processing_log (+ atomic UPDATE hands.context_table_ss_id).

Match (decisão pt38, Web): match temporal directo à mão PRIMEIRO; o
resolver-por-nome só desambigua quando há mãos de >1 torneio na janela
(multi-tabling). Janela ±5 min (TABLE_SS_MATCH_WINDOW_S). captured_at do
filename em TZ Europe/Lisbon (configurável) → UTC.

Alvo: #HRC-MTT-STACKS-PAGE-SKIPPED-ON-NULL-PLAYERS-LEFT.
"""
from __future__ import annotations

import hashlib
import logging
import os
import re
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Body, Depends, File, Form, HTTPException, Query, Response, UploadFile

from app.auth import require_auth, require_auth_or_api_key
from app.db import get_conn, query
from app.services.image_utils import detect_image_mime, compress_image
from app.services import table_ss_vision as tv
from app.services.tournament_resolver import (
    resolve_tournament_number, name_tokens_subset, clean_winamax_tournament_name,
)

router = APIRouter(prefix="/api/table-ss", tags=["table-ss"])
logger = logging.getLogger("table_ss")

# Janela do match temporal SS↔mão. pt38: ±5 min (ajuste do Web sobre os ±2 min
# do esboço).
TABLE_SS_MATCH_WINDOW_S = 300
# TZ assumida para o timestamp do filename (hora local de captura).
CAPTURE_TZ = os.getenv("TABLE_SS_CAPTURE_TZ", "Europe/Lisbon")

ALLOWED_SITES = {"GGPoker", "PokerStars", "Winamax", "WPN"}
_VALID_RESULTS = frozenset({
    "success", "vision_failed", "json_invalid", "site_undetected",
    "tm_not_found", "tm_ambiguous", "no_match_to_hand", "upsert_error",
})

# pt56 (#TABLE-SS-SITE-FROM-FILENAME) — o SITE vem do NOME do ficheiro
# (determinístico; a Vision mislê PS/WPN como GG/WN). 'Stars' é o token do formato
# ANTIGO (Shot<N>-Stars-…); 'PokerStars' o nome completo do formato NOVO. Os outros
# (GGPoker/Winamax/WPN) são iguais nos dois formatos.
# pt62 (#TABLE-SS-IT-EXE-PREFIX) — o Intuitive Tables passou a usar o nome do
# EXECUTÁVEL como 1º token (ex.: 'GGnet.exe', 'Winamax.exe'). PONTO ÚNICO de
# token→site: chaves em minúsculas, o sufixo '.exe' é aparado antes do lookup
# (ver `_normalize_site_token`). Para acrescentar PS/WPN/CoinPoker basta uma
# linha aqui.
_FILENAME_SITE_MAP = {
    "ggpoker": "GGPoker",
    "ggnet": "GGPoker",           # IT: GGnet.exe
    "winamax": "Winamax",         # IT: Winamax.exe (sufixo aparado antes do lookup)
    "wpn": "WPN",
    "yapoker": "WPN",             # skin WPN do Rui (IT: YaPoker.exe) → tratar como WPN
    "stars": "PokerStars",        # antigo: Shot<N>-Stars-…
    "pokerstars": "PokerStars",   # novo: nome completo
}


def _normalize_site_token(token: Optional[str]) -> Optional[str]:
    """Token do 1º campo do nome → site canónico. Único ponto de verdade do
    mapeamento. Case-insensitive; apara um sufixo '.exe' (prefixo do IT, ex.
    'GGnet.exe'→GGPoker). None quando o token não é reconhecido (→ fallback
    Vision a jusante)."""
    if not token:
        return None
    t = token.strip()
    if t.lower().endswith(".exe"):
        t = t[:-4]
    return _FILENAME_SITE_MAP.get(t.lower())

# #TABLE-SS-FILENAME-TN — o formato NOVO do Intuitive Tables traz o
# tournament_number no nome → fonte AUTORITÁRIA do torneio (mata o tm_ambiguous).
#   <Site>-<Title>(<tn>)(#<mesa>)-<YYYYMMDDHHMMSS>-<idx>
#   ex.: 'Winamax-Winamax ODYSSEY(1106616980)(#011)-20260605170038-1'
# Robusto (regex, não split posicional): o título pode ter hífens/espaços/$/(...).
# O `tn` é o parêntese SÓ-DÍGITOS imediatamente antes do (#<mesa>); o (#NNN) tem
# '#' (é a mesa, não o tn). O `(#` é a âncora única que fixa a mesa; por isso o
# `.+` ganancioso do título recua até ao tn certo mesmo com '(123)' no nome.
# Formato ANTIGO (sem tn): 'Shot<N>-<Site>-<YYYYMMDDHHMMSS>' — distingue-se pelo
# 1º token ('Shot').
_IT_NEW_RE = re.compile(
    r"^(?P<site>[A-Za-z]+(?:\.exe)?)-"
    r"(?P<title>.+)"
    r"\((?P<tn>\d+)\)"
    r"\(#(?P<table>\d+)\)-"
    r"(?P<ts>\d{14})-"
    r"(?P<idx>\d+)$"
)


def parse_table_ss_filename(filename: Optional[str]) -> dict:
    """Parser robusto do nome de ficheiro do Intuitive Tables. Devolve
    {site, tournament_number, tournament_name, table} (None quando ausente).
    Formato NOVO traz `tn` (autoritário); ANTIGO ('Shot<N>-…') não. Ver _IT_NEW_RE."""
    out = {"site": None, "tournament_number": None,
           "tournament_name": None, "table": None}
    if not filename:
        return out
    base = filename.rsplit(".", 1)[0] if "." in filename else filename
    first = base.split("-", 1)[0].strip()
    if first.lower().startswith("shot"):
        # ANTIGO: site no token [1]; sem tn.
        parts = base.split("-")
        if len(parts) >= 2:
            out["site"] = _normalize_site_token(parts[1])
        return out
    # NOVO: regex completa (com tn).
    m = _IT_NEW_RE.match(base)
    if m:
        out["site"] = _normalize_site_token(m.group("site"))
        out["tournament_number"] = m.group("tn")
        out["tournament_name"] = m.group("title").strip()
        out["table"] = m.group("table")
        return out
    # NOVO-ish mas sem tn (regex não bateu) → só o site do 1º token; tn None
    # → cai no fluxo ACTUAL (Vision + resolver), sem regressão. É por aqui que
    # passam as SS de MESA GG do IT (ex. 'GGnet.exe-… - Blinds … - Table …'),
    # cujo formato não tem '(tn)(#mesa)'.
    out["site"] = _normalize_site_token(first)
    return out


def _site_from_filename(filename: Optional[str]) -> Optional[str]:
    """Site a partir do nome (ambos os formatos). Back-compat — delega no
    `parse_table_ss_filename`. None → fallback Vision."""
    return parse_table_ss_filename(filename)["site"]


# #IT-MATCHER-CASCADE — o NOME do ficheiro do IT carrega o HAND-ID da mão (o grupo
# `_<dígitos>-<YYYYMMDDHHMMSS>-<idx>`), a MESA e as BLINDS. O hand-id é a âncora
# MAIS FIÁVEL (casa 1:1). Nenhum destes campos vem da Vision — vêm do nome.
_IT_HAND_NUM_RE = re.compile(r"_(\d+)-\d{14}-\d+(?:\.[a-z0-9]+)?$", re.I)
_IT_FN_TABLE_RE = re.compile(r"- Table (\d+)")
_IT_FN_BLINDS_RE = re.compile(r"Blinds ([\d,]+) _ ([\d,]+)")
_HH_TABLE_RE = re.compile(r"Table '(\d+)'")


def _parse_it_hand_fields(filename: Optional[str]) -> dict:
    """Extrai do NOME do ficheiro IT (não da Vision): hand_num (str; o hand-id da
    GG — pode vir TRUNCADO quando o título é longo, ex. Speed Racer), table (int),
    sb/bb (int). Campos None quando ausentes."""
    out = {"hand_num": None, "table": None, "sb": None, "bb": None}
    if not filename:
        return out
    m = _IT_HAND_NUM_RE.search(filename)
    if m:
        out["hand_num"] = m.group(1)
    mt = _IT_FN_TABLE_RE.search(filename)
    if mt:
        out["table"] = int(mt.group(1))
    mb = _IT_FN_BLINDS_RE.search(filename)
    if mb:
        out["sb"] = int(mb.group(1).replace(",", ""))
        out["bb"] = int(mb.group(2).replace(",", ""))
    return out


def _hand_by_exact_id(hand_id: str) -> Optional[dict]:
    """A mão GG com este hand_id EXATO (guard rails do resolver: 2026+, sem
    mtt_archive). None se não existe. É o Tier 1 do matcher IT."""
    rows = query(
        """SELECT id, hand_id, tournament_number, tournament_name, site, played_at, raw
             FROM hands
            WHERE hand_id = %s AND played_at >= '2026-01-01'
              AND study_state != 'mtt_archive'
            LIMIT 1""",
        (hand_id,),
    )
    return dict(rows[0]) if rows else None


def _hh_table_number(raw: Optional[str]) -> Optional[int]:
    """Nº de mesa da HH GG (linha `Table '<N>'`). None se ausente."""
    if not raw:
        return None
    m = _HH_TABLE_RE.search(raw)
    return int(m.group(1)) if m else None

# pt39 — o buy_in da SS de mesa vem como string com moeda ("€50", "$108"),
# ao contrário do lobby (float). Parse para (total_float, currency) p/ alimentar
# o discriminador buy_in do TIER 0 do resolver.
_BUY_IN_NUM_RE = re.compile(r"\d+(?:\.\d+)?")


def _parse_buy_in_str(s: Optional[str]) -> tuple[Optional[float], Optional[str]]:
    """'€50' -> (50.0, 'EUR'); '$108' -> (108.0, 'USD'); '€40+€10' -> (50.0,'EUR').

    (None, None) se vazio/sem número. Vírgulas de milhares removidas; assume
    buy-ins inteiros (decimal-vírgula EU não tratado — fora de scope pt39).
    """
    if not s or not isinstance(s, str):
        return (None, None)
    currency = "EUR" if "€" in s else ("USD" if "$" in s else None)
    nums = _BUY_IN_NUM_RE.findall(s.replace(",", ""))
    if not nums:
        return (None, currency)
    total = sum(float(n) for n in nums)
    return (total if total > 0 else None, currency)


# ── Schema ───────────────────────────────────────────────────────────────────

def ensure_table_ss_processing_log_schema():
    """Idempotente. Chamada no lifespan. Espelha lobby_processing_log mas com
    file_hash como chave de dedup (em vez de discord_message_id)."""
    sql = """
    CREATE TABLE IF NOT EXISTS table_ss_processing_log (
        id                 BIGSERIAL PRIMARY KEY,
        file_hash          TEXT UNIQUE NOT NULL,
        source             TEXT NOT NULL DEFAULT 'manual_upload',
        original_filename  TEXT,
        file_size          INTEGER,
        uploaded_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        captured_at        TIMESTAMP,   -- pt51: Lisboa naive (filename é local)
        attempt_count      INTEGER NOT NULL DEFAULT 1,
        result             TEXT NOT NULL,
        reason_detail      TEXT,
        site               TEXT,
        tournament_name    TEXT,
        tournament_number  TEXT,
        players_left       INTEGER,
        total_entries      INTEGER,
        matched_hand_id    TEXT,
        vision_json        JSONB
    );
    """
    # Estágio 2 desanon — imagem comprimida (1280/JPEG85, padrão dos replayers)
    # guardada na linha para o painel de triagem mostrar a SS ao lado da mão.
    # ADD COLUMN IF NOT EXISTS para BDs já em produção (lifespan boot).
    alter_img = (
        "ALTER TABLE table_ss_processing_log "
        "ADD COLUMN IF NOT EXISTS img_b64 TEXT;"
    )
    # pt72 — pasta-como-tag: a subpasta de captura do IT é a tag de estudo.
    # Guardada na linha p/ o reconcile re-aplicar à mão (o FT '-ft' é derivado da
    # Vision na aplicação, não guardado aqui).
    alter_folder_tag = (
        "ALTER TABLE table_ss_processing_log "
        "ADD COLUMN IF NOT EXISTS folder_tag TEXT;"
    )
    # #GG-HEALTH-ACTIONS (Ação 3): decisão do Rui sobre uma suspeita de troca —
    # 'moved' (aceitou, captura movida) / 'kept' (rejeitou, fica onde está) / NULL
    # (por rever). O painel exclui as revistas (swap_review IS NOT NULL).
    alter_swap_review = (
        "ALTER TABLE table_ss_processing_log "
        "ADD COLUMN IF NOT EXISTS swap_review TEXT;"
    )
    idx_uploaded = (
        "CREATE INDEX IF NOT EXISTS idx_table_ss_uploaded_at "
        "ON table_ss_processing_log (uploaded_at DESC);"
    )
    idx_result = (
        "CREATE INDEX IF NOT EXISTS idx_table_ss_result "
        "ON table_ss_processing_log (result);"
    )
    idx_tn_captured = (
        "CREATE INDEX IF NOT EXISTS idx_table_ss_tn_captured "
        "ON table_ss_processing_log (tournament_number, captured_at DESC) "
        "WHERE tournament_number IS NOT NULL AND players_left IS NOT NULL;"
    )
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(sql)
            cur.execute(alter_img)
            cur.execute(alter_folder_tag)
            cur.execute(alter_swap_review)
            cur.execute(idx_uploaded)
            cur.execute(idx_result)
            cur.execute(idx_tn_captured)
        conn.commit()
    finally:
        conn.close()


# ── Link da mão (hands.context_table_ss_id) ──────────────────────────────────

def _principal_rank(reason: Optional[str]) -> int:
    """Força do match para escolher a captura PRINCIPAL numa colisão. Tier 1
    (hand-id do nome) é a âncora mais forte; tempo/nome vêm a seguir."""
    if not reason:
        return 1
    if reason == "manual_link":         # o Rui escolheu — âncora mais forte
        return 4
    if reason == "filename_hand_id":
        return 3
    if (reason.startswith("physical") or reason.startswith("single_tn")
            or reason.startswith("disambiguated") or reason == "filename_tn"):
        return 2
    return 1


def _new_capture_wins_principal(cur, new_ss: int, cur_ss: int) -> bool:
    """Colisão (#IT-MATCHER-COLISOES): nova captura (new_ss) vs. principal actual
    (cur_ss) na MESMA mão. Vence o match mais forte (hand-id > tempo); empate →
    captured_at mais cedo; empate → ss_id menor. Determinístico → o resultado é o
    mesmo por qualquer ordem de processamento."""
    cur.execute(
        "SELECT id, reason_detail, captured_at FROM table_ss_processing_log "
        "WHERE id IN (%s, %s)", (new_ss, cur_ss),
    )
    rows = {r["id"]: r for r in cur.fetchall()}
    a, b = rows.get(new_ss), rows.get(cur_ss)
    if not b:
        return True          # principal actual desapareceu → nova assume
    if not a:
        return False
    ra, rb = _principal_rank(a["reason_detail"]), _principal_rank(b["reason_detail"])
    if ra != rb:
        return ra > rb
    ca, cb = a["captured_at"], b["captured_at"]
    if ca and cb and ca != cb:
        return ca < cb
    return new_ss < cur_ss


def _apply_hand_link(cur, ss_id: int, matched_hand_db_id: Optional[int]) -> None:
    """Reconcilia `hands.context_table_ss_id` para esta SS (id=ss_id), DENTRO da
    transacção do `cur`. Desliga mãos OBSOLETAS que ainda apontem para esta
    captura mas já não são o match. Idempotente: re-correr com o mesmo match não
    muda nada. Primitiva única usada pelo upload e pelo reconcile (#FIX-B3 pt50).

    #IT-MATCHER-COLISOES: VÁRIAS capturas podem casar a MESMA mão (2 prints da
    mesma mão = duplicados legítimos). A coluna guarda a captura PRINCIPAL (1 por
    mão); as restantes ficam SECUNDÁRIAS (têm `matched_hand_id` no log, mas não
    possuem o context). A escolha da principal é DETERMINÍSTICA (ver
    `_new_capture_wins_principal`) → ordem-independente."""
    if matched_hand_db_id is None:
        # Sem match → desliga qualquer mão que ainda aponte para esta SS.
        cur.execute(
            "UPDATE hands SET context_table_ss_id = NULL "
            "WHERE context_table_ss_id = %s",
            (ss_id,),
        )
        return
    # Desliga mãos obsoletas (apontavam para esta SS mas já não são o match)…
    cur.execute(
        "UPDATE hands SET context_table_ss_id = NULL "
        "WHERE context_table_ss_id = %s AND id <> %s",
        (ss_id, matched_hand_db_id),
    )
    # …e assume a principal SÓ se vencer a que lá está (ou se estiver livre).
    cur.execute(
        "SELECT context_table_ss_id FROM hands WHERE id = %s",
        (matched_hand_db_id,),
    )
    row = cur.fetchone()
    current = row.get("context_table_ss_id") if row else None
    if (current is None or current == ss_id
            or _new_capture_wins_principal(cur, ss_id, current)):
        cur.execute(
            "UPDATE hands SET context_table_ss_id = %s WHERE id = %s",
            (ss_id, matched_hand_db_id),
        )


# ── UPSERT (+ atomic link em hands) ──────────────────────────────────────────

def _upsert_table_ss_log(
    *,
    file_hash: str,
    source: str,
    original_filename: Optional[str],
    file_size: Optional[int],
    result: str,
    reason_detail: Optional[str] = None,
    site: Optional[str] = None,
    tournament_name: Optional[str] = None,
    tournament_number: Optional[str] = None,
    players_left: Optional[int] = None,
    total_entries: Optional[int] = None,
    captured_at: Optional[datetime] = None,
    matched_hand_id: Optional[str] = None,
    vision_json: Optional[dict] = None,
    matched_hand_db_id: Optional[int] = None,
    img_b64: Optional[str] = None,
    folder_tag: Optional[str] = None,
) -> Optional[int]:
    """UPSERT por file_hash; incrementa attempt_count em conflito. Reconcilia o
    link da mão na MESMA transacção via `_apply_hand_link` (#FIX-B3 pt50): liga a
    mão casada (matched_hand_db_id, só presente em success) e desliga obsoletas.
    Devolve o id."""
    if result not in _VALID_RESULTS:
        raise ValueError(f"invalid result {result!r}")
    try:
        conn = get_conn()
    except Exception as e:
        logger.error(f"[table_ss_log] get_conn failed: {type(e).__name__}: {e}")
        return None
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO table_ss_processing_log (
                    file_hash, source, original_filename, file_size, captured_at,
                    result, reason_detail, site, tournament_name,
                    tournament_number, players_left, total_entries,
                    matched_hand_id, vision_json, img_b64, folder_tag
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                )
                ON CONFLICT (file_hash) DO UPDATE SET
                    uploaded_at       = NOW(),
                    attempt_count     = table_ss_processing_log.attempt_count + 1,
                    source            = EXCLUDED.source,
                    result            = EXCLUDED.result,
                    reason_detail     = EXCLUDED.reason_detail,
                    original_filename = COALESCE(EXCLUDED.original_filename, table_ss_processing_log.original_filename),
                    file_size         = COALESCE(EXCLUDED.file_size, table_ss_processing_log.file_size),
                    captured_at       = COALESCE(EXCLUDED.captured_at, table_ss_processing_log.captured_at),
                    site              = COALESCE(EXCLUDED.site, table_ss_processing_log.site),
                    tournament_name   = COALESCE(EXCLUDED.tournament_name, table_ss_processing_log.tournament_name),
                    tournament_number = COALESCE(EXCLUDED.tournament_number, table_ss_processing_log.tournament_number),
                    players_left      = COALESCE(EXCLUDED.players_left, table_ss_processing_log.players_left),
                    total_entries     = COALESCE(EXCLUDED.total_entries, table_ss_processing_log.total_entries),
                    matched_hand_id   = COALESCE(EXCLUDED.matched_hand_id, table_ss_processing_log.matched_hand_id),
                    vision_json       = COALESCE(EXCLUDED.vision_json, table_ss_processing_log.vision_json),
                    img_b64           = COALESCE(EXCLUDED.img_b64, table_ss_processing_log.img_b64),
                    folder_tag        = COALESCE(EXCLUDED.folder_tag, table_ss_processing_log.folder_tag)
                RETURNING id
                """,
                (
                    file_hash, source, original_filename, file_size, captured_at,
                    result, reason_detail, site, tournament_name,
                    tournament_number, players_left, total_entries,
                    matched_hand_id, vision_json, img_b64, folder_tag,
                ),
            )
            row = cur.fetchone()
            ss_id = row["id"] if row else None
            # #FIX-B3 (pt50): reconcilia o link da mão SEMPRE (não só em success),
            # via a primitiva única: liga a mão casada e desliga qualquer mão
            # obsoleta que ainda aponte para esta SS. matched_hand_db_id só vem
            # != None quando R devolveu success.
            if ss_id is not None:
                _apply_hand_link(cur, ss_id, matched_hand_db_id)
        conn.commit()
        return ss_id
    except Exception as e:
        logger.error(
            f"[table_ss_log] upsert failed hash={file_hash[:12]}: "
            f"{type(e).__name__}: {e}"
        )
        try:
            conn.rollback()
        except Exception:
            pass
        return None
    finally:
        try:
            conn.close()
        except Exception:
            pass


# ── Match temporal mão → resolver-desambigua ─────────────────────────────────

def _find_candidate_hands(
    captured_at: datetime, site: str, table: Optional[int] = None
) -> list[dict]:
    """Candidatas do mesmo site pela REGRA FÍSICA: a captura mostra a mão A
    DECORRER, i.e. a última que começou ANTES (ou no instante) da captura — NUNCA
    a seguinte. Antes ordenava por ABS(proximidade) → escolhia a mais próxima, que
    era muitas vezes a mão SEGUINTE (a hora empurra a captura ~1 mão à frente = a
    origem das 209 "suspeitas"). Agora: `played_at <= captured_at`, ORDER BY
    played_at DESC → o [0] é a mão-a-decorrer. Quando o nome dá a MESA (GG), filtra
    por mesa (100% fiável) — encurta o multi-tabling ao feltro certo. Guard rails
    iguais ao resolver (2026+, sem mtt_archive, tournament_number presente)."""
    lo = captured_at - timedelta(seconds=TABLE_SS_MATCH_WINDOW_S)
    params = [site, lo, captured_at]
    table_clause = ""
    if table is not None:
        table_clause = " AND substring(raw from 'Table ''(\\d+)''') = %s"
        params.append(str(table))
    rows = query(
        f"""
        SELECT id, hand_id, tournament_number, tournament_name, site, played_at, raw
          FROM hands
         WHERE played_at >= '2026-01-01'
           AND site = %s
           AND played_at BETWEEN %s AND %s
           AND tournament_number IS NOT NULL
           AND study_state != 'mtt_archive'{table_clause}
         ORDER BY played_at DESC
        """,
        tuple(params),
    )
    return [dict(r) for r in rows]


# ── #WPN-PS-TABLE-SS-TIME-ONLY-MATCH: validação por NICKS (WPN/PS não têm nome fiável) ──
_SEAT_NICK_RE = re.compile(r'^Seat \d+: (.+?) \(', re.M)
_SS_NICK_MIN = 3          # nicks lidos mínimos para validar (senão sinal insuficiente)
_SS_NICK_FIT_MIN = 0.5    # sobreposição mínima: metade dos nicks lidos batem com a mão


def _ss_read_nicks(vj: dict) -> set:
    """Nicks lidos pela Vision na captura de mesa (lowercased, sem vazios)."""
    return {(s.get("nick") or "").strip().lower()
            for s in (vj.get("seats") or []) if (s.get("nick") or "").strip()}


def _hand_seat_nicks(raw) -> set:
    """Nicks dos Seat lines da HH (lowercased). WPN/PS têm nicks REAIS."""
    return {m.group(1).strip().lower() for m in _SEAT_NICK_RE.finditer(raw or "")}


def _nick_fit(ss_nicks: set, raw) -> float:
    """Fracção dos nicks LIDOS que aparecem nos seats da mão. 0..1."""
    if not ss_nicks:
        return 0.0
    return len(ss_nicks & _hand_seat_nicks(raw)) / len(ss_nicks)


def _find_closest_hand_by_tn(
    captured_at: datetime, site: str, tn: str
) -> Optional[dict]:
    """#TABLE-SS-FILENAME-TN — a mão (de estudo) do mesmo site + tournament_number
    mais próxima de captured_at. `tn` AUTORITÁRIO (do filename) → SEM janela
    temporal nem resolver-por-nome (a hora só escolhe QUAL mão do torneio). Guard
    rails iguais (2026+, sem mtt_archive). None se não há mão desse tn."""
    rows = query(
        """SELECT id, hand_id, tournament_number, tournament_name, site, played_at
             FROM hands
            WHERE played_at >= '2026-01-01'
              AND site = %s
              AND tournament_number = %s
              AND study_state != 'mtt_archive'
            ORDER BY ABS(EXTRACT(EPOCH FROM (played_at - %s)))
            LIMIT 1""",
        (site, tn, captured_at),
    )
    return dict(rows[0]) if rows else None


# #IT-MATCHER-HERO-LAST-HAND (regra do Rui, 11 Jul 2026) — janela do bust: o
# print é capturado segundos após a mão final (o Rui foto-a no momento do bust).
# played_at = início da mão; a captura vem depois (bust + demora a fotografar),
# com folga p/ a duração da própria mão.
_BUST_WINDOW_BEFORE_MIN = -5.0
_BUST_WINDOW_AFTER_MIN = 45.0


def _hero_last_hand_bust_candidate(site, tournament_name, captured_at):
    """Candidata do BUST: a mão do Hero do MESMO NOME (QUALQUER edição) cujo
    played_at cai na janela do bust — a mais recente antes/à-hora do print. TODAS
    as mãos em `hands` são do Hero (a app só guarda as dele) → basta o nome + a
    janela. ATRAVESSA edições de propósito: resolver 1 tn apontava a edição errada
    (vazia) quando o nome tem várias edições. Só sites de nome fiável (GG/WN); PS/
    WPN (nome NULL/genérico) → None (nada a validar por nome). None se nenhuma."""
    if not tournament_name or site not in _NAME_RELIABLE_SITES:
        return None
    lo = captured_at - timedelta(minutes=abs(_BUST_WINDOW_AFTER_MIN))
    hi = captured_at + timedelta(minutes=abs(_BUST_WINDOW_BEFORE_MIN))
    rows = query(
        "SELECT id, hand_id, tournament_number, tournament_name, site, played_at "
        "  FROM hands "
        " WHERE played_at >= '2026-01-01' AND site = %s "
        "   AND played_at BETWEEN %s AND %s "
        "   AND tournament_number IS NOT NULL AND study_state != 'mtt_archive' "
        " ORDER BY played_at DESC",
        (site, lo, hi),
    )
    for r in rows:                       # DESC → a 1ª que casa o nome = a do bust
        if name_tokens_subset(tournament_name, r.get("tournament_name") or ""):
            return dict(r)
    return None


# #FIX-B2 (pt50): salas cuja HH traz o NOME REAL do torneio (validável por nome
# token-a-token). GG e Winamax gravam o nome real; a Winamax pode trazer o nº de
# mesa #NNN (aparado por clean_tournament_name). WPN grava string de garantia
# genérica e PokerStars grava NULL → SEM nome usável para comparar; nessas salas
# o name-estrito ficaria sempre em mismatch e partia matches válidos, por isso
# caem na proximidade temporal.
_NAME_RELIABLE_SITES = {"GGPoker", "Winamax"}


def _resolve_match(
    captured_at: datetime, vj: dict, site: str, candidates: list[dict]
) -> dict:
    """Decide a mão associada à SS. Pura (recebe candidates já ordenados).

    - 0 candidatos              → no_hands_in_window
    - 1 tournament_number       → match directo (a mais próxima)
    - >1 tournament_number      → resolver-por-nome desambigua; se o tn cair
                                   entre os candidatos, match; senão ambíguo.
    Devolve {matched, tn, ambiguous, reason}.
    """
    if not candidates:
        return {"matched": None, "tn": None, "ambiguous": False,
                "reason": "no_hands_in_window"}
    tns = {c["tournament_number"] for c in candidates}
    if len(tns) == 1:
        c = candidates[0]
        # pt39 (parte 2/2): validar o nome antes de aceitar. Em single_tn a
        # proximidade temporal sozinha já ligou SSs ao torneio errado quando o
        # da SS não tinha mão na janela (ex.: EXPLORER→INTERSTELLAR,
        # ODYSSEY→ZENITH). Se a SS tem nome lido e NÃO bate com o do único
        # torneio na janela → o torneio da SS não tem mão aqui → no match.
        ss_name = vj.get("tournament_name")
        hand_name = c.get("tournament_name")
        # #FIX-B2 (pt50): name-estrito SÓ quando há nome fiável dos dois lados e a
        # sala grava nome real (GG/Winamax). Evita ligar ao torneio errado
        # (ODYSSEY→ZENITH). WPN (garantia genérica) e PS (NULL) não dão para
        # validar por nome → não rejeitar, cair na proximidade temporal.
        if (ss_name and hand_name and site in _NAME_RELIABLE_SITES
                and not name_tokens_subset(ss_name, hand_name)):
            return {"matched": None, "tn": None, "ambiguous": False,
                    "reason": f"single_tn_name_mismatch:{ss_name}!={hand_name}"}
        # #WPN-PS-TABLE-SS-TIME-ONLY-MATCH: WPN/PS não têm nome fiável (WPN=garantia
        # genérica, PS=NULL) → antes casava só pela HORA (armadilha em multi-tabling:
        # 2 mesas do mesmo torneio à mesma hora trocam). Agora valida por NICKS (as HH
        # WPN/PS têm nicks reais; a Vision lê-os): escolhe o candidato de melhor
        # sobreposição; divergência (fit < metade) → NÃO casa (orphan honesto). Só quando
        # a SS leu ≥3 nicks (sinal suficiente); com menos, cai na proximidade temporal.
        if site not in _NAME_RELIABLE_SITES:
            ss_n = _ss_read_nicks(vj)
            if len(ss_n) >= _SS_NICK_MIN:
                c = max(candidates, key=lambda cd: _nick_fit(ss_n, cd.get("raw")))
                fit = _nick_fit(ss_n, c.get("raw"))
                if fit < _SS_NICK_FIT_MIN:
                    return {"matched": None, "tn": None, "ambiguous": False,
                            "reason": f"wpn_ps_nick_mismatch:{fit:.0%}"}
        # SS sem nome lido, ou nicks insuficientes → leniente (proximidade temporal).
        return {"matched": c, "tn": c["tournament_number"], "ambiguous": False,
                "reason": "single_tn"}
    # Multi-tabling: desambiguar pelo nome lido nesta SS.
    ss_name = vj.get("tournament_name")
    # pt54: desambiguação DIRECTA pelo nome (limpo) contra os candidatos que já
    # temos na janela. Mais robusta que o resolver, cuja janela própria
    # (posted−30min) exclui um torneio iniciado <30min antes da SS — era o que
    # deixava o GALACTICA #034 ambíguo apesar de só haver 1 GALACTICA na janela.
    # Se exactamente UM torneio entre os candidatos bate o nome → é esse.
    if ss_name and site in _NAME_RELIABLE_SITES:
        name_hit = [c for c in candidates
                    if name_tokens_subset(ss_name, c.get("tournament_name"))]
        hit_tns = {c["tournament_number"] for c in name_hit}
        if len(hit_tns) == 1:
            return {"matched": name_hit[0], "tn": name_hit[0]["tournament_number"],
                    "ambiguous": False, "reason": "disambiguated_by_name_direct"}
    # Fallback: resolver-por-nome (TS/meta/hands) quando o directo não resolve.
    _bi, _cur = _parse_buy_in_str(vj.get("tournament_buy_in"))
    tn, _cands = resolve_tournament_number(
        site, ss_name or "", None,
        posted_at_hint=captured_at, buy_in=_bi, buy_in_currency=_cur,
    )
    if tn and tn in tns:
        closest = next((c for c in candidates if c["tournament_number"] == tn), None)
        if closest:
            return {"matched": closest, "tn": tn, "ambiguous": False,
                    "reason": "disambiguated_by_name"}
    return {"matched": None, "tn": None, "ambiguous": True,
            "reason": f"multi_tn_unresolved:{len(tns)}"}


# ── R — função determinística única de match (#FIX-B3 pt50) ──────────────────

def compute_table_ss_match(
    captured_at: Optional[datetime], site: Optional[str], vj: dict,
    filename_tn: Optional[str] = None, filename: Optional[str] = None,
) -> dict:
    """R — a ÚNICA função de match da SS de mesa. Dado o read guardado da SS
    (captured_at UTC, site, vision_json) + o conjunto ACTUAL de mãos na BD,
    calcula o match. Mesmos inputs + mesmo estado da BD → mesmo output, sem
    depender de quando a SS entrou nem de qualquer resultado anterior (recalcula
    sempre de raiz). Usada IGUALMENTE pelo upload e pelo reconcile.

    Pura quanto a escritas (só lê `hands` via `_find_candidate_hands` e o
    resolver). Devolve {result, reason_detail, site, tournament_number,
    matched_hand_id, matched_hand_db_id}; result ∈ {success, tm_ambiguous,
    no_match_to_hand}.
    """
    # pt56: o `site` já é AUTORITÁRIO (vem do nome do ficheiro, decidido na
    # ingestão/backfill) — compute confia nele e NÃO re-corrige por nome (evita
    # que a Regra B sobrescreva um site correcto do nome cujo torneio coincide
    # com o de outra sala). O self-heal Vision fica só no upload-fallback.
    # pt54: Winamax → nome canónico para o matching (idempotente; cobre rows com
    # vision_json ainda por-limpar no reconcile). Não muta o vj do caller.
    if site == "Winamax":
        _cl = clean_winamax_tournament_name(vj.get("tournament_name"))[0]
        if _cl != vj.get("tournament_name"):
            vj = {**vj, "tournament_name": _cl}
    base = {
        "result": "no_match_to_hand", "reason_detail": None, "site": site,
        "tournament_number": None, "matched_hand_id": None,
        "matched_hand_db_id": None,
    }

    # ── TIER 1 — HAND-ID do nome (âncora mais fiável; casa 1:1) ──────────────────
    # #IT-MATCHER-CASCADE: o número no nome do ficheiro é o HAND-ID da mão. Se
    # INTEIRO (10 dígitos) e a mão GG existe → casa AQUI, imediato, SEM passar pela
    # hora (era a hora que empurrava a captura 1 mão à frente = as 209 "suspeitas").
    # Guarda: a MESA do nome tem de bater com a da HH (100% fiável); se não bate, o
    # número aponta mão errada (raro) → cai para os tiers seguintes.
    fields = _parse_it_hand_fields(filename)
    if site == "GGPoker" and fields["hand_num"] and len(fields["hand_num"]) == 10:
        cand = _hand_by_exact_id(f"GG-{fields['hand_num']}")
        if cand:
            hh_table = _hh_table_number(cand.get("raw"))
            if fields["table"] is None or hh_table is None or hh_table == fields["table"]:
                return {
                    "result": "success", "reason_detail": "filename_hand_id",
                    "site": site, "tournament_number": cand["tournament_number"],
                    "matched_hand_id": cand["hand_id"],
                    "matched_hand_db_id": cand["id"],
                }

    # #TABLE-SS-FILENAME-TN — formato NOVO: o tn vem do NOME do ficheiro e é
    # AUTORITÁRIO. Match por site + tn + hora mais próxima, SEM passar pelo
    # resolver-por-nome da Vision → mata o tm_ambiguous; o filename ganha à Vision
    # se discordarem. (A Vision continua a correr no upload para players_left/
    # total_entries — só deixamos de a usar para a IDENTIDADE do torneio.)
    if filename_tn:
        base["tournament_number"] = filename_tn
        if captured_at is not None:
            best = _find_closest_hand_by_tn(captured_at, site, filename_tn)
            if best:
                return {
                    "result": "success", "reason_detail": "filename_tn", "site": site,
                    "tournament_number": filename_tn,
                    "matched_hand_id": best["hand_id"],
                    "matched_hand_db_id": best["id"],
                }
            base["reason_detail"] = f"filename_tn:{filename_tn}:no_hand_for_tn"
            return base
        base["reason_detail"] = "filename_tn: sem captured_at"
        return base

    if captured_at is None:
        # Sem âncora temporal não há match a uma mão; resolve tn p/ limbo.
        _bi, _cur = _parse_buy_in_str(vj.get("tournament_buy_in"))
        tn, _c = resolve_tournament_number(
            site, vj.get("tournament_name") or "", None,
            buy_in=_bi, buy_in_currency=_cur,
        )
        base["reason_detail"] = "sem captured_at (filename sem YYYYMMDDHHMMSS)"
        base["tournament_number"] = tn
        return base

    candidates = _find_candidate_hands(captured_at, site, table=fields["table"])
    m = _resolve_match(captured_at, vj, site, candidates)
    if m["matched"]:
        return {
            "result": "success", "reason_detail": m["reason"], "site": site,
            "tournament_number": m["tn"],
            "matched_hand_id": m["matched"]["hand_id"],
            "matched_hand_db_id": m["matched"]["id"],
        }

    # #IT-MATCHER-HERO-LAST-HAND (regra do Rui, 11 Jul; gate corrigido pela
    # evidência) — RESCUE do BUST: o hand-id do nome falhou (não há filename_tn
    # aqui — esse ramo retornou acima) E a via temporal NÃO casou. O print de bust
    # é capturado segundos após a mão FINAL do Hero → a última mão do torneio é a
    # candidata. Gate REAL do bust = captured_at na janela [−5, +45] min DEPOIS da
    # última mão (a guarda `_hero_last_hand_for_tn`), não a "visibilidade" do Hero:
    # 51/54 órfãs MOSTRAM o Hero (bottom-center) e são todas `no_hands_in_window`.
    # Casa pela mão do Hero (mesmo nome, qualquer edição) na janela do bust; toma
    # precedência sobre o ambíguo/no-hands (via temporal fraca no momento do bust).
    last = _hero_last_hand_bust_candidate(site, vj.get("tournament_name"), captured_at)
    if last:
        return {
            "result": "success", "reason_detail": "hero_last_hand_bust",
            "site": site, "tournament_number": last["tournament_number"],
            "matched_hand_id": last["hand_id"],
            "matched_hand_db_id": last["id"],
        }

    if m["ambiguous"]:
        base["result"] = "tm_ambiguous"
        base["reason_detail"] = m["reason"]
        return base
    # no_hands_in_window — resolve tn p/ limbo linkável.
    _bi, _cur = _parse_buy_in_str(vj.get("tournament_buy_in"))
    tn, _c = resolve_tournament_number(
        site, vj.get("tournament_name") or "", None,
        posted_at_hint=captured_at, buy_in=_bi, buy_in_currency=_cur,
    )
    base["reason_detail"] = m["reason"]
    base["tournament_number"] = tn
    return base


def _persist_table_ss_match(
    ss_id: int, desired: dict, *, prev_result=None, prev_matched_hand_id=None,
) -> bool:
    """Persiste o output de R numa row JÁ existente (o read Vision não muda):
    actualiza os campos de match e reconcilia o link da mão (`_apply_hand_link`:
    desliga obsoletas, liga a nova) — tudo em 1 transacção. NÃO confia em estado
    anterior. Devolve True se o match mudou (telemetria)."""
    changed = (
        desired["result"] != prev_result
        or desired["matched_hand_id"] != prev_matched_hand_id
    )
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE table_ss_processing_log
                   SET result = %s,
                       reason_detail = %s,
                       site = %s,
                       tournament_number = %s,
                       matched_hand_id = %s,
                       attempt_count = attempt_count + 1
                 WHERE id = %s
                """,
                (desired["result"], desired["reason_detail"], desired["site"],
                 desired["tournament_number"], desired["matched_hand_id"], ss_id),
            )
            _apply_hand_link(cur, ss_id, desired["matched_hand_db_id"])
        conn.commit()
        return changed
    except Exception as e:
        logger.error(
            f"[table_ss_reconcile] persist falhou id={ss_id}: {type(e).__name__}: {e}"
        )
        try:
            conn.rollback()
        except Exception:
            pass
        return False
    finally:
        try:
            conn.close()
        except Exception:
            pass


# ── Reconcile pós-import (R sobre TODAS as SS) ───────────────────────────────

def reconcile_table_ss(hand_ids=None) -> dict:
    """Corre R sobre TODAS as SS de mesa com read utilizável (já passaram
    Vision+parse+site-gate: result ∈ {success, no_match_to_hand, tm_ambiguous} e
    vision_json presente), recalculando o match de raiz e re-persistindo —
    INCLUINDO as já `success`, para CORRIGIR um match anterior errado quando
    chega uma mão melhor (vai além do relink B.1, que só re-tentava órfãs).

    Determinístico e idempotente: re-correr sem dados novos não muda nada (o
    link só é tocado quando o match muda de facto). O re-desanon + re-tag correm
    para TODO match success (não só quando `changed`) — no reimport o hand_id não
    muda mas a mão em BD é nova e anónima (#HRC-REIMPORT-REDEANON-CASADAS); o
    `_deanon_after_match` é idempotente (salta Discord/position_v3). Disparado
    fire-and-forget após cada import. `hand_ids=[]` → curto-circuita (nada
    importado). Devolve {checked, changed, success, orphan, ambiguous}.
    """
    if hand_ids is not None and len(hand_ids) == 0:
        return {"checked": 0, "changed": 0, "success": 0,
                "orphan": 0, "ambiguous": 0}

    rows = query(
        """SELECT id, captured_at, site, vision_json, result, matched_hand_id,
                  original_filename, folder_tag
             FROM table_ss_processing_log
            WHERE result IN ('success', 'no_match_to_hand', 'tm_ambiguous')
              AND vision_json IS NOT NULL"""
    )
    checked = changed = n_success = n_orphan = n_amb = 0
    for r in rows:
        checked += 1
        vj = r.get("vision_json") or {}
        # #TABLE-SS-FILENAME-TN: re-parseia o tn do nome guardado (autoritário).
        _ftn = parse_table_ss_filename(r.get("original_filename"))["tournament_number"]
        desired = compute_table_ss_match(
            r.get("captured_at"), r.get("site"), vj, filename_tn=_ftn,
            filename=r.get("original_filename"))
        if _persist_table_ss_match(
            r["id"], desired,
            prev_result=r.get("result"),
            prev_matched_hand_id=r.get("matched_hand_id"),
        ):
            changed += 1
        # Estágio 3-b: re-desanon + re-tag SEMPRE que o match é success — NÃO só quando
        # `changed`. #HRC-REIMPORT-REDEANON-CASADAS: no reimport o hand_id (GG-{tm}) é o
        # MESMO mas a mão em BD é NOVA e anónima → `changed=False`; sem isto as mãos com
        # captura casada voltavam ANÓNIMAS + sem tag no reimport. Idempotente: o
        # `_deanon_after_match` salta Discord/position_v3 e re-mapeia determinístico dos
        # `seats`; a folder-tag é upsert. Rows sem `seats` → no-op.
        if desired["result"] == "success":
            _deanon_after_match(desired["matched_hand_db_id"], vj)
            _apply_folder_tag_to_hand(desired["matched_hand_db_id"], r.get("folder_tag"), vj)
            n_success += 1
        elif desired["result"] == "tm_ambiguous":
            n_amb += 1
        else:
            n_orphan += 1
    logger.info(
        "[table_ss_reconcile] checked=%d changed=%d success=%d orphan=%d ambiguous=%d",
        checked, changed, n_success, n_orphan, n_amb,
    )
    return {"checked": checked, "changed": changed, "success": n_success,
            "orphan": n_orphan, "ambiguous": n_amb}


def relink_orphan_table_ss(hand_ids=None) -> dict:
    """Back-compat: os triggers de import (import_.py, hm3.py) chamam este nome.
    Agora delega no reconcile completo (R sobre TODAS as SS). Ver
    `reconcile_table_ss`."""
    return reconcile_table_ss(hand_ids)


def _parse_iso(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


# ── Orquestração ─────────────────────────────────────────────────────────────

def _blank_out(file_hash: str) -> dict:
    return {
        "result": "", "file_hash": file_hash, "dedup": False,
        "site": None, "tournament_name": None, "tournament_number": None,
        "players_left": None, "total_entries": None, "hand_matched": None,
        "captured_at": None, "reason_detail": None, "vision_json": None,
    }


# ── Desanonimização pós-match (Estágio 3-b) ──────────────────────────────────

def _hand_has_discord(hand_db_id: int) -> bool:
    """Mão tem presença Discord? (discord_tags não-vazio OU entry source=discord).
    Discord PREVALECE — uma mão assim não é desanonimizada pelo table-SS."""
    rows = query(
        "SELECT 1 FROM hands h WHERE h.id = %s AND ("
        "  (h.discord_tags IS NOT NULL AND h.discord_tags <> ARRAY[]::text[]) "
        "  OR EXISTS (SELECT 1 FROM entries e WHERE e.id = h.entry_id "
        "             AND e.source = 'discord')"
        ") LIMIT 1",
        (hand_db_id,),
    )
    return bool(rows)


def _deanon_after_match(matched_hand_db_id: Optional[int], vision_json) -> None:
    """Dispara a desanonimização da mão GG casada com os `seats` do table-SS.
    Gated (Estágio 3-b): só corre se a mão NÃO tem entrada Discord (Discord
    prevalece). Defensivo — falha aqui nunca rebenta o upload/reconcile. Rows
    antigas (vision_json sem `seats`, pré-Estágio-1) → no-op (Estágio 6 re-Vision)."""
    if not matched_hand_db_id or not isinstance(vision_json, dict):
        return
    seats = vision_json.get("seats") or []
    if not seats:
        return
    try:
        if _hand_has_discord(matched_hand_db_id):
            return  # Discord prevalece
        from app.services.table_ss_deanon import deanonymize_hand_from_table_ss
        res = deanonymize_hand_from_table_ss(
            matched_hand_db_id, seats, vision_json.get("hero_nick")
        )
        if res.get("status") == "deanonymized":
            logger.info(
                "[table_ss_deanon] hand %s: %s/%s mapeados (partial=%s)",
                matched_hand_db_id, res.get("mapped"), res.get("total"),
                res.get("deanon_partial"),
            )
    except Exception as e:  # pragma: no cover - defensivo
        logger.error("[table_ss_deanon] hand %s falhou: %s", matched_hand_db_id, e)


# ── pt72 — pasta-como-tag: aplicar a tag da subpasta do IT à mão casada ───────

def _ft_applies(vision_json) -> bool:
    """FT (mesa final) = nº de bancos OCUPADOS (com nick) == `players_left`,
    ambos lidos pela Vision. Fail-safe: qualquer um ausente/0 → False (sem '-ft').
    Pura/testável."""
    if not isinstance(vision_json, dict):
        return False
    seats = vision_json.get("seats") or []
    occupied = [
        s for s in seats
        if isinstance(s, dict) and (s.get("nick") or "").strip()
    ]
    pl = vision_json.get("players_left")
    return (
        bool(occupied)
        and isinstance(pl, int) and not isinstance(pl, bool) and pl > 0
        and len(occupied) == pl
    )


def _folder_tag_ft_source(base_tag: Optional[str], vision_json) -> Optional[str]:
    """Proveniência do sufixo de fase '-ft' (pt73), independente da BD. Pura.

    - `'manual'`  → a pasta JÁ trazia '-ft' (ICM PKO FT, PKO Pos FT): o Rui
      confirmou a mesa final à mão; NÃO se re-verifica.
    - `'auto'`    → a pasta era BASE e a Vision indicou mesa final (bancos ==
      restantes) → '-ft' adivinhado pela app (o Rui revê).
    - `None`      → sem '-ft' (base sem mesa final, ou sem tag).
    """
    if not base_tag:
        return None
    if base_tag.endswith("-ft"):
        return "manual"
    return "auto" if _ft_applies(vision_json) else None


def _final_folder_tag(base_tag: Optional[str], vision_json) -> Optional[str]:
    """tag final aplicada à mão (pt73). Prioridade MANUAL > AUTO:

    - pasta já com '-ft' (FT MANUAL) → devolve tal-e-qual (NÃO re-verifica nem
      duplica o sufixo — evita 'icm-pko-ft-ft');
    - pasta BASE → base + '-ft' (AUTO) se a Vision indicar mesa final, senão base.

    Fail-safe (Rui): incerto → sem '-ft' (preferir base a sufixo errado). Pura."""
    if not base_tag:
        return None
    if base_tag.endswith("-ft"):       # FT manual: confirmado, não mexer
        return base_tag
    return f"{base_tag}-ft" if _ft_applies(vision_json) else base_tag


def _apply_folder_tag_to_hand(
    matched_hand_db_id: Optional[int], base_tag: Optional[str], vision_json,
    *, conn=None,
) -> None:
    """Aplica a tag da PASTA do IT à mão casada: escreve em `discord_tags` (union
    distinct) + dispara `apply_villain_rules` — a MESMA porta da triagem manual
    (`capture_triage.tag`). A tag final ganha '-ft' se a Vision indicar mesa final.
    No-op se faltar mão/tag. Defensivo — falha aqui nunca rebenta o upload/reconcile.

    `conn` dado (reconcile) → escreve na transacção do caller (não faz commit);
    None → conn própria + commit."""
    # ★ Cura verde-KO (família A) — ANTES do early-return, para que uma mão JÁ-tagada
    # re-desanonimizada por captura SEM folder-tag (web-first) também seja scrubada. O
    # `incoming_folder_tag=base_tag` força tagged na captura que traz a tag ('tagada-depois');
    # sem base_tag, o wrapper usa is_tagged(mão). table-SS = captura cedo → sem verde →
    # MUST-only. O GUARD não pode ser saltado por early-return. Corre após o `_deanon_after_match`.
    if matched_hand_db_id:
        try:
            from app.services.eliminated_bounty import scrub_and_persist
            scrub_and_persist(matched_hand_db_id, vision_data=vision_json,
                              incoming_folder_tag=base_tag)
        except Exception as e:  # pragma: no cover - defensivo
            logger.error("[crown-cure] ⚠️ GUARD FALHOU (table-ss) hand %s — coroa de bustado "
                         "pode SOBREVIVER (o crivo eliminated-crown-scan apanha): %s",
                         matched_hand_db_id, e)
    if not matched_hand_db_id or not base_tag:
        return
    # Fonte única — canonicaliza o folder_tag que chega do IT (o appimport pode
    # mandar o nome da pasta, ex. "NKO Pos"→pos-nko). Passthrough para o que não
    # reconhece (não inventa nem deita fora). O sufixo '-ft' é aplicado depois.
    from app.services.tags_canonical import canonicalize_tag
    base_tag = canonicalize_tag(base_tag) or base_tag
    final_tag = _final_folder_tag(base_tag, vision_json)
    ft_source = _folder_tag_ft_source(base_tag, vision_json)   # pt73: 'manual'/'auto'/None
    own = conn is None
    try:
        if own:
            conn = get_conn()
        with conn.cursor() as cur:
            # pt73 — escreve a tag final + a proveniência do '-ft' (manual/auto).
            # COALESCE: não apaga um 'manual'/'auto' anterior quando ft_source=None.
            cur.execute(
                "UPDATE hands SET discord_tags = ARRAY(SELECT DISTINCT unnest("
                "COALESCE(discord_tags, '{}'::text[]) || %s::text[])), "
                "folder_ft_source = COALESCE(%s, folder_ft_source) WHERE id = %s",
                ([final_tag], ft_source, matched_hand_db_id),
            )
        if own:
            conn.commit()
        from app.services.villain_rules import apply_villain_rules
        apply_villain_rules(matched_hand_db_id, conn=conn)
        logger.info(
            "[table_ss_folder_tag] hand %s -> tag %r (ft_source=%s)",
            matched_hand_db_id, final_tag, ft_source,
        )
    except Exception as e:  # pragma: no cover - defensivo
        logger.error(
            "[table_ss_folder_tag] hand %s falhou: %s", matched_hand_db_id, e
        )
    finally:
        if own and conn is not None:
            conn.close()


def _reapply_folder_tag_on_dedup(matched_hand_id, folder_tag, vision_json, file_hash) -> None:
    """#DEDUP-DROPS-FOLDER-TAG (lote auditoria A1, Opção A). Um duplicado (mesmo
    file_hash de uma captura já bem-sucedida) reenviado COM `folder_tag` deitava a
    etiqueta fora (a via de dedup saía cedo). Aqui aplica-se a tag à mão JÁ casada
    e grava-se na row do log. Não re-corre Vision nem desanon. Idempotente:
    `_apply_folder_tag_to_hand` faz union distinct, logo uma tag já presente sai
    intacta; sem `folder_tag`/sem mão casada → no-op. Defensivo (nunca rebenta o upload)."""
    if not folder_tag or not matched_hand_id:
        return
    try:
        rows = query("SELECT id FROM hands WHERE hand_id = %s", (matched_hand_id,))
        if rows:
            _apply_folder_tag_to_hand(rows[0]["id"], folder_tag, vision_json)
        # A row do log passa a refletir a pasta (só preenche se estava vazia — Opção A:
        # não sobrescreve uma folder_tag diferente já lá).
        conn = get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE table_ss_processing_log SET folder_tag = %s "
                    "WHERE file_hash = %s AND folder_tag IS NULL",
                    (folder_tag, file_hash))
            conn.commit()
        finally:
            conn.close()
    except Exception as e:  # pragma: no cover - defensivo
        logger.error("[table_ss dedup] reaplicar folder_tag falhou (hand %s): %s",
                     matched_hand_id, e)


def _finalize(
    out: dict, *, source: str, original_filename: Optional[str],
    file_size: int, captured_at: Optional[datetime],
    matched_hand_db_id: Optional[int] = None,
    img_b64: Optional[str] = None,
    folder_tag: Optional[str] = None,
) -> dict:
    """Persiste o resultado e devolve `out`."""
    _upsert_table_ss_log(
        file_hash=out["file_hash"], source=source,
        original_filename=original_filename, file_size=file_size,
        result=out["result"], reason_detail=out["reason_detail"],
        site=out["site"], tournament_name=out["tournament_name"],
        tournament_number=out["tournament_number"],
        players_left=out["players_left"], total_entries=out["total_entries"],
        captured_at=captured_at, matched_hand_id=out["hand_matched"],
        vision_json=out["vision_json"], matched_hand_db_id=matched_hand_db_id,
        img_b64=img_b64, folder_tag=folder_tag,
    )
    # Estágio 3-b: após o link estar gravado, desanonimiza a mão GG casada.
    _deanon_after_match(matched_hand_db_id, out.get("vision_json"))
    # pt72 — pasta-como-tag: aplica a tag da subpasta do IT à mão casada (após o
    # de-anon, para a mão já ser table_ss quando as regras de vilão correm).
    _apply_folder_tag_to_hand(matched_hand_db_id, folder_tag, out.get("vision_json"))
    return out


async def _process_table_ss(
    content: bytes, filename: str, *,
    captured_at_override: Optional[str] = None, source: str = "manual_upload",
    folder_tag: Optional[str] = None,
) -> dict:
    """Pipeline de 1 SS de mesa. Devolve dict serializável de resultado.

    pt72 — `folder_tag` (pasta-como-tag do IT) é gravado no log e aplicado à mão
    casada (via `_finalize`). NB: a via de dedup (sucesso prévio) retorna cedo e
    NÃO re-aplica a tag — cada captura é processada uma vez (a tag entra aí)."""
    import asyncio

    file_hash = hashlib.sha256(content).hexdigest()
    out = _blank_out(file_hash)

    # 1. Dedup — sucesso prévio não re-corre a Vision (idempotente).
    existing = query(
        """SELECT result, site, tournament_name, tournament_number,
                  players_left, total_entries, matched_hand_id, captured_at,
                  vision_json
             FROM table_ss_processing_log WHERE file_hash = %s""",
        (file_hash,),
    )
    if existing and existing[0].get("result") == "success":
        e = dict(existing[0])
        # #DEDUP-DROPS-FOLDER-TAG (lote auditoria A1): um duplicado reenviado COM
        # folder_tag (ex.: print antes solto, agora na pasta SpeedRacer\) NÃO pode
        # deitar a etiqueta fora — aplica-a à mão JÁ casada antes de sair. Idempotente
        # (union distinct); sem re-correr Vision nem desanon. Opção A (Rui, 10 Jul).
        if folder_tag and e.get("matched_hand_id"):
            _reapply_folder_tag_on_dedup(
                e["matched_hand_id"], folder_tag, e.get("vision_json"), file_hash)
        out.update({
            "result": "success", "dedup": True,
            "site": e.get("site"), "tournament_name": e.get("tournament_name"),
            "tournament_number": e.get("tournament_number"),
            "players_left": e.get("players_left"),
            "total_entries": e.get("total_entries"),
            "hand_matched": e.get("matched_hand_id"),
            "captured_at": e["captured_at"].isoformat() if e.get("captured_at") else None,
            "vision_json": e.get("vision_json"),
            "reason_detail": "dedup: já processado com sucesso",
        })
        return out

    # 2. captured_at (override ISO > filename).
    captured_at = _parse_iso(captured_at_override) or tv.derive_captured_at(
        filename, tz_name=CAPTURE_TZ
    )
    out["captured_at"] = captured_at.isoformat() if captured_at else None
    fsize = len(content)

    # 2b. Imagem comprimida (1280/JPEG85, padrão dos replayers) — guardada na
    # linha para a triagem mostrar a SS ao lado da mão. Off-thread (PIL é CPU).
    img_b64, _ = await asyncio.to_thread(compress_image, content)

    # 3. Vision (off-thread — única chamada lenta/externa). pt73: vmeta apanha a
    # causa REAL da falha (ex. crédito Anthropic esgotado) p/ o reason_detail.
    mime = detect_image_mime(content)
    vmeta: dict = {}
    raw = await asyncio.to_thread(tv.extract_table_ss_json, content, mime, vmeta)
    if raw is None:
        out["result"] = "vision_failed"
        out["reason_detail"] = vmeta.get("error") or "extract_table_ss_json devolveu None"
        return _finalize(out, source=source, original_filename=filename,
                         file_size=fsize, captured_at=captured_at, img_b64=img_b64,
                         folder_tag=folder_tag)

    vj = tv.parse_and_validate_table_ss_json(raw)
    if vj is None:
        out["result"] = "json_invalid"
        out["reason_detail"] = "JSON inválido ou sem campos úteis"
        return _finalize(out, source=source, original_filename=filename,
                         file_size=fsize, captured_at=captured_at, img_b64=img_b64,
                         folder_tag=folder_tag)
    # #TABLE-SS-VISION-SITE-MISCLASS: corrige a site lida quando o nome a
    # contradiz (Regra A `#NNN` trailing + Regra B cross-check BD), ANTES de
    # gravar a site no log e de filtrar candidatos por site.
    # pt56: o NOME do ficheiro é a fonte AUTORITÁRIA do site (determinístico).
    # Se o nome dá token → ignora o que a Vision leu. Senão → fallback Vision
    # (+ _correct_site) e loga (para vermos quantos).
    _parsed_fn = parse_table_ss_filename(filename)
    _fsite = _parsed_fn["site"]
    if _fsite:
        vj["site"] = _fsite
    else:
        vj["site"] = tv._correct_site(vj.get("tournament_name"), vj.get("site"))
        logger.info(
            "[table_ss_site] nome sem token reconhecível (%r) → fallback Vision=%s",
            filename, vj.get("site"),
        )
    # pt54: Winamax → nome canónico (remove '#NNN' nº de mesa + '(ID)' do nome).
    if vj.get("site") == "Winamax":
        vj["tournament_name"] = clean_winamax_tournament_name(vj.get("tournament_name"))[0]
    out["vision_json"] = vj
    out["site"] = vj.get("site")
    out["tournament_name"] = vj.get("tournament_name")
    out["players_left"] = vj.get("players_left")
    out["total_entries"] = vj.get("total_entries")

    # 4. Site gate.
    site = vj.get("site")
    if site not in ALLOWED_SITES:
        out["result"] = "site_undetected"
        out["reason_detail"] = f"site={site!r} não suportado"
        return _finalize(out, source=source, original_filename=filename,
                         file_size=fsize, captured_at=captured_at, img_b64=img_b64,
                         folder_tag=folder_tag)

    # 5. Match — função determinística ÚNICA R (a MESMA que o reconcile corre).
    #    O upload deixa de ter caminho de match próprio: grava o read e chama R.
    #    #TABLE-SS-FILENAME-TN: passa o tn do filename (autoritário) quando existe.
    desired = compute_table_ss_match(
        captured_at, site, vj, filename_tn=_parsed_fn["tournament_number"],
        filename=filename)
    out["site"] = desired["site"]          # R pode ter re-corrigido a site
    out["result"] = desired["result"]
    out["reason_detail"] = desired["reason_detail"]
    out["tournament_number"] = desired["tournament_number"]
    out["hand_matched"] = desired["matched_hand_id"]

    return _finalize(out, source=source, original_filename=filename,
                     file_size=fsize, captured_at=captured_at,
                     matched_hand_db_id=desired["matched_hand_db_id"],
                     img_b64=img_b64, folder_tag=folder_tag)


# ── pt73 — Recuperar capturas que falharam a Vision (sem re-feed de ficheiros) ─
# Quando a Vision falhou (ex. crédito Anthropic esgotado) a captura ficou
# `vision_failed` mas COM `img_b64` (imagem comprimida) + `folder_tag` +
# `original_filename` no log. Esta ferramenta re-corre a Vision sobre a imagem
# GUARDADA → parse → match HH → deanon + folder_tag, ACTUALIZANDO a MESMA row
# (por id). Idempotente: não duplica linhas (UPDATE in-place) nem mãos (table-SS
# LIGA, não cria). Vision OFF-THREAD + sequencial + throttle → não volta a afogar
# o worker (#SYNC-ENDPOINTS-SYNCHRONOUS-TIMEOUT) nem rebenta o rate-limit. É o
# espelho do post-Vision do upload, mas a partir do read guardado.

_REPROCESS_THROTTLE_S = 0.4   # pausa entre Visions (suaviza o rate-limit)


def _update_failed_reason(ss_id: int, reason: str, *, result: str = "vision_failed") -> None:
    """Actualiza só result/reason_detail (+ attempt_count) quando o reprocesso
    não chega a produzir um read utilizável (Vision ainda falha, JSON inválido,
    site não suportado). Não toca o link da mão."""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE table_ss_processing_log SET result=%s, reason_detail=%s, "
                "attempt_count = attempt_count + 1 WHERE id=%s",
                (result, reason, ss_id),
            )
        conn.commit()
    finally:
        conn.close()


def _store_recovered_vision(ss_id: int, vj: dict) -> None:
    """Grava o read Vision recuperado na row existente (vision_json + derivados).
    NÃO toca match/link — isso é o _persist_table_ss_match a seguir. dict→jsonb
    via o adapter global (app.db)."""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE table_ss_processing_log SET vision_json=%s, site=%s, "
                "tournament_name=%s, players_left=%s, total_entries=%s WHERE id=%s",
                (vj, vj.get("site"), vj.get("tournament_name"),
                 vj.get("players_left"), vj.get("total_entries"), ss_id),
            )
        conn.commit()
    finally:
        conn.close()


async def _reprocess_failed_row(row: dict) -> dict:
    """Re-corre a Vision sobre o img_b64 guardado de UMA captura `vision_failed`
    e refaz o pipeline post-Vision na MESMA row. Devolve {id, result, reason}."""
    import base64
    ss_id = row["id"]
    filename = row.get("original_filename") or ""
    folder_tag = row.get("folder_tag")
    captured_at = row.get("captured_at")
    out = {"id": ss_id, "result": None, "reason": None}
    import asyncio

    try:
        content = base64.b64decode(row["img_b64"])
    except Exception:
        _update_failed_reason(ss_id, "img_b64 inválido")
        out["result"] = "vision_failed"; out["reason"] = "img_b64 inválido"
        return out

    err: dict = {}
    raw = await asyncio.to_thread(tv.extract_table_ss_json, content, "image/jpeg", err)
    if _REPROCESS_THROTTLE_S:
        await asyncio.sleep(_REPROCESS_THROTTLE_S)
    if raw is None:
        _update_failed_reason(ss_id, err.get("error") or "vision_failed (reprocess)")
        out["result"] = "vision_failed"; out["reason"] = err.get("error")
        return out

    vj = tv.parse_and_validate_table_ss_json(raw)
    if vj is None:
        _update_failed_reason(ss_id, "JSON inválido ou sem campos úteis", result="json_invalid")
        out["result"] = "json_invalid"; out["reason"] = "JSON inválido"
        return out

    # Site AUTORITÁRIO do nome do ficheiro (pt56); fallback Vision + _correct_site.
    _parsed = parse_table_ss_filename(filename)
    if _parsed["site"]:
        vj["site"] = _parsed["site"]
    else:
        vj["site"] = tv._correct_site(vj.get("tournament_name"), vj.get("site"))
    if vj.get("site") == "Winamax":
        vj["tournament_name"] = clean_winamax_tournament_name(vj.get("tournament_name"))[0]

    _store_recovered_vision(ss_id, vj)

    site = vj.get("site")
    if site not in ALLOWED_SITES:
        _update_failed_reason(ss_id, f"site={site!r} não suportado", result="site_undetected")
        out["result"] = "site_undetected"; out["reason"] = f"site={site!r}"
        return out

    # Match determinístico (a MESMA função R do upload/reconcile) + persist + link.
    desired = compute_table_ss_match(
        captured_at, site, vj, filename_tn=_parsed["tournament_number"],
        filename=filename)
    _persist_table_ss_match(
        ss_id, desired, prev_result="vision_failed", prev_matched_hand_id=None)
    if desired["result"] == "success":
        _deanon_after_match(desired["matched_hand_db_id"], vj)
        _apply_folder_tag_to_hand(desired["matched_hand_db_id"], folder_tag, vj)
    out["result"] = desired["result"]
    out["reason"] = desired["reason_detail"]
    return out


# ── Endpoints ────────────────────────────────────────────────────────────────

@router.post("/upload")
async def upload_table_ss(
    file: UploadFile = File(...),
    filename: Optional[str] = Form(None),
    captured_at: Optional[str] = Form(None),
    source: str = Form("manual_upload"),
    folder_tag: Optional[str] = Form(None),
    current_user=Depends(require_auth),
):
    """Upload de 1 SS de mesa (manual UI ou cliente automático). Cookie auth.

    pt72 — `folder_tag` (opcional, pasta-como-tag do IT): a subpasta de captura é
    a tag de estudo; o backend aplica-a à mão casada (+ '-ft' se mesa final)."""
    content = await file.read()
    if not content:
        raise HTTPException(400, "Ficheiro vazio")
    fname = filename or file.filename or "upload.png"
    return await _process_table_ss(
        content, fname, captured_at_override=captured_at, source=source,
        folder_tag=(folder_tag or "").strip() or None,
    )


@router.post("/attach-to-hand")
async def attach_ss_to_hand(
    file: UploadFile = File(...),
    hand_id: str = Form(...),
    filename: Optional[str] = Form(None),
    current_user=Depends(require_auth),
):
    """OBRA 2b (cartão de conflito de nomes na Saúde GG): o Rui anexa uma Gold/captura
    do disco a uma mão ESCOLHIDA (que a app não tinha imagem — ex. a forte GG-6083716159).
    Corre a Vision (persiste a captura com a imagem), depois FORÇA o link a essa mão
    reusando `_manual_link_ss` (o mesmo primitivo da Ação 2 das órfãs): Gold-manda no
    deanon (salta se já `position_v3`), aplica a folder-tag, e liga
    `hands.context_table_ss_id` → a miniatura passa a aparecer no lado do conflito.
    Idempotente (dedup por file_hash). A app NÃO adivinha a mão — vem do Rui."""
    content = await file.read()
    if not content:
        raise HTTPException(400, "Ficheiro vazio")
    fname = filename or file.filename or "attach.png"
    # 1) Vision + persist (o matcher automático pode não casar; forçamos a seguir).
    await _process_table_ss(content, fname, source="manual_attach")
    # 2) ss_id da row acabada de gravar (chave = file_hash).
    fh = hashlib.sha256(content).hexdigest()
    rows = query("SELECT id FROM table_ss_processing_log WHERE file_hash=%s", (fh,))
    if not rows:
        raise HTTPException(500, "captura não gravada")
    ss_id = rows[0]["id"]
    # 3) força o link à mão ESCOLHIDA pelo Rui (deanon salta se já position_v3).
    try:
        res = _manual_link_ss(ss_id, hand_id)
    except ValueError as e:
        raise HTTPException(404, str(e))
    return {"ok": True, "ss_id": ss_id,
            "image_url": f"/api/table-ss/image/{ss_id}", **res}


@router.get("/image/{ss_id}")
def table_ss_image(ss_id: int, current_user=Depends(require_auth)):
    """Serve a imagem comprimida (JPEG) guardada para uma SS de mesa.

    Endpoint espelho do `GET /api/screenshots/image/{id}` dos replayers — a
    triagem mostra a SS ao lado da mão. mime detectado dos bytes (robusto ao
    fallback fail-safe do `compress_image`). 404 se a linha não tem imagem."""
    rows = query(
        "SELECT img_b64 FROM table_ss_processing_log WHERE id = %s", (ss_id,)
    )
    if not rows or not rows[0].get("img_b64"):
        raise HTTPException(404, "Sem imagem para esta SS")
    import base64
    try:
        raw = base64.b64decode(rows[0]["img_b64"])
    except Exception:
        raise HTTPException(404, "Imagem inválida")
    return Response(
        content=raw, media_type=detect_image_mime(raw),
        headers={"Cache-Control": "private, max-age=86400"},
    )


@router.post("/reconcile")
def trigger_reconcile_table_ss(current_user=Depends(require_auth_or_api_key)):
    """Corre o reconcile R sobre TODAS as SS de mesa (recalcula match de raiz,
    re-persiste, inclui as `tm_ambiguous`/`no_match_to_hand`). Síncrono mas leve
    (consultas + updates, sem Vision). Usado p.ex. após backfill de nomes para
    re-ligar as SS já importadas (#FIX-B3 + pt54). Devolve o tally."""
    return reconcile_table_ss(hand_ids=None)


# ── #GG-HEALTH-ACTIONS — Ações 2/3: linkar captura à mão + decisão de troca ───

def _manual_link_ss(ss_id: int, hand_id: Optional[str]) -> dict:
    """Liga (ou desliga, hand_id=None) uma captura table-SS a uma mão ESCOLHIDA
    manualmente, reusando O MATCHER (persist + link + deanon com Gold-manda + tag).
    NÃO adivinha (a mão vem do Rui). Reversível: re-chamar com outra mão / None.
    Levanta ValueError('ss_not_found'|'hand_not_found')."""
    rows = query(
        "SELECT id, site, vision_json, folder_tag, result, matched_hand_id "
        "FROM table_ss_processing_log WHERE id=%s", (ss_id,))
    if not rows:
        raise ValueError("ss_not_found")
    r = rows[0]
    if hand_id:
        h = query("SELECT id, hand_id, tournament_number FROM hands WHERE hand_id=%s",
                  (hand_id,))
        if not h:
            raise ValueError("hand_not_found")
        h = h[0]
        desired = {"result": "success", "reason_detail": "manual_link", "site": r["site"],
                   "tournament_number": h["tournament_number"],
                   "matched_hand_id": h["hand_id"], "matched_hand_db_id": h["id"]}
    else:
        desired = {"result": "no_match_to_hand", "reason_detail": "manual_unlink",
                   "site": r["site"], "tournament_number": None,
                   "matched_hand_id": None, "matched_hand_db_id": None}
    _persist_table_ss_match(ss_id, desired, prev_result=r["result"],
                            prev_matched_hand_id=r["matched_hand_id"])
    if desired["result"] == "success":
        # Gold manda: _deanon_after_match salta se a mão já tem position_v3.
        _deanon_after_match(desired["matched_hand_db_id"], r["vision_json"])
        _apply_folder_tag_to_hand(desired["matched_hand_db_id"], r["folder_tag"],
                                  r["vision_json"])
    return {"result": desired["result"], "matched_hand_id": desired["matched_hand_id"]}


def _set_swap_review(ss_id: int, value: Optional[str]) -> None:
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("UPDATE table_ss_processing_log SET swap_review=%s WHERE id=%s",
                        (value, ss_id))
        conn.commit()
    finally:
        conn.close()


@router.post("/{ss_id}/link")
def link_table_ss(ss_id: int, payload: dict = Body(...),
                  current_user=Depends(require_auth_or_api_key)):
    """Ação 2 (órfãs) — liga a captura à mão ESCOLHIDA pelo Rui (a app NÃO adivinha
    pelo número do ficheiro). Gold manda. Reversível: re-link, ou hand_id=null →
    desliga. Idempotente. Body: {hand_id: 'GG-...'|null}."""
    try:
        return _manual_link_ss(ss_id, payload.get("hand_id"))
    except ValueError as e:
        raise HTTPException(404, str(e))


@router.post("/{ss_id}/swap-review")
def swap_review_table_ss(ss_id: int, payload: dict = Body(...),
                         current_user=Depends(require_auth_or_api_key)):
    """Ação 3 (suspeita de troca) — decisão do Rui. Body: {decision}.
    'accept' → move a captura para GG-<nº do ficheiro> (reusa o link) + marca
    'moved'. 'reject' → fica onde está, marca 'kept' (sai do painel). 'review' →
    limpa a marca (por rever)."""
    decision = payload.get("decision")
    rows = query("SELECT id, original_filename FROM table_ss_processing_log WHERE id=%s",
                 (ss_id,))
    if not rows:
        raise HTTPException(404, "captura não existe")
    if decision == "accept":
        num = _parse_it_hand_fields(rows[0]["original_filename"])["hand_num"]
        if not num or len(num) < 10:
            raise HTTPException(422, "nº do ficheiro truncado/ausente — sem ACEITAR automático")
        try:
            res = _manual_link_ss(ss_id, f"GG-{num}")
        except ValueError as e:
            raise HTTPException(404, str(e))
        _set_swap_review(ss_id, "moved")
        return {"decision": "accept", **res}
    if decision == "reject":
        _set_swap_review(ss_id, "kept")
        return {"decision": "reject"}
    if decision == "review":
        _set_swap_review(ss_id, None)
        return {"decision": "review"}
    raise HTTPException(400, "decision inválida (accept|reject|review)")


# ── Fase 1 do editor Saúde GG (A: suspeitas 2-candidatas + revert; E: verificada) ──

def _revert_hand_to_anonymous(hand_db_id: int) -> dict:
    """Primitiva "reverter mão à anónima" (Fase 1-A). Repõe o apa HASH-keyed do raw,
    limpa `player_names` ({}), apaga `hand_villains` e desliga `context_table_ss_id`.

    ⚠️ GUARDA (Gold-manda / Discord prevalece): só reverte se `match_method=='table_ss'`
    (a desanon veio de uma captura table-SS). `position_v3` (Gold), Discord, ou null →
    NÃO toca (devolve `reverted=False`). Reversível: re-ligar a captura re-deriva.
    Devolve {reverted, match_method, reason?}."""
    import json as _json
    from app.parsers.gg_hands import parse_hands
    rows = query("SELECT raw, player_names FROM hands WHERE id=%s", (hand_db_id,))
    if not rows:
        return {"reverted": False, "reason": "hand_not_found"}
    pn = rows[0]["player_names"] or {}
    if isinstance(pn, str):
        try:
            pn = _json.loads(pn)
        except (ValueError, TypeError):
            pn = {}
    mm = pn.get("match_method")
    if mm != "table_ss":                       # Gold/Discord/anónima → não tocar
        return {"reverted": False, "reason": "not_table_ss", "match_method": mm}
    raw = rows[0]["raw"] or ""
    parsed, _errs = parse_hands(raw.encode("utf-8"), "revert.txt")
    if not parsed or not parsed[0].get("all_players_actions"):
        return {"reverted": False, "reason": "reparse_failed", "match_method": mm}
    fresh_apa = parsed[0]["all_players_actions"]
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE hands SET all_players_actions=%s, player_names='{}'::jsonb, "
                "context_table_ss_id=NULL WHERE id=%s",
                (_json.dumps(fresh_apa), hand_db_id))
            cur.execute("DELETE FROM hand_villains WHERE hand_db_id=%s", (hand_db_id,))
        conn.commit()
    finally:
        conn.close()
    logger.info("revert-to-anon: hand %s revertida (era table_ss)", hand_db_id)
    return {"reverted": True, "match_method": mm}


def _hand_seats_for_id(hand_db_id: int) -> list:
    """Seats de uma mão (do apa) p/ comparar com a captura: seat·posição·stack·nick·hero.
    Nick só se mapeado (senão hash em `raw_hash`). Mesmo formato do `/hand-seats`."""
    import json as _json
    rows = query("SELECT all_players_actions apa, player_names pn FROM hands WHERE id=%s",
                 (hand_db_id,))
    if not rows:
        return []
    apa = rows[0]["apa"] or {}
    pn = rows[0]["pn"] or {}
    if isinstance(apa, str):
        apa = _json.loads(apa)
    if isinstance(pn, str):
        pn = _json.loads(pn)
    mapped = set((pn.get("anon_map") or {}).values())
    seats = []
    for k, info in apa.items():
        if k == "_meta" or not isinstance(info, dict):
            continue
        name = info.get("real_name", k)
        is_mapped = name in mapped
        seats.append({
            "seat": info.get("seat"), "position": info.get("position"),
            "nick": name if is_mapped else None,
            "raw_hash": None if is_mapped else name,
            "stack": info.get("stack"), "stack_bb": info.get("stack_bb"),
            "is_hero": bool(info.get("is_hero")), "mapped": is_mapped,
        })
    seats.sort(key=lambda s: (s["seat"] is None, s["seat"] if s["seat"] is not None else 0))
    return seats


@router.get("/{ss_id}/swap-candidates")
def swap_candidates(ss_id: int, current_user=Depends(require_auth_or_api_key)):
    """Fase 1-A (PRÉ-VISUALIZAÇÃO, read-only): as DUAS mãos candidatas de uma suspeita
    de troca, p/ o Rui escolher a dona certa da captura. (a) `current` = a mão ligada
    AGORA (matched_hand_id); (b) `filename` = a mão do NÚMERO do ficheiro (GG-<num>).
    Cada uma com os seats (posição/stack/nick) p/ comparar com a imagem."""
    rows = query("SELECT id, original_filename, matched_hand_id FROM "
                 "table_ss_processing_log WHERE id=%s", (ss_id,))
    if not rows:
        raise HTTPException(404, "captura não existe")
    r = rows[0]
    fnum = _parse_it_hand_fields(r["original_filename"])["hand_num"]
    filename_hand_id = f"GG-{fnum}" if fnum and len(fnum) >= 10 else None

    def _cand(hid, role):
        if not hid:
            return {"role": role, "hand_id": None, "exists": False, "seats": []}
        hr = query("SELECT id, (player_names->>'match_method') mm FROM hands WHERE hand_id=%s",
                   (hid,))
        if not hr:
            return {"role": role, "hand_id": hid, "exists": False, "seats": []}
        return {"role": role, "hand_id": hid, "hand_db_id": hr[0]["id"], "exists": True,
                "match_method": hr[0]["mm"], "seats": _hand_seats_for_id(hr[0]["id"])}

    return {
        "capture": {"ss_id": ss_id, "image_url": f"/api/table-ss/image/{ss_id}",
                    "filename": r["original_filename"], "filename_num": fnum},
        "candidates": [_cand(r["matched_hand_id"], "current"),
                       _cand(filename_hand_id, "filename")],
        "same_hand": bool(filename_hand_id) and filename_hand_id == r["matched_hand_id"],
    }


@router.post("/{ss_id}/resolve-owner")
def resolve_owner(ss_id: int, payload: dict = Body(...),
                  current_user=Depends(require_auth_or_api_key)):
    """Fase 1-A (DECISÃO): o Rui escolhe a DONA certa da captura (`owner_hand_id`) entre
    as 2 candidatas (ou null = nenhuma/desligar). O movimento INCLUI a limpeza da mão
    antiga: se a mão que tinha a captura (`matched_hand_id`) era `table_ss` e deixa de
    ser a dona, é REVERTIDA à anónima (fecha o buraco do Aceitar). Liga a nova via o
    matcher (`_manual_link_ss`; Gold-manda intacto — salta se a nova é `position_v3`).
    `dry_run=true` → só o plano, não grava. Body: {owner_hand_id: 'GG-...'|null, dry_run}."""
    owner = payload.get("owner_hand_id")
    dry = bool(payload.get("dry_run"))
    rows = query("SELECT id, matched_hand_id FROM table_ss_processing_log WHERE id=%s", (ss_id,))
    if not rows:
        raise HTTPException(404, "captura não existe")
    current = rows[0]["matched_hand_id"]
    if owner:                                   # owner tem de existir
        hr = query("SELECT id FROM hands WHERE hand_id=%s", (owner,))
        if not hr:
            raise HTTPException(422, f"mão {owner} não existe na base")
    # A antiga a reverter = a que tem a captura AGORA, se != owner E se for table_ss.
    revert_plan = None
    if current and current != owner:
        cr = query("SELECT id, (player_names->>'match_method') mm FROM hands WHERE hand_id=%s",
                   (current,))
        if cr and cr[0]["mm"] == "table_ss":
            revert_plan = {"hand_id": current, "hand_db_id": cr[0]["id"], "match_method": "table_ss"}
    plan = {"ss_id": ss_id, "current_hand": current, "owner": owner,
            "will_link": owner, "will_revert": revert_plan, "keep": (owner == current)}
    if dry:
        return {"dry_run": True, "plan": plan}
    if owner == current:                        # a ligação actual está certa → confirma
        _set_swap_review(ss_id, "kept")
        return {"decision": "kept", "plan": plan}
    if revert_plan:                             # limpa a antiga (embutido no movimento)
        _revert_hand_to_anonymous(revert_plan["hand_db_id"])
    try:
        res = _manual_link_ss(ss_id, owner)     # owner=None → desliga
    except ValueError as e:
        raise HTTPException(404, str(e))
    _set_swap_review(ss_id, "moved")
    return {"decision": "moved", "plan": plan, "link": res}


@router.post("/verify-deanon")
def verify_deanon(payload: dict = Body(...),
                  current_user=Depends(require_auth_or_api_key)):
    """Fase 1-E: marca/desmarca uma mão como VERIFICADA por mim (Rui). Escreve o flag
    ADITIVO `player_names.verified_by_user`; o `deanon_status` passa a 'verified' (o badge
    ⚠ some). NÃO toca anon_map/apa/match_method/vilões — só o flag. Cura o downgrade do
    `/set-anon-map` (mão editada à mão fica verificada por ti). Reversível
    (verified=false remove). Body: {hand_id, verified: bool (default true)}."""
    import json as _json
    hand_id = payload.get("hand_id")
    verified = payload.get("verified", True)
    if not hand_id:
        raise HTTPException(400, "hand_id obrigatório")
    rows = query("SELECT id, site, player_names FROM hands WHERE hand_id=%s", (hand_id,))
    if not rows:
        raise HTTPException(404, "mão não encontrada")
    pn = rows[0]["player_names"] or {}
    if isinstance(pn, str):
        try:
            pn = _json.loads(pn)
        except (ValueError, TypeError):
            pn = {}
    if verified:
        pn["verified_by_user"] = True
    else:
        pn.pop("verified_by_user", None)
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("UPDATE hands SET player_names=%s WHERE id=%s",
                        (_json.dumps(pn), rows[0]["id"]))
        conn.commit()
    finally:
        conn.close()
    from app.services.deanon_status import deanon_status_from_row
    status = deanon_status_from_row({"site": rows[0]["site"], "player_names": pn})
    return {"status": "set", "hand_id": hand_id,
            "verified_by_user": bool(verified), "deanon_status": status}


def _reparse_apa_hash_keyed(hand_db_id: int) -> bool:
    """pt95 (#REDEANON-NOT-IDEMPOTENT, restauro): re-deriva o `all_players_actions`
    HASH-keyed do raw HH (via parser GG) e remove o `anon_map`. Restaura mãos cujo
    apa ficou name-keyed (e o anon_map name→name) por re-corridas do /redeanon — a
    ÚNICA fonte de verdade dos hashes é o raw HH. Devolve True se restaurou."""
    import json as _json
    from app.parsers.gg_hands import parse_hands
    rows = query("SELECT raw FROM hands WHERE id = %s", (hand_db_id,))
    if not rows or not (rows[0]["raw"] or "").strip():
        return False
    parsed, _errs = parse_hands(rows[0]["raw"].encode("utf-8"), "reparse.txt")
    if not parsed:
        return False
    fresh_apa = parsed[0].get("all_players_actions") or {}
    if not [k for k in fresh_apa if k != "_meta"]:
        return False
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE hands SET all_players_actions = %s, "
                "player_names = (COALESCE(player_names, '{}'::jsonb) - 'anon_map') "
                "WHERE id = %s",
                (_json.dumps(fresh_apa), hand_db_id),
            )
        conn.commit()
    finally:
        conn.close()
    return True


@router.post("/redeanon")
def force_redeanon_table_ss(payload: dict = Body(...),
                            current_user=Depends(require_auth_or_api_key)):
    """pt93 (#HRC-REIMPORT-REDEANON-CASADAS, caso pontual): força a re-corrida da
    desanon por table-SS para mãos `hand_ids` ESPECÍFICAS cuja SS já está casada
    (success) mas o `anon_map` ficou VAZIO — um re-import de HH esvaziou-o sem
    re-disparar a desanon (o `reconcile` só re-corre quando o MATCH muda, e este
    não mudou). MESMO matcher (não muda nada nele) — só re-corre sobre os seats
    guardados. Caso real: GG-6113994321 (PKO com bounty achatado no solve).
    Body: {hand_ids:[...]}. Devolve {redeanon, skipped}."""
    hand_ids = payload.get("hand_ids") or []
    reparse = bool(payload.get("reparse"))   # pt95: restaura apa hash-keyed do raw 1º
    if not isinstance(hand_ids, list) or not hand_ids:
        raise HTTPException(400, "hand_ids (lista não-vazia) obrigatório")
    if len(hand_ids) > 200:
        raise HTTPException(400, "máximo 200 mãos por chamada")
    from app.services.table_ss_deanon import deanonymize_hand_from_table_ss
    done, skipped = [], []
    for hid in hand_ids:
        hrows = query("SELECT id FROM hands WHERE hand_id = %s", (hid,))
        if not hrows:
            skipped.append({"hand_id": hid, "reason": "mão não encontrada"})
            continue
        srows = query(
            "SELECT vision_json FROM table_ss_processing_log "
            "WHERE matched_hand_id = %s AND result = 'success' "
            "AND vision_json IS NOT NULL ORDER BY id DESC LIMIT 1",
            (hid,),
        )
        if not srows:
            skipped.append({"hand_id": hid, "reason": "sem table-SS casada (success)"})
            continue
        vj = srows[0]["vision_json"]
        if isinstance(vj, str):
            import json as _json
            try:
                vj = _json.loads(vj)
            except (ValueError, TypeError):
                vj = {}
        seats = (vj or {}).get("seats") or []
        if not seats:
            skipped.append({"hand_id": hid, "reason": "table-SS sem seats"})
            continue
        if reparse:
            _reparse_apa_hash_keyed(hrows[0]["id"])   # pt95: apa hash-keyed do raw 1º
        res = deanonymize_hand_from_table_ss(
            hrows[0]["id"], seats, (vj or {}).get("hero_nick"))
        done.append({"hand_id": hid, "status": res.get("status"),
                     "mapped": res.get("mapped"),
                     "deanon_partial": res.get("deanon_partial")})
    logger.info("table-ss redeanon: done=%d skipped=%d", len(done), len(skipped))
    return {"redeanon": done, "skipped": skipped}


def _assert_no_duplicate_real_names(anon_map: dict) -> None:
    """Guarda (b) mínima (APA §B.6.3) no ponto de escrita MANUAL do anon_map: o
    MESMO real_name atribuído a 2+ chaves é veneno — pelo invariante do hash (2
    hashes = 2 pessoas), um dos nomes está errado. Rejeita ANTES de gravar. É o
    único sítio onde um humano pode introduzir o duplicado; a quarentena completa
    (nome-já-usado por torneio) é a Fase 3. Valores vazios ("" = por mapear) ignoram-se.
    Substitui a antiga guarda pós-enrich (`len(enriched)!=len(hashes)`), que dava
    dead-code na Fase 2 (a chave-hash já nunca funde)."""
    seen: dict = {}
    for key, name in (anon_map or {}).items():
        if not name:
            continue
        if name in seen:
            raise HTTPException(
                409,
                f"nome '{name}' atribuído a 2 lugares ({seen[name]} e {key}) — "
                f"um deles está errado. Não gravado.",
            )
        seen[name] = key


@router.post("/set-anon-map")
def set_anon_map_override(payload: dict = Body(...),
                          current_user=Depends(require_auth_or_api_key)):
    """pt95: override MANUAL do anon_map (hash→nick) de UMA mão GG, quando a desanon
    automática COLOU seats (ex. GG-6113994321: o stack-match deu a um vilão o nome do
    Hero). Ancora-se nas BLINDS (decisão do Rui via gold+HH), não no stack. Re-deriva
    o apa HASH-keyed do raw, aplica o mapa DADO, escreve player_names + apa enriquecido,
    re-dispara villain_rules. VALIDA nicks DISTINTOS (recusa seats colados).
    Body: {hand_id, anon_map:{hash:nick,"Hero":nick}, bounties?:{nick:coroa_usd}}.
    Bounties (coroa $ da gold) corrigem a leitura errada do table-SS Vision."""
    import json as _json
    from app.routers.screenshot import _enrich_all_players_actions
    hand_id = payload.get("hand_id")
    anon_map = payload.get("anon_map") or {}
    if not hand_id or not isinstance(anon_map, dict) or not anon_map:
        raise HTTPException(400, "hand_id + anon_map (dict não-vazio) obrigatórios")
    vals = list(anon_map.values())
    _assert_no_duplicate_real_names(anon_map)   # guarda (b) mínima (APA §B.6.3)
    hrows = query("SELECT id FROM hands WHERE hand_id = %s", (hand_id,))
    if not hrows:
        raise HTTPException(404, "mão não encontrada")
    hand_db_id = hrows[0]["id"]
    if not _reparse_apa_hash_keyed(hand_db_id):
        raise HTTPException(422, "re-parse do raw falhou (sem HH?)")
    rows = query("SELECT all_players_actions apa, player_names pn, raw FROM hands WHERE id = %s",
                 (hand_db_id,))
    apa = rows[0]["apa"]; pn = rows[0]["pn"]; _raw = rows[0].get("raw")
    if isinstance(apa, str):
        apa = _json.loads(apa)
    if isinstance(pn, str):
        pn = _json.loads(pn)
    pn = pn or {}
    # pt95: override dos bounties pela COROA $ da gold (a coroa DOURADA = bounty em $;
    # corrige leitura errada do table-SS Vision, que pôs valores que não batem com a
    # coroa). ⚠️ NÃO é a chama LARANJA = VPIP (CLAUDE.md). Body: {nick: coroa_usd}.
    bounties = payload.get("bounties") or {}
    if bounties:
        pl = pn.get("players_list") or []
        for _e in pl:
            if _e.get("name") in bounties:
                _e["bounty_value_usd"] = bounties[_e["name"]]
        pn["players_list"] = pl
    hashes = [k for k in apa if k != "_meta"]
    missing = [h for h in hashes if h not in anon_map]
    vision_data = {"players_list": (pn or {}).get("players_list") or []}
    enriched = _enrich_all_players_actions(apa, anon_map, vision_data)
    # Guarda universal (#DESANON-SITTING-OUT-NPLUS1) — aqui em modo WARN (override MANUAL:
    # o mapa do Rui manda; se ficar inconsistente com o raw, é sinal de que o mapa dado
    # está torto). O C2 (nome duplicado) já foi barrado à entrada por _assert_no_duplicate.
    from app.services.table_ss_deanon import assert_deanon_consistency
    _cl, _cv = assert_deanon_consistency(_raw, enriched, anon_map)
    if _cl == "block":
        logger.warning("table-ss set-anon-map: hand %s inconsistente=%s (override MANUAL — grava na mesma)",
                       hand_id, _cv)
    # APA §B (Fase 2): a fusão de seats já não pode acontecer (o enrich mantém a
    # chave-hash); o duplicado de nome é barrado À ENTRADA por
    # _assert_no_duplicate_real_names (guarda viva que substitui a antiga pós-enrich).
    new_pn = {**(pn or {}), "anon_map": anon_map, "match_method": "table_ss",
              "source": "manual_blinds_override", "deanon_partial": bool(missing)}
    # O Hero do anon_map é autoritário — repõe também o campo pn.hero (a desanon
    # errada podia tê-lo deixado com o nick de um vilão; ex. swap R Sanchez↔Lauro).
    if anon_map.get("Hero"):
        new_pn["hero"] = anon_map["Hero"]
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("UPDATE hands SET all_players_actions = %s, player_names = %s "
                        "WHERE id = %s",
                        (_json.dumps(enriched), _json.dumps(new_pn), hand_db_id))
        conn.commit()
    finally:
        conn.close()
    try:
        from app.services.villain_rules import apply_villain_rules
        apply_villain_rules(hand_db_id)
    except Exception as e:  # pragma: no cover - defensivo
        logger.error("apply_villain_rules falhou hand %s: %s", hand_db_id, e)
    logger.info("table-ss set-anon-map: %s mapped=%d distinct=%d partial=%s",
                hand_id, len(anon_map), len(set(vals)), bool(missing))
    return {"status": "set", "hand_id": hand_id, "mapped": len(anon_map),
            "hashes": len(hashes), "missing": missing,
            "distinct_nicks": len(set(vals)), "deanon_partial": bool(missing)}


@router.post("/revert-to-anon")
def revert_to_anon(payload: dict = Body(...),
                   current_user=Depends(require_auth_or_api_key)):
    """Reverte UMA mão GG à ANÓNIMA (primitiva `_revert_hand_to_anonymous`, exposta pt97+).
    Uso: prints PÓS-BUST / sem o Rui visível que a desanon antiga (pré-guarda 11 Jul)
    ancorou num vilão → o Hero ficou com o nick do vilão (#DESANON-ANCHOR-REQUIRES-HERO-IN-IMAGE).
    Repõe o apa HASH-keyed do raw, limpa `player_names` ({}), apaga `hand_villains` e
    desliga `context_table_ss_id`. GUARDA: só toca se `match_method=='table_ss'` (Gold/
    Discord/anónima → devolve reverted=False). Reversível: um print COM o Rui re-desanon.
    Body: {hand_id}."""
    hand_id = (payload or {}).get("hand_id")
    if not hand_id:
        raise HTTPException(400, "hand_id obrigatório")
    rows = query("SELECT id FROM hands WHERE hand_id = %s", (hand_id,))
    if not rows:
        raise HTTPException(404, "mão não encontrada")
    res = _revert_hand_to_anonymous(rows[0]["id"])
    logger.info("table-ss revert-to-anon: %s -> %s", hand_id, res)
    return {"hand_id": hand_id, **res}


@router.get("/folder-tags")
def folder_tags_by_filename(current_user=Depends(require_auth)):
    """#ICM-FT-TAG-NOT-LANDING — mapa `original_filename → folder_tag` das capturas que
    trazem tag (folder_tag não-nulo). Read-only. Serve a arrumação do `done\\it` achatado
    (script local `tidy_done_it.py`): a BD é a fonte de verdade de que pasta cada print veio.
    Nomes de ficheiro repetidos ficam com a última tag vista (raro; a mesma captura reprocessada)."""
    rows = query(
        "SELECT original_filename, folder_tag FROM table_ss_processing_log "
        " WHERE folder_tag IS NOT NULL AND original_filename IS NOT NULL")
    m = {}
    for r in rows:
        m[r["original_filename"]] = r["folder_tag"]
    return {"count": len(m), "map": m}


@router.post("/set-bounties")
def set_bounties_override(payload: dict = Body(...),
                          current_user=Depends(require_auth_or_api_key)):
    """pt95 (#TABLE-SS-BOUNTY-UNDERREAD) + Fase 2: override MANUAL das coroas ($) de UMA
    mão, por nick. Actualiza `player_names.players_list[*].bounty_value_usd` **E**
    `all_players_actions[nick].bounty_value_usd` (os 2 stores — display/IRE lêem o apa,
    suspeitas/HRC lêem o players_list; ficam coerentes). Fase 2 aceita também:
    - `confirm: [nick,...]`  → marca `bounty_confirmed=true` (aceita a coroa <½-base como
      legítima; sai das suspeitas e do gate ½-base do HRC — exceção manual registada).
    - `unconfirm: [nick,...]` → remove o flag.
    - `dry_run: true` → devolve o PLANO (valores antes/depois + confirmações), não grava.
    Nicks ausentes do players_list ficam intactos + devolvidos em `not_found` (não se
    inventa). Body: {hand_id, bounties?:{nick:coroa}, confirm?:[], unconfirm?:[], dry_run?}."""
    import json as _json
    hand_id = payload.get("hand_id")
    bounties = payload.get("bounties") or {}
    confirm = [n for n in (payload.get("confirm") or [])]
    unconfirm = [n for n in (payload.get("unconfirm") or [])]
    dry = bool(payload.get("dry_run"))
    if not hand_id or (not bounties and not confirm and not unconfirm):
        raise HTTPException(400, "hand_id + (bounties|confirm|unconfirm) obrigatórios")
    rows = query("SELECT id, all_players_actions, player_names FROM hands WHERE hand_id = %s",
                 (hand_id,))
    if not rows:
        raise HTTPException(404, "mão não encontrada")
    pn = rows[0]["player_names"] or {}
    apa = rows[0]["all_players_actions"] or {}
    if isinstance(pn, str):
        pn = _json.loads(pn)
    if isinstance(apa, str):
        apa = _json.loads(apa)
    pl = pn.get("players_list") or []
    # APA §B.2 (Fase 1): mapa nome→entrada por real_name || chave (byte-idêntico hoje;
    # em Fase 2 a chave do apa é o hash e o patch continua a bater pelo nome real).
    apa_by_name = {(v.get("real_name") or k): v
                   for k, v in apa.items() if k != "_meta" and isinstance(v, dict)}
    updated, confirmed, unconfirmed, plan = [], [], [], []
    touched = set(bounties) | set(confirm) | set(unconfirm)
    for e in pl:
        nm = e.get("name")
        if nm not in touched:
            continue
        entry = {"name": nm, "old": e.get("bounty_value_usd"),
                 "was_confirmed": bool(e.get("bounty_confirmed"))}
        if nm in bounties:
            try:
                val = float(bounties[nm])
                if not dry:
                    e["bounty_value_usd"] = val
                    if nm in apa_by_name:
                        apa_by_name[nm]["bounty_value_usd"] = val
                entry["new"] = val
                updated.append(nm)
            except (ValueError, TypeError):
                entry["error"] = "valor inválido"
        if nm in confirm:
            if not dry:
                e["bounty_confirmed"] = True
            entry["confirm"] = True
            confirmed.append(nm)
        if nm in unconfirm:
            if not dry:
                e.pop("bounty_confirmed", None)
            entry["confirm"] = False
            unconfirmed.append(nm)
        plan.append(entry)
    not_found = [n for n in touched if n not in {p["name"] for p in plan}]
    if dry:
        return {"dry_run": True, "hand_id": hand_id, "plan": plan, "not_found": not_found}
    pn["players_list"] = pl
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("UPDATE hands SET player_names=%s, all_players_actions=%s WHERE id=%s",
                        (_json.dumps(pn), _json.dumps(apa), rows[0]["id"]))
        conn.commit()
    finally:
        conn.close()
    logger.info("table-ss set-bounties: %s updated=%d confirmed=%d unconfirmed=%d not_found=%d",
                hand_id, len(updated), len(confirmed), len(unconfirmed), len(not_found))
    return {"status": "set", "hand_id": hand_id, "updated": updated,
            "confirmed": confirmed, "unconfirmed": unconfirmed, "not_found": not_found}


# ── Varrimento de integridade de lugares (READ-ONLY) — padrão da GG-6118579134 ──
_SEAT_LINE_RE = re.compile(r"^\s*Seat\s+(\d+):\s*(.+?)\s*\(([\d,]+)\s+in chips\)", re.M)


def _scan_hand_integrity(raw, apa, pn):
    """Pura. Deteta o padrão da GG-6118579134 numa mão:
    A) nº de linhas Seat (com fichas) no raw != nº de lugares no apa;
    B) hashes do raw ausentes do anon_map (ignora 'Hero') — só se HÁ anon_map;
    C) nomes do players_list ausentes dos VALORES do anon_map — só se HÁ anon_map.
    B/C exigem anon_map não-vazio: sem anon_map a mão está 'ainda anónima', não 'partida'."""
    if isinstance(apa, str):
        try:
            apa = json.loads(apa)
        except (ValueError, TypeError):
            apa = {}
    if isinstance(pn, str):
        try:
            pn = json.loads(pn)
        except (ValueError, TypeError):
            pn = {}
    apa = apa or {}
    pn = pn or {}
    anon = pn.get("anon_map") or {}
    raw_hashes = [m[1].strip() for m in _SEAT_LINE_RE.findall(raw or "")]
    seats_raw = len(raw_hashes)
    seats_apa = len([k for k, v in apa.items() if k != "_meta" and isinstance(v, dict)])
    b_missing = []
    if anon:
        keys = set(anon.keys())
        b_missing = [h for h in raw_hashes if h != "Hero" and h not in keys]
    c_loose = []
    if anon:
        vals = {str(v).strip().lower() for v in anon.values()}
        c_loose = [e.get("name") for e in (pn.get("players_list") or [])
                   if e.get("name") and str(e["name"]).strip().lower() not in vals]
    return {"seats_raw": seats_raw, "seats_apa": seats_apa,
            "a": seats_raw != seats_apa, "b": bool(b_missing), "c": bool(c_loose),
            "unmapped_hashes": b_missing, "loose_names": c_loose}


def _integrity_sanity_6118579134():
    """Sanidade: a forma PARTIDA da GG-6118579134 (pré-correção) TEM de disparar A+B+C."""
    raw = ("Seat 1: Hero (66,974 in chips)\nSeat 2: a3f63bd (72,502 in chips)\n"
           "Seat 3: 83cf3150 (116,767 in chips)\nSeat 4: 860ceadf (83,611 in chips)\n"
           "Seat 5: 67e5ea92 (190,490 in chips)\n")
    apa = {"_meta": {}, "Lauro Dermio": {"seat": 1}, "leleye7311": {"seat": 2},
           "lalaalalaa": {"seat": 3}, "Wally2fun": {"seat": 5}}   # 4 lugares (colapso)
    pn = {"anon_map": {"Hero": "Lauro Dermio", "67e5ea92": "Wally2fun",
                       "83cf3150": "lalaalalaa", "860ceadf": "leleye7311"},  # a3f63bd em falta
          "players_list": [{"name": "MaLong07"}]}                            # nome solto
    return _scan_hand_integrity(raw, apa, pn)


@router.get("/seat-integrity-scan")
def seat_integrity_scan(tagged_only: bool = Query(False, description="só mãos com etiqueta (hm3_tags OU discord_tags) — universo de estudo"),
                        current_user=Depends(require_auth_or_api_key)):
    """READ-ONLY. Varre GG 2026 à procura do padrão da GG-6118579134 (lugares colapsados
    / hashes por mapear / nomes soltos). NÃO escreve nada. Batches de 500 por id (leve
    em qualquer universo). `tagged_only=true` → só mãos de ESTUDO (com ≥1 etiqueta em
    hm3_tags ou discord_tags). Exclui a GG-6118579134 dos totais (já corrigida) + devolve
    o sanity check (forma partida dela → dispara A+B+C)."""
    from app.services.deanon_status import deanon_status
    EXCLUDE = "GG-6118579134"
    A, B, C = [], [], []
    dist_mm, dist_ds = {}, {}
    total = 0
    last_id = 0
    tag_clause = ("AND (COALESCE(array_length(h.hm3_tags,1),0) > 0 "
                  "OR COALESCE(array_length(h.discord_tags,1),0) > 0)") if tagged_only else ""
    while True:
        batch = query(
            f"""SELECT h.id, h.hand_id, h.raw, h.all_players_actions, h.player_names,
                      h.tournament_name, h.played_at::text AS played_at,
                      h.hm3_tags, h.discord_tags, h.context_table_ss_id, h.entry_id,
                      (l.img_b64 IS NOT NULL) AS has_ts_img,
                      e.entry_type,
                      ((e.raw_json->>'img_b64') IS NOT NULL) AS has_gold_img
                 FROM hands h
                 LEFT JOIN table_ss_processing_log l ON l.id = h.context_table_ss_id
                 LEFT JOIN entries e ON e.id = h.entry_id
                WHERE h.site='GGPoker' AND h.played_at >= '2026-01-01'
                  AND h.raw IS NOT NULL AND h.raw <> '' {tag_clause} AND h.id > %s
                ORDER BY h.id LIMIT 500""",
            (last_id,))
        if not batch:
            break
        for r in batch:
            last_id = r["id"]
            total += 1
            if r["hand_id"] == EXCLUDE:
                continue
            pn = r["player_names"] or {}
            if isinstance(pn, str):
                try:
                    pn = json.loads(pn)
                except (ValueError, TypeError):
                    pn = {}
            sc = _scan_hand_integrity(r["raw"], r["all_players_actions"], pn)
            if not (sc["a"] or sc["b"] or sc["c"]):
                continue
            mm = pn.get("match_method") if isinstance(pn, dict) else None
            ds = deanon_status("GGPoker", mm, bool(isinstance(pn, dict) and pn.get("verified_by_user")))
            tags = list(r.get("hm3_tags") or []) + list(r.get("discord_tags") or [])
            rec = {"hand_id": r["hand_id"], "hand_db_id": r["id"],
                   "tournament_name": r["tournament_name"],
                   "played_at": r["played_at"], "tags": tags,
                   "seats_raw": sc["seats_raw"], "seats_apa": sc["seats_apa"],
                   "match_method": mm, "deanon_status": ds,
                   # imagens associadas (links no relatório; None = não existe)
                   "table_ss_id": r["context_table_ss_id"] if r.get("has_ts_img") else None,
                   "gold_entry_id": r["entry_id"] if r.get("has_gold_img") else None,
                   "gold_type": r.get("entry_type") if r.get("has_gold_img") else None}
            if sc["a"]:
                A.append(rec)
            if sc["b"]:
                B.append({**rec, "unmapped_hashes": sc["unmapped_hashes"]})
            if sc["c"]:
                C.append({**rec, "loose_names": sc["loose_names"]})
            dist_mm[mm or "∅(sem match)"] = dist_mm.get(mm or "∅(sem match)", 0) + 1
            dist_ds[ds or "∅(sem badge)"] = dist_ds.get(ds or "∅(sem badge)", 0) + 1
    setA = {x["hand_id"] for x in A}
    setB = {x["hand_id"] for x in B}
    setC = {x["hand_id"] for x in C}
    union = setA | setB | setC
    CAP = 400
    return {
        "scope": ("GGPoker 2026, SÓ etiquetadas (estudo)" if tagged_only
                  else "GGPoker 2026 (todas)") + "; B/C só p/ mãos com anon_map",
        "tagged_only": tagged_only,
        "total_scanned": total,
        "counts": {"A_seat_mismatch": len(A), "B_unmapped_hash": len(B),
                   "C_loose_names": len(C), "affected_union": len(union)},
        "intersections": {"A_and_B": len(setA & setB), "A_and_C": len(setA & setC),
                          "B_and_C": len(setB & setC), "A_B_C": len(setA & setB & setC)},
        "by_match_method": dist_mm,
        "by_deanon_status": dist_ds,
        "truncated": {k: (len(v) > CAP) for k, v in (("A", A), ("B", B), ("C", C))},
        "affected": {"A": A[:CAP], "B": B[:CAP], "C": C[:CAP]},
        "sanity_6118579134_broken_shape": _integrity_sanity_6118579134(),
    }


# ── Ensaio da cura estrutural + propagação por hash (READ-ONLY) ──────────────

def _propose_from_names(names_dict):
    """names_dict = {nome: [hand_ids]} para um hash no torneio. Devolve:
    - {"propose": nome, "from": [hand_ids]}  se HÁ exactamente 1 nome (hash fixo);
    - {"conflict": {nome:[hand_ids]}}         se >1 nome (não propor);
    - None                                    se desconhecido no torneio."""
    if not names_dict:
        return None
    if len(names_dict) == 1:
        nome = next(iter(names_dict))
        return {"propose": nome, "from": sorted(set(names_dict[nome]))[:6]}
    return {"conflict": {n: sorted(set(src))[:6] for n, src in names_dict.items()}}


@router.get("/cure-preview")
def cure_preview(ss_ids: str = Query("", description="ids de capturas table-ss (vírgula)"),
                 current_user=Depends(require_auth_or_api_key)):
    """READ-ONLY. Ensaio da cura estrutural + propagação por hash no torneio, para as
    capturas `ss_ids`. NÃO escreve. Por mão ligada devolve: (1) MESA agora (apa guardado);
    (2) DEPOIS da cura (reparse do raw + anon_map EXISTENTE; hash sem nome = branco, nunca
    inventado); (3) propagação: para cada hash branco, o nome desse hash NOUTRAS mãos do
    MESMO torneio (hash fixo por jogador). Conflito de nomes p/ o mesmo hash → mostra, não propõe."""
    import json as _json
    from app.parsers.gg_hands import parse_hands
    ids = [int(x) for x in ss_ids.split(",") if x.strip().isdigit()]
    if not ids:
        raise HTTPException(400, "ss_ids (vírgula) obrigatório")
    linked = []
    for sid in ids:
        r = query("SELECT matched_hand_id, original_filename FROM "
                  "table_ss_processing_log WHERE id=%s", (sid,))
        linked.append({"ss_id": sid,
                       "hand_id": r[0]["matched_hand_id"] if r else None,
                       "filename": r[0]["original_filename"] if r else None})
    hand_ids = [l["hand_id"] for l in linked if l["hand_id"]]
    hrows = query("SELECT hand_id, raw, all_players_actions, player_names, "
                  "tournament_number, tournament_name FROM hands WHERE hand_id = ANY(%s)",
                  (hand_ids,)) if hand_ids else []
    hb = {h["hand_id"]: h for h in hrows}
    tnums = sorted({h["tournament_number"] for h in hrows if h.get("tournament_number")})
    # mapa do torneio: hash -> {nome -> [hand_ids]} (propagação, hash fixo por jogador)
    thn = {}
    for tn in tnums:
        rows = query("SELECT hand_id, player_names FROM hands "
                     "WHERE site='GGPoker' AND tournament_number=%s", (tn,))
        m = {}
        for r in rows:
            pn = r["player_names"] or {}
            if isinstance(pn, str):
                try:
                    pn = _json.loads(pn)
                except (ValueError, TypeError):
                    pn = {}
            for k, v in (pn.get("anon_map") or {}).items():
                if k == "Hero" or not isinstance(v, str):
                    continue
                m.setdefault(k, {}).setdefault(v.strip(), []).append(r["hand_id"])
        thn[tn] = m

    def _seatsort(z):
        return (z["seat"] is None, z["seat"] if z["seat"] is not None else 0)

    out = []
    for l in linked:
        hid = l["hand_id"]; h = hb.get(hid)
        if not h:
            out.append({"ss_id": l["ss_id"], "hand_id": hid, "error": "sem mão ligada"})
            continue
        pn = h["player_names"] or {}
        if isinstance(pn, str):
            pn = _json.loads(pn)
        anon = pn.get("anon_map") or {}
        apa = h["all_players_actions"] or {}
        if isinstance(apa, str):
            apa = _json.loads(apa)
        mapped_names = set(anon.values())
        now = []
        for k, v in apa.items():
            if k == "_meta" or not isinstance(v, dict):
                continue
            nm = v.get("real_name") or k   # APA §B.6: real_name || chave ("" novo = por mapear → hash)
            named = nm in mapped_names
            now.append({"seat": v.get("seat"), "position": v.get("position"),
                        "name": nm if named else None, "hash": None if named else nm})
        now.sort(key=_seatsort)
        parsed, _e = parse_hands((h["raw"] or "").encode("utf-8"), hid)
        fresh = parsed[0].get("all_players_actions") if parsed else {}
        tn = h.get("tournament_number")
        after, blanks = [], []
        for k, v in (fresh or {}).items():
            if k == "_meta" or not isinstance(v, dict):
                continue
            if k == "Hero":
                nm = anon.get("Hero") or pn.get("hero") or "Hero"; named = True
            else:
                nm = anon.get(k); named = nm is not None
            after.append({"seat": v.get("seat"), "position": v.get("position"),
                          "name": nm if named else None, "hash": None if named else k})
            if not named:
                blanks.append({"hash": k, "seat": v.get("seat"), "position": v.get("position"),
                               "propagation": _propose_from_names(thn.get(tn, {}).get(k, {}))})
        after.sort(key=_seatsort)
        out.append({"ss_id": l["ss_id"], "hand_id": hid, "filename": l["filename"],
                    "tournament_name": h.get("tournament_name"), "tournament_number": tn,
                    "now_seats": len(now), "after_seats": len(after),
                    "now": now, "after": after, "blanks": blanks})
    return {"read_only": True, "linked": linked, "tournaments": tnums, "hands": out}


# pt73 — query única das capturas recuperáveis (vision_failed COM imagem guardada).
_REPROCESS_ELIGIBLE_SQL = (
    "FROM table_ss_processing_log "
    "WHERE result = 'vision_failed' AND img_b64 IS NOT NULL AND img_b64 <> ''"
)


@router.get("/reprocess-failed/preview")
def reprocess_failed_preview(current_user=Depends(require_auth_or_api_key)):
    """DRY-RUN: quantas capturas `vision_failed` têm imagem guardada (logo são
    recuperáveis server-side, sem re-feed de ficheiros). pt73: auth dual
    (cookie OU Bearer HRC_WATCHER_API_KEY) — recuperação service-side."""
    n = query(f"SELECT COUNT(*) AS n {_REPROCESS_ELIGIBLE_SQL}")[0]["n"]
    return {"eligible": n}


@router.post("/reprocess-failed")
async def reprocess_failed(
    confirm: bool = Query(False),
    limit: int = Query(25, ge=1, le=100),
    current_user=Depends(require_auth_or_api_key),
):
    """Recupera capturas `vision_failed` que têm `img_b64` guardado: re-corre a
    Vision sobre a imagem GUARDADA (sem o Rui mexer em ficheiros) → match HH →
    deanon + folder_tag, na MESMA row. Idempotente (UPDATE in-place; sem duplicar
    linhas nem mãos).

    Processa em VAGAS de `limit` (default 25) — Vision OFF-THREAD + sequencial +
    throttle, por isso o event loop fica livre (health/login respondem) e o
    rate-limit não rebenta. Chamar repetidamente (ou ver `remaining`) até 0.
    Requer ?confirm=true. Devolve tally por resultado + `remaining`."""
    if not confirm:
        raise HTTPException(400, "Adicionar ?confirm=true. Ver /reprocess-failed/preview primeiro.")
    rows = query(
        "SELECT id, original_filename, folder_tag, captured_at, img_b64 "
        f"{_REPROCESS_ELIGIBLE_SQL} ORDER BY id ASC LIMIT %s",
        (limit,),
    )
    tally = {"processed": 0, "success": 0, "no_match_to_hand": 0,
             "tm_ambiguous": 0, "vision_failed": 0, "json_invalid": 0,
             "site_undetected": 0}
    report = []
    for r in rows:
        res = await _reprocess_failed_row(r)
        tally["processed"] += 1
        tally[res["result"]] = tally.get(res["result"], 0) + 1
        report.append(res)
    remaining = query(f"SELECT COUNT(*) AS n {_REPROCESS_ELIGIBLE_SQL}")[0]["n"]
    logger.info("[table_ss_reprocess] %s remaining=%d", tally, remaining)
    return {"tally": tally, "remaining": remaining, "report": report}


# ── #CROWN-VISIBLE-READ-ZERO (Opção C, parte 1) — backfill da coroa table-SS→mão ──
def _norm_nick(s) -> str:
    return (s or "").lower().strip().rstrip(".")


def backfill_crowns_from_capture(dry_run: bool = True) -> dict:
    """Quando o GOLD desanon deu `$0`/ausente numa coroa mas a **table-SS CASADA** leu
    um valor VÁLIDO (≥ base÷2), preenche a coroa a partir da table-SS. 0 Vision (dados
    já na BD). Regra (REGISTO_CONCEITO 9 Jul, Opção C do Rui): o Gold manda, mas `$0` do
    Gold NÃO é leitura → cai para a table-SS; NUNCA inverte uma leitura VÁLIDA do Gold.
    Escreve em `all_players_actions` (display da mesa) E `player_names.players_list`
    (IRE + Mãos suspeitas). Só GG `position_v3` com `context_table_ss_id`."""
    from psycopg2.extras import Json
    from app.routers.screenshot import _same_player
    base_by_tn = {r["tournament_number"]: float(r["buy_in_bounty"]) for r in query(
        "SELECT tournament_number, buy_in_bounty FROM tournament_summaries "
        "WHERE site='GGPoker' AND buy_in_bounty IS NOT NULL")}
    rows = query("""SELECT h.id, h.hand_id, h.tournament_number,
                           h.all_players_actions AS apa, h.player_names AS pn,
                           t.vision_json AS tvj
                      FROM hands h JOIN table_ss_processing_log t ON t.id = h.context_table_ss_id
                     WHERE h.site='GGPoker' AND h.played_at >= '2026-01-01'
                       AND h.player_names->>'match_method' = 'position_v3'
                       AND t.vision_json IS NOT NULL""")
    hands_filled = crowns_filled = rejected_below_half = no_base = 0
    for r in rows:
        apa, pn, tvj = r["apa"], r["pn"], r["tvj"]
        if not isinstance(apa, dict) or not isinstance(pn, dict) or not isinstance(tvj, dict):
            continue
        # coroas VÁLIDAS (>0) da table-SS por nick
        tss = {}
        for s in (tvj.get("seats") or []):
            nk, bv = _norm_nick(s.get("nick")), s.get("bounty_usd")
            if nk and bv and float(bv) > 0:
                tss[nk] = float(bv)
        if not tss:
            continue
        base = base_by_tn.get(r["tournament_number"])
        if base is None:
            no_base += 1
            continue                       # sem base não há guarda ≥base/2 → não mexe
        floor = base / 2

        def _tss_crown(name):
            n = _norm_nick(name)
            if n in tss:
                return tss[n]
            cand = {v for k, v in tss.items() if _same_player(n, k)}   # truncagem
            return cand.pop() if len(cand) == 1 else None

        changed = False
        for key, pdata in apa.items():                 # 1) apa (mesa)
            if key == "_meta" or not isinstance(pdata, dict):
                continue
            if (pdata.get("bounty_value_usd") or 0) > 0:
                continue                               # Gold leu válido → NÃO inverter
            crown = _tss_crown(pdata.get("real_name") or key)
            if crown is None:
                continue
            if crown < floor:
                rejected_below_half += 1
                continue
            pdata["bounty_value_usd"] = crown
            crowns_filled += 1
            changed = True
        for p in (pn.get("players_list") or []):       # 2) player_names (IRE/suspeitas)
            if not isinstance(p, dict) or (p.get("bounty_value_usd") or 0) > 0:
                continue
            crown = _tss_crown(p.get("name"))
            if crown is not None and crown >= floor:
                p["bounty_value_usd"] = crown
                changed = True
        if changed:
            hands_filled += 1
            if not dry_run:
                conn = get_conn()
                try:
                    with conn.cursor() as cur2:
                        cur2.execute("UPDATE hands SET all_players_actions=%s, player_names=%s WHERE id=%s",
                                     (Json(apa), Json(pn), r["id"]))
                    conn.commit()
                finally:
                    conn.close()
        if not dry_run:
            # Cura verde-KO (família B): a coroa vinda da captura pode cair num seat HH-
            # bustado → o funil anula-a (captura = sem verde → MUST-only). Só-tagadas.
            try:
                from app.services.eliminated_bounty import scrub_and_persist
                scrub_and_persist(r["id"])
            except Exception as e:  # pragma: no cover - defensivo
                logger.error("[crown-cure] ⚠️ GUARD FALHOU (capture-backfill) hand %s — coroa "
                             "de bustado pode SOBREVIVER (o crivo apanha): %s",
                             r.get("hand_id", r["id"]), e)
    return {"hands_scanned": len(rows), "hands_filled": hands_filled,
            "crowns_filled": crowns_filled, "rejected_below_half": rejected_below_half,
            "hands_without_ts_base": no_base}


@router.post("/backfill-crowns-from-capture")
def backfill_crowns_from_capture_endpoint(
    confirm: bool = Query(False),
    current_user=Depends(require_auth_or_api_key),
):
    """#CROWN-VISIBLE-READ-ZERO parte 1. `?confirm=false` (default) = ENSAIO (plano, não
    escreve). `?confirm=true` = escreve. Ver a regra em `_backfill_crowns_from_capture`."""
    return backfill_crowns_from_capture(dry_run=not confirm)


@router.get("/recent")
def list_recent_table_ss(
    limit: int = Query(50, ge=1, le=200),
    current_user=Depends(require_auth),
):
    """Últimas SSs processadas (sem vision_json — lista leve para a UI)."""
    rows = query(
        """SELECT id, file_hash, source, original_filename, uploaded_at,
                  captured_at, attempt_count, result, reason_detail, site,
                  tournament_name, tournament_number, players_left,
                  total_entries, matched_hand_id
             FROM table_ss_processing_log
            ORDER BY uploaded_at DESC
            LIMIT %s""",
        (limit,),
    )
    return {"count": len(rows), "items": [dict(r) for r in rows]}


# ── pt73 — Auditoria read-only da desanon por table-SS (verificar a amostra) ──

_VERIFY_SCOPE = (
    "h.site='GGPoker' AND (h.player_names->>'match_method')='table_ss' "
    "AND h.context_table_ss_id IS NOT NULL AND h.played_at >= '2026-01-01' "
    "AND h.study_state <> 'mtt_archive'"
)


def _verify_is_strong(method: str) -> bool:
    """Método de match 'forte' = identidade por NOME directo ou tn do filename.
    'Fraco' = aproximação (stack/tempo) → verificar primeiro."""
    m = (method or "").lower()
    return ("name" in m) or ("filename_tn" in m)


@router.get("/verify-recovery")
def verify_recovery(
    samples: int = Query(4, ge=0, le=20),
    current_user=Depends(require_auth_or_api_key),
):
    """READ-ONLY (não altera nada). Retrato de confiança da desanon por table-SS
    (GG 2026): (1) distribuição por método + lista das FRACAS; (2) parciais vs
    completas + lista das parciais; (3) coerência cross-torneio (hash→nome fixo
    dentro do torneio? swaps); (4) amostras de torneios diferentes com nomes reais
    + link da captura. Auth dual (cookie OU Bearer)."""
    # (1) método de match — via reason_detail do log da captura ligada à mão.
    method_rows = query(
        f"""SELECT COALESCE(l.reason_detail, '(sem)') AS method, COUNT(*) AS n
              FROM hands h
              JOIN table_ss_processing_log l ON l.id = h.context_table_ss_id
             WHERE {_VERIFY_SCOPE}
             GROUP BY 1 ORDER BY n DESC"""
    )
    method_dist = [
        {"method": r["method"], "n": r["n"],
         "confianca": "forte" if _verify_is_strong(r["method"]) else "fraca"}
        for r in method_rows
    ]
    weak = query(
        f"""SELECT h.hand_id, h.tournament_name, h.played_at::text AS played_at,
                   h.context_table_ss_id AS ss_id, l.reason_detail AS method
              FROM hands h
              JOIN table_ss_processing_log l ON l.id = h.context_table_ss_id
             WHERE {_VERIFY_SCOPE}
               AND COALESCE(l.reason_detail, '') !~* '(name|filename_tn)'
             ORDER BY h.played_at DESC LIMIT 50"""
    )

    # (2) parciais vs completas.
    pc = query(
        f"""SELECT COALESCE((h.player_names->>'deanon_partial')='true', false) AS partial,
                   COUNT(*) AS n FROM hands h WHERE {_VERIFY_SCOPE} GROUP BY 1"""
    )
    pc_map = {bool(r["partial"]): r["n"] for r in pc}
    partial_list = query(
        f"""SELECT h.hand_id, h.tournament_name, h.played_at::text AS played_at,
                   h.context_table_ss_id AS ss_id
              FROM hands h
             WHERE {_VERIFY_SCOPE} AND (h.player_names->>'deanon_partial')='true'
             ORDER BY h.played_at DESC LIMIT 50"""
    )

    # (3) coerência cross-torneio: o hash GG deve mapear para 1 só nome dentro
    #     do torneio. >1 nome = swap (sinal vermelho). Esperado: 0.
    amap_rows = query(
        f"""SELECT h.hand_id, h.tournament_number,
                   h.player_names->'anon_map' AS anon_map
              FROM hands h
             WHERE {_VERIFY_SCOPE} AND h.tournament_number IS NOT NULL"""
    )
    by_tn: dict = {}
    for r in amap_rows:
        tn = r["tournament_number"]
        e = by_tn.setdefault(tn, {"hands": set(), "hash_names": {}})
        e["hands"].add(r["hand_id"])
        for hsh, name in (r.get("anon_map") or {}).items():
            e["hash_names"].setdefault(hsh, set()).add(name)
    multi = {tn: e for tn, e in by_tn.items() if len(e["hands"]) >= 2}
    conflicts = []
    for tn, e in multi.items():
        for hsh, names in e["hash_names"].items():
            if len(names) > 1:
                conflicts.append({"tournament_number": tn, "hash": hsh,
                                  "names": sorted(names)})

    # (4) amostras de torneios DIFERENTES (1 por tn), com nomes + link da captura.
    sample_rows = query(
        f"""SELECT DISTINCT ON (h.tournament_number)
                   h.hand_id, h.tournament_name, h.tournament_number,
                   h.played_at::text AS played_at,
                   h.context_table_ss_id AS ss_id,
                   h.player_names->'anon_map' AS anon_map,
                   h.player_names->>'hero' AS hero
              FROM hands h
             WHERE {_VERIFY_SCOPE}
             ORDER BY h.tournament_number, h.played_at DESC"""
    )
    out_samples = []
    for r in sample_rows[:samples]:
        names = sorted({v for v in (r.get("anon_map") or {}).values() if v})
        out_samples.append({
            "hand_id": r["hand_id"],
            "tournament_name": r["tournament_name"],
            "played_at": r["played_at"],
            "hero": r["hero"],
            "players": names,
            "n_mapped": len(names),
            "capture_url": f"/api/table-ss/image/{r['ss_id']}" if r["ss_id"] else None,
        })

    total = query(f"SELECT COUNT(*) AS n FROM hands h WHERE {_VERIFY_SCOPE}")[0]["n"]
    return {
        "total_deanon_table_ss": total,
        "method_distribution": method_dist,
        "weak_matches": [dict(r) for r in weak],
        "partial_vs_complete": {
            "complete": pc_map.get(False, 0), "partial": pc_map.get(True, 0)},
        "partial_list": [dict(r) for r in partial_list],
        "cross_tournament": {
            "tournaments_checked": len(by_tn),
            "tournaments_multi_capture": len(multi),
            "conflicts": len(conflicts),
            "conflict_detail": conflicts[:20],
        },
        "samples": out_samples,
    }


@router.get("/deanon-debug")
def deanon_debug(
    hand_id: Optional[str] = Query(None, description="forense de 1 mão; ausente = scan da frota"),
    mode: str = Query("fit", description="scan: 'fit' (SS≠mão por stacks/hero) ou 'gap' (stacks próximos)"),
    gap_bb: float = Query(2.0, description="scan gap: flag se 2 stacks não-hero ficam a <gap_bb BB"),
    current_user=Depends(require_auth_or_api_key),
):
    """READ-ONLY forense da desanon table-SS. A desanon mapeia nome→cadeira SÓ por
    STACK (a Vision do table-SS devolve uma LISTA de (nick, stack_bb) SEM posição/
    ordem) → dois stacks próximos podem PERMUTAR (nome na cadeira errada; a posição
    da cadeira é da HH e está certa, mas fica com o nome trocado).

    `hand_id` → detalhe: HH crua (seat·hash·stack·posição) vs nome gravado pela
    desanon, + o que a Vision leu (nick·stack). Ausente → scan das mãos desanon
    GG-2026: quantas têm ≥2 stacks não-hero a <`gap_bb` BB (risco de troca)."""
    if hand_id:
        rows = query(
            "SELECT hand_id, raw, all_players_actions, player_names, "
            "context_table_ss_id FROM hands WHERE hand_id=%s LIMIT 1", (hand_id,))
        if not rows:
            raise HTTPException(404, "mão não encontrada")
        h = rows[0]
        raw = h.get("raw") or ""
        apa = h.get("all_players_actions") or {}
        pn = h.get("player_names") or {}
        anon_map = pn.get("anon_map") or {}
        bb = (apa.get("_meta") or {}).get("bb")
        bm = re.search(r"Seat\s*#(\d+)\s+is the button", raw)
        button_seat = int(bm.group(1)) if bm else None
        # HH crua: seat -> hash + stack (direto do ficheiro, sem processamento).
        hh = {}
        for m in re.finditer(r"Seat\s+(\d+):\s*(.+?)\s*\(([\d,]+)\s+in chips\)", raw):
            seat = int(m.group(1)); hsh = m.group(2).strip()
            chips = float(m.group(3).replace(",", ""))
            hh[seat] = {
                "seat": seat, "hh_hash": hsh, "stack_chips": chips,
                "stack_bb": round(chips / bb, 1) if bb else None,
                "nick_gravado": (pn.get("hero") or "Hero") if hsh == "Hero"
                                else anon_map.get(hsh, f"({hsh}) POR-MAPEAR"),
                "mapped": hsh == "Hero" or hsh in anon_map,
            }
        # posição da HH por cadeira (do APA já parseado).
        for k, info in apa.items():
            if k == "_meta" or not isinstance(info, dict):
                continue
            s = info.get("seat")
            if s in hh:
                hh[s]["position"] = info.get("position")
                hh[s]["is_hero"] = bool(info.get("is_hero"))
        hh_seats = [hh[s] for s in sorted(hh)]
        # o que a VISION leu (lista plana nick+stack, SEM posição).
        vision_seats = []
        if h.get("context_table_ss_id"):
            vr = query("SELECT vision_json FROM table_ss_processing_log WHERE id=%s",
                       (h["context_table_ss_id"],))
            vj = (vr[0].get("vision_json") if vr else None) or {}
            for s in (vj.get("seats") or []):
                vision_seats.append({"nick": s.get("nick"),
                                     "stack_bb": s.get("stack_bb"),
                                     "is_hero": bool(s.get("is_hero"))})
        return {
            "hand_id": h["hand_id"], "bb": bb, "button_seat": button_seat,
            "n_hh_seats": len(hh_seats),
            "hh_seats_with_gravado": hh_seats,
            "vision_seats_lidos": vision_seats,
            "anon_map": anon_map,
            "nota": "posição = da HH (correcta); nick = mapeado por stack (pode trocar).",
        }

    if mode == "gap":
        # Risco de PERMUTAÇÃO por stacks próximos (within-hand). Sinal secundário.
        rows = query(
            f"""SELECT h.hand_id, h.tournament_name, h.all_players_actions
                  FROM hands h WHERE {_VERIFY_SCOPE} AND h.all_players_actions IS NOT NULL""")
        flagged = []
        for r in rows:
            apa = r.get("all_players_actions") or {}
            stacks = []
            for k, info in apa.items():
                if k == "_meta" or not isinstance(info, dict) or info.get("is_hero"):
                    continue
                sb = info.get("stack_bb")
                if isinstance(sb, (int, float)) and not isinstance(sb, bool) and sb > 0:
                    stacks.append((round(float(sb), 1), info.get("position")))
            stacks.sort()
            close = []
            for i in range(1, len(stacks)):
                gap = stacks[i][0] - stacks[i - 1][0]
                if gap < gap_bb:
                    close.append({"a": stacks[i - 1], "b": stacks[i], "gap_bb": round(gap, 2)})
            if close:
                flagged.append({"hand_id": r["hand_id"],
                                "tournament_name": r["tournament_name"], "close_pairs": close})
        return {"scope": "GG table_ss deanon 2026", "mode": "gap",
                "total_checked": len(rows), "gap_bb_threshold": gap_bb,
                "n_swap_risk": len(flagged), "flagged": flagged[:80]}

    # mode == 'fit' (default): a SS corresponde MESMO a esta mão? Compara os
    # stacks que a Vision leu na imagem com os stacks da HH. Sinal PRIMÁRIO do
    # bug GG-6042783089: se o hero está ALLIN na imagem mas tem stack na HH (ou
    # os conjuntos divergem muito), a SS é de OUTRA mão → deanon não-fiável.
    rows = query(
        f"""SELECT h.hand_id, h.tournament_name, h.all_players_actions, l.vision_json
              FROM hands h
              JOIN table_ss_processing_log l ON l.id = h.context_table_ss_id
             WHERE {_VERIFY_SCOPE} AND h.all_players_actions IS NOT NULL""")

    def _num(x):
        return float(x) if isinstance(x, (int, float)) and not isinstance(x, bool) else None

    flagged = []
    n_hero_allin_mismatch = 0
    for r in rows:
        apa = r.get("all_players_actions") or {}
        vj = r.get("vision_json") or {}
        hero_hh = None
        hh = []
        for k, info in apa.items():
            if k == "_meta" or not isinstance(info, dict):
                continue
            sb = _num(info.get("stack_bb"))
            if info.get("is_hero"):
                hero_hh = sb
            elif sb and sb > 0:
                hh.append(sb)
        hero_vis = None
        hero_vis_allin = False
        vis = []
        for s in (vj.get("seats") or []):
            raw = s.get("stack_bb")
            n = _num(raw)
            if s.get("is_hero"):
                hero_vis = n
                hero_vis_allin = (isinstance(raw, str) and raw.upper() == "ALLIN")
            elif n and n > 0:
                vis.append(n)
        # hero: ALLIN na imagem mas com stack na HH (ou diff grande) = SS≠mão.
        hero_allin_mismatch = bool(hero_vis_allin and hero_hh and hero_hh > 12)
        hero_diff = (abs(hero_hh - hero_vis) if (hero_hh and hero_vis) else None)
        # residual do melhor alinhamento (ordenado) dos stacks não-hero.
        a, b = sorted(hh), sorted(vis)
        m = min(len(a), len(b))
        resid = [abs(a[i] - b[i]) for i in range(m)] if m else []
        max_resid = round(max(resid), 1) if resid else None
        mean_resid = round(sum(resid) / len(resid), 1) if resid else None
        misfit = (
            hero_allin_mismatch
            or (hero_diff is not None and hero_diff > 10)
            or (max_resid is not None and max_resid > 12)
            or (mean_resid is not None and mean_resid > 6)
        )
        if hero_allin_mismatch:
            n_hero_allin_mismatch += 1
        if misfit:
            flagged.append({
                "hand_id": r["hand_id"], "tournament_name": r["tournament_name"],
                "hero_hh_bb": hero_hh, "hero_vision_bb": ("ALLIN" if hero_vis_allin else hero_vis),
                "hero_diff_bb": round(hero_diff, 1) if hero_diff is not None else None,
                "max_resid_bb": max_resid, "mean_resid_bb": mean_resid,
            })
    flagged.sort(key=lambda x: (x["mean_resid_bb"] or 0), reverse=True)
    return {
        "scope": "GG table_ss deanon 2026", "mode": "fit",
        "total_checked": len(rows),
        "n_misfit": len(flagged),
        "n_hero_allin_mismatch": n_hero_allin_mismatch,
        "criteria": "hero ALLIN-vs-stack, |hero diff|>10bb, max_resid>12bb, ou mean_resid>6bb",
        "flagged": flagged[:80],
    }


@router.get("/hand-seats")
def hand_seats(
    hand_ids: str = Query(..., description="hand_ids separados por vírgula"),
    current_user=Depends(require_auth_or_api_key),
):
    """READ-ONLY: mapa por ASSENTO de cada mão, EXACTAMENTE como ficou na BD após
    o match (de `all_players_actions`). Por assento: seat · nick (ou hash se por
    mapear) · stack (fichas + BB) · posição · hero. Para comparar banco-a-banco
    com a captura. Marca os assentos POR MAPEAR (all-in/ambíguos). Auth dual."""
    ids = [x.strip() for x in (hand_ids or "").split(",") if x.strip()]
    if not ids:
        raise HTTPException(400, "hand_ids vazio")
    rows = query(
        """SELECT hand_id, tournament_name, played_at::text AS played_at,
                  context_table_ss_id AS ss_id, all_players_actions, player_names
             FROM hands WHERE hand_id = ANY(%s)""",
        (ids,),
    )
    out = []
    for r in rows:
        apa = r.get("all_players_actions") or {}
        pn = r.get("player_names") or {}
        mapped_names = set((pn.get("anon_map") or {}).values())
        meta = apa.get("_meta") or {}
        seats = []
        for key, info in apa.items():
            if key == "_meta" or not isinstance(info, dict):
                continue
            name = info.get("real_name") or key   # APA §B.6: real_name || chave (hash se por mapear)
            is_mapped = name in mapped_names
            seats.append({
                "seat": info.get("seat"),
                "nick": name if is_mapped else None,
                "raw_hash": None if is_mapped else name,
                "stack": info.get("stack"),
                "stack_bb": info.get("stack_bb"),
                "position": info.get("position"),
                "is_hero": bool(info.get("is_hero")),
                "mapped": is_mapped,
            })
        seats.sort(key=lambda s: (s["seat"] is None, s["seat"] if s["seat"] is not None else 0))
        out.append({
            "hand_id": r["hand_id"],
            "tournament_name": r["tournament_name"],
            "played_at": r["played_at"],
            "capture_url": f"/api/table-ss/image/{r['ss_id']}" if r["ss_id"] else None,
            "blinds": {"sb": meta.get("sb"), "bb": meta.get("bb"), "level": meta.get("level")},
            "n_seats": len(seats),
            "n_mapped": sum(1 for s in seats if s["mapped"]),
            "seats": seats,
        })
    order = {h: i for i, h in enumerate(ids)}
    out.sort(key=lambda x: order.get(x["hand_id"], 999))
    return {"hands": out}
