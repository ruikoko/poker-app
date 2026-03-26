"""
Endpoint para upload de screenshots do replayer GG.
Fluxo:
  1. Recebe imagem (PNG/JPG)
  2. Usa Vision (GPT-4o-mini) para extrair o TM number do header
  3. Faz match com a mão na BD pelo hand_id (GG-{TM_number})
  4. Guarda screenshot_url e player_names na mão
  5. Devolve resultado do match
"""
import os
import base64
import re
import logging
from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from app.auth import require_auth
from app.db import get_conn, query

router = APIRouter(prefix="/api/screenshots", tags=["screenshots"])
logger = logging.getLogger("screenshots")


def _extract_tm_from_image(image_bytes: bytes, mime_type: str = "image/png") -> str | None:
    """Usa Vision para extrair o TM number do header do replayer GG."""
    try:
        from openai import OpenAI
        client = OpenAI()

        b64 = base64.b64encode(image_bytes).decode("utf-8")
        data_url = f"data:{mime_type};base64,{b64}"

        response = client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {"url": data_url, "detail": "low"},
                        },
                        {
                            "type": "text",
                            "text": (
                                "This is a GGPoker hand replayer screenshot. "
                                "In the header/title area there is a Tournament ID that starts with 'TM' followed by digits "
                                "(e.g. TM5750885374). "
                                "Also look for player names in the table (real nicknames, not hashes). "
                                "Reply in this exact format:\n"
                                "TM: <TM_number_or_NONE>\n"
                                "PLAYERS: <comma-separated list of player names visible>\n"
                                "HERO: <hero player name if identifiable>\n"
                                "Only output these 3 lines, nothing else."
                            ),
                        },
                    ],
                }
            ],
            max_tokens=150,
        )

        text = response.choices[0].message.content.strip()
        logger.info(f"Vision response: {text}")
        return text

    except Exception as e:
        logger.error(f"Vision error: {e}")
        return None


def _parse_vision_response(text: str) -> dict:
    """Parse the structured Vision response."""
    result = {"tm": None, "players": [], "hero": None}
    if not text:
        return result

    for line in text.splitlines():
        line = line.strip()
        if line.startswith("TM:"):
            val = line[3:].strip()
            if val and val.upper() != "NONE":
                # Extract just the TM number
                m = re.search(r'TM\d+', val)
                if m:
                    result["tm"] = m.group(0)
        elif line.startswith("PLAYERS:"):
            val = line[8:].strip()
            if val and val.upper() != "NONE":
                result["players"] = [p.strip() for p in val.split(",") if p.strip()]
        elif line.startswith("HERO:"):
            val = line[5:].strip()
            if val and val.upper() not in ("NONE", "UNKNOWN"):
                result["hero"] = val

    return result


def _upload_screenshot_to_storage(image_bytes: bytes, filename: str) -> str | None:
    """
    Guarda o screenshot e devolve uma URL acessível.
    Por agora guarda em /tmp/screenshots/ e devolve um path relativo.
    Em produção, fazer upload para S3/Railway storage.
    """
    import hashlib
    import os

    # Create storage dir
    storage_dir = "/tmp/poker_screenshots"
    os.makedirs(storage_dir, exist_ok=True)

    # Hash-based filename to avoid duplicates
    h = hashlib.md5(image_bytes).hexdigest()[:12]
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "png"
    stored_name = f"{h}.{ext}"
    stored_path = os.path.join(storage_dir, stored_name)

    with open(stored_path, "wb") as f:
        f.write(image_bytes)

    # Return a relative URL (served via /screenshots/ static route)
    return f"/screenshots/{stored_name}"


@router.post("")
async def upload_screenshot(
    file: UploadFile = File(...),
    current_user=Depends(require_auth),
):
    """
    Upload de screenshot do replayer GG.
    Extrai TM number via Vision, faz match com HH na BD.
    """
    content = await file.read()
    filename = file.filename or "screenshot.png"
    mime_type = file.content_type or "image/png"

    if not mime_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Ficheiro deve ser uma imagem (PNG/JPG)")

    # 1. Extrair TM e nomes via Vision
    vision_text = _extract_tm_from_image(content, mime_type)
    parsed = _parse_vision_response(vision_text)

    tm_number = parsed.get("tm")
    players = parsed.get("players", [])
    hero_name = parsed.get("hero")

    # 2. Guardar screenshot
    screenshot_url = _upload_screenshot_to_storage(content, filename)

    # 3. Tentar match com HH na BD
    matched_hand = None
    if tm_number:
        hand_id_pattern = f"GG-{tm_number}-%"
        rows = query(
            "SELECT id, hand_id, position, hero_cards, board FROM hands WHERE hand_id LIKE %s ORDER BY played_at DESC LIMIT 1",
            (hand_id_pattern,)
        )
        if rows:
            matched_hand = dict(rows[0])

    # 4. Se fez match, actualizar a mão com screenshot_url e player_names
    if matched_hand:
        player_names_json = {
            "players": players,
            "hero": hero_name,
            "raw_vision": vision_text,
        }
        conn = get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE hands
                    SET screenshot_url = %s,
                        player_names = %s
                    WHERE id = %s
                    """,
                    (screenshot_url, player_names_json, matched_hand["id"])
                )
            conn.commit()
        except Exception as e:
            conn.rollback()
            logger.error(f"Error updating hand: {e}")
        finally:
            conn.close()

        return {
            "status": "matched",
            "tm_number": tm_number,
            "hand_id": matched_hand["id"],
            "hand_hand_id": matched_hand["hand_id"],
            "screenshot_url": screenshot_url,
            "players_found": len(players),
            "players": players,
            "hero": hero_name,
        }

    # 5. Sem match — guardar como screenshot órfão para revisão manual
    # Criar uma entry para rastreabilidade
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO entries (source, entry_type, site, file_name, status, notes, raw_json)
                VALUES ('screenshot', 'screenshot', 'GGPoker', %s, 'new', %s, %s)
                RETURNING id
                """,
                (
                    filename,
                    f"Screenshot órfão — TM: {tm_number or 'não detectado'}",
                    {"tm": tm_number, "players": players, "hero": hero_name, "screenshot_url": screenshot_url},
                )
            )
            entry_id = cur.fetchone()["id"]
        conn.commit()
    except Exception as e:
        conn.rollback()
        logger.error(f"Error creating orphan entry: {e}")
        entry_id = None
    finally:
        conn.close()

    return {
        "status": "no_match",
        "tm_number": tm_number,
        "screenshot_url": screenshot_url,
        "players_found": len(players),
        "players": players,
        "hero": hero_name,
        "message": "Screenshot guardado mas sem match com HH. Importa a HH deste torneio primeiro.",
        "entry_id": entry_id,
    }


@router.get("/hand/{hand_id}")
def get_hand_screenshot(hand_id: int, current_user=Depends(require_auth)):
    """Devolve o screenshot_url e player_names de uma mão."""
    rows = query(
        "SELECT id, screenshot_url, player_names FROM hands WHERE id = %s",
        (hand_id,)
    )
    if not rows:
        raise HTTPException(status_code=404, detail="Mão não encontrada")
    return dict(rows[0])
