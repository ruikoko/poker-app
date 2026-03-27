"""
Endpoint para upload de screenshots do replayer GG.

Pipeline completo:
  1. Recebe imagem (PNG/JPG)
  2. Extrai data, hora, blinds e TM number do nome do ficheiro (fonte primária)
  3. Usa Vision (GPT-4.1-mini) para extrair jogadores por posição, stacks e bounties
  4. Faz match com a mão na BD pelo hand_id (GG-{TM_number})
  5. Constrói mapa anon_id → nome_real por correspondência de posição
  6. Actualiza all_players_actions, screenshot_url e player_names na mão
  7. Devolve resultado do match
"""
import os
import re
import base64
import json
import logging
import asyncio
import io
from datetime import datetime
from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, BackgroundTasks
from PIL import Image
from app.auth import require_auth
from app.db import get_conn, query

router = APIRouter(prefix="/api/screenshots", tags=["screenshots"])
logger = logging.getLogger("screenshots")


# ── Posições por número de jogadores ────────────────────────────────────────

POSITION_MAPS = {
    2:  ["SB", "BB"],
    3:  ["BTN", "SB", "BB"],
    4:  ["CO", "BTN", "SB", "BB"],
    5:  ["UTG", "CO", "BTN", "SB", "BB"],
    6:  ["UTG", "MP", "CO", "BTN", "SB", "BB"],
    7:  ["UTG", "UTG+1", "MP", "CO", "BTN", "SB", "BB"],
    8:  ["UTG", "UTG+1", "MP", "MP+1", "CO", "BTN", "SB", "BB"],
    9:  ["UTG", "UTG+1", "MP", "MP+1", "HJ", "CO", "BTN", "SB", "BB"],
    10: ["UTG", "UTG+1", "UTG+2", "MP", "MP+1", "HJ", "CO", "BTN", "SB", "BB"],
}


def _get_position(seat_num: int, button_seat: int, all_seats: list, num_players: int) -> str:
    sorted_seats = sorted(all_seats)
    if num_players == 2:
        return "SB" if seat_num == button_seat else "BB"
    btn_idx = sorted_seats.index(button_seat)
    ordered = sorted_seats[btn_idx + 1:] + sorted_seats[:btn_idx + 1]
    pos_map = POSITION_MAPS.get(num_players)
    if not pos_map:
        return "?"
    try:
        player_idx = ordered.index(seat_num)
    except ValueError:
        return "?"
    if seat_num == button_seat:
        return "BTN"
    if player_idx == 0:
        return "SB"
    elif player_idx == 1:
        return "BB"
    else:
        middle_positions = pos_map[:-3]
        mid_idx = player_idx - 2
        return middle_positions[mid_idx] if mid_idx < len(middle_positions) else "?"


# ── Parser do nome do ficheiro ───────────────────────────────────────────────

def _parse_filename(filename: str) -> dict:
    """
    Extrai data, hora, blinds e TM number do nome do ficheiro GGPoker.
    Formato: 2026-03-06_06_02_PM_2,000_4,000(500)_#TM5672663145.png
    """
    result = {"date": None, "time": None, "blinds": None, "tm": None}

    # TM number: #TM seguido de dígitos
    tm_m = re.search(r'#TM(\d+)', filename)
    if tm_m:
        result["tm"] = f"TM{tm_m.group(1)}"

    # Data: YYYY-MM-DD
    date_m = re.search(r'(\d{4}-\d{2}-\d{2})', filename)
    if date_m:
        result["date"] = date_m.group(1)

    # Hora: HH_MM_AM/PM → converter para 24h
    time_m = re.search(r'(\d{1,2})_(\d{2})_(AM|PM)', filename, re.IGNORECASE)
    if time_m:
        h, m, period = int(time_m.group(1)), int(time_m.group(2)), time_m.group(3).upper()
        if period == "PM" and h != 12:
            h += 12
        elif period == "AM" and h == 12:
            h = 0
        result["time"] = f"{h:02d}:{m:02d}"

    # Blinds: padrão X,XXX_Y,YYY(ZZZ) ou X_Y(Z)
    # Remover o TM e a data para não confundir
    name_clean = re.sub(r'#TM\d+', '', filename)
    name_clean = re.sub(r'\d{4}-\d{2}-\d{2}_\d{1,2}_\d{2}_(AM|PM)_', '', name_clean, flags=re.IGNORECASE)
    blinds_m = re.search(r'([\d,]+)_([\d,]+)(?:\(([\d,]+)\))?', name_clean)
    if blinds_m:
        sb = blinds_m.group(1).replace(",", "")
        bb = blinds_m.group(2).replace(",", "")
        ante = blinds_m.group(3).replace(",", "") if blinds_m.group(3) else None
        result["blinds"] = f"{sb}/{bb}" + (f"({ante})" if ante else "")

    return result


