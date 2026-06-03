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

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile

from app.auth import require_auth
from app.db import get_conn, query
from app.services.image_utils import detect_image_mime
from app.services import table_ss_vision as tv
from app.services.tournament_resolver import (
    resolve_tournament_number, name_tokens_subset,
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
        captured_at        TIMESTAMPTZ,
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
            cur.execute(idx_uploaded)
            cur.execute(idx_result)
            cur.execute(idx_tn_captured)
        conn.commit()
    finally:
        conn.close()


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
) -> Optional[int]:
    """UPSERT por file_hash; incrementa attempt_count em conflito. Quando
    result='success' e matched_hand_db_id presente, liga a mão na MESMA
    transacção (hands.context_table_ss_id = <id da log row>). Devolve o id."""
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
                    matched_hand_id, vision_json
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
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
                    vision_json       = COALESCE(EXCLUDED.vision_json, table_ss_processing_log.vision_json)
                RETURNING id
                """,
                (
                    file_hash, source, original_filename, file_size, captured_at,
                    result, reason_detail, site, tournament_name,
                    tournament_number, players_left, total_entries,
                    matched_hand_id, vision_json,
                ),
            )
            row = cur.fetchone()
            ss_id = row["id"] if row else None
            if (
                ss_id is not None
                and result == "success"
                and matched_hand_db_id is not None
            ):
                cur.execute(
                    "UPDATE hands SET context_table_ss_id = %s WHERE id = %s",
                    (ss_id, matched_hand_db_id),
                )
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
    _bi, _cur = _parse_buy_in_str(vj.get("tournament_buy_in"))
    tn, _cands = resolve_tournament_number(
        site, vj.get("tournament_name") or "", None,
        posted_at_hint=captured_at, buy_in=_bi, buy_in_currency=_cur,
    )
    if tn and tn in tns:
        closest = next((c for c in candidates if c["tournament_number"] == tn), None)
        if closest:
            return {"matched": closest, "tn": tn, "ambiguous": False,
                    "reason": "disambiguated_by_name"}
    return {"matched": None, "tn": None, "ambiguous": True,
            "reason": f"multi_tn_unresolved:{len(tns)}"}


# ── Re-link pós-import (peça em falta da Fase A) ─────────────────────────────

def _bump_attempt_table_ss(log_id: int) -> None:
    """Incrementa attempt_count sem mudar o result (continua orfão:
    no_match_to_hand ou tm_ambiguous — #FIX-B1 pt50)."""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE table_ss_processing_log SET attempt_count = attempt_count + 1 "
                "WHERE id = %s AND result IN ('no_match_to_hand', 'tm_ambiguous')",
                (log_id,),
            )
        conn.commit()
    except Exception as e:
        logger.error(f"[table_ss_relink] bump attempt falhou id={log_id}: {e}")
        try:
            conn.rollback()
        except Exception:
            pass
    finally:
        try:
            conn.close()
        except Exception:
            pass


def _persist_corrected_site_table_ss(log_id: int, new_site: str) -> None:
    """#TABLE-SS-VISION-SITE-MISCLASS self-healing: grava a site corrigida numa
    row órfã. Guard `result IN ('no_match_to_hand','tm_ambiguous')` = idempotência
    + escopo (nunca toca rows já `success`; #FIX-B1 pt50 cobre ambíguos)."""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE table_ss_processing_log SET site = %s "
                "WHERE id = %s AND result IN ('no_match_to_hand', 'tm_ambiguous')",
                (new_site, log_id),
            )
        conn.commit()
    except Exception as e:
        logger.error(f"[table_ss_relink] persistir site corrigida falhou id={log_id}: {e}")
        try:
            conn.rollback()
        except Exception:
            pass
    finally:
        try:
            conn.close()
        except Exception:
            pass


