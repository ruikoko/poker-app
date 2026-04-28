import re
import json
from fastapi import APIRouter, Depends, Query, HTTPException
from pydantic import BaseModel
from typing import Optional
from app.auth import require_auth
from app.db import query, execute, execute_returning
from app.hero_names import FRIEND_NICKS

router = APIRouter(prefix="/api/villains", tags=["villains"])

# ── Friends / Hero nicks to exclude from villains ─────────────────────────────
# FRIEND_NICKS is imported from app.hero_names — it includes both the user's
# own hero accounts AND the team/friend group. Any nick in this set will be
# filtered out of the villain database.
# Match is case-insensitive and supports truncated names (starts-with).


def _is_friend(nick: str) -> bool:
    """Check if a nick belongs to the friend group (case-insensitive, supports truncated names)."""
    if not nick:
        return False
    lower = nick.lower().strip()
    if lower in FRIEND_NICKS:
        return True
    # Check truncated names (GG truncates with ..)
    clean = lower.rstrip('.')
    if clean in FRIEND_NICKS:
        return True
    # Check starts-with for truncated names
    for friend in FRIEND_NICKS:
        if len(friend) >= 6 and clean.startswith(friend[:6]):
            # Additional check: the friend nick starts with the same chars
            if friend.startswith(clean.rstrip('.')):
                return True
    return False


# ── VPIP SQL fragment ─────────────────────────────────────────────────────────
# Reusable SQL condition for VPIP filtering
# A player has VPIP if:
#   - Has 'actions' field with non-fold preflop, OR has flop/turn/river actions
#   - OR has no 'actions' field (old format) — include by default

VPIP_CONDITION = """
    (
        val->'actions' IS NULL
        OR val->'actions'->>'flop' IS NOT NULL
        OR val->'actions'->>'turn' IS NOT NULL
        OR val->'actions'->>'river' IS NOT NULL
        OR (
            val->'actions'->>'preflop' IS NOT NULL
            AND val->'actions'->>'preflop' NOT LIKE '%%fold%%'
            AND val->'actions'->>'preflop' NOT LIKE '%%Fold%%'
        )
    )
"""


# ── Villain eligibility rule (A ∨ B ∨ C) ─────────────────────────────────────
# Canonical rule for 'a hand counts for villains'. Assumes alias `h` for hands.
#   (A) hm3_tags contém tag ILIKE 'nota%'
#   (B) match_method populado AND has_showdown = TRUE
#   (C) 'nota' in discord_tags AND match_method populado
# Filtro de 2026 está incluído dentro da própria condição (CLAUDE.md §5).

VILLAIN_ELIGIBILITY_CONDITION = """
    h.played_at >= '2026-01-01'
    AND (
        EXISTS (
            SELECT 1 FROM unnest(COALESCE(h.hm3_tags, ARRAY[]::text[])) t
            WHERE t ILIKE 'nota%%'
        )
        OR (
            h.player_names ->> 'match_method' IS NOT NULL
            AND h.player_names ->> 'match_method' NOT LIKE 'discord_placeholder_%%'
            AND h.has_showdown = TRUE
        )
        OR (
            'nota' = ANY(COALESCE(h.discord_tags, ARRAY[]::text[]))
            AND h.player_names ->> 'match_method' IS NOT NULL
            AND h.player_names ->> 'match_method' NOT LIKE 'discord_placeholder_%%'
        )
    )
"""


class VillainCreate(BaseModel):
    site:       Optional[str] = None
    nick:       str
    note:       Optional[str] = None
    tags:       Optional[list[str]] = None
    hands_seen: Optional[int] = 0


class VillainUpdate(BaseModel):
    note:       Optional[str] = None
    tags:       Optional[list[str]] = None
    hands_seen: Optional[int] = None


@router.get("")
def list_villains(
    site:      Optional[str] = Query(None),
    tag:       Optional[str] = Query(None),
    search:    Optional[str] = Query(None, description="Busca por nick (ILIKE)"),
    sort:      Optional[str] = Query(None),
    page:      int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    current_user=Depends(require_auth)
):
    conditions = []
    params = []

    if site:
        conditions.append("site = %s")
        params.append(site)
    if tag:
        conditions.append("%s = ANY(tags)")
        params.append(tag)
    if search:
        conditions.append("nick ILIKE %s")
        params.append(f"%{search}%")

    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""

    sort_map = {
        "hands_desc": "hands_seen DESC NULLS LAST",
        "hands_asc": "hands_seen ASC NULLS LAST",
        "updated_desc": "updated_at DESC",
        "updated_asc": "updated_at ASC",
        "nick_asc": "nick ASC",
    }
    order_by = sort_map.get(sort, "hands_seen DESC NULLS LAST")

    total = query(f"SELECT COUNT(*) AS total FROM villain_notes {where}", params)[0]["total"]
    offset = (page - 1) * page_size
    rows = query(
        f"""SELECT id, site, nick, note, tags, hands_seen, created_at, updated_at
            FROM villain_notes {where}
            ORDER BY {order_by}
            LIMIT %s OFFSET %s""",
        params + [page_size, offset]
    )

    return {
        "total": total, "page": page, "page_size": page_size,
        "pages": (total + page_size - 1) // page_size,
        "data": [dict(r) for r in rows],
    }


