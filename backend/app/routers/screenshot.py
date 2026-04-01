"""
Endpoint para upload de screenshots do replayer GG.

Pipeline completo (v2 — match por stack):
  1. Recebe imagem (PNG/JPG)
  2. Extrai data, hora, blinds e TM number do nome do ficheiro (fonte primária)
  3. Usa Vision (GPT-4.1-mini) para extrair:
     - SB e BB do painel esquerdo (100% fiável)
     - Nome + stack de cada jogador na mesa
     - Hero (centro da mesa)
  4. Faz match com a mão na BD pelo hand_id (GG-{TM_number})
  5. Constrói mapa hash → nome_real usando:
     a) Âncoras fixas: Hero, SB, BB
     b) Fold players: stack_screenshot ≈ stack_hh - ante (tolerância <2%)
     c) Eliminação: restantes (jogadores ativos no pot)
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
    Formatos suportados:
      Antigo: 2026-02-28_08_30_PM_25_000_50_000_6_000___TM5645872965.png
      Novo:   2026-03-28__05-45_PM__0_10__0_20__5761227426.png
    """
    result = {"date": None, "time": None, "blinds": None, "tm": None}

    # TM number — try multiple formats
    # Format 1: #TM followed by digits
    tm_m = re.search(r'#?TM(\d+)', filename)
    if tm_m:
        result["tm"] = f"TM{tm_m.group(1)}"
    else:
        # Format 2: #NUMBER (without TM prefix)
        tm_m2 = re.search(r'#(\d{8,})', filename)
        if tm_m2:
            result["tm"] = f"TM{tm_m2.group(1)}"
        else:
            # Format 3: bare digits at end of filename (new GG format)
            # Match last sequence of 8+ digits before extension
            tm_m3 = re.search(r'(\d{8,})(?:\.\w+)?$', filename)
            if tm_m3:
                result["tm"] = f"TM{tm_m3.group(1)}"

    # Date
    date_m = re.search(r'(\d{4}-\d{2}-\d{2})', filename)
    if date_m:
        result["date"] = date_m.group(1)

    # Time — support both underscore and hyphen separators
    # Format 1: 08_30_PM (old)
    time_m = re.search(r'(\d{1,2})[-_](\d{2})[-_](AM|PM)', filename, re.IGNORECASE)
    if time_m:
        h, m, period = int(time_m.group(1)), int(time_m.group(2)), time_m.group(3).upper()
        if period == "PM" and h != 12:
            h += 12
        elif period == "AM" and h == 12:
            h = 0
        result["time"] = f"{h:02d}:{m:02d}"

    # Blinds — support both formats
    # Strategy: detect format by presence of ___TM (old) vs __digits (new)
    has_triple_tm = '___TM' in filename

    if has_triple_tm:
        # OLD format: 2026-02-28_08_30_PM_25_000_50_000_6_000___TM5645872965.png
        # Also: 2026-03-29_07_08_PM_60_120_15___TM... (60/120 ante 15)
        # Underscores can be thousands separators (25_000) OR field separators (60_120_15)
        blinds_section = re.search(
            r'(?:AM|PM)[_\s]+([\d,_]+?)___TM',
            filename, re.IGNORECASE
        )
        if blinds_section:
            raw = blinds_section.group(1)
            parts = raw.split('_')
            n = len(parts)
            if n <= 3:
                # Direct: each part is a separate number (60_120_15 → 60/120/15)
                nums = parts
            elif n % 2 == 0:
                # Even count: try pairs as thousands (25_000_50_000 → 25000/50000)
                nums = [parts[i] + parts[i+1] for i in range(0, n, 2)]
            else:
                # Odd >3: group by _\d{3} pattern, fallback to split
                segments = re.findall(r'\d+(?:_\d{3})+|\d+', raw)
                nums = [s.replace('_', '') for s in segments]
                if len(nums) < 2:
                    nums = parts
            if len(nums) >= 2:
                sb, bb = nums[0], nums[1]
                ante = nums[2] if len(nums) >= 3 else None
                if len(sb) <= 6 and len(bb) <= 6:
                    result["blinds"] = f"{sb}/{bb}" + (f"({ante})" if ante else "")
    else:
        # NEW format: 2026-03-29__05-52_PM__1_50__3__5766245148.png
        # Blinds between PM__ and __TM_digits, underscores are DECIMAL points
        # Pattern: __SB__BB__DIGITS or __SB__BB__ANTE__DIGITS
        blinds_section = re.search(
            r'(?:AM|PM)__([\d_]+?)__([\d_]+?)(?:__([\d_]+?))?__(\d{8,})',
            filename, re.IGNORECASE
        )
        if blinds_section:
            def underscore_to_decimal(s):
                """Convert 1_50 → 1.50, 0_13 → 0.13, 3 → 3"""
                if '_' in s:
                    return s.replace('_', '.', 1)
                return s
            sb = underscore_to_decimal(blinds_section.group(1))
            bb = underscore_to_decimal(blinds_section.group(2))
            ante_raw = blinds_section.group(3)
            ante = underscore_to_decimal(ante_raw) if ante_raw else None
            # Validate: not too long
            if len(sb) <= 8 and len(bb) <= 8:
                result["blinds"] = f"{sb}/{bb}" + (f"({ante})" if ante else "")

    return result