def _link_orphan_table_ss(log_id: int, matched_hand: dict) -> bool:
    """Liga uma SS órfã à mão agora encontrada, em 1 transacção. O guard
    `WHERE result IN ('no_match_to_hand','tm_ambiguous')` garante idempotência
    (no-op se já success ou corrida concorrente) e, desde #FIX-B1 (pt50), permite
    resgatar rows que ficaram ambíguas no upload (ex.: o TS desambiguador chegou
    depois). Devolve True sse ligou."""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE table_ss_processing_log
                   SET result = 'success',
                       matched_hand_id = %s,
                       tournament_number = COALESCE(tournament_number, %s),
                       attempt_count = attempt_count + 1,
                       reason_detail = 'relinked_post_import'
                 WHERE id = %s AND result IN ('no_match_to_hand', 'tm_ambiguous')
                """,
                (matched_hand["hand_id"], matched_hand.get("tournament_number"), log_id),
            )
            if cur.rowcount == 0:
                conn.rollback()
                return False
            cur.execute(
                "UPDATE hands SET context_table_ss_id = %s WHERE id = %s",
                (log_id, matched_hand["id"]),
            )
        conn.commit()
        return True
    except Exception as e:
        logger.error(
            f"[table_ss_relink] link falhou id={log_id}: {type(e).__name__}: {e}"
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


def relink_orphan_table_ss(hand_ids=None) -> dict:
    """Re-tenta linkar SSs de mesa órfãs (`no_match_to_hand` ou `tm_ambiguous`)
    a mãos agora presentes (tipicamente recém-importadas). Disparado
    fire-and-forget no fim de import_hm3 / import GG zip.

    `hand_ids` é o sinal do trigger (que mãos chegaram); o match re-corre pela
    janela temporal (`_find_candidate_hands`), por isso serve só para
    curto-circuitar quando nada foi importado e para logging.

    Idempotente: só selecciona rows órfãs com captured_at; rows já `success`
    nunca são tocadas. #FIX-B1 (pt50): inclui `tm_ambiguous` para que uma SS que
    ficou ambígua no upload (resolver sem TS/meta na altura) seja re-avaliada
    quando o desambiguador chega — convergência independente da ordem. Devolve
    {checked, linked, still_orphan}.
    """
    if hand_ids is not None and len(hand_ids) == 0:
        return {"checked": 0, "linked": 0, "still_orphan": 0}

    rows = query(
        """SELECT id, captured_at, site, vision_json
             FROM table_ss_processing_log
            WHERE result IN ('no_match_to_hand', 'tm_ambiguous')
              AND captured_at IS NOT NULL"""
    )
    checked = linked = still = 0
    for r in rows:
        checked += 1
        site = r.get("site")
        captured_at = r.get("captured_at")
        if not site or captured_at is None:
            _bump_attempt_table_ss(r["id"])
            still += 1
            continue
        vj = r.get("vision_json") or {}
        # #TABLE-SS-VISION-SITE-MISCLASS self-healing: corrige a site já gravada
        # quando o nome a contradiz, ANTES do match; persiste a correcção no log.
        corrected = tv._correct_site(vj.get("tournament_name"), site)
        if corrected != site:
            logger.info(
                "[table_ss_relink] site corrigida id=%s %s -> %s | name=%r",
                r["id"], site, corrected, vj.get("tournament_name"),
            )
            _persist_corrected_site_table_ss(r["id"], corrected)
            site = corrected
        candidates = _find_candidate_hands(captured_at, site)
        m = _resolve_match(captured_at, vj, site, candidates)
        if m["matched"] and _link_orphan_table_ss(r["id"], m["matched"]):
            linked += 1
        else:
            _bump_attempt_table_ss(r["id"])
            still += 1
    logger.info(
        "[table_ss_relink] checked=%d linked=%d still_orphan=%d",
        checked, linked, still,
    )
    return {"checked": checked, "linked": linked, "still_orphan": still}


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


def _finalize(
    out: dict, *, source: str, original_filename: Optional[str],
    file_size: int, captured_at: Optional[datetime],
    matched_hand_db_id: Optional[int] = None,
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
    )
    return out


async def _process_table_ss(
    content: bytes, filename: str, *,
    captured_at_override: Optional[str] = None, source: str = "manual_upload",
) -> dict:
    """Pipeline de 1 SS de mesa. Devolve dict serializável de resultado."""
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

    # 3. Vision (off-thread — única chamada lenta/externa).
    mime = detect_image_mime(content)
    raw = await asyncio.to_thread(tv.extract_table_ss_json, content, mime)
    if raw is None:
        out["result"] = "vision_failed"
        out["reason_detail"] = "extract_table_ss_json devolveu None"
        return _finalize(out, source=source, original_filename=filename,
                         file_size=fsize, captured_at=captured_at)

    vj = tv.parse_and_validate_table_ss_json(raw)
    if vj is None:
        out["result"] = "json_invalid"
        out["reason_detail"] = "JSON inválido ou sem campos úteis"
        return _finalize(out, source=source, original_filename=filename,
                         file_size=fsize, captured_at=captured_at)
    # #TABLE-SS-VISION-SITE-MISCLASS: corrige a site lida quando o nome a
    # contradiz (Regra A `#NNN` trailing + Regra B cross-check BD), ANTES de
    # gravar a site no log e de filtrar candidatos por site.
    vj["site"] = tv._correct_site(vj.get("tournament_name"), vj.get("site"))
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
                         file_size=fsize, captured_at=captured_at)

    # 5. Match temporal mão → resolver-desambigua.
    matched_db_id = None
    if captured_at is None:
        out["result"] = "no_match_to_hand"
        out["reason_detail"] = "sem captured_at (filename sem YYYYMMDDHHMMSS)"
        _bi, _cur = _parse_buy_in_str(vj.get("tournament_buy_in"))
        tn, _c = resolve_tournament_number(
            site, vj.get("tournament_name") or "", None,
            buy_in=_bi, buy_in_currency=_cur,
        )
        out["tournament_number"] = tn
    else:
        candidates = _find_candidate_hands(captured_at, site)
        m = _resolve_match(captured_at, vj, site, candidates)
        if m["matched"]:
            out["result"] = "success"
            out["reason_detail"] = m["reason"]
            out["tournament_number"] = m["tn"]
            out["hand_matched"] = m["matched"]["hand_id"]
            matched_db_id = m["matched"]["id"]
        elif m["ambiguous"]:
            out["result"] = "tm_ambiguous"
            out["reason_detail"] = m["reason"]
        else:  # no_hands_in_window — tenta resolver p/ guardar tn (limbo linkável)
            out["result"] = "no_match_to_hand"
            out["reason_detail"] = m["reason"]
            _bi, _cur = _parse_buy_in_str(vj.get("tournament_buy_in"))
            tn, _c = resolve_tournament_number(
                site, vj.get("tournament_name") or "", None,
                posted_at_hint=captured_at, buy_in=_bi, buy_in_currency=_cur,
            )
            out["tournament_number"] = tn

    return _finalize(out, source=source, original_filename=filename,
                     file_size=fsize, captured_at=captured_at,
                     matched_hand_db_id=matched_db_id)


# ── Endpoints ────────────────────────────────────────────────────────────────

@router.post("/upload")
async def upload_table_ss(
    file: UploadFile = File(...),
    filename: Optional[str] = Form(None),
    captured_at: Optional[str] = Form(None),
    source: str = Form("manual_upload"),
    current_user=Depends(require_auth),
):
    """Upload de 1 SS de mesa (manual UI ou cliente automático). Cookie auth."""
    content = await file.read()
    if not content:
        raise HTTPException(400, "Ficheiro vazio")
    fname = filename or file.filename or "upload.png"
    return await _process_table_ss(
        content, fname, captured_at_override=captured_at, source=source,
    )


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
