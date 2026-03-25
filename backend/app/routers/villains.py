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

    total = query(f"SELECT COUNT(*) AS total FROM villain_notes {where}", params)[0]["total"]
    offset = (page - 1) * page_size

    rows = query(
        f"""
        SELECT id, site, nick, note, tags, hands_seen, created_at, updated_at
        FROM villain_notes
        {where}
        ORDER BY updated_at DESC
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
