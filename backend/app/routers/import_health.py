"""Saúde do Import (pt68) — agrega o que os logs de importação já registam, por
pipeline, com contagens + lista de falhas/rejeitados/sem-match (motivo + timestamp).

v1 read-only sobre as tabelas existentes:
  • mesa   → table_ss_processing_log (result/reason_detail/captured_at/site)
  • lobby  → lobby_processing_log    (result/reason_detail/posted_at/site)
  • hh_ts  → import_logs             (status/records_*/log/imported_at)  [só /api/import]
  • inbox  → entries                 (source/entry_type/status/created_at)

Janela: conceito "dia-de-jogo" 15:00→15:00 (Lisboa naive). `?day=YYYY-MM-DD` →
[day 15:00, (day+1) 15:00]. Sem `day` → tudo.

Buracos conhecidos (logging a acrescentar em v2, devolvidos em `holes`):
  • HM3 import (.bat) não persiste log (só devolve o resumo na resposta).
  • Vision do replayer GG falha em log de CONSOLA, não em tabela queryable.
  • Ficheiros rejeitados no appimport (SKIP) são client-side → sem rasto na BD.
"""
from __future__ import annotations
import logging
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from app.auth import require_auth
from app.db import query

router = APIRouter(prefix="/api/import-health", tags=["import-health"])
logger = logging.getLogger("import_health")

_FAIL_LIMIT = 300

# Resultados "sucesso" por pipeline (tudo o resto é falha/sem-match).
_OK_RESULTS = {"success"}

_HOLES = [
    "HM3 (.bat): sem log persistente — só o resumo na resposta do import.",
    "Vision do replayer GG: falhas só em log de consola, não em tabela.",
    "Ficheiros rejeitados/saltados no appimport (SKIP): client-side, sem rasto na BD.",
    "Parse de HH por mão: erros agregados no import_logs.log; não há detalhe por mão.",
]


def _window(day: Optional[str]) -> Optional[tuple]:
    """`day` YYYY-MM-DD → (from, to) = [day 15:00, (day+1) 15:00] Lisboa naive.
    None → sem janela."""
    if not day:
        return None
    try:
        d = datetime.strptime(day.strip(), "%Y-%m-%d")
    except (ValueError, AttributeError):
        raise HTTPException(400, "day deve ser YYYY-MM-DD")
    lo = d.replace(hour=15, minute=0, second=0, microsecond=0)
    return (lo, lo + timedelta(days=1))


def _result_block(table: str, time_expr: str, win: Optional[tuple],
                  fail_cols: str) -> dict:
    """Bloco genérico para as tabelas com coluna `result` (mesa/lobby).
    `time_expr` = expressão SQL do timestamp (já em Lisboa naive)."""
    where, params = "", []
    if win:
        where = f" WHERE {time_expr} >= %s AND {time_expr} < %s"
        params = [win[0], win[1]]
    by = query(
        f"SELECT result, COUNT(*) AS n FROM {table}{where} GROUP BY result "
        f"ORDER BY n DESC", tuple(params),
    )
    total = sum(r["n"] for r in by)
    ok = sum(r["n"] for r in by if r["result"] in _OK_RESULTS)
    fails = query(
        f"SELECT {fail_cols}, {time_expr} AS at FROM {table}"
        f"{where}{' AND' if where else ' WHERE'} result <> ALL(%s) "
        f"ORDER BY at DESC NULLS LAST LIMIT {_FAIL_LIMIT}",
        tuple(params) + (list(_OK_RESULTS),),
    )
    return {
        "total": total, "ok": ok, "fail": total - ok,
        "by_result": [dict(r) for r in by],
        "failures": [dict(r) for r in fails],
    }