# ── Vision: extrair jogadores por posição ────────────────────────────────────

def _extract_hand_data_from_image(image_bytes: bytes, mime_type: str = "image/png") -> str | None:
    """
    Usa Vision para extrair jogadores por posição, stacks e bounties.
    Devolve texto estruturado.
    """
    try:
        from openai import OpenAI
        client = OpenAI()

        b64 = base64.b64encode(image_bytes).decode("utf-8")
        data_url = f"data:{mime_type};base64,{b64}"

        prompt = (
            "This is a GGPoker hand replayer screenshot.\n\n"
            "Extract ALL the following and reply in EXACTLY this format (no extra text, no markdown):\n\n"
            "TM: <TM number from title, digits only after TM, e.g. TM5672663145>\n"
            "TOURNAMENT: <tournament name from title>\n"
            "HERO: <hero player name — the player at bottom center of the table>\n"
            "BOARD: <community cards space-separated, e.g. 7s 9d 5d Jc Kd, or NONE>\n"
            "POT: <final pot size number only, or NONE>\n\n"
            "Then for EACH player visible at the table, one line:\n"
            "PLAYER: <position> | <name> | <stack_chips> | <bounty_pct> | <country_flag>\n\n"
            "Position MUST be one of: UTG, UTG+1, MP, MP+1, HJ, CO, BTN, SB, BB\n"
            "Use the action panel at the bottom to determine positions (UTG acts first preflop).\n"
            "Stack is the chip count shown below the player name.\n"
            "Bounty_pct is the percentage shown in the bounty badge (e.g. 18%), or 0 if none.\n"
            "Country_flag is the 2-letter country code from the flag icon, or NONE.\n\n"
            "Example lines:\n"
            "PLAYER: UTG | offon0ff- | 39000 | 0% | TH\n"
            "PLAYER: BB | Lauro Dermio | 38000 | 0% | BR\n\n"
            "Output ONLY the structured lines above. No explanations."
        )

        response = client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "image_url", "image_url": {"url": data_url, "detail": "high"}},
                        {"type": "text", "text": prompt},
                    ],
                }
            ],
            max_tokens=700,
        )

        text = response.choices[0].message.content.strip()
        logger.info(f"Vision response: {text}")
        return text

    except Exception as e:
        logger.error(f"Vision error: {e}")
        return None


# Normalise position labels to match HH parser convention
_POS_NORM = {
    "UTG+1": "UTG1", "UTG+2": "UTG2",
    "MP+1": "MP1", "MP+2": "MP2",
    "HJ": "HJ",  # already correct
}

def _normalise_position(pos: str) -> str:
    return _POS_NORM.get(pos.upper(), pos.upper())


def _parse_vision_response(text: str) -> dict:
    """Parse the structured Vision response into a dict."""
    result = {
        "tm": None,
        "tournament": None,
        "hero": None,
        "board": [],
        "pot": None,
        "players_by_position": {},  # position → {name, stack, bounty_pct, country}
    }
    if not text:
        return result

    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue

        if line.startswith("TM:"):
            val = line[3:].strip()
            m = re.search(r'TM(\d+)', val)
            if m:
                result["tm"] = f"TM{m.group(1)}"

        elif line.startswith("TOURNAMENT:"):
            result["tournament"] = line[11:].strip()

        elif line.startswith("HERO:"):
            val = line[5:].strip()
            if val and val.upper() not in ("NONE", "UNKNOWN"):
                result["hero"] = val

        elif line.startswith("BOARD:"):
            val = line[6:].strip()
            if val and val.upper() != "NONE":
                result["board"] = val.split()

        elif line.startswith("POT:"):
            val = line[4:].strip().replace(",", "")
            if val and val.upper() != "NONE":
                try:
                    result["pot"] = int(val)
                except ValueError:
                    pass

        elif line.startswith("PLAYER:"):
            parts = [p.strip() for p in line[7:].split("|")]
            if len(parts) >= 3:
                pos = parts[0].upper()
                name = parts[1]
                stack_str = parts[2].replace(",", "")
                bounty_str = parts[3] if len(parts) > 3 else "0%"
                country = parts[4] if len(parts) > 4 else None

                try:
                    stack = int(stack_str)
                except ValueError:
                    stack = 0

                bounty_pct = 0
                bounty_m = re.search(r'(\d+)', bounty_str)
                if bounty_m:
                    bounty_pct = int(bounty_m.group(1))

                pos = _normalise_position(pos)
                result["players_by_position"][pos] = {
                    "name": name,
                    "stack": stack,
                    "bounty_pct": bounty_pct,
                    "country": country if country and country.upper() != "NONE" else None,
                }

    return result


