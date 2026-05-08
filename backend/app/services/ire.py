"""
IRE v2 (Indice de Reducao de Equity / Bounty Power) — GG-only, ratio 25%.

Substitui v1 (formula em runtime) por lookup numa tabela hardcoded W3cray
(SI/KO_inicial = 4 = ratio 25%) com nearest-neighbour clamp e fallback
formula quando a celula = None ou (stack_si, ko_units) cai fora da tabela.

Filtros de activacao (qualquer falha => return None, IRE escondido):
    - hand.site == 'GGPoker'
    - match_method real (nao discord_placeholder_*)
    - tag *ko* em hm3_tags ou discord_tags (case-insens)
    - tournament_format in {'PKO', 'Mystery KO'}
    - tournaments_meta com starting_stack > 0
    - tournament_name NAO contem 'Super KO' (= ratio 40%, escondido em v1)
    - >= 1 oponente (non-hero) com bounty_pct > 0

Output (quando aplicavel):
    {
      "main_villain": {nick, position, stack_chips, stack_bb, stack_si,
                       ko_pct, ko_units, ire_pct, is_covered},
      "per_opponent": [
        {nick, position, stack_chips, stack_bb, stack_si, ko_pct, ko_units,
         ire_pct, is_main, is_active, is_covered},
        ...   # ordenado por SEAT_ORDER (UTG -> BTN -> SB -> BB)
      ],
    }

per_opponent inclui foldados (com is_active=False, ire_pct calculado se
ko_pct>0). Hero excluido.
"""
from __future__ import annotations
import json
import logging
import re
from typing import Optional

logger = logging.getLogger(__name__)


ALLOWED_FORMATS = {"PKO", "Mystery KO"}
KO_TAG_NEEDLE = "ko"
SUPER_KO_NEEDLE = "super ko"
_STREETS = ("preflop", "flop", "turn", "river")

# Ordem visual da mesa (mesma de HandDetailPage.jsx).
_SEAT_ORDER = ["UTG", "UTG1", "UTG+1", "UTG2", "UTG+2", "MP", "MP1", "MP+1",
               "HJ", "CO", "BTN", "SB", "BB"]


# ── Tabela W3cray (ratio 25%) ────────────────────────────────────────────────
# Validada via Mathematics.xlsx sheet "IRE". Linhas = stack_op em SI;
# colunas = ko_op em KO_inicial. Valores em % (None = celula vazia).

W3CRAY_TABLE_25PCT = {
    "rows_si": [0.25, 0.33, 0.5, 0.75, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 4.5, 5.0, 5.5, 6.0, 6.5, 7.0],
    "cols_ko": [1, 1.5, 2, 2.5, 3, 3.5, 4, 4.5, 5],
    "values_pct": {
        0.25: [13.0, None, None, None, None, None, None, None, None],
        0.33: [11.8, None, None, None, None, None, None, None, None],
        0.5:  [8.8, 11.8, 13.0, None, None, None, None, None, None],
        0.75: [6.5, 8.8, 9.5, 12.1, 13.0, None, None, None, None],
        1.0:  [5.1, 7.1, 8.8, 10.4, 11.8, 12.5, 13.0, None, None],
        1.5:  [3.9, 5.1, 6.5, 7.8, 8.8, 10.0, 10.8, None, None],
        2.0:  [2.6, 4.2, 5.1, 6.4, 7.1, 8.1, 8.8, None, None],
        2.5:  [2.0, 3.5, 4.3, 5.1, 6.0, 6.8, 7.8, None, None],
        3.0:  [1.7, 2.6, 3.7, 4.4, 5.1, 5.9, 6.5, None, None],
        3.5:  [1.4, 2.1, 3.0, 3.9, 4.6, 5.1, 5.7, None, None],
        4.0:  [1.2, 1.8, 2.6, 3.6, 4.2, 4.5, 5.1, None, None],
        4.5:  [0.9, 1.7, 2.5, 3.0, 3.7, 4.2, 4.6, 5.1, None],
        5.0:  [0.8, 1.5, 2.0, 2.6, 3.5, 3.9, 4.3, None, 5.1],
        5.5:  [0.7, 1.3, 1.8, 2.5, 3.0, 3.6, 4.0, None, None],
        6.0:  [0.5, 1.2, 1.6, 2.0, 2.6, 3.2, 3.7, None, None],
        6.5:  [0.4, 1.0, 1.5, 1.8, 2.5, 2.8, 3.5, None, None],
        7.0:  [0.2, 0.8, 1.4, 1.7, 2.2, 2.6, 3.2, None, None],
    },
}


