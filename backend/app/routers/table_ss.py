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

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Response, UploadFile

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
            cur.execute(idx_uploaded)
            cur.execute(idx_result)
            cur.execute(idx_tn_captured)
        conn.commit()
    finally:
        conn.close()


# ── Link da mão (hands.context_table_ss_id) ──────────────────────────────────

def _apply_hand_link(cur, ss_id: int, matched_hand_db_id: Optional[int]) -> None:
    """Reconcilia `hands.context_table_ss_id` para esta SS (id=ss_id), DENTRO da
    transacção do `cur`. Invariante: depois disto, APENAS a mão casada (ou
    nenhuma) aponta para a SS — desliga qualquer mão obsoleta que ainda aponte
    para ela e liga a nova. Idempotente: re-correr com o mesmo match não muda
    nada. É a primitiva única de (des)ligação usada pelo upload e pelo reconcile
    (#FIX-B3 pt50)."""
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
    # …e liga a mão casada.
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

def _find_candidate_hands(captured_at: datetime, site: str) -> list[dict]:
    """Mãos do mesmo site com played_at dentro de ±TABLE_SS_MATCH_WINDOW_S de
    captured_at, ordenadas por proximidade. Guard rails iguais ao resolver
    (2026+, sem mtt_archive, tournament_number presente)."""
    lo = captured_at - timedelta(seconds=TABLE_SS_MATCH_WINDOW_S)
    hi = captured_at + timedelta(seconds=TABLE_SS_MATCH_WINDOW_S)
    rows = query(
        """
        SELECT id, hand_id, tournament_number, tournament_name, site, played_at
          FROM hands
         WHERE played_at >= '2026-01-01'
           AND site = %s
           AND played_at BETWEEN %s AND %s
           AND tournament_number IS NOT NULL
           AND study_state != 'mtt_archive'
         ORDER BY ABS(EXTRACT(EPOCH FROM (played_at - %s)))
        """,
        (site, lo, hi, captured_at),
    )
    return [dict(r) for r in rows]


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
        # SS sem nome lido, ou sala de nome genérico (WPN/PS) → leniente
        # (proximidade temporal é o único sinal).
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
    filename_tn: Optional[str] = None,
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

    candidates = _find_candidate_hands(captured_at, site)
    m = _resolve_match(captured_at, vj, site, candidates)
    if m["matched"]:
        return {
            "result": "success", "reason_detail": m["reason"], "site": site,
            "tournament_number": m["tn"],
            "matched_hand_id": m["matched"]["hand_id"],
            "matched_hand_db_id": m["matched"]["id"],
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
    link só é tocado quando o match muda de facto). Disparado fire-and-forget
    após cada import. `hand_ids=[]` → curto-circuita (nada importado). Devolve
    {checked, changed, success, orphan, ambiguous}.
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
            r.get("captured_at"), r.get("site"), vj, filename_tn=_ftn)
        if _persist_table_ss_match(
            r["id"], desired,
            prev_result=r.get("result"),
            prev_matched_hand_id=r.get("matched_hand_id"),
        ):
            changed += 1
            # Estágio 3-b: o match MUDOU para uma mão nova → desanonimiza-a
            # (gated GG-sem-Discord). Só quando muda, para não re-correr em
            # cada reconcile de import. Rows antigas sem `seats` → no-op.
            if desired["result"] == "success":
                _deanon_after_match(desired["matched_hand_db_id"], vj)
                # pt72 — re-aplica a tag da pasta à mão (nova) casada.
                _apply_folder_tag_to_hand(
                    desired["matched_hand_db_id"], r.get("folder_tag"), vj)
        if desired["result"] == "success":
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
    if not matched_hand_db_id or not base_tag:
        return
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
        captured_at, site, vj, filename_tn=_parsed_fn["tournament_number"])
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
        captured_at, site, vj, filename_tn=_parsed["tournament_number"])
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
def trigger_reconcile_table_ss(current_user=Depends(require_auth)):
    """Corre o reconcile R sobre TODAS as SS de mesa (recalcula match de raiz,
    re-persiste, inclui as `tm_ambiguous`/`no_match_to_hand`). Síncrono mas leve
    (consultas + updates, sem Vision). Usado p.ex. após backfill de nomes para
    re-ligar as SS já importadas (#FIX-B3 + pt54). Devolve o tally."""
    return reconcile_table_ss(hand_ids=None)


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
            name = info.get("real_name", key)
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
