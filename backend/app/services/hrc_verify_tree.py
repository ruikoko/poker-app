"""pt86 (#HRC-VERIFY) — vista legível "HH vs HRC" por mão resolvida.

Read-only. Abre o `result_zip` do HRC e produz, em texto estruturado, o que a
árvore HRC diz no **nó central** + ramos imediatos — no mesmo formato que se
extraiu à mão para a GRAVITY (sizes + frequências fold/call/raise por nó). O Rui
lê e julga à vista; **o sistema não dá veredicto**.

NÓ CENTRAL (regra do watcher, mas localizado por SEQUENCE-MATCH no grafo, nunca
pelo offset de linha — escapa ao `#HRC-NODE-OFFSET-IMPLICIT-LINES`):
  segue a linha real da HH desde a raiz; pára no 1º nó onde o jogador **não
  foldou** (1ª agressão/entrada = "a primeira ação da mão") OU onde o jogador é
  o **Hero** (folded-to-Hero). Esse é o nó central.

Frequências: por nó, `range%` ponderada por combos reais (par=6, suited=4,
offsuit=12) × weight, somando `played[a]`. Idêntico ao probe da GRAVITY.

Acesso aos nós é LAZY (lê `nodes/<i>.json` à medida que percorre) — um zip GG
pode ter 8 MB / 1500+ nós, mas só se tocam ~o nó central + ramos (cap baixo).
"""
from __future__ import annotations

import io
import json
import re
import zipfile
from typing import Optional

_VOLUNTARY = {"calls", "raises", "bets"}  # entrada/agressão (fold/check não)
_ACTION_RE = re.compile(r"^(.+?):?\s+(folds|calls|raises|bets|checks)\b", re.M)
_HERO_RE = re.compile(r"^Dealt to (.+?) \[", re.M)


def _combos(key: str) -> int:
    """Combos de uma classe de mão HRC ('22','AKs','A2o')."""
    if len(key) == 2:
        return 6            # par
    return 4 if key.endswith("s") else 12   # suited / offsuit


def _action_label(a: dict, BB: float, actor_stack: float):
    t = a.get("type")
    if t == "F":
        return "FOLD", False
    if t == "C":
        return "CALL", False
    if t == "X":
        return "CHECK", False
    if t == "R":
        amt = a.get("amount") or 0
        is_allin = abs(amt - actor_stack) < BB * 0.5
        return (f"R {amt / BB:.1f}bb" + (" ALLIN" if is_allin else "")), is_allin
    return (t or "?"), False


def _node_strategy(node: dict, BB: float, stacks: list) -> dict:
    """Frequências range% por ação de um nó + meta (actor, facing)."""
    p = node["player"]
    actor_stack = stacks[p] if p < len(stacks) else 0
    acts = node.get("actions", [])
    nacts = len(acts)
    tot = 0.0
    acc = [0.0] * nacts
    for key, info in node.get("hands", {}).items():
        w = info.get("weight", 1.0)
        c = _combos(key) * w
        played = info.get("played", [])
        tot += c
        for a in range(min(nacts, len(played))):
            acc[a] += c * played[a]
    out_actions = []
    for a in range(nacts):
        label, is_allin = _action_label(acts[a], BB, actor_stack)
        out_actions.append({
            "label": label,
            "is_allin": is_allin,
            "pct": round(100 * acc[a] / tot, 1) if tot else 0.0,
            "child": acts[a].get("node"),
        })
    return {"player_idx": p, "combos": round(tot), "actions": out_actions}


def _seq_str(seq: list, idx2pos: dict) -> str:
    parts = []
    for s in seq:
        pos = idx2pos.get(s["player"], f"p{s['player']}")
        if s["type"] == "R":
            parts.append(f"{pos}:R{s.get('amount', 0) / max(1, s.get('_bb', 1)):.0f}" if False else f"{pos}:R")
        else:
            parts.append(f"{pos}:{s['type']}")
    return " ".join(parts) if parts else "(raiz)"


def _seq_str_bb(seq: list, idx2pos: dict, BB: float) -> str:
    parts = []
    for s in seq:
        pos = idx2pos.get(s["player"], f"p{s['player']}")
        if s["type"] == "R":
            parts.append(f"{pos}:R{(s.get('amount', 0)) / BB:.1f}")
        else:
            parts.append(f"{pos}:{s['type']}")
    return " ".join(parts) if parts else "(raiz)"


def _hh_first_actions(raw: str, nick_to_idx: dict) -> dict:
    """idx -> 1ª acção preflop ('folds'/'raises'/...). Cross-site (GG ':',
    WN sem ':'). Só a 1ª acção de cada seat conta."""
    if not raw:
        return {}
    start = raw.find("*** PRE-FLOP ***")
    if start < 0:
        start = raw.find("*** HOLE CARDS ***")
    if start < 0:
        start = 0
    ends = [e for e in (raw.find("*** FLOP ***", start), raw.find("*** SUMMARY ***", start)) if e > 0]
    block = raw[start:(min(ends) if ends else len(raw))]
    first = {}
    for m in _ACTION_RE.finditer(block):
        nick, kind = m.group(1).strip(), m.group(2)
        idx = nick_to_idx.get(nick)
        if idx is not None and idx not in first:
            first[idx] = kind
    return first


