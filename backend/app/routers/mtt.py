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
from app.auth import require_auth
from app.db import get_conn, query, execute

router = APIRouter(prefix="/api/mtt", tags=["mtt"])
logger = logging.getLogger("mtt")


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
    "CREATE UNIQUE INDEX IF NOT EXISTS uniq_mtt_hands_tm ON mtt_hands(tm_number)",
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
    
    # Construir mapa nome → seat_num
    name_to_seat = {}
    for seat_num, info in seats.items():
        name_to_seat[info["name"]] = seat_num
    
    # Construir mapa de IDs anónimos (reutilizar lógica do gg_hands)
    from app.parsers.gg_hands import _build_anon_map
    anon_map = _build_anon_map(block, seats)
    
    # Analisar cada linha de acção no preflop
    vpip_actions = {"calls", "raises", "bets"}
    
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
        
        # Resolver nome real
        player_name = anon_map.get(raw_actor, raw_actor)
        
        # Ignorar hero
        if player_name == hero_name:
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
        
        if is_vpip and player_name in name_to_seat:
            seat = name_to_seat[player_name]
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

def _match_screenshot(tm_number: str) -> dict | None:
    """
    Procura um screenshot órfão pelo TM number.
    Retorna os dados do Vision (players_by_position, hero) ou None.
    """
    tm_digits = tm_number.replace("TM", "")
    
    # Procurar na tabela entries por screenshots com este TM
    rows = query(
        """SELECT id, raw_json 
           FROM entries 
           WHERE entry_type = 'screenshot' 
             AND raw_json->>'tm' LIKE %s
           LIMIT 1""",
        (f"%{tm_digits}%",)
    )
    
    if not rows:
        return None
    
    raw = rows[0].get("raw_json") or {}
    vision_done = raw.get("vision_done", False)
    
    if not vision_done:
        return None
    
    return {
        "entry_id": rows[0]["id"],
        "players_by_position": raw.get("players_by_position", {}),
        "hero": raw.get("hero"),
        "board": raw.get("board", []),
    }


