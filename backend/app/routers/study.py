"""
Router para sessões de estudo.

Modelo simples: cada sessão é um par (hand_id, start_time, end_time).
O frontend chama POST /start quando o utilizador carrega em "Estudar"
numa mão, e POST /stop quando carrega em "Parar" ou sai da página.

Permite calcular tempo total, tempo semanal e histórico por mão.
"""
import logging
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from app.auth import require_auth
from app.db import get_conn, query, execute_returning

router = APIRouter(prefix="/api/study", tags=["study"])
logger = logging.getLogger("study")


def ensure_study_schema():
    """Cria tabela study_sessions se não existir."""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS study_sessions (
                    id          BIGSERIAL PRIMARY KEY,
                    hand_id     BIGINT REFERENCES hands(id) ON DELETE SET NULL,
                    started_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    ended_at    TIMESTAMPTZ,
                    duration_s  INTEGER
                )
            """)
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_study_sessions_hand
                ON study_sessions(hand_id)
            """)
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_study_sessions_started
                ON study_sessions(started_at DESC)
            """)
        conn.commit()
    except Exception as e:
        conn.rollback()
        logger.warning(f"ensure_study_schema: {e}")
    finally:
        conn.close()


class StartBody(BaseModel):
    hand_id: int | None = None


class StopBody(BaseModel):
    session_id: int


@router.post("/start")
def start_session(body: StartBody, current_user=Depends(require_auth)):
    """
    Começa uma nova sessão de estudo.
    Devolve o session_id para o frontend guardar e enviar em /stop.
    """
    row = execute_returning(
        """
        INSERT INTO study_sessions (hand_id, started_at)
        VALUES (%s, NOW())
        RETURNING id, hand_id, started_at
        """,
        (body.hand_id,)
    )
    if not row:
        raise HTTPException(500, "Falha ao criar sessão")
    return {
        "session_id": row["id"],
        "hand_id": row["hand_id"],
        "started_at": row["started_at"].isoformat() if row["started_at"] else None,
    }


@router.post("/stop")
def stop_session(body: StopBody, current_user=Depends(require_auth)):
    """
    Termina a sessão aberta.
    Calcula duração em segundos. Ignora sessões já fechadas.
    """
    rows = query(
        "SELECT id, started_at, ended_at FROM study_sessions WHERE id = %s",
        (body.session_id,)
    )
    if not rows:
        raise HTTPException(404, "Sessão não encontrada")
    session = dict(rows[0])
    if session.get("ended_at"):
        # Já fechada — idempotente, não é erro
        return {"session_id": session["id"], "duration_s": session.get("duration_s") or 0, "already_closed": True}

    started = session["started_at"]
    updated = execute_returning(
        """
        UPDATE study_sessions
        SET ended_at = NOW(),
            duration_s = EXTRACT(EPOCH FROM (NOW() - started_at))::INTEGER
        WHERE id = %s
        RETURNING id, duration_s, ended_at
        """,
        (body.session_id,)
    )
    if not updated:
        raise HTTPException(500, "Falha ao fechar sessão")
    return {
        "session_id": updated["id"],
        "duration_s": updated["duration_s"],
        "ended_at": updated["ended_at"].isoformat() if updated["ended_at"] else None,
    }


@router.get("/week")
def weekly_study(current_user=Depends(require_auth)):
    """
    Total desta semana (segunda 00:00 → domingo 23:59) + breakdown
    por dia para o sparkline do dashboard.
    """
    today = datetime.now(timezone.utc).date()
    monday = today - timedelta(days=today.weekday())

    rows = query(
        """
        SELECT
            DATE(started_at AT TIME ZONE 'UTC') AS day,
            COALESCE(SUM(duration_s), 0) AS seconds
        FROM study_sessions
        WHERE started_at >= %s
          AND ended_at IS NOT NULL
        GROUP BY day
        ORDER BY day
        """,
        (monday,)
    )
    day_map = {r["day"]: int(r["seconds"]) for r in rows}
    days = []
    for i in range(7):
        d = monday + timedelta(days=i)
        days.append({
            "day": d.isoformat(),
            "seconds": day_map.get(d, 0),
        })
    total_s = sum(d["seconds"] for d in days)
    return {
        "week_start": monday.isoformat(),
        "total_seconds": total_s,
        "days": days,
    }