# ── Vision: extrair jogadores, SB/BB do painel, stacks ───────────────────────

def _extract_hand_data_from_image(image_bytes: bytes, mime_type: str = "image/png") -> str | None:
    """
    Usa Vision para extrair dados do screenshot do replayer GG.

    Estratégia validada por testes (10 mesas, 77 jogadores):
    - SB e BB: lidos do PAINEL ESQUERDO (Blind/Ante section) — 100% fiável
    - Nomes + stacks: lidos da mesa para cada jogador
    - Posições visuais: NÃO confiáveis — o match real é feito por stack
    """
    try:
        from openai import OpenAI
        client = OpenAI()

        b64 = base64.b64encode(image_bytes).decode("utf-8")
        data_url = f"data:{mime_type};base64,{b64}"

        prompt = (
            "This is a GGPoker hand replayer screenshot.\n\n"
            "KNOWN FACTS:\n"
            "- The HERO is always 'Lauro Dermio', 'koumpounophobia', 'FlightRisk', or 'Karluz' (bottom center of table).\n"
            "- SB and BB player names are written in the LEFT PANEL (Blind/Ante section).\n"
            "- Player names can appear in different colors: white, yellow, purple/lilac, green.\n"
            "- Players with 'WIN' overlay on their avatar must still be included.\n"
            "- Players who went all-in may show stack 0.\n\n"
            "YOUR TASKS:\n"
            "1. Read the title bar for TM number and tournament name.\n"
            "2. Read the LEFT PANEL to identify the SB and BB player names.\n"
            "3. For EVERY player seated at the table, read their nickname, chip stack,\n"
            "   bounty percentage (if shown), and country flag.\n"
            "   The chip stack is the colored number shown directly below each player's name.\n\n"
            "Reply in EXACTLY this format (no extra text, no markdown):\n"
            "TM: <TM number, e.g. TM5672663145>\n"
            "TOURNAMENT: <tournament name from title>\n"
            "HERO: <hero player name>\n"
            "BOARD: <community cards, e.g. 7s 9d 5d Jc Kd, or NONE>\n"
            "POT: <pot size number, or NONE>\n"
            "SB: <SB player name from LEFT PANEL>\n"
            "BB: <BB player name from LEFT PANEL>\n"
            "PLAYER: <name> | <stack> | <bounty_pct> | <country>\n"
            "PLAYER: <name> | <stack> | <bounty_pct> | <country>\n"
            "... (one PLAYER line per player, including Hero, SB, and BB)\n\n"
            "RULES:\n"
            "- Stack must be the exact number shown below the name (e.g. 65021 or 102944)\n"
            "- If a player's stack shows 0, write 0\n"
            "- Bounty_pct is the percentage in the badge (e.g. 18%), or 0 if none\n"
            "- Country is the 2-letter code from the flag, or NONE\n"
            "- Include ALL players visible at the table, even if eliminated\n"
            "- Do NOT guess positions — only output SB and BB from the left panel\n\n"
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
    "HJ": "HJ",
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
        "vision_sb": None,
        "vision_bb": None,
        "players_by_position": {},
        "players_list": [],
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

        elif line.startswith("SB:"):
            val = line[3:].strip()
            if val and val.upper() not in ("NONE", "UNKNOWN"):
                result["vision_sb"] = val

        elif line.startswith("BB:"):
            val = line[3:].strip()
            if val and val.upper() not in ("NONE", "UNKNOWN"):
                result["vision_bb"] = val

        elif line.startswith("PLAYER:"):
            parts = [p.strip() for p in line[7:].split("|")]
            if len(parts) >= 2:
                name = parts[0]
                stack_str = parts[1].replace(",", "").replace(".", "")
                bounty_str = parts[2] if len(parts) > 2 else "0%"
                country = parts[3] if len(parts) > 3 else None

                try:
                    stack = int(stack_str)
                except ValueError:
                    stack = 0

                bounty_pct = 0
                bounty_m = re.search(r'(\d+)', bounty_str)
                if bounty_m:
                    bounty_pct = int(bounty_m.group(1))

                player_info = {
                    "name": name,
                    "stack": stack,
                    "bounty_pct": bounty_pct,
                    "country": country if country and country.upper() != "NONE" else None,
                }
                result["players_list"].append(player_info)

    return result


# ── Extracção de dados da HH raw ──────────────────────────────────────────

def _parse_hh_stacks_and_blinds(raw_hh: str) -> dict:
    """
    Extrai stacks iniciais (chips), ante, SB/BB sizes da HH raw.
    
    Importante: a HH mostra stacks ANTES de antes/blinds.
    O screenshot mostra stacks no FINAL da mão.
    Para fold players: stack_screenshot = stack_hh - ante
    """
    result = {"ante": 0, "sb_size": 0, "bb_size": 0, "button_seat": None, "players": {}}

    level_m = re.search(r"Level\s*\d+\s*\(([\d,]+)/([\d,]+)(?:\(([\d,]+)\))?\)", raw_hh)
    if level_m:
        result["sb_size"] = int(level_m.group(1).replace(",", ""))
        result["bb_size"] = int(level_m.group(2).replace(",", ""))
        if level_m.group(3):
            result["ante"] = int(level_m.group(3).replace(",", ""))

    if result["ante"] == 0:
        ante_m = re.search(r"posts the ante\s+([\d,]+)", raw_hh)
        if ante_m:
            result["ante"] = int(ante_m.group(1).replace(",", ""))

    btn_m = re.search(r"Seat\s*#(\d+)\s+is the button", raw_hh)
    if btn_m:
        result["button_seat"] = int(btn_m.group(1))

    seats = {}
    all_seat_nums = []
    for sm in re.finditer(r"Seat\s+(\d+):\s*(.+?)\s*\(([\d,]+)\s+in chips\)", raw_hh):
        seat_num = int(sm.group(1))
        name = sm.group(2).strip()
        stack = int(sm.group(3).replace(",", ""))
        seats[seat_num] = {"name": name, "stack_chips": stack}
        all_seat_nums.append(seat_num)

    num_players = len(all_seat_nums)
    button_seat = result["button_seat"]
    if button_seat and all_seat_nums:
        for seat_num, info in seats.items():
            pos = _get_position(seat_num, button_seat, all_seat_nums, num_players)
            info["position"] = pos
            result["players"][info["name"]] = {
                "seat": seat_num,
                "stack_chips": info["stack_chips"],
                "position": pos,
            }

    return result


def _is_fold_preflop(actions: dict) -> bool:
    """Verifica se o jogador fez fold preflop (ou não teve ação)."""
    if not actions:
        return True
    preflop = actions.get("preflop", [])
    if not preflop:
        return True
    if len(preflop) == 1 and "Fold" in preflop[0]:
        return True
    return False


# ── Match: âncoras + stack esperado + eliminação ─────────────────────────────

def _build_anon_to_real_map(hand_row: dict, vision_data: dict) -> dict:
    """
    Constrói mapa player_key → nome_real usando 3 estratégias:

    1. ÂNCORAS FIXAS: Hero (centro), SB e BB (painel esquerdo — 100% fiável)
    2. FOLD PLAYERS: stack_esperado = stack_hh - ante → match com Vision (<2%)
    3. ELIMINAÇÃO: jogadores restantes (ativos no pot)

    O screenshot mostra stacks no FINAL da mão.
    A HH mostra stacks no INÍCIO (antes de antes/blinds).
    Para fold players: stack_screenshot = stack_hh - ante
    """
    anon_map = {}

    all_players = hand_row.get("all_players_actions")
    if not all_players:
        return anon_map

    vision_sb = vision_data.get("vision_sb")
    vision_bb = vision_data.get("vision_bb")
    vision_list = vision_data.get("players_list", [])
    hero_name_vision = vision_data.get("hero")

    raw_hh = hand_row.get("raw", "")
    hh_data = _parse_hh_stacks_and_blinds(raw_hh) if raw_hh else None

    used_vision = set()
    hero_names = ["lauro dermio", "koumpounophobia", "lauro derm", "flightrisk", "karluz"]

    # ── Fase 1: Âncoras fixas ────────────────────────────────────────────

    for player_key, info in all_players.items():
        pos = info.get("position", "")

        # Hero
        if player_key == "Hero" or info.get("is_hero"):
            for i, vp in enumerate(vision_list):
                if i in used_vision:
                    continue
                if any(h in vp["name"].lower() for h in hero_names):
                    anon_map[player_key] = vp["name"]
                    used_vision.add(i)
                    break
            if player_key not in anon_map:
                anon_map[player_key] = hero_name_vision or "Hero"
            continue

        # SB (do painel esquerdo — alta fiabilidade)
        if pos == "SB" and vision_sb:
            for i, vp in enumerate(vision_list):
                if i in used_vision:
                    continue
                if vp["name"].lower().startswith(vision_sb.lower()[:6]):
                    anon_map[player_key] = vp["name"]
                    used_vision.add(i)
                    break
            if player_key not in anon_map:
                anon_map[player_key] = vision_sb
            continue

        # BB (do painel esquerdo — alta fiabilidade)
        if pos == "BB" and vision_bb:
            for i, vp in enumerate(vision_list):
                if i in used_vision:
                    continue
                if vp["name"].lower().startswith(vision_bb.lower()[:6]):
                    anon_map[player_key] = vp["name"]
                    used_vision.add(i)
                    break
            if player_key not in anon_map:
                anon_map[player_key] = vision_bb
            continue

    # ── Fase 2: Fold players — match por stack esperado ──────────────────

    if hh_data:
        ante = hh_data["ante"]

        for player_key, info in all_players.items():
            if player_key in anon_map:
                continue

            actions = info.get("actions", {})
            if not _is_fold_preflop(actions):
                continue

            hh_player = hh_data["players"].get(player_key, {})
            stack_initial = hh_player.get("stack_chips", 0)
            if stack_initial == 0:
                continue

            # Stack esperado no screenshot = stack_inicial - ante
            stack_esperado = stack_initial - ante

            best_i = None
            best_diff = float("inf")
            for i, vp in enumerate(vision_list):
                if i in used_vision:
                    continue
                diff = abs(stack_esperado - vp["stack"])
                pct = (diff / stack_esperado * 100) if stack_esperado > 0 else 999
                if pct < 2.0 and diff < best_diff:
                    best_diff = diff
                    best_i = i

            if best_i is not None:
                anon_map[player_key] = vision_list[best_i]["name"]
                used_vision.add(best_i)
                logger.info(f"  Fold match: {player_key} -> {vision_list[best_i]['name']} "
                           f"(esperado={stack_esperado}, vision={vision_list[best_i]['stack']}, "
                           f"diff={best_diff})")

    # ── Fase 3: Eliminação — jogadores restantes ─────────────────────────

    unmapped_hh = [k for k in all_players if k not in anon_map]
    unmapped_vision = [i for i in range(len(vision_list)) if i not in used_vision]

    if len(unmapped_hh) == 1 and len(unmapped_vision) == 1:
        anon_map[unmapped_hh[0]] = vision_list[unmapped_vision[0]]["name"]
        logger.info(f"  Elimination match: {unmapped_hh[0]} -> {vision_list[unmapped_vision[0]]['name']}")
    elif len(unmapped_hh) > 0 and len(unmapped_vision) > 0:
        still_unmapped_vision = set(unmapped_vision)
        for player_key in unmapped_hh:
            hh_player = hh_data["players"].get(player_key, {}) if hh_data else {}
            stack_initial = hh_player.get("stack_chips", 0)

            best_i = None
            best_diff = float("inf")
            for i in still_unmapped_vision:
                vp = vision_list[i]
                diff = abs(stack_initial - vp["stack"])
                if diff < best_diff:
                    best_diff = diff
                    best_i = i

            if best_i is not None:
                anon_map[player_key] = vision_list[best_i]["name"]
                still_unmapped_vision.discard(best_i)
                logger.info(f"  Approx match: {player_key} -> {vision_list[best_i]['name']} "
                           f"(hh_initial={stack_initial}, vision={vision_list[best_i]['stack']}, "
                           f"diff={best_diff})")

    logger.info(f"Match result: {len(anon_map)}/{len(all_players)} mapped. "
               f"Anchors: Hero+SB+BB. Folds: stack match. Rest: elimination.")
    return anon_map


def _enrich_all_players_actions(all_players: dict, anon_map: dict, vision_data: dict) -> dict:
    """
    Substitui chaves anónimas pelos nomes reais em all_players_actions
    e adiciona bounty_pct e country de cada jogador.
    """
    enriched = {}

    vision_by_name = {}
    for vp in vision_data.get("players_list", []):
        vision_by_name[vp["name"].lower()] = vp
    vision_by_pos = vision_data.get("players_by_position", {})

    for player_key, info in all_players.items():
        real_name = anon_map.get(player_key, player_key)

        vision_info = vision_by_name.get(real_name.lower(), {})
        if not vision_info:
            pos = info.get("position", "")
            vision_info = vision_by_pos.get(pos, {})

        new_info = dict(info)
        new_info["real_name"] = real_name
        new_info["bounty_pct"] = vision_info.get("bounty_pct", 0)
        new_info["country"] = vision_info.get("country")

        enriched[real_name] = new_info

    return enriched


# ── Compressão de imagem ─────────────────────────────────────────────────────

def _compress_image(image_bytes: bytes, max_width: int = 1280, quality: int = 85) -> tuple[str, str]:
    """Comprime imagem: redimensiona para max_width e converte para JPEG."""
    try:
        img = Image.open(io.BytesIO(image_bytes))
        if img.mode in ("RGBA", "P", "LA"):
            img = img.convert("RGB")
        elif img.mode != "RGB":
            img = img.convert("RGB")

        if img.width > max_width:
            ratio = max_width / img.width
            new_height = int(img.height * ratio)
            img = img.resize((max_width, new_height), Image.LANCZOS)

        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=quality, optimize=True)
        compressed_bytes = buf.getvalue()
        compressed_b64 = base64.b64encode(compressed_bytes).decode("utf-8")

        original_kb = len(image_bytes) / 1024
        compressed_kb = len(compressed_bytes) / 1024
        logger.info(f"Compress: {original_kb:.0f}KB -> {compressed_kb:.0f}KB ({img.width}x{img.height}) "
                    f"ratio: {compressed_kb/original_kb*100:.0f}%")

        return compressed_b64, "image/jpeg"
    except Exception as e:
        logger.error(f"Compress error: {e}. Using original.")
        return base64.b64encode(image_bytes).decode("utf-8"), "image/png"