def _create_villains_for_hand(conn, mtt_hand_id: int, hh_hand: dict, screenshot_data: dict):
    """
    Cria registos hand_villains para jogadores com VPIP.
    Nomes vêm SEMPRE do screenshot (Vision).
    Posições e VPIP vêm da HH.
    """
    vpip_seats = hh_hand.get("vpip_seats", {})
    if not vpip_seats:
        return 0
    
    seats = hh_hand.get("seats", {})
    ss_players = screenshot_data.get("players_by_position", {})
    
    # Construir mapa posição → nome do screenshot
    ss_name_by_position = {}
    for pos, pdata in ss_players.items():
        if isinstance(pdata, dict):
            ss_name_by_position[pos] = pdata.get("name", "")
        elif isinstance(pdata, str):
            ss_name_by_position[pos] = pdata
    
    created = 0
    with conn.cursor() as cur:
        for seat_num, vpip_action in vpip_seats.items():
            seat_num = int(seat_num)
            seat_info = seats.get(seat_num, {})
            position = seat_info.get("position", "?")
            
            # Nome vem do screenshot pela posição
            player_name = ss_name_by_position.get(position, seat_info.get("name", "Unknown"))
            
            # Stack do screenshot se disponível, senão da HH
            ss_player = ss_players.get(position, {})
            stack = None
            bounty_pct = None
            country = None
            
            if isinstance(ss_player, dict):
                stack = ss_player.get("stack") or ss_player.get("stack_chips")
                bounty_pct = ss_player.get("bounty_pct") or ss_player.get("bounty")
                country = ss_player.get("country_flag") or ss_player.get("country")
            
            if stack is None:
                stack = seat_info.get("stack")
            
            cur.execute(
                """INSERT INTO hand_villains 
                   (mtt_hand_id, player_name, position, stack, bounty_pct, country, vpip_action)
                   VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                (mtt_hand_id, player_name, position, stack, bounty_pct, country, vpip_action)
            )
            created += 1
    
    return created


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
                # Verificar duplicado
                cur.execute(
                    "SELECT id FROM mtt_hands WHERE tm_number = %s",
                    (h["tm_number"],)
                )
                if cur.fetchone():
                    skipped += 1
                    continue
                
                # Procurar screenshot match
                screenshot = _match_screenshot(h["tm_number"])
                has_screenshot = screenshot is not None
                screenshot_entry_id = screenshot["entry_id"] if screenshot else None
                
                # Inserir mão
                cur.execute(
                    """INSERT INTO mtt_hands 
                       (tm_number, tournament_name, played_at, blinds,
                        sb_size, bb_size, ante_size, num_players,
                        hero_position, hero_cards, board, hero_result,
                        players_by_position, screenshot_entry_id, has_screenshot, raw)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                       RETURNING id""",
                    (
                        h["tm_number"], h["tournament_name"], h["played_at"], h["blinds"],
                        h["sb_size"], h["bb_size"], h["ante_size"], h["num_players"],
                        h["hero_position"], h["hero_cards"], h["board"], h["hero_result"],
                        json.dumps(h["players_by_position"]),
                        screenshot_entry_id, has_screenshot, h["raw"],
                    )
                )
                mtt_hand_id = cur.fetchone()["id"]
                inserted += 1
                
                # Criar villains se houver screenshot
                if has_screenshot and h.get("vpip_seats"):
                    n = _create_villains_for_hand(conn, mtt_hand_id, h, screenshot)
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
    """Lista mãos de MTT, opcionalmente filtradas por screenshot."""
    conditions = []
    params = []
    
    if has_screenshot is not None:
        conditions.append("h.has_screenshot = %s")
        params.append(has_screenshot)
    
    if tm_search:
        conditions.append("h.tm_number ILIKE %s")
        params.append(f"%{tm_search}%")
    
    where = ""
    if conditions:
        where = "WHERE " + " AND ".join(conditions)
    
    # Count
    count_rows = query(
        f"SELECT COUNT(*) as n FROM mtt_hands h {where}",
        tuple(params)
    )
    total = count_rows[0]["n"] if count_rows else 0
    
    # Fetch
    offset = (page - 1) * page_size
    rows = query(
        f"""SELECT h.*, 
                   (SELECT COUNT(*) FROM hand_villains v WHERE v.mtt_hand_id = h.id) as villain_count
            FROM mtt_hands h 
            {where}
            ORDER BY h.played_at DESC NULLS LAST
            LIMIT %s OFFSET %s""",
        tuple(params) + (page_size, offset)
    )
    
    result = []
    for r in rows:
        hand = dict(r)
        # Não enviar o raw (muito grande)
        hand.pop("raw", None)
        # Carregar villains
        villains = query(
            "SELECT * FROM hand_villains WHERE mtt_hand_id = %s ORDER BY position",
            (hand["id"],)
        )
        hand["villains"] = [dict(v) for v in villains]
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
    """Detalhe de uma mão de MTT com villains."""
    rows = query(
        "SELECT * FROM mtt_hands WHERE id = %s",
        (hand_id,)
    )
    if not rows:
        raise HTTPException(status_code=404, detail="Mão não encontrada")
    
    hand = dict(rows[0])
    hand.pop("raw", None)
    
    villains = query(
        "SELECT * FROM hand_villains WHERE mtt_hand_id = %s ORDER BY position",
        (hand_id,)
    )
    hand["villains"] = [dict(v) for v in villains]
    
    # Carregar screenshot se existir
    if hand.get("screenshot_entry_id"):
        ss_rows = query(
            "SELECT raw_json FROM entries WHERE id = %s",
            (hand["screenshot_entry_id"],)
        )
        if ss_rows:
            raw = ss_rows[0].get("raw_json") or {}
            hand["screenshot_players"] = raw.get("players_by_position", {})
            hand["screenshot_hero"] = raw.get("hero")
            # Não enviar img_b64 (muito grande)
    
    return hand


@router.get("/stats")
def mtt_stats(current_user=Depends(require_auth)):
    """Estatísticas gerais de MTT."""
    rows = query("""
        SELECT 
            COUNT(*) as total_hands,
            COUNT(*) FILTER (WHERE has_screenshot) as hands_with_screenshot,
            COUNT(DISTINCT tournament_name) as tournaments,
            (SELECT COUNT(*) FROM hand_villains) as total_villains,
            (SELECT COUNT(DISTINCT player_name) FROM hand_villains) as unique_villains
        FROM mtt_hands
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
    Lista screenshots que ainda não têm match com HH.
    Agrupa por TM number.
    """
    rows = query("""
        SELECT e.id, e.raw_json, e.created_at
        FROM entries e
        WHERE e.entry_type = 'screenshot'
          AND e.status = 'new'
          AND NOT EXISTS (
              SELECT 1 FROM mtt_hands m WHERE m.screenshot_entry_id = e.id
          )
        ORDER BY e.created_at DESC
    """)
    
    orphans = []
    for r in rows:
        raw = r.get("raw_json") or {}
        orphans.append({
            "entry_id": r["id"],
            "tm": raw.get("tm"),
            "vision_done": raw.get("vision_done", False),
            "hero": raw.get("hero"),
            "file_meta": raw.get("file_meta", {}),
            "created_at": str(r["created_at"]) if r.get("created_at") else None,
        })
    
    return orphans


@router.post("/rematch")
async def rematch_screenshots(
    current_user=Depends(require_auth),
):
    """
    Re-tenta match de screenshots órfãos com mãos de MTT existentes.
    Útil após importar novas HH.
    """
    # Buscar mãos sem screenshot
    hands_without = query(
        "SELECT id, tm_number FROM mtt_hands WHERE has_screenshot = false"
    )
    
    matched = 0
    villains_created = 0
    
    conn = get_conn()
    try:
        for h in hands_without:
            screenshot = _match_screenshot(h["tm_number"])
            if not screenshot:
                continue
            
            with conn.cursor() as cur:
                cur.execute(
                    """UPDATE mtt_hands 
                       SET has_screenshot = true, screenshot_entry_id = %s 
                       WHERE id = %s""",
                    (screenshot["entry_id"], h["id"])
                )
            
            # Buscar dados completos da mão para criar villains
            hand_rows = query(
                "SELECT * FROM mtt_hands WHERE id = %s",
                (h["id"],)
            )
            if hand_rows:
                hand_data = dict(hand_rows[0])
                # Reconstruir vpip_seats a partir do raw
                raw = hand_data.get("raw", "")
                if raw:
                    parsed = _parse_mtt_hand(raw)
                    if parsed and parsed.get("vpip_seats"):
                        n = _create_villains_for_hand(conn, h["id"], parsed, screenshot)
                        villains_created += n
            
            matched += 1
        
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
        "total_without_screenshot": len(hands_without),
    }
