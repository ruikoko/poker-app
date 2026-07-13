"""Página da mão (Wizard) — Resultados HRC Fase 2.

Read-only sobre o `result_zip`. Dois produtos:
  - `hand_positions(zip)` — coroas ($ bounty) por HRC idx (settings.handdata.bounties),
    para a barra de posições (stacks vêm do `build_verify_tree`).
  - `node_detail(zip, node_idx)` — para um nó: cartões de ação (freq% + combos + EV
    médio, por ação) + **grelha 13×13** (por classe de mão: ação dominante + freq),
    já com a semântica de cor da paleta do Rui (fold/call/raise/3bet/allin).

Paleta (kind por ação): fold · call · check · raise (1º raise = open) · 3bet (raise
sobre raise) · allin. O frontend pinta: fold=azul · call/check=verde · raise=amarelo ·
3bet=vermelho · allin=laranja.
"""
from __future__ import annotations

import io
import json
import re
import zipfile


def _combos(key: str) -> int:
    if len(key) == 2:
        return 6
    return 4 if key.endswith("s") else 12


def _kind(a: dict, prior_raises: int, actor_stack: float, bb: float) -> str:
    t = a.get("type")
    if t == "F":
        return "fold"
    if t == "C":
        return "call"
    if t == "X":
        return "check"
    if t == "R":
        amt = a.get("amount") or 0
        if actor_stack and abs(amt - actor_stack) < bb * 0.5:
            return "allin"
        return "3bet" if prior_raises >= 1 else "raise"
    return "other"


def _label(a: dict, bb: float, kind: str) -> str:
    t = a.get("type")
    if t == "F":
        return "Fold"
    if t == "C":
        return "Call"
    if t == "X":
        return "Check"
    if t == "R":
        amt = (a.get("amount") or 0) / bb if bb else 0
        pre = "All-in" if kind == "allin" else ("3-Bet" if kind == "3bet" else "Raise")
        return f"{pre} {amt:.1f}bb"
    return "?"


def _open_zip(zip_bytes: bytes):
    zf = zipfile.ZipFile(io.BytesIO(zip_bytes))
    settings = json.loads(zf.read("settings.json"))
    hd = settings.get("handdata") or {}
    stacks = [float(s) for s in (hd.get("stacks") or []) if isinstance(s, (int, float))]
    blinds = [float(b) for b in (hd.get("blinds") or []) if isinstance(b, (int, float))]
    bb = blinds[0] if blinds else 1.0
    return zf, hd, stacks, bb


def hand_bounties(zip_bytes: bytes) -> dict:
    """Coroa ($ bounty) por HRC idx, de settings.handdata.bounties (se PKO)."""
    try:
        _zf, hd, _stacks, _bb = _open_zip(zip_bytes)
    except (zipfile.BadZipFile, KeyError, ValueError):
        return {}
    bounties = hd.get("bounties") or []
    out = {}
    for i, b in enumerate(bounties):
        if isinstance(b, (int, float)) and b > 0:
            out[i] = round(float(b), 2)
    return out


def node_detail(zip_bytes: bytes, node_idx: int) -> dict:
    """Cartões de ação + grelha 13×13 de um nó. Read-only, lazy (só este nó)."""
    try:
        zf, _hd, stacks, bb = _open_zip(zip_bytes)
    except (zipfile.BadZipFile, KeyError, ValueError):
        return {"error": "zip/settings inválidos"}
    try:
        node = json.loads(zf.read(f"nodes/{node_idx}.json"))
    except (KeyError, ValueError):
        return {"error": f"nó {node_idx} ausente"}

    actor = node.get("player", 0)
    actor_stack = stacks[actor] if actor < len(stacks) else 0.0
    seq = node.get("sequence") or []
    prior_raises = sum(1 for s in seq if s.get("type") == "R")
    acts = node.get("actions", [])
    n = len(acts)
    kinds = [_kind(a, prior_raises, actor_stack, bb) for a in acts]

    tot = 0.0
    accf = [0.0] * n
    acce = [0.0] * n
    grid = {}
    for key, info in (node.get("hands") or {}).items():
        w = info.get("weight", 1.0)
        c = _combos(key) * w
        played = info.get("played", [])
        evs = info.get("evs", [])
        tot += c
        for a in range(min(n, len(played))):
            accf[a] += c * played[a]
            if a < len(evs):
                acce[a] += c * played[a] * evs[a]
        if played:
            di = max(range(min(n, len(played))), key=lambda i: played[i])
            grid[key] = {"k": kinds[di] if di < n else "other",
                         "pct": round(100 * played[di], 0)}

    actions = []
    for a in range(n):
        f = (accf[a] / tot) if tot else 0.0
        actions.append({
            "kind": kinds[a],
            "label": _label(acts[a], bb, kinds[a]),
            "pct": round(100 * f, 1),
            "combos": round(accf[a], 1),
            "ev": (round(acce[a] / (accf[a] or 1e-9), 4) if accf[a] else None),
            "child": acts[a].get("node"),
        })

    return {
        "node_idx": node_idx,
        "actor_idx": actor,
        "actor_stack_bb": round(actor_stack / bb, 1) if bb else None,
        "combos_total": round(tot),
        "actions": actions,
        "grid": grid,
    }
