"""Detetor de bounties recuperáveis — endpoints (#CROWN-RECOVERY).

Varre TODAS as mãos GG KO/PKO com Gold e classifica coroas NULL (via
`services.crown_recovery.classify_hand`): grupo 1 (bustou+NULL = recuperável),
grupo 2 (não-bustou+não-Hero+NULL = falha real → balde das coroas), e over-read
(Seat lines != extraídos → revisão à parte, fora do grupo-1 automático).

Scan em daemon thread com CANCELAR (regra permanente: toda op em lote cancela;
mantém o parcial). Read-only — NÃO escreve. A escrita é o fluxo (A)+(B), gated
pelo carimbo do Rui, mostrando SEMPRE a imagem antes (LICAO 14 Jul)."""
from __future__ import annotations
import logging
import threading
from datetime import datetime, timezone

from fastapi import APIRouter, Depends

from app.auth import require_auth
from app.db import query
from app.services.crown_recovery import classify_hand

router = APIRouter(prefix="/api/gg-health/crown-recovery", tags=["crown-recovery"])
logger = logging.getLogger("crown_recovery")

_STATE: dict = {
    "status": "idle",          # idle | running | done | cancelled | error
    "done": 0, "total": 0,
    "group1": [], "group2": [], "over_read": [],
    "cancel": False,
    "started_at": None, "finished_at": None, "error": None,
}
_LOCK = threading.Lock()

_POP_SQL = (
    "SELECT h.id, h.hand_id, h.tournament_name, h.raw, h.player_names AS pn, "
    "       e.id AS entry_id "
    "FROM hands h JOIN entries e ON e.id = h.entry_id AND e.entry_type='screenshot' "
    "     AND (e.raw_json->>'img_b64') IS NOT NULL "
    "WHERE h.site='GGPoker' AND h.played_at >= '2026-01-01' "
    "  AND lower(COALESCE(h.tournament_format,'')) ~ 'ko|pko|bounty' "
    "ORDER BY h.played_at DESC"
)


def _run_scan():
    try:
        rows = query(_POP_SQL)
    except Exception as exc:  # pragma: no cover - defensivo
        logger.exception("[crown-recovery] query da população falhou")
        with _LOCK:
            _STATE.update(status="error", error=str(exc),
                          finished_at=datetime.now(timezone.utc).isoformat())
        return
    with _LOCK:
        _STATE.update(status="running", total=len(rows), done=0,
                      group1=[], group2=[], over_read=[], error=None, cancel=False,
                      started_at=datetime.now(timezone.utc).isoformat(), finished_at=None)
    cancelled = False
    for r in rows:
        with _LOCK:
            if _STATE.get("cancel"):
                cancelled = True
                break
        try:
            res = classify_hand(r["raw"], r["pn"])
            base = {"hand_db_id": r["id"], "hand_id": r["hand_id"],
                    "entry_id": r["entry_id"], "tournament": r["tournament_name"]}
            if res["over_read"]:
                # over-read fora do grupo-1 automático (revisão à parte)
                with _LOCK:
                    _STATE["over_read"].append({**base, "num_hh": res["num_hh"],
                                                "num_extracted": res["num_extracted"]})
            elif res["group1"]:
                with _LOCK:
                    _STATE["group1"].append({**base, "busted": res["group1"],
                                             "matadores": res["matadores"]})
            if not res["over_read"] and res["group2"]:
                with _LOCK:
                    _STATE["group2"].append({**base, "seats": res["group2"]})
        except Exception:  # pragma: no cover - defensivo (nunca parte o lote)
            logger.exception("[crown-recovery] classify falhou (hand %s)", r.get("hand_id"))
        with _LOCK:
            _STATE["done"] += 1
    with _LOCK:
        _STATE.update(status="cancelled" if cancelled else "done",
                      finished_at=datetime.now(timezone.utc).isoformat())
    logger.info("[crown-recovery] %s: %d/%d | G1=%d G2=%d over=%d",
                "cancelado" if cancelled else "terminado", _STATE["done"], _STATE["total"],
                len(_STATE["group1"]), len(_STATE["group2"]), len(_STATE["over_read"]))


@router.post("/scan")
def crown_recovery_scan(current_user=Depends(require_auth)):
    """Arranca (ou re-arranca) o scan em daemon thread. Idempotente. Read-only."""
    with _LOCK:
        if _STATE["status"] == "running":
            return {"status": "running", "done": _STATE["done"], "total": _STATE["total"],
                    "note": "já a correr"}
        _STATE["status"] = "running"
    threading.Thread(target=_run_scan, daemon=True).start()
    return {"status": "running", "note": "scan arrancado (todas as KO/PKO c/ Gold)"}


@router.post("/cancel")
def crown_recovery_cancel(current_user=Depends(require_auth)):
    """Cancela o scan em curso — interrompe na próxima mão, mantém o parcial."""
    with _LOCK:
        if _STATE["status"] != "running":
            return {"status": _STATE["status"], "note": "nada a cancelar"}
        _STATE["cancel"] = True
    return {"status": "cancelling", "note": "interrompe na próxima mão; mantém o parcial"}


@router.get("")
def crown_recovery_state(current_user=Depends(require_auth)):
    """Progresso + worklists (grupo 1 recuperável, grupo 2 falha real, over-read).
    NÃO escreve nada."""
    with _LOCK:
        return {
            "status": _STATE["status"], "done": _STATE["done"], "total": _STATE["total"],
            "group1_count": len(_STATE["group1"]),
            "group2_count": len(_STATE["group2"]),
            "over_read_count": len(_STATE["over_read"]),
            "group1": list(_STATE["group1"]),
            "group2": list(_STATE["group2"]),
            "over_read": list(_STATE["over_read"]),
            "started_at": _STATE["started_at"], "finished_at": _STATE["finished_at"],
            "error": _STATE["error"],
        }
