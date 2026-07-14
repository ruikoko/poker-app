"""Amostrador de coroas Gold — verificação por RELEITURA (#CROWN-SAMPLE-VERIFY).

Re-lê com o prompt ATUAL da Vision (Gold/replayer) uma AMOSTRA de coroas Gold e
LISTA as divergências vs o valor gravado, COM imagem, para o olho do Rui.
Amostra (ordem do Rui, 14 Jul): 127 do "sliver" (Golds lidas 9 Jul 00:05-04:31,
antes dos refinamentos crown-cure) + 50 aleatórias do in-band Gold.

⚠️ NÃO ESCREVE NADA — nem as coroas/hands, nem uma tabela de revisão. O resultado
vive em CACHE IN-PROCESS (perde-se no redeploy). É verificação one-shot; onde a
releitura divergir, é só para o Rui ver e decidir — nunca auto-corrige.

Corre em daemon thread (177 chamadas Vision = minutos; não bloqueia o request).
Ver `docs/JOURNAL_2026-07-14` (censos 1+2 + amostrador)."""
from __future__ import annotations
import base64
import json
import logging
import random
import threading
from datetime import datetime, timezone

from fastapi import APIRouter, Depends

from app.auth import require_auth
from app.db import query

router = APIRouter(prefix="/api/gg-health/crown-sample", tags=["crown-sample"])
logger = logging.getLogger("crown_sample")

# Janela do sliver (Lisboa +01) — Golds lidas antes dos refinamentos crown-cure.
_SLIVER_START = "2026-07-09 00:05:00+01"
_SLIVER_END = "2026-07-09 04:31:00+01"
_INBAND_RANDOM = 50
# Seed FIXA do sorteio das 50 → a lista de candidatas é estável (mesmo após
# redeploy); o Rui revê sempre as MESMAS 177.
_SEED = 20260714
# Tolerância p/ "igual": abs<=0.01 OU relativa<=1% (wobble de OCR não é divergência).
_ABS_TOL = 0.01
_REL_TOL = 0.01

_STATE: dict = {
    "status": "idle",          # idle | running | done | cancelled | error
    "done": 0, "total": 0,
    "candidates": [],          # 177 candidatas c/ coroas GRAVADAS (preview, sem Vision)
    "divergences": [],         # lista p/ o painel (com imagem), após releitura
    "reread_seats": 0,
    "cancel": False,           # bandeira cooperativa de cancelamento
    "started_at": None, "finished_at": None, "error": None,
}
_LOCK = threading.Lock()


def _crowns_of(pn) -> dict:
    """{name: bounty_value_usd} do player_names gravado (só seats com coroa)."""
    if isinstance(pn, str):
        try:
            pn = json.loads(pn or "{}")
        except Exception:
            pn = {}
    out = {}
    for e in ((pn or {}).get("players_list") or []):
        bv = e.get("bounty_value_usd")
        if bv is not None and e.get("name"):
            out[e["name"]] = bv
    return out


def _select_sample() -> list[dict]:
    """127 sliver + 50 aleatórias in-band (excl. sliver). Determinístico salvo a
    aleatoriedade das 50. Read-only."""
    base_join = (
        "FROM hands h "
        "JOIN entries e ON e.id = h.entry_id AND e.entry_type='screenshot' "
        "  AND (e.raw_json->>'img_b64') IS NOT NULL "
        "LEFT JOIN tournament_summaries ts "
        "  ON ts.site='GGPoker' AND ts.tournament_number = h.tournament_number "
        "WHERE h.site='GGPoker' AND h.played_at >= '2026-01-01' "
    )
    sliver = query(
        "SELECT h.id, h.hand_id, h.tournament_name, h.player_names AS pn, "
        "       ts.buy_in_bounty AS base, e.id AS entry_id, e.created_at AS gold_at " + base_join +
        "AND e.created_at >= %s AND e.created_at <= %s",
        (_SLIVER_START, _SLIVER_END))
    sliver_ids = {r["id"] for r in sliver}

    # candidatos in-band (fora do sliver): mão KO/PKO com base e ≥1 coroa in-band.
    rest = query(
        "SELECT h.id, h.hand_id, h.tournament_name, h.player_names AS pn, "
        "       ts.buy_in_bounty AS base, e.id AS entry_id " + base_join +
        "AND ts.buy_in_bounty IS NOT NULL "
        "AND lower(COALESCE(h.tournament_format,'')) ~ 'ko|pko|bounty'")
    inband = []
    for r in rest:
        if r["id"] in sliver_ids:
            continue
        base = r.get("base")
        try:
            b = float(base)
        except (TypeError, ValueError):
            continue
        has_inband = any(b / 2 <= float(v) <= 3 * b
                         for v in _crowns_of(r["pn"]).values()
                         if _is_num(v))
        if has_inband:
            inband.append(r)
    # ordena por id (determinístico) ANTES do shuffle com seed fixa → estável.
    inband.sort(key=lambda r: r["id"])
    random.Random(_SEED).shuffle(inband)
    picked = list(sliver) + inband[:_INBAND_RANDOM]
    for p in picked:
        p["_sliver"] = p["id"] in sliver_ids
    return picked


