import zipfile
import io
import re
import json
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
from app.routers.hm3 import _parse_hand as hm3_parse_hand
from app.ingest_filters import is_pre_2026

logger = logging.getLogger("import")

router = APIRouter(prefix="/api/import", tags=["import"])

# Parsers de summaries/torneios (P&L)
SUMMARY_PARSERS = {
    "winamax": winamax.parse_file,
    "ggpoker": ggpoker.parse_file,
}

# ── HH multi-site splitter ────────────────────────────────────────────────────

# Patterns that mark the start of a new hand in each site's HH format
_HAND_START_PATTERNS = [
    re.compile(r"^Winamax Poker - ", re.MULTILINE),
    re.compile(r"^PokerStars Hand #", re.MULTILINE),
    re.compile(r"^PokerStars Tournament #", re.MULTILINE),
    re.compile(r"^Americas Cardroom Hand", re.MULTILINE),
    re.compile(r"^Black Chip Poker Hand", re.MULTILINE),
    re.compile(r"^Poker Hand #", re.MULTILINE),
]

def _detect_site_from_block(block: str) -> str:
    """Detect which site a HH block belongs to."""
    if block.startswith("Winamax Poker"):
        return "Winamax"
    if block.startswith("PokerStars"):
        return "PokerStars"
    if block.startswith("Americas Cardroom") or block.startswith("Black Chip"):
        return "WPN"
    if block.startswith("Poker Hand #"):
        return "GGPoker"
    return "Unknown"

def _split_hh_blocks(text: str) -> list[str]:
    """Split a multi-hand HH file into individual hand blocks."""
    # Find all start positions
    starts = []
    for pat in _HAND_START_PATTERNS:
        for m in pat.finditer(text):
            starts.append(m.start())
    starts = sorted(set(starts))

    if not starts:
        return [text.strip()] if text.strip() else []

    blocks = []
    for i, start in enumerate(starts):
        end = starts[i + 1] if i + 1 < len(starts) else len(text)
        block = text[start:end].strip()
        if block:
            blocks.append(block)
    return blocks

def _parse_hh_file(content: bytes, filename: str) -> tuple[list[dict], list[str]]:
    """Parse a .txt HH file that may contain hands from multiple sites.
    Returns (parsed_hands, errors)."""
    text = content.decode("utf-8", errors="replace")
    # Normalise line endings
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    blocks = _split_hh_blocks(text)
    parsed = []
    errors = []

    for i, block in enumerate(blocks):
        site = _detect_site_from_block(block)
        try:
            if site == "GGPoker":
                # Use GG parser for GG hands
                hands_list, errs = parse_hands(block.encode("utf-8"), filename)
                parsed.extend(hands_list)
                errors.extend(errs)
            else:
                # Use hm3 parser for Winamax/PS/WPN
                result = hm3_parse_hand(block, site)
                if result:
                    # Build all_players_actions JSON for insertion
                    all_players = result.pop("all_players", {})
                    meta = {
                        "bb": result.get("bb_size", 0),
                        "sb": result.get("sb_size", 0),
                        "ante": result.get("ante_size", 0),
                        "level": result.get("level"),
                    }
                    all_players["_meta"] = meta
                    result["all_players_actions"] = all_players
                    parsed.append(result)
                else:
                    errors.append(f"Block {i+1}: parser returned None for {site}")
        except Exception as e:
            errors.append(f"Block {i+1} ({site}): {e}")

    return parsed, errors


