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
from difflib import SequenceMatcher
from itertools import permutations
from typing import Optional
from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, BackgroundTasks, Response, Query, Body
from PIL import Image
from app.auth import require_auth, require_auth_or_api_key
from app.db import get_conn, query
from app.hero_names import HERO_NAMES_ALL, ALL_NICKS_BY_SITE, FRIEND_HEROES
from app.ingest_filters import is_pre_2026
from app.utils.timezones import utc_to_lisbon_naive

router = APIRouter(prefix="/api/screenshots", tags=["screenshots"])
logger = logging.getLogger("screenshots")

# ── Hero nicks seen in GG screenshots ────────────────────────────────────────
# GG uses anonymised display names for non-hero players, so the hero's
# real nickname is always visible in the bottom-center seat. Keep this list
# restricted to aliases actually used on GGPoker by the user.


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

def _build_gg_vision_prompt() -> str:
    """Prompt ÚNICO da Vision do replayer GG (#pt53; a leitura corre em Claude).
    Injecta a lista dinâmica de heroes GG (Rui + FRIEND_HEROES) e preserva os
    detalhes sensíveis: VPIP% (badge laranja) vs bounty USD (coroa dourada), e os
    nomes SB/BB lidos do painel esquerdo. Saída em LINHAS (parseada por
    _parse_vision_response)."""
    # Lista dinâmica de heroes GG (Rui + FRIEND_HEROES aplicáveis a GG).
    # 4 nicks — pequeno o suficiente para não confundir o modelo.
    gg_heroes = sorted(n.title() for n in ALL_NICKS_BY_SITE.get("GGPoker", []))
    hero_list_str = ", ".join(f"'{n}'" for n in gg_heroes) if gg_heroes else "'Lauro Dermio'"

    return (
        "This is a GGPoker hand replayer screenshot.\n\n"
        "KNOWN FACTS:\n"
        f"- The HERO is one of these names (centered at bottom of table): {hero_list_str}.\n"
        "- SB and BB player names are written in the LEFT PANEL (Blind/Ante section).\n"
        "- The tournament LEVEL number is shown in the LEFT PANEL (e.g. 'Lv 5' or 'Level 5').\n"
        "- Player names can appear in different colors: white, yellow, purple/lilac, green.\n"
        "- Players with 'WIN' overlay on their avatar must still be included.\n"
        "- Players who went all-in may show stack 0.\n"
        "- Each player avatar shows TWO SEPARATE pieces of info — do NOT confuse them\n"
        "  (see #FIELD-BOUNTY-PCT-MISNAMED):\n"
        "    * VPIP: a small dark CIRCLE holding a plain integer right next to the avatar\n"
        "      (e.g. '34', '26', '40', '0'), usually with a tiny orange flame. It has NO\n"
        "      dollar sign. It is how often the player enters pots — it is NOT the bounty.\n"
        "    * BOUNTY (the PKO knockout prize): a DOLLAR amount shown in the GOLDEN/TAN\n"
        "      BANNER (plate) at the very TOP of the avatar, ABOVE the nickname — e.g.\n"
        "      '$268.18', '$57.03', '$142.20', '$81.25', '$303.33'. It ALWAYS has a '$'\n"
        "      and usually 2 decimals; a small golden crown/trophy icon may sit beside it.\n"
        "      ⚠️ This is a BOUNTY tournament: EVERY active player has this $ banner at the\n"
        "      top of their avatar — read it for each one. It is almost never 0. Only use 0\n"
        "      if a player genuinely has no $ banner (e.g. already busted, stack 0).\n"
        "      If the banner shows two amounts like '$344.65 +$151.67' (Hero with a pending\n"
        "      knockout), take ONLY the FIRST amount ('344.65').\n\n"
        "YOUR TASKS:\n"
        "1. Read the title bar for TM number and tournament name.\n"
        "2. Read the LEFT PANEL to identify the SB and BB player names.\n"
        "3. Read the LEFT PANEL for the current tournament LEVEL number.\n"
        "4. For EVERY player seated at the table, read:\n"
        "   (a) Nickname.\n"
        "   (b) Chip stack — the colored number shown directly below each player's name.\n"
        "   (c) VPIP percentage — the integer inside the ORANGE FLAME badge (use 0 if not shown).\n"
        "   (d) Bounty USD value — the dollar amount in the GOLDEN/TAN BANNER at the TOP of\n"
        "       the avatar (above the name). Output the number ONLY (no '$' or commas). If\n"
        "       two amounts are shown, take the FIRST. Use 0 ONLY if there is genuinely no\n"
        "       $ banner for that player.\n"
        "   (e) Country code from the flag (2 letters, or NONE).\n"
        "   (f) Position label, read from the ACTION LOG in the BOTTOM/LEFT panel\n"
        "       (the panel with Pre-Flop/Flop/Turn/River columns, one row per\n"
        "       action). In that log, each player's action row shows a small\n"
        "       POSITION BADGE next to the player name — one of: UTG, UTG+1,\n"
        "       UTG+2, MP, MP+1, LJ, HJ, CO, BTN (or BU), SB, BB. Transcribe that\n"
        "       badge EXACTLY as drawn. If a player has NO badge in the action log\n"
        "       (e.g. the Hero, or someone seated but not dealt into this hand),\n"
        "       output NONE. NEVER infer a position from stack size or seat order\n"
        "       — only transcribe a badge that is actually printed in the log.\n\n"
        "Reply in EXACTLY this format (no extra text, no markdown):\n"
        "TM: <TM number, e.g. TM5672663145>\n"
        "TOURNAMENT: <tournament name from title>\n"
        "LEVEL: <integer level number from LEFT PANEL, e.g. 5, or NONE>\n"
        "HERO: <hero player name>\n"
        "BOARD: <community cards, e.g. 7s 9d 5d Jc Kd, or NONE>\n"
        "POT: <pot size number, or NONE>\n"
        "SB: <SB player name from LEFT PANEL>\n"
        "BB: <BB player name from LEFT PANEL>\n"
        "PLAYER: <name> | <stack> | <vpip_pct> | <bounty_value_usd> | <country> | <position>\n"
        "PLAYER: <name> | <stack> | <vpip_pct> | <bounty_value_usd> | <country> | <position>\n"
        "... (one PLAYER line per player, including Hero, SB, and BB)\n"
        "GREEN_KO: <winner_name> | <green_value>\n"
        "... (one GREEN_KO line per GREEN KO-transfer value you see; none → omit)\n\n"
        "RULES:\n"
        "- Stack must be the exact number shown below the name (e.g. 65021 or 102944)\n"
        "- If a player's stack shows 0, write 0\n"
        "- vpip_pct is the integer in the ORANGE FLAME badge ON the avatar (e.g. '28'\n"
        "  for 28%); use 0 if not visible. The orange flame is ALWAYS the VPIP\n"
        "  statistic — it is NEVER the bounty. See #FIELD-BOUNTY-PCT-MISNAMED.\n"
        "- bounty_value_usd is the DOLLAR amount printed on the rectangular $ PLATE that\n"
        "  sits DIRECTLY ABOVE the avatar (e.g. '268.18' for $268.18, '57.03' for\n"
        "  $57.03). This $ plate is a SEPARATE element above the seat and is the ONLY\n"
        "  place the bounty is shown. There is NO crown, coin or badge icon on the\n"
        "  avatar itself. NEVER include '$' or commas.\n"
        "  ★ The $ plate is drawn above the avatar EVEN WHEN the avatar below is COVERED\n"
        "    — by face-down (red) cards, a red 'All-In' seal, a 'WIN' seal, or (for the\n"
        "    Hero) the Hero's own large hole cards. A covered avatar does NOT hide the\n"
        "    plate above it.\n"
        "  ★ Do NOT confuse the orange FLAME on the avatar (a small % like '28', no '$')\n"
        "    with the bounty on the $ PLATE above it (a dollar amount like '268.18'). If\n"
        "    the only bounty-looking thing near a seat is the orange flame %, that seat's\n"
        "    bounty is NOT that number.\n"
        "  ★ If there is NO readable $ plate above a seat, write NULL (not 0). Do NOT\n"
        "    invent a value and do NOT copy a neighbour's plate.\n"
        "- ★ ELIMINATED seat (0 chips / cracked-broken cards over the avatar / a player\n"
        "  who just busted this hand): an eliminated player has NO OWN $ plate — it is\n"
        "  GONE. Write bounty_value_usd = NULL for that seat (their real bounty is read\n"
        "  from the GREEN value below, not from any plate near their seat).\n"
        "- ★ GREEN_KO: when a player ELIMINATES someone, HALF of the eliminated player's\n"
        "  bounty appears as a GREEN dollar value ON/NEXT TO the eliminator's $ PLATE\n"
        "  (e.g. a plate showing '$253.75 +$102.27' — the '+$102.27' in GREEN is the KO\n"
        "  transfer). For EACH green value you see, emit one GREEN_KO line: the winner's\n"
        "  name and the green number (no '$', no '+'). No green values → no GREEN_KO line.\n"
        "- Country is the 2-letter code from the flag, or NONE\n"
        "- Level must be a plain integer (strip 'Lv' or 'Level' prefix) or NONE if not visible\n"
        "- Include ALL players visible at the table, even if eliminated\n"
        "- position: transcribe the position BADGE shown in the ACTION LOG (bottom/\n"
        "  left panel) next to each player's action row, EXACTLY as drawn (UTG,\n"
        "  UTG+1, UTG+2, MP, MP+1, LJ, HJ, CO, BTN/BU, SB, BB). Output NONE when a\n"
        "  player has no badge in the log. NEVER guess from stack or seat order.\n"
        "  (SB/BB names above come from the blinds area; this position field comes\n"
        "  from the per-player badge in the action log.)\n\n"
        "Output ONLY the structured lines above. No explanations."
    )


# Modelo Claude para a Vision do replayer (#pt53). Igual aos outros 3 pipelines.
_REPLAYER_CLAUDE_MODEL = "claude-sonnet-4-6"


