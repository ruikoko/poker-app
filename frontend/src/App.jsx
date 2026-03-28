"""
Router para Stats — folha de Rail.

Guarda stats mensais por categoria/formato e valores ideais.
Os dados são inseridos manualmente (do HM3 ou da spreadsheet).
"""
import json
import logging
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from typing import Optional
from app.auth import require_auth
from app.db import get_conn, query, execute

router = APIRouter(prefix="/api/stats", tags=["stats"])
logger = logging.getLogger("stats")

# ── Schema ────────────────────────────────────────────────────────────────────

STATS_SCHEMA = [
    """
    CREATE TABLE IF NOT EXISTS monthly_stats (
        id BIGSERIAL PRIMARY KEY,
        month TEXT NOT NULL,
        format TEXT NOT NULL DEFAULT '9-max',
        category TEXT NOT NULL,
        stat_name TEXT NOT NULL,
        value REAL,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        UNIQUE(month, format, category, stat_name)
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_monthly_stats_month ON monthly_stats(month)",
    "CREATE INDEX IF NOT EXISTS idx_monthly_stats_format ON monthly_stats(format)",
    """
    CREATE TABLE IF NOT EXISTS stat_ideals (
        id BIGSERIAL PRIMARY KEY,
        format TEXT NOT NULL DEFAULT '9-max',
        category TEXT NOT NULL,
        stat_name TEXT NOT NULL,
        ideal_value REAL NOT NULL,
        UNIQUE(format, category, stat_name)
    )
    """,
]


def ensure_stats_schema():
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            for sql in STATS_SCHEMA:
                try:
                    cur.execute(sql)
                except Exception as e:
                    conn.rollback()
                    logger.warning(f"Stats schema: {e}")
                    continue
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ── Default ideals (from the spreadsheet top row) ─────────────────────────────

DEFAULT_IDEALS = {
    "9-max": {
        "RFI": {"Early RFI": 19, "Middle RFI": 23, "CO Steal": 36, "BTN Steal": 48},
        "BvB": {"SB UO VPIP": 83, "BB fold to SB steal": 30, "BB raise vs SB limp UOP": 57, "SB Steal": 28},
        "CC/3Bet IP": {
            "EP 3bet": 8, "EP Cold Call": 0, "EP VPIP": 0,
            "MP 3bet": 11, "MP Cold Call": 0, "MP VPIP": 0,
            "CO 3bet": 15, "CO Cold Call": 0, "CO VPIP": 0,
            "BTN 3bet": 0, "BTN Cold Call": 0, "BTN VPIP": 0,
        },
        "Vs 3Bet IP/OOP": {"BTN fold to CO steal": 21, "BTN VPIP": 74, "Fold to 3bet IP": 55, "Fold to 3bet OOP": 50},
        "Squeeze": {"Squeeze": 7, "Squeeze vs BTN Raiser": 12},
        "Defesa BB": {
            "BB fold vs CO steal": 23, "BB fold vs BTN steal": 19, "BB fold vs SB steal": 16,
            "BB resteal vs BTN steal": 0, "BB fold to CO Steal": 0, "BB resteal vs SB steal": 0,
        },
        "Defesa SB": {"SB fold to CO Steal": 0, "SB fold to BTN Steal": 0, "SB resteal vs BTN": 0},
    },
    "6-max": {
        "RFI": {"Early RFI": 23, "Middle RFI": 28, "CO Steal": 34, "BTN Steal": 47},
        "BvB": {"SB UO VPIP": 82, "BB fold to SB steal": 30, "BB raise vs SB limp UOP": 55, "SB Steal": 28},
    },
    "PKO": {
        "RFI": {"Early RFI": 19, "Middle RFI": 23, "CO Steal": 36, "BTN Steal": 48},
        "BvB": {"SB UO VPIP": 83, "BB fold to SB steal": 30, "BB raise vs SB limp UOP": 57, "SB Steal": 28},
    },
    "Post-flop": {
        "Flop Cbet": {"Flop CBet IP %": 90, "Flop CBet 3BetPot IP": 90, "Flop Cbet OOP%": 37},
        "Vs Cbet": {"Flop fold vs Cbet IP": 31, "Flop raise Cbet IP": 12.5, "Flop raise Cbet OOP": 20, "Fold vs Check Raise": 32},
        "Skipped Cbet": {"Flop bet vs missed Cbet SRP": 60},
        "Turn Play": {
            "Turn CBet IP%": 60, "Turn Cbet OOP%": 50, "Turn donk bet": 8,
            "Turn donk bet SRP vs PFR": 12, "Bet turn vs Missed Flop": 45,
        },
        "Turn Fold": {"Turn Fold vs Cbet OOP": 43},
        "River play": {"WTSD%": 30, "W$SD%": 50, "W$WSF Rating": 0, "River Agg %": 2.5, "W$SD% B River": 57},
    },
}


# ── Endpoints ─────────────────────────────────────────────────────────────────

class StatEntry(BaseModel):
    month: str          # "2026-01" or "jan/2026"
    format: str         # "9-max", "6-max", "PKO", "Post-flop"
    category: str       # "RFI", "BvB", etc.
    stat_name: str      # "Early RFI", "BTN Steal", etc.
    value: Optional[float] = None


class StatBulk(BaseModel):
    entries: list[StatEntry]


class IdealEntry(BaseModel):
    format: str
    category: str
    stat_name: str
    ideal_value: float


@router.post("/init-schema")
def init_schema(current_user=Depends(require_auth)):
    """Cria as tabelas de stats se não existirem."""
    ensure_stats_schema()
    return {"ok": True}


@router.post("/save")
def save_stats(body: StatBulk, current_user=Depends(require_auth)):
    """Guarda ou actualiza stats mensais em bulk."""
    ensure_stats_schema()
    conn = get_conn()
    saved = 0
    try:
        with conn.cursor() as cur:
            for e in body.entries:
                if e.value is None:
                    continue
                cur.execute(
                    """INSERT INTO monthly_stats (month, format, category, stat_name, value, updated_at)
                       VALUES (%s, %s, %s, %s, %s, NOW())
                       ON CONFLICT (month, format, category, stat_name)
                       DO UPDATE SET value = EXCLUDED.value, updated_at = NOW()""",
                    (e.month, e.format, e.category, e.stat_name, e.value)
                )
                saved += 1
        conn.commit()
    except Exception as ex:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(ex))
    finally:
        conn.close()
    return {"ok": True, "saved": saved}


@router.get("/monthly")
def get_monthly(
    format: Optional[str] = Query(None),
    month: Optional[str] = Query(None),
    current_user=Depends(require_auth),
):
    """Devolve stats mensais, opcionalmente filtradas por formato e/ou mês."""
    ensure_stats_schema()
    conditions = []
    params = []
    if format:
        conditions.append("format = %s")
        params.append(format)
    if month:
        conditions.append("month = %s")
        params.append(month)
    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""

    rows = query(
        f"SELECT * FROM monthly_stats {where} ORDER BY month DESC, format, category, stat_name",
        params
    )
    return {"data": [dict(r) for r in rows]}


@router.get("/ideals")
def get_ideals(
    format: Optional[str] = Query(None),
    current_user=Depends(require_auth),
):
    """Devolve valores ideais."""
    ensure_stats_schema()
    conditions = []
    params = []
    if format:
        conditions.append("format = %s")
        params.append(format)
    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""

    rows = query(f"SELECT * FROM stat_ideals {where} ORDER BY format, category, stat_name", params)
    return {"data": [dict(r) for r in rows]}


@router.post("/ideals")
def save_ideal(body: IdealEntry, current_user=Depends(require_auth)):
    """Guarda ou actualiza um valor ideal."""
    ensure_stats_schema()
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO stat_ideals (format, category, stat_name, ideal_value)
                   VALUES (%s, %s, %s, %s)
                   ON CONFLICT (format, category, stat_name)
                   DO UPDATE SET ideal_value = EXCLUDED.ideal_value""",
                (body.format, body.category, body.stat_name, body.ideal_value)
            )
        conn.commit()
    except Exception as ex:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(ex))
    finally:
        conn.close()
    return {"ok": True}


