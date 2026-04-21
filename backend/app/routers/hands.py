from fastapi import APIRouter, Depends, Query, HTTPException
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
import logging
from app.auth import require_auth
from app.db import query, execute, execute_returning, get_conn

router = APIRouter(prefix="/api/hands", tags=["hands"])
logger = logging.getLogger("hands")


# ── Schema migration ────────────────────────────────────────────────────────

def ensure_hm3_tags_column():
    """
    Garante que a coluna hm3_tags (TEXT[]) existe na tabela hands.
    Criada em v9 para separar tags reais do HM3 das auto-geradas (showdown, nicks).
    """
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                ALTER TABLE hands
                ADD COLUMN IF NOT EXISTS hm3_tags TEXT[]
            """)
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_hands_hm3_tags
                ON hands USING GIN (hm3_tags)
            """)
        conn.commit()
    except Exception as e:
        conn.rollback()
        logger.warning(f"ensure_hm3_tags_column: {e}")
    finally:
        conn.close()


def ensure_has_showdown_column():
    """
    Garante que hands.has_showdown (BOOLEAN DEFAULT FALSE) existe.
    Preenchido ao inserir/actualizar mãos em que algum jogador não-hero
    mostrou cartas. Usado para priorizar mãos com showdown no estudo/villains.
    """
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                ALTER TABLE hands
                ADD COLUMN IF NOT EXISTS has_showdown BOOLEAN DEFAULT FALSE
            """)
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_hands_has_showdown
                ON hands(has_showdown) WHERE has_showdown = TRUE
            """)
        conn.commit()
    except Exception as e:
        conn.rollback()
        logger.warning(f"ensure_has_showdown_column: {e}")
    finally:
        conn.close()


def ensure_discord_tags_column():
    """
    Garante que hands.discord_tags (TEXT[]) existe.
    Preenchido quando a mão foi partilhada num canal Discord de estudo
    (ex: tag 'nota' → canal #nota). Usado para elegibilidade de villains
    e para badges de origem na UI.
    """
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                ALTER TABLE hands
                ADD COLUMN IF NOT EXISTS discord_tags TEXT[] DEFAULT ARRAY[]::text[]
            """)
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_hands_discord_tags
                ON hands USING GIN (discord_tags)
            """)
        conn.commit()
    except Exception as e:
        conn.rollback()
        logger.warning(f"ensure_discord_tags_column: {e}")
    finally:
        conn.close()


def ensure_origin_column():
    """
    Garante que hands.origin (TEXT) existe.
    Indica a fonte da mão: 'hm3' (script .bat), 'discord' (bot),
    'ss_upload' (upload manual SS), 'hh_import' (upload ZIP/TXT HH).
    Validação dos valores fica na camada aplicacional (sem CHECK constraint).
    """
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                ALTER TABLE hands
                ADD COLUMN IF NOT EXISTS origin TEXT
            """)
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_hands_origin
                ON hands(origin)
            """)
        conn.commit()
    except Exception as e:
        conn.rollback()
        logger.warning(f"ensure_origin_column: {e}")
    finally:
        conn.close()