# ── Match: posição → anon_id → nome real ────────────────────────────────────

def _build_anon_to_real_map(hand_row: dict, vision_players: dict) -> dict:
    """
    Constrói mapa anon_id → nome_real usando correspondência por posição.

    hand_row: linha da BD com all_players_actions (JSONB)
    vision_players: dict posição → {name, stack, ...} do Vision
    """
    anon_map = {}

    all_players = hand_row.get("all_players_actions")
    if not all_players:
        return anon_map

    # all_players_actions: {nome_ou_anon: {seat, position, stack_bb, actions, ...}}
    for player_key, info in all_players.items():
        if player_key == "Hero":
            anon_map["Hero"] = "Hero"
            continue

        pos = info.get("position", "")
        vision_info = vision_players.get(pos)
        if vision_info:
            anon_map[player_key] = vision_info["name"]

    return anon_map


def _enrich_all_players_actions(all_players: dict, anon_map: dict, vision_players: dict) -> dict:
    """
    Substitui chaves anónimas pelos nomes reais em all_players_actions
    e adiciona bounty_pct e country de cada jogador.
    """
    enriched = {}
    for player_key, info in all_players.items():
        real_name = anon_map.get(player_key, player_key)
        pos = info.get("position", "")
        vision_info = vision_players.get(pos, {})

        new_info = dict(info)
        new_info["real_name"] = real_name
        new_info["bounty_pct"] = vision_info.get("bounty_pct", 0)
        new_info["country"] = vision_info.get("country")

        enriched[real_name] = new_info

    return enriched

# ── Compressão de imagem ────────────────────────────────────────────────────────────────

def _compress_image(image_bytes: bytes, max_width: int = 1280, quality: int = 85) -> tuple[str, str]:
    """
    Comprime imagem: redimensiona para max_width e converte para JPEG quality.
    Devolve (img_b64_compressed, mime_type).
    """
    try:
        img = Image.open(io.BytesIO(image_bytes))
        # Converter RGBA/P para RGB (JPEG não suporta alpha)
        if img.mode in ("RGBA", "P", "LA"):
            img = img.convert("RGB")
        elif img.mode != "RGB":
            img = img.convert("RGB")

        # Redimensionar se largura > max_width
        if img.width > max_width:
            ratio = max_width / img.width
            new_height = int(img.height * ratio)
            img = img.resize((max_width, new_height), Image.LANCZOS)

        # Guardar como JPEG
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=quality, optimize=True)
        compressed_bytes = buf.getvalue()
        compressed_b64 = base64.b64encode(compressed_bytes).decode("utf-8")

        original_kb = len(image_bytes) / 1024
        compressed_kb = len(compressed_bytes) / 1024
        logger.info(f"Compressão: {original_kb:.0f}KB → {compressed_kb:.0f}KB ({img.width}x{img.height}) "
                    f"ratio: {compressed_kb/original_kb*100:.0f}%")

        return compressed_b64, "image/jpeg"
    except Exception as e:
        logger.error(f"Erro na compressão: {e}. A usar imagem original.")
        return base64.b64encode(image_bytes).decode("utf-8"), "image/png"

# ── Storage ──────────────────────────────────────────────────────────────────────────

def _upload_screenshot_to_storage(image_bytes: bytes, filename: str) -> str | None:
    import hashlib
    storage_dir = "/tmp/poker_screenshots"
    os.makedirs(storage_dir, exist_ok=True)
    h = hashlib.md5(image_bytes).hexdigest()[:12]
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "png"
    stored_name = f"{h}.{ext}"
    stored_path = os.path.join(storage_dir, stored_name)
    with open(stored_path, "wb") as f:
        f.write(image_bytes)
    return f"/screenshots/{stored_name}"


