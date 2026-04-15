from fastapi import APIRouter, HTTPException, Query, Depends
from pydantic import BaseModel
from app.auth import require_auth
from app.services.entry_service import list_entries, get_entry, update_entry
from app.services.hand_service import process_entry_to_hands

router = APIRouter(prefix="/api/entries", tags=["entries"])


class EntryPatchBody(BaseModel):
    status: str | None = None
    notes: str | None = None


@router.get("")
def entries_list(
    source: str | None = None,
    entry_type: str | None = None,
    status: str | None = None,
    site: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    current_user=Depends(require_auth),
):
    return list_entries(
        source=source,
        entry_type=entry_type,
        status=status,
        site=site,
        page=page,
        page_size=page_size,
    )


@router.get("/{entry_id}")
def entry_detail(entry_id: int, current_user=Depends(require_auth)):
    entry = get_entry(entry_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Entry não encontrada")
    return entry


@router.patch("/{entry_id}")
def entry_patch(entry_id: int, body: EntryPatchBody, current_user=Depends(require_auth)):
    entry = get_entry(entry_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Entry não encontrada")

    updated = update_entry(entry_id, status=body.status, notes=body.notes)
    return updated


@router.post("/{entry_id}/reprocess")
def entry_reprocess(entry_id: int, current_user=Depends(require_auth)):
    """Reprocessa uma entry do tipo hand_history, extraindo mãos para a tabela hands."""
    entry = get_entry(entry_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Entry não encontrada")

    if entry["entry_type"] != "hand_history":
        raise HTTPException(
            status_code=400,
            detail="Só entries do tipo hand_history podem ser reprocessadas"
        )

    result = process_entry_to_hands(entry_id)
    return result


@router.delete("/{entry_id}")
def entry_delete(entry_id: int, current_user=Depends(require_auth)):
    """Apaga uma entry (screenshot, HH, etc.) e limpa referências em hands."""
    from app.db import get_conn, execute
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            # Limpar referência em hands que apontam para este entry
            cur.execute("UPDATE hands SET entry_id = NULL, study_state = 'mtt_archive' WHERE entry_id = %s", (entry_id,))
            # Apagar o entry
            cur.execute("DELETE FROM entries WHERE id = %s", (entry_id,))
            deleted = cur.rowcount
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Erro ao apagar: {e}")
    finally:
        conn.close()
    if deleted == 0:
        raise HTTPException(status_code=404, detail="Entry não encontrada")
    return {"ok": True, "deleted": deleted}


class BulkDeleteBody(BaseModel):
    entry_ids: list[int]


@router.post("/bulk-delete")
def entries_bulk_delete(body: BulkDeleteBody, current_user=Depends(require_auth)):
    """Apaga múltiplos entries de uma vez."""
    if not body.entry_ids:
        return {"ok": True, "deleted": 0}
    from app.db import get_conn
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            # Limpar referências em hands
            cur.execute(
                "UPDATE hands SET entry_id = NULL, study_state = 'mtt_archive' WHERE entry_id = ANY(%s)",
                (body.entry_ids,)
            )
            # Apagar entries
            cur.execute("DELETE FROM entries WHERE id = ANY(%s)", (body.entry_ids,))
            deleted = cur.rowcount
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Erro ao apagar: {e}")
    finally:
        conn.close()
    return {"ok": True, "deleted": deleted}