def _extract_hand_data_from_image_claude(image_bytes: bytes, mime_type: str = "image/png") -> str | None:
    """Leitura LIVE do replayer GG via Claude (claude-sonnet-4-6) — #pt53. Saída
    em LINHAS (parseada por _parse_vision_response); padrão de imagem base64 dos
    3 outros pipelines Claude. Devolve o texto, ou None em falha de API (não
    engole: o caller (_run_vision_for_entry) deixa a entry retry-able)."""
    try:
        from anthropic import Anthropic  # lazy
    except ImportError:
        logger.error("anthropic SDK não instalado")
        return None
    try:
        client = Anthropic()
        b64 = base64.b64encode(image_bytes).decode("ascii")
        prompt = _build_gg_vision_prompt()
        response = client.messages.create(
            model=_REPLAYER_CLAUDE_MODEL,
            max_tokens=1500,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": mime_type,
                                "data": b64,
                            },
                        },
                        {"type": "text", "text": prompt},
                    ],
                },
            ],
        )
        text = (response.content[0].text or "").strip()
        logger.info(f"[claude] Vision response: {text}")
        return text
    except Exception as e:
        logger.error(f"[claude] Vision error: {type(e).__name__}: {e}")
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
        "vision_level": None,
        "players_by_position": {},
        "players_list": [],
        "green_kos": [],   # verde-KO: {winner, value} (cura verde-KO)
    }
    if not text:
        return result

    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue

        if line.startswith("GREEN_KO:"):
            body = line[len("GREEN_KO:"):].strip()
            parts = [p.strip() for p in body.split("|")]
            if len(parts) >= 2:
                m = re.search(r"[\d]+(?:[.,]\d+)?", parts[1])
                if m:
                    try:
                        val = float(m.group(0).replace(",", ""))
                    except ValueError:
                        val = 0.0
                    if parts[0] and val > 0:
                        result["green_kos"].append({"winner": parts[0], "value": val})
            continue

        if line.startswith("TM:"):
            val = line[3:].strip()
            # #P10 fix (pt14) — Recidiva de #B33: regex word-boundary
            # \b(\d{8,12})\b só casava quando Vision omitia o prefixo "TM"
            # (3% dos casos). No caso maioritário "TM12345" não havia boundary
            # entre M e 5 (ambos word chars), logo o regex falhava silenciosamente
            # em 67/69 entries (97%). Fix correcto: prefixo "TM" opcional
            # DENTRO do match, sem depender de word boundary. Aceita os 4
            # formatos pretendidos pelo #B33: "TM12345", "12345", "TM 12345",
            # "TM: 12345" (este último já tratado pelo line[3:].strip() acima).
            m = re.search(r'(?:TM\s*)?(\d{8,12})', val)
            if m:
                result["tm"] = f"TM{m.group(1)}"

        elif line.startswith("TOURNAMENT:"):
            result["tournament"] = line[11:].strip()

        elif line.startswith("LEVEL:"):
            val = line[6:].strip()
            if val and val.upper() != "NONE":
                # Tolera "5", "Lv 5", "Level 5" — extrai o primeiro inteiro.
                m = re.search(r'\d+', val)
                if m:
                    try:
                        result["vision_level"] = int(m.group(0))
                    except ValueError:
                        pass

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
                raw_stack = parts[1]
                # pt24: format estendido `name | stack | vpip_pct | bounty_value_usd | country`
                # (5 fields). Backward-compat com format legacy 4-field
                # `name | stack | bounty_pct | country` — onde bounty_pct historicamente
                # era usado para VPIP % (orange flame), não para bounty $. Tech debt
                # #FIELD-BOUNTY-PCT-MISNAMED traceia o rename futuro do field key.
                # pt-pos: 6º campo opcional `position` (rótulo lido junto ao seat
                # na gold image). Aditivo — não altera o caminho stack-elimination.
                position_str = None
                if len(parts) >= 5:
                    vpip_str = parts[2]
                    bounty_value_str = parts[3]
                    country = parts[4]
                    if len(parts) >= 6:
                        position_str = parts[5]
                else:
                    vpip_str = parts[2] if len(parts) > 2 else "0%"
                    bounty_value_str = "0"
                    country = parts[3] if len(parts) > 3 else None

                # Parse stack. Vision devolve em 2 formatos possíveis:
                #   "215940"     → fichas (inteiro)
                #   "10.2 BB"    → big blinds (float com sufixo)
                #   "32 BB"      → big blinds (inteiro com sufixo)
                # Guardamos stack_raw (valor original) + stack_unit ("chips" | "bb").
                # A conversão bb→chips é feita depois, quando já temos o bb_size
                # da HH (função _normalize_vision_stacks).
                stack_value = 0.0
                stack_unit = "chips"

                # Remover vírgulas (milhares) antes de qualquer coisa
                s = raw_stack.replace(",", "").strip()

                # Detectar sufixo BB (case-insensitive, com ou sem espaço)
                bb_match = re.search(r"([\d.]+)\s*BB", s, re.IGNORECASE)
                if bb_match:
                    try:
                        stack_value = float(bb_match.group(1))
                        stack_unit = "bb"
                    except ValueError:
                        stack_value = 0.0
                else:
                    # Formato fichas. Pode ter "." como separador de milhares
                    # (configuração regional, ex: "1.234.567") — mas neste caso
                    # não há "BB" no fim. Só removemos "." se houver mais do que um
                    # (senão mantemos como decimal, improvável mas seguro).
                    s_clean = s.replace(".", "") if s.count(".") > 1 else s
                    try:
                        stack_value = float(s_clean)
                    except ValueError:
                        stack_value = 0.0

                # ⚠️ ARMADILHA RECORRENTE: isto é o VPIP do jogador (a CHAMA LARANJA 🔥),
                # NÃO o bounty. O bounty (PKO/KO) é a COROA DOURADA 👑 em $ =
                # `bounty_value_usd` (abaixo). O nome do campo `bounty_pct` é histórico
                # e ENGANADOR — guarda o VPIP %. Backward-compat com 4 consumidores:
                # villain_rules.py, mtt.py (incl. coluna BD hand_villains.bounty_pct),
                # ire.py (gate), screenshot.py _replace_hashes_in_actions. Rename para
                # `vpip_pct` deferido — ver #FIELD-BOUNTY-PCT-MISNAMED.
                bounty_pct = 0
                vpip_m = re.search(r'(\d+)', vpip_str)
                if vpip_m:
                    bounty_pct = int(vpip_m.group(1))

                # bounty_value_usd — dollar amount on the $ PLATE above the avatar
                # (prompt novo 11 Jul). "NULL"/vazio (sem placa legível) → None =
                # 'por rever', NUNCA 0 (num PKO não há bounty 0; a leitura falhou).
                # Strip de "$"/"," defensivo. Ver #FLAME-AS-CROWN-GUARD.
                bv = (bounty_value_str or "").replace("$", "").replace(",", "").strip()
                if bv.upper() in ("", "NULL", "NONE", "-", "N/A"):
                    bounty_value_usd = None
                else:
                    bv_m = re.search(r'[\d]+(?:\.[\d]+)?', bv)
                    bounty_value_usd = float(bv_m.group(0)) if bv_m else None

                player_info = {
                    "name": name,
                    # Compatibilidade: `stack` continua a ser um int em fichas quando
                    # possível. Se Vision devolveu BB, `stack` é 0 até haver conversão.
                    # O matching usa stack_chips (preenchido por _normalize_vision_stacks).
                    "stack": int(stack_value) if stack_unit == "chips" else 0,
                    "stack_raw": stack_value,
                    "stack_unit": stack_unit,
                    "stack_chips": int(stack_value) if stack_unit == "chips" else None,
                    "bounty_pct": bounty_pct,             # historic name; semantically VPIP % — see #FIELD-BOUNTY-PCT-MISNAMED
                    "bounty_value_usd": bounty_value_usd, # pt24: USD bounty (golden crown)
                    "country": country if country and country.upper() != "NONE" else None,
                    # pt-pos: rótulo de posição lido na imagem (None se não visível).
                    # Aditivo; consumido só pelo mapa por posição (match_method
                    # 'position_v3'). O caminho stack-elimination ignora-o.
                    "position": (position_str.strip().upper()
                                 if position_str and position_str.strip().upper() != "NONE"
                                 else None),
                }
                result["players_list"].append(player_info)

    return result


def _normalize_vision_stacks(vision_data: dict, bb_size: int) -> dict:
    """
    Garante que cada jogador no players_list tem `stack_chips` preenchido
    (valor em fichas, int). Converte unidades "bb" → "chips" usando bb_size.

    Não modifica o vision_data original — devolve uma cópia com os players_list
    normalizados. Se bb_size for 0, não faz nada (devolve original).
    """
    if not vision_data or not bb_size:
        return vision_data
    pl = vision_data.get("players_list") or []
    if not pl:
        return vision_data

    new_list = []
    for p in pl:
        np = dict(p)
        # Já tem chips → nada a fazer
        if np.get("stack_chips"):
            new_list.append(np)
            continue
        unit = np.get("stack_unit")
        raw = np.get("stack_raw")
        # Entries antigos: sem stack_unit/stack_raw, só com "stack" (int fichas ou 0)
        if unit is None and raw is None:
            legacy_stack = np.get("stack", 0)
            np["stack_chips"] = int(legacy_stack) if legacy_stack else None
            new_list.append(np)
            continue
        if unit == "bb" and raw is not None:
            np["stack_chips"] = int(round(float(raw) * bb_size))
            np["stack"] = np["stack_chips"]  # compat: preencher também o campo antigo
        elif unit == "chips" and raw is not None:
            np["stack_chips"] = int(raw)
        new_list.append(np)

    new_data = dict(vision_data)
    new_data["players_list"] = new_list
    return new_data


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

    # Normalizar stacks do Vision para fichas se vieram em BB.
    # Alguns SS GG têm stacks em "10.2 BB" em vez de "35700" fichas.
    # Usamos bb_size da HH (fonte de verdade) para converter.
    bb_size = (hh_data or {}).get("bb_size", 0)
    if bb_size:
        vision_data = _normalize_vision_stacks(vision_data, bb_size)
        vision_list = vision_data.get("players_list", [])

    used_vision = set()
    hero_names = HERO_NAMES_ALL

    # ── Fase 1: Âncoras fixas ────────────────────────────────────────────

    for player_key, info in all_players.items():
        if player_key == "_meta":
            continue  # metadata, não é jogador
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
            # Tech Debt #B2: substituir startswith[:6] por SequenceMatcher
            # ratio >=0.85. Match exacto prioritário; truncamento típico
            # Vision (ratio ~0.91) coberto; nick lido mal (ratio <0.85) cai
            # em fallback explícito vision_sb. Collect+sort impede
            # ambiguidade quando >1 candidato qualifica.
            sb_lower = vision_sb.lower()
            candidates = []
            for i, vp in enumerate(vision_list):
                if i in used_vision:
                    continue
                v_lower = vp["name"].lower()
                if v_lower == sb_lower:
                    candidates = [(i, 1.0)]
                    break
                ratio = SequenceMatcher(None, v_lower, sb_lower).ratio()
                if ratio >= 0.85:
                    candidates.append((i, ratio))
            if candidates:
                candidates.sort(key=lambda c: -c[1])
                best_i = candidates[0][0]
                anon_map[player_key] = vision_list[best_i]["name"]
                used_vision.add(best_i)
            else:
                anon_map[player_key] = vision_sb
            continue

        # BB (do painel esquerdo — alta fiabilidade)
        if pos == "BB" and vision_bb:
            # Tech Debt #B2: idem SB, ver comentário acima.
            bb_lower = vision_bb.lower()
            candidates = []
            for i, vp in enumerate(vision_list):
                if i in used_vision:
                    continue
                v_lower = vp["name"].lower()
                if v_lower == bb_lower:
                    candidates = [(i, 1.0)]
                    break
                ratio = SequenceMatcher(None, v_lower, bb_lower).ratio()
                if ratio >= 0.85:
                    candidates.append((i, ratio))
            if candidates:
                candidates.sort(key=lambda c: -c[1])
                best_i = candidates[0][0]
                anon_map[player_key] = vision_list[best_i]["name"]
                used_vision.add(best_i)
            else:
                anon_map[player_key] = vision_bb
            continue

    # ── Fase 2: Fold players — match por stack esperado ──────────────────

    if hh_data:
        ante = hh_data["ante"]

        for player_key, info in all_players.items():
            if player_key == "_meta":
                continue  # metadata, não é jogador
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
                # Preferir stack_chips (normalizado). Fallback para stack (compat).
                vp_stack = vp.get("stack_chips")
                if vp_stack is None:
                    vp_stack = vp.get("stack", 0)
                if not vp_stack:
                    continue
                diff = abs(stack_esperado - vp_stack)
                # Tech Debt #B1: tolerância dinâmica. 2% relativo OU 20 chips
                # absoluto, o que for maior. Cobre micro-stacks (<1000 chips)
                # onde 2% é demasiado restritivo para erro OCR Vision típico
                # (±5-10 chips); mid/deep stacks mantêm comportamento idêntico.
                tolerance = max(20, stack_esperado * 0.02)
                if diff <= tolerance and diff < best_diff:
                    best_diff = diff
                    best_i = i

            if best_i is not None:
                anon_map[player_key] = vision_list[best_i]["name"]
                used_vision.add(best_i)
                vp_stack_log = vision_list[best_i].get("stack_chips") or vision_list[best_i].get("stack", 0)
                logger.info(f"  Fold match: {player_key} -> {vision_list[best_i]['name']} "
                           f"(esperado={stack_esperado}, vision={vp_stack_log}, "
                           f"diff={best_diff})")

    # ── Fase 3: Eliminação — jogadores restantes ─────────────────────────

    unmapped_hh = [k for k in all_players if k not in anon_map and k != "_meta"]
    unmapped_vision = [i for i in range(len(vision_list)) if i not in used_vision]

    if len(unmapped_hh) == 1 and len(unmapped_vision) == 1:
        anon_map[unmapped_hh[0]] = vision_list[unmapped_vision[0]]["name"]
        logger.info(f"  Elimination match: {unmapped_hh[0]} -> {vision_list[unmapped_vision[0]]['name']}")
    elif len(unmapped_hh) > 0 and len(unmapped_vision) > 0:
        # Tech Debt #B4: substituir greedy ordem-dependente por brute-force
        # enumeration que minimiza soma global de diffs. Para max ~8 jogadores
        # por mesa: 8! = 40320 perms, ~30-80ms — desprezível vs 1 chamada por
        # match. Garante atribuição global óptima.
        hh_stacks = []
        for player_key in unmapped_hh:
            hh_player = hh_data["players"].get(player_key, {}) if hh_data else {}
            hh_stacks.append(hh_player.get("stack_chips", 0))

        vision_stacks = []
        for i in unmapped_vision:
            vp = vision_list[i]
            vp_stack = vp.get("stack_chips")
            if vp_stack is None:
                vp_stack = vp.get("stack", 0)
            vision_stacks.append(vp_stack)

        n = len(unmapped_hh)
        m = len(unmapped_vision)

        best_perm = None
        best_total = float("inf")
        if n <= m:
            for vis_perm in permutations(range(m), n):
                total = sum(
                    abs(hh_stacks[hh_idx] - vision_stacks[vis_perm[hh_idx]])
                    for hh_idx in range(n)
                )
                if total < best_total:
                    best_total = total
                    best_perm = vis_perm

        if best_perm is not None:
            for hh_idx, vis_local_idx in enumerate(best_perm):
                global_vis_idx = unmapped_vision[vis_local_idx]
                player_key = unmapped_hh[hh_idx]
                anon_map[player_key] = vision_list[global_vis_idx]["name"]
                vp_stack_log = vision_stacks[vis_local_idx]
                logger.info(f"  Optimal match: {player_key} -> "
                           f"{vision_list[global_vis_idx]['name']} "
                           f"(hh_initial={hh_stacks[hh_idx]}, "
                           f"vision={vp_stack_log}, "
                           f"diff={abs(hh_stacks[hh_idx] - vp_stack_log)})")

    logger.info(f"Match result: {len(anon_map)}/{len(all_players)} mapped. "
               f"Anchors: Hero+SB+BB. Folds: stack match. Rest: elimination.")
    return anon_map


# ── Mapa nome→cadeira por POSIÇÃO (match_method 'position_v3') ───────────────
# Caminho ADITIVO, separado do stack-elimination acima. NÃO está ligado a
# nenhum caller vivo — é a desanon por posição (prove-first). A HH dá
# seat→posição (botão conhecido); para cada jogador da Vision com rótulo de
# posição visível, o nome vai para o seat da HH com a MESMA posição. Sem
# aritmética de stack. NUNCA adivinha: rótulo em falta, posição sem seat
# correspondente, ou colisão → deixa por mapear e sinaliza (lacuna honesta).

POSITION_V3_MATCH_METHOD = "position_v3"