@router.get("/categorized")
def list_villains_categorized(
    category:  Optional[str] = Query("all", pattern="^(all|sd|nota|friend)$"),
    site:      Optional[str] = Query(None, description="Filtrar por sala. Aceita CSV multi-value (ex: 'Winamax,WPN')."),
    search:    Optional[str] = Query(None, description="ILIKE no player_name"),
    page:      int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    current_user=Depends(require_auth),
):
    """
    Tech Debt #4 — re-arquitectura página Vilões.

    Devolve agregação por nick a partir de `hand_villains.category`:
    sd_count / nota_count / friend_count / total_count + last_seen +
    sites + dates. Filtra por category (sd|nota|friend|all).

    Tech Debt #13b: parâmetro `site` aceita CSV (ex: "Winamax,WPN") para
    filtros multi-select. None = sem filtro de sala (todas).

    Coexiste com o endpoint legacy GET /api/villains (que lê de
    villain_notes). Frontend Parte D consome este; legacy fica para
    housekeeping após Parte D estável.
    """
    offset = (page - 1) * page_size

    # Tech Debt #13b — parse CSV multi-site. Lista vazia tratada como None.
    site_list = None
    if site:
        site_list = [s.strip() for s in site.split(',') if s.strip()] or None

    params = {
        "category": category,
        "site_list": site_list,
        "search": search,
        "search_like": f"%{search}%" if search else None,
        "limit": page_size,
        "offset": offset,
    }

    rows = query(
        """
        SELECT
            nick,
            sd_count, nota_count, friend_count, total_count,
            last_seen, sites, dates,
            COUNT(*) OVER() AS total_villains
        FROM (
            SELECT
                hv.player_name AS nick,
                COUNT(*) FILTER (WHERE hv.category = 'sd')     AS sd_count,
                COUNT(*) FILTER (WHERE hv.category = 'nota')   AS nota_count,
                COUNT(*) FILTER (WHERE hv.category = 'friend') AS friend_count,
                COUNT(*)                                       AS total_count,
                MAX(h.played_at)                               AS last_seen,
                ARRAY_AGG(DISTINCT h.site)                     AS sites,
                ARRAY_AGG(DISTINCT h.played_at::date
                          ORDER BY h.played_at::date DESC)     AS dates
            FROM hand_villains hv
            JOIN hands h ON h.id = hv.hand_db_id
            WHERE hv.hand_db_id IS NOT NULL
              AND h.played_at >= '2026-01-01'
              AND (%(site_list)s IS NULL OR h.site = ANY(%(site_list)s))
              AND (%(search)s IS NULL OR hv.player_name ILIKE %(search_like)s)
            GROUP BY hv.player_name
            HAVING (
                CASE %(category)s
                    WHEN 'sd'     THEN COUNT(*) FILTER (WHERE hv.category = 'sd')     > 0
                    WHEN 'nota'   THEN COUNT(*) FILTER (WHERE hv.category = 'nota')   > 0
                    WHEN 'friend' THEN COUNT(*) FILTER (WHERE hv.category = 'friend') > 0
                    ELSE TRUE
                END
            )
        ) AS v
        ORDER BY total_count DESC, last_seen DESC NULLS LAST
        LIMIT %(limit)s OFFSET %(offset)s
        """,
        params,
    )

    total = rows[0]["total_villains"] if rows else 0
    data = []
    for r in rows:
        d = dict(r)
        d.pop("total_villains", None)
        # ISO-format dates para JSON friendly
        if d.get("last_seen"):
            d["last_seen"] = d["last_seen"].isoformat()
        if d.get("dates"):
            d["dates"] = [dt.isoformat() if hasattr(dt, "isoformat") else dt for dt in d["dates"]]
        data.append(d)

    return {
        "category": category,
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": (total + page_size - 1) // page_size if total else 0,
        "data": data,
    }