def _detect_site(filename: str, content: bytes) -> str | None:
    fn = filename.lower()
    if "winamax" in fn:
        return "winamax"
    if "ggpoker" in fn or fn.startswith("gg"):
        return "ggpoker"
    if "pokerstars" in fn or fn.startswith("ps"):
        return "pokerstars"
    if "wpn" in fn or "americas" in fn or "blackchip" in fn:
        return "wpn"

    sample = content[:2000].decode("utf-8", errors="replace").lower()
    if "winamax" in sample:
        return "winamax"
    if "ggpoker" in sample or "gg poker" in sample:
        return "ggpoker"
    if "pokerstars" in sample:
        return "pokerstars"
    if "americas cardroom" in sample or "black chip" in sample:
        return "wpn"

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
        total_inserted = 0
        total_skipped = 0
        total_rejected_pre_2026 = 0
        all_errors = []

        if is_zip:
            try:
                with zipfile.ZipFile(io.BytesIO(content)) as zf:
                    for name in zf.namelist():
                        if not name.lower().endswith(".txt"):
                            continue
                        file_content = zf.read(name)
                        hands_parsed, errors = _parse_hh_file(file_content, name)
                        all_errors.extend(errors)
                        conn = get_conn()
                        try:
                            for h in hands_parsed:
                                if is_pre_2026(h.get("played_at")):
                                    total_rejected_pre_2026 += 1
                                    logger.warning(f"[import] Rejeitada hand_id={h.get('hand_id')} played_at={h.get('played_at')} (<2026)")
                                    continue
                                ok = _insert_hand(conn, h, entry_id, study_state='new', origin='hh_import')
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
        else:
            # Single .txt file
            hands_parsed, errors = _parse_hh_file(content, filename)
            all_errors.extend(errors)
            conn = get_conn()
            try:
                for h in hands_parsed:
                    if is_pre_2026(h.get("played_at")):
                        total_rejected_pre_2026 += 1
                        logger.warning(f"[import] Rejeitada hand_id={h.get('hand_id')} played_at={h.get('played_at')} (<2026)")
                        continue
                    ok = _insert_hand(conn, h, entry_id, study_state='new', origin='hh_import')
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

        # ── Auto-rematch de screenshots órfãos ──
        rematched = []
        migrated_to_study = 0
        try:
            # Inclui Discord replayer_link/image — cobre o caso em que um
            # placeholder Discord foi substituído por HH real neste import.
            # Sem isto, as mãos ficam com match_method='discord_placeholder_no_hh'
            # (stale) e falham na regra B/C de villains.
            #
            # status='resolved' também apanhado: _create_placeholder_if_needed
            # (fix f70ae05) marca entries resolved imediatamente ao criar
            # placeholder. Quando _insert_hand substitui o placeholder por HH
            # real, all_players_actions fica com hashes do HH GG anonimizado —
            # _enrich_hand_from_orphan_entry substitui pelos nicks Vision.
            # Guard-rail: só re-corre se a hand existe e tem raw real (já foi
            # substituída), e o match_method indica dados Vision disponíveis.
            # _enrich é idempotente — repeat no-op para hands já enriched.
            orphan_rows = query(
                """SELECT e.id, e.raw_json FROM entries e
                   WHERE (
                     e.status = 'new'
                     OR (
                       e.status = 'resolved'
                       AND EXISTS (
                         SELECT 1 FROM hands h
                         WHERE h.entry_id = e.id
                           AND (h.player_names->>'match_method') IS NOT NULL
                           AND h.raw IS NOT NULL AND h.raw <> ''
                       )
                     )
                   )
                   AND (
                     e.entry_type = 'screenshot'
                     OR (e.source = 'discord' AND e.entry_type IN ('replayer_link','image'))
                   )
                   AND e.raw_json ? 'tm'"""
            )
            for orphan in orphan_rows:
                raw = orphan.get("raw_json") or {}
                tm = raw.get("tm")
                if not tm:
                    continue
                tm_digits = tm.replace("TM", "")
                hand_rows = query(
                    "SELECT id, (player_names->>'match_method') AS mm "
                    "FROM hands WHERE hand_id = %s LIMIT 1",
                    (f"GG-{tm_digits}",)
                )
                if hand_rows:
                    prev_mm = hand_rows[0].get("mm")
                    was_anon = prev_mm is None or (
                        isinstance(prev_mm, str) and prev_mm.startswith("discord_placeholder_")
                    )
                    enrich_result = _enrich_hand_from_orphan_entry(
                        orphan["id"], hand_rows[0]["id"], raw
                    )
                    if was_anon and enrich_result.get("status") == "ok":
                        migrated_to_study += 1
                    rematched.append({
                        "entry_id": orphan["id"],
                        "tm": tm,
                        "hand_id": hand_rows[0]["id"],
                        "players_mapped": enrich_result.get("players_mapped", 0),
                        "enrich_status": enrich_result.get("status"),
                    })
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
            "hands_rejected_pre_2026": total_rejected_pre_2026,
            "errors": len(all_errors),
            "error_log": all_errors[:20],
            "rematched_screenshots": len(rematched),
            "rematched": rematched,
            "migrated_to_study": migrated_to_study,
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
