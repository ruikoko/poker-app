from fastapi import APIRouter, Depends, Query, HTTPException
from pydantic import BaseModel
from typing import Optional
from app.auth import require_auth
from app.db import query, execute, execute_returning

router = APIRouter(prefix="/api/villains", tags=["villains"])


class VillainCreate(BaseModel):
    site:       Optional[str] = None
    nick:       str
    note:       Optional[str] = None
    tags:       Optional[list[str]] = None
    hands_seen: Optional[int] = 0


class VillainUpdate(BaseModel):
    note:       Optional[str] = None
    tags:       Optional[list[str]] = None
    hands_seen: Optional[int] = None


@router.get("")
def list_villains(
    site:      Optional[str] = Query(None),
    tag:       Optional[str] = Query(None),
    search:    Optional[str] = Query(None, description="Busca por nick (ILIKE)"),
    sort:      Optional[str] = Query(None, description="Ordenação: hands_desc, hands_asc, updated_desc, updated_asc, nick_asc"),
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

    if search:
        conditions.append("nick ILIKE %s")
        params.append(f"%{search}%")

    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""

    # Sort
    sort_map = {
        "hands_desc": "hands_seen DESC NULLS LAST",
        "hands_asc": "hands_seen ASC NULLS LAST",
        "updated_desc": "updated_at DESC",
        "updated_asc": "updated_at ASC",
        "nick_asc": "nick ASC",
    }
    order_by = sort_map.get(sort, "hands_seen DESC NULLS LAST")

    total = query(f"SELECT COUNT(*) AS total FROM villain_notes {where}", params)[0]["total"]
    offset = (page - 1) * page_size

    rows = query(
        f"""
        SELECT id, site, nick, note, tags, hands_seen, created_at, updated_at
        FROM villain_notes
        {where}
        ORDER BY {order_by}
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


@router.get("/{villain_id}")
def get_villain(villain_id: int, current_user=Depends(require_auth)):
    rows = query("SELECT * FROM villain_notes WHERE id = %s", (villain_id,))
    if not rows:
        raise HTTPException(status_code=404, detail="Vilão não encontrado")
    return dict(rows[0])


@router.post("")
def create_villain(body: VillainCreate, current_user=Depends(require_auth)):
    # UNIQUE (site, nick) — retorna o existente se colidir
    existing = query(
        "SELECT id FROM villain_notes WHERE site IS NOT DISTINCT FROM %s AND nick = %s",
        (body.site, body.nick)
    )
    if existing:
        raise HTTPException(
            status_code=409,
            detail=f"Vilão '{body.nick}' já existe. Usa PATCH /{existing[0]['id']} para actualizar."
        )

    row = execute_returning(
        """
        INSERT INTO villain_notes (site, nick, note, tags, hands_seen)
        VALUES (%(site)s, %(nick)s, %(note)s, %(tags)s, %(hands_seen)s)
        RETURNING id, created_at
        """,
        body.model_dump()
    )
    return {"id": row["id"], "created_at": row["created_at"]}


@router.patch("/{villain_id}")
def update_villain(villain_id: int, body: VillainUpdate, current_user=Depends(require_auth)):
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    if not updates:
        raise HTTPException(status_code=400, detail="Nada para actualizar")

    updates["updated_at"] = "NOW()"
    set_parts = []
    params = {}
    for k, v in updates.items():
        if k == "updated_at":
            set_parts.append("updated_at = NOW()")
        else:
            set_parts.append(f"{k} = %({k})s")
            params[k] = v

    params["villain_id"] = villain_id
    rows = execute(
        f"UPDATE villain_notes SET {', '.join(set_parts)} WHERE id = %(villain_id)s",
        params
    )
    if not rows:
        raise HTTPException(status_code=404, detail="Vilão não encontrado")
    return {"ok": True}


@router.delete("/{villain_id}")
def delete_villain(villain_id: int, current_user=Depends(require_auth)):
    rows = execute("DELETE FROM villain_notes WHERE id = %s", (villain_id,))
    if not rows:
        raise HTTPException(status_code=404, detail="Vilão não encontrado")
    return {"ok": True}


@router.get("/search/hands")
def villain_hands(
    nick: str = Query(..., description="Nick do vilão"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user=Depends(require_auth)
):
    """
    Encontra mãos onde o vilão aparece em all_players_actions.
    Pesquisa pelo nick exacto (case-insensitive) nas chaves do JSONB.
    """
    offset = (page - 1) * page_size

    # Search in all_players_actions keys (player names)
    # Also search in player_names JSONB
    rows = query(
        """
        SELECT h.id, h.hand_id, h.played_at, h.stakes, h.position,
               h.hero_cards, h.board, h.result, h.study_state,
               h.all_players_actions, h.screenshot_url, h.player_names,
               h.entry_id, h.raw, h.site
        FROM hands h
        WHERE (
            h.all_players_actions ? %s
            OR h.player_names::text ILIKE %s
        )
        ORDER BY h.played_at DESC NULLS LAST
        LIMIT %s OFFSET %s
        """,
        (nick, f"%{nick}%", page_size, offset)
    )

    total_rows = query(
        """
        SELECT COUNT(*) AS total FROM hands h
        WHERE (
            h.all_players_actions ? %s
            OR h.player_names::text ILIKE %s
        )
        """,
        (nick, f"%{nick}%")
    )
    total = total_rows[0]["total"] if total_rows else 0

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": (total + page_size - 1) // page_size,
        "data": [dict(r) for r in rows],
    }


@router.post("/recalculate-hands")
def recalculate_hands_seen(current_user=Depends(require_auth)):
    """
    Recalcula hands_seen para todos os vilões.
    Conta mãos de AMBAS as fontes:
    - hand_villains (MTT hands)
    - all_players_actions JSONB nas hands de estudo
    Usa UNION para evitar duplicados entre as duas fontes.
    """
    from app.db import get_conn
    conn = get_conn()
    updated = 0
    try:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE villain_notes vn SET
                    hands_seen = COALESCE(sub.cnt, 0),
                    updated_at = NOW()
                FROM (
                    SELECT nick, COUNT(DISTINCT hand_ref) as cnt
                    FROM (
                        SELECT player_name AS nick, mtt_hand_id::text AS hand_ref
                        FROM hand_villains
                        UNION
                        SELECT key AS nick, h.id::text AS hand_ref
                        FROM hands h, jsonb_object_keys(h.all_players_actions) AS key
                        WHERE h.all_players_actions IS NOT NULL
                          AND key != '_meta'
                    ) combined
                    GROUP BY nick
                ) sub
                WHERE vn.nick = sub.nick
            """)
            updated = cur.rowcount
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()
    return {"ok": True, "updated": updated}