# ── Storage ──────────────────────────────────────────────────────────────────

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

_vision_sem = asyncio.Semaphore(2)

async def _run_vision_for_entry(entry_id: int, content: bytes, mime_type: str,
                                tm_number: str, file_meta: dict, img_b64: str):
    """
    Processa Vision em background para um entry já guardado na BD.
    Vision recebe imagem ORIGINAL (resolução máxima) para melhor extracção.
    Após Vision, comprime e actualiza entry na BD.
    Se houver match com HH, enriquece a mão com nomes reais.
    """
    try:
        async with _vision_sem:
            vision_text = await asyncio.to_thread(_extract_hand_data_from_image, content, mime_type)
        vision_data = _parse_vision_response(vision_text)
        tm_final = tm_number or vision_data.get("tm")
        vision_players = vision_data.get("players_list", [])
        hero_name = vision_data.get("hero")
        board = vision_data.get("board", [])
        vision_sb = vision_data.get("vision_sb")
        vision_bb = vision_data.get("vision_bb")
        logger.info(f"[bg] Vision OK entry {entry_id} -- TM: {tm_final}, "
                    f"players: {len(vision_players)}, SB={vision_sb}, BB={vision_bb}")

        # Comprimir imagem DEPOIS do Vision (Vision já recebeu original)
        compressed_b64, compressed_mime = await asyncio.to_thread(_compress_image, content)

        def _db_update():
            conn = get_conn()
            try:
                with conn.cursor() as cur:
                    raw_json_str = json.dumps({
                            "tm": tm_final,
                            "file_meta": file_meta,
                            "mime_type": compressed_mime,
                            "img_b64": compressed_b64,
                            "players_list": vision_players,
                            "players_by_position": {},
                            "hero": hero_name,
                            "board": board,
                            "vision_sb": vision_sb,
                            "vision_bb": vision_bb,
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
                logger.error(f"[bg] DB update error entry {entry_id}: {e}")
            finally:
                conn.close()
        await asyncio.to_thread(_db_update)

        # Tentar match com HH se tiver TM
        if tm_final and vision_players:
            def _try_match():
                tm_digits = tm_final.replace("TM", "")
                
                # 1. Tentar match na tabela hands (fluxo antigo)
                hand_rows = query(
                    "SELECT id, hand_id, all_players_actions, position, raw "
                    "FROM hands WHERE hand_id = %s LIMIT 1",
                    (f"GG-{tm_digits}",)
                )
                if hand_rows:
                    result = _enrich_hand_from_orphan_entry(entry_id, hand_rows[0]["id"], {
                        "players_list": vision_players,
                        "players_by_position": {},
                        "hero": hero_name,
                        "vision_sb": vision_sb,
                        "vision_bb": vision_bb,
                        "file_meta": file_meta,
                    })
                    logger.info(f"[bg] Match entry {entry_id} -> hand {hand_rows[0]['id']}: {result}")
                
                # 2. Tentar match na tabela mtt_hands (auto-rematch bidirecional)
                try:
                    mtt_rows = query(
                        "SELECT id, tm_number, raw FROM mtt_hands "
                        "WHERE tm_number = %s AND has_screenshot = false LIMIT 1",
                        (f"TM{tm_digits}",)
                    )
                    if mtt_rows:
                        from app.routers.mtt import (
                            _parse_mtt_hand, _create_villains_for_hand,
                            _build_seat_to_name_map, _promote_to_study
                        )
                        
                        screenshot_data = {
                            "entry_id": entry_id,
                            "players_list": vision_players,
                            "players_by_position": {},
                            "hero": hero_name,
                            "vision_sb": vision_sb,
                            "vision_bb": vision_bb,
                            "file_meta": file_meta,
                        }
                        
                        mtt_hand = mtt_rows[0]
                        parsed = _parse_mtt_hand(mtt_hand["raw"]) if mtt_hand.get("raw") else None
                        
                        if parsed:
                            conn = get_conn()
                            try:
                                with conn.cursor() as cur:
                                    cur.execute(
                                        "UPDATE mtt_hands SET has_screenshot = true, screenshot_entry_id = %s WHERE id = %s",
                                        (entry_id, mtt_hand["id"])
                                    )
                                
                                if parsed.get("vpip_seats"):
                                    _create_villains_for_hand(conn, mtt_hand["id"], parsed, screenshot_data)
                                
                                seat_to_name = _build_seat_to_name_map(parsed, screenshot_data)
                                _promote_to_study(conn, mtt_hand["id"], parsed, screenshot_data, seat_to_name)
                                
                                conn.commit()
                                logger.info(f"[bg] MTT auto-match: entry {entry_id} -> mtt_hand {mtt_hand['id']} (TM{tm_digits})")
                            except Exception as e:
                                conn.rollback()
                                logger.error(f"[bg] MTT auto-match error: {e}")
                            finally:
                                conn.close()
                except Exception as e:
                    logger.error(f"[bg] MTT auto-match failed for TM{tm_digits}: {e}")
            
            await asyncio.to_thread(_try_match)

    except Exception as e:
        logger.error(f"[bg] Vision failed for entry {entry_id}: {e}")


@router.post("")
async def upload_screenshot(
    file: UploadFile = File(...),
    background_tasks: BackgroundTasks = None,
    current_user=Depends(require_auth),
):
    """
    Upload de screenshot do replayer GG.
    Pipeline: guardar imediatamente -> responder -> Vision em background.
    """
    content = await file.read()
    filename = file.filename or "screenshot.png"
    mime_type = file.content_type or "image/png"

    if not mime_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Ficheiro deve ser uma imagem (PNG/JPG)")

    file_meta = _parse_filename(filename)
    tm_number = file_meta.get("tm")
    logger.info(f"Filename parsed: {file_meta}")

    # Comprimir para BD (original fica em memória para Vision)
    compressed_b64, compressed_mime = _compress_image(content)
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
                    f"Screenshot -- TM: {tm_number or 'not detected'}",
                    json.dumps({
                        "tm": tm_number,
                        "file_meta": file_meta,
                        "mime_type": compressed_mime,
                        "img_b64": compressed_b64,
                        "players_list": [],
                        "players_by_position": {},
                        "hero": None,
                        "vision_sb": None,
                        "vision_bb": None,
                        "vision_done": False,
                    }),
                )
            )
            entry_id = cur.fetchone()["id"]
        conn.commit()
        logger.info(f"Screenshot saved as entry {entry_id} (TM: {tm_number})")
    except Exception as e:
        conn.rollback()
        logger.error(f"Error saving screenshot entry: {e}")
        raise HTTPException(status_code=500, detail=f"Error saving screenshot: {e}")
    finally:
        conn.close()

    # Vision em background (passa original, não comprimido)
    if background_tasks is not None:
        background_tasks.add_task(
            _run_vision_for_entry, entry_id, content, mime_type, tm_number, file_meta, img_b64_original
        )
    else:
        asyncio.create_task(
            _run_vision_for_entry(entry_id, content, mime_type, tm_number, file_meta, img_b64_original)
        )

    return {
        "status": "queued",
        "tm_number": tm_number,
        "file_meta": file_meta,
        "message": "Screenshot guardado. Vision a processar em background.",
        "entry_id": entry_id,
    }