# ── Helpers ──────────────────────────────────────────────────────────────────

def _has_ko_tag(hm3_tags, discord_tags) -> bool:
    for tag in (hm3_tags or []):
        if tag and KO_TAG_NEEDLE in tag.lower():
            return True
    for tag in (discord_tags or []):
        if tag and KO_TAG_NEEDLE in tag.lower():
            return True
    return False


def _coerce_apa(apa) -> Optional[dict]:
    if isinstance(apa, str):
        try:
            apa = json.loads(apa)
        except (ValueError, TypeError):
            return None
    return apa if isinstance(apa, dict) else None


def _coerce_pn(pn) -> dict:
    if isinstance(pn, str):
        try:
            pn = json.loads(pn)
        except (ValueError, TypeError):
            return {}
    return pn if isinstance(pn, dict) else {}


def _coerce_int(v) -> int:
    """bounty_pct vem como int (apa) ou TEXT/None. Coerce robusta."""
    if v is None:
        return 0
    if isinstance(v, (int, float)):
        return int(v)
    try:
        m = re.search(r"\d+", str(v))
        return int(m.group(0)) if m else 0
    except (ValueError, TypeError):
        return 0


def _is_active(actions: Optional[dict]) -> bool:
    """Activo = nao tem 'Fold' em nenhuma das suas accoes em qualquer rua.
    Sem accoes (sit-out / dealt-fold) = inactivo."""
    if not actions:
        return False
    has_any = False
    for street in _STREETS:
        for a in actions.get(street, []) or []:
            if not isinstance(a, str):
                continue
            has_any = True
            if a.startswith("Fold"):
                return False
    return has_any


def _seat_order_key(position: Optional[str]) -> int:
    if not position:
        return 99
    try:
        return _SEAT_ORDER.index(position)
    except ValueError:
        return 99


# ── Lookup ───────────────────────────────────────────────────────────────────

def _nearest_idx(value: float, axis: list) -> int:
    if value <= axis[0]:
        return 0
    if value >= axis[-1]:
        return len(axis) - 1
    return min(range(len(axis)), key=lambda i: abs(axis[i] - value))


def _formula_fallback(stack_si: float, ko_units: float) -> Optional[float]:
    """IRE_pct = bounty_si / (4*stack_si + 2*bounty_si) * 100, com bounty_si
    = ko_units * 0.25 (= ratio 25% expresso em SI)."""
    if ko_units <= 0 or stack_si <= 0:
        return None
    bounty_si = ko_units * 0.25
    denom = 4.0 * stack_si + 2.0 * bounty_si
    if denom <= 0:
        return None
    return (bounty_si / denom) * 100.0


def lookup_ire_pct(stack_si: float, ko_units: float) -> Optional[float]:
    """Devolve IRE % para (stack_op_em_SI, ko_op_em_KO_inicial). Ratio 25%.
    None quando ko_units<=0 ou stack invalido."""
    if ko_units <= 0 or stack_si <= 0:
        return None
    rows = W3CRAY_TABLE_25PCT["rows_si"]
    cols = W3CRAY_TABLE_25PCT["cols_ko"]
    y_idx = _nearest_idx(stack_si, rows)
    x_idx = _nearest_idx(ko_units, cols)
    cell = W3CRAY_TABLE_25PCT["values_pct"][rows[y_idx]][x_idx]
    if cell is not None:
        return float(cell)
    return _formula_fallback(stack_si, ko_units)


# ── Vilao principal (regra D) ────────────────────────────────────────────────

def _pick_main_villain(per_opponent: list, hero_stack_chips: float) -> Optional[dict]:
    activos = [op for op in per_opponent if op["is_active"] and op["ko_pct"] > 0]
    if not activos:
        return None
    if len(activos) == 1:
        return activos[0]
    cobertos = [op for op in activos if op["stack_chips"] <= hero_stack_chips]
    if len(cobertos) == 1:
        return cobertos[0]
    if cobertos:
        return max(cobertos, key=lambda op: op["stack_chips"])
    return max(activos, key=lambda op: op["stack_chips"])