# Nicks-Hero conhecidos (lowercase) — usado para VERIFICAR o Hero lido pela
# Vision antes de o escrever no seat 'Hero'. Inclui a lista global + os de GG,
# MENOS os FRIEND_HEROES.
# #DESANON-HERO-FRIEND-NICK-ACCEPTED: os friend-heroes (Karluz/flightrisk) são
# VILÕES nas mãos do Rui. A Vision, no campo `hero`, às vezes lê o nick de um
# vilão-amigo como sendo o Hero (raw_vision literal "HERO: Karluz" em
# GG-6113127853/6113686726). Como estavam na whitelist, o guarda ACEITAVA-o e
# escrevia anon_map["Hero"]="Karluz" → nome do vilão no seat do Hero, colidindo
# com o vilão real (apa fundia 2 seats num "Karluz"). Excluí-los → o guarda
# rejeita o friend-nick-como-Hero e deixa lacuna honesta. Raio medido: 0 Gold
# legítimas com Hero=friend (as 2 únicas eram o bug). O Hero é lido pelo texto
# AMARELO na gold (cue fiável — ver prompt da Vision).
_KNOWN_HERO_NICKS = ({n.strip().lower() for n in HERO_NAMES_ALL} | {
    n.strip().lower() for n in ALL_NICKS_BY_SITE.get("GGPoker", [])
}) - {n.strip().lower() for n in FRIEND_HEROES}


def _canon_position(p: str | None) -> str | None:
    """Normaliza um rótulo de posição (HH ou Vision) para um canónico único,
    para que os dois lados comparem sem depender da grafia. Estritamente
    lexical — NÃO infere nada."""
    if not p:
        return None
    s = re.sub(r"\s+", "", str(p).strip().upper()).replace("+", "")
    syn = {
        "BU": "BTN", "BTN": "BTN", "BUTTON": "BTN", "DEALER": "BTN", "D": "BTN",
        "SMALLBLIND": "SB", "SB": "SB",
        "BIGBLIND": "BB", "BB": "BB",
        "LOJACK": "LJ", "LJ": "LJ", "HIJACK": "HJ", "HJ": "HJ",
    }
    return syn.get(s, s)


def _build_anon_to_real_map_by_position(hand_row: dict, vision_data: dict) -> dict:
    """Mapa player_key→nome_real PURAMENTE por posição (sem stack).

    Devolve um dict de diagnóstico:
      {
        "anon_map": {player_key: real_name, ...},   # só os que casaram
        "match_method": "position_v3",
        "hero_ok": bool | None,                       # nome+posição Hero batem?
        "no_label": [vision_name, ...],               # Vision sem rótulo de posição
        "vision_pos_no_hh_seat": [(name, canon_pos)], # rótulo sem seat na HH
        "vision_pos_collision": [canon_pos, ...],     # 2+ Vision na mesma posição
        "unmapped_hh": [(player_key, canon_pos)],     # seats HH sem nome
        "n_mapped": int, "n_hh_seats": int,
      }
    """
    raw_hh = (hand_row.get("raw") or "")
    hh = _parse_hh_stacks_and_blinds(raw_hh)
    hh_players = hh.get("players") or {}   # name(hash/"Hero") -> {seat, stack_chips, position}

    # HH: canon_pos -> player_key (a HH não deve ter colisão de posição)
    pos_to_hhkey = {}
    hh_pos_collision = []
    for key, info in hh_players.items():
        cp = _canon_position(info.get("position"))
        if cp is None:
            continue
        if cp in pos_to_hhkey:
            hh_pos_collision.append(cp)  # defensivo; não deve acontecer
        else:
            pos_to_hhkey[cp] = key

    vlist = vision_data.get("players_list") or []

    # Vision: detectar colisão de posição do lado da imagem
    vis_pos_count = {}
    for vp in vlist:
        cp = _canon_position(vp.get("position"))
        if cp:
            vis_pos_count[cp] = vis_pos_count.get(cp, 0) + 1
    vis_collisions = {cp for cp, n in vis_pos_count.items() if n > 1}

    anon_map = {}
    no_label = []
    vision_pos_no_hh_seat = []
    used_hhkeys = set()

    for vp in vlist:
        name = vp.get("name")
        cp = _canon_position(vp.get("position"))
        if cp is None:
            no_label.append(name)
            continue
        if cp in vis_collisions:
            # 2+ jogadores da Vision com a mesma posição → ambíguo, não mapear
            continue
        hhkey = pos_to_hhkey.get(cp)
        if hhkey is None:
            vision_pos_no_hh_seat.append((name, cp))
            continue
        if hhkey in used_hhkeys:
            continue  # já ocupado (defensivo)
        anon_map[hhkey] = name
        used_hhkeys.add(hhkey)

    # Seat do Hero: NUNCA escrever o 'hero' da Vision às cegas. A Vision por
    # vezes identifica mal o Hero (ex. #6083126980: leu 'MR_WEI' como Hero) — e
    # escrever isso no seat 'Hero' metia o nome de um VILÃO no lugar do Hero.
    # Só mapeamos o seat 'Hero' se o nome da Vision for um nick-Hero CONHECIDO
    # (exacto normalizado, ou ratio ≥ 0.9 para tolerar OCR). Senão: lacuna
    # honesta — deixa 'Hero' por mapear (a jusante o seat continua 'Hero', que
    # já é o Hero) e sinaliza.
    hero_ok = None
    hero_unverified = False
    hero_name_vision = (vision_data.get("hero") or "").strip()
    if "Hero" in hh_players:
        hv = hero_name_vision.lower()
        is_known = bool(hv) and (
            hv in _KNOWN_HERO_NICKS
            or any(SequenceMatcher(None, hv, k).ratio() >= 0.9 for k in _KNOWN_HERO_NICKS)
        )
        hero_ok = is_known
        if is_known:
            anon_map["Hero"] = hero_name_vision
            used_hhkeys.add("Hero")
        else:
            hero_unverified = True

    unmapped_hh = [(k, _canon_position(v.get("position")))
                   for k, v in hh_players.items() if k not in used_hhkeys]

    return {
        "anon_map": anon_map,
        "match_method": POSITION_V3_MATCH_METHOD,
        "hero_ok": hero_ok,
        "hero_unverified": hero_unverified,
        "no_label": no_label,
        "vision_pos_no_hh_seat": vision_pos_no_hh_seat,
        "vision_pos_collision": sorted(vis_collisions),
        "hh_pos_collision": hh_pos_collision,
        "unmapped_hh": unmapped_hh,
        "n_mapped": len([k for k in anon_map if k != "Hero"]),
        "n_hh_seats": len([k for k in hh_players if k != "Hero"]),
    }


def _enrich_all_players_actions(all_players: dict, anon_map: dict, vision_data: dict,
                                tn: str | None = None) -> dict:
    """
    APA §B (Fase 2, core aprovado 8 Jul): enriquece `all_players_actions` **SEM
    re-indexar por nome**. A CHAVE da HH mantém-se (hash GG / nick real não-GG /
    "Hero"); o nome real passa a **atributo** `real_name = anon_map.get(chave) or ""`
    (`""` = por mapear, honesto — o lugar **FICA na mesa**). Copia
    bounty_pct/bounty_value_usd/country da Vision. Preserva '_meta' e TODOS os
    campos do jogador (cards/actions/seat/stack/...) via `dict(info)`.

    Antes (pré-Fase 2) fazia `enriched[real_name]` → dois hashes com o MESMO nome
    FUNDIAM num só lugar (bug MaLong07) e hashes sem nome CAÍAM (sitting-out
    desaparecido). Agora a chave é a identidade da HH → sem fusão, sem queda.
    Leitores lêem `real_name || chave` (Fase 1). Ver `APA_INDEXACAO_E_COLAPSO §B`,
    `DESANON_ANATOMIA §3.4`.

    Nota: o `_rekey_apa_to_hashes` (table_ss_deanon) passa a NO-OP em mãos de
    formato novo (já hash-keyed) — mantido só p/ mãos antigas name-keyed (pré-wipe).
    Mãos ANTIGAS não se migram: um re-enrich sobre elas mantém a chave-nome
    (real_name fica "", mas o leitor mostra a chave) — sem corrupção.
    """
    enriched = {}

    # #FLAME-AS-CROWN-GUARD (position_v3/Gold) — base÷2 + grelha aritmética à ENTRADA
    # da escrita de coroas. Rejeitado → NULL + 'por rever' (crown_review), nunca
    # descarte silencioso. Mutação in-place: o caller usa o MESMO players_list para
    # o `player_names`, logo cobre apa + player_names de uma vez. Só quando `tn`
    # (torneio conhecido → base). Ver `table_ss_deanon._guard_suspect_crowns`.
    if tn:
        try:
            from app.services.table_ss_deanon import _guard_suspect_crowns
            _guard_suspect_crowns(vision_data.get("players_list", []), tn)
        except Exception:
            pass  # ficheiro delicado: a guarda nunca pode partir um import

    # SELO das coroas (invariante do Rui) — importado uma vez p/ o loop.
    from app.services.eliminated_bounty import is_bounty_sealed

    # Preservar metadata — não é um jogador
    if "_meta" in all_players:
        enriched["_meta"] = all_players["_meta"]

    vision_by_name = {}
    for vp in vision_data.get("players_list", []):
        vision_by_name[vp["name"].lower()] = vp
    vision_by_pos = vision_data.get("players_by_position", {})

    for player_key, info in all_players.items():
        if player_key == "_meta":
            continue  # já preservado acima
        # NÃO re-indexar: a chave da HH é a identidade. real_name = atributo.
        real_name = anon_map.get(player_key) or ""

        vision_info = vision_by_name.get(real_name.lower(), {}) if real_name else {}
        if not vision_info:
            pos = info.get("position", "")
            vision_info = vision_by_pos.get(pos, {})

        new_info = dict(info)
        new_info["real_name"] = real_name
        new_info["bounty_pct"] = vision_info.get("bounty_pct", 0)
        # #GOLD-BOUNTY-CARRY: a coroa ($) já vem lida no vision (players_list do
        # entry da Gold); copia-a na MESMA passagem que leva os nomes. Antes só se
        # copiava o VPIP → as 332 mãos Gold ficavam sem coroas. Valor cru aqui; a
        # guarda half-base vive no consumo (queue_export) e no backfill.
        # SELO (invariante do Rui, forense 6570): uma coroa VALIDADA não é reescrita
        # pela leitura da Vision no re-deanon/re-apply. `dict(info)` já traz o valor
        # + source/confirmed selados do apa prévio → preserva-se; salta a Vision + log.
        if is_bounty_sealed(info):
            logger.info("[crown-seal] apa %s (%s) selado (%s) — coroa preservada, "
                        "leitura Vision saltada", player_key, real_name or "?",
                        info.get("bounty_source") or "confirmed")
        else:
            new_info["bounty_value_usd"] = vision_info.get("bounty_value_usd", 0)
        new_info["country"] = vision_info.get("country")
        # Campo `played` RESERVADO p/ sitting-outs futuros (§B.3) — não populado aqui.

        enriched[player_key] = new_info

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


def _link_second_discord_entry_to_existing_hand(
    entry_id: int,
    hand_db_id: int,
    vision_players,
    hero_name,
    vision_sb,
    vision_bb,
    file_meta,
) -> None:
    """
    Quando a 2ª entry Discord chega para o mesmo TM e a hand já existe (do 1º
    match / placeholder / HH import), em vez de bail silencioso:
      1. Append do canal desta entry a hands.discord_tags (idempotente, via
         hand_service.append_discord_channel_to_hand).
      2. Mark entries.status='resolved' (feito pelo mesmo helper).
      3. Aplica regras canónicas A∨C∨D via apply_villain_rules
         (services/villain_rules.py).
    entry_id da 1ª entry é preservado — primeiro ingress continua a ser a
    fonte primária da hand.
    """
    from app.services.hand_service import append_discord_channel_to_hand
    result = append_discord_channel_to_hand(hand_db_id, entry_id)
    if not result["resolved"]:
        return
    logger.info(
        f"[bg] Linked 2nd Discord entry {entry_id} -> hand {hand_db_id} "
        f"(channel={result['channel_added']}, discord_tags={result['discord_tags']})"
    )
    # ONDA 1 #B23 refactor: substitui _maybe_create_rule_c_villain_for_hand
    # pela função canónica única apply_villain_rules (lê tudo de hands +
    # entries.raw_json internamente, aplica A∨C∨D, idempotente).
    from app.services.villain_rules import apply_villain_rules
    try:
        apply_villain_rules(hand_db_id)
    except Exception as e:
        logger.error(
            f"[bg] apply_villain_rules failed hand={hand_db_id} entry={entry_id}: {e}"
        )


