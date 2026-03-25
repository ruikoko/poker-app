from fastapi import APIRouter, Depends, Query, HTTPException
from pydantic import BaseModel
from typing import Optional
from app.auth import require_auth
from app.db import query, execute, execute_returning

router = APIRouter(prefix="/api/hands", tags=["hands"])


class HandCreate(BaseModel):
    site:       Optional[str] = None
    hand_id:    Optional[str] = None
    played_at:  Optional[str] = None   # ISO datetime string
    stakes:     Optional[str] = None
    position:   Optional[str] = None
    hero_cards: Optional[list[str]] = None
    board:      Optional[list[str]] = None
    result:     Optional[float] = None
    currency:   Optional[str] = None
    notes:      Optional[str] = None
    tags:       Optional[list[str]] = None
    raw:        Optional[str] = None   # HH original


class HandUpdate(BaseModel):
    notes:    Optional[str] = None
    tags:     Optional[list[str]] = None
    position: Optional[str] = None


@router.get("")
def list_hands(
    site:      Optional[str] = Query(None),
    tag:       Optional[str] = Query(None, description="Filtrar por tag"),
    page:      int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    current_user=Depends(require_auth)
):
    conditions = []
    params = []

    if site:
        conditions.append("site = %s")
        params.append(site)

    if tag:
        conditions.append("%s = ANY(tags)")
        params.append(tag)

    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""

    total = query(f"SELECT COUNT(*) AS total FROM hands {where}", params)[0]["total"]
    offset = (page - 1) * page_size

    rows = query(
        f"""
        SELECT id, site, hand_id, played_at, stakes, position,
               hero_cards, board, result, currency, notes, tags, created_at
        FROM hands
        {where}
        ORDER BY played_at DESC NULLS LAST, id DESC
        LIMIT %s OFFSET %s
        """,
        params + [page_size, offset]
    )

    return {
        "total":     total,
        "page":      page,
        "page_size": page_size,
        "pages":     (total + page_size - 1) // page_size,
        "data":      [dict(r) for r in rows],
    }


@router.get("/{hand_id}")
def get_hand(hand_id: int, current_user=Depends(require_auth)):
    rows = query("SELECT * FROM hands WHERE id = %s", (hand_id,))
    if not rows:
        raise HTTPException(status_code=404, detail="Mão não encontrada")
    return dict(rows[0])


@router.post("")
def create_hand(body: HandCreate, current_user=Depends(require_auth)):
    row = execute_returning(
        """
        INSERT INTO hands
            (site, hand_id, played_at, stakes, position, hero_cards,
             board, result, currency, notes, tags, raw)
        VALUES
            (%(site)s, %(hand_id)s, %(played_at)s, %(stakes)s, %(position)s,
             %(hero_cards)s, %(board)s, %(result)s, %(currency)s,
             %(notes)s, %(tags)s, %(raw)s)
        RETURNING id, created_at
        """,
        body.model_dump()
    )
    return {"id": row["id"], "created_at": row["created_at"]}


@router.patch("/{hand_id}")
def update_hand(hand_id: int, body: HandUpdate, current_user=Depends(require_auth)):
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    if not updates:
        raise HTTPException(status_code=400, detail="Nada para actualizar")

    set_clause = ", ".join(f"{k} = %({k})s" for k in updates)
    updates["hand_id_pk"] = hand_id

    rows = execute(
        f"UPDATE hands SET {set_clause} WHERE id = %(hand_id_pk)s",
        updates
    )
    if not rows:
        raise HTTPException(status_code=404, detail="Mão não encontrada")
    return {"ok": True}


@router.delete("/{hand_id}")
def delete_hand(hand_id: int, current_user=Depends(require_auth)):
    rows = execute("DELETE FROM hands WHERE id = %s", (hand_id,))
    if not rows:
        raise HTTPException(status_code=404, detail="Mão não encontrada")
    return {"ok": True}