def _hh_preflop_text(raw: str) -> str:
    """Bloco legível: header + seats + ANTE/BLINDS + PRE-FLOP (até ao FLOP)."""
    if not raw:
        return ""
    cut = [e for e in (raw.find("*** FLOP ***"), raw.find("*** SUMMARY ***")) if e > 0]
    return raw[:(min(cut) if cut else len(raw))].strip()


def build_verify_tree(hand: dict, zip_bytes: bytes, max_nodes: int = 1500) -> dict:
    """Subárvore preflop completa a partir do nó-âncora (Selected Subtree), em
    forma navegável: cada nó com a estratégia agregada da sua posição + links
    para os nós-filho (`actions[].node`). `hand`: row de `hands` (raw).
    `zip_bytes`: result_zip do HRC. `max_nodes`: tecto defensivo (truncated)."""
    from app.services.queue_export import derive_seats_in_preflop_order

    try:
        zf = zipfile.ZipFile(io.BytesIO(zip_bytes))
    except zipfile.BadZipFile:
        return {"error": "result_zip inválido"}

    try:
        settings = json.loads(zf.read("settings.json"))
    except (KeyError, ValueError):
        return {"error": "settings.json ausente/ilegível no result_zip"}
    hd = settings.get("handdata") or {}
    stacks = hd.get("stacks") or []
    blinds = hd.get("blinds") or []
    if not stacks or len(blinds) < 1:
        return {"error": "handdata sem stacks/blinds"}
    BB = float(blinds[0])

    node_names = {int(re.match(r"nodes/(\d+)", n).group(1))
                  for n in zf.namelist() if re.match(r"nodes/\d+\.json$", n)}
    n_total = len(node_names)
    _cache: dict = {}

    def get_node(i):
        if i not in _cache:
            try:
                _cache[i] = json.loads(zf.read(f"nodes/{i}.json"))
            except (KeyError, ValueError):
                _cache[i] = None
        return _cache[i]

    raw = hand.get("raw") or ""
    order = derive_seats_in_preflop_order(raw)
    idx2pos = {e["hrc_idx"]: e.get("position") for e in order}
    nick_to_idx = {e["nick"]: e["hrc_idx"] for e in order}
    hero_m = _HERO_RE.search(raw)
    hero_idx = nick_to_idx.get(hero_m.group(1).strip()) if hero_m else None
    first_actions = _hh_first_actions(raw, nick_to_idx)

    # ── Nó central: segue a linha real até 1ª não-fold OU Hero (sequence-match) ──
    central = 0
    guard = 0
    cur = 0
    while get_node(cur) is not None and guard < n_total + 2:
        guard += 1
        nd = get_node(cur)
        p = nd["player"]
        if p == hero_idx:
            central = cur
            break
        kind = first_actions.get(p)
        if kind in _VOLUNTARY:           # 1ª agressão/entrada = "1ª acção da mão"
            central = cur
            break
        if kind == "folds":              # segue o ramo Fold real
            fold_child = next((a.get("node") for a in nd.get("actions", []) if a["type"] == "F"), None)
            if fold_child is None or get_node(fold_child) is None:
                central = cur            # fold leva a leaf (heads-up) — pára aqui
                break
            cur = fold_child
            continue
        central = cur                    # sem info da HH → pára
        break

    # ── Subárvore preflop COMPLETA a partir do nó-âncora (central) ──
    # pt86 v2 (árvore navegável): BFS por TODAS as acções (incl. folds — o Rui
    # quer navegar ramos que não aconteceram, desde que o solver os tenha). Cada
    # nó traz a estratégia agregada da sua posição (todas as opções + freq). Os
    # filhos vêm de `actions[].node`; o frontend expande on-click. Agregados são
    # leves (~5 acções/nó), por isso devolve-se a subárvore inteira de uma vez.
    rendered = []
    seen = set()
    bfs = [central]
    truncated = False
    while bfs:
        i = bfs.pop(0)
        if i in seen:
            continue
        if len(seen) >= max_nodes:
            truncated = True
            break
        nd = get_node(i)
        if nd is None or not nd.get("actions"):
            continue
        seen.add(i)
        strat = _node_strategy(nd, BB, stacks)
        p = strat["player_idx"]
        rendered.append({
            "idx": i,
            "actor": idx2pos.get(p, f"p{p}"),
            "actor_stack_bb": round(stacks[p] / BB, 1) if p < len(stacks) else None,
            "facing": _seq_str_bb(nd.get("sequence", []), idx2pos, BB),
            "is_central": (i == central),
            "street": nd.get("street", 0),
            "combos": strat["combos"],
            "actions": strat["actions"],
        })
        for a in nd["actions"]:
            ch = a.get("node")
            if ch is not None and ch not in seen:
                bfs.append(ch)

    return {
        "central_node": central,
        "root": central,
        "hero_idx": hero_idx,
        "n_nodes_total": n_total,
        "subtree_size": len(rendered),
        "truncated": truncated,
        "tree_complete": (get_node(0) is not None and not get_node(0).get("sequence")),
        "blinds_bb_chips": BB,
        "positions": [{"idx": i, "pos": idx2pos.get(i),
                       "stack_bb": round(stacks[i] / BB, 1) if i < len(stacks) else None}
                      for i in sorted(idx2pos)],
        "nodes": rendered,
        "hh_preflop": _hh_preflop_text(raw),
    }