async def _run_vision_for_entry(entry_id: int, content: bytes, mime_type: str,
                                tm_number: str, file_meta: dict, img_b64: str,
                                force: bool = False):
    """
    Processa Vision em background para um entry já guardado na BD.
    Vision recebe imagem ORIGINAL (resolução máxima) para melhor extracção.
    Após Vision, comprime e actualiza entry na BD.
    Se houver match com HH, enriquece a mão com nomes reais.
    """
    try:
        async with _vision_sem:
            # pt53: leitura ao vivo via CLAUDE (claude-sonnet-4-6). Toda a Vision
            # da app está na conta Anthropic — caminho OpenAI removido no passo 3.
            vision_text = await asyncio.to_thread(_extract_hand_data_from_image_claude, content, mime_type)
        # pt52: a função de Vision devolve None quando FALHA (ex.: 429 quota,
        # timeout, excepção). NÃO marcar vision_done=true nesse caso — deixa a
        # entry retry-able. Antes marcava done com TM=None (falso "Vision OK"),
        # encravando a recuperação (250 entries presas em pt51).
        if vision_text is None:
            logger.warning(
                f"[bg] Vision FALHOU entry {entry_id} — não marca vision_done "
                f"(retry-able)"
            )
            return
        vision_data = _parse_vision_response(vision_text)
        tm_final = tm_number or vision_data.get("tm")
        vision_players = vision_data.get("players_list", [])
        hero_name = vision_data.get("hero")
        board = vision_data.get("board", [])
        vision_sb = vision_data.get("vision_sb")
        vision_bb = vision_data.get("vision_bb")
        vision_level = vision_data.get("vision_level")
        logger.info(f"[bg] Vision OK entry {entry_id} -- TM: {tm_final}, "
                    f"players: {len(vision_players)}, SB={vision_sb}, BB={vision_bb}, Lv={vision_level}")

        # Comprimir imagem DEPOIS do Vision (Vision já recebeu original)
        compressed_b64, compressed_mime = await asyncio.to_thread(_compress_image, content)

        def _db_update():
            conn = get_conn()
            try:
                with conn.cursor() as cur:
                    import hashlib as _hl
                    raw_json_str = json.dumps({
                            "tm": tm_final,
                            # preservar o file_hash (dedup): este UPDATE reconstrói
                            # o raw_json, e sem isto a 2ª importação da mesma gold
                            # image não encontraria o dedup. Mesmo hash do endpoint.
                            "file_hash": _hl.sha256(content).hexdigest(),
                            "tournament": vision_data.get("tournament"),
                            "file_meta": file_meta,
                            "mime_type": compressed_mime,
                            "img_b64": compressed_b64,
                            "players_list": vision_players,
                            "players_by_position": {},
                            "hero": hero_name,
                            "board": board,
                            "vision_sb": vision_sb,
                            "vision_bb": vision_bb,
                            "vision_level": vision_level,
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
                    }, force=force)
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

            # Fallback placeholder: se nenhuma mão foi criada/ligada a este entry
            # (ex: SS chega mas HH ainda não foi importada), criar uma mão
            # placeholder para ficar visível. Discord → tag GGDiscord + origin
            # 'discord'; upload manual → tag SSMatch + origin 'ss_upload'.
            # Quando a HH for importada via bulk, _promote_to_study apaga esta
            # via DELETE FROM hands WHERE hand_id = %s e insere a versão completa.
            # match_method 'discord_placeholder_no_hh' é reutilizado em ambos os
            # casos — descreve o estado de enrichment (placeholder sem HH), o
            # canal de ingress vive em `origin`.
            def _create_placeholder_if_needed():
                if not tm_final:
                    return
                existing = query(
                    "SELECT id FROM hands WHERE entry_id = %s LIMIT 1",
                    (entry_id,)
                )
                if existing:
                    return  # match correu, já há mão

                ent = query(
                    "SELECT source, discord_channel, discord_posted_at FROM entries WHERE id = %s",
                    (entry_id,)
                )
                if not ent:
                    return
                source = ent[0].get("source")
                is_discord = source == "discord"
                is_ss_upload = source == "screenshot"
                if not (is_discord or is_ss_upload):
                    return

                tm_digits = tm_final.replace("TM", "")
                hand_id = f"GG-{tm_digits}"

                # Não substituir se já existe uma mão GG-<tm> (para não apagar uma
                # mão bulk ou outra SS).
                existing_hand = query(
                    "SELECT id FROM hands WHERE hand_id = %s LIMIT 1",
                    (hand_id,)
                )
                if existing_hand:
                    if is_discord:
                        # 2ª entry Discord para o mesmo TM. Linkar canal + resolve
                        # entry + (condicional) villain C.
                        _link_second_discord_entry_to_existing_hand(
                            entry_id, existing_hand[0]["id"],
                            vision_players, hero_name, vision_sb, vision_bb, file_meta,
                        )
                    # Upload manual de SS duplicado para mesmo TM já com mão:
                    # deixamos existir sem criar placeholder; entry fica ligada
                    # por Vision mas não substitui a mão canónica.
                    return

                # all_players_actions minimal com _meta vindo do Vision data.
                # from_discord_placeholder kept como flag genérica "este é um
                # placeholder sem HH" — é consumido por filtros (ex: MTT exclui
                # placeholders de listas). Mantém nome legado por compatibilidade.
                apa = {
                    "_meta": {
                        "num_players": len(vision_players) if vision_players else 0,
                        "from_discord_placeholder": True,
                    }
                }

                pn_json = {
                    "players_list": vision_players,
                    "hero": hero_name,
                    "board": board,
                    "vision_sb": vision_sb,
                    "vision_bb": vision_bb,
                    "vision_level": vision_level,
                    "file_meta": file_meta,
                    "match_method": "discord_placeholder_no_hh",
                }

                # played_at: Discord → extrair do unix ms em og:image URL;
                # upload manual → None (filename pode não ter data/hora, e
                # mesmo quando tem, TZ é ambígua). Quando HH real chegar,
                # played_at canónico vem do parser.
                played_at_extracted = None
                screenshot_url_val = None
                if is_discord:
                    og_url = (file_meta or {}).get("og_image_url")
                    if og_url:
                        import re as _re
                        from datetime import datetime as _dt, timezone as _tz
                        m = _re.search(r"/(\d{13})\.png", og_url)
                        if m:
                            try:
                                ts_ms = int(m.group(1))
                                # pt51: unix-ms é UTC → grava em Lisboa naive.
                                played_at_extracted = utc_to_lisbon_naive(_dt.fromtimestamp(ts_ms / 1000, tz=_tz.utc))
                            except (ValueError, OSError):
                                pass
                    screenshot_url_val = og_url

                # Defensiva: se a data extraída via og:image é <2026, abortar
                # criação do placeholder. Discord bot já filtra `_save_to_db`
                # mas placeholders podem vir de paths admin ou reprocessing.
                if is_pre_2026(played_at_extracted):
                    logger.warning(f"[placeholder] Rejeitado entry {entry_id}: played_at={played_at_extracted} <2026")
                    return

                # discord_tags: Discord resolve canal; upload manual fica vazio.
                channel_bruto_list = []
                if is_discord:
                    from app.discord_bot import _resolve_channel_name_for_entry
                    channel_name = _resolve_channel_name_for_entry(entry_id)
                    if channel_name:
                        channel_bruto_list = [channel_name]

                # Valores parametrizados por origem
                origin_val = "discord" if is_discord else "ss_upload"
                tags_val = [] if is_discord else ["SSMatch"]
                hm3_tags_val = ["GGDiscord"] if is_discord else []
                notes_val = (
                    f"Discord SS sem HH ainda. TM: {tm_final}"
                    if is_discord
                    else f"SS upload sem HH. TM: {tm_final}"
                )

                conn = get_conn()
                try:
                    with conn.cursor() as cur:
                        cur.execute(
                            """INSERT INTO hands
                               (site, hand_id, played_at, notes, tags, hm3_tags,
                                entry_id, study_state, screenshot_url,
                                all_players_actions, player_names,
                                origin, discord_tags)
                               VALUES ('GGPoker', %s, %s, %s, %s, %s, %s, 'new', %s,
                                       %s::jsonb, %s::jsonb,
                                       %s, %s::text[])
                               ON CONFLICT (hand_id) DO NOTHING""",
                            (
                                hand_id,
                                played_at_extracted,
                                notes_val,
                                tags_val,
                                hm3_tags_val,
                                entry_id,
                                screenshot_url_val,
                                json.dumps(apa),
                                json.dumps(pn_json),
                                origin_val,
                                channel_bruto_list,
                            )
                        )
                        logger.info(
                            f"[bg] Created {origin_val} placeholder for entry {entry_id} "
                            f"({hand_id}, played_at={played_at_extracted})"
                        )
                        # Marcar entry resolved — placeholder criado (ou já existia
                        # via ON CONFLICT DO NOTHING). Em ambos os casos a entry
                        # passa a estar "coberta" por uma hand com este hand_id.
                        # Consistente com _link_second_discord_entry_to_existing_hand
                        # e _enrich_hand_from_orphan_entry, que também marcam resolved.
                        cur.execute(
                            "UPDATE entries SET status = 'resolved' WHERE id = %s",
                            (entry_id,),
                        )
                    conn.commit()
                except Exception as e:
                    conn.rollback()
                    logger.error(f"[bg] Failed to create {origin_val} placeholder: {e}")
                finally:
                    conn.close()

            await asyncio.to_thread(_create_placeholder_if_needed)

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

    # Barreira pre-2026: filename com data clara <2026 rejeita upload.
    # Filename sem data (ex: peco1.png) passa — placeholder com played_at=None aceito.
    fm_date = file_meta.get("date")
    fm_time = (file_meta.get("time") or "00:00") if file_meta else "00:00"
    if fm_date:
        try:
            from datetime import datetime as _dt, timezone as _tz
            ss_dt = _dt.fromisoformat(f"{fm_date}T{fm_time}").replace(tzinfo=_tz.utc)
            if is_pre_2026(ss_dt):
                logger.warning(f"[ss-upload] Rejeitado {filename}: played_at={ss_dt} <2026")
                raise HTTPException(status_code=400, detail=f"Screenshot rejeitado: data {fm_date} é anterior a 2026.")
        except (ValueError, TypeError):
            pass  # parse fail → deixa passar (filename ambíguo não bloqueia)

    # Dedup server-side por file_hash (espelho do table_ss_processing_log): correr
    # a via de pasta (appimport) outra vez sobre a MESMA gold image NÃO cria um
    # entry novo nem re-dispara Vision. Hash do conteúdo ORIGINAL.
    import hashlib
    file_hash = hashlib.sha256(content).hexdigest()
    dup = query(
        "SELECT id FROM entries WHERE entry_type = 'screenshot' "
        "AND raw_json->>'file_hash' = %s ORDER BY id LIMIT 1",
        (file_hash,),
    )
    if dup:
        eid = dup[0]["id"]
        logger.info(f"[ss-upload] dedup file_hash={file_hash[:12]}… → entry {eid} (skip)")
        return {
            "status": "duplicate",
            "tm_number": tm_number,
            "file_meta": file_meta,
            "message": "Screenshot já importado (dedup file_hash) — sem novo entry.",
            "entry_id": eid,
        }

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
                        "file_hash": file_hash,
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