# ── Endpoint principal ───────────────────────────────────────────────────────

# Semáforo global — máximo 2 chamadas Vision em paralelo
_vision_sem = asyncio.Semaphore(2)

async def _run_vision_for_entry(entry_id: int, content: bytes, mime_type: str,
                                tm_number: str, file_meta: dict, img_b64: str):
    """
    Processa Vision em background para um entry já guardado na BD.
    Usa asyncio.to_thread para não bloquear o event loop.
    Actualiza raw_json com players_by_position, hero, board e vision_done=True.
    Se houver match com HH, enriquece a mão com nomes reais.
    """
    try:
        async with _vision_sem:
            vision_text = await asyncio.to_thread(_extract_hand_data_from_image, content, mime_type)
        vision_data = _parse_vision_response(vision_text)
        tm_final = tm_number or vision_data.get("tm")
        vision_players = vision_data.get("players_by_position", {})
        hero_name = vision_data.get("hero")
        board = vision_data.get("board", [])
        logger.info(f"[bg] Vision OK entry {entry_id} \u2014 TM: {tm_final}, players: {list(vision_players.keys())}")

        # Comprimir imagem DEPOIS do Vision (Vision j\u00e1 recebeu original)
        compressed_b64, compressed_mime = await asyncio.to_thread(_compress_image, content)

        # Actualizar entry com dados do Vision + imagem comprimida
        def _db_update():
            conn = get_conn()
            try:
                with conn.cursor() as cur:
                    raw_json_str = json.dumps({
                            "tm": tm_final,
                            "file_meta": file_meta,
                            "mime_type": compressed_mime,
                            "img_b64": compressed_b64,
                            "players_by_position": vision_players,
                            "hero": hero_name,
                            "board": board,
                            "raw_vision": vision_text,
                            "vision_done": True,
                        })
                    cur.execute(
                        "UPDATE entries SET raw_json = %s WHERE id = %s",
                        (raw_json_str, entry_id)
                    )
                conn.commit()
            except Exception as e:
                conn.rollback()
                logger.error(f"[bg] Erro ao actualizar entry {entry_id} com Vision: {e}")
            finally:
                conn.close()
        await asyncio.to_thread(_db_update)

        # Tentar match com HH se tiver TM (em thread)
        if tm_final and vision_players:
            def _try_match():
                tm_digits = tm_final.replace("TM", "")
                hand_rows = query(
                    "SELECT id, hand_id, all_players_actions, position FROM hands WHERE hand_id = %s LIMIT 1",
                    (f"GG-{tm_digits}",)
                )
                if hand_rows:
                    raw_for_enrich = {
                        "players_by_position": vision_players,
                        "hero": hero_name,
                        "file_meta": file_meta,
                    }
                    result = _enrich_hand_from_orphan_entry(entry_id, hand_rows[0]["id"], raw_for_enrich)
                    logger.info(f"[bg] Match entry {entry_id} \u2192 hand {hand_rows[0]['id']}: {result}")
            await asyncio.to_thread(_try_match)

    except Exception as e:
        logger.error(f"[bg] Vision falhou para entry {entry_id}: {e}")


