"""Derive HRC `max_players` hint — SPAN âncora→BB (LEI do Rui, REGRAS_NEGOCIO §15).

Conta-se de uma **ÂNCORA, inclusivé, até à BB** — span POSICIONAL (inclui os
folders entre a âncora e a BB), NÃO uma contagem de participantes:

  1. Herói foldou ANTES de qualquer ação voluntária (pote por abrir até ele):
     âncora = posição do **HERÓI**.
  2. Caso contrário: âncora = posição da **1ª AÇÃO VOLUNTÁRIA** (call/limp/raise/bet).

`max = (índice da BB − índice da âncora + 1)` na ordem preflop. A BB é o último
seat na ordem (`hrc_idx = N−1`), logo `max = N − idx_âncora`. **Teto 6** (emenda de
produto do Rui, 10 Jun): `max = min(span, 6)`, mínimo 2 — mesmo 9-max com UTG
all-in (span 9) → 6. Clamp final **2..6**.

pt67 (#HRC-MAX-PLAYERS-SPAN-NOT-PARTICIPANTS): substitui a contagem antiga de
PARTICIPANTES (`voluntary_before + hero + still_to_act`), que **descartava os
folders entre a âncora e o herói** → subcontava quando o herói era tardio (ex.: BB
com folds no meio). Cross-check pt66: GG-6028190109 (6-max, herói BU, âncora HJ)=5;
GG-6039094225 (8-max, herói BB, âncora SB)=2; GG-6029013400 (8-max, herói BB,
âncora HJ)=5 (o código antigo dava 2).

Reusa `derive_seats_in_preflop_order` (fonte única do mapping nick↔hrc_idx↔position
do pipeline HRC) — qualquer mudança de convenção fica centralizada lá. Import lazy
(`queue_export` importa este módulo → evita ciclo).

O caller (`build_queue_zip` em `queue_export.py`) escreve o resultado em `meta.json`
como `max_players`; o watcher lê-o e passa a `set_hand_mode_players`.
"""
from __future__ import annotations
import re
from typing import Optional

# Hero é a linha `Dealt to <nick> [<cards>]` — só o Hero tem brackets de cartas
# em PS HH standard (em GG pós-`_replace_hashes` todos os seats têm `Dealt to`
# sem brackets, por isso exigimos `[`). `.+?` tolera nicks com espaços.
_HERO_RE = re.compile(r"^Dealt to (.+?) \[", re.MULTILINE)
# Action lines: "<nick>: folds|calls|raises|bets|checks". `\b` evita "raised" no
# SUMMARY. `.+?` (não `\S+`) tolera nicks com espaços.
_ACTION_RE = re.compile(
    r"^(.+?): (folds|calls|raises|bets|checks)\b",
    re.MULTILINE,
)
# Dinheiro voluntário no pote (limp/call/raise/bet). Folds e checks NÃO contam.
_VOLUNTARY = {"calls", "raises", "bets"}


def _clamp(n: int) -> int:
    # Emenda Rui (10 Jun): teto 6 em qualquer situação (mínimo 2 mantém-se).
    return min(max(n, 2), 6)


def derive_max_players(hh_text: Optional[str]) -> int:
    """Span âncora→BB em [2, 9]. Defensivo (parsing erro / degenerate) → 2."""
    if not hh_text:
        return 2

    # Import lazy: `queue_export` importa este módulo (ciclo a nível de módulo).
    from app.services.queue_export import (
        derive_seats_in_preflop_order,
        find_preflop_marker,
    )

    # Ordem preflop canónica: hrc_idx 0 = first-to-act (UTG), hrc_idx N−1 = BB.
    order = derive_seats_in_preflop_order(hh_text)
    if len(order) < 2:
        return 2
    n = len(order)
    nick_to_idx = {e["nick"]: e["hrc_idx"] for e in order}

    # Hero (para a regra 1).
    hero_m = _HERO_RE.search(hh_text)
    hero = hero_m.group(1).strip() if hero_m else None
    hero_idx = nick_to_idx.get(hero) if hero else None

    # Bloco preflop (cross-site, via marker canónico).
    start = find_preflop_marker(hh_text)
    if start is None:
        return 2
    ends = [
        e for e in (
            hh_text.find("*** FLOP ***", start),
            hh_text.find("*** SUMMARY ***", start),
        ) if e > 0
    ]
    end = min(ends) if ends else len(hh_text)
    preflop = hh_text[start:end]

    # Âncora: percorre as ações por ordem. O 1º de:
    #   (a) ação voluntária  → regra 2 (âncora = essa posição); OU
    #   (b) fold do herói    → regra 1 (âncora = herói)
    # determina a âncora.
    anchor_idx: Optional[int] = None
    for m in _ACTION_RE.finditer(preflop):
        nick, kind = m.group(1).strip(), m.group(2)
        if nick not in nick_to_idx:
            continue
        if kind in _VOLUNTARY:
            anchor_idx = nick_to_idx[nick]          # regra 2
            break
        if kind == "folds" and nick == hero:
            anchor_idx = hero_idx                   # regra 1
            break

    if anchor_idx is None:
        # Walk-to-BB / sem ação voluntária / herói desconhecido → SB-vs-BB (2)
        # por convenção (HRC modela este spot degenerate como heads-up).
        return 2

    # Span âncora→BB inclusive: BB = hrc_idx (n−1) → (n−1) − anchor_idx + 1 = n − anchor_idx.
    return _clamp(n - anchor_idx)