def _enrich_hand_from_orphan_entry(entry_id: int, hand_db_id: int, raw_json: dict,
                                   force: bool = False) -> dict:
    """
    Dado um entry de screenshot e o id da mão na BD,
    aplica o enriquecimento completo (nomes reais, bounty, country)
    e preenche campos básicos da mão a partir dos dados Vision.
    Marca o entry como 'resolved'.

    force=True (pt-crown): em mãos JÁ enriquecidas (que caem no guard de
    idempotência), refresca a metadata por-jogador (bounty_value_usd / bounty_pct /
    country) em player_names.players_list a partir da nova leitura Vision, SEM
    re-derivar o anon_map nem o apa. Usado pelo backfill de coroa (prompt novo).
    """
    hero_name = raw_json.get("hero")
    file_meta = raw_json.get("file_meta", {})
    screenshot_url = raw_json.get("screenshot_url")

    hand_rows = query(
        "SELECT id, hand_id, all_players_actions, position, raw, stakes, hero_cards, board, player_names FROM hands WHERE id = %s",
        (hand_db_id,)
    )
    if not hand_rows:
        return {"status": "hand_not_found"}

    matched_hand = dict(hand_rows[0])
    all_players_raw = matched_hand.get("all_players_actions") or {}

    # Tech Debt #21: idempotência. Se hand já foi enriched (match_method=
    # anchors_stack_elimination_v2 + raw populado), pular re-execução.
    # Sem este guard, _build_anon_to_real_map trabalha com apa pós-enrich
    # (keys=nicks em vez de hashes) e produz mapping divergente, criando
    # villains stale em hand_villains a cada re-corrida do auto-rematch
    # loop em import_.py:411.
    pn_existing = matched_hand.get("player_names") or {}
    if isinstance(pn_existing, str):
        try:
            pn_existing = json.loads(pn_existing)
        except (ValueError, TypeError):
            pn_existing = {}
    existing_mm = (
        pn_existing.get("match_method") if isinstance(pn_existing, dict) else None
    )
    existing_anon_map = (
        pn_existing.get("anon_map") if isinstance(pn_existing, dict) else None
    )
    raw_already_present = bool((matched_hand.get("raw") or "").strip())
    # Fix #B32: guard idempotência exige anon_map populado para considerar
    # enrich completo. Sem isto, hands com match_method='v2' mas anon_map={}
    # (estado degenerate causado por enrich correr quando apa só tinha _meta)
    # ficavam presas — re-enrich nunca corria, apa permanecia com hashes.
    # SELO DE NOMES (invariante do Rui): uma mão VERIFICADA à mão (verified_by_user)
    # NUNCA é re-derivada por este caminho Gold — era o ghost (c) da reincidência
    # tipo-6570-com-nomes (GG-6177132682): após o /set-anon-map a mão fica
    # match_method='table_ss', que NÃO estava neste guard → o re-link Gold re-derivava
    # position_v3 e pisava a correção. Verified entra no guard (preserva nomes; tags/bounty
    # continuam a refrescar abaixo).
    _is_verified = bool(isinstance(pn_existing, dict) and pn_existing.get("verified_by_user"))
    if (_is_verified or (existing_mm in ("anchors_stack_elimination_v2", POSITION_V3_MATCH_METHOD)
            and raw_already_present
            and existing_anon_map)):
        # apa já enriquecido → NÃO re-corre o algoritmo v2 caro (anon_map). MAS
        # continua a fazer as duas coisas que NÃO dependem do re-enrich, senão
        # perdem-se silenciosamente quando uma 2ª/3ª entry da MESMA mão (mesma
        # mão partilhada em vários canais Discord) cai neste guard
        # (#VILLAIN-MISSED-ON-ENRICH-GUARD):
        #   (1) apensar a discord_tag DESTE entry — sem isto a tag do 2º canal
        #       (ex.: pos-pko / icm-pko) nunca chega à mão.
        #   (2) re-correr apply_villain_rules (idempotente) contra as
        #       discord_tags ACTUAIS — sem isto, tags que chegam depois do 1º
        #       enrich (ex.: 'nota' de outro canal) nunca disparam a Regra C →
        #       villain perdido. O loop de auto-rematch (import_.py) re-corre
        #       por mão em cada import, por isso isto torna o fix self-healing
        #       nos re-imports da fase 2/3.
        from app.discord_bot import _resolve_channel_name_for_entry
        conn = get_conn()
        try:
            with conn.cursor() as cur:
                _ch = _resolve_channel_name_for_entry(entry_id)
                if _ch:
                    cur.execute(
                        "UPDATE hands SET discord_tags = ARRAY(SELECT DISTINCT unnest("
                        "COALESCE(discord_tags, '{}'::text[]) || %s::text[])) WHERE id = %s",
                        ([_ch], hand_db_id),
                    )
                cur.execute(
                    "UPDATE entries SET status = 'resolved' WHERE id = %s",
                    (entry_id,),
                )
                # pt-crown: refresh da metadata por-jogador (coroa/bounty/vpip/país)
                # a partir da nova leitura Vision, SEM tocar anon_map/apa/match_method.
                # Faz o backfill de coroa funcionar nas mãos já enriquecidas.
                if force:
                    from app.services.eliminated_bounty import is_bounty_sealed
                    fresh_by_name = {}
                    for fp in (raw_json.get("players_list") or []):
                        if isinstance(fp, dict):
                            nm = (fp.get("name") or "").strip().lower()
                            if nm:
                                fresh_by_name[nm] = fp
                    pl = pn_existing.get("players_list") or []
                    changed = False
                    for p in pl:
                        if not isinstance(p, dict):
                            continue
                        fp = fresh_by_name.get((p.get("name") or "").strip().lower())
                        if not fp:
                            continue
                        # SELO — a coroa validada não é reescrita pela re-Vision (país/VPIP sim).
                        _sealed = is_bounty_sealed(p)
                        for k in ("bounty_value_usd", "bounty_pct", "country"):
                            if k == "bounty_value_usd" and _sealed:
                                continue
                            if fp.get(k) is not None:
                                p[k] = fp.get(k)
                        changed = True
                    if changed:
                        pn_existing["players_list"] = pl
                        cur.execute(
                            "UPDATE hands SET player_names = %s WHERE id = %s",
                            (json.dumps(pn_existing), hand_db_id),
                        )
            conn.commit()
        finally:
            conn.close()
        try:
            from app.services.villain_rules import apply_villain_rules
            apply_villain_rules(hand_db_id)  # idempotente; lê discord_tags actuais
        except Exception as e:
            logger.error(
                f"Villain creation (already_enriched guard) failed hand {hand_db_id}: {e}"
            )
        return {
            "status": "already_enriched",
            "hand_id": hand_db_id,
            "players_mapped": 0,
            "anon_map": {},
        }

    # #B-NOVO-2: assert defensivo. _build_anon_to_real_map retorna {} silently
    # quando apa só tem _meta (placeholder Discord pré-HH) — era a precondição
    # do bug #B32. Hoje #B32 cobre set+guard; chegar aqui com apa placeholder-
    # only é sinal de bug upstream. Falha explícita > silent skip.
    if not [k for k in (all_players_raw or {}) if k != "_meta"]:
        raise ValueError(
            f"_enrich_hand_from_orphan_entry: hand_db_id={hand_db_id} apa "
            f"placeholder-only (só _meta) — bug upstream, não devia chegar aqui."
        )

    # Desanon POR MÃO (pt-pos):
    #  • Se a gold image trouxe SIGLAS de posição (descarga completa GG, lidas
    #    do log de acção), usa o mapa por POSIÇÃO (position_v3) — robusto, sem
    #    aritmética de stack.
    #  • Caso contrário (sem siglas), cai no stack-elimination legacy
    #    (anchors_stack_elimination_v2).
    # ⚠️ O fallback é POR MÃO. Dentro de uma mão com gold image NUNCA se preenche
    # por stack uma lacuna honesta do position_v3: um seat sem sigla fica por
    # mapear (o hash mantém-se). Não se mistura os dois caminhos na mesma mão.
    _has_positions = any(
        (p or {}).get("position") for p in (raw_json.get("players_list") or [])
    )
    # A ORDEM NÃO PODE IMPORTAR: no match DIRECTO (HH antes da imagem) o caller
    # passa o players_list fresco da Vision (com posições) → position_v3. No
    # RE-LINK (imagem antes da HH) alguns callers passam um raw_json que perdeu
    # as posições → caía no stack. Robustez caller-agnóstica: se o raw_json
    # recebido não traz posições mas o ENTRY guardado tem (gold image já com
    # Vision feita), recupera-as do entry e usa position_v3 — mesmo resultado
    # que o directo. Entries SEM posições (table-SS, replayer antigo) ficam como
    # estão → stack-elimination intacto.
    if not _has_positions:
        try:
            _erow = query("SELECT raw_json FROM entries WHERE id = %s", (entry_id,))
            _erj = (_erow[0].get("raw_json") if _erow else None) or {}
            if isinstance(_erj, str):
                _erj = json.loads(_erj)
            _epl = _erj.get("players_list") or []
            if any((p or {}).get("position") for p in _epl):
                raw_json = {
                    **raw_json,
                    "players_list": _epl,
                    "hero": raw_json.get("hero") or _erj.get("hero"),
                    "vision_sb": raw_json.get("vision_sb") or _erj.get("vision_sb"),
                    "vision_bb": raw_json.get("vision_bb") or _erj.get("vision_bb"),
                }
                hero_name = hero_name or _erj.get("hero")
                _has_positions = True
        except Exception as _e:
            logger.warning(f"[pos-v3] recover positions from entry {entry_id} falhou: {_e}")
    if _has_positions:
        anon_map = _build_anon_to_real_map_by_position(matched_hand, raw_json)["anon_map"]
        _used_position_v3 = True
    else:
        anon_map = _build_anon_to_real_map(matched_hand, raw_json)
        _used_position_v3 = False
    _tn_guard = matched_hand.get("tournament_number")
    enriched_actions = _enrich_all_players_actions(all_players_raw, anon_map, raw_json, tn=_tn_guard)

    # Guarda UNIVERSAL de consistência (#DESANON-SITTING-OUT-NPLUS1): position_v3 (por rótulo)
    # isento do C3; o fallback stack (por ordem) está sujeito. block → mantém a mão ANÓNIMA
    # (não escreve nomes deslizados/injetados — branco > errado).
    from app.services.table_ss_deanon import assert_deanon_consistency
    _cl, _cv = assert_deanon_consistency(
        matched_hand.get("raw"), enriched_actions, anon_map,
        vision_seat_count=len(raw_json.get("players_list") or []),
        by_order=not _used_position_v3)
    if _cl == "block":
        logger.warning("[pos-v3] hand %s CONSISTÊNCIA=%s → fica ANÓNIMA (não escreve nomes)",
                       hand_db_id, _cv)
        anon_map = {}
        enriched_actions = _enrich_all_players_actions(all_players_raw, {}, raw_json, tn=_tn_guard)

    # match_method só sobe a 'anchors_stack_elimination_v2' quando há HH real
    # (raw populado). Sem HH, a hand continua a ser placeholder mesmo após
    # 2ª entry Discord cruzar nicks via Vision — anteriormente este path
    # promovia incondicionalmente, criando 25 mãos com etiqueta de match
    # completo mas sem raw, que escapavam ao filtro de Estudo.
    has_real_hh = bool((matched_hand.get("raw") or "").strip())
    pn_old = matched_hand.get("player_names") or {}
    if isinstance(pn_old, str):
        try:
            pn_old = json.loads(pn_old)
        except (ValueError, TypeError):
            pn_old = {}
    # Fix #B32: só promover a match_method='v2' quando anon_map foi de facto
    # produzido. _build_anon_to_real_map devolve {} quando apa só tem _meta
    # (placeholder Discord, antes do parse completar). Gravar 'v2' nesse caso
    # é falso positivo: o guard idempotência depois fecha a porta para re-
    # correr quando apa já foi populada com hashes via outro caminho.
    if has_real_hh and anon_map:
        match_method_value = (
            POSITION_V3_MATCH_METHOD if _used_position_v3
            else "anchors_stack_elimination_v2"
        )
    else:
        # Preservar match_method existente do placeholder (ex:
        # 'discord_placeholder_no_hh' / '_backfill'); fallback ao default
        # se de algum modo estiver vazio.
        match_method_value = (
            (pn_old.get("match_method") if isinstance(pn_old, dict) else None)
            or "discord_placeholder_no_hh"
        )

    player_names_json = {
        "players_list": raw_json.get("players_list", []),
        "hero": hero_name,
        "vision_sb": raw_json.get("vision_sb"),
        "vision_bb": raw_json.get("vision_bb"),
        "anon_map": anon_map,
        "file_meta": file_meta,
        "match_method": match_method_value,
    }

    # Fill basic fields from Vision data if hand is empty
    extra_updates = []
    extra_params = []

    # Tournament name from Vision
    tournament_name = raw_json.get("tournament") or file_meta.get("tournament")
    if tournament_name and not matched_hand.get("stakes"):
        extra_updates.append("stakes = %s")
        extra_params.append(tournament_name)

    # Hero position from Vision SB/BB or from players list
    if not matched_hand.get("position") and hero_name:
        vision_sb = raw_json.get("vision_sb", "")
        vision_bb = raw_json.get("vision_bb", "")
        if hero_name == vision_sb:
            extra_updates.append("position = %s")
            extra_params.append("SB")
        elif hero_name == vision_bb:
            extra_updates.append("position = %s")
            extra_params.append("BB")

    # played_at: NÃO derivar do nome do ficheiro.
    # A data/hora no nome do screenshot GG é o instante do DOWNLOAD, não a
    # hora-de-jogo (ver DESANON_ANATOMIA §2 + `#GG-DOWNLOAD-IMG-FILENAME-TIME-
    # AND-BLINDS-UNRELIABLE`). A hora-de-jogo é matematicamente exacta só na HH;
    # sem HH com played_at, fica NULL — não se inventa do nome do download.

    # Entry ID link
    extra_updates.append("entry_id = %s")
    extra_params.append(entry_id)

    # Study state: promove a 'new' SÓ quando estava 'mtt_archive'.
    # Antes do fix #6 (pt16) este UPDATE forçava 'new' incondicionalmente,
    # causando regressão visual: mãos já marcadas como 'resolved' (Revista
    # pelo Rui) voltavam a 'new' (Nova) sempre que Vision re-corria
    # enrichment para a mesma TM. Agora preserva 'resolved' e 'new'; só
    # promove archive→new (intenção original do comentário).
    extra_updates.append(
        "study_state = CASE WHEN study_state = 'mtt_archive' "
        "THEN 'new' ELSE study_state END"
    )

    # Se a entry veio do Discord, append discord_tags com o nome raw do canal.
    # NAO tocamos em origin nem em tags: a hand ja veio de um path primario
    # (HM3 .bat ou HH import) e so esta a ser enriquecida com dados Vision;
    # preservar origem. discord_tags e' additive metadata (regra C villain).
    from app.discord_bot import _resolve_channel_name_for_entry
    _discord_channel = _resolve_channel_name_for_entry(entry_id)
    if _discord_channel:
        extra_updates.append(
            "discord_tags = ARRAY(SELECT DISTINCT unnest(COALESCE(discord_tags, '{}'::text[]) || %s::text[]))"
        )
        extra_params.append([_discord_channel])

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            update_fields = "player_names = %s, all_players_actions = %s"
            update_params = [json.dumps(player_names_json), json.dumps(enriched_actions)]

            if screenshot_url:
                update_fields += ", screenshot_url = %s"
                update_params.append(screenshot_url)

            if extra_updates:
                update_fields += ", " + ", ".join(extra_updates)
                update_params.extend(extra_params)

            update_params.append(hand_db_id)
            cur.execute(
                f"UPDATE hands SET {update_fields} WHERE id = %s",
                tuple(update_params)
            )
            cur.execute("UPDATE entries SET status = 'resolved' WHERE id = %s", (entry_id,))
        conn.commit()
        logger.info(f"Enriched hand {hand_db_id} from entry {entry_id}: {len(anon_map)} mappings, extras: {len(extra_updates)}")
    except Exception as e:
        conn.rollback()
        logger.error(f"Error enriching hand {hand_db_id} from entry {entry_id}: {e}")
        return {"status": "error", "error": str(e)}
    finally:
        conn.close()

    # ONDA 1 #B23 refactor: substitui _create_ggpoker_villain_notes_for_hand
    # pela função canónica única apply_villain_rules (services/villain_rules.py).
    # Lê tudo de hands (apa enriched + player_names JSON) e aplica A∨C∨D.
    # Função abre conn própria; falha aqui não bloqueia enrich — só log error.
    try:
        from app.services.villain_rules import apply_villain_rules
        result = apply_villain_rules(hand_db_id)
        logger.info(
            f"Villain creation hand {hand_db_id}: "
            f"{result['n_villains_created']} villains, "
            f"{result['n_villain_notes_upserts']} notes"
            + (f" (skipped: {result['skipped_reason']})" if result.get('skipped_reason') else "")
        )
    except Exception as e:
        logger.error(f"Villain creation error for hand {hand_db_id}: {e}")

    return {
        "status": "enriched",
        "hand_id": hand_db_id,
        "players_mapped": len([k for k, v in anon_map.items() if k != "Hero"]),
        "anon_map": anon_map,
    }


