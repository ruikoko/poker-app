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


def _build_conditions(
    site, tag, study_state, position, search, date_from,
    exclude_mtt_only: bool = False,
    result_min: float = None,
    result_max: float = None,
):
    """Constrói lista de condições SQL e parâmetros para filtros de mãos."""
    conditions = []
    params = []

    if site:
        conditions.append("h.site = %s")
        params.append(site)

    if tag:
        if tag == '__none__':
            conditions.append("(h.tags IS NULL OR h.tags = '{}')")
        else:
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

    if result_min is not None:
        conditions.append("h.result >= %s")
        params.append(result_min)

    if result_max is not None:
        conditions.append("h.result <= %s")
        params.append(result_max)

    if exclude_mtt_only:
        conditions.append(
            "(h.tags IS NULL OR h.tags = '{}' OR NOT (h.tags = ARRAY['mtt']::text[]))"
        )

    return conditions, params


@router.get("")
def list_hands(
    site:             Optional[str] = Query(None),
    tag:              Optional[str] = Query(None, description="Filtrar por tag"),
    study_state:      Optional[str] = Query(None, description="Filtrar por estado de estudo"),
    position:         Optional[str] = Query(None, description="Filtrar por posição"),
    search:           Optional[str] = Query(None, description="Pesquisa livre em notas/raw"),
    date_from:        Optional[str] = Query(None, description="Filtrar por data (ISO date, ex: 2026-03-20)"),
    result_min:       Optional[float] = Query(None, description="Resultado mínimo em BB"),
    result_max:       Optional[float] = Query(None, description="Resultado máximo em BB"),
    exclude_mtt_only: bool = Query(False, description="Excluir mãos que só têm tag #mtt"),
    include_archive:  bool = Query(False, description="Incluir mãos de arquivo MTT (mtt_archive)"),
    page:             int = Query(1, ge=1),
    page_size:        int = Query(50, ge=1, le=500),
    current_user=Depends(require_auth)
):
    conditions, params = _build_conditions(
        site, tag, study_state, position, search, date_from, exclude_mtt_only,
        result_min, result_max
    )
    # Excluir arquivo MTT por defeito (a não ser que pedido explicitamente ou filtrado por study_state)
    if not include_archive and study_state != 'mtt_archive':
        conditions.append("h.study_state != 'mtt_archive'")
    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""

    total = query(
        f"""SELECT COUNT(*) AS total FROM hands h
            LEFT JOIN entries e ON h.entry_id = e.id
            LEFT JOIN discord_sync_state d ON e.discord_channel = d.channel_id
            {where}""",
        params
    )[0]["total"]
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


@router.get("/tag-groups")
def tag_groups(
    site:             Optional[str] = Query(None),
    study_state:      Optional[str] = Query(None),
    position:         Optional[str] = Query(None),
    search:           Optional[str] = Query(None),
    date_from:        Optional[str] = Query(None),
    exclude_mtt_only: bool = Query(False, description="Excluir mãos que só têm tag #mtt"),
    include_archive:  bool = Query(False, description="Incluir mãos de arquivo MTT"),
    current_user=Depends(require_auth)
):
    """Devolve grupos de tags com contagens, wins/losses e resultado total em BB."""
    conditions, params = _build_conditions(
        site, None, study_state, position, search, date_from, exclude_mtt_only
    )
    # Excluir arquivo MTT por defeito
    if not include_archive and study_state != 'mtt_archive':
        conditions.append("h.study_state != 'mtt_archive'")
    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""

    # Fetch all matching hands (only id, tags, result) — no pagination
    rows = query(
        f"SELECT h.id, h.tags, h.result, h.study_state FROM hands h {where} ORDER BY h.played_at DESC NULLS LAST",
        params
    )

    # Group by sorted tag combination
    groups = {}  # tagKey -> {tags, count, wins, losses, total_bb}
    no_tag = {"tags": [], "count": 0, "wins": 0, "losses": 0, "total_bb": 0.0}

    for r in rows:
        tags = r["tags"] or []
        result = float(r["result"] or 0.0)
        win = 1 if result > 0 else 0
        loss = 1 if result < 0 else 0

        if not tags:
            no_tag["count"] += 1
            no_tag["wins"] += win
            no_tag["losses"] += loss
            no_tag["total_bb"] += result
        else:
            key = "+".join(sorted(tags))
            if key not in groups:
                groups[key] = {"tags": sorted(tags), "count": 0, "wins": 0, "losses": 0, "total_bb": 0.0}
            groups[key]["count"] += 1
            groups[key]["wins"] += win
            groups[key]["losses"] += loss
            groups[key]["total_bb"] += result

    # Sort by count desc
    sorted_groups = sorted(groups.values(), key=lambda g: g["count"], reverse=True)
    if no_tag["count"] > 0:
        sorted_groups.append(no_tag)

    return {"groups": sorted_groups, "total": len(rows)}


@router.get("/stats")
def hand_stats(current_user=Depends(require_auth)):
    """Estatísticas globais das mãos (exclui arquivo MTT)."""
    rows = query("""
        SELECT
            COUNT(*) FILTER (WHERE study_state != 'mtt_archive') AS total,
            COUNT(*) FILTER (WHERE study_state = 'new') AS new,
            COUNT(*) FILTER (WHERE study_state = 'review') AS review,
            COUNT(*) FILTER (WHERE study_state = 'studying') AS studying,
            COUNT(*) FILTER (WHERE study_state = 'resolved') AS resolved,
            COUNT(*) FILTER (WHERE study_state = 'mtt_archive') AS mtt_archive,
            COUNT(DISTINCT site) FILTER (WHERE study_state != 'mtt_archive') AS sites,
            COUNT(DISTINCT position) FILTER (WHERE position IS NOT NULL AND study_state != 'mtt_archive') AS positions
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


@router.get("/{hand_pk}/screenshot")
def get_hand_screenshot(hand_pk: int, current_user=Depends(require_auth)):
    """Devolve a imagem do screenshot associado a uma mão (como data URL)."""
    rows = query(
        "SELECT entry_id, player_names FROM hands WHERE id = %s",
        (hand_pk,)
    )
    if not rows:
        raise HTTPException(status_code=404, detail="Mão não encontrada")

    hand = dict(rows[0])
    entry_id = hand.get("entry_id")
    player_names = hand.get("player_names") or {}

    # Fallback: entry_id pode estar no player_names
    if not entry_id:
        entry_id = player_names.get("screenshot_entry_id")

    if not entry_id:
        raise HTTPException(status_code=404, detail="Sem screenshot associado")

    entry_rows = query(
        "SELECT raw_json FROM entries WHERE id = %s",
        (entry_id,)
    )
    if not entry_rows:
        raise HTTPException(status_code=404, detail="Entry do screenshot não encontrado")

    raw = entry_rows[0].get("raw_json") or {}
    img_b64 = raw.get("img_b64", "")
    mime_type = raw.get("mime_type", "image/png")

    if not img_b64:
        raise HTTPException(status_code=404, detail="Imagem não disponível")

    return {
        "data_url": f"data:{mime_type};base64,{img_b64}",
        "entry_id": entry_id,
    }