# ── API publica ──────────────────────────────────────────────────────────────

def compute_ire(hand: dict, tm_meta: Optional[dict]) -> Optional[dict]:
    """Devolve {main_villain, per_opponent} ou None.
    Hero e excluido de per_opponent. Vilao principal escolhido pela regra D."""
    if hand.get("site") != "GGPoker":
        return None

    pn = _coerce_pn(hand.get("player_names"))
    mm = pn.get("match_method")
    if not mm or (isinstance(mm, str) and mm.startswith("discord_placeholder_")):
        return None

    if hand.get("tournament_format") not in ALLOWED_FORMATS:
        return None

    if not _has_ko_tag(hand.get("hm3_tags"), hand.get("discord_tags")):
        return None

    if not tm_meta or not tm_meta.get("starting_stack"):
        return None
    try:
        si = float(tm_meta["starting_stack"])
    except (TypeError, ValueError):
        return None
    if si <= 0:
        return None

    tname = (tm_meta.get("tournament_name") or "").lower()
    if SUPER_KO_NEEDLE in tname:
        return None  # ratio 40%, escondido em v1

    apa = _coerce_apa(hand.get("all_players_actions"))
    if not apa:
        return None
    bb = (apa.get("_meta") or {}).get("bb") or 0
    if bb <= 0:
        return None

    pl_by_name = {}
    for p in (pn.get("players_list") or []):
        if isinstance(p, dict):
            for key in ("name", "real_name"):
                v = p.get(key)
                if v:
                    pl_by_name.setdefault(v, p)

    hero_stack = None
    per_opponent: list[dict] = []
    for nick, info in apa.items():
        if nick == "_meta" or not isinstance(info, dict):
            continue
        if info.get("is_hero"):
            hero_stack = info.get("stack")
            continue
        try:
            stack_chips = float(info.get("stack") or 0)
        except (TypeError, ValueError):
            stack_chips = 0.0
        ko_pct = _coerce_int(info.get("bounty_pct"))
        if ko_pct <= 0:
            ko_pct = _coerce_int((pl_by_name.get(nick) or {}).get("bounty_pct"))
        ko_units = ko_pct / 100.0 if ko_pct > 0 else 0.0
        stack_si = stack_chips / si if si > 0 else 0.0
        ire_pct = lookup_ire_pct(stack_si, ko_units) if ko_units > 0 else None
        per_opponent.append({
            "nick": nick,
            "position": info.get("position"),
            "stack_chips": int(round(stack_chips)),
            "stack_bb": round(stack_chips / bb, 1) if bb else None,
            "stack_si": round(stack_si, 3),
            "ko_pct": ko_pct,
            "ko_units": round(ko_units, 2),
            "ire_pct": round(ire_pct, 1) if ire_pct is not None else None,
            "is_main": False,
            "is_active": _is_active(info.get("actions")),
            "is_covered": False,  # preenchido depois quando soubermos hero_stack
        })

    if not per_opponent:
        return None

    # nenhum oponente com bounty>0 => escondido
    if not any(op["ko_pct"] > 0 for op in per_opponent):
        return None

    if hero_stack is None or hero_stack <= 0:
        return None
    hero_stack_f = float(hero_stack)

    for op in per_opponent:
        op["is_covered"] = op["stack_chips"] <= hero_stack_f

    main = _pick_main_villain(per_opponent, hero_stack_f)
    if main is None:
        return None
    for op in per_opponent:
        if op["nick"] == main["nick"]:
            op["is_main"] = True
            break

    per_opponent.sort(key=lambda op: _seat_order_key(op.get("position")))

    main_out = {
        "nick": main["nick"],
        "position": main.get("position"),
        "stack_chips": main["stack_chips"],
        "stack_bb": main["stack_bb"],
        "stack_si": main["stack_si"],
        "ko_pct": main["ko_pct"],
        "ko_units": main["ko_units"],
        "ire_pct": main["ire_pct"],
        "is_covered": main["is_covered"],
    }
    return {"main_villain": main_out, "per_opponent": per_opponent}
