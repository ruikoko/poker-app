"""
GTO Brain — Fase 1
Router para importação e gestão de trees HRC.
Tabelas: gto_trees, gto_nodes
"""
import json
import logging
import os
import zipfile
import io
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from pydantic import BaseModel
from app.db import get_db
from app.auth import require_auth

router = APIRouter(prefix="/api/gto", tags=["gto"])
logger = logging.getLogger("gto")

# ── Schema Migration ──────────────────────────────────────────────────────────

MIGRATION_SQL = """
CREATE TABLE IF NOT EXISTS gto_trees (
    id                SERIAL PRIMARY KEY,
    name              TEXT NOT NULL,
    format            TEXT,                    -- "PKO", "KO", "vanilla", "mystery"
    num_players       INT,
    tournament_phase  TEXT,                    -- "early", "middle", "bubble", "itm", "final_table"
    hero_position     TEXT,                    -- posição do hero no root node
    hero_stack_bb_min NUMERIC,
    hero_stack_bb_max NUMERIC,
    villain_stack_bb  NUMERIC,                 -- stack do vilão principal (covering match)
    hero_covers       BOOLEAN,                 -- hero cobre vilão na tree?
    covers_at_least_one   BOOLEAN DEFAULT FALSE,
    covered_by_at_least_one BOOLEAN DEFAULT FALSE,
    tags              TEXT[] DEFAULT '{}',
    settings_json     JSONB,
    equity_json       JSONB,
    uploaded_by       TEXT,
    source_file       TEXT,
    node_count        INT DEFAULT 0,
    created_at        TIMESTAMPTZ DEFAULT NOW(),
    updated_at        TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_gto_trees_lookup
    ON gto_trees(num_players, format, tournament_phase);
CREATE INDEX IF NOT EXISTS idx_gto_trees_position
    ON gto_trees(hero_position, hero_stack_bb_min);

CREATE TABLE IF NOT EXISTS gto_nodes (
    id           SERIAL PRIMARY KEY,
    tree_id      INT REFERENCES gto_trees ON DELETE CASCADE,
    node_index   INT NOT NULL,
    player       INT NOT NULL,
    street       INT DEFAULT 0,
    sequence     JSONB DEFAULT '[]',
    actions      JSONB NOT NULL,
    hands        JSONB NOT NULL,
    is_terminal  BOOLEAN DEFAULT FALSE,
    has_mixed    BOOLEAN DEFAULT FALSE,
    UNIQUE(tree_id, node_index)
);

CREATE INDEX IF NOT EXISTS idx_gto_nodes_tree
    ON gto_nodes(tree_id, node_index);
CREATE INDEX IF NOT EXISTS idx_gto_nodes_mixed
    ON gto_nodes(tree_id, has_mixed) WHERE has_mixed = TRUE;
"""

def run_migration(conn):
    with conn.cursor() as cur:
        cur.execute(MIGRATION_SQL)
    conn.commit()

# ── HRC Parser ────────────────────────────────────────────────────────────────

HAND_ORDER = [
    "AA","KK","QQ","JJ","TT","99","88","77","66","55","44","33","22",
    "AKs","AQs","AJs","ATs","A9s","A8s","A7s","A6s","A5s","A4s","A3s","A2s",
    "KQs","KJs","KTs","K9s","K8s","K7s","K6s","K5s","K4s","K3s","K2s",
    "QJs","QTs","Q9s","Q8s","Q7s","Q6s","Q5s","Q4s","Q3s","Q2s",
    "JTs","J9s","J8s","J7s","J6s","J5s","J4s","J3s","J2s",
    "T9s","T8s","T7s","T6s","T5s","T4s","T3s","T2s",
    "98s","97s","96s","95s","94s","93s","92s",
    "87s","86s","85s","84s","83s","82s",
    "76s","75s","74s","73s","72s",
    "65s","64s","63s","62s",
    "54s","53s","52s",
    "43s","42s","32s",
    "AKo","AQo","AJo","ATo","A9o","A8o","A7o","A6o","A5o","A4o","A3o","A2o",
    "KQo","KJo","KTo","K9o","K8o","K7o","K6o","K5o","K4o","K3o","K2o",
    "QJo","QTo","Q9o","Q8o","Q7o","Q6o","Q5o","Q4o","Q3o","Q2o",
    "JTo","J9o","J8o","J7o","J6o","J5o","J4o","J3o","J2o",
    "T9o","T8o","T7o","T6o","T5o","T4o","T3o","T2o",
    "98o","97o","96o","95o","94o","93o","92o",
    "87o","86o","85o","84o","83o","82o",
    "76o","75o","74o","73o","72o",
    "65o","64o","63o","62o",
    "54o","53o","52o",
    "43o","42o","32o",
]