def ensure_buy_in_column():
    """
    Garante que hands.buy_in (NUMERIC(10,2)) existe.
    Valor em unidades da moeda do torneio (sem conversão). Extraído do HH
    pelo parser da sala; NULL quando desconhecido. Usado no header do torneio
    na UI e em agregações por torneio.
    """
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                ALTER TABLE hands
                ADD COLUMN IF NOT EXISTS buy_in NUMERIC(10,2)
            """)
        conn.commit()
    except Exception as e:
        conn.rollback()
        logger.warning(f"ensure_buy_in_column: {e}")
    finally:
        conn.close()


# ── Lista das tags reais do HM3 (para migração retroactiva) ─────────────────
# Obtida via scan directo à BD HM3 (handmarkcategories).
# Cada entrada: (category_id, description).
HM3_REAL_TAGS = [
    (1,  "For Review"),
    (5,  "RFI PKO+"),
    (6,  "RFI PKO-"),
    (7,  "nota++"),
    (8,  "nota"),
    (9,  "PKO pos"),
    (10, "MW OP"),
    (11, "MW IP"),
    (12, "ICM"),
    (13, "ICM PKO"),
    (14, "PKO SS"),
    (15, "Timetell"),
    (16, "GTw"),
    (17, "Bvb pre"),
    (18, "bvB pre"),
    (19, "Bvb pos"),
    (20, "cbet OP PKO+"),
    (22, "OP vs 3bet"),
    (23, "IP vs 3bet"),
    (24, "OP vs 3bet PKO"),
    (25, "IP vs 3bet PKO"),
    (26, "SQZ PKO"),
    (27, "SQZ"),
    (28, "vs Turn cbet OP"),
    (30, "Turn Cbet IP"),
    (32, "Flop Cbet IP PKO- ES"),
    (33, "Flop Cbet IP PKO- MS"),
    (34, "Flop Cbet IP PKO- LS"),
    (35, "probe MW"),
    (36, "stats"),
    (37, "cc/3b IP PKO +"),
    (38, "cc/3b IP PKO-"),
    (39, "Turn cbet IP"),
    (40, "IP vs mcbet Flop"),
    (41, "IP vs mcbet Flop PKO"),
    (42, "OP vs cbet Flop PKO+"),
    (43, "OP vs cbet Flop PKO -"),
    (44, "OP vs Cbet PKO 3bet"),
    (45, "RFI PKO LS"),
    (46, "Stats"),
    (47, "perceived range river forte"),
    (48, "spots do pisso river q devia r"),
    (49, "RFI FT"),
    (50, "MW"),
    (51, "MW PKO"),
    (53, "prbe PKO"),
    (54, "bvB PKO PRE"),
    (55, "Bvb PKO pre"),
    (56, "bvB PKO pos"),
    (57, "Bvb PKO pos"),
    (58, "CC vs SQZ PKO"),
    (59, "OR vs SQZ PKO"),
    (60, "OR vs SQZ"),
    (61, "CC vs SQZ"),
    (62, "SB vs Steal"),
    (63, "SB vs Steal PKO"),
    (64, "SB vs Steal LS"),
    (65, "SB vs Steal PKO LS"),
    (66, "PKO pos 3bet"),
    (67, "GTw 3bet"),
    (68, "SB SS vs open"),
    (69, "chat"),
    (70, "bvb pos"),
    (71, "BB SS vs cbet"),
    (72, "BB SS vs CBET PKO"),
    (73, "BB vs SS CBET"),
    (74, "BB vs SS CBET PKO"),
    (75, "cbet OP"),
    (77, "bet vs mcbet"),
    (78, "3b pos flop mono"),
    (79, "nando"),
    (80, "analise field"),
    (81, "nota ex"),
]

# Set de nomes de tags HM3 para match rápido
HM3_REAL_TAG_NAMES = {name for _, name in HM3_REAL_TAGS}


class HandCreate(BaseModel):
    site:       Optional[str] = None
    hand_id:    Optional[str] = None
    played_at:  Optional[str] = None   # ISO datetime string
    stakes:     Optional[str] = None
    position:   Optional[str] = None
    hero_cards: Optional[list[str]] = None
    board:      Optional[list[str]] = None
    result:     Optional[float] = None
    currency:   Optional[str] = None
    notes:      Optional[str] = None
    tags:       Optional[list[str]] = None
    raw:        Optional[str] = None   # HH original


class HandUpdate(BaseModel):
    notes:       Optional[str] = None
    tags:        Optional[list[str]] = None
    hm3_tags:    Optional[list[str]] = None
    position:    Optional[str] = None
    study_state: Optional[str] = None


def _build_conditions(
    site, tag, study_state, position, search, date_from,
    exclude_mtt_only: bool = False,
    result_min: float = None,
    result_max: float = None,
    source: str = None,
    villain: str = None,
    date_to: str = None,
    hm3_tag: str = None,
    has_showdown: Optional[bool] = None,
):
    """Constrói lista de condições SQL e parâmetros para filtros de mãos."""
    conditions = []
    params = []

    if site:
        conditions.append("h.site = %s")
        params.append(site)

    if tag:
        if tag == '__none__':
            conditions.append("(h.tags IS NULL OR h.tags = '{}')")
        else:
            conditions.append("%s = ANY(h.tags)")
            params.append(tag)

    if hm3_tag:
        conditions.append("%s = ANY(h.hm3_tags)")
        params.append(hm3_tag)

    if study_state:
        conditions.append("h.study_state = %s")
        params.append(study_state)

    if position:
        conditions.append("h.position = %s")
        params.append(position)

    if search:
        conditions.append("(h.notes ILIKE %s OR h.raw ILIKE %s OR h.hand_id ILIKE %s OR h.stakes ILIKE %s OR h.all_players_actions::text ILIKE %s)")
        like = f"%{search}%"
        params.extend([like, like, like, like, like])

    if date_from:
        conditions.append("h.played_at >= %s")
        params.append(date_from)

    if date_to:
        conditions.append("h.played_at <= %s")
        params.append(date_to + ' 23:59:59')

    if result_min is not None:
        conditions.append("(h.result >= %s OR h.result <= %s)")
        params.append(result_min)
        params.append(-abs(result_min))

    if result_max is not None:
        conditions.append("(h.result <= %s AND h.result >= %s)")
        params.append(result_max)
        params.append(-abs(result_max))

    if exclude_mtt_only:
        conditions.append(
            "(h.tags IS NULL OR h.tags = '{}' OR NOT (h.tags = ARRAY['mtt']::text[]))"
        )

    if source:
        conditions.append("e.source = %s")
        params.append(source)

    if villain:
        conditions.append("h.all_players_actions ? %s")
        params.append(villain)

    if has_showdown is True:
        conditions.append("h.has_showdown = TRUE")
    elif has_showdown is False:
        conditions.append("(h.has_showdown = FALSE OR h.has_showdown IS NULL)")

    return conditions, params


@router.get("")
def list_hands(
    site:             Optional[str] = Query(None),
    tag:              Optional[str] = Query(None, description="Filtrar por tag (na coluna tags)"),
    hm3_tag:          Optional[str] = Query(None, description="Filtrar por tag HM3 (na coluna hm3_tags)"),
    study_state:      Optional[str] = Query(None, description="Filtrar por estado de estudo"),
    position:         Optional[str] = Query(None, description="Filtrar por posição"),
    search:           Optional[str] = Query(None, description="Pesquisa livre em notas/raw"),
    date_from:        Optional[str] = Query(None, description="Filtrar por data (ISO date, ex: 2026-03-20)"),
    date_to:          Optional[str] = Query(None, description="Filtrar até data (ISO date)"),
    result_min:       Optional[float] = Query(None, description="Resultado mínimo em BB"),
    result_max:       Optional[float] = Query(None, description="Resultado máximo em BB"),
    exclude_mtt_only: bool = Query(False, description="Excluir mãos que só têm tag #mtt"),
    include_archive:  bool = Query(False, description="Incluir mãos de arquivo MTT (mtt_archive)"),
    source:           Optional[str] = Query(None, description="Filtrar por source da entry (ex: discord)"),
    villain:          Optional[str] = Query(None, description="Filtrar por vilão (nick exacto em all_players_actions)"),
    has_showdown:     Optional[bool] = Query(None, description="Filtrar por has_showdown (true/false)"),
    page:             int = Query(1, ge=1),
    page_size:        int = Query(50, ge=1, le=2000),
    current_user=Depends(require_auth)
):
    conditions, params = _build_conditions(
        site, tag, study_state, position, search, date_from, exclude_mtt_only,
        result_min, result_max, source=source, villain=villain, date_to=date_to,
        hm3_tag=hm3_tag, has_showdown=has_showdown,
    )
    # Excluir arquivo MTT por defeito (a não ser que pedido explicitamente ou filtrado por study_state)
    if not include_archive and study_state != 'mtt_archive':
        conditions.append("h.study_state != 'mtt_archive'")
    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""

    total = query(
        f"""SELECT COUNT(*) AS total FROM hands h
            LEFT JOIN entries e ON h.entry_id = e.id
            LEFT JOIN discord_sync_state d ON e.discord_channel = d.channel_id
            {where}""",
        params
    )[0]["total"]
    offset = (page - 1) * page_size

    rows = query(
        f"""
        SELECT h.id, h.site, h.hand_id, h.played_at, h.stakes, h.position,
               h.hero_cards, h.board, h.result, h.currency, h.notes, h.tags, h.hm3_tags,
               h.study_state, h.entry_id, h.viewed_at, h.studied_at, h.created_at,
               h.all_players_actions, h.screenshot_url, h.player_names,
               e.discord_channel, e.discord_posted_at,
               d.channel_name AS discord_channel_name
        FROM hands h
        LEFT JOIN entries e ON h.entry_id = e.id
        LEFT JOIN discord_sync_state d ON e.discord_channel = d.channel_id
        {where}
        ORDER BY h.played_at DESC NULLS LAST, h.id DESC
        LIMIT %s OFFSET %s
        """,
        params + [page_size, offset]
    )

    return {
        "total":     total,
        "page":      page,
        "page_size": page_size,
        "pages":     (total + page_size - 1) // page_size,
        "data":      [dict(r) for r in rows],
    }


@router.get("/tag-groups")
def tag_groups(
    site:             Optional[str] = Query(None),
    study_state:      Optional[str] = Query(None),
    position:         Optional[str] = Query(None),
    search:           Optional[str] = Query(None),
    date_from:        Optional[str] = Query(None),
    exclude_mtt_only: bool = Query(False, description="Excluir mãos que só têm tag #mtt"),
    include_archive:  bool = Query(False, description="Incluir mãos de arquivo MTT"),
    use_hm3_tags:     bool = Query(False, description="Agrupar por hm3_tags em vez de tags"),
    has_showdown:     Optional[bool] = Query(None, description="Filtrar por has_showdown (true/false)"),
    current_user=Depends(require_auth)
):
    """Devolve grupos de tags com contagens, wins/losses e resultado total em BB.

    Se use_hm3_tags=true, usa coluna hm3_tags (tags reais HM3) e IGNORA mãos sem hm3_tags.
    """
    conditions, params = _build_conditions(
        site, None, study_state, position, search, date_from, exclude_mtt_only,
        has_showdown=has_showdown,
    )
    # Excluir arquivo MTT por defeito
    if not include_archive and study_state != 'mtt_archive':
        conditions.append("h.study_state != 'mtt_archive'")

    tag_col = "hm3_tags" if use_hm3_tags else "tags"

    # Quando use_hm3_tags=true, só queremos mãos que TÊM pelo menos uma hm3_tag
    if use_hm3_tags:
        conditions.append("h.hm3_tags IS NOT NULL AND array_length(h.hm3_tags, 1) > 0")

    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""

    rows = query(
        f"SELECT h.id, h.{tag_col} AS tags, h.result, h.study_state FROM hands h {where} ORDER BY h.played_at DESC NULLS LAST",
        params
    )

    # Group by sorted tag combination
    groups = {}  # tagKey -> {tags, count, wins, losses, total_bb}
    no_tag = {"tags": [], "count": 0, "wins": 0, "losses": 0, "total_bb": 0.0}

    for r in rows:
        tags = r["tags"] or []
        result = float(r["result"] or 0.0)
        win = 1 if result > 0 else 0
        loss = 1 if result < 0 else 0

        if not tags:
            no_tag["count"] += 1
            no_tag["wins"] += win
            no_tag["losses"] += loss
            no_tag["total_bb"] += result
        else:
            key = "+".join(sorted(tags))
            if key not in groups:
                groups[key] = {"tags": sorted(tags), "count": 0, "wins": 0, "losses": 0, "total_bb": 0.0}
            groups[key]["count"] += 1
            groups[key]["wins"] += win
            groups[key]["losses"] += loss
            groups[key]["total_bb"] += result

    # Sort by count desc
    sorted_groups = sorted(groups.values(), key=lambda g: g["count"], reverse=True)
    if no_tag["count"] > 0:
        sorted_groups.append(no_tag)

    return {"groups": sorted_groups, "total": len(rows)}


@router.get("/stats")
def hand_stats(current_user=Depends(require_auth)):
    """Estatísticas globais das mãos (exclui arquivo MTT).

    Inclui:
      - total/new/review/studying/resolved — contadores por estado
      - new_this_week — mãos criadas nos últimos 7 dias
      - recent — 5 últimas mãos importadas (por created_at)
    """
    rows = query("""
        SELECT
            COUNT(*) FILTER (WHERE study_state != 'mtt_archive') AS total,
            COUNT(*) FILTER (WHERE study_state = 'new') AS new,
            COUNT(*) FILTER (WHERE study_state = 'review') AS review,
            COUNT(*) FILTER (WHERE study_state = 'studying') AS studying,
            COUNT(*) FILTER (WHERE study_state = 'resolved') AS resolved,
            COUNT(*) FILTER (WHERE study_state = 'mtt_archive') AS mtt_archive,
            COUNT(*) FILTER (
                WHERE study_state != 'mtt_archive'
                  AND created_at >= NOW() - INTERVAL '7 days'
            ) AS new_this_week,
            COUNT(DISTINCT site) FILTER (WHERE study_state != 'mtt_archive') AS sites,
            COUNT(DISTINCT position) FILTER (WHERE position IS NOT NULL AND study_state != 'mtt_archive') AS positions
        FROM hands
    """)
    result = dict(rows[0]) if rows else {}

    # 5 últimas mãos importadas (excluindo bulk MTT e GG sem match SS)
    # Mãos GG sem match SS têm nicks anonimizados (hashes GG tipo "9e7ff3a8")
    # e não fazem sentido para estudo. São detectadas por:
    #   - site contém "GG" E
    #   - player_names->>'match_method' é NULL (nunca passou pelo _promote_to_study)
    recent_rows = query("""
        SELECT id, site, hand_id, played_at, stakes, position,
               hero_cards, board, result, currency, study_state,
               tags, hm3_tags, created_at
        FROM hands
        WHERE study_state != 'mtt_archive'
          AND NOT (
              site ILIKE '%GG%'
              AND (player_names IS NULL OR player_names->>'match_method' IS NULL)
          )
        ORDER BY created_at DESC, id DESC
        LIMIT 5
    """)
    result["recent"] = [dict(r) for r in recent_rows]

    # Screenshot stats — "orphan_screenshots" inclui:
    #   - entries screenshot (upload manual) sem mão criada
    #   - mãos GGDiscord (placeholder Discord SS sem HH)
    # Tudo é "SS sem match" para o utilizador, sem distinção visual no Dashboard.
    try:
        ss_rows = query("""
            SELECT
                COUNT(*) AS total_screenshots,
                COUNT(*) FILTER (
                    WHERE status = 'new'
                      AND NOT EXISTS (SELECT 1 FROM mtt_hands m WHERE m.screenshot_entry_id = e.id)
                      AND NOT EXISTS (SELECT 1 FROM hands h WHERE h.entry_id = e.id)
                ) AS orphan_ss_only
            FROM entries e
            WHERE entry_type = 'screenshot'
        """)
        orphan_ss = ss_rows[0]["orphan_ss_only"] if ss_rows else 0
        result["total_screenshots"] = ss_rows[0]["total_screenshots"] if ss_rows else 0
    except Exception:
        orphan_ss = 0
        result["total_screenshots"] = 0

    try:
        gd_rows = query("""
            SELECT COUNT(*) AS n FROM hands WHERE 'GGDiscord' = ANY(hm3_tags)
        """)
        gg_discord = gd_rows[0]["n"] if gd_rows else 0
    except Exception:
        gg_discord = 0

    # Contagem unificada — o que o painel "Sem match" do Dashboard mostra
    result["orphan_screenshots"] = orphan_ss + gg_discord

    return result


@router.get("/{hand_pk}")
def get_hand(hand_pk: int, current_user=Depends(require_auth)):
    rows = query("""
        SELECT h.*, e.discord_channel, e.discord_posted_at,
               d.channel_name AS discord_channel_name
        FROM hands h
        LEFT JOIN entries e ON h.entry_id = e.id
        LEFT JOIN discord_sync_state d ON e.discord_channel = d.channel_id
        WHERE h.id = %s
    """, (hand_pk,))
    if not rows:
        raise HTTPException(status_code=404, detail="Mão não encontrada")

    hand = dict(rows[0])

    # Marcar como vista se ainda não foi
    if not hand.get("viewed_at"):
        execute(
            "UPDATE hands SET viewed_at = NOW() WHERE id = %s",
            (hand_pk,)
        )
        hand["viewed_at"] = datetime.utcnow().isoformat()

    return hand


@router.post("")
def create_hand(body: HandCreate, current_user=Depends(require_auth)):
    row = execute_returning(
        """
        INSERT INTO hands
            (site, hand_id, played_at, stakes, position, hero_cards,
             board, result, currency, notes, tags, raw, study_state)
        VALUES
            (%(site)s, %(hand_id)s, %(played_at)s, %(stakes)s, %(position)s,
             %(hero_cards)s, %(board)s, %(result)s, %(currency)s,
             %(notes)s, %(tags)s, %(raw)s, 'new')
        RETURNING id, created_at
        """,
        body.model_dump()
    )
    return {"id": row["id"], "created_at": row["created_at"]}


@router.patch("/{hand_pk}")
def update_hand(hand_pk: int, body: HandUpdate, current_user=Depends(require_auth)):
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    if not updates:
        raise HTTPException(status_code=400, detail="Nada para actualizar")

    # Se mudar para 'resolved', registar studied_at
    if updates.get("study_state") == "resolved":
        updates["studied_at"] = datetime.utcnow()

    set_clause = ", ".join(f"{k} = %({k})s" for k in updates)
    updates["hand_pk"] = hand_pk

    execute(
        f"UPDATE hands SET {set_clause} WHERE id = %(hand_pk)s",
        updates
    )
    return {"ok": True}


@router.delete("/{hand_pk}")
def delete_hand(hand_pk: int, current_user=Depends(require_auth)):
    execute("DELETE FROM hands WHERE id = %s", (hand_pk,))
    return {"ok": True}


@router.get("/{hand_pk}/screenshot")
def get_hand_screenshot(hand_pk: int, current_user=Depends(require_auth)):
    """Devolve a imagem do screenshot associado a uma mão (como data URL)."""
    rows = query(
        "SELECT entry_id, player_names FROM hands WHERE id = %s",
        (hand_pk,)
    )
    if not rows:
        raise HTTPException(status_code=404, detail="Mão não encontrada")

    hand = dict(rows[0])
    entry_id = hand.get("entry_id")
    player_names = hand.get("player_names") or {}

    # Fallback: entry_id pode estar no player_names
    if not entry_id:
        entry_id = player_names.get("screenshot_entry_id")

    if not entry_id:
        raise HTTPException(status_code=404, detail="Sem screenshot associado")

    entry_rows = query(
        "SELECT raw_json FROM entries WHERE id = %s",
        (entry_id,)
    )
    if not entry_rows:
        raise HTTPException(status_code=404, detail="Entry do screenshot não encontrado")

    raw = entry_rows[0].get("raw_json") or {}
    img_b64 = raw.get("img_b64", "")
    mime_type = raw.get("mime_type", "image/png")

    if not img_b64:
        raise HTTPException(status_code=404, detail="Imagem não disponível")

    return {
        "data_url": f"data:{mime_type};base64,{img_b64}",
        "entry_id": entry_id,
    }


# ── Admin endpoints ───────────────────────────────────────────────────────────

@router.post("/admin/reset-all")
def admin_reset_all(current_user=Depends(require_auth)):
    """Apaga TODAS as mãos, entries, e vilões. Reset total."""
    from app.db import get_conn
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM hand_villains")
            cur.execute("DELETE FROM hands")
            cur.execute("DELETE FROM entries")
            cur.execute("DELETE FROM villain_notes")
        conn.commit()
        return {"ok": True, "message": "BD limpa — todas as mãos, entries e vilões apagados"}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()


@router.post("/admin/reset-hm3")
def admin_reset_hm3(current_user=Depends(require_auth)):
    """Apaga apenas mãos HM3 (Winamax, PokerStars, WPN)."""
    from app.db import get_conn
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM hands WHERE site IN ('Winamax', 'PokerStars', 'WPN')")
            deleted = cur.rowcount
        conn.commit()
        return {"ok": True, "deleted": deleted, "message": f"{deleted} mãos HM3 apagadas"}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()


@router.post("/admin/reset-gg")
def admin_reset_gg(current_user=Depends(require_auth)):
    """Apaga mãos GGPoker e entries/screenshots associados."""
    from app.db import get_conn
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM hand_villains")
            cur.execute("DELETE FROM hands WHERE site = 'GGPoker'")
            deleted_hands = cur.rowcount
            cur.execute("DELETE FROM entries")
            deleted_entries = cur.rowcount
        conn.commit()
        return {"ok": True, "deleted_hands": deleted_hands, "deleted_entries": deleted_entries}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()


@router.post("/admin/reparse-gg")
def admin_reparse_gg(current_user=Depends(require_auth)):
    """
    Re-parseia mãos GGPoker existentes que têm raw mas faltam dados.
    Preenche hero_cards, board, position, result, all_players_actions com _meta.
    """
    import json as json_mod
    from app.parsers.gg_hands import parse_hands as gg_parse
    from app.db import get_conn

    # Fetch GG hands with raw but missing data
    rows = query(
        """SELECT id, hand_id, raw, hero_cards, board, position, result, all_players_actions, tags
           FROM hands
           WHERE site = 'GGPoker'
             AND raw IS NOT NULL AND raw != ''
             AND (hero_cards IS NULL OR hero_cards = '{}' 
                  OR all_players_actions IS NULL
                  OR NOT (all_players_actions ? '_meta'))
           ORDER BY id
           LIMIT 5000"""
    )

    if not rows:
        return {"processed": 0, "updated": 0, "message": "Nenhuma mão GG para re-parsear"}

    updated = 0
    errors = 0
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            for hand in rows:
                try:
                    raw = hand.get("raw", "")
                    if not raw or len(raw) < 50:
                        continue

                    # Re-parse the hand
                    parsed_list, errs = gg_parse(raw.encode("utf-8"), "reparse.txt")
                    if not parsed_list:
                        continue

                    parsed = parsed_list[0]
                    apa = parsed.get("all_players_actions") or {}

                    # Build update
                    updates = []
                    params = []

                    if parsed.get("hero_cards") and (not hand.get("hero_cards") or hand["hero_cards"] == []):
                        updates.append("hero_cards = %s")
                        params.append(parsed["hero_cards"])

                    if parsed.get("board") and (not hand.get("board") or hand["board"] == []):
                        updates.append("board = %s")
                        params.append(parsed["board"])

                    if parsed.get("position") and not hand.get("position"):
                        updates.append("position = %s")
                        params.append(parsed["position"])

                    if parsed.get("result") is not None and hand.get("result") is None:
                        updates.append("result = %s")
                        params.append(parsed["result"])

                    if parsed.get("stakes") and not hand.get("stakes"):
                        updates.append("stakes = %s")
                        params.append(parsed["stakes"])

                    if apa and "_meta" in apa:
                        # Merge with existing apa if any
                        existing_apa = hand.get("all_players_actions") or {}
                        if isinstance(existing_apa, str):
                            existing_apa = json_mod.loads(existing_apa)
                        # Only update if existing doesn't have _meta
                        if "_meta" not in existing_apa:
                            updates.append("all_players_actions = %s")
                            params.append(json_mod.dumps(apa))
                        elif not existing_apa.get("_meta", {}).get("bb"):
                            # _meta exists but bb is missing
                            existing_apa["_meta"] = apa["_meta"]
                            updates.append("all_players_actions = %s")
                            params.append(json_mod.dumps(existing_apa))

                    if updates:
                        params.append(hand["id"])
                        cur.execute(
                            f"UPDATE hands SET {', '.join(updates)} WHERE id = %s",
                            tuple(params)
                        )
                        updated += 1

                    if updated % 200 == 0 and updated > 0:
                        conn.commit()

                except Exception as e:
                    errors += 1
                    if errors < 5:
                        import logging
                        logging.getLogger("hands").warning(f"Reparse GG error hand {hand.get('id')}: {e}")

        conn.commit()
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Erro no reparse: {e}")
    finally:
        conn.close()

    return {
        "processed": len(rows),
        "updated": updated,
        "errors": errors,
    }


@router.post("/admin/promote-archive")
def admin_promote_archive(current_user=Depends(require_auth)):
    """Promove mãos com study_state='mtt_archive' para 'new'.

    Útil para corrigir mãos importadas via /api/import que foram
    inseridas com study_state errado (bug corrigido).
    """
    from app.db import get_conn
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE hands SET study_state = 'new' WHERE study_state = 'mtt_archive'"
            )
            updated = cur.rowcount
        conn.commit()
        return {"ok": True, "promoted": updated, "message": f"{updated} mãos promovidas de mtt_archive para new"}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()


@router.post("/admin/delete-before-2026")
def admin_delete_before_2026(current_user=Depends(require_auth)):
    """Apaga todas as maos jogadas antes de 2026-01-01 (estudo + arquivo)."""
    from app.db import get_conn
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM hand_villains WHERE hand_db_id IN (SELECT id FROM hands WHERE played_at < '2026-01-01')")
            villains_deleted = cur.rowcount
            cur.execute("DELETE FROM hands WHERE played_at < '2026-01-01'")
            hands_deleted = cur.rowcount
        conn.commit()
        return {"ok": True, "hands_deleted": hands_deleted, "villains_deleted": villains_deleted}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()


@router.post("/admin/tag-gg-hands")
def admin_tag_gg_hands(current_user=Depends(require_auth)):
    """
    Adiciona 'GG Hands' ao hm3_tags de todas as mãos GGPoker em `hands`.
    Corre uma vez depois da migração para apanhar as mãos promovidas pelo pipeline antigo
    (que gravava em `tags` em vez de `hm3_tags`).
    """
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE hands
                SET hm3_tags = CASE
                    WHEN hm3_tags IS NULL THEN ARRAY['GG Hands']::text[]
                    WHEN NOT ('GG Hands' = ANY(hm3_tags)) THEN hm3_tags || ARRAY['GG Hands']::text[]
                    ELSE hm3_tags
                END
                WHERE site = 'GGPoker'
            """)
            updated = cur.rowcount
        conn.commit()
        return {"ok": True, "updated": updated}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()


