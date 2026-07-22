"""FACTOS da HH crua — helpers ÚNICOS (fonte única, #LEI-FIX-NA-CAUSA).

Nascem para o painel de reconciliação dos prints fora de tempo (22 Jul 2026),
mas são A régua de "houve ação pós-flop / houve showdown" para quem precisar —
não se reimplementa noutro sítio.

- `hero_postflop_betting`: houve RONDA DE APOSTAS pós-flop com o Hero
  (bets/checks/calls/raises depois do *** FLOP ***). ⚠️ "Chegou ao flop" NÃO
  chega: um triplo all-in pré-flop com board a correr é SEM pós-flop (provado
  na GG-6180819531 pelo Rui) — a régua é AÇÃO, não distribuição de cartas.
  (Lista de ações ditada pelo Rui; um fold-do-Hero-a-bet pós-flop sem outra
  ação sua não conta — se aparecer um caso real, é palavra do Rui.)
- `real_showdown`: houve showdown REAL — linhas `X: shows [...]` — e não o
  marcador `*** SHOWDOWN ***` cru, que o GG emite espúrio em mãos fold-to
  (a mesma regra do passo 4 do conversor HRC, `queue_export.py:1154`).
"""
from __future__ import annotations

import re

_FLOP_MARK = "*** FLOP ***"
_SUMMARY_MARK = "*** SUMMARY ***"
# ações de aposta (ditadas pelo Rui): bet/check/call/raise
_HERO_BET_ACTION_RE = re.compile(r"^Hero: (?:bets|checks|calls|raises)\b", re.M)
# showdown real: alguém MOSTROU cartas ("<key>: shows [Ah Kd] (...)")
_SHOWS_RE = re.compile(r"^[^:\n]+: shows \[", re.M)


def _postflop_slice(raw: str) -> str:
    """O troço da HH entre o *** FLOP *** e o SUMMARY ('' se não houve flop)."""
    raw = raw or ""
    i = raw.find(_FLOP_MARK)
    if i == -1:
        return ""
    j = raw.find(_SUMMARY_MARK, i)
    return raw[i:j if j != -1 else len(raw)]


def hero_postflop_betting(raw: str) -> bool:
    """True sse o Hero teve AÇÃO DE APOSTA pós-flop (bets/checks/calls/raises
    depois do flop). All-in pré com board a correr → False; fold pré → False."""
    return bool(_HERO_BET_ACTION_RE.search(_postflop_slice(raw)))


def real_showdown(raw: str) -> bool:
    """True sse houve showdown REAL (linhas 'X: shows [...]'). O marcador
    `*** SHOWDOWN ***` sozinho não conta (espúrio em fold-to)."""
    return bool(_SHOWS_RE.search(raw or ""))
