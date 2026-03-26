from fastapi import APIRouter, Depends, Query, HTTPException
from app.auth import require_auth
from app.db import query

router = APIRouter(prefix="/api/tournaments", tags=["tournaments"])


def _build_query(
    site:     str | None,
    type_:    str | None,
    speed:    str | None,
    result:   str | None,
    buyin_min: float | None,
    buyin_max: float | None,
    date_from: str | None,
    date_to:   str | None,
    page:      int,
    page_size: int,
):
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
            t.id, t.site, t.tid, t.name, t.date,
            t.buyin, t.cashout, t.result,
            t.position, t.players,
            t.type, t.speed, t.currency,
            t.import_id, t.created_at,
            COUNT(h.id) AS hand_count
        FROM tournaments t
        LEFT JOIN hands h ON h.tournament_id = t.id
        {where.replace('WHERE ', 'WHERE t.') if where else ''}
        GROUP BY t.id
        ORDER BY t.date DESC, t.id DESC
        LIMIT %s OFFSET %s
    """
    return sql_data, sql_count, params, offset, page_size


@router.get("")
def list_tournaments(
    site:      str | None = Query(None),
    type_:     str | None = Query(None, alias="type"),
    speed:     str | None = Query(None),
    result:    str | None = Query(None),
    buyin_min: float | None = Query(None),
    buyin_max: float | None = Query(None),
    date_from: str | None = Query(None),
    date_to:   str | None = Query(None),
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
    total = query(sql_count, params)[0]["total"]
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
            site, currency,
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


@router.get("/{tournament_id}/hands")
def tournament_hands(
    tournament_id: int,
    page:      int = Query(1, ge=1),
    page_size: int = Query(200, ge=1, le=500),
    current_user=Depends(require_auth)
):
    """Lista todas as mãos de um torneio específico."""
    t_rows = query("SELECT * FROM tournaments WHERE id = %s", (tournament_id,))
    if not t_rows:
        raise HTTPException(status_code=404, detail="Torneio não encontrado")
    tournament = dict(t_rows[0])

    offset = (page - 1) * page_size
    total = query(
        "SELECT COUNT(*) AS total FROM hands WHERE tournament_id = %s",
        (tournament_id,)
    )[0]["total"]
    rows = query(
        """
        SELECT id, hand_id, played_at, stakes, position,
               hero_cards, board, result, currency, notes, tags,
               study_state, all_players_actions, screenshot_url, player_names
        FROM hands
        WHERE tournament_id = %s
        ORDER BY played_at ASC NULLS LAST, id ASC
        LIMIT %s OFFSET %s
        """,
        (tournament_id, page_size, offset)
    )

    return {
        "tournament": tournament,
        "total":      total,
        "page":       page,
        "page_size":  page_size,
        "pages":      (total + page_size - 1) // page_size,
        "data":       [dict(r) for r in rows],
    }
