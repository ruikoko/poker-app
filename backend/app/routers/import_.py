import zipfile
import io
import logging
from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from app.auth import require_auth
from app.db import get_conn, query
from app.parsers import winamax, ggpoker
from app.parsers.gg_hands import parse_hands
from app.services.entry_classifier import classify_entry
from app.services.entry_service import create_entry
from app.services.hand_service import process_entry_to_hands, _insert_hand
from app.routers.screenshot import _enrich_hand_from_orphan_entry

logger = logging.getLogger("import")

router = APIRouter(prefix="/api/import", tags=["import"])

# Parsers de summaries/torneios (P&L)
SUMMARY_PARSERS = {
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


def _detect_zip_content_type(content: bytes) -> str:
    """Abre o ZIP e le o primeiro ficheiro .txt para determinar o tipo de conteudo."""
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as zf:
            for name in zf.namelist():
                if not name.lower().endswith(".txt"):
                    continue
                text = zf.read(name).decode("utf-8", errors="replace").strip()
                if not text:
                    continue
                first_lines = "\n".join(text.splitlines()[:10]).lower()
                if "buy-in" in first_lines and "tournament" in first_lines:
                    return "tournament_summary"
                if text.startswith("Poker Hand #") and "hole cards" in text.lower():
                    return "hand_history"
                if text.startswith("Tournament #") and "you finished" in text.lower():
                    return "tournament_summary"
                if "poker hand #" in first_lines:
                    return "hand_history"
                if "buy-in" in first_lines:
                    return "tournament_summary"
    except Exception:
        pass
    return "unknown"


def _detect_site_from_zip(content: bytes) -> str | None:
    """Tenta detectar a sala a partir dos nomes dos ficheiros dentro do ZIP."""
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as zf:
            for name in zf.namelist():
                fn = name.lower()
                if fn.startswith("gg") or "ggpoker" in fn:
                    return "ggpoker"
                if "winamax" in fn:
                    return "winamax"
                if "pokerstars" in fn:
                    return "pokerstars"
    except Exception:
        pass
    return None


def _run_tournament_import(conn, records: list[dict], import_id: int) -> tuple[int, int]:
    """Insere torneios na transaccao aberta."""
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
                {**r, "import_id": import_id},
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
        (detected_site, filename, records_found),
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
        (
            status,
            inserted,
            skipped,
            len(parse_errors),
            "\n".join(parse_errors) if parse_errors else "",
            import_id,
        ),
    )


