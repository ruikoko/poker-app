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

from app.auth import require_auth
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


def _final_folder_tag(base_tag: Optional[str], vision_json) -> Optional[str]:
    """tag final = base + '-ft' quando a Vision indica mesa final (bancos ==
    restantes); senão só a base. Fail-safe (Rui): incerto → sem '-ft'. Pura."""
    if not base_tag:
        return None
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
    own = conn is None
    try:
        if own:
            conn = get_conn()
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE hands SET discord_tags = ARRAY(SELECT DISTINCT unnest("
                "COALESCE(discord_tags, '{}'::text[]) || %s::text[])) WHERE id = %s",
                ([final_tag], matched_hand_db_id),
            )
        if own:
            conn.commit()
        from app.services.villain_rules import apply_villain_rules
        apply_villain_rules(matched_hand_db_id, conn=conn)
        logger.info(
            "[table_ss_folder_tag] hand %s -> tag %r", matched_hand_db_id, final_tag
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

    # 3. Vision (off-thread — única chamada lenta/externa).
    mime = detect_image_mime(content)
    raw = await asyncio.to_thread(tv.extract_table_ss_json, content, mime)
    if raw is None:
        out["result"] = "vision_failed"
        out["reason_detail"] = "extract_table_ss_json devolveu None"
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
