"""Motor do EV perdido — Resultados HRC Fase 1b (16 Jul 2026).

Read-only. Abre o `result_zip` do HRC e mede, no **nó de decisão do Hero**, quanta
**equity de torneio (ICM, `TABLE_EQUITY_PERCENT`)** a jogada REAL do Hero perdeu contra
a melhor resposta da solução — para a mão específica do Hero (classe da mão).

Método:
  1. `settings.json` (stacks/blinds/BB) + `equity.json` (equityUnit, conversão p/ USD).
  2. Do `raw`: seats↔posição↔HRC idx (`derive_seats_in_preflop_order`), Hero + cartas,
     e a SEQUÊNCIA REAL de ações preflop (com o to-amount em fichas HH).
  3. Anda do nó 0 seguindo a linha REAL (cada ação casada ao ramo do nó **POR VALOR** —
     não por tipo: era o bug do protótipo, que apanhava o último raise/all-in em vez do
     verdadeiro 3-bet) até ser a vez do Hero → esse é o **nó de decisão**.
  4. `evs[]` da classe da mão do Hero nesse nó: `loss = max(evs) − evs[ação real]`.

Partilhado com a página da mão (Fase 2). Cacheável por (mão, zip) — determinístico.
"""
from __future__ import annotations

import io
import json
import re
import zipfile

from app.services.hrc_verify import (
    parse_hh_blinds, _hh_bb, _hh_seat_stacks, _derive_scale,
)

_HERO_RE = re.compile(r"^Dealt to (.+?) \[([2-9TJQKA][cdhs])\s+([2-9TJQKA][cdhs])\]", re.M)
# ação preflop (GG ':' e WN sem ':'); captura nick, tipo e (para raise/bet) o to-amount
_ACT_RE = re.compile(
    r"^(.+?):?\s+(folds|checks|calls|bets|raises)\b(?:.*?\bto\s+([\d,]+))?(?:.*?\b([\d,]+))?",
    re.M,
)
_RANKS = "23456789TJQKA"


def _card_class(c1: str, c2: str) -> str:
    """Duas cartas ('Kh','6h') → classe HRC ('K6s'/'K6o'/'KK')."""
    r1, s1 = c1[0], c1[1]
    r2, s2 = c2[0], c2[1]
    if r1 == r2:
        return r1 + r2
    hi, lo = (r1, r2) if _RANKS.index(r1) > _RANKS.index(r2) else (r2, r1)
    return f"{hi}{lo}{'s' if s1 == s2 else 'o'}"


def _real_preflop_actions(raw: str) -> list:
    """Sequência REAL de ações preflop: [(nick, type, to_amount_hh|None)]. type em
    F/C/X/R (bet→R). Exclui posts de blinds. GG (com ':') e WN (sem ':')."""
    if not raw:
        return []
    s = raw.find("*** PRE-FLOP ***")
    if s < 0:
        s = raw.find("*** HOLE CARDS ***")
    if s < 0:
        return []
    end = raw.find("*** FLOP ***", s)
    blk = raw[s:(end if end > 0 else len(raw))]
    out = []
    tmap = {"folds": "F", "checks": "X", "calls": "C", "raises": "R", "bets": "R"}
    for m in _ACT_RE.finditer(blk):
        nick = m.group(1).strip()
        if nick.startswith("***") or "Dealt to" in nick:
            continue
        kind = tmap[m.group(2)]
        amt = None
        if kind == "R":
            a = m.group(3) or m.group(4)  # 'raises X to Y' → Y (g3); 'bets X' → X (g4)
            if a:
                try:
                    amt = float(a.replace(",", ""))
                except ValueError:
                    amt = None
        out.append((nick, kind, amt))
    return out


def _match_action_idx(node: dict, kind: str, to_amt_hrc: float | None) -> int | None:
    """Índice da ação do nó que casa com a ação real. Fold/Call/Check por tipo;
    Raise POR VALOR (a R com amount mais próximo de `to_amt_hrc`)."""
    acts = node.get("actions", [])
    if kind in ("F", "C", "X"):
        for i, a in enumerate(acts):
            if a.get("type") == kind:
                return i
        # check↔call fallback (nós sem X explícito)
        for i, a in enumerate(acts):
            if a.get("type") in ("C", "X"):
                return i
        return None
    # Raise: mais próximo por valor
    r_idx = [i for i, a in enumerate(acts) if a.get("type") == "R"]
    if not r_idx:
        return None
    if to_amt_hrc is None:
        return r_idx[0]
    return min(r_idx, key=lambda i: abs((acts[i].get("amount") or 0) - to_amt_hrc))


def _label(a: dict, bb: float) -> str:
    t = a.get("type")
    if t == "F":
        return "Fold"
    if t == "C":
        return "Call"
    if t == "X":
        return "Check"
    if t == "R":
        return f"Raise {(a.get('amount') or 0) / bb:.1f}bb" if bb else "Raise"
    return t or "?"


