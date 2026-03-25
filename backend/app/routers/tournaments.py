from fastapi import APIRouter, Depends, Query
from app.auth import require_auth
from app.db import query

router = APIRouter(prefix="/api/tournaments", tags=["tournaments"])


def _build_query(
    site:     str | None,
    type_:    str | None,
    speed:    str | None,
    result:   str | None,    # "itm" | "bust" | None
    buyin_min: float | None,
    buyin_max: float | None,
    date_from: str | None,   # YYYY-MM-DD
    date_to:   str | None,
    page:      int,
    page_size: int,
) -> tuple[str, str, list]:
    """
    Constrói duas queries parametrizadas: uma para dados, outra para COUNT.
    Devolve (sql_data, sql_count, params).
    """
    conditions = []
    params = []

    if site:
        conditions.append("site = %s")
        params.append(site)

    if type_:
        conditions.append("type = %s")
        params.append(type_)

    if speed:
        conditions.append("speed = %s")
        params.append(speed)

    if result == "cashed":
        conditions.append("cashout > 0")
    elif result == "no_cash":
        conditions.append("cashout = 0")

    if buyin_min is not None:
        conditions.append("buyin >= %s")
        params.append(buyin_min)

    if buyin_max is not None:
        conditions.append("buyin <= %s")
        params.append(buyin_max)

    if date_from:
        conditions.append("date >= %s")
        params.append(date_from)

    if date_to:
        conditions.append("date <= %s")
        params.append(date_to)

    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""

    sql_count = f"SELECT COUNT(*) AS total FROM tournaments {where}"

    offset = (page - 1) * page_size
    sql_data = f"""
        SELECT
            id, site, tid, name, date,
            buyin, cashout, result,
            position, players,
            type, speed, currency,
            import_id, created_at
        FROM tournaments
        {where}
        ORDER BY date DESC, id DESC
        LIMIT %s OFFSET %s
    """

    return sql_data, sql_count, params, offset, page_size


@router.get("")
def list_tournaments(
    site:      str | None = Query(None, description="Winamax | GGPoker | PokerStars | WPN"),
    type_:     str | None = Query(None, alias="type", description="ko | nonko"),
    speed:     str | None = Query(None, description="normal | turbo | hyper"),
    result:    str | None = Query(None, description="cashed (cashout>0) | no_cash (cashout=0)"),
    buyin_min: float | None = Query(None),
    buyin_max: float | None = Query(None),
    date_from: str | None = Query(None, description="YYYY-MM-DD"),
    date_to:   str | None = Query(None, description="YYYY-MM-DD"),
    page:      int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    current_user=Depends(require_auth)
):
    sql_data, sql_count, params, offset, size = _build_query(
        site, type_, speed, result,
        buyin_min, buyin_max,
        date_from, date_to,
        page, page_size
    )

    total_row = query(sql_count, params)
    total = total_row[0]["total"]

    rows = query(sql_data, params + [size, offset])

    return {
        "total":     total,
        "page":      page,
        "page_size": size,
        "pages":     (total + size - 1) // size,
        "data":      [dict(r) for r in rows],
    }


@router.get("/summary")
def tournaments_summary(
    site: str | None = Query(None),
    current_user=Depends(require_auth)
):
    """Agregados por sala: total torneios, profit, ITM%, ROI."""
    where = "WHERE site = %s" if site else ""
    params = [site] if site else []

    rows = query(
        f"""
        SELECT
            site,
            currency,
            COUNT(*)                                        AS total,
            SUM(buyin)                                      AS total_buyin,
            SUM(cashout)                                    AS total_cashout,
            SUM(result)                                     AS profit,
            ROUND(
                100.0 * COUNT(*) FILTER (WHERE cashout > 0)
                / NULLIF(COUNT(*), 0), 1
            )                                              AS itm_pct,
            ROUND(
                100.0 * SUM(result) / NULLIF(SUM(buyin), 0), 1
            )                                              AS roi_pct
        FROM tournaments
        {where}
        GROUP BY site, currency
        ORDER BY site
        """,
        params
    )
    return [dict(r) for r in rows]
