"""GET /api/tournaments/meta -- metadata canonica por torneio."""
from typing import Optional
from fastapi import APIRouter, Depends, Query
from app.auth import require_auth
from app.db import query

router = APIRouter(prefix="/api/tournaments", tags=["tournaments-meta"])


@router.get("/meta")
def get_tournaments_meta(
    tms: Optional[str] = Query(None, description="CSV de tournament_numbers; sem param = todos"),
    current_user=Depends(require_auth),
):
    """
    Devolve dict {tournament_number: {starting_stack, name, format, buy_in,
    currency, start_time, site, hand_count}}.

    Sem param tms -> todos os tournaments_meta. Com tms -> so os pedidos.
    """
    if tms:
        tm_list = [t.strip() for t in tms.split(",") if t.strip()]
        if not tm_list:
            return {"data": {}}
        rows = query(
            """SELECT * FROM tournaments_meta
                WHERE tournament_number = ANY(%s)""",
            (tm_list,),
        )
    else:
        rows = query("SELECT * FROM tournaments_meta")

    data = {}
    for r in rows:
        d = dict(r)
        if d.get("start_time"):
            d["start_time"] = d["start_time"].isoformat()
        if d.get("updated_at"):
            d["updated_at"] = d["updated_at"].isoformat()
        if d.get("buy_in") is not None:
            d["buy_in"] = float(d["buy_in"])
        if d.get("starting_stack") is not None:
            d["starting_stack"] = float(d["starting_stack"])
        data[d["tournament_number"]] = d
    return {"data": data}