def compute_ev_loss(hand: dict, zip_bytes: bytes) -> dict:
    """EV perdido (% equity ICM) da jogada real do Hero vs melhor resposta HRC.
    Devolve {ok, loss_eq_pct, loss_usd, hero_class, real_label, best_label,
    node_idx, ...} ou {ok:False, error}."""
    raw = hand.get("raw") or ""
    try:
        zf = zipfile.ZipFile(io.BytesIO(zip_bytes))
    except zipfile.BadZipFile:
        return {"ok": False, "error": "zip inválido"}
    try:
        settings = json.loads(zf.read("settings.json"))
        equity = json.loads(zf.read("equity.json"))
    except (KeyError, ValueError):
        return {"ok": False, "error": "settings/equity ausentes"}

    hd = settings.get("handdata") or {}
    stacks = [s for s in (hd.get("stacks") or []) if isinstance(s, (int, float))]
    blinds = [b for b in (hd.get("blinds") or []) if isinstance(b, (int, float))]
    if not stacks or not blinds:
        return {"ok": False, "error": "handdata sem stacks/blinds"}
    bb = float(blinds[0])
    to_usd = (equity.get("conversionFactors") or {}).get("toUSD")

    # seats ↔ posição ↔ HRC idx + Hero + cartas
    from app.services.queue_export import derive_seats_in_preflop_order
    order = derive_seats_in_preflop_order(raw)
    if not order:
        return {"ok": False, "error": "seats não derivados"}
    nick_to_idx = {e["nick"]: e["hrc_idx"] for e in order}
    idx_to_pos = {e["hrc_idx"]: e.get("position") for e in order}
    hm = _HERO_RE.search(raw)
    if not hm:
        return {"ok": False, "error": "Hero/cartas não lidos"}
    hero_nick = hm.group(1).strip()
    hero_idx = nick_to_idx.get(hero_nick)
    if hero_idx is None:
        return {"ok": False, "error": "Hero fora do mapa de seats"}
    hero_class = _card_class(hm.group(2), hm.group(3))

    hh_bb = _hh_bb(raw, parse_hh_blinds(raw))
    scale = _derive_scale(blinds, hh_bb, stacks, _hh_seat_stacks(raw))

    node_names = {int(re.match(r"nodes/(\d+)", n).group(1))
                  for n in zf.namelist() if re.match(r"nodes/\d+\.json$", n)}

    def get_node(i):
        try:
            return json.loads(zf.read(f"nodes/{i}.json"))
        except (KeyError, ValueError):
            return None

    # anda a linha real até à decisão do Hero
    reals = _real_preflop_actions(raw)
    cur = 0
    guard = 0
    for (nick, kind, to_hh) in reals:
        guard += 1
        if guard > len(node_names) + 4:
            return {"ok": False, "error": "loop guard"}
        node = get_node(cur)
        if node is None or not node.get("actions"):
            return {"ok": False, "error": "nó/leaf inesperado"}
        actor_idx = node.get("player")
        if actor_idx == hero_idx:
            # nó de decisão do Hero encontrado
            hands = node.get("hands") or {}
            hk = hands.get(hero_class)
            if not hk or not hk.get("evs"):
                return {"ok": False, "error": f"sem evs p/ {hero_class} no nó {cur}"}
            evs = hk["evs"]
            to_hrc = (to_hh * scale) if (to_hh is not None and scale) else None
            ridx = _match_action_idx(node, kind, to_hrc)
            if ridx is None or ridx >= len(evs):
                return {"ok": False, "error": "ação real não casada no nó"}
            best = max(range(len(evs)), key=lambda i: evs[i])
            loss = evs[best] - evs[ridx]
            acts = node["actions"]
            return {
                "ok": True,
                "loss_eq_pct": round(loss, 4),
                "loss_usd": (round(loss * to_usd, 2) if isinstance(to_usd, (int, float)) else None),
                "hero_class": hero_class,
                "hero_pos": idx_to_pos.get(hero_idx),
                "real_label": _label(acts[ridx], bb),
                "best_label": _label(acts[best], bb),
                "node_idx": cur,
            }
        # avança seguindo a ação real deste jogador (casada por valor)
        to_hrc = (to_hh * scale) if (to_hh is not None and scale) else None
        aidx = _match_action_idx(node, kind, to_hrc)
        if aidx is None:
            return {"ok": False, "error": "ação (não-Hero) não casada"}
        nxt = node["actions"][aidx].get("node")
        if nxt is None:
            return {"ok": False, "error": "ramo sem nó filho"}
        cur = nxt
    return {"ok": False, "error": "Hero sem decisão (walk?)"}
