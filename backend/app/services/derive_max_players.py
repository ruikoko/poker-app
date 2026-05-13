"""Derive HRC `max_players` hint from a PS-compatible hand history.

Conta apenas jogadores **relevantes à decisão do hero** preflop:
  - Open agressor (raise/limp/bet)
  - Jogadores que entraram voluntariamente no pot antes de hero
    (calls, raises, limps, 3-bets)
  - Hero
  - Jogadores em posições atrás de hero que ainda não agiram preflop

Foldados (antes do agressor ou entre agressor↔hero) NÃO contam — o HRC
ignora-os do solver, evitando que a árvore exploda com seats vazios.

Saída clamped a 2..9 (range aceite pelo HRC).

Fonte: pt23 fix Bug B do watcher. O caller (`setup_hand` no watcher
patched) lê `max_players` do payouts.json e passa a `set_hand_mode_players`.
"""
from __future__ import annotations
import re
from typing import Optional


# Seat: NICK (X in chips), with X possibly comma-grouped.
_SEAT_RE = re.compile(r"^Seat (\d+): (\S+) \(\d", re.MULTILINE)
_HERO_RE = re.compile(r"^Dealt to (\S+)", re.MULTILINE)
# Action lines: "<nick>: folds" / "calls X" / "raises X to Y" / "bets X" / "checks".
# `\b` after the verb evita capturar "raised" no SUMMARY.
_ACTION_RE = re.compile(
    r"^(\S+): (folds|calls|raises|bets|checks)\b",
    re.MULTILINE,
)


def _clamp(n: int) -> int:
    return min(max(n, 2), 9)


def derive_max_players(hh_text: Optional[str]) -> int:
    """Devolve o nº de jogadores relevantes à decisão do hero, em [2, 9].

    Regra detalhada no docstring do módulo. Defensivo: parsing erro,
    HH vazio, hero não encontrado, etc. → devolve 2.
    """
    if not hh_text:
        return 2

    # 1. parse seats
    seats: dict[int, str] = {}
    for m in _SEAT_RE.finditer(hh_text):
        seats[int(m.group(1))] = m.group(2)
    if len(seats) < 2:
        return 2

    # 2. find hero
    hero_m = _HERO_RE.search(hh_text)
    if not hero_m:
        return _clamp(len(seats))
    hero = hero_m.group(1)

    # 3. extract preflop block
    start = hh_text.find("*** HOLE CARDS ***")
    if start < 0:
        return _clamp(len(seats))
    candidates = [
        hh_text.find("*** FLOP ***", start),
        hh_text.find("*** SUMMARY ***", start),
    ]
    candidates = [c for c in candidates if c > 0]
    end = min(candidates) if candidates else len(hh_text)
    preflop = hh_text[start:end]

    # 4. ordered list of preflop actions, filtered to known players
    nicks = set(seats.values())
    actions: list[tuple[str, str]] = []
    for m in _ACTION_RE.finditer(preflop):
        nick, kind = m.group(1), m.group(2)
        if nick in nicks:
            actions.append((nick, kind))

    # 5. find hero's first preflop action
    hero_idx: Optional[int] = None
    for i, (nick, _) in enumerate(actions):
        if nick == hero:
            hero_idx = i
            break

    # 6. classify others by what happened before hero's turn
    slice_end = hero_idx if hero_idx is not None else len(actions)
    voluntary_before: set[str] = set()
    acted_before: set[str] = set()
    for nick, kind in actions[:slice_end]:
        if nick == hero:
            continue
        acted_before.add(nick)
        if kind != "folds":
            voluntary_before.add(nick)

    # Walk-to-BB (ou HH cortado cedo sem acção voluntária) → degenerate.
    # Por convenção, HRC modela este spot como SB-vs-BB (2 jogadores).
    if hero_idx is None and not voluntary_before:
        return 2

    # Quem ainda não agiu = todos os seats menos os que já agiram menos hero.
    still_to_act = nicks - acted_before - {hero}

    count = len(voluntary_before) + 1 + len(still_to_act)
    return _clamp(count)
