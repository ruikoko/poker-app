"""
IRE (Indice de Reducao de Equity / Bounty Power) — v1, GG-only.

Mede a pressao do bounty do villain face ao call. Mais alto = mais incentivo
matematico para o hero pagar mesmo com equity baixa.

Formula:
    IRE = bounty_chips / (4 * call_chips + 2 * bounty_chips)

onde:
    bounty_chips = (bounty_pct / 100) * bounty_inicial_chips
    bounty_inicial_chips = SI * ratio
    SI = tournaments_meta.starting_stack (GG-only, populado do hero da 1a hand)
    ratio = 0.40 se tournament_name contem "Super KO" (case-insens), 0.25 default
    call_chips = min(stack_hero, stack_villain) — stack efectivo (apa[*].stack)

Pre-condicoes (qualquer falha => return None, IRE escondido):
    - hand.site == 'GGPoker'
    - match_method real (nao discord_placeholder_*)
    - tag *ko* em hm3_tags ou discord_tags (case-insens)
    - tournament_format in {'PKO', 'Mystery KO'}
    - tournaments_meta com starting_stack > 0
    - 1 villain (non-hero) all-in em qualquer rua. Multi-villain (2+) escondido em v1.
    - bounty_pct > 0
    - call_chips > 0
"""
from __future__ import annotations
import json
import logging
import re
from typing import Optional

logger = logging.getLogger(__name__)


BOUNTY_RATIO_OVERRIDES: list[tuple[str, float]] = [
    ("Super KO", 0.40),
]
DEFAULT_BOUNTY_RATIO = 0.25
ALLOWED_FORMATS = {"PKO", "Mystery KO"}
KO_TAG_NEEDLE = "ko"
_STREETS = ("preflop", "flop", "turn", "river")


def _has_ko_tag(hm3_tags, discord_tags) -> bool:
    for tag in (hm3_tags or []):
        if tag and KO_TAG_NEEDLE in tag.lower():
            return True
    for tag in (discord_tags or []):
        if tag and KO_TAG_NEEDLE in tag.lower():
            return True
    return False


def _resolve_bounty_ratio(tournament_name: Optional[str]) -> float:
    if not tournament_name:
        return DEFAULT_BOUNTY_RATIO
    lower = tournament_name.lower()
    for needle, ratio in BOUNTY_RATIO_OVERRIDES:
        if needle.lower() in lower:
            return ratio
    return DEFAULT_BOUNTY_RATIO


def _coerce_apa(apa) -> Optional[dict]:
    if isinstance(apa, str):
        try:
            apa = json.loads(apa)
        except (ValueError, TypeError):
            return None
    return apa if isinstance(apa, dict) else None


def _player_has_allin(actions: Optional[dict]) -> bool:
    if not actions:
        return False
    for street in _STREETS:
        for a in actions.get(street, []) or []:
            if isinstance(a, str) and "(All-In)" in a:
                return True
    return False


def _coerce_int(v) -> int:
    """bounty_pct vem como int (apa) ou TEXT (hand_villains). Coerce robusta."""
    if v is None:
        return 0
    if isinstance(v, (int, float)):
        return int(v)
    try:
        m = re.search(r"\d+", str(v))
        return int(m.group(0)) if m else 0
    except (ValueError, TypeError):
        return 0


def compute_ire(hand: dict, tm_meta: Optional[dict]) -> Optional[dict]:
    """Devolve dict {ire_pct, villain, call_chips, bounty_chips} ou None."""
    if hand.get("site") != "GGPoker":
        return None

    pn = hand.get("player_names") or {}
    if isinstance(pn, str):
        try:
            pn = json.loads(pn)
        except (ValueError, TypeError):
            pn = {}
    if not isinstance(pn, dict):
        pn = {}
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

    apa = _coerce_apa(hand.get("all_players_actions"))
    if not apa:
        return None
    meta = apa.get("_meta") or {}
    bb = meta.get("bb") or 0
    if bb <= 0:
        return None

    hero_stack = None
    villains_allin: list[tuple[str, dict]] = []
    for name, info in apa.items():
        if name == "_meta" or not isinstance(info, dict):
            continue
        if info.get("is_hero"):
            hero_stack = info.get("stack")
            continue
        if _player_has_allin(info.get("actions")):
            villains_allin.append((name, info))

    # Multi-villain (2+) e zero-villain ambos escondidos em v1.
    if len(villains_allin) != 1:
        return None

    villain_name, villain_info = villains_allin[0]
    villain_stack = villain_info.get("stack")
    if not hero_stack or not villain_stack:
        return None
    try:
        call_chips = int(min(float(hero_stack), float(villain_stack)))
    except (TypeError, ValueError):
        return None
    if call_chips <= 0:
        return None

    bounty_pct = _coerce_int(villain_info.get("bounty_pct"))
    if bounty_pct <= 0:
        # Fallback: players_list pelo nome real
        for p in (pn.get("players_list") or []):
            if not isinstance(p, dict):
                continue
            if p.get("name") == villain_name or p.get("real_name") == villain_name:
                bounty_pct = _coerce_int(p.get("bounty_pct"))
                break
    if bounty_pct <= 0:
        return None

    ratio = _resolve_bounty_ratio(tm_meta.get("tournament_name"))
    bounty_inicial_chips = si * ratio
    bounty_chips = (bounty_pct / 100.0) * bounty_inicial_chips
    if bounty_chips <= 0:
        return None

    denom = 4.0 * call_chips + 2.0 * bounty_chips
    if denom <= 0:
        return None
    ire_pct = (bounty_chips / denom) * 100.0
    if ire_pct <= 0:
        return None

    return {
        "ire_pct": round(ire_pct, 1),
        "villain": villain_name,
        "call_chips": call_chips,
        "bounty_chips": int(round(bounty_chips)),
    }