def _compress_hands(hands_dict: dict) -> list:
    """
    Converte o dict de 169 mãos para array ordenado (mais compacto que objecto JSON).
    Formato: [[weight, [played...], [evs...]], ...] na ordem HAND_ORDER.
    Mãos em falta ficam como None.
    """
    result = []
    for hand in HAND_ORDER:
        if hand in hands_dict:
            d = hands_dict[hand]
            result.append([d["weight"], d["played"], d["evs"]])
        else:
            result.append(None)
    return result

def _has_mixed(hands_dict: dict) -> bool:
    """Verifica se alguma mão tem acções mistas (não é 100% uma acção)."""
    for hand, data in hands_dict.items():
        if any(0.01 < p < 0.99 for p in data["played"]):
            return True
    return False

def parse_hrc_zip(zip_bytes: bytes) -> dict:
    """
    Parseia um ZIP do HRC Pro e devolve um dict com:
    - settings: dados do settings.json
    - equity: dados do equity.json
    - nodes: lista de nós parseados
    - meta: metadata extraída automaticamente (stacks_bb, num_players, bounties, etc.)
    """
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        names = zf.namelist()

        # settings.json
        settings_name = next((n for n in names if n.endswith("settings.json")), None)
        if not settings_name:
            raise ValueError("settings.json não encontrado no ZIP")
        settings = json.loads(zf.read(settings_name))

        # equity.json (opcional)
        equity_name = next((n for n in names if n.endswith("equity.json")), None)
        equity = json.loads(zf.read(equity_name)) if equity_name else {}

        # nodes/*.json
        node_names = sorted(
            [n for n in names if "/nodes/" in n and n.endswith(".json")],
            key=lambda x: int(os.path.splitext(os.path.basename(x))[0])
        )
        if not node_names:
            raise ValueError("Nenhum nó encontrado no ZIP (nodes/*.json)")

        nodes = []
        for node_name in node_names:
            node_index = int(os.path.splitext(os.path.basename(node_name))[0])
            node_data = json.loads(zf.read(node_name))
            nodes.append({
                "node_index": node_index,
                "player": node_data.get("player", 0),
                "street": node_data.get("street", 0),
                "sequence": node_data.get("sequence", []),
                "actions": node_data.get("actions", []),
                "hands": _compress_hands(node_data.get("hands", {})),
                "is_terminal": node_data.get("children", 1) == 0,
                "has_mixed": _has_mixed(node_data.get("hands", {})),
            })

    # Extrair metadata do settings
    hd = settings.get("handdata", {})
    stacks_raw = hd.get("stacks", [])
    blinds_raw = hd.get("blinds", [])
    bounties_raw = hd.get("bounties", [])

    # BB = maior dos primeiros 2 blinds
    bb = max(blinds_raw[:2]) if len(blinds_raw) >= 2 else 1
    stacks_bb = [round(s / bb, 1) for s in stacks_raw]
    num_players = len(stacks_raw)

    # Detectar formato: PKO/KO se tem bounties > 0
    has_bounty = any(b > 0 for b in bounties_raw)
    # Mystery bounty: bounties iguais entre si (não diferenciados)
    all_equal = len(set(bounties_raw)) <= 1 if bounties_raw else True
    if has_bounty:
        fmt = "PKO"  # default para bounty; pode ser refinado pelo utilizador
    else:
        fmt = "vanilla"

    # Covering: hero (player 0 no root) vs restantes
    hero_stack = stacks_bb[0] if stacks_bb else 0
    other_stacks = stacks_bb[1:] if len(stacks_bb) > 1 else []
    covers_at_least_one = any(hero_stack > s for s in other_stacks)
    covered_by_at_least_one = any(hero_stack < s for s in other_stacks)
    hero_covers = covers_at_least_one and not covered_by_at_least_one

    return {
        "settings": settings,
        "equity": equity,
        "nodes": nodes,
        "meta": {
            "num_players": num_players,
            "stacks_bb": stacks_bb,
            "hero_stack_bb": hero_stack,
            "bb_raw": bb,
            "bounties": bounties_raw,
            "has_bounty": has_bounty,
            "format": fmt,
            "covers_at_least_one": covers_at_least_one,
            "covered_by_at_least_one": covered_by_at_least_one,
            "hero_covers": hero_covers,
            "node_count": len(nodes),
        }
    }

# ── Pydantic Models ───────────────────────────────────────────────────────────