@router.post("")
async def import_file(
    file: UploadFile = File(...),
    site: str | None = None,
    current_user=Depends(require_auth),
):
    content = await file.read()
    filename = file.filename or "upload"
    is_zip = filename.lower().endswith(".zip")

    # ── Detectar sala ──
    detected_site = site or _detect_site(filename, content)
    if not detected_site and is_zip:
        detected_site = _detect_site_from_zip(content)

    # ── Classificar o conteudo ──
    if is_zip:
        content_type = _detect_zip_content_type(content)
    else:
        content_text = content.decode("utf-8", errors="ignore")
        classification = classify_entry(filename, content_text)
        content_type = classification["entry_type"]

    # ── Criar entry para rastreabilidade ──
    raw_text = None if is_zip else content.decode("utf-8", errors="ignore")
    entry_source = "hh_text" if content_type == "hand_history" else "summary"
    entry_site_label = None
    if detected_site == "ggpoker":
        entry_site_label = "GGPoker"
    elif detected_site == "winamax":
        entry_site_label = "Winamax"

    entry = create_entry(
        source=entry_source,
        entry_type=content_type if content_type != "unknown" else "text",
        site=entry_site_label,
        file_name=filename,
        external_id=None,
        raw_text=raw_text,
        raw_json=None,
        status="new",
        notes=f"ZIP com {content_type}" if is_zip else None,
        import_log_id=None,
    )
    entry_id = entry["id"]

    # ── HAND HISTORY → vai para hands ──
    if content_type == "hand_history":
        if is_zip:
            total_inserted = 0
            total_skipped = 0
            all_errors = []
            try:
                with zipfile.ZipFile(io.BytesIO(content)) as zf:
                    for name in zf.namelist():
                        if not name.lower().endswith(".txt"):
                            continue
                        file_content = zf.read(name)
                        hands_parsed, errors = parse_hands(file_content, name)
                        all_errors.extend(errors)
                        conn = get_conn()
                        try:
                            for h in hands_parsed:
                                ok = _insert_hand(conn, h, entry_id)
                                if ok:
                                    total_inserted += 1
                                else:
                                    total_skipped += 1
                            conn.commit()
                        except Exception:
                            conn.rollback()
                            raise
                        finally:
                            conn.close()
            except Exception as e:
                all_errors.append(str(e))

            # ── Auto-rematch de screenshots órfãos ──
            rematched = []
            try:
                orphan_rows = query(
                    "SELECT id, raw_json FROM entries WHERE entry_type = 'screenshot' AND status = 'new'"
                )
                for orphan in orphan_rows:
                    raw = orphan.get("raw_json") or {}
                    tm = raw.get("tm")
                    if not tm:
                        continue
                    tm_digits = tm.replace("TM", "")
                    hand_rows = query(
                        "SELECT id FROM hands WHERE hand_id = %s LIMIT 1",
                        (f"GG-{tm_digits}",)
                    )
                    if hand_rows:
                        enrich_result = _enrich_hand_from_orphan_entry(
                            orphan["id"], hand_rows[0]["id"], raw
                        )
                        rematched.append({
                            "entry_id": orphan["id"],
                            "tm": tm,
                            "hand_id": hand_rows[0]["id"],
                            "players_mapped": enrich_result.get("players_mapped", 0),
                            "enrich_status": enrich_result.get("status"),
                        })
                        logger.info(f"Auto-rematch: entry {orphan['id']} enriched for GG-{tm_digits}, {enrich_result.get('players_mapped', 0)} players mapped")
            except Exception as e:
                logger.error(f"Auto-rematch query error: {e}")

            return {
                "import_type": "hands",
                "entry_id": entry_id,
                "site": entry_site_label or detected_site,
                "filename": filename,
                "status": "ok" if total_inserted > 0 else "error",
                "hands_found": total_inserted + total_skipped,
                "hands_inserted": total_inserted,
                "hands_skipped": total_skipped,
                "errors": len(all_errors),
                "error_log": all_errors[:20],
                "rematched_screenshots": len(rematched),
                "rematched": rematched,
            }
        else:
            result = process_entry_to_hands(entry_id)
            return {
                "import_type": "hands",
                "entry_id": entry_id,
                "site": entry_site_label or detected_site,
                "filename": filename,
                "status": "ok" if result["inserted"] > 0 else "error",
                "hands_found": result["inserted"] + result["skipped"],
                "hands_inserted": result["inserted"],
                "hands_skipped": result["skipped"],
                "errors": len(result["errors"]),
                "error_log": result["errors"][:20],
            }

    # ── TOURNAMENT SUMMARY / REPORT → vai para tournaments (P&L) ──
    if not detected_site or detected_site not in SUMMARY_PARSERS:
        raise HTTPException(
            status_code=400,
            detail=f"Sala nao reconhecida ({detected_site}). Usa ?site=winamax ou ?site=ggpoker",
        )

    records, parse_errors = SUMMARY_PARSERS[detected_site](content, filename)
    records_found = len(records)

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            import_id = _create_log(cur, detected_site, filename, records_found)

        inserted, skipped = _run_tournament_import(conn, records, import_id)

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
        "import_type": "tournaments",
        "import_id": import_id,
        "entry_id": entry_id,
        "site": detected_site,
        "filename": filename,
        "status": status,
        "records_found": records_found,
        "inserted": inserted,
        "skipped": skipped,
        "errors": len(parse_errors),
        "error_log": parse_errors[:20],
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