def _is_num(v) -> bool:
    try:
        float(v)
        return True
    except (TypeError, ValueError):
        return False


def _diff(stored, reread) -> bool:
    """True se a releitura DIVERGE do gravado (para além da tolerância)."""
    s_num, r_num = _is_num(stored), _is_num(reread)
    if s_num != r_num:                       # um tem coroa, o outro não
        return True
    if not s_num:                            # ambos None
        return False
    s, r = float(stored), float(reread)
    if abs(s - r) <= _ABS_TOL:
        return False
    denom = max(abs(s), abs(r), 1e-9)
    return abs(s - r) / denom > _REL_TOL


def _reread_crowns(img_b64: str) -> dict | None:
    """Corre a Vision ATUAL da Gold sobre a imagem guardada → {name: bounty}.
    None se a Vision falhar (não conta como divergência)."""
    from app.routers.screenshot import (
        _extract_hand_data_from_image_claude, _parse_vision_response)
    from app.services.image_utils import detect_image_mime
    b = img_b64 or ""
    if "base64," in b:
        b = b.split("base64,", 1)[1]
    try:
        content = base64.b64decode(b)
    except Exception:
        return None
    mime = detect_image_mime(content) or "image/jpeg"
    text = _extract_hand_data_from_image_claude(content, mime)
    if not text:
        return None
    parsed = _parse_vision_response(text)
    out = {}
    for e in (parsed.get("players_list") or []):
        if e.get("name"):
            out[e["name"]] = e.get("bounty_value_usd")
    return out


def _build_candidates(force: bool = False) -> list[dict]:
    """Seleciona (ou reusa) as 177 e monta as candidatas com as coroas GRAVADAS
    por seat — SEM Vision, sem custo, sem escrita. Cacheado em `_STATE` para o
    preview ("Ver candidatas") e o run usarem o MESMO conjunto (sorteio fixo →
    lista estável). `force=True` re-seleciona."""
    with _LOCK:
        if _STATE.get("candidates") and not force:
            return list(_STATE["candidates"])
    sample = _select_sample()
    cands = []
    for r in sample:
        stored = _crowns_of(r["pn"])
        cands.append({
            "hand_db_id": r["id"], "hand_id": r["hand_id"],
            "entry_id": r.get("entry_id"), "tournament": r["tournament_name"],
            "sliver": r["_sliver"],
            "crowns": [{"seat": k, "stored": v} for k, v in stored.items()],
        })
    with _LOCK:
        _STATE["candidates"] = cands
    return list(cands)


