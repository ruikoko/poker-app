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