class TreeCatalogForm(BaseModel):
    name: str
    format: Optional[str] = None          # override do auto-detectado
    num_players: Optional[int] = None
    tournament_phase: Optional[str] = None
    hero_position: Optional[str] = None
    hero_stack_bb_min: Optional[float] = None
    hero_stack_bb_max: Optional[float] = None
    villain_stack_bb: Optional[float] = None
    hero_covers: Optional[bool] = None
    tags: Optional[List[str]] = None
    uploaded_by: Optional[str] = None

# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/import")
async def import_tree(
    file: UploadFile = File(...),
    name: str = Form(...),
    format: Optional[str] = Form(None),
    num_players: Optional[int] = Form(None),
    tournament_phase: Optional[str] = Form(None),
    hero_position: Optional[str] = Form(None),
    hero_stack_bb_min: Optional[float] = Form(None),
    hero_stack_bb_max: Optional[float] = Form(None),
    villain_stack_bb: Optional[float] = Form(None),
    hero_covers: Optional[bool] = Form(None),
    tags: Optional[str] = Form(None),   # JSON string: '["pko","push_fold"]'
    uploaded_by: Optional[str] = Form(None),
    conn=Depends(get_db),
    _=Depends(require_auth),
):
    """
    Importa um ZIP do HRC Pro.
    Parseia settings.json, equity.json e todos os nodes/*.json.
    Guarda a tree e os nós na BD em lotes de 100.
    """
    run_migration(conn)

    zip_bytes = await file.read()
    if not zip_bytes:
        raise HTTPException(400, "Ficheiro vazio")

    try:
        parsed = parse_hrc_zip(zip_bytes)
    except Exception as e:
        raise HTTPException(400, f"Erro ao parsear ZIP: {e}")

    meta = parsed["meta"]
    tags_list = json.loads(tags) if tags else []

    # Usar valores do formulário ou auto-detectados
    tree_format = format or meta["format"]
    tree_num_players = num_players or meta["num_players"]
    tree_hero_covers = hero_covers if hero_covers is not None else meta["hero_covers"]
    tree_hero_stack_min = hero_stack_bb_min or meta["hero_stack_bb"]
    tree_hero_stack_max = hero_stack_bb_max or meta["hero_stack_bb"]

    with conn.cursor() as cur:
        # Inserir tree
        cur.execute("""
            INSERT INTO gto_trees (
                name, format, num_players, tournament_phase,
                hero_position, hero_stack_bb_min, hero_stack_bb_max,
                villain_stack_bb, hero_covers,
                covers_at_least_one, covered_by_at_least_one,
                tags, settings_json, equity_json,
                uploaded_by, source_file, node_count
            ) VALUES (
                %s, %s, %s, %s,
                %s, %s, %s,
                %s, %s,
                %s, %s,
                %s, %s, %s,
                %s, %s, %s
            ) RETURNING id
        """, (
            name, tree_format, tree_num_players, tournament_phase,
            hero_position, tree_hero_stack_min, tree_hero_stack_max,
            villain_stack_bb, tree_hero_covers,
            meta["covers_at_least_one"], meta["covered_by_at_least_one"],
            tags_list,
            json.dumps(parsed["settings"]),
            json.dumps(parsed["equity"]) if parsed["equity"] else None,
            uploaded_by, file.filename, meta["node_count"],
        ))
        tree_id = cur.fetchone()[0]

        # Inserir nós em lotes de 100
        nodes = parsed["nodes"]
        BATCH = 100
        for i in range(0, len(nodes), BATCH):
            batch = nodes[i:i + BATCH]
            args = []
            for n in batch:
                args.append((
                    tree_id,
                    n["node_index"],
                    n["player"],
                    n["street"],
                    json.dumps(n["sequence"]),
                    json.dumps(n["actions"]),
                    json.dumps(n["hands"]),
                    n["is_terminal"],
                    n["has_mixed"],
                ))
            cur.executemany("""
                INSERT INTO gto_nodes (
                    tree_id, node_index, player, street,
                    sequence, actions, hands, is_terminal, has_mixed
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (tree_id, node_index) DO NOTHING
            """, args)

    conn.commit()
    logger.info(f"Tree importada: id={tree_id}, name={name}, nodes={meta['node_count']}")

    return {
        "id": tree_id,
        "name": name,
        "format": tree_format,
        "num_players": tree_num_players,
        "node_count": meta["node_count"],
        "meta": meta,
    }


