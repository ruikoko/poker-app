"""HRC export — converte raw HH GG para formato PokerStars-compativel.

FASE 1 cobre apenas a conversao de uma mao. O packaging em zip (build_queue_zip)
fica para COMMIT 3.

Decisoes (D1-D4 do plano FASE 1):
  D1: linha 1 mantem prefixo `Poker Hand #` (validado pt16 commit 0d18c52).
  D2: header LevelN(SB/BB(ante)) -> LevelN (SB/BB) sem ante embutido.
      Razao: HRC tem bug parsing ante na 2a parens (ja confirmado em pt16).
      Antes continuam nas linhas `<player>: posts the ante X` no corpo da HH.
  D3: hashes 7-8 hex sao substituidos por nicks reais via player_names.anon_map
      quando este existir. Sem anon_map -> hashes ficam (degrade graceful).
  D4: bounty inline em seats NAO e adicionado em FASE 1. HRC le do payouts.json.
"""
from __future__ import annotations
import json
import re


# Captura `LevelN(SB/BB(ante))` com numeros podendo ter virgulas de milhar.
# Ex: `Level17(2,500/5,000(600))` -> grupos: 17, 2,500, 5,000, 600.
_LEVEL_RE = re.compile(
    r"\bLevel(\d+)\(([\d,]+)/([\d,]+)\(([\d,]+)\)\)"
)


def _format_level_line(text: str) -> str:
    """Transforma `LevelN(SB/BB(ante))` em `LevelN (SB/BB)` (sem ante,
    sem virgulas)."""
    def repl(m: re.Match) -> str:
        n, sb, bb, _ante = m.groups()
        return f"Level{n} ({sb.replace(',', '')}/{bb.replace(',', '')})"
    return _LEVEL_RE.sub(repl, text)


def _replace_hashes(text: str, anon_map: dict) -> str:
    """Substitui literalmente cada hash do anon_map pelo respectivo nick.
    Mantem `Hero` intacto. Hashes nao mapeados ficam tal e qual.

    Ordena hashes por comprimento decrescente para evitar matches parciais
    quando dois hashes partilham prefixo (caso raro mas defensivo)."""
    if not anon_map:
        return text
    items = [
        (h, nick) for h, nick in anon_map.items()
        if h and h != "Hero" and nick
    ]
    items.sort(key=lambda kv: -len(kv[0]))
    for hash_id, nick in items:
        pat = re.compile(r"\b" + re.escape(hash_id) + r"\b")
        text = pat.sub(lambda m, n=nick: n, text)
    return text


def _coerce_player_names(pn) -> dict:
    if isinstance(pn, str):
        try:
            pn = json.loads(pn)
        except (ValueError, TypeError):
            return {}
    return pn if isinstance(pn, dict) else {}


def convert_gg_hh_to_pokerstars_compatible(hand: dict) -> str:
    """Converte raw HH GG para formato compativel com HRC.

    Hands non-GG (PokerStars, Winamax) passam tal e qual (pass-through) —
    Fase 2 tratara conversoes especificas se HRC reclamar de Winamax.

    Hands com `raw` vazio devolvem string vazia (caller deve filtrar)."""
    raw = (hand.get("raw") or "").strip()
    if not raw:
        return ""
    if hand.get("site") != "GGPoker":
        return hand.get("raw") or ""

    pn = _coerce_player_names(hand.get("player_names"))
    anon_map = pn.get("anon_map") or {}

    out = _format_level_line(raw)
    out = _replace_hashes(out, anon_map)
    return out