@router.post("/admin/delete-gg-without-screenshot")
def admin_delete_gg_no_ss(current_user=Depends(require_auth)):
    """
    Apaga mãos GGPoker da tabela `hands` que não têm screenshot nem vêm do HM3.
    Estas mãos são bulk (vieram de import de ZIP HH) e duplicam o que está em mtt_hands.
    A arquitectura correcta é:
      - mtt_hands guarda TODAS as GG
      - hands só tem GG que foram promovidas (por match de SS)
    """
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            # Contar antes
            cur.execute("""
                SELECT COUNT(*) AS n FROM hands
                WHERE site = 'GGPoker'
                  AND (screenshot_url IS NULL OR screenshot_url = '')
                  AND (player_names IS NULL OR player_names::text IN ('null', '{}'))
            """)
            to_delete = cur.fetchone()["n"]

            # Apagar
            cur.execute("""
                DELETE FROM hands
                WHERE site = 'GGPoker'
                  AND (screenshot_url IS NULL OR screenshot_url = '')
                  AND (player_names IS NULL OR player_names::text IN ('null', '{}'))
            """)
            deleted = cur.rowcount
        conn.commit()
        return {"ok": True, "to_delete_estimate": to_delete, "deleted": deleted}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()


@router.post("/admin/migrate-hm3-tags")
def admin_migrate_hm3_tags(current_user=Depends(require_auth)):
    """
    Migração retroactiva: para cada mão, separa em duas colunas:
    - hm3_tags: tags que batem com HM3_REAL_TAG_NAMES
    - tags: apenas as que NÃO batem (auto-geradas: showdown, nicks de vilões)
    Corre uma vez depois de aplicar a coluna hm3_tags.
    """
    conn = get_conn()
    try:
        # Lê todas as mãos que ainda não têm hm3_tags populado
        rows = query(
            """
            SELECT id, tags FROM hands
            WHERE tags IS NOT NULL AND array_length(tags, 1) > 0
              AND (hm3_tags IS NULL OR array_length(hm3_tags, 1) IS NULL)
            """
        )
        total = len(rows)
        updated = 0
        unchanged = 0

        with conn.cursor() as cur:
            for row in rows:
                old_tags = row["tags"] or []
                hm3 = [t for t in old_tags if t in HM3_REAL_TAG_NAMES]
                auto = [t for t in old_tags if t not in HM3_REAL_TAG_NAMES]
                if hm3:
                    cur.execute(
                        "UPDATE hands SET hm3_tags = %s, tags = %s WHERE id = %s",
                        (hm3, auto, row["id"])
                    )
                    updated += 1
                else:
                    unchanged += 1
        conn.commit()
        logger.info(f"[migrate-hm3-tags] total={total} updated={updated} unchanged={unchanged}")
        return {
            "ok": True,
            "total_scanned": total,
            "updated": updated,
            "unchanged_no_hm3_match": unchanged,
            "hm3_tags_list_size": len(HM3_REAL_TAG_NAMES),
        }
    except Exception as e:
        conn.rollback()
        logger.error(f"[migrate-hm3-tags] Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()


@router.get("/admin/scope-anonmap-bug")
def admin_scope_anonmap_bug(current_user=Depends(require_auth)):
    """
    DIAGNÓSTICO (read-only).

    Conta mãos GG onde o matching Vision↔raw colocou a metadata do
    all_players_actions (bb/sb/ante/level) com chave de nome de jogador,
    e o nome de um jogador real com chave '_meta'. Sintoma:

      all_players_actions._meta  → undefined (em vez de dict)
      all_players_actions.<nick> → {bb, sb, ante, level, ...} (em vez de dados do jogador)
      player_names.anon_map._meta → string com nome de jogador

    Devolve: total GG com SS, nº afectadas, até 5 exemplos (id + hero + nick_fantasma).
    NÃO MODIFICA NADA.
    """
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            # Total de mãos GG promovidas (com player_names populado)
            cur.execute("""
                SELECT COUNT(*) AS n FROM hands
                WHERE site = 'GGPoker'
                  AND player_names IS NOT NULL
                  AND player_names::text NOT IN ('null', '{}')
            """)
            total_gg = cur.fetchone()["n"]

            # Afectadas: anon_map tem chave '_meta' cujo valor é string (nick)
            # em vez de dict (metadata). Usamos JSONB path para inspeccionar.
            cur.execute("""
                SELECT id, hand_id, hero_cards,
                       player_names->'anon_map'->>'_meta' AS ghost_nick,
                       played_at, stakes
                FROM hands
                WHERE site = 'GGPoker'
                  AND player_names IS NOT NULL
                  AND player_names->'anon_map' ? '_meta'
                  AND jsonb_typeof(player_names->'anon_map'->'_meta') = 'string'
                ORDER BY played_at DESC NULLS LAST
                LIMIT 5000
            """)
            affected_rows = cur.fetchall()
            affected_count = len(affected_rows)

            # Amostra (5 exemplos)
            examples = [
                {
                    "id": r["id"],
                    "hand_id": r["hand_id"],
                    "hero_cards": r["hero_cards"],
                    "ghost_nick": r["ghost_nick"],
                    "played_at": r["played_at"].isoformat() if r["played_at"] else None,
                    "stakes": r["stakes"],
                }
                for r in affected_rows[:5]
            ]

            # Contagem cruzada: destes, quantos também têm o sintoma no all_players_actions
            # (chave do nick fantasma existe como "player" com bb/sb/ante em vez de seat/stack)
            cur.execute("""
                SELECT COUNT(*) AS n FROM hands
                WHERE site = 'GGPoker'
                  AND player_names IS NOT NULL
                  AND player_names->'anon_map' ? '_meta'
                  AND jsonb_typeof(player_names->'anon_map'->'_meta') = 'string'
                  AND all_players_actions IS NOT NULL
                  AND NOT (all_players_actions ? '_meta')
            """)
            apa_without_meta = cur.fetchone()["n"]

        return {
            "ok": True,
            "total_gg_with_screenshot": total_gg,
            "affected_count": affected_count,
            "affected_pct": round(100 * affected_count / total_gg, 1) if total_gg else 0,
            "apa_missing_meta": apa_without_meta,
            "examples": examples,
        }
    except Exception as e:
        logger.error(f"[scope-anonmap-bug] Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()


# ─────────────────────────────────────────────────────────────────────────────
# REFIX anon-map bug — re-aplica matching correcto às 42 mãos afectadas.
#
# Contexto: a Fase 3 do matching em screenshot.py (`_build_anon_to_real_map`)
# iterava sobre a chave '_meta' de all_players_actions como se fosse jogador.
# Resultado: em mãos com observador no SS, o dict _meta (bb/sb/ante/level)
# ficava gravado sob uma chave de nick, e o _meta real desaparecia.
#
# Este endpoint:
#   1. Encontra as mãos afectadas (mesmo critério de scope-anonmap-bug)
#   2. Para cada uma: restaura _meta no seu sítio, apaga entrada fantasma
#   3. Re-corre _build_anon_to_real_map + _enrich_all_players_actions (já fixos)
#      usando o players_list guardado em player_names (offline, sem chamar Vision)
#   4. Grava all_players_actions e player_names.anon_map actualizados
#
# Tem preview (GET) e execute (POST con confirm=true).
# ─────────────────────────────────────────────────────────────────────────────

def _restore_apa_meta(apa: dict, player_names: dict) -> tuple[dict, str | None]:
    """
    Desfaz o swap:
      - Lê ghost_nick = anon_map['_meta']
      - Se all_players_actions[ghost_nick] é dict com chaves de metadata
        (bb, sb ou ante), move-o para _meta e apaga a chave ghost_nick
    Devolve (apa_corrigido, ghost_nick) — ghost_nick é None se não aplicável.
    """
    if not isinstance(apa, dict) or not isinstance(player_names, dict):
        return apa, None

    anon_map = player_names.get("anon_map") or {}
    ghost_nick = anon_map.get("_meta")
    if not isinstance(ghost_nick, str):
        return apa, None

    # Se o apa já tem _meta correcto, não fazemos nada
    if isinstance(apa.get("_meta"), dict) and any(
        k in apa["_meta"] for k in ("bb", "sb", "ante", "level")
    ):
        return apa, None

    # Procurar o dict de metadata escondido sob ghost_nick
    hidden = apa.get(ghost_nick)
    if not isinstance(hidden, dict):
        return apa, None
    # Validar que parece mesmo metadata (não um jogador normal)
    is_metadata = any(k in hidden for k in ("bb", "sb", "ante", "level")) and \
                  "seat" not in hidden and "stack" not in hidden
    if not is_metadata:
        return apa, None

    new_apa = {k: v for k, v in apa.items() if k != ghost_nick}
    new_apa["_meta"] = hidden
    return new_apa, ghost_nick


@router.get("/admin/refix-anonmap-bug/preview")
def admin_refix_anonmap_preview(current_user=Depends(require_auth)):
    """
    DRY-RUN. Mostra para cada mão afectada o que seria alterado.
    Não grava nada.

    Estratégia (v2):
      1. Reparsear a HH raw para obter all_players_actions PRE-ENRICH
         (chaves = hashes GG, não nicks reais). Usa parsers.gg_hands.
      2. Carregar raw_vision do entry do SS, reparsear com o novo parser
         (aceita formato BB e fichas) e normalizar stacks com bb_size da HH.
      3. Correr _build_anon_to_real_map + _enrich_all_players_actions.
      4. Resultado: anon_map com {hash: nick_real} correctamente, all_players_actions com nicks como chaves.
    """
    from app.routers.screenshot import (
        _build_anon_to_real_map,
        _enrich_all_players_actions,
        _parse_vision_response,
        _normalize_vision_stacks,
        _parse_hh_stacks_and_blinds,
    )
    from app.parsers.gg_hands import parse_hands as gg_parse_hands

    rows = query(
        """
        SELECT h.id, h.hand_id, h.raw, h.all_players_actions, h.player_names,
               h.hero_cards, h.stakes, h.entry_id,
               e.raw_json AS entry_raw_json
        FROM hands h
        LEFT JOIN entries e ON e.id = h.entry_id
        WHERE h.site = 'GGPoker'
          AND h.player_names IS NOT NULL
          AND h.player_names->'anon_map' ? '_meta'
          AND jsonb_typeof(h.player_names->'anon_map'->'_meta') = 'string'
        ORDER BY h.played_at DESC NULLS LAST
        """
    )

    results = []
    skipped = []
    for r in rows:
        try:
            hand_db_id = r["id"]
            hand_id = r["hand_id"]
            raw_hh = r["raw"] or ""
            entry_rj = r["entry_raw_json"] or {}

            if not raw_hh:
                skipped.append({"id": hand_db_id, "hand_id": hand_id, "reason": "sem HH raw"})
                continue

            # ── Passo 1: reconstruir all_players_actions pre-enrich da HH raw ──
            # gg_parse_hands espera bytes; passamos o raw como bytes UTF-8.
            parsed_list, errors = gg_parse_hands(raw_hh.encode("utf-8"), f"hand_{hand_db_id}.txt")
            if not parsed_list:
                skipped.append({
                    "id": hand_db_id, "hand_id": hand_id,
                    "reason": f"reparse HH falhou: {errors[:3] if errors else 'sem resultado'}"
                })
                continue
            apa_pre_enrich = parsed_list[0].get("all_players_actions") or {}
            if not apa_pre_enrich:
                skipped.append({"id": hand_db_id, "hand_id": hand_id, "reason": "reparse HH sem all_players_actions"})
                continue

            # ── Passo 2: obter vision_data ──
            # Preferir reparsear raw_vision do entry (para apanhar stacks que o parser antigo zerou).
            vision_data = None
            raw_vision_text = entry_rj.get("raw_vision") if isinstance(entry_rj, dict) else None
            if raw_vision_text:
                vision_data = _parse_vision_response(raw_vision_text)
                # _parse_vision_response não devolve file_meta — mantemos do entry se existir
                if isinstance(entry_rj, dict):
                    vision_data["file_meta"] = entry_rj.get("file_meta") or {}
            else:
                # Fallback: usar player_names da mão (pode ter stacks a 0 se era formato BB)
                pn = r["player_names"] or {}
                vision_data = {
                    "hero": pn.get("hero"),
                    "vision_sb": pn.get("vision_sb"),
                    "vision_bb": pn.get("vision_bb"),
                    "players_list": pn.get("players_list") or [],
                    "players_by_position": pn.get("players_by_position") or {},
                    "file_meta": pn.get("file_meta") or {},
                }

            if not vision_data.get("players_list"):
                skipped.append({"id": hand_db_id, "hand_id": hand_id, "reason": "sem players_list Vision"})
                continue

            # Normalizar stacks (BB → fichas usando bb_size da HH)
            hh_data = _parse_hh_stacks_and_blinds(raw_hh)
            bb_size = (hh_data or {}).get("bb_size", 0)
            if bb_size:
                vision_data = _normalize_vision_stacks(vision_data, bb_size)

            # ── Passo 3: correr matching + enrich ──
            hand_row_pre = {
                "all_players_actions": apa_pre_enrich,
                "raw": raw_hh,
            }
            new_anon_map = _build_anon_to_real_map(hand_row_pre, vision_data)
            new_apa = _enrich_all_players_actions(apa_pre_enrich, new_anon_map, vision_data)

            # ── Resumo das mudanças ──
            old_apa = r["all_players_actions"] or {}
            old_pn = r["player_names"] or {}
            old_keys = sorted([k for k in old_apa.keys() if k != "_meta"])
            new_keys = sorted([k for k in new_apa.keys() if k != "_meta"])
            old_anon_map = old_pn.get("anon_map") or {}

            results.append({
                "id": hand_db_id,
                "hand_id": hand_id,
                "stakes": r["stakes"],
                "bb_size": bb_size,
                "had_raw_vision": bool(raw_vision_text),
                "meta_after": new_apa.get("_meta"),
                "apa_keys_before": old_keys,
                "apa_keys_after": new_keys,
                "anon_map_before": {k: v for k, v in old_anon_map.items()},
                "anon_map_after": new_anon_map,
                "mapped_count": len([k for k, v in new_anon_map.items() if k != "Hero"]),
                "hh_seat_count": len([k for k in apa_pre_enrich if k != "_meta"]),
            })
        except Exception as e:
            logger.error(f"[refix-preview] Hand {r['id']}: {e}")
            skipped.append({"id": r["id"], "hand_id": r["hand_id"], "reason": f"erro: {e}"})

    return {
        "ok": True,
        "total_affected": len(rows),
        "will_update": len(results),
        "will_skip": len(skipped),
        "skipped": skipped,
        "sample": results[:3],
        "all_hand_ids": [r["hand_id"] for r in results],
    }


@router.post("/admin/refix-anonmap-bug")
def admin_refix_anonmap_execute(
    confirm: bool = Query(False, description="Tem de ser true para executar"),
    current_user=Depends(require_auth),
):
    """
    EXECUÇÃO. Aplica o fix nas mãos afectadas. Requer ?confirm=true.

    Mesma lógica do /preview mas escreve:
      - all_players_actions (rebuild completo do pipeline)
      - player_names.anon_map (mapping correcto hash→nick)
      - player_names.players_list (normalizado com stacks em fichas)
    """
    if not confirm:
        raise HTTPException(
            status_code=400,
            detail="Adicionar ?confirm=true para executar. Corre o /preview primeiro."
        )

    from app.routers.screenshot import (
        _build_anon_to_real_map,
        _enrich_all_players_actions,
        _parse_vision_response,
        _normalize_vision_stacks,
        _parse_hh_stacks_and_blinds,
    )
    from app.parsers.gg_hands import parse_hands as gg_parse_hands

    rows = query(
        """
        SELECT h.id, h.hand_id, h.raw, h.player_names, h.entry_id,
               e.raw_json AS entry_raw_json
        FROM hands h
        LEFT JOIN entries e ON e.id = h.entry_id
        WHERE h.site = 'GGPoker'
          AND h.player_names IS NOT NULL
          AND h.player_names->'anon_map' ? '_meta'
          AND jsonb_typeof(h.player_names->'anon_map'->'_meta') = 'string'
        """
    )

    updated = 0
    skipped = []
    failed = []
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            for r in rows:
                try:
                    hand_db_id = r["id"]
                    raw_hh = r["raw"] or ""
                    entry_rj = r["entry_raw_json"] or {}

                    if not raw_hh:
                        skipped.append({"id": hand_db_id, "reason": "sem HH raw"})
                        continue

                    # Passo 1: reparse HH
                    parsed_list, _errs = gg_parse_hands(raw_hh.encode("utf-8"), f"hand_{hand_db_id}.txt")
                    if not parsed_list:
                        skipped.append({"id": hand_db_id, "reason": "reparse HH falhou"})
                        continue
                    apa_pre_enrich = parsed_list[0].get("all_players_actions") or {}
                    if not apa_pre_enrich:
                        skipped.append({"id": hand_db_id, "reason": "reparse sem APA"})
                        continue

                    # Passo 2: vision_data
                    raw_vision_text = entry_rj.get("raw_vision") if isinstance(entry_rj, dict) else None
                    if raw_vision_text:
                        vision_data = _parse_vision_response(raw_vision_text)
                        if isinstance(entry_rj, dict):
                            vision_data["file_meta"] = entry_rj.get("file_meta") or {}
                    else:
                        pn_old = r["player_names"] or {}
                        vision_data = {
                            "hero": pn_old.get("hero"),
                            "vision_sb": pn_old.get("vision_sb"),
                            "vision_bb": pn_old.get("vision_bb"),
                            "players_list": pn_old.get("players_list") or [],
                            "players_by_position": pn_old.get("players_by_position") or {},
                            "file_meta": pn_old.get("file_meta") or {},
                        }

                    if not vision_data.get("players_list"):
                        skipped.append({"id": hand_db_id, "reason": "sem players_list"})
                        continue

                    # Normalizar stacks
                    hh_data = _parse_hh_stacks_and_blinds(raw_hh)
                    bb_size = (hh_data or {}).get("bb_size", 0)
                    if bb_size:
                        vision_data = _normalize_vision_stacks(vision_data, bb_size)

                    # Passo 3: rebuild
                    hand_row_pre = {"all_players_actions": apa_pre_enrich, "raw": raw_hh}
                    new_anon_map = _build_anon_to_real_map(hand_row_pre, vision_data)
                    new_apa = _enrich_all_players_actions(apa_pre_enrich, new_anon_map, vision_data)

                    # Construir novo player_names
                    old_pn = r["player_names"] or {}
                    new_pn = dict(old_pn)
                    new_pn["anon_map"] = new_anon_map
                    new_pn["players_list"] = vision_data.get("players_list") or []
                    new_pn["hero"] = vision_data.get("hero") or old_pn.get("hero")
                    new_pn["vision_sb"] = vision_data.get("vision_sb") or old_pn.get("vision_sb")
                    new_pn["vision_bb"] = vision_data.get("vision_bb") or old_pn.get("vision_bb")
                    new_pn["match_method"] = "anchors_stack_elimination_v2_refix"

                    import json
                    cur.execute(
                        "UPDATE hands SET all_players_actions = %s::jsonb, player_names = %s::jsonb WHERE id = %s",
                        (json.dumps(new_apa), json.dumps(new_pn), hand_db_id)
                    )
                    updated += 1
                except Exception as e:
                    logger.error(f"[refix-execute] Hand {r['id']}: {e}")
                    failed.append({"id": r["id"], "error": str(e)})

        conn.commit()
        return {
            "ok": True,
            "total_scanned": len(rows),
            "updated": updated,
            "skipped_count": len(skipped),
            "skipped": skipped[:10],
            "failed_count": len(failed),
            "failed": failed[:10],
        }
    except Exception as e:
        conn.rollback()
        logger.error(f"[refix-execute] Rollback: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