@router.get("/{villain_id}")
def get_villain(villain_id: int, current_user=Depends(require_auth)):
    rows = query("SELECT * FROM villain_notes WHERE id = %s", (villain_id,))
    if not rows:
        raise HTTPException(status_code=404, detail="Vilão não encontrado")
    return dict(rows[0])


@router.post("")
def create_villain(body: VillainCreate, current_user=Depends(require_auth)):
    existing = query(
        "SELECT id FROM villain_notes WHERE site IS NOT DISTINCT FROM %s AND nick = %s",
        (body.site, body.nick)
    )
    if existing:
        raise HTTPException(status_code=409, detail=f"Vilão '{body.nick}' já existe.")

    row = execute_returning(
        """INSERT INTO villain_notes (site, nick, note, tags, hands_seen)
           VALUES (%(site)s, %(nick)s, %(note)s, %(tags)s, %(hands_seen)s)
           RETURNING id, created_at""",
        body.model_dump()
    )
    return {"id": row["id"], "created_at": row["created_at"]}


@router.patch("/{villain_id}")
def update_villain(villain_id: int, body: VillainUpdate, current_user=Depends(require_auth)):
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    if not updates:
        raise HTTPException(status_code=400, detail="Nada para actualizar")

    set_parts = []
    params = {}
    for k, v in updates.items():
        set_parts.append(f"{k} = %({k})s")
        params[k] = v
    set_parts.append("updated_at = NOW()")

    params["villain_id"] = villain_id
    execute(f"UPDATE villain_notes SET {', '.join(set_parts)} WHERE id = %(villain_id)s", params)
    return {"ok": True}


@router.delete("/{villain_id}")
def delete_villain(villain_id: int, current_user=Depends(require_auth)):
    execute("DELETE FROM villain_notes WHERE id = %s", (villain_id,))
    return {"ok": True}


def _compute_villain_result(raw: str, villain_nick: str, bb_size: float) -> float | None:
    """
    Computa resultado do villain em BB (net) a partir do raw HH.
    Mesma formula do _parse_hand para hero (hm3.py), aplicada ao villain.

    Suporta sintaxes das 4 salas:
      - Winamax:   "nick posts ante N"      "nick calls N"       "nick raises X to Y"
      - PokerStars:"nick: posts the ante N" "nick: calls N"      "nick: raises X to Y"
      - WPN:       "nick posts ante N.00"   "nick bets N.00"     (similar a WN)
      - GG:        parecido a WN mas raw GG usa hashes anonimos; se villain_nick for
                   o nome real (pos-match SS), regex nao apanha e devolve 0 bb —
                   fallback no frontend mostra h.result hero. Bug latente, fora
                   de scope.

    Regex flexibilidade:
      - '(?::)?'         colon opcional pos-nick (PS style)
      - '(?:the\\s+)?'   "the" opcional antes de ante/blind (PS style)
      - '[\\d,.]+'       decimais (WPN .00) + virgulas milhares (pots grandes)
      - re.escape(nick)  protege chars especiais em nicks ([m], -, etc.)

    Multi-way / side pots: re.finditer soma todas as ocorrencias de "collected"
    e "wins" para o villain (inclui "from main pot" / "from side pot" naturalmente).

    Devolve None se bb_size invalido ou nick vazio. Nunca lanca.

    Caveat: soma de raises usa o 'to' value (mesmo comportamento do hero parser;
    em pots com multi-raise o invested fica sobre-estimado, mas consistente com
    o hero — o delta de perspectiva mantem-se coerente).
    """
    if not raw or not villain_nick or not bb_size or bb_size <= 0:
        return None

    nick_re = re.escape(villain_nick)
    invested = 0.0
    won = 0.0

    try:
        for m in re.finditer(
            rf"{nick_re}(?::)?\s+posts\s+(?:the\s+)?(?:ante|small blind|big blind)\s+([\d,.]+)",
            raw,
        ):
            invested += float(m.group(1).replace(",", ""))

        for m in re.finditer(
            rf"{nick_re}(?::)?\s+(?:calls|bets)\s+([\d,.]+)",
            raw,
        ):
            invested += float(m.group(1).replace(",", ""))

        for m in re.finditer(
            rf"{nick_re}(?::)?\s+raises\s+[\d,.]+\s+to\s+([\d,.]+)",
            raw,
        ):
            invested += float(m.group(1).replace(",", ""))

        uncalled_m = re.search(
            rf"Uncalled bet \(([\d,.]+)\) returned to {nick_re}",
            raw,
        )
        if uncalled_m:
            invested -= float(uncalled_m.group(1).replace(",", ""))

        for m in re.finditer(rf"{nick_re} collected ([\d,.]+)", raw):
            won += float(m.group(1).replace(",", ""))

        for m in re.finditer(rf"{nick_re} wins ([\d,.]+)", raw):
            won += float(m.group(1).replace(",", ""))

        return round((won - invested) / bb_size, 2)
    except (ValueError, ZeroDivisionError):
        return None