def _enrich_hand_from_orphan_entry(entry_id: int, hand_db_id: int, raw_json: dict) -> dict:
    """
    Dado um entry de screenshot e o id da mão na BD,
    aplica o enriquecimento completo (nomes reais, bounty, country)
    e marca o entry como 'resolved'.
    """
    hero_name = raw_json.get("hero")
    file_meta = raw_json.get("file_meta", {})
    screenshot_url = raw_json.get("screenshot_url")

    hand_rows = query(
        "SELECT id, hand_id, all_players_actions, position, raw FROM hands WHERE id = %s",
        (hand_db_id,)
    )
    if not hand_rows:
        return {"status": "hand_not_found"}

    matched_hand = dict(hand_rows[0])
    all_players_raw = matched_hand.get("all_players_actions") or {}

    # Novo algoritmo v2: âncoras + stack esperado + eliminação
    anon_map = _build_anon_to_real_map(matched_hand, raw_json)
    enriched_actions = _enrich_all_players_actions(all_players_raw, anon_map, raw_json)

    player_names_json = {
        "players_list": raw_json.get("players_list", []),
        "hero": hero_name,
        "vision_sb": raw_json.get("vision_sb"),
        "vision_bb": raw_json.get("vision_bb"),
        "anon_map": anon_map,
        "file_meta": file_meta,
        "match_method": "anchors_stack_elimination_v2",
    }

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            if screenshot_url:
                cur.execute(
                    """UPDATE hands
                    SET player_names = %s, all_players_actions = %s, screenshot_url = %s
                    WHERE id = %s""",
                    (json.dumps(player_names_json), json.dumps(enriched_actions),
                     screenshot_url, hand_db_id)
                )
            else:
                cur.execute(
                    """UPDATE hands
                    SET player_names = %s, all_players_actions = %s
                    WHERE id = %s""",
                    (json.dumps(player_names_json), json.dumps(enriched_actions), hand_db_id)
                )
            cur.execute("UPDATE entries SET status = 'resolved' WHERE id = %s", (entry_id,))
        conn.commit()
        logger.info(f"Enriched hand {hand_db_id} from entry {entry_id}: {len(anon_map)} mappings")
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
    """Worker assíncrono que processa entries 1 a 1 sequencialmente."""
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
            await asyncio.sleep(1)
        except Exception as e:
            logger.error(f"[backfill] Error entry {eid}: {e}")


@router.post("/vision/backfill")
async def vision_backfill(
    limit: int = 50,
    current_user=Depends(require_auth),
):
    """Reprocessa screenshots com vision_done=false em background."""
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
            "SELECT COUNT(*) as n FROM entries WHERE entry_type='screenshot' "
            "AND (raw_json->>'vision_done')::boolean = false",
            ()
        )[0]["n"]
    total_pending = await asyncio.to_thread(_count_pending)

    return {
        "queued": len(entry_ids),
        "total_pending": total_pending,
        "message": f"{len(entry_ids)} screenshots a processar em background.",
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
