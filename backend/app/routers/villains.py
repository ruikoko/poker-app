from fastapi import APIRouter, Depends, Query, HTTPException
from pydantic import BaseModel
from typing import Optional
from app.auth import require_auth
from app.db import query, execute, execute_returning

router = APIRouter(prefix="/api/villains", tags=["villains"])

# ── Friends / Hero nicks to exclude from villains ─────────────────────────────
# These are nicks of the user's group — they appear at the table but are NOT villains.
# Match is case-insensitive and supports truncated names (starts-with).

FRIEND_NICKS = {
    # Hero nicks
    "schadenfreud", "thinvalium", "sapz", "misterpoker1973",
    "cringemeariver", "flightrisk", "karluz", "koumpounophobia",
    "lauro dermio", "andacasa", "jeandouca",
    # GG group (with truncations handled by starts-with)
    # Winamax / Multi-sala group
    "1otario", "a lagardere", "abutrinzi", "algorhythm",
    "amazeswhores", "arr0zdepat0", "aturatu", "autoswiperight",
    "avecamos", "beijamyrola", "cattleking", "cavalitos",
    "cmaculatum", "coconacueca", "covfef3", "cr7dagreta",
    "cr7dapussy", "crashcow", "cunetejaune", "dapanal?",
    "decode", "deusfumo", "djobidjoba87", "dincredible",
    "eitaqdelicia", "el kingzaur", "etonelespute", "floptwist",
    "freeolivença", "godsmoke", "golimar666", "grenouille",
    "hmhm", "hollywoodpimp", "huntermilf", "i<3kebab",
    "ipaysor", "iuse2bspewer", "jackpito", "joao barbosa",
    "johngeologic", "kabalaharris", "klklwoku", "kokonakueka",
    "lendiadbisca", "leportugay8", "lewinsky", "ltbau",
    "luckytobme", "luckytobvsu", "milffinder", "milfodds",
    "mmaboss", "mrpeco", "mrpecoo", "narsa114",
    "neurose", "obviamente.", "ohum", "opaidasputas",
    "opaidelas", "pagachorari", "paidaskengas", "patodesisto",
    "pec0", "pelosithenancy", "pokerfan1967", "priest lucy",
    "proctocolectomy", "queleiteon", "quimterro", "quimtrega",
    "rail iota", "rapinzi", "rapinzi12", "rapinzi1988",
    "rapinzigg", "robyoungbff", "rosanorte", "ruing",
    "ryandays", "sapinzi", "shaamp00", "shrug",
    "sticklapisse", "tintin", "takiozaur", "thanatos",
    "toniextractor", "tonixtractor", "trapatonigpt", "traumatizer",
    "vanaldinho", "vascodagamba", "vascodagamba", "vtmizer",
    "zen17", "zen1to",
    # c78d hash nick
    "c78d63886ce0850aa6e75c3b58d63b",
}

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


@router.get("/search/hands")
def villain_hands(
    nick: str = Query(..., description="Nick do vilão"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user=Depends(require_auth)
):
    """
    Encontra mãos onde o vilão aparece com VPIP.
    Usa a mesma lógica VPIP do recalculate para consistência.
    """
    offset = (page - 1) * page_size

    vpip_sql = f"""
        SELECT DISTINCT h.id, h.hand_id, h.played_at, h.stakes, h.position,
               h.hero_cards, h.board, h.result, h.study_state,
               h.all_players_actions, h.screenshot_url, h.player_names,
               h.entry_id, h.raw, h.site
        FROM hands h, jsonb_each(h.all_players_actions) AS kv(key, val)
        WHERE h.all_players_actions IS NOT NULL
          AND key = %s
          AND {VPIP_CONDITION}
    """

    rows = query(
        f"{vpip_sql} ORDER BY h.played_at DESC NULLS LAST LIMIT %s OFFSET %s",
        (nick, page_size, offset)
    )

    total_rows = query(
        f"SELECT COUNT(DISTINCT h.id) AS total FROM hands h, jsonb_each(h.all_players_actions) AS kv(key, val) WHERE h.all_players_actions IS NOT NULL AND key = %s AND {VPIP_CONDITION}",
        (nick,)
    )
    total = total_rows[0]["total"] if total_rows else 0

    return {
        "total": total, "page": page, "page_size": page_size,
        "pages": (total + page_size - 1) // page_size,
        "data": [dict(r) for r in rows],
    }


@router.post("/recalculate-hands")
def recalculate_hands_seen(current_user=Depends(require_auth)):
    """
    Recalcula hands_seen para todos os vilões.
    1. Reset ALL to zero
    2. Count VPIP hands from all_players_actions
    3. Also count from hand_villains (MTT pipeline)
    Uses same VPIP_CONDITION for consistency.
    """
    from app.db import get_conn
    conn = get_conn()
    reset_count = 0
    updated = 0
    friends_cleaned = 0
    try:
        with conn.cursor() as cur:
            # Step 1: Reset ALL to zero
            cur.execute("UPDATE villain_notes SET hands_seen = 0")
            reset_count = cur.rowcount

            # Step 2: Recalculate from actual data
            cur.execute(f"""
                UPDATE villain_notes vn SET
                    hands_seen = COALESCE(sub.cnt, 0),
                    updated_at = NOW()
                FROM (
                    SELECT nick, COUNT(DISTINCT hand_ref) as cnt
                    FROM (
                        SELECT player_name AS nick, mtt_hand_id::text AS hand_ref
                        FROM hand_villains
                        UNION
                        SELECT key AS nick, h.id::text AS hand_ref
                        FROM hands h, jsonb_each(h.all_players_actions) AS kv(key, val)
                        WHERE h.all_players_actions IS NOT NULL
                          AND key != '_meta'
                          AND {VPIP_CONDITION}
                    ) combined
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