@router.post("")
async def upload_screenshot(
    file: UploadFile = File(...),
    background_tasks: BackgroundTasks = None,
    current_user=Depends(require_auth),
):
    """
    Upload de screenshot do replayer GG.
    Pipeline: guardar imediatamente → responder → Vision em background.
    O screenshot é sempre guardado na BD antes de chamar o Vision.
    """
    content = await file.read()
    filename = file.filename or "screenshot.png"
    mime_type = file.content_type or "image/png"

    if not mime_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Ficheiro deve ser uma imagem (PNG/JPG)")

    # 1. Extrair dados do nome do ficheiro (fonte primária — rápido, sem rede)
    file_meta = _parse_filename(filename)
    tm_number = file_meta.get("tm")
    logger.info(f"Filename parsed: {file_meta}")

    # 2. Comprimir imagem para guardar na BD (original vai para Vision)
    compressed_b64, compressed_mime = _compress_image(content)
    # Manter original em memória para Vision (não guardar na BD)
    img_b64_original = base64.b64encode(content).decode("utf-8")

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
                    f"Screenshot \u2014 TM: {tm_number or 'n\u00e3o detectado'}",
                    json.dumps({
                        "tm": tm_number,
                        "file_meta": file_meta,
                        "mime_type": compressed_mime,
                        "img_b64": compressed_b64,
                        "players_by_position": {},
                        "hero": None,
                        "vision_done": False,
                    }),
                )
            )
            entry_id = cur.fetchone()["id"]
        conn.commit()
        logger.info(f"Screenshot guardado como entry {entry_id} (TM: {tm_number}, comprimido)")
    except Exception as e:
        conn.rollback()
        logger.error(f"Erro ao guardar entry de screenshot: {e}")
        raise HTTPException(status_code=500, detail=f"Erro ao guardar screenshot: {e}")
    finally:
        conn.close()

    # 3. Lançar Vision em background (não bloqueia o response)
    # Nota: passa content (original) para Vision ter melhor qualidade
    if background_tasks is not None:
        background_tasks.add_task(
            _run_vision_for_entry, entry_id, content, mime_type, tm_number, file_meta, img_b64_original
        )
    else:
        asyncio.create_task(
            _run_vision_for_entry(entry_id, content, mime_type, tm_number, file_meta, img_b64_original)
        )

    # 4. Responder imediatamente — Vision e match correm em background
    return {
        "status": "queued",
        "tm_number": tm_number,
        "file_meta": file_meta,
        "message": "Screenshot guardado. Vision a processar em background.",
        "entry_id": entry_id,
    }


def _enrich_hand_from_orphan_entry(entry_id: int, hand_db_id: int, raw_json: dict) -> dict:
    """
    Função partilhada: dado um entry de screenshot órfão e o id da mão na BD,
    aplica o enriquecimento completo (nomes reais, bounty, country) à mão
    e marca o entry como 'resolved'.
    Devolve um dict com o resultado do enriquecimento.
    """
    vision_players = raw_json.get("players_by_position", {})
    hero_name = raw_json.get("hero")
    file_meta = raw_json.get("file_meta", {})
    screenshot_url = raw_json.get("screenshot_url")

    # Buscar a mão completa para enriquecimento
    hand_rows = query(
        "SELECT id, hand_id, all_players_actions, position FROM hands WHERE id = %s",
        (hand_db_id,)
    )
    if not hand_rows:
        return {"status": "hand_not_found"}

    matched_hand = dict(hand_rows[0])
    all_players_raw = matched_hand.get("all_players_actions") or {}

    # Construir mapa anon → nome real por posição
    anon_map = _build_anon_to_real_map(matched_hand, vision_players)

    # Enriquecer all_players_actions com nomes reais + bounty + country
    enriched_actions = _enrich_all_players_actions(all_players_raw, anon_map, vision_players)

    # Metadata completa para player_names
    player_names_json = {
        "players_by_position": vision_players,
        "hero": hero_name,
        "anon_map": anon_map,
        "file_meta": file_meta,
    }

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            # Actualizar a mão com nomes reais e screenshot_url
            if screenshot_url:
                cur.execute(
                    """
                    UPDATE hands
                    SET player_names = %s,
                        all_players_actions = %s,
                        screenshot_url = %s
                    WHERE id = %s
                    """,
                    (
                        json.dumps(player_names_json),
                        json.dumps(enriched_actions),
                        screenshot_url,
                        hand_db_id,
                    )
                )
            else:
                cur.execute(
                    """
                    UPDATE hands
                    SET player_names = %s,
                        all_players_actions = %s
                    WHERE id = %s
                    """,
                    (
                        json.dumps(player_names_json),
                        json.dumps(enriched_actions),
                        hand_db_id,
                    )
                )
            # Marcar entry como resolvida
            cur.execute("UPDATE entries SET status = 'resolved' WHERE id = %s", (entry_id,))
        conn.commit()
        logger.info(f"Enriched hand {hand_db_id} from orphan entry {entry_id}: {len(anon_map)} mappings")
    except Exception as e:
        conn.rollback()
        logger.error(f"Error enriching hand {hand_db_id} from entry {entry_id}: {e}")
        return {"status": "error", "error": str(e)}
    finally:
        conn.close()

    return {
        "status": "enriched",
        "hand_id": hand_db_id,
        "players_mapped": len([k for k, v in anon_map.items() if k != "Hero"]),
        "anon_map": anon_map,
    }