@router.get("")
def import_health(
    day: Optional[str] = Query(None, description="dia-de-jogo YYYY-MM-DD (15:00→15:00)"),
    current_user=Depends(require_auth),
):
    win = _window(day)
    out = {
        "filter": {"day": day,
                   "from": win[0].isoformat() if win else None,
                   "to": win[1].isoformat() if win else None},
        "pipelines": {},
        "holes": _HOLES,
    }

    # ── mesa (table_ss_processing_log) ──────────────────────────────────────
    try:
        blk = _result_block(
            "table_ss_processing_log",
            "captured_at",
            win,
            "id, original_filename AS filename, result, reason_detail AS reason, "
            "site, tournament_number",
        )
        blk["label"] = "SS de mesa (Intuitive Tables)"
        blk["time_field"] = "captured_at (hora de captura)"
        out["pipelines"]["mesa"] = blk
    except Exception as e:
        logger.exception("import-health mesa")
        out["pipelines"]["mesa"] = {"error": f"{type(e).__name__}: {e}"}

    # ── lobby (lobby_processing_log) ────────────────────────────────────────
    try:
        lobby_time = ("COALESCE((posted_at AT TIME ZONE 'Europe/Lisbon'), "
                      "(attempted_at AT TIME ZONE 'Europe/Lisbon'))")
        blk = _result_block(
            "lobby_processing_log",
            lobby_time,
            win,
            "discord_message_id AS id, result, reason_detail AS reason, site, "
            "tournament_number",
        )
        blk["label"] = "SS de lobby (→ payouts)"
        blk["time_field"] = "posted_at / attempted_at"
        out["pipelines"]["lobby"] = blk
    except Exception as e:
        logger.exception("import-health lobby")
        out["pipelines"]["lobby"] = {"error": f"{type(e).__name__}: {e}"}

    # ── HH/TS (import_logs) ─────────────────────────────────────────────────
    try:
        where, params = "", []
        if win:
            where = " WHERE (imported_at AT TIME ZONE 'Europe/Lisbon') >= %s " \
                    "AND (imported_at AT TIME ZONE 'Europe/Lisbon') < %s"
            params = [win[0], win[1]]
        runs = query(
            "SELECT id, site, filename, status, records_found, records_ok, "
            "records_skipped, records_error, LEFT(COALESCE(log,''), 2000) AS log, "
            "imported_at AS at FROM import_logs" + where +
            " ORDER BY imported_at DESC LIMIT 500", tuple(params),
        )
        n_err = sum(1 for r in runs if r["status"] == "error")
        n_part = sum(1 for r in runs if r["status"] == "partial")
        out["pipelines"]["hh_ts"] = {
            "label": "Import HH/TS por ficheiro (/api/import)",
            "time_field": "imported_at (hora de import)",
            "total": len(runs), "errors": n_err, "partial": n_part,
            "runs": [dict(r) for r in runs],
        }
    except Exception as e:
        logger.exception("import-health hh_ts")
        out["pipelines"]["hh_ts"] = {"error": f"{type(e).__name__}: {e}"}

    # ── hands importadas (overview por played_at = hora de jogo) ────────────
    try:
        where, params = "", []
        if win:
            where = " WHERE played_at >= %s AND played_at < %s"
            params = [win[0], win[1]]
        by = query(
            "SELECT site, study_state, COUNT(*) AS n FROM hands" + where +
            " GROUP BY site, study_state ORDER BY n DESC", tuple(params),
        )
        # mãos GG anónimas (sem nicks reais) = sem match SS↔HH ainda
        no_match = query(
            "SELECT COUNT(*) AS n FROM hands" +
            (where + " AND" if where else " WHERE") +
            " site = 'GGPoker' AND (player_names->>'match_method') IS NULL",
            tuple(params),
        )[0]["n"]
        out["pipelines"]["hands"] = {
            "label": "Mãos importadas (resultado)",
            "time_field": "played_at (hora de jogo) — o ÚNICO com dia-de-jogo real",
            "total": sum(r["n"] for r in by),
            "gg_sem_match": no_match,
            "by_site_state": [dict(r) for r in by],
        }
    except Exception as e:
        logger.exception("import-health hands")
        out["pipelines"]["hands"] = {"error": f"{type(e).__name__}: {e}"}

    # ── inbox (entries) ─────────────────────────────────────────────────────
    try:
        where, params = "", []
        if win:
            where = " WHERE created_at >= %s AND created_at < %s"
            params = [win[0], win[1]]
        by = query(
            "SELECT source, entry_type, status, COUNT(*) AS n FROM entries" + where +
            " GROUP BY source, entry_type, status ORDER BY n DESC", tuple(params),
        )
        failed = query(
            "SELECT id, source, entry_type, created_at AS at FROM entries" +
            (where + " AND" if where else " WHERE") + " status = 'failed' "
            "ORDER BY created_at DESC NULLS LAST LIMIT " + str(_FAIL_LIMIT),
            tuple(params),
        )
        out["pipelines"]["inbox"] = {
            "label": "Inbox (entries) — Discord + uploads",
            "time_field": "created_at",
            "total": sum(r["n"] for r in by),
            "failed": len(failed),
            "by_source_type_status": [dict(r) for r in by],
            "failed_items": [dict(r) for r in failed],
        }
    except Exception as e:
        logger.exception("import-health inbox")
        out["pipelines"]["inbox"] = {"error": f"{type(e).__name__}: {e}"}

    return out
