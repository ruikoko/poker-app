from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from app.auth import require_auth
from app.db import get_conn, query
from app.parsers import winamax, ggpoker
from app.services.entry_classifier import classify_entry
from app.services.entry_service import create_entry

router = APIRouter(prefix="/api/import", tags=["import"])

SITE_PARSERS = {
    "winamax": winamax.parse_file,
    "ggpoker": ggpoker.parse_file,
}

def _detect_site(filename: str, content: bytes) -> str | None:
    fn = filename.lower()
    if "winamax" in fn:
        return "winamax"
    if "ggpoker" in fn or fn.startswith("gg"):
        return "ggpoker"
    sample = content[:2000].decode("utf-8", errors="replace").lower()
    if "winamax" in sample:
        return "winamax"
    if "ggpoker" in sample or "gg poker" in sample:
        return "ggpoker"
    return None


def _run_import(conn, records: list[dict], import_id: int) -> tuple[int, int]:
    """Insere torneios na transaccao aberta. Lanca excepcao se falhar."""
    inserted = 0
    skipped = 0
    with conn.cursor() as cur:
        for r in records:
            cur.execute(
                """
                INSERT INTO tournaments
                    (site, tid, name, date, buyin, cashout, position, players,
                     type, speed, currency, import_id)
                VALUES
                    (%(site)s, %(tid)s, %(name)s, %(date)s, %(buyin)s, %(cashout)s,
                     %(position)s, %(players)s, %(type)s, %(speed)s, %(currency)s, %(import_id)s)
                ON CONFLICT DO NOTHING
                """,
                {**r, "import_id": import_id}
            )
            if cur.rowcount:
                inserted += 1
            else:
                skipped += 1
    return inserted, skipped


def _create_log(cur, detected_site, filename, records_found):
    cur.execute(
        """
        INSERT INTO import_logs
            (site, filename, status, records_found,
             records_ok, records_skipped, records_error, log)
        VALUES (%s, %s, 'partial', %s, 0, 0, 0, '')
        RETURNING id
        """,
        (detected_site, filename, records_found)
    )
    return cur.fetchone()["id"]


def _update_log(cur, import_id, status, inserted, skipped, parse_errors):
    cur.execute(
        """
        UPDATE import_logs
        SET status=%s, records_ok=%s, records_skipped=%s,
            records_error=%s, log=%s
        WHERE id=%s
        """,
        (status, inserted, skipped, len(parse_errors),
         "\n".join(parse_errors) if parse_errors else "", import_id)
    )


@router.post("")
async def import_file(
    file: UploadFile = File(...),
    site: str | None = None,
    current_user=Depends(require_auth)
):
    content = await file.read()
filename = file.filename or "upload"

content_text = content.decode("utf-8", errors="ignore")

classification = classify_entry(filename, content_text)

entry = create_entry(
    source=classification["source"],
    entry_type=classification["entry_type"],
    site=classification.get("site"),
    file_name=filename,
    external_id=classification.get("external_id"),
    raw_text=content_text,
    raw_json=None,
    status="new",
    notes=None,
    import_log_id=None,
)

entry_id = entry["id"]

detected_site = site or _detect_site(filename, content)

if not detected_site or detected_site not in SITE_PARSERS:
    raise HTTPException(
        status_code=400,
        detail="Sala nao reconhecida. Usa ?site=winamax ou ?site=ggpoker"
    )

records, parse_errors = SITE_PARSERS[detected_site](content, filename)
records_found = len(records)

conn = get_conn()
try:
    with conn.cursor() as cur:
        import_id = _create_log(cur, detected_site, filename, records_found)

    inserted, skipped = _run_import(conn, records, import_id)

    status = "ok" if not parse_errors else ("partial" if inserted > 0 else "error")

    with conn.cursor() as cur:
        _update_log(cur, import_id, status, inserted, skipped, parse_errors)

    conn.commit()

except Exception as exc:
    conn.rollback()
    raise HTTPException(status_code=500, detail=f"Rollback efectuado: {exc}")

finally:
    conn.close()

return {
    "import_id":     import_id,
    "site":          detected_site,
    "filename":      filename,
    "status":        status,
    "records_found": records_found,
    "inserted":      inserted,
    "skipped":       skipped,
    "errors":        len(parse_errors),
    "error_log":     parse_errors[:20],
}


@router.get("/logs")
def import_logs(current_user=Depends(require_auth)):
    rows = query(
        """
        SELECT id, site, filename, status,
               records_found, records_ok, records_skipped, records_error,
               imported_at
        FROM import_logs
        ORDER BY imported_at DESC
        LIMIT 50
        """
    )
return list(rows)