@router.post("/orphans/{entry_id}/rematch")
def rematch_orphan(entry_id: int, current_user=Depends(require_auth)):
    """Tenta novamente o match de um screenshot órfão com a HH já importada."""
    rows = query(
        "SELECT id, raw_json FROM entries WHERE id = %s AND entry_type = 'screenshot' AND status = 'new'",
        (entry_id,)
    )
    if not rows:
        raise HTTPException(status_code=404, detail="Screenshot órfão não encontrado")

    raw = rows[0].get("raw_json") or {}
    tm_number = raw.get("tm")
    if not tm_number:
        return {"status": "no_tm", "message": "TM number não detectado neste screenshot"}

    tm_digits = tm_number.replace("TM", "")
    hand_rows = query(
        "SELECT id, hand_id FROM hands WHERE hand_id = %s LIMIT 1",
        (f"GG-{tm_digits}",)
    )
    if not hand_rows:
        return {"status": "no_match", "message": f"HH do torneio {tm_number} ainda não importada"}

    # Match encontrado — enriquecer a mão com nomes reais
    result = _enrich_hand_from_orphan_entry(entry_id, hand_rows[0]["id"], raw)
    return {
        "status": result.get("status", "matched"),
        "hand_id": hand_rows[0]["id"],
        "hand_hand_id": hand_rows[0]["hand_id"],
        "players_mapped": result.get("players_mapped", 0),
        "anon_map": result.get("anon_map", {}),
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


async def _backfill_worker(entry_ids: list):
    """
    Worker assíncrono que processa entries 1 a 1 sequencialmente.
    Busca cada imagem da BD individualmente para não sobrecarregar a memória.
    Todas as operações síncronas correm em threads para não bloquear o event loop.
    """
    for eid in entry_ids:
        try:
            def _fetch_entry(entry_id):
                return query(
                    "SELECT id, raw_json FROM entries WHERE id = %s",
                    (entry_id,)
                )
            rows = await asyncio.to_thread(_fetch_entry, eid)
            if not rows:
                continue
            raw = rows[0].get("raw_json") or {}
            img_b64 = raw.get("img_b64", "")
            if not img_b64:
                continue

            content = base64.b64decode(img_b64)
            mime_type = raw.get("mime_type", "image/png")
            tm_number = raw.get("tm")
            file_meta = raw.get("file_meta", {})

            await _run_vision_for_entry(eid, content, mime_type, tm_number, file_meta, img_b64)
            await asyncio.sleep(1)  # Pausa entre chamadas para não sobrecarregar
        except Exception as e:
            logger.error(f"[backfill] Erro no entry {eid}: {e}")


@router.post("/vision/backfill")
async def vision_backfill(
    limit: int = 50,
    current_user=Depends(require_auth),
):
    """
    Reprocessa screenshots com vision_done=false.
    Busca apenas os IDs e lança um worker assíncrono em background.
    Responde imediatamente.
    """
    def _fetch_pending_ids(lim):
        return query(
            """SELECT id
               FROM entries
               WHERE entry_type = 'screenshot'
                 AND status = 'new'
                 AND (raw_json->>'vision_done')::boolean = false
               ORDER BY id ASC
               LIMIT %s""",
            (lim,)
        )
    rows = await asyncio.to_thread(_fetch_pending_ids, limit)

    entry_ids = [r["id"] for r in rows]

    if entry_ids:
        asyncio.create_task(_backfill_worker(entry_ids))

    def _count_pending():
        return query(
            "SELECT COUNT(*) as n FROM entries WHERE entry_type='screenshot' AND (raw_json->>'vision_done')::boolean = false",
            ()
        )[0]["n"]
    total_pending = await asyncio.to_thread(_count_pending)

    return {
        "queued": len(entry_ids),
        "total_pending": total_pending,
        "message": f"{len(entry_ids)} screenshots a processar sequencialmente em background.",
    }


@router.get("/vision/status")
def vision_status(current_user=Depends(require_auth)):
    """Estado do processamento Vision: quantos feitos vs pendentes."""
    rows = query(
        """SELECT
             COUNT(*) FILTER (WHERE (raw_json->>'vision_done')::boolean = true) as done,
             COUNT(*) FILTER (WHERE (raw_json->>'vision_done')::boolean = false) as pending,
             COUNT(*) as total
           FROM entries WHERE entry_type = 'screenshot'""",
        ()
    )
    r = rows[0] if rows else {"done": 0, "pending": 0, "total": 0}
    return {"done": r["done"], "pending": r["pending"], "total": r["total"]}
