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
    """Apaga uma entry (screenshot, HH, etc.) e limpa referências em hands.

    Para mãos com tag 'GGDiscord' (placeholder Discord sem HH), apaga também
    a mão da BD — não faz sentido manter placeholder sem o entry de origem.
    Para outras mãos, apenas remove a referência (entry_id=NULL) e arquiva.

    #ORFA-HM3-SYNTHETIC-ENTRIES Peça 3: entries com source='hm3_synthetic'
    estão protegidas — apagar uma dessas arquivaria a mão HM3 correspondente
    (study_state='mtt_archive'), removendo-a de Estudo. Rejeitado com 400.
    """
    from app.db import get_conn, execute
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            # Peça 3 guard: bloquear DELETE em entries sintéticas HM3.
            cur.execute(
                "SELECT source FROM entries WHERE id = %s",
                (entry_id,)
            )
            existing = cur.fetchone()
            if not existing:
                raise HTTPException(status_code=404, detail="Entry não encontrada")
            if existing["source"] == "hm3_synthetic":
                raise HTTPException(
                    status_code=400,
                    detail=(
                        "Não é possível apagar entries sintéticas HM3 — "
                        "a operação cascateia em UPDATE hands SET entry_id=NULL "
                        "+ study_state='mtt_archive', removendo a mão de Estudo. "
                        "Para gerir mãos HM3 apaga a mão directamente."
                    ),
                )

            # Apagar mãos GGDiscord ligadas a este entry (são placeholder, sem HH)
            cur.execute(
                "DELETE FROM hands WHERE entry_id = %s AND 'GGDiscord' = ANY(hm3_tags)",
                (entry_id,)
            )
            # Limpar referência em outras mãos que apontam para este entry
            cur.execute(
                "UPDATE hands SET entry_id = NULL, study_state = 'mtt_archive' WHERE entry_id = %s",
                (entry_id,)
            )
            # Apagar o entry
            cur.execute("DELETE FROM entries WHERE id = %s", (entry_id,))
            deleted = cur.rowcount
        conn.commit()
    except HTTPException:
        conn.rollback()
        raise
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
    """Apaga múltiplos entries de uma vez.

    #ORFA-HM3-SYNTHETIC-ENTRIES Peça 3: rejeita lote inteiro com 400 se
    contiver pelo menos uma entry com source='hm3_synthetic' (proteccao
    contra cleanup acidental). Caller deve filtrar essas antes de chamar.
    """
    if not body.entry_ids:
        return {"ok": True, "deleted": 0}
    from app.db import get_conn
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            # Peça 3 guard: bloquear lote se contiver entries sintéticas HM3.
            cur.execute(
                "SELECT id FROM entries WHERE id = ANY(%s) AND source = 'hm3_synthetic' LIMIT 5",
                (body.entry_ids,)
            )
            synth_hits = cur.fetchall()
            if synth_hits:
                synth_ids = [r["id"] for r in synth_hits]
                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"Lote contém entries sintéticas HM3 (ex: {synth_ids}). "
                        "Estas estão protegidas — remove-as do lote ou apaga as "
                        "mãos HM3 directamente."
                    ),
                )
            # Limpar referências em hands
            cur.execute(
                "UPDATE hands SET entry_id = NULL, study_state = 'mtt_archive' WHERE entry_id = ANY(%s)",
                (body.entry_ids,)
            )
            # Apagar entries
            cur.execute("DELETE FROM entries WHERE id = ANY(%s)", (body.entry_ids,))
            deleted = cur.rowcount
        conn.commit()
    except HTTPException:
        conn.rollback()
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Erro ao apagar: {e}")
    finally:
        conn.close()
    return {"ok": True, "deleted": deleted}