@router.get("/trees")
def list_trees(
    format: Optional[str] = None,
    num_players: Optional[int] = None,
    tournament_phase: Optional[str] = None,
    hero_position: Optional[str] = None,
    hero_stack_bb: Optional[float] = None,
    conn=Depends(get_db),
    _=Depends(require_auth),
):
    """Lista trees com filtros opcionais."""
    run_migration(conn)

    conditions = []
    params = []

    if format:
        conditions.append("format = %s")
        params.append(format)
    if num_players:
        conditions.append("num_players = %s")
        params.append(num_players)
    if tournament_phase:
        conditions.append("tournament_phase = %s")
        params.append(tournament_phase)
    if hero_position:
        conditions.append("hero_position = %s")
        params.append(hero_position)
    if hero_stack_bb:
        conditions.append("hero_stack_bb_min <= %s AND hero_stack_bb_max >= %s")
        params.extend([hero_stack_bb, hero_stack_bb])

    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""

    with conn.cursor() as cur:
        cur.execute(f"""
            SELECT id, name, format, num_players, tournament_phase,
                   hero_position, hero_stack_bb_min, hero_stack_bb_max,
                   villain_stack_bb, hero_covers,
                   covers_at_least_one, covered_by_at_least_one,
                   tags, uploaded_by, source_file, node_count, created_at
            FROM gto_trees
            {where}
            ORDER BY created_at DESC
        """, params)
        rows = cur.fetchall()
        cols = [d[0] for d in cur.description]

    return [dict(zip(cols, row)) for row in rows]


@router.get("/trees/{tree_id}")
def get_tree(tree_id: int, conn=Depends(get_db), _=Depends(require_auth)):
    """Detalhes de uma tree (sem nós)."""
    with conn.cursor() as cur:
        cur.execute("""
            SELECT id, name, format, num_players, tournament_phase,
                   hero_position, hero_stack_bb_min, hero_stack_bb_max,
                   villain_stack_bb, hero_covers,
                   covers_at_least_one, covered_by_at_least_one,
                   tags, settings_json, equity_json,
                   uploaded_by, source_file, node_count, created_at
            FROM gto_trees WHERE id = %s
        """, (tree_id,))
        row = cur.fetchone()
    if not row:
        raise HTTPException(404, "Tree não encontrada")
    cols = [d[0] for d in cur.description]
    return dict(zip(cols, row))


@router.get("/trees/{tree_id}/node/{node_index}")
def get_node(tree_id: int, node_index: int, conn=Depends(get_db), _=Depends(require_auth)):
    """Nó específico de uma tree (lazy-load)."""
    with conn.cursor() as cur:
        cur.execute("""
            SELECT node_index, player, street, sequence, actions, hands,
                   is_terminal, has_mixed
            FROM gto_nodes
            WHERE tree_id = %s AND node_index = %s
        """, (tree_id, node_index))
        row = cur.fetchone()
    if not row:
        raise HTTPException(404, "Nó não encontrado")
    cols = [d[0] for d in cur.description]
    node = dict(zip(cols, row))
    # Reconstituir hands como dict para o frontend (HAND_ORDER → dict)
    hands_array = node["hands"]
    if isinstance(hands_array, list):
        hands_dict = {}
        for i, hand in enumerate(HAND_ORDER):
            if i < len(hands_array) and hands_array[i] is not None:
                w, played, evs = hands_array[i]
                hands_dict[hand] = {"weight": w, "played": played, "evs": evs}
        node["hands"] = hands_dict
    node["hand_order"] = HAND_ORDER
    return node


@router.get("/trees/{tree_id}/nodes")
def get_nodes_path(
    tree_id: int,
    indices: str,   # "0,847,1325" — caminho de nós a carregar
    conn=Depends(get_db),
    _=Depends(require_auth),
):
    """
    Carrega múltiplos nós de uma tree por índice (lazy-load por caminho).
    indices: string com índices separados por vírgula.
    """
    try:
        idx_list = [int(x) for x in indices.split(",") if x.strip()]
    except ValueError:
        raise HTTPException(400, "Índices inválidos")

    if len(idx_list) > 50:
        raise HTTPException(400, "Máximo 50 nós por pedido")

    with conn.cursor() as cur:
        cur.execute("""
            SELECT node_index, player, street, sequence, actions, hands,
                   is_terminal, has_mixed
            FROM gto_nodes
            WHERE tree_id = %s AND node_index = ANY(%s)
        """, (tree_id, idx_list))
        rows = cur.fetchall()
        cols = [d[0] for d in cur.description]

    result = {}
    for row in rows:
        node = dict(zip(cols, row))
        hands_array = node["hands"]
        if isinstance(hands_array, list):
            hands_dict = {}
            for i, hand in enumerate(HAND_ORDER):
                if i < len(hands_array) and hands_array[i] is not None:
                    w, played, evs = hands_array[i]
                    hands_dict[hand] = {"weight": w, "played": played, "evs": evs}
            node["hands"] = hands_dict
        result[node["node_index"]] = node

    return result