@router.post("/orphans/{entry_id}/relink")
def force_relink_orphan(entry_id: int, current_user=Depends(require_auth_or_api_key)):
    """Força o re-link Gold (`_enrich_hand_from_orphan_entry`) de UMA entry screenshot já
    LIGADA à sua mão — INDEPENDENTE do status (o `/rematch` só apanha órfãs `status='new'`).
    Idempotente; RESPEITA o SELO (uma mão `verified_by_user` NÃO é re-derivada, guard
    screenshot.py:1701). Maintenance + prova do ghost (c) do selo de nomes. Bearer.
    Body: nenhum (entry_id no path)."""
    rows = query("SELECT id, raw_json FROM entries WHERE id=%s AND entry_type='screenshot'",
                 (entry_id,))
    if not rows:
        raise HTTPException(404, "entry screenshot não encontrada")
    raw = rows[0].get("raw_json") or {}
    hrows = query("SELECT id, hand_id FROM hands WHERE entry_id=%s LIMIT 1", (entry_id,))
    if not hrows:
        tm = (raw.get("tm") or "").replace("TM", "")
        if tm:
            hrows = query("SELECT id, hand_id FROM hands WHERE hand_id=%s LIMIT 1", (f"GG-{tm}",))
    if not hrows:
        return {"status": "no_hand", "entry_id": entry_id}
    result = _enrich_hand_from_orphan_entry(entry_id, hrows[0]["id"], raw)
    return {"status": result.get("status", "relinked"), "entry_id": entry_id,
            "hand_id": hrows[0]["hand_id"], "result": result}


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


# ── Cleanup: apagar SS órfãos de mãos anteriores a 2026 ─────────────────────

@router.get("/cleanup-before-2026/preview")
def cleanup_before_2026_preview(current_user=Depends(require_auth)):
    """
    Preview: devolve contagem e amostra dos SS órfãos cuja data da mão
    (raw_json.file_meta.date) é anterior a 2026-01-01.
    Não apaga nada.
    """
    count_rows = query(
        """
        SELECT COUNT(*) AS n FROM entries
        WHERE entry_type = 'screenshot'
          AND status = 'new'
          AND (raw_json->'file_meta'->>'date') < '2026-01-01'
        """
    )
    count = count_rows[0]["n"] if count_rows else 0

    sample_rows = query(
        """
        SELECT id, file_name,
               raw_json->'file_meta'->>'date' AS data_mao,
               raw_json->>'tm' AS tm
        FROM entries
        WHERE entry_type = 'screenshot'
          AND status = 'new'
          AND (raw_json->'file_meta'->>'date') < '2026-01-01'
        ORDER BY (raw_json->'file_meta'->>'date') DESC
        LIMIT 10
        """
    )
    return {
        "count": count,
        "sample": [dict(r) for r in sample_rows],
    }