def _run_sample():
    try:
        cands = _build_candidates()   # reusa o preview → mesmo conjunto
    except Exception as exc:  # pragma: no cover - defensivo
        logger.exception("[crown-sample] seleção falhou")
        with _LOCK:
            _STATE.update(status="error", error=str(exc),
                          finished_at=datetime.now(timezone.utc).isoformat())
        return
    with _LOCK:
        _STATE.update(status="running", total=len(cands), done=0,
                      divergences=[], reread_seats=0, error=None, cancel=False,
                      started_at=datetime.now(timezone.utc).isoformat(),
                      finished_at=None)
    cancelled = False
    for c in cands:
        with _LOCK:
            if _STATE.get("cancel"):
                cancelled = True
                break
        divs = []
        try:
            img_b64 = None
            if c.get("entry_id") is not None:
                img = query("SELECT raw_json->>'img_b64' AS img FROM entries WHERE id=%s",
                            (c["entry_id"],))
                img_b64 = img[0]["img"] if img else None
            reread = _reread_crowns(img_b64) if img_b64 else None
            if reread is not None:
                for cr in c["crowns"]:
                    name, sval = cr["seat"], cr["stored"]
                    rval = reread.get(name)
                    with _LOCK:
                        _STATE["reread_seats"] += 1
                    if _diff(sval, rval):
                        divs.append({"seat": name, "stored": sval, "reread": rval})
        except Exception:  # pragma: no cover - defensivo (nunca parte o lote)
            logger.exception("[crown-sample] releitura falhou (hand %s)", c.get("hand_id"))
        with _LOCK:
            _STATE["done"] += 1
            if divs:
                _STATE["divergences"].append({
                    "hand_db_id": c["hand_db_id"], "hand_id": c["hand_id"],
                    "entry_id": c.get("entry_id"), "tournament": c["tournament"],
                    "sliver": c["sliver"], "seats": divs,
                })
    with _LOCK:
        _STATE.update(status="cancelled" if cancelled else "done",
                      finished_at=datetime.now(timezone.utc).isoformat())
    logger.info("[crown-sample] %s: %d/%d, %d mãos com divergência",
                "cancelado" if cancelled else "terminado",
                _STATE["done"], _STATE["total"], len(_STATE["divergences"]))


@router.post("/run")
def crown_sample_run(current_user=Depends(require_auth)):
    """Arranca (ou re-arranca) o amostrador em daemon thread. Idempotente: se já
    corre, não duplica. NÃO escreve nada."""
    with _LOCK:
        if _STATE["status"] == "running":
            return {"status": "running", "done": _STATE["done"], "total": _STATE["total"],
                    "note": "já a correr"}
        _STATE["status"] = "running"
    threading.Thread(target=_run_sample, daemon=True).start()
    return {"status": "running", "note": "amostrador arrancado (177 releituras em background)"}


@router.get("/candidates")
def crown_sample_candidates(reselect: bool = False, current_user=Depends(require_auth)):
    """Modo "Ver candidatas": as 177 com a IMAGEM (entry_id) + coroas GRAVADAS
    por seat + selo do grupo (sliver) + link da mão. SEM Vision, sem custo, sem
    escrita. Sorteio fixo → lista estável. `reselect=true` re-seleciona."""
    cands = _build_candidates(force=reselect)
    return {"total": len(cands),
            "sliver": sum(1 for c in cands if c["sliver"]),
            "candidates": cands}


@router.post("/cancel")
def crown_sample_cancel(current_user=Depends(require_auth)):
    """Cancela o run em curso (bandeira cooperativa) — interrompe na PRÓXIMA
    releitura, mantém o parcial já apurado (status→'cancelled'). NÃO escreve nada."""
    with _LOCK:
        if _STATE["status"] != "running":
            return {"status": _STATE["status"], "note": "nada a cancelar"}
        _STATE["cancel"] = True
    return {"status": "cancelling",
            "note": "interrompe na próxima releitura; mantém o parcial"}


@router.get("")
def crown_sample_state(current_user=Depends(require_auth)):
    """Progresso + lista de divergências (para o painel). NÃO escreve nada."""
    with _LOCK:
        n_div_hands = len(_STATE["divergences"])
        n_div_seats = sum(len(d["seats"]) for d in _STATE["divergences"])
        return {
            "status": _STATE["status"], "done": _STATE["done"], "total": _STATE["total"],
            "reread_seats": _STATE["reread_seats"],
            "divergent_hands": n_div_hands, "divergent_seats": n_div_seats,
            "divergences": list(_STATE["divergences"]),
            "started_at": _STATE["started_at"], "finished_at": _STATE["finished_at"],
            "error": _STATE["error"],
        }