@router.post("/ideals/init-defaults")
def init_default_ideals(current_user=Depends(require_auth)):
    """Carrega os valores ideais por defeito (da spreadsheet)."""
    ensure_stats_schema()
    conn = get_conn()
    count = 0
    try:
        with conn.cursor() as cur:
            for fmt, categories in DEFAULT_IDEALS.items():
                for cat, stats in categories.items():
                    for stat_name, ideal in stats.items():
                        cur.execute(
                            """INSERT INTO stat_ideals (format, category, stat_name, ideal_value)
                               VALUES (%s, %s, %s, %s)
                               ON CONFLICT (format, category, stat_name) DO NOTHING""",
                            (fmt, cat, stat_name, ideal)
                        )
                        count += 1
        conn.commit()
    except Exception as ex:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(ex))
    finally:
        conn.close()
    return {"ok": True, "loaded": count}


@router.get("/dashboard")
def dashboard(
    month: Optional[str] = Query(None, description="Mês específico (YYYY-MM) ou vazio para último"),
    current_user=Depends(require_auth),
):
    """
    Devolve dados para o dashboard de stats:
    - stats do mês (ou último mês com dados)
    - valores ideais
    - scores por categoria
    """
    ensure_stats_schema()

    # Se não especificou mês, buscar o último com dados
    if not month:
        latest = query("SELECT DISTINCT month FROM monthly_stats ORDER BY month DESC LIMIT 1")
        if not latest:
            return {"month": None, "stats": {}, "ideals": {}, "scores": {}}
        month = latest[0]["month"]

    # Stats do mês
    rows = query(
        "SELECT format, category, stat_name, value FROM monthly_stats WHERE month = %s ORDER BY format, category",
        (month,)
    )

    # Ideals
    ideal_rows = query("SELECT format, category, stat_name, ideal_value FROM stat_ideals")

    # Organizar stats
    stats = {}
    for r in rows:
        fmt = r["format"]
        cat = r["category"]
        if fmt not in stats:
            stats[fmt] = {}
        if cat not in stats[fmt]:
            stats[fmt][cat] = {}
        stats[fmt][cat][r["stat_name"]] = r["value"]

    # Organizar ideals
    ideals = {}
    for r in ideal_rows:
        fmt = r["format"]
        cat = r["category"]
        if fmt not in ideals:
            ideals[fmt] = {}
        if cat not in ideals[fmt]:
            ideals[fmt][cat] = {}
        ideals[fmt][cat][r["stat_name"]] = r["ideal_value"]

    # Calcular scores (0-100, quanto mais perto do ideal melhor)
    scores = {}
    for fmt in stats:
        scores[fmt] = {}
        fmt_total = 0
        fmt_count = 0
        for cat in stats[fmt]:
            cat_total = 0
            cat_count = 0
            for stat_name, value in stats[fmt][cat].items():
                ideal = ideals.get(fmt, {}).get(cat, {}).get(stat_name)
                if ideal is not None and ideal > 0:
                    # Score = 100 - abs(deviation percentage), capped 0-100
                    deviation = abs(value - ideal) / ideal * 100
                    score = max(0, min(100, 100 - deviation))
                    cat_total += score
                    cat_count += 1
            if cat_count > 0:
                scores[fmt][cat] = round(cat_total / cat_count, 1)
                fmt_total += cat_total
                fmt_count += cat_count
        if fmt_count > 0:
            scores[fmt]["_average"] = round(fmt_total / fmt_count, 1)

    # Lista de meses disponíveis
    months = query("SELECT DISTINCT month FROM monthly_stats ORDER BY month DESC")

    return {
        "month": month,
        "stats": stats,
        "ideals": ideals,
        "scores": scores,
        "available_months": [r["month"] for r in months],
    }