@router.post("/cleanup-before-2026")
def cleanup_before_2026(current_user=Depends(require_auth)):
    """
    Apaga todos os SS órfãos (status='new') cuja data da mão é anterior a 2026-01-01.
    Irreversível.
    """
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                DELETE FROM entries
                WHERE entry_type = 'screenshot'
                  AND status = 'new'
                  AND (raw_json->'file_meta'->>'date') < '2026-01-01'
                RETURNING id
                """
            )
            deleted_ids = [r["id"] for r in cur.fetchall()]
        conn.commit()
        logger.info(f"[cleanup-before-2026] Deleted {len(deleted_ids)} orphan screenshots")
        return {
            "deleted": len(deleted_ids),
            "deleted_ids": deleted_ids[:50],  # amostra
        }
    except Exception as e:
        conn.rollback()
        logger.error(f"[cleanup-before-2026] Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()


# ── Servir imagem de um entry de screenshot ────────────────────────────────

@router.get("/image/{entry_id}")
def get_screenshot_image(entry_id: int, current_user=Depends(require_auth)):
    """
    Devolve a imagem guardada em entries.raw_json.img_b64 como binário
    (image/jpeg ou image/png). Permite abrir em nova tab sem limites de data: URIs.

    #REPLAYER-IMG-HH-FIRST (pt46): serve SS manual (entry_type='screenshot')
    E replayer GG (entry_type='replayer_link', cujo img_b64 é a imagem captada
    do replayer). Antes só 'screenshot' -> mãos HH-primeiro ficavam sem imagem
    apesar dos bytes estarem em BD.
    """
    rows = query(
        "SELECT raw_json FROM entries WHERE id = %s "
        "AND entry_type IN ('screenshot', 'replayer_link')",
        (entry_id,)
    )
    if not rows:
        raise HTTPException(status_code=404, detail="Screenshot não encontrado")

    raw = rows[0].get("raw_json") or {}
    img_b64 = raw.get("img_b64")
    if not img_b64:
        raise HTTPException(status_code=404, detail="Imagem não disponível neste entry")

    mime = raw.get("mime_type", "image/jpeg")
    try:
        img_bytes = base64.b64decode(img_b64)
    except Exception as e:
        logger.error(f"Failed to decode image for entry {entry_id}: {e}")
        raise HTTPException(status_code=500, detail="Erro ao descodificar imagem")

    return Response(
        content=img_bytes,
        media_type=mime,
        headers={
            "Cache-Control": "private, max-age=3600",
            "Content-Disposition": f'inline; filename="screenshot_{entry_id}.jpg"',
        },
    )


def _serve_img_b64(raw_json, entry_id_for_name) -> Response:
    """Descodifica img_b64 de um raw_json e serve como binário. 404 se ausente."""
    raw = raw_json or {}
    img_b64 = raw.get("img_b64")
    if not img_b64:
        raise HTTPException(status_code=404, detail="Imagem não disponível")
    mime = raw.get("mime_type", "image/jpeg")
    try:
        img_bytes = base64.b64decode(img_b64)
    except Exception as e:
        logger.error(f"Failed to decode image entry {entry_id_for_name}: {e}")
        raise HTTPException(status_code=500, detail="Erro ao descodificar imagem")
    return Response(content=img_bytes, media_type=mime,
                    headers={"Cache-Control": "private, max-age=3600",
                             "Content-Disposition": f'inline; filename="hand_{entry_id_for_name}.jpg"'})


@router.get("/hand-image/{hand_db_id}")
def get_hand_image(hand_db_id: int, current_user=Depends(require_auth_or_api_key)):
    """Serve a imagem da LEITURA de UMA mão, resolvendo a fonte SERVER-SIDE — os painéis passam
    `hand_db_id` e NUNCA adivinham qual capture tem a imagem (a doença recorrente: `h.entry_id`
    aponta muitas vezes ao entry `hand_history`, sem img_b64 → 404 → imagem partida). As coroas
    GG lêem-se de DUAS origens: a GOLD (entry screenshot/replayer_link) E o print de MESA do IT
    (`table_ss_processing_log.img_b64`, via `hands.context_table_ss_id`). Ordem:
    (1) `h.entry_id` se for screenshot/replayer_link com img_b64; (2) entry screenshot/replayer
    do MESMO tm; (3) **o print table-SS da mão** (a leitura por-testemunha vive AQUI, não em
    `entries` — era o buraco: mãos table_ss-deanon davam 404 com a imagem a existir). 404 só se
    NENHUMA fonte tiver imagem. Bearer|cookie."""
    rows = query(
        "SELECT e.raw_json FROM hands h JOIN entries e ON e.id = h.entry_id "
        " WHERE h.id = %s AND e.entry_type IN ('screenshot','replayer_link') "
        "   AND (e.raw_json->>'img_b64') IS NOT NULL", (hand_db_id,))
    if not rows:
        rows = query(
            "SELECT e.raw_json FROM hands h "
            "  JOIN entries e ON e.entry_type IN ('screenshot','replayer_link') "
            "   AND (e.raw_json->>'img_b64') IS NOT NULL "
            "   AND replace(e.raw_json->>'tm','TM','') = replace(h.hand_id,'GG-','') "
            " WHERE h.id = %s ORDER BY e.id DESC LIMIT 1", (hand_db_id,))
    if rows:
        return _serve_img_b64(rows[0].get("raw_json"), f"hand{hand_db_id}")
    # (3) print table-SS da mão (a imagem da leitura por-testemunha)
    tss = query(
        "SELECT l.img_b64 FROM hands h JOIN table_ss_processing_log l "
        "  ON l.id = h.context_table_ss_id "
        " WHERE h.id = %s AND l.img_b64 IS NOT NULL", (hand_db_id,))
    if tss:
        return _serve_img_b64({"img_b64": tss[0]["img_b64"], "mime_type": "image/jpeg"},
                              f"tss_hand{hand_db_id}")
    raise HTTPException(status_code=404, detail="Sem imagem para esta mão")


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


# ── #GOLD-BOUNTY-CARRY — backfill das coroas nas mãos Gold (position_v3) ──────
def backfill_gold_bounties(dry_run: bool = False) -> dict:
    """Preenche as coroas ($ bounty) nas mãos GG desanon pela GOLD (position_v3)
    que ficaram sem elas: copia `bounty_value_usd` do `players_list` do ENTRY da
    Gold para o `all_players_actions` da mão. Reusa o entry guardado → 0 Vision.

    Guarda half-base: coroa < base÷2 (base = tournament_summaries.buy_in_bounty)
    → NÃO escreve (provável leitura errada). Hero com coroa 0 → salta (frente à
    parte). Não toca nos NOMES (Gold manda) — só adiciona a coroa por jogador.
    dry_run=True → não escreve, devolve o plano."""
    from psycopg2.extras import Json
    base_rows = query("SELECT tournament_number, buy_in_bounty FROM tournament_summaries "
                      "WHERE site='GGPoker' AND buy_in_bounty IS NOT NULL")
    base_by_tn = {r["tournament_number"]: float(r["buy_in_bounty"]) for r in base_rows}

    rows = query("""SELECT h.id, h.hand_id, h.tournament_number, h.all_players_actions,
                           e.raw_json->'players_list' AS entry_players
                      FROM hands h JOIN entries e ON e.id = h.entry_id
                     WHERE h.site='GGPoker' AND h.played_at >= '2026-01-01'
                       AND h.player_names->>'match_method' = 'position_v3'""")
    hands_filled = players_filled = players_rejected = no_base = 0
    players_via_trunc = players_ambiguous_trunc = players_overwritten = 0
    for r in rows:
        apa = r["all_players_actions"]
        if not isinstance(apa, dict):
            continue
        crowns = {}
        for p in (r["entry_players"] or []):
            if isinstance(p, dict) and p.get("name"):
                crowns[p["name"].lower()] = p.get("bounty_value_usd")
        base = base_by_tn.get(r["tournament_number"])
        floor = base / 2 if base else None
        if base is None:
            no_base += 1
        changed = False
        for key, pdata in apa.items():
            if key == "_meta" or not isinstance(pdata, dict):
                continue
            name = (pdata.get("real_name") or key).lower()
            crown = crowns.get(name) or crowns.get(key.lower())
            via_trunc = False
            # #GOLD-CROWN-CARRY-NAME-TRUNCATION: se o nome exato está AUSENTE (apa
            # completo vs Gold truncado), casa por _same_player. Só quando ausente
            # → protege o Hero-a-0 (nome presente com coroa 0) e as já-preenchidas.
            if (not crown or crown <= 0) and name not in crowns and key.lower() not in crowns:
                uniq = {crowns[g] for g in crowns
                        if crowns.get(g) and crowns[g] > 0 and _same_player(name, g)}
                if len(uniq) == 1:
                    crown = uniq.pop()
                    via_trunc = True
                elif len(uniq) > 1:
                    players_ambiguous_trunc += 1   # truncagem ambígua → NÃO escreve
            if not crown or crown <= 0:
                continue                       # sem coroa / Hero-a-0 → salta
            if floor is not None and crown < floor:
                players_rejected += 1          # < base÷2 → mal lida, NÃO escreve
                continue
            prior = pdata.get("bounty_value_usd")
            if prior != crown:
                if prior and prior > 0:
                    players_overwritten += 1   # já-preenchida a mudar (deve ser 0)
                pdata["bounty_value_usd"] = crown
                players_filled += 1
                if via_trunc:
                    players_via_trunc += 1
                changed = True
        if changed:
            hands_filled += 1
            if not dry_run:
                conn = get_conn()
                try:
                    with conn.cursor() as cur:
                        cur.execute("UPDATE hands SET all_players_actions=%s WHERE id=%s",
                                    (Json(apa), r["id"]))
                    conn.commit()
                finally:
                    conn.close()
        if not dry_run:
            # Cura verde-KO (família B): a gold-carry pode carregar a coroa do vizinho para
            # um seat HH-bustado → o funil anula-a (sem verde aqui → MUST-only). Só-tagadas.
            try:
                from app.services.eliminated_bounty import scrub_and_persist
                scrub_and_persist(r["id"])
            except Exception as e:  # pragma: no cover - defensivo
                logger.error("[crown-cure] ⚠️ GUARD FALHOU (gold-carry) hand %s — coroa de bustado pode "
                             "SOBREVIVER (o crivo apanha): %s", r["hand_id"], e)
    return {"hands_scanned": len(rows), "hands_filled": hands_filled,
            "players_filled": players_filled,
            "players_via_truncation": players_via_trunc,
            "players_ambiguous_truncation": players_ambiguous_trunc,
            "players_overwritten_already_filled": players_overwritten,
            "players_rejected_below_half": players_rejected,
            "hands_without_ts_base": no_base}


@router.post("/backfill-gold-bounties")
def trigger_backfill_gold_bounties(dry_run: bool = False,
                                   current_user=Depends(require_auth_or_api_key)):
    """#GOLD-BOUNTY-CARRY — preenche as coroas das mãos Gold (position_v3) a partir
    do entry da Gold, com guarda half-base. `dry_run=true` → não escreve. Sem Vision."""
    return backfill_gold_bounties(dry_run=dry_run)


# ── #CROWN-VISIBLE-READ-ZERO (Opção C, parte 2) — re-leitura das coroas do GOLD ──
def _crown_from_fresh(name, fresh):
    n = (name or "").lower().strip().rstrip(".")
    if n in fresh:
        return fresh[n]
    cand = {v for k, v in fresh.items() if _same_player(n, k)}   # truncagem
    return cand.pop() if len(cand) == 1 else None


async def reread_gold_crowns(hand_ids=None, dry_run: bool = True, limit: int = 30) -> dict:
    """Re-lê as coroas nas mãos GG desanon por GOLD (`position_v3`) que ficaram com $0,
    re-correndo a Vision do GOLD sobre a imagem GUARDADA do entry (prompt afinado: ler a
    coroa mesmo com o avatar tapado). Atualiza SÓ coroas $0 onde a nova leitura é VÁLIDA
    (>0 e ≥ base÷2). NÃO toca nomes (regra: Gold manda, $0 não é leitura). Escreve apa +
    player_names. Vision OFF-THREAD. `hand_ids` limita ao teste (2-3); senão todas as $0."""
    import asyncio
    from psycopg2.extras import Json
    base_by_tn = {r["tournament_number"]: float(r["buy_in_bounty"]) for r in query(
        "SELECT tournament_number, buy_in_bounty FROM tournament_summaries "
        "WHERE site='GGPoker' AND buy_in_bounty IS NOT NULL")}
    where = "AND h.hand_id = ANY(%s)" if hand_ids else ""
    params = (hand_ids,) if hand_ids else tuple()
    rows = query(
        "SELECT h.id, h.hand_id, h.tournament_number, h.all_players_actions AS apa, "
        "       h.player_names AS pn, e.raw_json->>'img_b64' AS img "
        "  FROM hands h JOIN entries e ON e.id = h.entry_id "
        " WHERE h.site='GGPoker' AND h.played_at >= '2026-01-01' "
        "   AND h.player_names->>'match_method' = 'position_v3' "
        "   AND e.raw_json->>'img_b64' IS NOT NULL "
        # #CROWN-VISIBLE-READ-ZERO: SÓ torneios COM bounty. Uma coroa $0 num
        # torneio vanilla é INEXISTENTE (não há bounty), não 'por ler' — alinha
        # com o gate da secção Mãos suspeitas (suspicious._bounty_below_half_hands).
        "   AND EXISTS (SELECT 1 FROM tournament_summaries ts "
        "                WHERE ts.site='GGPoker' "
        "                  AND ts.tournament_number = h.tournament_number "
        "                  AND ts.buy_in_bounty > 0) " + where,
        params,
    )

    def _has_zero(pn):
        return isinstance(pn, dict) and any(
            (p.get("bounty_value_usd") or 0) <= 0
            for p in (pn.get("players_list") or []) if isinstance(p, dict))

    targets = [r for r in rows if _has_zero(r["pn"])][:limit]
    hands_updated = crowns_recovered = vision_failed = 0
    report = []
    for r in targets:
        b = r["img"] or ""
        if "," in b[:40]:
            b = b.split(",", 1)[1]
        try:
            img = base64.b64decode(b)
        except Exception:
            continue
        # As imagens GUARDADAS são JPEG comprimido (1280/JPEG85) — declarar
        # o mime real; a Anthropic rejeita 400 se media_type≠magic (#CROWN-VISIBLE-READ-ZERO).
        from app.services.image_utils import detect_image_mime
        mime = detect_image_mime(img)
        text = await asyncio.to_thread(_extract_hand_data_from_image_claude, img, mime)
        if not text:
            vision_failed += 1
            report.append({"hand_id": r["hand_id"], "result": "vision_failed"})
            continue
        vd = _parse_vision_response(text)
        fresh = {}
        for p in (vd.get("players_list") or []):
            nm = (p.get("name") or "").lower().strip()
            bv = p.get("bounty_value_usd")
            if nm and bv and float(bv) > 0:
                fresh[nm] = float(bv)
        base = base_by_tn.get(r["tournament_number"])
        floor = base / 2 if base else None
        apa, pn = r["apa"], r["pn"]
        changed = False
        recov = 0
        recov_detail = []  # #CROWN-VISIBLE-READ-ZERO: auditoria — o que a Vision leu.
        if isinstance(apa, dict):
            for key, pdata in apa.items():
                if key == "_meta" or not isinstance(pdata, dict):
                    continue
                if (pdata.get("bounty_value_usd") or 0) > 0:
                    continue
                nm = pdata.get("real_name") or key
                cr = _crown_from_fresh(nm, fresh)
                if cr is None or (floor is not None and cr < floor):
                    continue
                pdata["bounty_value_usd"] = cr
                changed = True
                recov += 1
                recov_detail.append({"name": nm, "from": 0.0, "to": cr,
                                     "floor": floor, "base": base})
        if isinstance(pn, dict):
            for p in (pn.get("players_list") or []):
                if not isinstance(p, dict) or (p.get("bounty_value_usd") or 0) > 0:
                    continue
                cr = _crown_from_fresh(p.get("name"), fresh)
                if cr is None or (floor is not None and cr < floor):
                    continue
                p["bounty_value_usd"] = cr
                changed = True
        report.append({"hand_id": r["hand_id"], "recovered": recov,
                       "crowns": recov_detail})
        if changed:
            hands_updated += 1
            crowns_recovered += recov
            if not dry_run:
                conn = get_conn()
                try:
                    with conn.cursor() as cur:
                        cur.execute("UPDATE hands SET all_players_actions=%s, player_names=%s WHERE id=%s",
                                    (Json(apa), Json(pn), r["id"]))
                    conn.commit()
                finally:
                    conn.close()
        if not dry_run:
            # ★ Cura verde-KO (família B): garante que nenhum seat HH-bustado fica com uma
            # coroa de origem-Vision (incl. as que o reread ACABOU de preencher) — verde-
            # derivado (vd tem green_kos) ou NULL+'por rever'. Só-tagadas (o wrapper valida).
            # Fecha o caminho que produziu o $170.63.
            try:
                from app.services.eliminated_bounty import scrub_and_persist
                scrub_and_persist(r["id"], vision_data=vd)
            except Exception as e:  # pragma: no cover - defensivo
                logger.error("[crown-cure] ⚠️ GUARD FALHOU (reread) hand %s — coroa de bustado pode "
                             "SOBREVIVER (o crivo apanha): %s", r["hand_id"], e)
    return {"targets": len(targets), "hands_updated": hands_updated,
            "crowns_recovered": crowns_recovered, "vision_failed": vision_failed,
            "report": report}


@router.post("/reread-gold-crowns")
async def trigger_reread_gold_crowns(
    confirm: bool = Query(False),
    hand_ids: Optional[str] = Query(None),
    limit: int = Query(30, ge=1, le=100),
    current_user=Depends(require_auth_or_api_key),
):
    """#CROWN-VISIBLE-READ-ZERO parte 2. `?confirm=false` (default) = ENSAIO (não escreve).
    `hand_ids=GG-a,GG-b` limita ao teste (2-3 mãos). Sem `hand_ids` = todas as Gold com
    coroa $0 (até `limit`). Re-Vision do GOLD com o prompt afinado."""
    ids = [h.strip() for h in hand_ids.split(",") if h.strip()] if hand_ids else None
    return await reread_gold_crowns(hand_ids=ids, dry_run=not confirm, limit=limit)


@router.post("/green-ko-dryrun")
async def green_ko_dryrun(
    hand_ids: Optional[str] = Query(None),
    limit: int = Query(60, ge=1, le=120),
    current_user=Depends(require_auth_or_api_key),
):
    """READ-ONLY (guarantee #2 da cura verde-KO). Para as mãos GG desanon com BUST (HH),
    corre a Vision (prompt novo) na imagem de ESTADO FINAL (Gold) e mede o bónus do verde
    SEM escrever. Separa por tipo de imagem:
      - `gold`: o verde ESTÁ na imagem → reporta verde-lido + bounty derivado ('green_ko')
                ou 'por rever' (verde ilegível).
      - `table_ss_only`/`none`: captura cedo, o verde (no fim) NÃO está → 'por rever' é o
                resultado ESPERADO e correto (não corre Vision — não há onde ler o verde).
    O pass/fail DURO é o crivo=0 (eliminated-crown-scan); isto é só a MEDIDA do bónus."""
    import asyncio
    import copy as _copy
    from app.services.eliminated_bounty import (
        busted_real_names, resolve_seat_bounty, parse_green_kos,
        BOUNTY_REVIEW_KEY, BOUNTY_SOURCE_KEY, SOURCE_GREEN_KO,
    )
    ids = [h.strip() for h in hand_ids.split(",") if h.strip()] if hand_ids else None
    where = "AND h.hand_id = ANY(%s)" if ids else ""
    params = (ids,) if ids else tuple()
    rows = query(
        "SELECT h.id, h.hand_id, h.raw, h.all_players_actions AS apa, h.player_names AS pn, "
        "       e.raw_json->>'img_b64' AS gold_img, "
        "       (h.context_table_ss_id IS NOT NULL) AS has_tss "
        "  FROM hands h LEFT JOIN entries e ON e.id = h.entry_id "
        " WHERE h.site='GGPoker' AND h.played_at >= '2026-01-01' "
        "   AND h.player_names->>'match_method' IS NOT NULL " + where,
        params,
    )
    gold_read = gold_review = tss_only_expected = 0
    report = []
    for r in rows:
        apa = r["apa"] if isinstance(r["apa"], dict) else json.loads(r["apa"] or "{}")
        busted = busted_real_names(r["raw"], apa)
        if not busted:
            continue
        if not r["gold_img"]:
            # sem Gold → o verde não está guardado → 'por rever' esperado (não é falha).
            tss_only_expected += 1
            report.append({"hand_id": r["hand_id"],
                           "image": "table_ss_only" if r["has_tss"] else "none",
                           "busted": sorted(busted), "expected": "por rever"})
            continue
        b = r["gold_img"]
        if "," in b[:40]:
            b = b.split(",", 1)[1]
        try:
            img = base64.b64decode(b)
        except Exception:
            continue
        from app.services.image_utils import detect_image_mime
        text = await asyncio.to_thread(
            _extract_hand_data_from_image_claude, img, detect_image_mime(img))
        greens = parse_green_kos(_parse_vision_response(text)) if text else []
        seats = []
        for name in sorted(busted):
            val, review, source = resolve_seat_bounty(
                name, None, busted_names=busted, green_kos=greens)
            if source == SOURCE_GREEN_KO:
                gold_read += 1
            else:
                gold_review += 1
            seats.append({"name": name, "bounty": val,
                          "source": source, "review": review})
        report.append({"hand_id": r["hand_id"], "image": "gold",
                       "greens_read": greens, "seats": seats})
    return {
        "busted_hands": len(report),
        "gold": {"seats_derived_green": gold_read, "seats_por_rever": gold_review},
        "table_ss_only_hands": tss_only_expected,
        "report": report,
    }


# ── Re-enrich do baralhamento Gold (#DESANON-GOLD-SCRAMBLE) ──────────────────
# As mãos Gold (position_v3) cujo all_players_actions ficou STALE (enriquecido com
# um mapa antigo/errado): nomes trocados de cadeira e/ou vilões largados como hash.
# O anon_map GUARDADO está certo (validado por stack). Reconstrói o apa do RAW
# (recupera os vilões largados) e re-enriquece pelo anon_map+seat + re-carrega as
# coroas da Gold — tudo no mesmo passe. Só escreve as que passam o gate de fichas.

_SS_SEAT_RE = re.compile(r"^Seat (\d+): (.+?) \(([\d,]+) in chips\)", re.M)
_SS_LVL_RE = re.compile(r"Level\s*\d+\s*\(([\d,]+)/([\d,]+)(?:\(([\d,]+)\))?\)")


def _ss_num(s: str) -> float:
    return float(s.replace(",", ""))


def _same_player(a: str, b: str) -> bool:
    """True se a e b são o MESMO jogador módulo truncagem '..'/variação de OCR.
    Evita marcar 'vunzigeviktor' vs 'vunzigevikt..' como baralhamento."""
    ca = (a or "").rstrip(". ").lower()
    cb = (b or "").rstrip(". ").lower()
    if ca == cb:
        return True
    n = min(len(ca), len(cb), 6)
    return n >= 4 and ca[:n] == cb[:n]


def _seats_from_raw(raw: str) -> dict:
    head = (raw or "").split("*** HOLE CARDS")[0]
    return {int(m.group(1)): (m.group(2).strip(), _ss_num(m.group(3)))
            for m in _SS_SEAT_RE.finditer(head)}


def _final_chips_by_token(raw: str, seats: dict) -> dict:
    """Fichas FINAIS por token (fim da mão): inicial − ante − comprometido_por_street
    + uncalled + collected. #GOLD-STACK-MOMENT-END-NOT-START."""
    tokens = {tok for (tok, _) in seats.values()}
    idx_flop = raw.find("*** FLOP")
    idx_turn = raw.find("*** TURN")
    idx_river = raw.find("*** RIVER")
    idx_show = raw.find("*** SHOW")
    idx_sum = raw.find("*** SUMMARY")
    ends = [i for i in (idx_flop, idx_turn, idx_river, idx_show, idx_sum) if i >= 0]
    pre_end = min(ends) if ends else len(raw)
    sections = [raw[:pre_end]]
    if idx_flop >= 0:
        e = min([i for i in (idx_turn, idx_river, idx_show, idx_sum) if i > idx_flop] or [len(raw)])
        sections.append(raw[idx_flop:e])
    if idx_turn >= 0:
        e = min([i for i in (idx_river, idx_show, idx_sum) if i > idx_turn] or [len(raw)])
        sections.append(raw[idx_turn:e])
    if idx_river >= 0:
        e = min([i for i in (idx_show, idx_sum) if i > idx_river] or [len(raw)])
        sections.append(raw[idx_river:e])

    ante = {t: 0.0 for t in tokens}
    invested = {t: 0.0 for t in tokens}
    won = {t: 0.0 for t in tokens}
    for t in tokens:
        te = re.escape(t)
        for m in re.finditer(rf"^{te}: posts the ante ([\d,]+)", raw, re.M):
            ante[t] += _ss_num(m.group(1))
        for m in re.finditer(rf"Uncalled bet \(([\d,]+)\) returned to {te}\b", raw):
            invested[t] -= _ss_num(m.group(1))
        for m in re.finditer(rf"^{te} collected ([\d,]+) from", raw, re.M):
            won[t] += _ss_num(m.group(1))
    for text in sections:
        for t in tokens:
            commit = 0.0
            for line in text.splitlines():
                if not line.startswith(t + ":"):
                    continue
                mr = re.search(r"raises [\d,]+ to ([\d,]+)", line)
                mb = re.search(r"posts (?:small|big) blind ([\d,]+)", line)
                mstr = re.search(r"posts straddle ([\d,]+)", line)
                mc = re.search(r"(?:calls|bets) ([\d,]+)", line)
                if mr:
                    commit = _ss_num(mr.group(1))          # "to Y" = total da street
                elif mb:
                    commit += _ss_num(mb.group(1))
                elif mstr:
                    commit += _ss_num(mstr.group(1))
                elif mc:
                    commit += _ss_num(mc.group(1))
            invested[t] += commit
    final = {}
    for _s, (tok, init) in seats.items():
        final[tok] = init - ante[tok] - invested[tok] + won[tok]
    return final


def _scramble_state(raw: str, anon_map: dict, apa: dict, seats: dict):
    """Devolve (broken, incomplete). broken exclui truncagem/OCR do mesmo nome."""
    players = {k: v for k, v in (apa or {}).items()
               if k != "_meta" and isinstance(v, dict)}
    apa_seats = {v.get("seat") for v in players.values() if isinstance(v.get("seat"), int)}
    raw_seats = set(seats)
    mism = [n for n, i in players.items()
            if isinstance(i.get("seat"), int) and seats.get(i["seat"])
            and anon_map.get(seats[i["seat"]][0])
            and not _same_player(n, anon_map.get(seats[i["seat"]][0]))]
    dropped = raw_seats - apa_seats
    non_hero = {tok for (tok, _) in seats.values() if tok != "Hero"}
    incomplete = not all(h in anon_map for h in non_hero)
    return (bool(mism) or bool(dropped)), incomplete


def _stack_gate_ok(seats: dict, anon_map: dict, gold: dict, final_chips: dict, bb: float):
    """Gold(fim) vs fichas FINAIS da HH. Unit-agnóstico (Gold legado misto: BB ou fichas)."""
    checked = matched = 0
    for _s, (tok, _init) in seats.items():
        name = anon_map.get(tok)
        if not name:
            continue
        gv = gold.get(name.strip().lower())
        if gv is None:
            continue
        fc = final_chips.get(tok)
        if fc is None:
            continue
        checked += 1
        fbb = fc / bb if bb else fc
        if (abs(gv - fc) <= max(0.08 * max(fc, 1), 2 * bb)
                or abs(gv - fbb) <= max(0.15 * max(fbb, 1), 1.0)):
            matched += 1
    return (checked > 0 and matched >= checked - 2), checked, matched


def reenrich_scrambled_gold(dry_run: bool = False) -> dict:
    """Re-enriquece as mãos Gold (position_v3) baralhadas: reconstrói o apa do RAW
    (recupera vilões largados), re-enriquece por anon_map+seat + re-carrega coroas
    da Gold (guarda ½-base). SÓ escreve as que passam o gate de fichas FINAIS.
    Não toca nas já-certas, nas de truncagem, nas que reprovam o gate ou anon_map
    incompleto. dry_run=True → não escreve, devolve o plano."""
    from psycopg2.extras import Json
    from app.parsers.gg_hands import parse_hands

    base_rows = query("SELECT tournament_number, buy_in_bounty FROM tournament_summaries "
                      "WHERE site='GGPoker' AND buy_in_bounty IS NOT NULL")
    base_by_tn = {r["tournament_number"]: float(r["buy_in_bounty"]) for r in base_rows}

    rows = query("""SELECT h.id, h.hand_id, h.raw, h.tournament_number, h.player_names,
                           h.all_players_actions,
                           e.raw_json->'players_list' AS entry_players
                      FROM hands h JOIN entries e ON e.id = h.entry_id
                     WHERE h.site='GGPoker' AND h.played_at >= '2026-01-01'
                       AND h.player_names->>'match_method' = 'position_v3'""")

    total = len(rows)
    not_broken = incomplete = gate_fail = no_stack = written = 0
    players_recovered = crowns_carried = crowns_rejected = 0
    written_ids = []
    fails = []
    for r in rows:
        raw = r["raw"] or ""
        pn = r["player_names"] or {}
        anon_map = pn.get("anon_map") or {}
        apa = r["all_players_actions"] or {}
        seats = _seats_from_raw(raw)
        lm = _SS_LVL_RE.search(raw)
        bb = _ss_num(lm.group(2)) if lm else None
        if not bb or not seats:
            not_broken += 1
            continue

        broken, is_incomplete = _scramble_state(raw, anon_map, apa, seats)
        if not broken:
            not_broken += 1
            continue
        if is_incomplete:
            incomplete += 1
            fails.append((r["hand_id"], "anon_map incompleto"))
            continue

        gold = {}
        for p in (r["entry_players"] or []):
            if isinstance(p, dict) and p.get("name"):
                sv = p.get("stack_bb")
                if sv is None:
                    sv = p.get("stack_chips")
                gold[p["name"].strip().lower()] = sv

        final_chips = _final_chips_by_token(raw, seats)
        ok, checked, _matched = _stack_gate_ok(seats, anon_map, gold, final_chips, bb)
        if not ok:
            if checked == 0:
                no_stack += 1
                fails.append((r["hand_id"], "sem stacks na Gold p/ validar"))
            else:
                gate_fail += 1
                fails.append((r["hand_id"], "seats divergem"))
            continue

        # ── re-enrich: RAW → apa por-hash → nomes+coroas por anon_map+seat ──
        parsed, _errs = parse_hands(raw.encode("utf-8"), r["hand_id"])
        if not parsed or not parsed[0].get("all_players_actions"):
            fails.append((r["hand_id"], "re-parse falhou"))
            continue
        hash_apa = parsed[0]["all_players_actions"]
        old_players = sum(1 for k, v in apa.items()
                          if k != "_meta" and isinstance(v, dict))
        new_apa = _enrich_all_players_actions(
            hash_apa, anon_map, {"players_list": r["entry_players"] or []})

        # guarda ½-base nas coroas re-carregadas
        base = base_by_tn.get(r["tournament_number"])
        floor = base / 2 if base else None
        for k, v in new_apa.items():
            if k == "_meta" or not isinstance(v, dict):
                continue
            crown = v.get("bounty_value_usd") or 0
            if crown > 0 and floor is not None and crown < floor:
                v["bounty_value_usd"] = 0            # < ½-base → provável má leitura
                crowns_rejected += 1
            elif crown > 0:
                crowns_carried += 1

        new_players = sum(1 for k, v in new_apa.items()
                          if k != "_meta" and isinstance(v, dict))
        players_recovered += max(0, new_players - old_players)
        written += 1
        written_ids.append(r["hand_id"])
        if not dry_run:
            conn = get_conn()
            try:
                with conn.cursor() as cur:
                    cur.execute("UPDATE hands SET all_players_actions=%s WHERE id=%s",
                                (Json(new_apa), r["id"]))
                conn.commit()
            finally:
                conn.close()
            # Cura verde-KO (família A): re-enrich do gold baralhado → o funil garante que
            # um seat HH-bustado não fica com coroa de origem-Vision. Só-tagadas.
            try:
                from app.services.eliminated_bounty import scrub_and_persist
                scrub_and_persist(r["id"])
            except Exception as e:  # pragma: no cover - defensivo
                logger.error("[crown-cure] ⚠️ GUARD FALHOU (reenrich) hand %s — coroa de bustado pode "
                             "SOBREVIVER (o crivo apanha): %s", r["hand_id"], e)

    return {
        "hands_scanned": total,
        "not_broken_untouched": not_broken,
        "written": written,
        "players_recovered_from_hash": players_recovered,
        "crowns_carried": crowns_carried,
        "crowns_rejected_below_half": crowns_rejected,
        "skipped_incomplete_anon_map": incomplete,
        "skipped_gate_diverge": gate_fail,
        "skipped_no_gold_stacks": no_stack,
        "written_ids": written_ids,
        "skipped_ids": fails,
        "dry_run": dry_run,
    }


@router.post("/reenrich-scrambled-gold")
def trigger_reenrich_scrambled_gold(dry_run: bool = False,
                                    current_user=Depends(require_auth_or_api_key)):
    """#DESANON-GOLD-SCRAMBLE — re-enriquece as mãos Gold baralhadas (nomes trocados/
    vilões a hash) reconstruindo o apa do RAW + anon_map+seat + coroas. Só escreve as
    que passam o gate de fichas FINAIS. `dry_run=true` → não escreve. Sem Vision."""
    return reenrich_scrambled_gold(dry_run=dry_run)


async def _backfill_worker(entry_ids: list, force: bool = False):
    """Worker assíncrono que processa entries 1 a 1 sequencialmente.
    force=True → re-Vision mesmo em entries já feitos e refresca os crowns nas
    mãos já enriquecidas (propaga para _run_vision_for_entry)."""
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

            await _run_vision_for_entry(eid, content, mime_type, tm_number, file_meta, img_b64, force=force)
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


@router.post("/gold-vision-run")
async def gold_vision_run(payload: dict = Body(...),
                          current_user=Depends(require_auth_or_api_key)):
    """Recuperação/teste — re-corre a Vision do GOLD (NOMES) sobre a imagem GUARDADA de
    mãos GG cuja gold nunca foi processada (`vision_done=false` + `img_b64` presente).
    Estas caíram no vão: o worker normal só apanha `img_b64 IS NULL` (o import trouxe a
    imagem) e o `revision-replayers` só apanha `replayer_link` do Discord. Corre
    `_run_vision_for_entry(force=True)` → extrai `players_list` + de-anon (position_v3).
    SÍNCRONO, cap **10** por chamada (anti-massivo: lotes grandes = ordem do Rui). Body:
    {hand_ids:[...]}. Devolve por mão: nomes extraídos + mm/hero resultante."""
    hand_ids = payload.get("hand_ids") or []
    if not isinstance(hand_ids, list) or not hand_ids:
        raise HTTPException(400, "hand_ids (lista não-vazia) obrigatório")
    if len(hand_ids) > 10:
        raise HTTPException(400, "máx 10 por chamada (lotes grandes = ordem do Rui)")
    out = []
    for hid in hand_ids:
        rows = query(
            "SELECT e.id AS eid, e.raw_json AS rj, h.id AS hdbid "
            "  FROM entries e JOIN hands h ON h.entry_id = e.id "
            " WHERE h.hand_id = %s AND e.entry_type = 'screenshot' "
            "   AND (e.raw_json->>'img_b64') IS NOT NULL", (hid,))
        if not rows:
            out.append({"hand_id": hid, "status": "sem gold com img_b64"})
            continue
        e = rows[0]
        raw = e["rj"] or {}
        b = raw.get("img_b64", "") or ""
        if "," in b[:40]:
            b = b.split(",", 1)[1]
        try:
            content = base64.b64decode(b)
        except Exception:
            out.append({"hand_id": hid, "status": "img_b64 inválida"})
            continue
        await _run_vision_for_entry(
            e["eid"], content, raw.get("mime_type", "image/png"),
            raw.get("tm"), raw.get("file_meta", {}), raw.get("img_b64", ""), force=True)
        er = query("SELECT COALESCE(jsonb_array_length(raw_json->'players_list'),0) AS n, "
                   "raw_json->'players_list' AS pl, raw_json->>'vision_done' AS vd "
                   "FROM entries WHERE id = %s", (e["eid"],))[0]
        hr = query("SELECT player_names->>'match_method' AS mm, "
                   "player_names->>'hero' AS hero FROM hands WHERE id = %s", (e["hdbid"],))[0]
        names = [p.get("name") for p in (er["pl"] or [])
                 if isinstance(p, dict) and p.get("name")]
        out.append({"hand_id": hid, "vision_done": er["vd"], "n_names": er["n"],
                    "names": names, "mm": hr["mm"], "hero": hr["hero"]})
    return {"results": out}


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
