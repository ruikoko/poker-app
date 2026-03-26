from fastapi import APIRouter, Depends, Query, HTTPException
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
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
    notes:       Optional[str] = None
    tags:        Optional[list[str]] = None
    position:    Optional[str] = None
    study_state: Optional[str] = None


@router.get("")
def list_hands(
    site:        Optional[str] = Query(None),
    tag:         Optional[str] = Query(None, description="Filtrar por tag"),
    study_state: Optional[str] = Query(None, description="Filtrar por estado de estudo"),
    position:    Optional[str] = Query(None, description="Filtrar por posição"),
    search:      Optional[str] = Query(None, description="Pesquisa livre em notas/raw"),
    date_from:   Optional[str] = Query(None, description="Filtrar por data (ISO date, ex: 2026-03-20)"),
    page:        int = Query(1, ge=1),
    page_size:   int = Query(50, ge=1, le=200),
    current_user=Depends(require_auth)
):
    conditions = []
    params = []

    if site:
        conditions.append("h.site = %s")
        params.append(site)

    if tag:
        conditions.append("%s = ANY(h.tags)")
        params.append(tag)

    if study_state:
        conditions.append("h.study_state = %s")
        params.append(study_state)

    if position:
        conditions.append("h.position = %s")
        params.append(position)

    if search:
        conditions.append("(h.notes ILIKE %s OR h.raw ILIKE %s OR h.hand_id ILIKE %s OR h.stakes ILIKE %s)")
        like = f"%{search}%"
        params.extend([like, like, like, like])

    if date_from:
        conditions.append("h.played_at >= %s")
        params.append(date_from)

    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""

    total = query(f"SELECT COUNT(*) AS total FROM hands h LEFT JOIN entries e ON h.entry_id = e.id LEFT JOIN discord_sync_state d ON e.discord_channel = d.channel_id {where}", params)[0]["total"]
    offset = (page - 1) * page_size

    rows = query(
        f"""
        SELECT h.id, h.site, h.hand_id, h.played_at, h.stakes, h.position,
               h.hero_cards, h.board, h.result, h.currency, h.notes, h.tags,
               h.study_state, h.entry_id, h.viewed_at, h.studied_at, h.created_at,
               h.all_players_actions, h.screenshot_url, h.player_names,
               e.discord_channel, e.discord_posted_at,
               d.channel_name AS discord_channel_name
        FROM hands h
        LEFT JOIN entries e ON h.entry_id = e.id
        LEFT JOIN discord_sync_state d ON e.discord_channel = d.channel_id
        {where}
        ORDER BY h.played_at DESC NULLS LAST, h.id DESC
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


@router.get("/stats")
def hand_stats(current_user=Depends(require_auth)):
    """Estatísticas globais das mãos."""
    rows = query("""
        SELECT
            COUNT(*) AS total,
            COUNT(*) FILTER (WHERE study_state = 'new') AS new,
            COUNT(*) FILTER (WHERE study_state = 'review') AS review,
            COUNT(*) FILTER (WHERE study_state = 'studying') AS studying,
            COUNT(*) FILTER (WHERE study_state = 'resolved') AS resolved,
            COUNT(DISTINCT site) AS sites,
            COUNT(DISTINCT position) FILTER (WHERE position IS NOT NULL) AS positions
        FROM hands
    """)
    return dict(rows[0]) if rows else {}


@router.get("/{hand_pk}")
def get_hand(hand_pk: int, current_user=Depends(require_auth)):
    rows = query("""
        SELECT h.*, e.discord_channel, e.discord_posted_at,
               d.channel_name AS discord_channel_name
        FROM hands h
        LEFT JOIN entries e ON h.entry_id = e.id
        LEFT JOIN discord_sync_state d ON e.discord_channel = d.channel_id
        WHERE h.id = %s
    """, (hand_pk,))
    if not rows:
        raise HTTPException(status_code=404, detail="Mão não encontrada")

    hand = dict(rows[0])

    # Marcar como vista se ainda não foi
    if not hand.get("viewed_at"):
        execute(
            "UPDATE hands SET viewed_at = NOW() WHERE id = %s",
            (hand_pk,)
        )
        hand["viewed_at"] = datetime.utcnow().isoformat()

    return hand


@router.post("")
def create_hand(body: HandCreate, current_user=Depends(require_auth)):
    row = execute_returning(
        """
        INSERT INTO hands
            (site, hand_id, played_at, stakes, position, hero_cards,
             board, result, currency, notes, tags, raw, study_state)
        VALUES
            (%(site)s, %(hand_id)s, %(played_at)s, %(stakes)s, %(position)s,
             %(hero_cards)s, %(board)s, %(result)s, %(currency)s,
             %(notes)s, %(tags)s, %(raw)s, 'new')
        RETURNING id, created_at
        """,
        body.model_dump()
    )
    return {"id": row["id"], "created_at": row["created_at"]}


@router.patch("/{hand_pk}")
def update_hand(hand_pk: int, body: HandUpdate, current_user=Depends(require_auth)):
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    if not updates:
        raise HTTPException(status_code=400, detail="Nada para actualizar")

    # Se mudar para 'resolved', registar studied_at
    if updates.get("study_state") == "resolved":
        updates["studied_at"] = datetime.utcnow()

    set_clause = ", ".join(f"{k} = %({k})s" for k in updates)
    updates["hand_pk"] = hand_pk

    execute(
        f"UPDATE hands SET {set_clause} WHERE id = %(hand_pk)s",
        updates
    )
    return {"ok": True}


@router.delete("/{hand_pk}")
def delete_hand(hand_pk: int, current_user=Depends(require_auth)):
    execute("DELETE FROM hands WHERE id = %s", (hand_pk,))
    return {"ok": True}