@router.get("/search/hands")
def villain_hands(
    nick: str = Query(..., description="Nick do vilão"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user=Depends(require_auth)
):
    """
    Devolve mãos do vilão presentes em hand_villains (2026+, cumprindo A∨B∨C).
    v2: join canónico por hv.hand_db_id; rows legacy só-com-mtt_hand_id ignoradas.
    """
    offset = (page - 1) * page_size

    base_from_where = f"""
        FROM hands h
        JOIN hand_villains hv ON hv.hand_db_id = h.id
        WHERE hv.player_name = %s
          AND {VILLAIN_ELIGIBILITY_CONDITION}
    """

    rows = query(
        f"""SELECT DISTINCT h.id, h.hand_id, h.played_at, h.stakes, h.position,
                   h.hero_cards, h.board, h.result, h.study_state,
                   h.all_players_actions, h.screenshot_url, h.player_names,
                   h.entry_id, h.raw, h.site,
                   h.tournament_name, h.tournament_number, h.tournament_format, h.buy_in
            {base_from_where}
            ORDER BY h.played_at DESC NULLS LAST
            LIMIT %s OFFSET %s""",
        (nick, page_size, offset)
    )

    total_rows = query(
        f"SELECT COUNT(DISTINCT h.id) AS total {base_from_where}",
        (nick,)
    )
    total = total_rows[0]["total"] if total_rows else 0

    # Enrich: villain_result (net BB na perspectiva do villain, computado do raw).
    # bb_size vive em all_players_actions._meta.bb; defensivo contra apa=str/None.
    data = []
    for r in rows:
        d = dict(r)
        apa = d.get("all_players_actions")
        if isinstance(apa, str):
            try:
                apa = json.loads(apa)
            except Exception:
                apa = None
        bb_size = None
        if isinstance(apa, dict):
            meta = apa.get("_meta")
            if isinstance(meta, dict):
                bb_size = meta.get("bb")
        try:
            bb_size_f = float(bb_size) if bb_size is not None else 0.0
        except (TypeError, ValueError):
            bb_size_f = 0.0
        d["villain_result"] = _compute_villain_result(d.get("raw") or "", nick, bb_size_f)
        data.append(d)

    return {
        "total": total, "page": page, "page_size": page_size,
        "pages": (total + page_size - 1) // page_size,
        "data": data,
    }


@router.post("/recalculate-hands")
def recalculate_hands_seen(current_user=Depends(require_auth)):
    """
    Recalcula hands_seen para todos os vilões.
    v2: conta mãos em hand_villains cumprindo (A∨B∨C) com filtro 2026.
    1. Reset ALL to zero
    2. COUNT DISTINCT hands per nick via hand_villains JOIN hands + regra ABC
    3. Delete friend nicks from villain_notes
    """
    from app.db import get_conn
    conn = get_conn()
    reset_count = 0
    updated = 0
    friends_cleaned = 0
    try:
        with conn.cursor() as cur:
            cur.execute("UPDATE villain_notes SET hands_seen = 0")
            reset_count = cur.rowcount

            cur.execute(f"""
                UPDATE villain_notes vn SET
                    hands_seen = COALESCE(sub.cnt, 0),
                    updated_at = NOW()
                FROM (
                    SELECT hv.player_name AS nick,
                           COUNT(DISTINCT h.id) AS cnt
                    FROM hand_villains hv
                    JOIN hands h ON h.id = hv.hand_db_id
                    WHERE {VILLAIN_ELIGIBILITY_CONDITION}
                    GROUP BY nick
                ) sub
                WHERE vn.nick = sub.nick
            """)
            updated = cur.rowcount

            # Step 3: Delete friend nicks from villain_notes
            friend_list = list(FRIEND_NICKS)
            if friend_list:
                placeholders = ','.join(['%s'] * len(friend_list))
                cur.execute(
                    f"DELETE FROM villain_notes WHERE LOWER(nick) IN ({placeholders})",
                    friend_list
                )
                friends_cleaned = cur.rowcount

        conn.commit()
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()
    return {"ok": True, "reset": reset_count, "updated": updated, "friends_removed": friends_cleaned}
