"""
Router para MTT (Multi-Table Tournaments).

Fluxo:
  1. Importa ficheiro HH de MTT (.txt ou .zip)
  2. Parseia cada mão → extrai TM number, jogadores por posição, VPIP preflop
  3. Faz match com screenshots órfãos pelo TM number
  4. Para cada mão com screenshot, cria hand_villains (apenas jogadores com VPIP)
  5. Nomes dos jogadores vêm SEMPRE do screenshot (Vision), nunca da HH
"""
import os
import re
import io
import json
import zipfile
import logging
import asyncio
from datetime import datetime
from collections import defaultdict
from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from app.auth import require_auth
from app.db import get_conn, query, execute
from app.hero_names import HERO_NAMES

router = APIRouter(prefix="/api/mtt", tags=["mtt"])
logger = logging.getLogger("mtt")

# ── Hero nicks seen in GG screenshots (same subset as screenshot.py) ─────────
_GG_HERO_ALIASES = ["lauro dermio", "koumpounophobia", "lauro derm"]


# ── Schema ────────────────────────────────────────────────────────────────────

MTT_SCHEMA_STATEMENTS = [
    """
    CREATE TABLE IF NOT EXISTS mtt_hands (
        id BIGSERIAL PRIMARY KEY,
        tm_number TEXT NOT NULL,
        tournament_name TEXT,
        played_at TIMESTAMPTZ,
        blinds TEXT,
        sb_size REAL,
        bb_size REAL,
        ante_size REAL,
        num_players INT,
        hero_position TEXT,
        hero_cards TEXT[],
        board TEXT[],
        hero_result REAL,
        players_by_position JSONB,
        screenshot_entry_id BIGINT,
        has_screenshot BOOLEAN DEFAULT FALSE,
        raw TEXT,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_mtt_hands_tm ON mtt_hands(tm_number)",
    "CREATE INDEX IF NOT EXISTS idx_mtt_hands_played_at ON mtt_hands(played_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_mtt_hands_has_screenshot ON mtt_hands(has_screenshot)",
    "CREATE UNIQUE INDEX IF NOT EXISTS uniq_mtt_hands_tm_time ON mtt_hands(tm_number, played_at)",
    """
    CREATE TABLE IF NOT EXISTS hand_villains (
        id BIGSERIAL PRIMARY KEY,
        mtt_hand_id BIGINT NOT NULL REFERENCES mtt_hands(id) ON DELETE CASCADE,
        player_name TEXT NOT NULL,
        position TEXT,
        stack REAL,
        bounty_pct TEXT,
        country TEXT,
        vpip_action TEXT,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_hand_villains_mtt_hand ON hand_villains(mtt_hand_id)",
    "CREATE INDEX IF NOT EXISTS idx_hand_villains_name ON hand_villains(player_name)",
]


def ensure_mtt_schema():
    """Cria as tabelas de MTT se não existirem."""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            for sql in MTT_SCHEMA_STATEMENTS:
                try:
                    cur.execute(sql)
                except Exception as e:
                    conn.rollback()
                    logger.warning(f"MTT schema statement skipped: {e}")
                    continue
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ── VPIP Detection ────────────────────────────────────────────────────────────

def _detect_vpip_players(block: str, seats: dict, hero_name: str = "Hero") -> dict:
    """
    Analisa a secção preflop de uma mão e devolve os jogadores que fizeram VPIP.
    VPIP = qualquer acção voluntária (call, raise, bet, all-in) que não seja post de blinds.
    
    NOTA: No GGPoker, os nomes nos seats (ex: "539b5a64") são os MESMOS que aparecem
    nas linhas de acção. Não há tradução necessária — o raw_actor É o nome do seat.
    O _build_anon_map do gg_hands.py tentava mapear entre dois sistemas de IDs
    mas neste contexto baralha tudo. Usamos mapeamento directo.
    
    Retorna: { seat_num: "action_description", ... } para jogadores com VPIP (excluindo hero)
    """
    vpip_players = {}
    
    # Encontrar a secção preflop (entre HOLE CARDS e FLOP/SUMMARY)
    preflop_start = block.find("*** HOLE CARDS ***")
    if preflop_start == -1:
        return vpip_players
    
    preflop_end = len(block)
    for marker in ["*** FLOP ***", "*** SUMMARY ***", "*** SHOWDOWN ***"]:
        idx = block.find(marker, preflop_start)
        if idx != -1 and idx < preflop_end:
            preflop_end = idx
    
    preflop_section = block[preflop_start:preflop_end]
    
    # Construir mapa nome → seat_num (directo, sem anon_map)
    name_to_seat = {}
    for seat_num, info in seats.items():
        name_to_seat[info["name"]] = seat_num
    
    # Analisar cada linha de acção no preflop
    for line in preflop_section.split("\n"):
        line = line.strip()
        if not line or line.startswith("***") or line.startswith("Dealt"):
            continue
        
        m = re.match(r"^(.+?):\s+(.+)$", line)
        if not m:
            continue
        
        raw_actor = m.group(1).strip()
        action_text = m.group(2).strip().lower()
        
        # Ignorar posts de blinds/antes
        if "posts" in action_text:
            continue
        
        # Ignorar hero
        if raw_actor == hero_name:
            continue
        
        # Verificar se é VPIP
        is_vpip = False
        action_desc = ""
        
        if action_text.startswith("calls"):
            is_vpip = True
            action_desc = "call"
        elif action_text.startswith("raises"):
            is_vpip = True
            action_desc = "raise"
        elif action_text.startswith("bets"):
            is_vpip = True
            action_desc = "bet"
        elif "all-in" in action_text and not action_text.startswith("folds"):
            is_vpip = True
            action_desc = "all-in"
        
        if is_vpip and raw_actor in name_to_seat:
            seat = name_to_seat[raw_actor]
            if seat not in vpip_players:
                vpip_players[seat] = action_desc
    
    return vpip_players


# ── Parse single hand for MTT ────────────────────────────────────────────────

def _parse_mtt_hand(block: str) -> dict | None:
    """
    Parseia uma mão de HH para uso no MTT.
    Extrai: TM number, torneio, data, blinds, jogadores por posição, VPIP.
    """
    if not block.strip() or len(block) < 50:
        return None
    
    # TM number
    hid_m = re.search(r"Hand\s*#(?:TM|RC)?(\d+)", block)
    if not hid_m:
        return None
    tm_number = f"TM{hid_m.group(1)}"
    
    # Tournament name
    tournament_name = None
    name_m = re.search(r"Tournament\s*#\d+\s*,?\s*(.+?)(?:\s+Hold'em|\s*$)", block, re.M)
    if name_m:
        tournament_name = name_m.group(1).strip().rstrip(",")
    
    # Date
    played_at = None
    date_m = re.search(r"(\d{4})[/-](\d{2})[/-](\d{2})\s+(\d{1,2}):(\d{2}):(\d{2})", block)
    if date_m:
        try:
            played_at = datetime(
                int(date_m.group(1)), int(date_m.group(2)), int(date_m.group(3)),
                int(date_m.group(4)), int(date_m.group(5)), int(date_m.group(6)),
            ).isoformat()
        except ValueError:
            pass
    
    # Blinds
    sb_size = 0
    bb_size = 0
    ante_size = 0
    level_m = re.search(r"Level\s*\d+\s*\(([\d,]+)/([\d,]+)(?:\(([\d,]+)\))?\)", block)
    if level_m:
        sb_size = float(level_m.group(1).replace(",", ""))
        bb_size = float(level_m.group(2).replace(",", ""))
        if level_m.group(3):
            ante_size = float(level_m.group(3).replace(",", ""))
    
    blinds = f"{int(sb_size)}/{int(bb_size)}"
    if ante_size:
        blinds += f"({int(ante_size)})"
    
    # Button seat
    table_m = re.search(r"Table\s+'[^']*'\s+(\d+)-max\s+Seat\s*#(\d+)\s+is the button", block)
    button_seat = None
    if table_m:
        button_seat = int(table_m.group(2))
    
    # Seats
    seats = {}
    all_seat_nums = []
    hero_seat = None
    
    for sm in re.finditer(r"Seat\s+(\d+):\s*(.+?)\s*\(([\d,]+)\s+in chips\)", block):
        seat_num = int(sm.group(1))
        name = sm.group(2).strip()
        stack = float(sm.group(3).replace(",", ""))
        seats[seat_num] = {"name": name, "stack": stack}
        all_seat_nums.append(seat_num)
        if name == "Hero":
            hero_seat = seat_num
    
    num_players = len(all_seat_nums)
    
    # Positions
    from app.parsers.gg_hands import _get_position, POSITION_MAPS
    
    players_by_position = {}
    hero_position = None
    
    if button_seat and all_seat_nums:
        for seat_num in all_seat_nums:
            pos = _get_position(seat_num, button_seat, all_seat_nums, num_players)
            seats[seat_num]["position"] = pos
            players_by_position[pos] = {
                "name": seats[seat_num]["name"],
                "seat": seat_num,
                "stack": seats[seat_num]["stack"],
                "stack_bb": round(seats[seat_num]["stack"] / bb_size, 1) if bb_size > 0 else 0,
            }
            if seat_num == hero_seat:
                hero_position = pos
    
    # Hero cards
    hero_cards = []
    hero_m = re.search(r"Dealt to Hero\s*\[(.+?)\]", block)
    if hero_m:
        hero_cards = [c.strip() for c in hero_m.group(1).split() if c.strip()]
    
    # Board
    board = []
    flop_m = re.search(r"\*\*\*\s*FLOP\s*\*\*\*\s*\[(.+?)\]", block)
    if flop_m:
        board.extend([c.strip() for c in flop_m.group(1).split() if c.strip()])
    turn_m = re.search(r"\*\*\*\s*TURN\s*\*\*\*\s*\[.+?\]\s*\[(.+?)\]", block)
    if turn_m:
        board.extend([c.strip() for c in turn_m.group(1).split() if c.strip()])
    river_m = re.search(r"\*\*\*\s*RIVER\s*\*\*\*\s*\[.+?\]\s*\[(.+?)\]", block)
    if river_m:
        board.extend([c.strip() for c in river_m.group(1).split() if c.strip()])
    
    # Hero result (em BB)
    hero_result = None
    if bb_size > 0:
        hero_invested = 0
        hero_won = 0
        
        ante_m2 = re.search(r"Hero:\s+posts the ante\s+([\d,]+)", block)
        if ante_m2:
            hero_invested += float(ante_m2.group(1).replace(",", ""))
        sb_m = re.search(r"Hero:\s+posts small blind\s+([\d,]+)", block)
        if sb_m:
            hero_invested += float(sb_m.group(1).replace(",", ""))
        bb_m = re.search(r"Hero:\s+posts big blind\s+([\d,]+)", block)
        if bb_m:
            hero_invested += float(bb_m.group(1).replace(",", ""))
        for am in re.finditer(r"Hero:\s+(?:calls|bets)\s+([\d,]+)", block):
            hero_invested += float(am.group(1).replace(",", ""))
        for am in re.finditer(r"Hero:\s+raises\s+[\d,]+\s+to\s+([\d,]+)", block):
            hero_invested += float(am.group(1).replace(",", ""))
        uncalled_m = re.search(r"Uncalled bet \(([\d,]+)\) returned to Hero", block)
        if uncalled_m:
            hero_invested -= float(uncalled_m.group(1).replace(",", ""))
        for wm in re.finditer(r"Hero collected ([\d,]+) from", block):
            hero_won += float(wm.group(1).replace(",", ""))
        
        hero_result = round((hero_won - hero_invested) / bb_size, 2)
    
    # VPIP detection
    vpip_players = _detect_vpip_players(block, seats, "Hero")
    
    return {
        "tm_number": tm_number,
        "tournament_name": tournament_name,
        "played_at": played_at,
        "blinds": blinds,
        "sb_size": sb_size,
        "bb_size": bb_size,
        "ante_size": ante_size,
        "num_players": num_players,
        "hero_position": hero_position,
        "hero_cards": hero_cards,
        "board": board,
        "hero_result": hero_result,
        "players_by_position": players_by_position,
        "vpip_seats": vpip_players,  # { seat_num: "action_desc" }
        "seats": seats,
        "raw": block.strip(),
    }


def _parse_mtt_file(content: bytes, filename: str) -> tuple[list[dict], list[str]]:
    """Parseia um ficheiro de HH de MTT. Devolve (hands, errors)."""
    hands = []
    errors = []
    
    try:
        text = content.decode("utf-8", errors="replace")
    except Exception as e:
        return [], [f"Erro a ler ficheiro: {e}"]
    
    blocks = re.split(r"(?=(?:Poker\s+)?Hand\s*#)", text)
    
    for i, block in enumerate(blocks):
        block = block.strip()
        if not block or len(block) < 50:
            continue
        try:
            hand = _parse_mtt_hand(block)
            if hand and hand["tm_number"]:
                hands.append(hand)
        except Exception as e:
            errors.append(f"Bloco {i}: {e}")
    
    return hands, errors


# ── Match com screenshots ─────────────────────────────────────────────────────

def _extract_tm_digits(tm_value: str) -> str:
    """
    Extrai só os dígitos de qualquer formato de TM/tournament ID.
    Suporta: TM5754140681, #TM5754140681, GG-5754140681, 5754140681,
             Poker Hand #TM5754140681, Hand #5754140681, etc.
    """
    if not tm_value:
        return ""
    digits = re.sub(r"[^0-9]", "", str(tm_value))
    return digits


def _extract_screenshot_data(raw: dict, entry_id: int) -> dict:
    """Extrai dados relevantes de um entry de screenshot."""
    return {
        "entry_id": entry_id,
        "players_by_position": raw.get("players_by_position", {}),
        "players_list": raw.get("players_list", []),
        "hero": raw.get("hero"),
        "board": raw.get("board", []),
        "vision_sb": raw.get("vision_sb"),
        "vision_bb": raw.get("vision_bb"),
    }


def _match_screenshot(tm_number: str, played_at: str | None = None, blinds: str | None = None) -> dict | None:
    """
    Procura um screenshot órfão pelo TM number + hora + blinds.
    Usa apenas dígitos para comparação (ignora prefixos TM, GG-, #, etc.)
    
    Estratégia:
      1. Filtrar por TM number (só dígitos)
      2. Se houver múltiplos, filtrar por blinds
      3. Se ainda houver múltiplos, filtrar por hora (±5 min)
    Retorna dados do Vision incluindo players_list e vision_sb/bb.
    """
    tm_digits = _extract_tm_digits(tm_number)
    if not tm_digits:
        return None
    
    rows = query(
        """SELECT id, raw_json 
           FROM entries 
           WHERE entry_type = 'screenshot' 
             AND raw_json->>'tm' LIKE %s
             AND (raw_json->>'vision_done')::boolean = true
           ORDER BY id""",
        (f"%{tm_digits}%",)
    )
    
    if not rows:
        return None
    
    if len(rows) == 1:
        raw = rows[0].get("raw_json") or {}
        return _extract_screenshot_data(raw, rows[0]["id"])
    
    # Múltiplos screenshots do mesmo TM — filtrar por blinds + hora
    def _normalise_blinds(b: str | None) -> str:
        if not b:
            return ""
        return re.sub(r"[,\s]", "", b).lower()
    
    hh_blinds_norm = _normalise_blinds(blinds)
    
    candidates = []
    for row in rows:
        raw = row.get("raw_json") or {}
        file_meta = raw.get("file_meta") or {}
        ss_blinds = file_meta.get("blinds") or raw.get("blinds") or ""
        ss_blinds_norm = _normalise_blinds(ss_blinds)
        if hh_blinds_norm and ss_blinds_norm and hh_blinds_norm == ss_blinds_norm:
            candidates.append(row)
    
    if not candidates:
        candidates = rows
    
    if len(candidates) == 1:
        raw = candidates[0].get("raw_json") or {}
        return _extract_screenshot_data(raw, candidates[0]["id"])
    
    # Filtrar por hora (±5 minutos)
    if played_at:
        try:
            hh_dt = datetime.fromisoformat(played_at.replace("Z", "+00:00"))
            best = None
            best_diff = float("inf")
            for row in candidates:
                raw = row.get("raw_json") or {}
                file_meta = raw.get("file_meta") or {}
                ss_time_str = file_meta.get("time")
                ss_date_str = file_meta.get("date")
                if ss_time_str and ss_date_str:
                    try:
                        ss_dt = datetime.fromisoformat(f"{ss_date_str}T{ss_time_str}:00")
                        diff = abs((hh_dt.replace(tzinfo=None) - ss_dt).total_seconds())
                        if diff < best_diff:
                            best_diff = diff
                            best = row
                    except Exception:
                        pass
            if best and best_diff < 300:
                raw = best.get("raw_json") or {}
                return _extract_screenshot_data(raw, best["id"])
        except Exception as e:
            logger.warning(f"Erro ao comparar horas no match: {e}")
    
    raw = candidates[0].get("raw_json") or {}
    return _extract_screenshot_data(raw, candidates[0]["id"])


def _build_seat_to_name_map(hh_hand: dict, screenshot_data: dict) -> dict:
    """
    Constrói mapa seat_num → nome_real usando o algoritmo v2:
    1. Âncoras fixas: Hero, SB (do painel), BB (do painel)
    2. Fold players: stack_hh - ante ≈ stack_vision (<2%)
    3. Eliminação: restantes

    A HH mostra stacks ANTES de antes/blinds.
    O screenshot mostra stacks no FINAL da mão.
    Para fold players: stack_screenshot = stack_hh - ante
    """
    seats = hh_hand.get("seats", {})
    vision_list = screenshot_data.get("players_list", [])
    vision_sb = screenshot_data.get("vision_sb")
    vision_bb = screenshot_data.get("vision_bb")
    hero_name_vision = screenshot_data.get("hero")

    # Ante da HH
    ante = hh_hand.get("ante_size", 0)

    seat_to_name = {}  # seat_num → nome_real
    used_vision = set()
    hero_names = _GG_HERO_ALIASES

    # ── Fase 1: Âncoras fixas ────────────────────────────────────────

    for seat_num, info in seats.items():
        pos = info.get("position", "")
        name = info.get("name", "")

        # Hero
        if name == "Hero":
            for i, vp in enumerate(vision_list):
                if i in used_vision:
                    continue
                if any(h in vp["name"].lower() for h in hero_names):
                    seat_to_name[seat_num] = vp["name"]
                    used_vision.add(i)
                    break
            if seat_num not in seat_to_name:
                seat_to_name[seat_num] = hero_name_vision or "Hero"
            continue

        # SB
        if pos == "SB" and vision_sb:
            for i, vp in enumerate(vision_list):
                if i in used_vision:
                    continue
                if vp["name"].lower().startswith(vision_sb.lower()[:6]):
                    seat_to_name[seat_num] = vp["name"]
                    used_vision.add(i)
                    break
            if seat_num not in seat_to_name:
                seat_to_name[seat_num] = vision_sb
            continue

        # BB
        if pos == "BB" and vision_bb:
            for i, vp in enumerate(vision_list):
                if i in used_vision:
                    continue
                if vp["name"].lower().startswith(vision_bb.lower()[:6]):
                    seat_to_name[seat_num] = vp["name"]
                    used_vision.add(i)
                    break
            if seat_num not in seat_to_name:
                seat_to_name[seat_num] = vision_bb
            continue

    # ── Fase 2: Fold players — match por stack esperado ──────────────

    # Determinar quem foldou preflop (reparse do raw)
    raw = hh_hand.get("raw", "")
    preflop_folders = set()
    if raw:
        preflop_start = raw.find("*** HOLE CARDS ***")
        preflop_end = len(raw)
        for marker in ["*** FLOP ***", "*** SUMMARY ***", "*** SHOWDOWN ***"]:
            idx = raw.find(marker, preflop_start if preflop_start >= 0 else 0)
            if idx != -1 and idx < preflop_end:
                preflop_end = idx

        if preflop_start >= 0:
            preflop_section = raw[preflop_start:preflop_end]
            for line in preflop_section.split("\n"):
                line = line.strip()
                m = re.match(r"^(.+?):\s+folds", line)
                if m:
                    preflop_folders.add(m.group(1).strip())

    for seat_num, info in seats.items():
        if seat_num in seat_to_name:
            continue

        name = info.get("name", "")
        stack = info.get("stack", 0)

        # Verificar se este jogador foldou preflop
        is_folder = name in preflop_folders
        if not is_folder:
            continue

        # Stack esperado no screenshot = stack_inicial - ante
        stack_esperado = stack - ante

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
            seat_to_name[seat_num] = vision_list[best_i]["name"]
            used_vision.add(best_i)

    # ── Fase 3: Eliminação ───────────────────────────────────────────

    unmapped_seats = [s for s in seats if s not in seat_to_name]
    unmapped_vision = [i for i in range(len(vision_list)) if i not in used_vision]

    if len(unmapped_seats) == 1 and len(unmapped_vision) == 1:
        seat_to_name[unmapped_seats[0]] = vision_list[unmapped_vision[0]]["name"]
    elif len(unmapped_seats) > 0 and len(unmapped_vision) > 0:
        still_unmapped = set(unmapped_vision)
        for seat_num in unmapped_seats:
            stack = seats[seat_num].get("stack", 0)
            best_i = None
            best_diff = float("inf")
            for i in still_unmapped:
                diff = abs(stack - vision_list[i]["stack"])
                if diff < best_diff:
                    best_diff = diff
                    best_i = i
            if best_i is not None:
                seat_to_name[seat_num] = vision_list[best_i]["name"]
                still_unmapped.discard(best_i)

    return seat_to_name


def _create_villains_for_hand(conn, hh_hand: dict, screenshot_data: dict, *, mtt_hand_id: int = None, hand_db_id: int = None, showdown_only: bool = False):
    assert (mtt_hand_id is None) ^ (hand_db_id is None), "must pass exactly one of mtt_hand_id or hand_db_id"
    """
    Cria registos hand_villains.
    Se showdown_only=True, villains = jogadores não-herói que mostraram cartas no showdown.
    Caso contrário, villains = jogadores com VPIP (comportamento legacy).
    Nomes vêm do screenshot via match por stack (algoritmo v2).
    Posições vêm da HH.
    """
    if showdown_only:
        # Showdown mode: villains are non-hero players who showed cards
        all_players = hh_hand.get("all_players_actions", {})
        if not isinstance(all_players, dict):
            return 0
        showdown_seats = {}
        for p, pdata in all_players.items():
            if p == "_meta":
                continue
            if isinstance(pdata, dict) and not pdata.get("is_hero") and pdata.get("cards"):
                showdown_seats[pdata["seat"]] = ", ".join(pdata["cards"])
        if not showdown_seats:
            return 0
        vpip_seats = showdown_seats
    else:
        vpip_seats = hh_hand.get("vpip_seats", {})
        if not vpip_seats:
            return 0

    seats = hh_hand.get("seats", {})

    # Construir mapa seat → nome real usando match por stack
    seat_to_name = _build_seat_to_name_map(hh_hand, screenshot_data)

    # Lookup para bounty/country a partir da vision_list
    vision_by_name = {}
    for vp in screenshot_data.get("players_list", []):
        vision_by_name[vp["name"].lower()] = vp

    created = 0
    with conn.cursor() as cur:
        for seat_num, vpip_action in vpip_seats.items():
            seat_num = int(seat_num)
            seat_info = seats.get(seat_num, {})
            position = seat_info.get("position", "?")

            # Nome real vem do match por stack
            player_name = seat_to_name.get(seat_num, seat_info.get("name", "Unknown"))

            # Bounty/country do Vision
            vision_info = vision_by_name.get(player_name.lower(), {})
            stack = vision_info.get("stack") or seat_info.get("stack")
            bounty_pct = vision_info.get("bounty_pct")
            country = vision_info.get("country")

            cur.execute(
                """INSERT INTO hand_villains
                   (mtt_hand_id, hand_db_id, player_name, position, stack, bounty_pct, country, vpip_action)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
                (mtt_hand_id, hand_db_id, player_name, position, stack, bounty_pct, country, vpip_action)
            )
            created += 1

            # Auto-populate villain_notes
            if player_name and player_name != "Unknown" and player_name != "Hero":
                cur.execute(
                    """INSERT INTO villain_notes (site, nick, hands_seen, updated_at)
                       VALUES ('GGPoker', %s, 1, NOW())
                       ON CONFLICT (site, nick) DO UPDATE SET
                           hands_seen = villain_notes.hands_seen + 1,
                           updated_at = NOW()""",
                    (player_name,)
                )

    return created


def _detect_tournament_format(tournament_name: str) -> str:
    """Detect tournament format from name: PKO, KO, vanilla, mystery."""
    if not tournament_name:
        return "vanilla"
    name_lower = tournament_name.lower()
    if "mystery" in name_lower:
        return "mystery"
    if "bounty" in name_lower or "pko" in name_lower or "knockout" in name_lower:
        return "PKO"
    if " ko " in name_lower or name_lower.endswith(" ko"):
        return "KO"
    return "vanilla"


def _extract_buyin(tournament_name: str) -> str | None:
    """Extract buy-in from tournament name."""
    if not tournament_name:
        return None
    m = re.search(r'\$(\d+(?:[,.]?\d+)?)', tournament_name)
    if m:
        return f"${m.group(1)}"
    m = re.search(r'(\d+(?:[,.]?\d+)?)\s*[€]', tournament_name)
    if m:
        return f"{m.group(1)}€"
    m = re.search(r'buyIn:\s*([\d€$,.+\s]+)', tournament_name, re.I)
    if m:
        return m.group(1).strip()
    return None


def _promote_to_study(conn, mtt_hand_id: int, hh_hand: dict, screenshot_data: dict, seat_to_name: dict):
    """
    Quando uma mão MTT tem screenshot, garante que existe na tabela hands
    com study_state='new'. Adds tag 'Match SS' + format + buy-in.
    """
    tm_number = hh_hand.get("tm_number", "")
    tm_digits = _extract_tm_digits(tm_number)
    hand_id = f"GG-{tm_digits}"

    tournament_name = hh_hand.get("tournament_name") or hh_hand.get("blinds", "")
    tournament_format = _detect_tournament_format(tournament_name)
    buyin = _extract_buyin(tournament_name)

    # Auto-tags: "GG Hands" vai para hm3_tags (tema de estudo principal).
    # Tags de formato/max-players continuam em tags (auto-geradas).
    hm3_tags = ["GG Hands"]
    auto_tags = []
    if tournament_format != "vanilla":
        auto_tags.append(tournament_format.lower())
    num_players = len(hh_hand.get("seats", {}))
    if num_players > 0:
        auto_tags.append(f"{num_players}max")

    # Construir all_players_actions com nomes reais
    seats = hh_hand.get("seats", {})
    bb_size = hh_hand.get("bb_size", 1)

    all_players = {}
    for seat_num, info in seats.items():
        name = info.get("name", "")
        pos = info.get("position", "?")
        stack_bb = round(info.get("stack", 0) / bb_size, 1) if bb_size > 0 else 0
        real_name = seat_to_name.get(seat_num, name)

        all_players[real_name] = {
            "seat": seat_num,
            "position": pos,
            "stack_bb": stack_bb,
            "real_name": real_name,
            "is_hero": name == "Hero",
        }

    player_names = {
        "players_list": screenshot_data.get("players_list", []),
        "hero": screenshot_data.get("hero"),
        "vision_sb": screenshot_data.get("vision_sb"),
        "vision_bb": screenshot_data.get("vision_bb"),
        "seat_to_name": {str(k): v for k, v in seat_to_name.items()},
        "screenshot_entry_id": screenshot_data.get("entry_id"),
        "match_method": "mtt_promote_v2",
        "tournament_format": tournament_format,
        "buyin": buyin,
    }

    conn2 = get_conn()
    try:
        with conn2.cursor() as cur:
            cur.execute("DELETE FROM hands WHERE hand_id = %s", (hand_id,))
            cur.execute(
                """INSERT INTO hands
                   (site, hand_id, played_at, stakes, position,
                    hero_cards, board, result, currency,
                    raw, study_state, all_players_actions, player_names,
                    entry_id, tags, hm3_tags)
                VALUES
                   (%s, %s, %s, %s, %s,
                    %s, %s, %s, %s,
                    %s, %s, %s, %s,
                    %s, %s, %s)""",
                (
                    "GGPoker",
                    hand_id,
                    hh_hand.get("played_at"),
                    tournament_name,
                    hh_hand.get("hero_position"),
                    hh_hand.get("hero_cards", []),
                    hh_hand.get("board", []),
                    hh_hand.get("hero_result"),
                    "$",
                    hh_hand.get("raw", ""),
                    "new",
                    json.dumps(all_players),
                    json.dumps(player_names),
                    screenshot_data.get("entry_id"),
                    auto_tags,
                    hm3_tags,
                )
            )
        conn2.commit()
        logger.info(f"Promoted {hand_id} to study (hm3_tags={hm3_tags}, tags={auto_tags})")
    except Exception as e:
        conn2.rollback()
        logger.error(f"Promote failed for {hand_id}: {e}")
    finally:
        conn2.close()


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/import")
async def import_mtt(
    file: UploadFile = File(...),
    current_user=Depends(require_auth),
):
    """
    Importa ficheiro HH de MTT (.txt ou .zip).
    Parseia cada mão, faz match com screenshots, cria villains com VPIP.
    """
    content = await file.read()
    filename = file.filename or "upload"
    is_zip = filename.lower().endswith(".zip")
    
    all_hands = []
    all_errors = []
    
    if is_zip:
        try:
            with zipfile.ZipFile(io.BytesIO(content)) as zf:
                for name in zf.namelist():
                    if not name.lower().endswith(".txt"):
                        continue
                    file_content = zf.read(name)
                    hands, errors = _parse_mtt_file(file_content, name)
                    all_hands.extend(hands)
                    all_errors.extend(errors)
        except Exception as e:
            all_errors.append(f"Erro a abrir ZIP: {e}")
    else:
        hands, errors = _parse_mtt_file(content, filename)
        all_hands.extend(hands)
        all_errors.extend(errors)
    
    if not all_hands:
        return {
            "status": "error",
            "message": "Nenhuma mão encontrada no ficheiro",
            "errors": all_errors[:20],
        }
    
    # Inserir mãos e fazer match com screenshots
    inserted = 0
    skipped = 0
    matched = 0
    villains_created = 0
    
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            for h in all_hands:
                tm_number = h["tm_number"]
                tm_digits = _extract_tm_digits(tm_number)
                hand_id = f"GG-{tm_digits}"

                logger.info(f"[import_mtt] Processando hand_id: {hand_id}")
                # Verificar duplicado na tabela hands
                cur.execute(
                    "SELECT id, raw, hm3_tags FROM hands WHERE hand_id = %s",
                    (hand_id,)
                )
                existing = cur.fetchone()
                if existing:
                    logger.info(f"[import_mtt] hand_id {hand_id} já existe. ID: {existing['id']}, raw_len: {len(existing['raw']) if existing['raw'] else 0}, tags: {existing['hm3_tags']}")
                    # Se for placeholder GGDiscord (raw vazio + tag GGDiscord), apaga-o para dar lugar à HH real
                    is_placeholder = (
                        (not existing["raw"] or existing["raw"].strip() == "") and
                        existing["hm3_tags"] and "GGDiscord" in existing["hm3_tags"]
                    )
                    if is_placeholder:
                        logger.info(f"[import_mtt] hand_id {hand_id} é placeholder GGDiscord. A apagar para substituir.")
                        cur.execute("DELETE FROM hands WHERE id = %s", (existing["id"],))
                    else:
                        logger.info(f"[import_mtt] hand_id {hand_id} NÃO é placeholder. Ignorando (duplicado).")
                        skipped += 1
                        continue
                else:
                    logger.info(f"[import_mtt] hand_id {hand_id} é novo. A inserir.")
                
                # Procurar screenshot match (TM + hora + blinds)
                screenshot = _match_screenshot(h["tm_number"], h.get("played_at"), h.get("blinds"))
                has_screenshot = screenshot is not None
                screenshot_entry_id = screenshot["entry_id"] if screenshot else None

                tournament_name = h.get("tournament_name") or h.get("blinds", "")
                bb_size = h.get("bb_size", 1)

                # Build all_players_actions
                seats = h.get("seats", {})
                all_players = {}
                seat_to_name = {}
                if has_screenshot:
                    seat_to_name = _build_seat_to_name_map(h, screenshot)

                for seat_num, info in seats.items():
                    name = info.get("name", "")
                    pos = info.get("position", "?")
                    stack = info.get("stack", 0)
                    stack_bb = round(stack / bb_size, 1) if bb_size > 0 else 0
                    real_name = seat_to_name.get(seat_num, name) if has_screenshot else name

                    all_players[real_name] = {
                        "seat": seat_num,
                        "position": pos,
                        "stack": stack,
                        "stack_bb": stack_bb,
                        "real_name": real_name,
                        "is_hero": name == "Hero",
                    }

                all_players["_meta"] = {
                    "level": None,
                    "sb": h.get("sb_size", 0),
                    "bb": h.get("bb_size", 0),
                    "ante": h.get("ante_size", 0),
                    "num_players": h.get("num_players", 0),
                }

                # Auto-tags
                tags = []
                if has_screenshot:
                    tags.append("Match SS")
                    tournament_format = _detect_tournament_format(tournament_name)
                    if tournament_format != "vanilla":
                        tags.append(tournament_format.lower())
                num_p = len(seats)
                if num_p > 0:
                    tags.append(f"{num_p}max")

                study_state = "new" if has_screenshot else "mtt_archive"

                # Player names (screenshot data)
                player_names = None
                if has_screenshot:
                    buyin = _extract_buyin(tournament_name)
                    player_names = json.dumps({
                        "players_list": screenshot.get("players_list", []),
                        "hero": screenshot.get("hero"),
                        "vision_sb": screenshot.get("vision_sb"),
                        "vision_bb": screenshot.get("vision_bb"),
                        "seat_to_name": {str(k): v for k, v in seat_to_name.items()},
                        "screenshot_entry_id": screenshot_entry_id,
                        "match_method": "mtt_import_v3",
                        "tournament_format": _detect_tournament_format(tournament_name),
                        "buyin": buyin,
                    })

                # Inserir na tabela hands (fonte primária)
                cur.execute(
                    """INSERT INTO hands
                       (site, hand_id, played_at, stakes, position,
                        hero_cards, board, result, currency,
                        raw, study_state, all_players_actions, player_names,
                        entry_id, tags)
                    VALUES
                       (%s, %s, %s, %s, %s,
                        %s, %s, %s, %s,
                        %s, %s, %s, %s,
                        %s, %s)
                    ON CONFLICT (hand_id) DO NOTHING
                    RETURNING id""",
                    (
                        "GGPoker",
                        hand_id,
                        h.get("played_at"),
                        tournament_name,
                        h.get("hero_position"),
                        h.get("hero_cards", []),
                        h.get("board", []),
                        h.get("hero_result"),
                        "$",
                        h.get("raw", ""),
                        study_state,
                        json.dumps(all_players),
                        player_names,
                        screenshot_entry_id,
                        tags if tags else None,
                    )
                )
                row = cur.fetchone()
                if not row:
                    skipped += 1
                    continue

                hands_id = row["id"]
                inserted += 1

                # Também inserir em mtt_hands (backup/legacy)
                try:
                    cur.execute(
                        """INSERT INTO mtt_hands 
                           (tm_number, tournament_name, played_at, blinds,
                            sb_size, bb_size, ante_size, num_players,
                            hero_position, hero_cards, board, hero_result,
                            players_by_position, screenshot_entry_id, has_screenshot, raw)
                           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                           ON CONFLICT (tm_number, played_at) DO NOTHING
                           RETURNING id""",
                        (
                            h["tm_number"], tournament_name, h["played_at"], h["blinds"],
                            h["sb_size"], h["bb_size"], h["ante_size"], h["num_players"],
                            h["hero_position"], h["hero_cards"], h["board"], h["hero_result"],
                            json.dumps(h["players_by_position"]),
                            screenshot_entry_id, has_screenshot, h["raw"],
                        )
                    )
                    mtt_row = cur.fetchone()
                    mtt_hand_id = mtt_row["id"] if mtt_row else None
                except Exception:
                    mtt_hand_id = None
                
                # Criar villains se houver screenshot
                if has_screenshot and h.get("vpip_seats"):
                    # Use mtt_hand_id for legacy FK, hands_id for new FK
                    if mtt_hand_id:
                        n = _create_villains_for_hand(conn, h, screenshot, mtt_hand_id=mtt_hand_id)
                    else:
                        n = _create_villains_for_hand(conn, h, screenshot, hand_db_id=hands_id)
                    villains_created += n
                    if n > 0:
                        matched += 1
        
        conn.commit()
    except Exception as e:
        conn.rollback()
        logger.error(f"Erro ao importar MTT: {e}")
        raise HTTPException(status_code=500, detail=f"Erro ao importar: {e}")
    finally:
        conn.close()
    
    # Extrair nome do torneio (usar o primeiro hand que tem)
    tournament_name = None
    for h in all_hands:
        if h.get("tournament_name"):
            tournament_name = h["tournament_name"]
            break
    
    return {
        "status": "ok",
        "filename": filename,
        "tournament_name": tournament_name,
        "total_hands": len(all_hands),
        "inserted": inserted,
        "skipped": skipped,
        "matched_with_screenshots": matched,
        "villains_created": villains_created,
        "errors": len(all_errors),
        "error_log": all_errors[:20],
    }


@router.get("/hands")
def list_mtt_hands(
    has_screenshot: bool | None = None,
    tm_search: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    current_user=Depends(require_auth),
):
    """Lista mãos GGPoker MTT da tabela hands (pós-migração)."""
    conditions = ["h.site = 'GGPoker'", "h.hand_id LIKE 'GG-%%'"]
    params = []
    
    if has_screenshot is not None:
        if has_screenshot:
            conditions.append("(h.screenshot_url IS NOT NULL OR h.player_names IS NOT NULL)")
        else:
            conditions.append("h.screenshot_url IS NULL AND h.player_names IS NULL")
    
    if tm_search:
        conditions.append("h.hand_id ILIKE %s")
        params.append(f"%{tm_search}%")
    
    where = "WHERE " + " AND ".join(conditions)
    
    # Count
    count_rows = query(
        f"SELECT COUNT(*) as n FROM hands h {where}",
        tuple(params)
    )
    total = count_rows[0]["n"] if count_rows else 0
    
    # Fetch
    offset = (page - 1) * page_size
    rows = query(
        f"""SELECT h.id, h.hand_id, h.played_at, h.stakes, h.position,
                   h.hero_cards, h.board, h.result, h.study_state,
                   h.screenshot_url, h.player_names, h.all_players_actions,
                   h.entry_id
            FROM hands h 
            {where}
            ORDER BY h.played_at DESC NULLS LAST
            LIMIT %s OFFSET %s""",
        tuple(params) + (page_size, offset)
    )
    
    result = []
    for r in rows:
        hand = dict(r)
        # Map to MTT-compatible fields for frontend
        tm_digits = (hand.get("hand_id") or "").replace("GG-", "")
        hand["tm_number"] = f"TM{tm_digits}" if tm_digits else None
        hand["tournament_name"] = hand.get("stakes")
        hand["hero_position"] = hand.get("position")
        hand["hero_result"] = float(hand["result"]) if hand.get("result") is not None else None
        hand["has_screenshot"] = bool(hand.get("screenshot_url") or hand.get("player_names"))
        hand["blinds"] = None
        # Extract blinds from all_players_actions meta
        apa = hand.get("all_players_actions") or {}
        if isinstance(apa, str):
            apa = json.loads(apa)
        meta = apa.get("_meta", {})
        if meta.get("sb") and meta.get("bb"):
            sb_val = meta["sb"]
            bb_val = meta["bb"]
            ante_val = meta.get("ante")
            hand["blinds"] = f"{sb_val}/{bb_val}" + (f"({ante_val})" if ante_val else "")
        hand["num_players"] = meta.get("num_players", 0)
        # Screenshot entry_id for delete button
        pn = hand.get("player_names") or {}
        if isinstance(pn, str):
            pn = json.loads(pn)
        hand["screenshot_entry_id"] = hand.get("entry_id") or pn.get("screenshot_entry_id")
        # Villains from hand_villains (try both FK columns)
        try:
            villains = query(
                """SELECT * FROM hand_villains 
                   WHERE mtt_hand_id = %s OR hand_db_id = %s
                   ORDER BY position""",
                (hand["id"], hand["id"])
            )
        except Exception:
            # hand_db_id column may not exist yet
            villains = query(
                "SELECT * FROM hand_villains WHERE mtt_hand_id = %s ORDER BY position",
                (hand["id"],)
            )
        hand["villains"] = [dict(v) for v in villains]
        hand["villain_count"] = len(villains)
        # Cleanup: don't send heavy fields
        hand.pop("all_players_actions", None)
        hand.pop("player_names", None)
        result.append(hand)
    
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "hands": result,
    }


@router.get("/hands/{hand_id}")
def get_mtt_hand(
    hand_id: int,
    current_user=Depends(require_auth),
):
    """Detalhe de uma mão GGPoker MTT da tabela hands."""
    rows = query(
        """SELECT id, hand_id, played_at, stakes, position,
                  hero_cards, board, result, study_state,
                  screenshot_url, player_names, all_players_actions,
                  entry_id
           FROM hands WHERE id = %s""",
        (hand_id,)
    )
    if not rows:
        raise HTTPException(status_code=404, detail="Mão não encontrada")
    
    hand = dict(rows[0])
    # Map to MTT-compatible fields
    tm_digits = (hand.get("hand_id") or "").replace("GG-", "")
    hand["tm_number"] = f"TM{tm_digits}" if tm_digits else None
    hand["tournament_name"] = hand.get("stakes")
    hand["hero_position"] = hand.get("position")
    hand["hero_result"] = float(hand["result"]) if hand.get("result") is not None else None
    hand["has_screenshot"] = bool(hand.get("screenshot_url") or hand.get("player_names"))
    
    apa = hand.get("all_players_actions") or {}
    if isinstance(apa, str):
        apa = json.loads(apa)
    meta = apa.get("_meta", {})
    hand["blinds"] = None
    if meta.get("sb") and meta.get("bb"):
        hand["blinds"] = f"{meta['sb']}/{meta['bb']}" + (f"({meta['ante']})" if meta.get("ante") else "")
    
    # Villains
    try:
        villains = query(
            """SELECT * FROM hand_villains 
               WHERE mtt_hand_id = %s OR hand_db_id = %s
               ORDER BY position""",
            (hand_id, hand_id)
        )
    except Exception:
        villains = query(
            "SELECT * FROM hand_villains WHERE mtt_hand_id = %s ORDER BY position",
            (hand_id,)
        )
    hand["villains"] = [dict(v) for v in villains]
    
    # Screenshot players from player_names
    pn = hand.get("player_names") or {}
    if isinstance(pn, str):
        pn = json.loads(pn)
    hand["screenshot_players"] = pn.get("players_by_position", {})
    hand["screenshot_hero"] = pn.get("hero")
    hand["screenshot_entry_id"] = hand.get("entry_id") or pn.get("screenshot_entry_id")
    
    # Don't send raw heavy fields
    hand.pop("all_players_actions", None)
    hand.pop("player_names", None)
    
    return hand


@router.get("/stats")
def mtt_stats(current_user=Depends(require_auth)):
    """Estatísticas gerais de mãos GGPoker MTT."""
    rows = query("""
        SELECT 
            COUNT(*) as total_hands,
            COUNT(*) FILTER (WHERE screenshot_url IS NOT NULL OR player_names IS NOT NULL) as hands_with_screenshot,
            COUNT(DISTINCT stakes) as tournaments,
            (SELECT COUNT(*) FROM hand_villains) as total_villains,
            (SELECT COUNT(DISTINCT player_name) FROM hand_villains) as unique_villains
        FROM hands
        WHERE site = 'GGPoker' AND hand_id LIKE 'GG-%%'
    """)
    
    if rows:
        return dict(rows[0])
    return {
        "total_hands": 0,
        "hands_with_screenshot": 0,
        "tournaments": 0,
        "total_villains": 0,
        "unique_villains": 0,
    }


@router.get("/orphan-screenshots")
def orphan_screenshots(current_user=Depends(require_auth)):
    """
    Lista mãos/screenshots sem HH match — mistura 2 origens no mesmo formato:

      1. Entries `screenshot` (upload manual) sem mão criada
      2. Mãos placeholder GGDiscord (SS Discord sem HH match ainda)

    Devolvidos juntos no mesmo formato. O frontend trata-os como orphan SS
    sem distinção visual. Para o utilizador, é tudo "SS sem match".
    """
    # Origem 1: orphan screenshots tradicionais (entries sem mão)
    orphan_ss_rows = query("""
        SELECT e.id, e.raw_json, e.created_at, e.discord_posted_at,
               NULL::bigint AS hand_db_id,
               NULL::text AS gg_discord_screenshot_url,
               NULL::timestamp AS played_at
        FROM entries e
        WHERE e.entry_type = 'screenshot'
          AND e.status = 'new'
          AND NOT EXISTS (
              SELECT 1 FROM mtt_hands m WHERE m.screenshot_entry_id = e.id
          )
          AND NOT EXISTS (
              SELECT 1 FROM hands h WHERE h.entry_id = e.id
          )
    """)

    # Origem 2: mãos GGDiscord (placeholder Discord sem HH)
    gg_discord_rows = query("""
        SELECT e.id, e.raw_json, e.created_at, e.discord_posted_at,
               h.id AS hand_db_id,
               h.screenshot_url AS gg_discord_screenshot_url,
               h.played_at
        FROM hands h
        JOIN entries e ON e.id = h.entry_id
        WHERE 'GGDiscord' = ANY(h.hm3_tags)
    """)

    items = []
    for r in (orphan_ss_rows + gg_discord_rows):
        raw = r.get("raw_json") or {}
        items.append({
            "id": r["id"],                         # entry_id
            "hand_db_id": r["hand_db_id"],         # null para orphan_ss, id para GGDiscord
            "tm": raw.get("tm"),
            "vision_done": raw.get("vision_done", False),
            "hero": raw.get("hero"),
            "file_meta": raw.get("file_meta", {}),
            "screenshot_url": r["gg_discord_screenshot_url"],  # só GGDiscord
            "raw_json": raw,
            "played_at": str(r["played_at"]) if r.get("played_at") else None,
            "discord_posted_at": str(r["discord_posted_at"]) if r.get("discord_posted_at") else None,
            "created_at": str(r["created_at"]) if r.get("created_at") else None,
        })

    # Ordenar por played_at (real) com fallback para discord_posted_at e created_at
    items.sort(key=lambda x: x.get("played_at") or x.get("discord_posted_at") or x.get("created_at") or "", reverse=True)
    return items


@router.post("/rematch")
async def rematch_screenshots(
    current_user=Depends(require_auth),
):
    """
    Re-tenta match de screenshots com mãos.
    Procura em AMBAS as tabelas (mtt_hands e hands) usando só dígitos do TM.
    """
    # Buscar screenshots com Vision concluído
    screenshot_entries = query(
        """SELECT id, raw_json 
           FROM entries 
           WHERE entry_type = 'screenshot' 
             AND (raw_json->>'vision_done')::boolean = true
           ORDER BY id"""
    )
    
    if not screenshot_entries:
        return {"matched": 0, "villains_created": 0, "total_screenshots": 0}
    
    matched = 0
    villains_created = 0
    promoted = 0
    already_matched = 0
    no_hh = 0
    
    conn = get_conn()
    try:
        for ss_entry in screenshot_entries:
            raw = ss_entry.get("raw_json") or {}
            tm = raw.get("tm")
            if not tm:
                continue
            
            tm_digits = _extract_tm_digits(tm)
            if not tm_digits:
                continue
            
            # Verificar se já há match para este screenshot (em mtt_hands)
            existing = query(
                "SELECT id FROM mtt_hands WHERE screenshot_entry_id = %s LIMIT 1",
                (ss_entry["id"],)
            )
            if existing:
                already_matched += 1
                continue
            
            # Também verificar se já tem match em hands
            existing_hands = query(
                "SELECT id FROM hands WHERE entry_id = %s LIMIT 1",
                (ss_entry["id"],)
            )
            if existing_hands:
                already_matched += 1
                continue
            
            # ── Tentar match na mtt_hands (procura flexível por dígitos) ──
            mtt_rows = query(
                """SELECT id, tm_number, raw FROM mtt_hands 
                   WHERE regexp_replace(tm_number, '[^0-9]', '', 'g') = %s
                     AND has_screenshot = false 
                   LIMIT 1""",
                (tm_digits,)
            )
            
            if mtt_rows:
                mtt_hand = mtt_rows[0]
                screenshot_data = _extract_screenshot_data(raw, ss_entry["id"])
                
                # Marcar mão como tendo screenshot
                with conn.cursor() as cur:
                    cur.execute(
                        "UPDATE mtt_hands SET has_screenshot = true, screenshot_entry_id = %s WHERE id = %s",
                        (ss_entry["id"], mtt_hand["id"])
                    )
                
                # Parsear a mão para extrair VPIP e criar villains
                parsed = _parse_mtt_hand(mtt_hand["raw"]) if mtt_hand.get("raw") else None
                if parsed:
                    if parsed.get("vpip_seats"):
                        n = _create_villains_for_hand(conn, parsed, screenshot_data, mtt_hand_id=mtt_hand["id"])
                        villains_created += n
                    
                    seat_to_name = _build_seat_to_name_map(parsed, screenshot_data)
                    _promote_to_study(conn, mtt_hand["id"], parsed, screenshot_data, seat_to_name)
                    promoted += 1
                
                matched += 1
                continue
            
            # ── Tentar match na tabela hands (mãos importadas pelo /api/import) ──
            hand_id_pattern = f"GG-{tm_digits}"
            hand_rows = query(
                "SELECT id, hand_id FROM hands WHERE hand_id = %s LIMIT 1",
                (hand_id_pattern,)
            )
            
            if not hand_rows:
                # Tentar match flexível: extrair dígitos do hand_id
                hand_rows = query(
                    """SELECT id, hand_id FROM hands 
                       WHERE regexp_replace(hand_id, '[^0-9]', '', 'g') = %s
                       LIMIT 1""",
                    (tm_digits,)
                )
            
            if hand_rows:
                from app.routers.screenshot import _enrich_hand_from_orphan_entry
                try:
                    enrich_result = _enrich_hand_from_orphan_entry(
                        ss_entry["id"], hand_rows[0]["id"], raw
                    )
                    
                    # Criar villain_notes — só para jogadores com VPIP
                    players_list = raw.get("players_list", [])
                    hero_name = raw.get("hero", "")
                    
                    # Get updated all_players_actions
                    updated_hand = query("SELECT all_players_actions FROM hands WHERE id = %s", (hand_rows[0]["id"],))
                    apa = (updated_hand[0].get("all_players_actions") or {}) if updated_hand else {}
                    
                    with conn.cursor() as cur:
                        for player in players_list:
                            pname = player.get("name", "")
                            if not pname or pname == "Unknown" or pname == hero_name:
                                continue
                            
                            # Check VPIP
                            player_data = apa.get(pname, {})
                            actions = player_data.get("actions", {})
                            preflop_action = actions.get("preflop", "")
                            has_vpip = (
                                actions.get("flop") is not None
                                or actions.get("turn") is not None
                                or actions.get("river") is not None
                                or (preflop_action and "fold" not in preflop_action.lower())
                            )
                            
                            if not has_vpip:
                                continue
                            
                            cur.execute(
                                """INSERT INTO villain_notes (site, nick, hands_seen, updated_at)
                                   VALUES ('GGPoker', %s, 1, NOW())
                                   ON CONFLICT (site, nick) DO UPDATE SET
                                       hands_seen = villain_notes.hands_seen + 1,
                                       updated_at = NOW()""",
                                (pname,)
                            )
                            villains_created += 1
                    
                    matched += 1
                    promoted += 1
                    logger.info(f"Rematch via hands table: entry {ss_entry['id']} → hand {hand_rows[0]['id']} ({hand_id_pattern}), {len(players_list)} players")
                except Exception as e:
                    logger.warning(f"Rematch enrich failed for entry {ss_entry['id']}: {e}")
                continue
            
            no_hh += 1

        # ── SEGUNDA FASE: reconciliar mãos GGDiscord órfãs ──
        # Verifica, para cada placeholder GGDiscord, se existe agora uma HH real
        # em `hands` com raw preenchido (mesmo torneio/TM) e substitui a placeholder.
        #
        # Caminho normal (post fix do /mtt/import):
        #   Import novo apaga placeholder antes de INSERT. Esta fase não encontra nada.
        # Caminho de recuperação:
        #   Se houver placeholders órfãos (criados depois de HH já importada, ou com
        #   hand_id divergente), esta fase reconcilia.
        ggdiscord_hands = query("""
            SELECT h.id AS hand_db_id, h.hand_id, h.entry_id,
                   e.raw_json AS entry_raw_json
            FROM hands h
            LEFT JOIN entries e ON e.id = h.entry_id
            WHERE 'GGDiscord' = ANY(h.hm3_tags)
              AND (h.raw IS NULL OR h.raw = '')
        """)

        for gd in ggdiscord_hands:
            entry_raw = gd.get("entry_raw_json") or {}
            tm = entry_raw.get("tm")
            if not tm:
                continue
            tm_digits = _extract_tm_digits(tm)
            if not tm_digits:
                continue

            # Procurar HH real em `hands` (HH do bulk upload vai directamente para hands)
            # O hand_id tem o formato GG-<tm_digits> tanto para placeholder como para HH real.
            # Logo aqui, se encontrarmos linha diferente do placeholder com raw preenchido,
            # é a HH real desse torneio a viver com hand_id diferente — caso edge.
            # Mais provável: não há HH → continuar como GGDiscord (utilizador precisa importar HH).
            real_hand = query(
                """SELECT id, hand_id, raw FROM hands
                   WHERE id != %s
                     AND regexp_replace(hand_id, '[^0-9]', '', 'g') = %s
                     AND raw IS NOT NULL
                     AND raw != ''
                   LIMIT 1""",
                (gd["hand_db_id"], tm_digits)
            )
            if not real_hand:
                no_hh += 1
                continue

            # Há uma HH real. Apaga placeholder (que é gd) e a HH real mantém-se.
            # Se o entry_id da placeholder não é None, reaponta para a HH real se esta não tiver entry_id.
            with conn.cursor() as cur:
                # Transferir entry_id se a real não tem
                if gd["entry_id"]:
                    cur.execute(
                        """UPDATE hands
                           SET entry_id = COALESCE(entry_id, %s)
                           WHERE id = %s""",
                        (gd["entry_id"], real_hand[0]["id"])
                    )
                # Apagar placeholder
                cur.execute("DELETE FROM hands WHERE id = %s", (gd["hand_db_id"],))
                promoted += 1
                matched += 1
                logger.info(f"GGDiscord reconciliado: placeholder {gd['hand_id']} apagado, HH real preservada ({real_hand[0]['hand_id']})")

        conn.commit()
    except Exception as e:
        conn.rollback()
        logger.error(f"Erro no rematch: {e}")
        raise HTTPException(status_code=500, detail=f"Erro no rematch: {e}")
    finally:
        conn.close()
    
    return {
        "matched": matched,
        "villains_created": villains_created,
        "promoted_to_study": promoted,
        "already_matched": already_matched,
        "no_hh_found": no_hh,
        "total_screenshots": len(screenshot_entries),
    }


@router.post("/re-enrich")
async def re_enrich_all(
    current_user=Depends(require_auth),
):
    """
    Re-processa TODOS os screenshots com Vision concluído.
    Para cada um, actualiza player_names, all_players_actions e cria villain_notes.
    Funciona independentemente de a mão estar em mtt_hands ou hands.
    """
    screenshot_entries = query(
        """SELECT id, raw_json 
           FROM entries 
           WHERE entry_type = 'screenshot' 
             AND (raw_json->>'vision_done')::boolean = true
           ORDER BY id"""
    )
    
    if not screenshot_entries:
        return {"processed": 0, "villains_created": 0, "errors": 0}
    
    processed = 0
    villains_created = 0
    errors = 0
    
    conn = get_conn()
    try:
        for ss_entry in screenshot_entries:
            raw = ss_entry.get("raw_json") or {}
            tm = raw.get("tm")
            if not tm:
                continue
            
            tm_digits = _extract_tm_digits(tm)
            if not tm_digits:
                continue
            
            # Procurar mão na hands (por hand_id)
            hand_rows = query(
                "SELECT id, hand_id, raw, all_players_actions FROM hands WHERE hand_id = %s LIMIT 1",
                (f"GG-{tm_digits}",)
            )
            if not hand_rows:
                hand_rows = query(
                    """SELECT id, hand_id, raw, all_players_actions FROM hands 
                       WHERE regexp_replace(hand_id, '[^0-9]', '', 'g') = %s
                       LIMIT 1""",
                    (tm_digits,)
                )
            
            if not hand_rows:
                continue
            
            hand = hand_rows[0]
            
            # Enrich hand com dados do screenshot
            try:
                from app.routers.screenshot import _enrich_hand_from_orphan_entry
                _enrich_hand_from_orphan_entry(ss_entry["id"], hand["id"], raw)
            except Exception as e:
                logger.warning(f"Re-enrich failed for hand {hand['id']}: {e}")
                errors += 1
                continue
            
            # Criar/actualizar villain_notes — só para jogadores com VPIP
            players_list = raw.get("players_list", [])
            hero_name = raw.get("hero", "")
            
            # Reload hand to get updated all_players_actions
            updated_hand = query("SELECT all_players_actions FROM hands WHERE id = %s", (hand["id"],))
            apa = (updated_hand[0].get("all_players_actions") or {}) if updated_hand else {}
            
            with conn.cursor() as cur:
                for player in players_list:
                    pname = player.get("name", "")
                    if not pname or pname == "Unknown" or pname == hero_name:
                        continue
                    
                    # Check if player had VPIP (not just fold preflop)
                    player_data = apa.get(pname, {})
                    actions = player_data.get("actions", {})
                    preflop_action = actions.get("preflop", "")
                    has_vpip = (
                        actions.get("flop") is not None
                        or actions.get("turn") is not None
                        or actions.get("river") is not None
                        or (preflop_action and "fold" not in preflop_action.lower())
                    )
                    
                    if not has_vpip:
                        continue
                    
                    cur.execute(
                        """INSERT INTO villain_notes (site, nick, hands_seen, updated_at)
                           VALUES ('GGPoker', %s, 1, NOW())
                           ON CONFLICT (site, nick) DO UPDATE SET
                               hands_seen = villain_notes.hands_seen + 1,
                               updated_at = NOW()""",
                        (pname,)
                    )
                    villains_created += 1
            
            # Também criar na mtt_hands se existir lá
            mtt_rows = query(
                """SELECT id, raw FROM mtt_hands 
                   WHERE regexp_replace(tm_number, '[^0-9]', '', 'g') = %s
                   LIMIT 1""",
                (tm_digits,)
            )
            if mtt_rows:
                mtt_hand = mtt_rows[0]
                screenshot_data = _extract_screenshot_data(raw, ss_entry["id"])
                parsed = _parse_mtt_hand(mtt_hand["raw"]) if mtt_hand.get("raw") else None
                if parsed and parsed.get("vpip_seats"):
                    # Limpar villains antigos deste mtt_hand
                    with conn.cursor() as cur:
                        cur.execute("DELETE FROM hand_villains WHERE mtt_hand_id = %s", (mtt_hand["id"],))
                    n = _create_villains_for_hand(conn, parsed, screenshot_data, mtt_hand_id=mtt_hand["id"])
                    villains_created += n
                
                # Marcar como tendo screenshot
                with conn.cursor() as cur:
                    cur.execute(
                        "UPDATE mtt_hands SET has_screenshot = true, screenshot_entry_id = %s WHERE id = %s",
                        (ss_entry["id"], mtt_hand["id"])
                    )
            
            processed += 1
        
        conn.commit()
    except Exception as e:
        conn.rollback()
        logger.error(f"Erro no re-enrich: {e}")
        raise HTTPException(status_code=500, detail=f"Erro no re-enrich: {e}")
    finally:
        conn.close()
    
    return {
        "processed": processed,
        "villains_created": villains_created,
        "errors": errors,
        "total_screenshots": len(screenshot_entries),
    }
async def reset_and_rematch(
    current_user=Depends(require_auth),
):
    """
    Reset completo: apaga villains, mãos promovidas, e refaz todos os matches.
    Usa screenshots como iterador (rápido).
    """
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM hand_villains")
            # Reverter mãos promovidas para mtt_archive (não apagar)
            cur.execute("UPDATE hands SET study_state = 'mtt_archive', all_players_actions = NULL, player_names = NULL, entry_id = NULL WHERE study_state = 'new'")
            cur.execute("UPDATE mtt_hands SET has_screenshot = false, screenshot_entry_id = NULL")
        conn.commit()
        logger.info("Reset-matches: cleared villains, reverted study hands, and screenshot flags")
    except Exception as e:
        conn.rollback()
        logger.error(f"Reset-matches cleanup error: {e}")
        raise HTTPException(status_code=500, detail=f"Erro no reset: {e}")
    finally:
        conn.close()

    # Agora correr o rematch
    # Buscar screenshots com Vision concluído
    screenshot_entries = query(
        """SELECT id, raw_json 
           FROM entries 
           WHERE entry_type = 'screenshot' 
             AND (raw_json->>'vision_done')::boolean = true
           ORDER BY id"""
    )

    if not screenshot_entries:
        return {"reset": True, "matched": 0, "villains_created": 0, "promoted": 0, "total_screenshots": 0}

    matched = 0
    villains_created = 0
    promoted = 0

    conn = get_conn()
    try:
        for ss_entry in screenshot_entries:
            raw = ss_entry.get("raw_json") or {}
            tm = raw.get("tm")
            if not tm:
                continue

            tm_digits = tm.replace("TM", "")

            mtt_rows = query(
                "SELECT id, tm_number, raw FROM mtt_hands WHERE tm_number = %s LIMIT 1",
                (f"TM{tm_digits}",)
            )
            if not mtt_rows:
                continue

            mtt_hand = mtt_rows[0]
            screenshot_data = _extract_screenshot_data(raw, ss_entry["id"])

            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE mtt_hands SET has_screenshot = true, screenshot_entry_id = %s WHERE id = %s",
                    (ss_entry["id"], mtt_hand["id"])
                )

            parsed = _parse_mtt_hand(mtt_hand["raw"]) if mtt_hand.get("raw") else None
            if parsed:
                if parsed.get("vpip_seats"):
                    n = _create_villains_for_hand(conn, parsed, screenshot_data, mtt_hand_id=mtt_hand["id"])
                    villains_created += n

                seat_to_name = _build_seat_to_name_map(parsed, screenshot_data)
                _promote_to_study(conn, mtt_hand["id"], parsed, screenshot_data, seat_to_name)
                promoted += 1

            matched += 1

        conn.commit()
    except Exception as e:
        conn.rollback()
        logger.error(f"Reset-matches rematch error: {e}")
        raise HTTPException(status_code=500, detail=f"Erro no rematch: {e}")
    finally:
        conn.close()

    return {
        "reset": True,
        "matched": matched,
        "villains_created": villains_created,
        "promoted": promoted,
        "total_screenshots": len(screenshot_entries),
    }


@router.post("/backfill-promote-matched")
def backfill_promote_matched(current_user=Depends(require_auth)):
    """
    Percorre todas as mtt_hands com has_screenshot=true e promove-as
    para a tabela hands (se ainda não estiverem lá) com hm3_tags=['GG Hands'].
    Usa os dados já guardados em mtt_hands + entries.raw_json (Vision).
    """
    rows = query(
        """
        SELECT m.id AS mtt_id, m.tm_number, m.tournament_name, m.played_at,
               m.hero_position, m.hero_cards, m.board, m.hero_result, m.blinds,
               m.num_players, m.players_by_position,
               m.screenshot_entry_id, m.raw AS raw_hh,
               e.raw_json AS screenshot_raw
        FROM mtt_hands m
        LEFT JOIN entries e ON e.id = m.screenshot_entry_id
        WHERE m.has_screenshot = true
        ORDER BY m.id ASC
        """
    )
    total = len(rows)
    promoted = 0
    skipped_already = 0
    errors = 0

    for r in rows:
        tm_digits = _extract_tm_digits(r["tm_number"] or "")
        hand_id_str = f"GG-{tm_digits}"

        # Já existe em hands?
        existing = query("SELECT id FROM hands WHERE hand_id = %s LIMIT 1", (hand_id_str,))
        if existing:
            skipped_already += 1
            continue

        try:
            # Construir hh_hand e screenshot_data no formato que _promote_to_study espera
            screenshot_raw = r.get("screenshot_raw") or {}
            hh_hand = {
                "tm_number": r["tm_number"],
                "tournament_name": r["tournament_name"],
                "played_at": r["played_at"],
                "hero_position": r["hero_position"],
                "hero_cards": r["hero_cards"] or [],
                "board": r["board"] or [],
                "hero_result": r["hero_result"],
                "blinds": r["blinds"],
                "num_players": r["num_players"],
                "raw": r.get("raw_hh") or "",
                "seats": (r.get("players_by_position") or {}) if isinstance(r.get("players_by_position"), dict) else {},
                "bb_size": 1,  # fallback; _promote_to_study usa este para calcular stack_bb
            }
            screenshot_data = {
                "entry_id": r["screenshot_entry_id"],
                "players_list": screenshot_raw.get("players_list", []),
                "hero": screenshot_raw.get("hero"),
                "vision_sb": screenshot_raw.get("vision_sb"),
                "vision_bb": screenshot_raw.get("vision_bb"),
                "file_meta": screenshot_raw.get("file_meta", {}),
            }
            seat_to_name = _build_seat_to_name_map(hh_hand, screenshot_data)

            conn = get_conn()
            try:
                _promote_to_study(conn, r["mtt_id"], hh_hand, screenshot_data, seat_to_name)
                promoted += 1
            finally:
                conn.close()
        except Exception as e:
            errors += 1
            logger.error(f"Backfill promote error for mtt_id={r['mtt_id']}: {e}")

    return {
        "total_matched": total,
        "promoted": promoted,
        "skipped_already_in_hands": skipped_already,
        "errors": errors,
    }


@router.post("/cleanup")
async def cleanup_mtt(
    current_user=Depends(require_auth),
):
    """
    Liberta espaço: apaga mãos MTT sem screenshot e faz VACUUM.
    Mantém apenas as mãos que têm match com screenshots.
    """
    # Contar antes
    before = query("SELECT COUNT(*) as n FROM mtt_hands")[0]["n"]
    with_ss = query("SELECT COUNT(*) as n FROM mtt_hands WHERE has_screenshot = true")[0]["n"]
    
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            # Apagar villains de mãos sem screenshot
            cur.execute(
                "DELETE FROM hand_villains WHERE mtt_hand_id IN "
                "(SELECT id FROM mtt_hands WHERE has_screenshot = false)"
            )
            # Apagar mãos sem screenshot
            cur.execute("DELETE FROM mtt_hands WHERE has_screenshot = false")
            deleted = cur.rowcount
        conn.commit()
        
        # VACUUM para recuperar espaço
        conn2 = get_conn()
        conn2.autocommit = True
        try:
            with conn2.cursor() as cur:
                cur.execute("VACUUM FULL mtt_hands")
        except Exception as e:
            logger.warning(f"VACUUM failed (non-critical): {e}")
        finally:
            conn2.close()
        
    except Exception as e:
        conn.rollback()
        logger.error(f"Cleanup error: {e}")
        raise HTTPException(status_code=500, detail=f"Erro no cleanup: {e}")
    finally:
        conn.close()
    
    after = query("SELECT COUNT(*) as n FROM mtt_hands")[0]["n"]
    
    return {
        "before": before,
        "deleted": deleted,
        "kept": with_ss,
        "after": after,
    }


@router.delete("/hands/{hand_id}")
def delete_mtt_hand(hand_id: int, current_user=Depends(require_auth)):
    """Apaga uma mão MTT e seus villains associados."""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            # Apagar villains associados (both FK columns)
            cur.execute("DELETE FROM hand_villains WHERE mtt_hand_id = %s", (hand_id,))
            try:
                cur.execute("DELETE FROM hand_villains WHERE hand_db_id = %s", (hand_id,))
            except Exception:
                pass
            # Apagar da tabela hands
            cur.execute("DELETE FROM hands WHERE id = %s", (hand_id,))
            deleted = cur.rowcount
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Erro ao apagar: {e}")
    finally:
        conn.close()
    if deleted == 0:
        raise HTTPException(status_code=404, detail="Mão não encontrada")
    return {"ok": True, "deleted": deleted}


@router.delete("/screenshot/{entry_id}")
def delete_screenshot_and_revert(entry_id: int, current_user=Depends(require_auth)):
    """
    Apaga um screenshot e reverte o match:
    - Remove villains associados
    - Reverte a mão na tabela hands para mtt_archive
    - Apaga o entry do screenshot
    """
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            # Encontrar mão na tabela hands associada a este entry
            cur.execute(
                "SELECT id, hand_id FROM hands WHERE entry_id = %s",
                (entry_id,)
            )
            hand_row = cur.fetchone()

            if hand_row:
                # Apagar villains
                cur.execute("DELETE FROM hand_villains WHERE mtt_hand_id = %s", (hand_row["id"],))
                try:
                    cur.execute("DELETE FROM hand_villains WHERE hand_db_id = %s", (hand_row["id"],))
                except Exception:
                    pass
                # Reverter mão para mtt_archive
                cur.execute(
                    "UPDATE hands SET study_state = 'mtt_archive', player_names = NULL, screenshot_url = NULL, entry_id = NULL WHERE id = %s",
                    (hand_row["id"],)
                )

            # Also check mtt_hands (legacy)
            cur.execute(
                "SELECT id, tm_number FROM mtt_hands WHERE screenshot_entry_id = %s",
                (entry_id,)
            )
            mtt_hand = cur.fetchone()
            if mtt_hand:
                cur.execute("DELETE FROM hand_villains WHERE mtt_hand_id = %s", (mtt_hand["id"],))
                cur.execute(
                    "UPDATE mtt_hands SET has_screenshot = false, screenshot_entry_id = NULL WHERE id = %s",
                    (mtt_hand["id"],)
                )

            # Apagar o entry do screenshot
            cur.execute("DELETE FROM entries WHERE id = %s", (entry_id,))

        conn.commit()
        logger.info(f"Deleted screenshot entry {entry_id} and reverted match")
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Erro ao apagar screenshot: {e}")
    finally:
        conn.close()

    return {"ok": True, "reverted_mtt_hand": mtt_hand["id"] if mtt_hand else None}


@router.post("/migrate-to-hands")
def migrate_mtt_to_hands(current_user=Depends(require_auth)):
    """
    Migra mtt_hands → hands em lotes de 100.
    Safe to run multiple times (idempotent).
    """
    migrated = 0
    skipped = 0
    errors = 0
    total_rows = 0
    batch_size = 100
    offset = 0

    # First ensure study_state allows mtt_archive
    conn0 = get_conn()
    try:
        with conn0.cursor() as cur:
            cur.execute("""
                ALTER TABLE hands DROP CONSTRAINT IF EXISTS hands_study_state_check;
                ALTER TABLE hands ADD CONSTRAINT hands_study_state_check
                    CHECK (study_state IN ('new', 'review', 'studying', 'resolved', 'mtt_archive'));
            """)
        conn0.commit()
    except Exception:
        conn0.rollback()
    finally:
        conn0.close()

    # Count total
    count_rows = query("SELECT COUNT(*) as cnt FROM mtt_hands")
    total_rows = count_rows[0]["cnt"] if count_rows else 0

    while offset < total_rows:
        conn = get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT id, tm_number, tournament_name, played_at, blinds,
                           sb_size, bb_size, ante_size, num_players,
                           hero_position, hero_cards, board, hero_result,
                           players_by_position, screenshot_entry_id, has_screenshot,
                           raw
                    FROM mtt_hands ORDER BY id
                    LIMIT %s OFFSET %s
                """, (batch_size, offset))
                batch = cur.fetchall()

                if not batch:
                    break

                for mh in batch:
                    try:
                        tm = mh["tm_number"] or ""
                        tm_digits = _extract_tm_digits(tm)
                        hand_id = f"GG-{tm_digits}"

                        cur.execute("SELECT id FROM hands WHERE hand_id = %s", (hand_id,))
                        if cur.fetchone():
                            skipped += 1
                            continue

                        all_players = {}
                        pbp = mh.get("players_by_position") or {}
                        if isinstance(pbp, str):
                            pbp = json.loads(pbp)
                        bb_sz = mh.get("bb_size") or 1
                        for pos, info in pbp.items():
                            if isinstance(info, dict):
                                name = info.get("name", pos)
                                stack = info.get("stack", 0)
                                all_players[name] = {
                                    "position": pos,
                                    "stack": stack,
                                    "stack_bb": round(stack / bb_sz, 1) if bb_sz > 0 else 0,
                                    "is_hero": info.get("is_hero", False),
                                    "bounty": info.get("bounty"),
                                }

                        all_players["_meta"] = {
                            "level": None,
                            "sb": mh.get("sb_size", 0),
                            "bb": mh.get("bb_size", 0),
                            "ante": mh.get("ante_size", 0),
                            "num_players": mh.get("num_players", 0),
                        }

                        study_state = "new" if mh.get("has_screenshot") else "mtt_archive"
                        tournament_name = mh.get("tournament_name") or mh.get("blinds") or ""

                        cur.execute(
                            """INSERT INTO hands
                               (site, hand_id, played_at, stakes, position,
                                hero_cards, board, result, currency,
                                raw, study_state, all_players_actions,
                                tags, created_at)
                            VALUES
                               (%s, %s, %s, %s, %s,
                                %s, %s, %s, %s,
                                %s, %s, %s,
                                %s, NOW())
                            ON CONFLICT (hand_id) DO NOTHING""",
                            (
                                "GGPoker",
                                hand_id,
                                mh.get("played_at"),
                                tournament_name,
                                mh.get("hero_position"),
                                mh.get("hero_cards", []),
                                mh.get("board", []),
                                mh.get("hero_result"),
                                "$",
                                mh.get("raw", ""),
                                study_state,
                                json.dumps(all_players),
                                ["migrated"],
                            )
                        )
                        migrated += 1

                    except Exception as e:
                        errors += 1
                        if errors < 10:
                            logger.warning(f"Migration error for mtt_hand {mh.get('id')}: {e}")

            conn.commit()
        except Exception as e:
            conn.rollback()
            logger.error(f"Migration batch error at offset {offset}: {e}")
            errors += 1
        finally:
            conn.close()

        offset += batch_size

    return {
        "migrated": migrated,
        "skipped": skipped,
        "errors": errors,
        "total_mtt_hands": total_rows,
    }


# ─── Debug: diagnosticar porque /mtt/rematch não promove mãos GGDiscord ─────

@router.get("/debug-ggdiscord-match")
def debug_ggdiscord_match(current_user=Depends(require_auth)):
    """
    Devolve diagnóstico completo para perceber porque as mãos GGDiscord
    não estão a ser promovidas a GG Hands. Verifica para cada uma:
      - tm digits na entry
      - se existe row em mtt_hands com mesmo tm_digits
      - se tm_number em mtt_hands tem formato diferente
    """
    # Todas as mãos GGDiscord
    gd_hands = query("""
        SELECT h.id AS hand_db_id, h.hand_id, h.entry_id, h.created_at,
               e.raw_json AS entry_raw_json,
               e.entry_type AS entry_type_real
        FROM hands h
        LEFT JOIN entries e ON e.id = h.entry_id
        WHERE 'GGDiscord' = ANY(h.hm3_tags)
        ORDER BY h.id
    """)

    result = {
        "total_ggdiscord": len(gd_hands),
        "hands_with_no_entry": 0,
        "hands_with_no_tm_in_entry": 0,
        "hands_with_match_in_mtt_hands": 0,
        "hands_without_match_in_mtt_hands": 0,
        "details": [],
    }

    # Amostra dos tm_numbers em mtt_hands para perceber formato
    sample_mtt = query("""
        SELECT tm_number, regexp_replace(tm_number, '[^0-9]', '', 'g') AS tm_digits
        FROM mtt_hands
        ORDER BY id DESC
        LIMIT 5
    """)
    result["sample_mtt_hands_recent"] = sample_mtt

    # Total mtt_hands
    total_mtt = query("SELECT COUNT(*) AS n FROM mtt_hands")
    result["total_mtt_hands"] = total_mtt[0]["n"] if total_mtt else 0

    # Total mtt_hands com has_screenshot=false
    avail_mtt = query("SELECT COUNT(*) AS n FROM mtt_hands WHERE has_screenshot = false")
    result["mtt_hands_available_for_match"] = avail_mtt[0]["n"] if avail_mtt else 0

    for gd in gd_hands:
        entry_raw = gd.get("entry_raw_json") or {}
        tm = entry_raw.get("tm")

        row = {
            "hand_id": gd["hand_id"],
            "entry_id": gd["entry_id"],
            "entry_type": gd["entry_type_real"],
            "tm_in_entry": tm,
        }

        if not gd["entry_id"]:
            result["hands_with_no_entry"] += 1
            row["status"] = "no_entry"
            result["details"].append(row)
            continue

        if not tm:
            result["hands_with_no_tm_in_entry"] += 1
            row["status"] = "no_tm_in_entry"
            result["details"].append(row)
            continue

        tm_digits = _extract_tm_digits(tm)
        row["tm_digits"] = tm_digits

        # Procurar em mtt_hands
        mtt_matches = query(
            """SELECT id, tm_number, has_screenshot, screenshot_entry_id
               FROM mtt_hands
               WHERE regexp_replace(tm_number, '[^0-9]', '', 'g') = %s
               LIMIT 5""",
            (tm_digits,)
        )

        if mtt_matches:
            result["hands_with_match_in_mtt_hands"] += 1
            row["status"] = "match_found_in_mtt_hands"
            row["mtt_matches"] = [
                {"id": m["id"], "tm_number": m["tm_number"],
                 "has_screenshot": m["has_screenshot"],
                 "screenshot_entry_id": m["screenshot_entry_id"]}
                for m in mtt_matches
            ]
        else:
            # Procurar em hands (onde bulk upload insere agora)
            # Por TM (usando notes/raw) — hand_id da HH bulk pode ser diferente da GGDiscord
            hands_matches = query(
                """SELECT id, hand_id, hm3_tags, site,
                          length(raw) AS raw_length,
                          played_at
                   FROM hands
                   WHERE (hand_id != %s)
                     AND (
                       regexp_replace(hand_id, '[^0-9]', '', 'g') = %s
                       OR raw LIKE %s
                     )
                   LIMIT 5""",
                (gd["hand_id"], tm_digits, f"%{tm_digits}%")
            )

            if hands_matches:
                row["status"] = "match_in_hands_table"
                row["hands_matches"] = [
                    {"id": h["id"], "hand_id": h["hand_id"],
                     "hm3_tags": h["hm3_tags"], "raw_length": h["raw_length"],
                     "played_at": str(h["played_at"]) if h["played_at"] else None}
                    for h in hands_matches
                ]
                result["hands_without_match_in_mtt_hands"] += 1
            else:
                result["hands_without_match_in_mtt_hands"] += 1
                row["status"] = "no_match_anywhere"

        result["details"].append(row)

    return result


@router.get("/debug-version")
def debug_version(current_user=Depends(require_auth)):
    """Devolve se o fix do hand_service está activo."""
    import inspect
    from app.services.hand_service import _insert_hand
    source = inspect.getsource(_insert_hand)
    return {
        "hand_service_has_ggdiscord_fix": "GGDiscord" in source,
        "hand_service_line_count": len(source.split("\n")),
    }
