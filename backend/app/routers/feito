from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from app.services.entry_service import list_entries, get_entry, update_entry

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
def entry_detail(entry_id: int):
    entry = get_entry(entry_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Entry não encontrada")
    return entry


@router.patch("/{entry_id}")
def entry_patch(entry_id: int, body: EntryPatchBody):
    entry = get_entry(entry_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Entry não encontrada")

    updated = update_entry(entry_id, status=body.status, notes=body.notes)
    return updated