@router.delete("/trees/{tree_id}")
def delete_tree(tree_id: int, conn=Depends(get_db), _=Depends(require_auth)):
    """Apaga uma tree e todos os seus nós (CASCADE)."""
    with conn.cursor() as cur:
        cur.execute("DELETE FROM gto_trees WHERE id = %s RETURNING id", (tree_id,))
        row = cur.fetchone()
    if not row:
        raise HTTPException(404, "Tree não encontrada")
    conn.commit()
    return {"deleted": tree_id}


@router.patch("/trees/{tree_id}")
def update_tree(
    tree_id: int,
    data: dict,
    conn=Depends(get_db),
    _=Depends(require_auth),
):
    """Actualiza campos de catalogação de uma tree (nome, fase, posição, tags, etc.)."""
    allowed = {
        "name", "format", "num_players", "tournament_phase",
        "hero_position", "hero_stack_bb_min", "hero_stack_bb_max",
        "villain_stack_bb", "hero_covers", "tags", "uploaded_by"
    }
    updates = {k: v for k, v in data.items() if k in allowed}
    if not updates:
        raise HTTPException(400, "Nenhum campo válido para actualizar")

    set_clause = ", ".join(f"{k} = %s" for k in updates)
    values = list(updates.values()) + [tree_id]

    with conn.cursor() as cur:
        cur.execute(
            f"UPDATE gto_trees SET {set_clause}, updated_at = NOW() WHERE id = %s RETURNING id",
            values
        )
        row = cur.fetchone()
    if not row:
        raise HTTPException(404, "Tree não encontrada")
    conn.commit()
    return {"updated": tree_id}


@router.get("/match")
def match_tree(
    hero_position: str,
    hero_stack_bb: float,
    format: str,
    num_players: int,
    tournament_phase: Optional[str] = None,
    villain_covers_hero: Optional[bool] = None,
    conn=Depends(get_db),
    _=Depends(require_auth),
):
    """
    Matching engine: dado um spot, encontra a tree mais próxima.
    Fase 1: filtro discreto + score contínuo por stack distance.
    Cobertura: penalização forte por covering errado em PKO/KO.
    """
    run_migration(conn)

    with conn.cursor() as cur:
        cur.execute("""
            SELECT id, name, format, num_players, tournament_phase,
                   hero_position, hero_stack_bb_min, hero_stack_bb_max,
                   villain_stack_bb, hero_covers,
                   covers_at_least_one, covered_by_at_least_one,
                   node_count
            FROM gto_trees
            WHERE num_players = %s AND format = %s AND hero_position = %s
        """, (num_players, format, hero_position))
        rows = cur.fetchall()
        cols = [d[0] for d in cur.description]

    candidates = [dict(zip(cols, row)) for row in rows]
    if not candidates:
        return {"match": None, "reason": "Nenhuma tree encontrada para este spot"}

    is_ko = format in ("PKO", "KO", "mystery")

    def score(tree):
        # Stack distance (normalizada)
        mid = (tree["hero_stack_bb_min"] + tree["hero_stack_bb_max"]) / 2
        stack_diff = abs(hero_stack_bb - mid)
        s = stack_diff

        # Penalização por covering errado (crítico em KO/PKO)
        if is_ko and villain_covers_hero is not None:
            # villain_covers_hero=True → hero é coberto → hero_covers deve ser False
            expected_hero_covers = not villain_covers_hero
            if tree["hero_covers"] is not None and tree["hero_covers"] != expected_hero_covers:
                s += 100  # penalização forte

        # Bonus por fase correcta
        if tournament_phase and tree["tournament_phase"] != tournament_phase:
            s += 5

        return s

    best = min(candidates, key=score)
    best_score = score(best)
    mid = (best["hero_stack_bb_min"] + best["hero_stack_bb_max"]) / 2
    stack_diff = abs(hero_stack_bb - mid)

    return {
        "match": best,
        "score": best_score,
        "stack_diff_bb": round(stack_diff, 1),
        "covering_ok": (
            best["hero_covers"] == (not villain_covers_hero)
            if villain_covers_hero is not None and best["hero_covers"] is not None
            else None
        ),
        "confidence": max(0, round(100 - stack_diff * 2 - (50 if best_score > 50 else 0), 1)),
    }
