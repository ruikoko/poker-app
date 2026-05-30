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
      (pt24 revisao revertida pt28-v3 smoke 20 Maio: HRC parser rejeita HH
      com ", $X.XX bounty)" nas Seat lines com popup "Hand Import: No valid
      hand-history found in the Clipboard". Testes A/B do Rui isolaram
      bounty inline como causa raiz. Nicks resolvidos via `_replace_hashes`
      continuam OK. Bounties continuam disponiveis no payouts.json paralelo
      — o HRC le bounties por essa via, nao via Seat lines. Tech debt
      `#HRC-GG-KOS-EXTRACTION` reabre.)
"""
from __future__ import annotations
import io
import json
import logging
import os
import re
import zipfile
from datetime import datetime, timezone
from typing import Any, Optional

from app.routers.hands import normalize_tag_key
from app.services.derive_max_players import derive_max_players

logger = logging.getLogger("queue_export")

# Tags FT-style → equity model `malmuth_harville_icm`. Restantes mãos default →
# `multi_table_icm`. Comparação via `normalize_tag_key` (#B17): case-insensitive
# + hyphen→space, daí 'ICM FT' ≡ 'icm-ft' ≡ 'ICM-ft' batem todos a 'icm ft'.
# Substituiu pt23 os sets `_EQUITY_FT_HM3` / `_EQUITY_FT_DISCORD` (case-sensitive,
# exigiam manter ambas as formas à mão).
_EQUITY_FT_NORM_KEYS = {"icm ft", "icm pko ft"}


# pt41 #HERO-BOUNTY-FROM-TS-DERIVATION — formatos de torneio com bounty real.
# Valores lowercase (comparados contra `tournament_format` normalizado). FONTE
# ÚNICA partilhada com o gate SQL do Andar 1 (`services/hrc_queue.py`) — não
# duplicar (anti-drift, à la `classify_aggressor_source`).
#   BOUNTY_FORMATS   — qualquer evento com bounty (decide se há token no HH).
#   MYSTERY_FORMATS  — HRC não modela Mystery KO → excluídos do /hrc (gate).
#   TS_GATED_FORMATS — exigem `tournament_summaries.buy_in_bounty` (GG only).
BOUNTY_FORMATS = ("pko", "super ko", "ko", "mystery ko", "mystery")
MYSTERY_FORMATS = ("mystery ko", "mystery")
TS_GATED_FORMATS = ("pko", "super ko", "ko")
# pt42c #WN-BOUNTY-NULL-IN-HRC-PIPELINE — formatos bounty WN com pipeline
# de injecção via HH crua (não TS, ao contrário do GG). Mystery KO fica
# fora (HRC não modela; já gated em MYSTERY_FORMATS).
WINAMAX_BOUNTY_FORMATS = ("pko", "super ko", "ko")


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


# pt25d: helpers para seat ↔ HRC player index ↔ position label.
# HRC scripting convention oficial (docs): índices 0..N-1 onde
# 0 = first-to-act preflop (UTG em N>=3; BU/SB em HU), N-2 = SB, N-1 = BB.
# Compatível com `ctx.getPlayerIndex*()` e `ctx.getActivePlayer()` do HRC
# engine. Preflop turn order = [0, 1, ..., N-1] sequencial (BB sempre último).
_SEAT_ALL_RE = re.compile(r"^Seat (\d+): (.+?) \(\d", re.MULTILINE)
_BUTTON_RE = re.compile(r"Seat #(\d+) is the button")
# Linhas de post de blind, cross-site (GG/PS com colon, WN/WPN sem).
# Ex.: "Hero: posts small blind 200" | "Dvstrr posts small blind 1000".
_POSTS_BLIND_RE = re.compile(
    r"^(.+?):?\s+posts (small|big) blind\s+([\d,.]+)", re.MULTILINE
)
# Labels de late position por distância ao botão (vocab Rui): 1 antes do
# botão = CO, 2 = HJ, 3 = MP, 4 = UTG1, 5 = UTG, 6 = UTG2.
_DEAD_BUTTON_DISTANCE_LABELS = ("CO", "HJ", "MP", "UTG1", "UTG", "UTG2")
# pt25b: regex tolera ambos os formatos de action line:
# - PS/GG: `Hero: raises 800 to 1200` (com colon após nick)
# - Winamax: `blueballs67 raises 8000 to 16000` (sem colon)
# `(?::)?` torna o `:` opcional. `(?: ... )?` é non-capturing.
_PREFLOP_OPEN_RE = re.compile(r"^(.+?)(?::)?\s+(raises|bets)\b", re.MULTILINE)


def find_preflop_marker(hh_text: str) -> Optional[int]:
    """pt25b — posição do marker preflop num HH, agnóstico de site.

    Aceita 2 variantes:
    - `*** HOLE CARDS ***` (PokerStars, GGPoker)
    - `*** PRE-FLOP ***` (Winamax)

    Devolve a posição mais cedo (qual encontrar primeiro) ou None se nenhum
    estiver presente.
    """
    if not hh_text:
        return None
    candidates: list = []
    for marker in ("*** HOLE CARDS ***", "*** PRE-FLOP ***"):
        pos = hh_text.find(marker)
        if pos >= 0:
            candidates.append(pos)
    return min(candidates) if candidates else None


# Labels canónicos por nº de jogadores sentados na mão. Convenção do Rui
# (distância geométrica ao botão): CO=1 antes, HJ=2, MP=3, UTG1=4, UTG=5,
# UTG2=6. Lista em ORDEM DE ACÇÃO preflop: idx 0 = mais distante do botão
# presente (= first-to-act), idx N-2 = SB, idx N-1 = BB. Em HU (n=2) o botão
# é o SB. Para tables com seats vazios tratamos como N-handed.
# ⚠️ ESPELHADA em mtt_advanced_canonical_2026.js:POSITION_LABELS_BY_N — manter
# em sync (semântica idêntica). O botão chama-se "BTN" aqui; na camada de
# sizings HRC converte para "BU" (nome do HRC) via _canonical_3bet_position.
_POSITION_LABELS_BY_N: dict = {
    2: ["SB", "BB"],
    3: ["BTN", "SB", "BB"],
    4: ["CO", "BTN", "SB", "BB"],
    5: ["HJ", "CO", "BTN", "SB", "BB"],
    6: ["MP", "HJ", "CO", "BTN", "SB", "BB"],
    7: ["UTG1", "MP", "HJ", "CO", "BTN", "SB", "BB"],
    8: ["UTG", "UTG1", "MP", "HJ", "CO", "BTN", "SB", "BB"],
    9: ["UTG2", "UTG1", "UTG", "MP", "HJ", "CO", "BTN", "SB", "BB"],  # n=9/UTG2 provisório
}


def _parse_posted_blinds(hh_text: str) -> dict:
    """Parseia as linhas `posts small/big blind` → `{'small': (nick, amount),
    'big': (nick, amount)}`. Devolve só as chaves encontradas (pode ser
    parcial / vazio). Montantes em chips (decimais truncados via int(float)).
    """
    out: dict = {}
    if not hh_text:
        return out
    for m in _POSTS_BLIND_RE.finditer(hh_text):
        nick = m.group(1).strip()
        which = m.group(2)
        if which in out:  # 1º vence (defensivo contra re-posts)
            continue
        try:
            amt = int(float(m.group(3).replace(",", "")))
        except ValueError:
            continue
        out[which] = (nick, amt)
    return out


def _blinds_match(hh_text: str, posted: dict) -> bool:
    """Cross-check: os montantes postados (SB/BB) batem com o header da HH?

    Defesa contra HH adulterada / parsing parcial: se o SB ou BB postado não
    bate com o nível do header, o caller (dead button) rejeita a derivação em
    vez de produzir posições erradas.
    """
    header_blinds = _extract_blinds_from_header(hh_text)
    if not header_blinds:
        return False
    sb_h, bb_h = header_blinds
    sb = posted.get("small")
    bb = posted.get("big")
    if not sb or not bb:
        return False
    return sb[1] == sb_h and bb[1] == bb_h


def _derive_seats_dead_button(
    seats_dict: dict, btn_seat: int, hh_text: str
) -> list:
    """Dead button: o botão aponta para um seat vazio (eliminação típica de
    MTT). Sem jogador no botão, não há linha BTN — ancoramos nas blinds
    postadas + distância geométrica ao botão morto.

    Algoritmo:
    1. Parseia quem postou SB/BB; cross-check com o header (`_blinds_match`).
    2. Ordena os seats ocupados em sentido horário a partir do seat logo a
       seguir ao botão (morto): `cw = [seats > btn] + [seats < btn]`. O 1º é o
       SB, o 2º o BB (rejeita se não bater — só tratamos dead button com
       blinds vivas).
    3. SB/BB ganham os seus labels; os restantes seats (entre BB e o botão)
       recebem CO/HJ/MP/... por distância ao botão (o mais próximo = CO).
    4. Ordem de acção preflop (hrc_idx) = [não-blinds (UTG→CO), SB, BB].

    Devolve `[]` se as blinds não baterem / parsing falhar — graceful, igual
    aos outros early-returns de `derive_seats_in_preflop_order`.
    """
    posted = _parse_posted_blinds(hh_text)
    if not _blinds_match(hh_text, posted):
        return []
    sb_nick = posted["small"][0]
    bb_nick = posted["big"][0]
    nick_to_seat = {nick: seat for seat, nick in seats_dict.items()}
    sb_seat = nick_to_seat.get(sb_nick)
    bb_seat = nick_to_seat.get(bb_nick)
    if sb_seat is None or bb_seat is None:
        return []

    occupied = sorted(seats_dict.keys())
    # Sentido horário a partir do seat logo após o botão morto.
    cw = [s for s in occupied if s > btn_seat] + [s for s in occupied if s < btn_seat]
    if len(cw) < 2 or cw[0] != sb_seat or cw[1] != bb_seat:
        return []

    middles = cw[2:]  # seats entre BB e o botão (UTG-most → CO-most)
    pos_for_seat = {sb_seat: "SB", bb_seat: "BB"}
    # O mais próximo do botão (último em cw) = CO; depois HJ, MP, ...
    for j, seat in enumerate(reversed(middles)):
        if j >= len(_DEAD_BUTTON_DISTANCE_LABELS):
            return []  # mais seats do que labels conhecidas → não fabricar
        pos_for_seat[seat] = _DEAD_BUTTON_DISTANCE_LABELS[j]

    action_order = middles + [sb_seat, bb_seat]
    return [
        {
            "seat": seat,
            "position": pos_for_seat[seat],
            "hrc_idx": hrc_idx,
            "nick": seats_dict[seat],
        }
        for hrc_idx, seat in enumerate(action_order)
    ]


def derive_seats_in_preflop_order(hh_text: str) -> list:
    """pt25d — fonte canónica do mapping seat ↔ HRC player index ↔ position
    label ↔ nick, ordenado pre-flop por convenção HRC docs (UTG primeiro =
    hrc_idx 0; BB último = hrc_idx N-1).

    Parsing:
    - Header (pre `find_preflop_marker`): Seat lines com nick + chip stack
    - Button: `Seat #N is the button` (universal nos 4 sites)
    - First-to-act preflop:
        * N >= 3 (incl. 3-handed onde BU é first-to-act): button + 3 wraps mod N
        * N == 2 (HU): button (BU/SB age primeiro preflop)

    Posições labelled por convenção `_POSITION_LABELS_BY_N[N]` onde N é o
    nº de jogadores sentados na mão (não o table_format). Mesa 6-max com
    5 sentados → tratada como 5-handed (CO desaparece). Label "BU" alinhado
    com vocab da Strategy Table HRC (pt25e Bloco 2 follow-up; era "BTN" em
    pt25d/Bloco 1).

    Devolve `[]` se parsing falhar (sem button, sem seats). Quando o button
    aponta para um seat vazio (dead button, eliminação MTT) despacha para
    `_derive_seats_dead_button` (ancora nas blinds postadas + distância
    geométrica ao botão morto). Cada entry: `{seat: int, position: str,
    hrc_idx: int, nick: str}`.

    Sample 5-handed INTERSTELLAR (button=Seat 2 imbagosu):
        idx 0 = UTG (Seat 5, blueballs67)
        idx 1 = HJ  (Seat 1, yousnouf75)
        idx 2 = BU  (Seat 2, imbagosu)
        idx 3 = SB  (Seat 3, Beu_Teu)
        idx 4 = BB  (Seat 4, thinvalium)
    """
    if not hh_text:
        return []
    end = find_preflop_marker(hh_text)
    header = hh_text[:end] if end is not None else hh_text

    seats_dict: dict = {}
    for m in _SEAT_ALL_RE.finditer(header):
        seats_dict[int(m.group(1))] = m.group(2).strip()
    if len(seats_dict) < 2:
        return []

    btn_m = _BUTTON_RE.search(hh_text)
    if not btn_m:
        return []
    btn_seat = int(btn_m.group(1))
    seat_list = sorted(seats_dict.keys())
    if btn_seat not in seat_list:
        # Dead button: botão num seat vazio (eliminação). Ancorar nas blinds.
        return _derive_seats_dead_button(seats_dict, btn_seat, hh_text)

    btn_idx_in_list = seat_list.index(btn_seat)
    n = len(seat_list)
    # First-to-act preflop offset relativo ao button (no seat_list ordenado):
    # N==2 (HU): BU/SB (botão) age primeiro → offset 0.
    # N>=3: UTG = botão + 3 (wraps mod N para 3/4-handed, onde BU/UTG colapsam).
    first_to_act_offset = 0 if n == 2 else 3

    labels = _POSITION_LABELS_BY_N.get(n) or [f"POS{i}" for i in range(n)]

    out: list = []
    for hrc_idx in range(n):
        seat_in_list = (btn_idx_in_list + first_to_act_offset + hrc_idx) % n
        seat_num = seat_list[seat_in_list]
        out.append({
            "seat": seat_num,
            "position": labels[hrc_idx] if hrc_idx < len(labels) else f"POS{hrc_idx}",
            "hrc_idx": hrc_idx,
            "nick": seats_dict[seat_num],
        })
    return out


def derive_table_format(hh_text: str) -> int:
    """pt25b — extrai table_format (N-max) do header, universal nos 4 sites.

    PS: `Table '3983882920 23' 6-max Seat #5 is the button`
    GG: `Table '155' 8-max Seat #1 is the button`
    WN: `Table: 'INTERSTELLAR(...)' 6-max (real money) Seat #2 is the button`
    WPN: `Table '39' 8-max Seat #1 is the button`

    Fallback 8 com log warning se não encontrar (defensive).
    """
    if not hh_text:
        return 8
    m = re.search(r"\b(\d+)-max\b", hh_text)
    if m:
        try:
            return int(m.group(1))
        except ValueError:
            pass
    logger.warning("derive_table_format: no N-max in header, fallback 8")
    return 8


def _build_nick_to_hrc_index(hh_text: str) -> dict:
    """Mapa nick → HRC player index. Wrapper de `derive_seats_in_preflop_order`
    para preservar chamadas existentes (e.g. `derive_real_aggressor_position`).

    Devolve `{}` se parsing falhar.
    """
    seats = derive_seats_in_preflop_order(hh_text)
    return {s["nick"]: s["hrc_idx"] for s in seats}


def derive_real_aggressor_position(hh_text: str) -> Optional[int]:
    """pt25d — devolve o HRC player index (convenção docs: UTG=0 first-to-act
    preflop, SB=N-2, BB=N-1) do primeiro a abrir o pot preflop com raise/bet
    voluntário.

    Excepções (devolvem None):
    - Nenhum raise/bet preflop (limp pot, walk-to-BB)
    - Parsing falha (sem button, sem marker preflop, etc.)
    - Nick do primeiro raiser não está nos seats parseados (HH inválido)

    SB-aggressor NÃO é early-return None desde pt25d. Em pt25/pt25b SB=idx 0
    fazia o aggressor parecer "primeiro a agir preflop" sem ser; em convenção
    HRC docs SB=N-2 e a função devolve o índice correcto.

    Calls preflop (incluindo SB-completes) NÃO contam como abertura.

    pt25b: marker preflop resolved via `find_preflop_marker` (PS/GG/WPN
    usam `*** HOLE CARDS ***`, Winamax usa `*** PRE-FLOP ***`).
    `_PREFLOP_OPEN_RE` tolera ambos os formatos de action line (com colon
    PS/GG e sem colon Winamax/WPN).
    """
    if not hh_text:
        return None
    nick_to_idx = _build_nick_to_hrc_index(hh_text)
    if not nick_to_idx:
        return None

    start = find_preflop_marker(hh_text)
    if start is None:
        return None
    end_flop = hh_text.find("*** FLOP ***", start)
    end_summary = hh_text.find("*** SUMMARY ***", start)
    ends = [e for e in (end_flop, end_summary) if e > 0]
    end = min(ends) if ends else len(hh_text)
    preflop = hh_text[start:end]

    m = _PREFLOP_OPEN_RE.search(preflop)
    if not m:
        return None  # limp pot / walk-to-BB
    nick = m.group(1).strip()
    idx = nick_to_idx.get(nick)
    if idx is None:
        return None  # nick não está em seats (HH inválido)
    return idx


# pt25e #META-AGGRESSOR-REAL-ACTION: regex em cadeia para extrair (SB, BB)
# do header da HH, cobrindo os 4 sites. Tenta os padrões mais específicos
# primeiro para evitar falsos positivos (e.g., WN tem 3 números nas parens
# do header — ante/sb/bb — e a regex genérica `(sb/bb)` apanharia ante/sb).
_BLINDS_WN_RE = re.compile(r"\((\d[\d,]*)/(\d[\d,]*)/(\d[\d,]*)\)")
_BLINDS_GG_PRECONVERT_RE = re.compile(
    r"\bLevel\d+\(([\d,]+)/([\d,]+)\([\d,]+\)\)"
)
_BLINDS_GENERIC_RE = re.compile(
    r"\(([\d,]+(?:\.\d+)?)/([\d,]+(?:\.\d+)?)\)"
)


def _extract_blinds_from_header(hh_text: str) -> Optional[tuple]:
    """pt25e — heurística cross-site para extrair (SB, BB) em chips do
    header da HH (primeira linha).

    Cobertura:
    - WN: `Holdem no limit (ante/sb/bb)` — 3 números separados por `/`
    - GG pre-convert: `LevelN(SB/BB(ante))` — ante embutido em 2ª parens
    - PS / GG post-convert / WPN: `(SB/BB)` genérico, com ou sem decimais

    Devolve `(sb, bb)` ints (decimais truncados via int(float(...))) ou
    `None` se nenhum padrão match — caller (`derive_aggressor_real_action`)
    devolve None nesse caso (graceful, prune off para essa mão).
    """
    if not hh_text:
        return None
    header = hh_text.split("\n", 1)[0]
    m = _BLINDS_WN_RE.search(header)
    if m:
        try:
            sb = int(float(m.group(2).replace(",", "")))
            bb = int(float(m.group(3).replace(",", "")))
            if bb > 0:
                return sb, bb
        except ValueError:
            pass
    m = _BLINDS_GG_PRECONVERT_RE.search(header)
    if m:
        try:
            sb = int(m.group(1).replace(",", ""))
            bb = int(m.group(2).replace(",", ""))
            if bb > 0:
                return sb, bb
        except ValueError:
            pass
    m = _BLINDS_GENERIC_RE.search(header)
    if m:
        try:
            sb = int(float(m.group(1).replace(",", "")))
            bb = int(float(m.group(2).replace(",", "")))
            if bb > 0:
                return sb, bb
        except ValueError:
            pass
    return None


# pt25e #META-AGGRESSOR-REAL-ACTION: regex para parsear o sizing dentro da
# linha do primeiro raise/bet preflop. Tolera comma-thousands e decimais
# (WPN) e o "and is all-in" suffix (PS/GG quando shove).
_RAISE_TO_AMOUNT_RE = re.compile(r"raises\s+[\d,.]+\s+to\s+([\d,.]+)")
_BET_AMOUNT_RE = re.compile(r"bets\s+([\d,.]+)")


def _resolve_position_for_nick(hh_text: str, nick: str) -> Optional[str]:
    """pt25e #META-AGGRESSOR-POSITION — devolve a position canónica
    (`_POSITION_LABELS_BY_N`) do `nick` no preflop order, ou `None` se o
    parsing de seats falhar / o nick não estiver entre os seats sentados.

    Usa `derive_seats_in_preflop_order` (única fonte de verdade do mapping
    seat ↔ hrc_idx ↔ position label) — qualquer mudança de convenção fica
    centralizada lá.
    """
    if not nick:
        return None
    for s in derive_seats_in_preflop_order(hh_text):
        if s.get("nick") == nick:
            pos = s.get("position")
            return pos if isinstance(pos, str) else None
    return None


def derive_aggressor_real_action(
    hh_text: str,
    level_sb: int,
    level_bb: int,
) -> Optional[dict]:
    """pt25e #META-AGGRESSOR-REAL-ACTION — devolve `{type, size_bb, position}`
    do primeiro raise/bet preflop voluntário, agnóstico de site
    (PS/GG/WN/WPN).

    O watcher precisa deste dado para Bug G passo 3 (selecionar a linha do
    sizing real do raiser inicial na tree HRC para a 2ª run em Selected
    Subtree). pt25e #META-AGGRESSOR-POSITION estendeu o dict com `position`
    (string maiúsculas — labels de `_POSITION_LABELS_BY_N`): Bloco 2 do
    watcher faz OCR confinado à coluna Player da Strategy Table HRC e
    clica a primeira linha onde Player == position. Reduz drasticamente o
    custo de OCR (vocabulário fechado de ~6 strings curtos vs OCR genérico).

    Argumentos:
    - hh_text: HH raw text (pode estar pré ou pós-conversão PS-compat).
    - level_sb, level_bb: blinds do level da mão em chips.

    Devolve:
    - `{"type": "raise", "size_bb": float, "position": str|None}` quando
      primeira accção é `raises X to Y` → size_bb = Y / level_bb
      (arredondado a 2 decimais).
    - `{"type": "bet", "size_bb": float, "position": str|None}` para
      `bets X` → size_bb = X / BB.
    - `position` segue `_POSITION_LABELS_BY_N`: HU=`BU/SB`/`BB`; 3-handed
      `BU`/`SB`/`BB`; 4=`UTG`/`BU`/`SB`/`BB`; 5=`UTG`/`HJ`/`BU`/`SB`/`BB`;
      6=`UTG`/`HJ`/`CO`/`BU`/`SB`/`BB`; 7..9 includem `EP`/`MP`/`EP1`/`EP2`.
      Label "BU" alinhado com vocab Strategy Table HRC (pt25e Bloco 2
      follow-up; era "BTN" em pt25d/Bloco 1).
      `None` quando parsing de seats falha ou nick não está nos seats.
    - `None` (dict inteiro) quando: mão sem raise/bet preflop (limps+folds,
      walk-to-BB), marker preflop ausente, level_bb inválido, parsing do
      sizing falha.

    Reaproveita `find_preflop_marker` (pt25b cross-site) e `_PREFLOP_OPEN_RE`
    (pt25b colon-opcional) para localizar o primeiro accionamento; resolve
    a position via `_resolve_position_for_nick`.
    """
    if not hh_text:
        return None
    if not isinstance(level_bb, int) or level_bb <= 0:
        return None
    start = find_preflop_marker(hh_text)
    if start is None:
        return None
    end_flop = hh_text.find("*** FLOP ***", start)
    end_summary = hh_text.find("*** SUMMARY ***", start)
    ends = [e for e in (end_flop, end_summary) if e > 0]
    end = min(ends) if ends else len(hh_text)
    preflop = hh_text[start:end]
    m = _PREFLOP_OPEN_RE.search(preflop)
    if not m:
        return None
    nick = m.group(1).strip()
    action_type = m.group(2)
    line_start = preflop.rfind("\n", 0, m.start()) + 1
    line_end = preflop.find("\n", m.end())
    if line_end < 0:
        line_end = len(preflop)
    line = preflop[line_start:line_end]
    position = _resolve_position_for_nick(hh_text, nick)
    if action_type == "raises":
        sm = _RAISE_TO_AMOUNT_RE.search(line)
        if not sm:
            return None
        try:
            chips = float(sm.group(1).replace(",", ""))
        except ValueError:
            return None
        return {
            "type": "raise",
            "size_bb": round(chips / level_bb, 2),
            "position": position,
        }
    sm = _BET_AMOUNT_RE.search(line)
    if not sm:
        return None
    try:
        chips = float(sm.group(1).replace(",", ""))
    except ValueError:
        return None
    return {
        "type": "bet",
        "size_bb": round(chips / level_bb, 2),
        "position": position,
    }


# ---------------------------------------------------------------------------
# pt29 Fase 2 — converter GG -> PokerStars-compat (8 transformacoes)
#
# Smoke pt28-v3 (20 Maio) + testes A/B manuais do Rui isolaram que o HRC
# parser rejeita HH GG com varias diferencas vs formato PokerStars autentico.
# Esta seccao implementa as 8 transformacoes que tornam a HH aceitavel pelo
# HRC, validadas empiricamente:
#   1. Header `Poker Hand #TM<id>` -> `PokerStars Hand #<id>`
#   2. Level spacing: `Level14 (1750/3500)` -> `Level 14 (1750/3500)`
#   3. Bounty PS format inline `(<chips> in chips, €<X> bounty)`. Hero TEM
#      bounty (HRC rejeita se nao). Sem decimais quando inteiro. €.
#   4. Remover `*** SHOWDOWN ***` quando nao houver `<player>: shows` entre
#      SHOWDOWN e SUMMARY.
#   5. Adicionar `<player>: doesn't show hand` apos `collected ... from pot`
#      se nao existir.
#   6. Remover linhas `Dealt to <player>` sem cartas (manter so Hero).
#   7. Total pot trim: descartar trailing `| Jackpot 0 | Bingo 0 | ...`.
#   8. Remover virgulas de TODOS os amounts numericos (passada final).
#
# pt41 #HERO-BOUNTY-FROM-TS-DERIVATION: o bounty base deixou de ser hardcoded
# ($250 = Big Game $525). Vem agora de `tournament_summaries.buy_in_bounty` por
# torneio, injectado via `bounty_ctx` (ver `_inject_bounties_ps_format` +
# `build_queue_zip`). O gate de formato vive no Andar 1 (`services/hrc_queue.py`):
# só PKO/SuperKO/KO COM TS chegam ao injector; vanilla/mystery não levam token.
# ---------------------------------------------------------------------------


_HEADER_TM_RE = re.compile(r"^Poker Hand #TM(\d+):", re.MULTILINE)


def _rewrite_header_to_pokerstars(text: str) -> str:
    """Passo 1: `Poker Hand #TM<id>` -> `PokerStars Hand #<id>` (1a linha)."""
    return _HEADER_TM_RE.sub(r"PokerStars Hand #\1:", text, count=1)


_LEVEL_SPACING_RE = re.compile(r"\bLevel(\d+)\b")


def _normalize_level_spacing(text: str) -> str:
    """Passo 2: `Level14` -> `Level 14`."""
    return _LEVEL_SPACING_RE.sub(r"Level \1", text)


# Regex para Seat lines pos-_replace_hashes (nicks reais + Hero literal).
# `)` final fora dos grupos para podermos injectar antes do fecho.
_SEAT_LINE_RE = re.compile(
    r"^(Seat \d+: )(.+?)( \([\d,]+ in chips)\)", re.MULTILINE
)


def _format_bounty_amount(value: float) -> str:
    """`250.0` -> `'250'`; `112.5` -> `'112.50'`. Sem decimais quando inteiro."""
    if float(value).is_integer():
        return str(int(value))
    return f"{value:.2f}"


def _vision_bounties_by_name(players_list: list) -> dict:
    """`{nick_real: bounty_value_usd}` para os seats que a Vision leu (>0).
    Vazio para GG anonimizado sem SS match."""
    out: dict = {}
    for p in (players_list or []):
        name = (p.get("name") or "").strip()
        bv = p.get("bounty_value_usd")
        if name and isinstance(bv, (int, float)) and bv > 0:
            out[name] = float(bv)
    return out


def compute_hero_bounty(
    players_list: list, anon_map: dict, starting_bounty: float
) -> tuple[float, str]:
    """pt41 — bounty do Hero + fonte. Hero = max(Vision acumulado, base do TS).

    `starting_bounty` = `tournament_summaries.buy_in_bounty` (base por torneio).
    O valor do Vision (post-KO accumulator) ganha quando é maior que a base.
    Devolve `(valor, fonte)` com fonte ∈ {'vision','ts'}. FONTE ÚNICA partilhada
    por `_inject_bounties_ps_format` e pelo audit do manifest em `build_queue_zip`.
    """
    hero_real = (anon_map or {}).get("Hero")
    vision = _vision_bounties_by_name(players_list).get(hero_real, 0.0) if hero_real else 0.0
    if vision > starting_bounty:
        return vision, "vision"
    return float(starting_bounty), "ts"


def compute_hero_bounty_from_hh(
    players_list: list, anon_map: dict, hh_bounties_by_nick: dict,
) -> tuple[float, str]:
    """pt42c — Hero bounty para Winamax. Vision tem prioridade (regra pt41
    mantida); fallback à HH (que tem o pós-KO accumulator real do nick).

    `hh_bounties_by_nick` = output de `_extract_winamax_seat_bounties`.
    `anon_map.get("Hero")` resolve o nick real do Hero na HH (em WN não há
    anonimização — o Hero aparece com o nick real, ex.: `thinvalium`).

    Devolve `(valor, fonte)` com fonte ∈ {'vision','hh'}. Distinto do GG
    pt41 (`compute_hero_bounty`) que devolve {'vision','ts'}.

    Edge cases:
      - `anon_map` vazio / sem "Hero" → vision=0, hh_value=0 → devolve (0.0, "hh").
      - Vision = 0 ou ausente → devolve (hh_value, "hh"). Caso típico em WN
        (Vision do replayer Discord é GG-only).
    """
    hero_real = (anon_map or {}).get("Hero")
    if not hero_real:
        return 0.0, "hh"
    hh_value = float(hh_bounties_by_nick.get(hero_real, 0.0))
    vision = (
        _vision_bounties_by_name(players_list).get(hero_real, 0.0)
        if hero_real else 0.0
    )
    if vision > hh_value:
        return float(vision), "vision"
    return hh_value, "hh"


def _inject_bounties_ps_format(
    text: str, players_list: list, anon_map: dict, *, starting_bounty: float
) -> str:
    """Passo 3: injecta `, €<X> bounty)` em cada Seat line do HH.

    pt41 #HERO-BOUNTY-FROM-TS-DERIVATION: o bounty base vem do TS
    (`starting_bounty` = tournament_summaries.buy_in_bounty), não de um hardcode.

    - Hero: `max(Vision acumulado, starting_bounty)` (via compute_hero_bounty).
    - Vilões: bounty real do Vision por nick (mãos GG com SS match); senão
      `starting_bounty` (base do torneio — todos iguais, aproximação aceite
      para GG anonimizado, onde a Vision não lê os hashes).
    - Currency `€` literal (validado pelo Rui: HRC aceita € e rejeita $).

    O caller (`convert_gg_hh_to_pokerstars_compatible`) só chama esta função
    para formatos bounty-gated (PKO/SuperKO/KO) com `starting_bounty` não-None.
    Vanilla/mystery não passam por aqui (sem token).
    """
    if not text:
        return text

    bounty_by_name = _vision_bounties_by_name(players_list)
    hero_value, _src = compute_hero_bounty(players_list, anon_map, starting_bounty)

    def _repl(m: re.Match) -> str:
        prefix, nick, mid = m.group(1), m.group(2), m.group(3)
        if nick == "Hero":
            value = hero_value
        else:
            value = bounty_by_name.get(nick, float(starting_bounty))
        formatted = _format_bounty_amount(value)
        return f"{prefix}{nick}{mid}, €{formatted} bounty)"

    return _SEAT_LINE_RE.sub(_repl, text)


# pt42c #WN-BOUNTY-NULL-IN-HRC-PIPELINE — extracção de bounty Winamax
# directamente da HH crua. WN não tem pipeline TS (parser GG-only desde
# pt19); por isso a base de bounty vem do próprio HH, onde cada Seat
# tem `(<chips>, <X>€ bounty)` literal (formato WN).
#
# Captura nick + chips + bounty. Currency `€` literal; vírgula obrigatória
# como separador entre chips e bounty. Não confundir com vírgula de
# milhares — WN escreve `75308` (sem vírgula) e PS escreve `75,308`.

_WN_SEAT_BOUNTY_RE = re.compile(
    r"^(?P<prefix>Seat\s+\d+:\s+)(?P<nick>.+?)\s+"
    r"\((?P<chips>[\d,]+),\s+(?P<bounty>[\d.,]+)€\s+bounty\)\s*$",
    re.MULTILINE,
)


def _extract_winamax_seat_bounties(hh_text: str) -> dict:
    """Mapa `{nick: bounty_eur_float}` parseado dos Seat lines Winamax.

    Cada Seat WN PKO tem o formato `Seat N: nick (chips, X€ bounty)` com
    `X` em € (pode ter decimal). Devolve dict vazio se nenhum Seat tem
    token bounty (formato non-bounty ou HH malformada — defensivo).
    """
    if not hh_text:
        return {}
    out: dict = {}
    for m in _WN_SEAT_BOUNTY_RE.finditer(hh_text):
        nick = m.group("nick").strip()
        raw_bounty = m.group("bounty").replace(",", ".")
        try:
            bounty = float(raw_bounty)
        except ValueError:
            continue
        if nick:
            out[nick] = bounty
    return out


def _patch_winamax_payouts_bountytype(
    blob: dict, *,
    progressive_factor: float = 0.5,
    tournament_number: Optional[str] = None,
) -> dict:
    """Sobrescreve `structures[i].bountyType` e `progressiveFactor` em cada
    structure do `payouts_json` para WN PKO. Em pt42d, também aplica
    `_format_winamax_structure_name` ao `structures[i].name` para o padrão
    HRC-aceite "<Name>  #<tn>" (quando `tournament_number` é passado).

    Causa raiz: o lobby vision (apply_ratio_lookup em services/lobby_vision.py)
    só reconhece nomes branded GG/PS ("Bounty Hunters", "[bounty]", etc.).
    Nomes WN (GRAVITY, ZENITH, EXPLORER, ...) caem no default ("None", 0.0).
    Adicionalmente (pt42d): o HRC guarda a structure importada na sua
    biblioteca persistente (`custom.json`) com o `name` como chave; sem
    sufixo `#<tn>`, structures de torneios distintos com mesmo nome
    colidem e a biblioteca fica corrupta. Patch aqui sobrescreve no zip
    (não na BD — audit trail preservado).

    Devolve novo dict (deep-copy via json round-trip; não muta o input).
    Se `blob` não é dict ou não tem `structures`, devolve cópia sem
    alterações.

    Args:
      blob: payout_blob como vem da BD (lobby vision).
      progressive_factor: 0.5 para PKO 50% (default — Rui confirma WN PKO
        50% universal).
      tournament_number: se passado, aplica `_format_winamax_structure_name`
        ao `structures[i].name`. None → name original preservado (pt42c
        compat).
    """
    if not isinstance(blob, dict):
        return blob
    patched = json.loads(json.dumps(blob))  # deep-copy via serialização
    structs = patched.get("structures")
    if not isinstance(structs, list):
        return patched
    for s in structs:
        if not isinstance(s, dict):
            continue
        s["bountyType"] = "PKO"
        s["progressiveFactor"] = float(progressive_factor)
        # pt42d — name "<Name>  #<tn>" (HRC-aceite). Sem `tn` → preserva original.
        if tournament_number:
            s["name"] = _format_winamax_structure_name(
                s.get("name"), tournament_number,
            )
    return patched


def _format_winamax_structure_name(
    name: Optional[str], tournament_number: Optional[str],
) -> Optional[str]:
    """pt42d — formata `structures[i].name` para o padrão HRC-aceite.

    Convenção observada empiricamente nos JSON HRC Ninja (validada pelo
    Rui em pt42d): "<TournamentName>  #<tournament_number>" — **2 espaços**
    + #ID. Ex.: "GRAVITY  #1101080235".

    Sem este formato, o HRC importa a structure mas a sua biblioteca
    `custom.json` guarda-a com `bountyType` ausente — quando re-corrida,
    cai em ICM puro mesmo que o JSON do zip tenha `bountyType: "PKO"`.

    Defensivo:
    - `name` None → devolve None (caller decide).
    - `tournament_number` None/empty/falsy → devolve `name` original
      (sem sufixo).
    - Ambos preenchidos → `"<name>  #<tn>"`.
    """
    if name is None:
        return None
    if not tournament_number:
        return name
    return f"{name}  #{tournament_number}"


_SHOWDOWN_MARK = "*** SHOWDOWN ***"
_SUMMARY_MARK = "*** SUMMARY ***"


def _drop_showdown_if_no_show(text: str) -> str:
    """Passo 4: remove `*** SHOWDOWN ***` se nao houver `<player>: shows`
    entre SHOWDOWN e SUMMARY. Mãos fold-to (raise + folds) tem o marker
    SHOWDOWN spurio do GG raw — HRC rejeita."""
    sd_idx = text.find(_SHOWDOWN_MARK)
    if sd_idx == -1:
        return text
    sm_idx = text.find(_SUMMARY_MARK, sd_idx)
    middle = text[sd_idx:sm_idx] if sm_idx != -1 else text[sd_idx:]
    if ": shows" in middle:
        return text
    # Remover a linha SHOWDOWN inteira (com trailing \n)
    line_end = text.find("\n", sd_idx)
    if line_end == -1:
        return text[:sd_idx].rstrip()
    return text[:sd_idx] + text[line_end + 1:]


_COLLECTED_FROM_POT_RE = re.compile(r"^(.+?)\s+collected\s+\S+\s+from pot")


def _add_doesnt_show_after_collected(text: str) -> str:
    """Passo 5: apos cada `<player> collected X from pot` (fora do SUMMARY),
    se nao existir ja `<player>: doesn't show hand`, adicionar."""
    lines = text.split("\n")
    out: list = []
    in_summary = False
    for i, line in enumerate(lines):
        if line.startswith(_SUMMARY_MARK):
            in_summary = True
        out.append(line)
        if in_summary:
            continue
        m = _COLLECTED_FROM_POT_RE.match(line)
        if not m:
            continue
        player = m.group(1).strip()
        next_line = lines[i + 1] if i + 1 < len(lines) else ""
        marker = f"{player}: doesn't show hand"
        if marker not in next_line:
            out.append(marker)
    return "\n".join(out)


def _drop_dealt_to_non_hero(text: str) -> str:
    """Passo 6: remove linhas `Dealt to <player>` sem cartas (sem `[`).
    Manter `Dealt to Hero [...]`. GG raw mete `Dealt to <hash>` para todos
    os seats; HRC so quer o Hero."""
    out: list = []
    for line in text.split("\n"):
        if line.startswith("Dealt to ") and "[" not in line:
            continue
        out.append(line)
    return "\n".join(out)


_TOTAL_POT_TRIM_RE = re.compile(
    r"(Total pot \S+ \| Rake \S+) \| Jackpot \S+ \| Bingo \S+ \| Fortune \S+ \| Tax \S+"
)


def _trim_total_pot_trailing_fields(text: str) -> str:
    """Passo 7: `Total pot X | Rake 0 | Jackpot 0 | Bingo 0 | Fortune 0 | Tax 0`
    -> `Total pot X | Rake 0`. GG raw mete metricas extra que HRC nao quer."""
    return _TOTAL_POT_TRIM_RE.sub(r"\1", text)


_THOUSANDS_COMMA_RE = re.compile(r"\d{1,3}(?:,\d{3})+")


def _strip_commas_from_amounts(text: str) -> str:
    """Passo 8 (passada final): `40,492` -> `40492`. Aplica a chips em
    Seats, raises, blinds, collected, etc."""
    return _THOUSANDS_COMMA_RE.sub(lambda m: m.group(0).replace(",", ""), text)


def convert_gg_hh_to_pokerstars_compatible(
    hand: dict, *, bounty_ctx: Optional[dict] = None
) -> str:
    """Converte raw HH para formato compatível com HRC.

    Sites suportados:

    - **GGPoker**: pipeline pt29 completo (8 transformações: conversão
      de header, hashes, bounty via TS, etc.).
    - **PokerStars, Winamax, WPN**: passthrough total — HH crua entregue
      ao HRC sem reescrita. HRC lê os formatos nativos directamente.
      Pt42c havia introduzido um branch WN para reescrita Seat lines mas
      foi revertido em pt42d: HRC aceita formato WN nativo; só o
      `payouts.json` precisa de patch (em `build_queue_zip`).

    Hands com `raw` vazio devolvem string vazia (caller deve filtrar).

    Pipeline pt29 Fase 2 — só para GGPoker:
      _format_level_line   -> drop ante + virgulas no Level header
      _replace_hashes      -> substitui hashes por nicks reais
      passo 1              -> Poker Hand #TM<id>  ->  PokerStars Hand #<id>
      passo 2              -> Level14             ->  Level 14
      passo 3              -> injecta `, €<X> bounty)` em cada Seat
      passo 4              -> drop SHOWDOWN spurio
      passo 5              -> add "doesn't show hand" pos-collected
      passo 6              -> drop "Dealt to" non-Hero
      passo 7              -> trim Total pot trailing
      passo 8 (final)      -> remove virgulas de amounts
    """
    raw = (hand.get("raw") or "").strip()
    if not raw:
        return ""

    # pt42d — branch WN PKO removido. HRC lê HH WN nativa (com `(<X>€ bounty)`
    # nos Seats) sem necessitar de conversão para PS-compat. O bounty pt42c
    # vive agora apenas no `payouts.json` (via `_patch_winamax_payouts_bountytype`
    # em `build_queue_zip`) com formato HRC-aceite.
    if hand.get("site") != "GGPoker":
        # PS, Winamax e WPN → passthrough total.
        return hand.get("raw") or ""

    pn = _coerce_player_names(hand.get("player_names"))
    anon_map = pn.get("anon_map") or {}
    players_list = pn.get("players_list") or []

    # pt41: bounty só para formatos bounty-gated (PKO/SuperKO/KO) com base do TS.
    # Vanilla/Mystery/sem-base → sem token (Opção A). starting_bounty vem do
    # bounty_ctx (tournament_summaries.buy_in_bounty), threaded por build_queue_zip.
    fmt = (hand.get("tournament_format") or "").lower()
    starting_bounty = (bounty_ctx or {}).get("starting_bounty")

    out = _format_level_line(raw)
    out = _replace_hashes(out, anon_map)
    out = _rewrite_header_to_pokerstars(out)                       # 1
    out = _normalize_level_spacing(out)                            # 2
    if fmt in TS_GATED_FORMATS and starting_bounty is not None:    # 3
        out = _inject_bounties_ps_format(
            out, players_list, anon_map, starting_bounty=float(starting_bounty),
        )
    out = _drop_showdown_if_no_show(out)                           # 4
    out = _add_doesnt_show_after_collected(out)                    # 5
    out = _drop_dealt_to_non_hero(out)                             # 6
    out = _trim_total_pot_trailing_fields(out)                     # 7
    out = _strip_commas_from_amounts(out)                          # 8 (final)
    return out


def _derive_equity_model(hm3_tags, discord_tags) -> str:
    """pt23 fix Bug A. Decide equity model hint based on tag membership.

    Devolve 'malmuth_harville_icm' se houver tag FT (HM3 ou Discord, em
    qualquer case-variant); caso contrário 'multi_table_icm' (default p/
    mid-MTT). Comparação cross-source via `normalize_tag_key` (#B17).
    """
    for t in list(hm3_tags or []) + list(discord_tags or []):
        if normalize_tag_key(t) in _EQUITY_FT_NORM_KEYS:
            return "malmuth_harville_icm"
    return "multi_table_icm"


# Mapping equity_model → stage para o watcher (pt25e Bloco 2 piece 2).
# Stage FT bypassa a página MTT Stacks no wizard HRC; MTT entra nela.
_STAGE_BY_EQUITY_MODEL = {
    "malmuth_harville_icm": "FT",
    "multi_table_icm": "MTT",
}

# Default CI Target. pt27: alinhado em 10.0 para ambas as runs.
# Antes era 5.0 (legacy setup_hand) mas o watcher já hardcode passa 10.0
# para `start_calculation_selected_subtree` na 2ª run — Rui confirmou que
# quer 10.0 em ambas (#CI-DEFAULT-MISMATCH fechado pt27).
_DEFAULT_CI_TARGET = 10.0


def _derive_stage_from_equity_model(equity_model) -> str:
    """`malmuth_harville_icm` → `FT`; `multi_table_icm` → `MTT`; outros → `FT`
    (defensive default, mesmo que `setup_hand` legacy)."""
    return _STAGE_BY_EQUITY_MODEL.get(equity_model, "FT")


def _build_hand_meta(
    hand: dict,
    hh_text: str,
    equity_model,
    payout_blob,
    target_node_offset,
    *,
    max_players: Optional[int] = None,
    script_path: Optional[str] = None,
    aggressor_real_action: Optional[dict] = None,
) -> dict:
    """Compõe o `meta.json` per-hand.

    Schema:
      - `stage`           : "FT" ou "MTT" (deriva de equity_model).
      - `players_left`    : int | None (lookup em lobby_processing_log).
      - `total_chips`     : int | None (legacy — input manual no UI HRC).
      - `ci`              : float (default 10.0, CI Target aplicado a
                            ambas as runs — alinhado pt27 com o watcher
                            que já hardcode 10.0 na 2ª run).
      - `target_node_offset`: int | None (pt25e Bloco 2 piece 2 — setas
                              para baixo até pousar na linha do raiser
                              antes da 2ª run em Selected Subtree).

    Hints pt42d (movidos de `payouts.json` em pt42d porque HRC rejeita
    campos extra no payouts.json; ficam aqui no meta.json):
      - `equity_model`    : "malmuth_harville_icm" | "multi_table_icm".
                            Watcher (`set_equity_model`) faz typeahead
                            no dropdown HRC.
      - `max_players`     : int | None (override do `players_in_hand`
                            no `set_hand_mode_players`).
      - `script_path`     : str | None ("script.js" no zip; adapter
                            reescreve para path absoluto pós-unzip).
      - `aggressor_real_action`: dict | None. Gate da 2ª run: se
                            `is not None`, watcher dispara
                            `navigate_to_target_node` +
                            `start_calculation_selected_subtree`.

    Defensivo: campos individuais que falham na derivação caem para None
    (graceful — `setup_hand` legacy tem fallbacks para cada um).
    """
    return {
        "stage": _derive_stage_from_equity_model(equity_model),
        "players_left": _resolve_players_left(hand, payout_blob),
        "total_chips": None,
        "ci": _DEFAULT_CI_TARGET,
        "target_node_offset": target_node_offset,
        "equity_model": equity_model,
        "max_players": max_players,
        "script_path": script_path,
        "aggressor_real_action": aggressor_real_action,
    }


def _build_watcher_hints(hand: dict, hh_text: str) -> dict:
    """pt23 fix A/B/C — 3 hints que o watcher patched lê em setup_hand.

    Defensivo: cada hint é wrapped em try/except. Falha individual → omite
    a key (watcher cai no default seguro). Falha total → dict vazio.
    """
    hints: dict = {}
    try:
        hints["equity_model"] = _derive_equity_model(
            hand.get("hm3_tags"), hand.get("discord_tags"),
        )
    except Exception:
        logger.exception(
            "derive equity_model falhou hand_id=%s", hand.get("hand_id"),
        )
    try:
        hints["max_players"] = derive_max_players(hh_text)
    except Exception:
        logger.exception(
            "derive max_players falhou hand_id=%s", hand.get("hand_id"),
        )
    # pt24+: derivar script_path por tag/profundidade. Por agora None.
    hints["script_path"] = None
    return hints


def _resolve_players_left(hand: dict, payout_blob) -> Optional[int]:
    """pt25-revisado — resolve `players_left` para o trigger da prune.

    Ordem de prioridade:
    1. `hand["players_left"]` quando o router/SELECT vier a popular.
       Hoje não é (column inexistente em `hands`), mas mantemos para tests
       in-memory e futura wiring caso seja necessário.
    2. Lookup em `lobby_processing_log`: pega o `players_left` mais recente
       associado ao `tournament_number` da mão, restringido a `result='success'`
       e `players_left IS NOT NULL`. Valor extraído pelo Vision pt25 sobre
       SSs de lobby mid-tournament postadas em `#lobbys`.

    Devolve None quando nenhuma fonte fornece valor — caller deve tratar
    como "informação ausente" (graceful).

    NOTA: `payout_blob` mantém-se na assinatura por compatibilidade com o
    caller; não é mais consultado (pt25 diagnóstico confirmou que
    `tournament_payouts.payouts_json.CompletedTournament.PlayersLeft` nunca
    existe em prod).
    """
    if isinstance(hand, dict) and isinstance(hand.get("players_left"), int):
        return hand["players_left"]

    # pt38 — prioridade 2: SS de mesa alinhada a ESTA mão (granular).
    # hands.context_table_ss_id → table_ss_processing_log.players_left.
    # Preferida ao lookup por tournament_number (lobby) por ser per-mão.
    ctx_id = hand.get("context_table_ss_id") if isinstance(hand, dict) else None
    if isinstance(ctx_id, int):
        try:
            from app.db import query
            rows = query(
                "SELECT players_left FROM table_ss_processing_log "
                "WHERE id = %s AND players_left IS NOT NULL",
                (ctx_id,),
            )
            if rows:
                val = rows[0].get("players_left") if isinstance(rows[0], dict) else None
                if isinstance(val, int):
                    return val
        except Exception:
            logger.exception(
                "_resolve_players_left table_ss lookup failed ctx_id=%s", ctx_id,
            )

    tn = hand.get("tournament_number") if isinstance(hand, dict) else None
    if not tn:
        return None

    try:
        # Lazy import: evita acoplamento ao app.db em tests que mockam query.
        from app.db import query
    except Exception:
        return None

    try:
        rows = query(
            """
            SELECT players_left
              FROM lobby_processing_log
             WHERE tournament_number = %s
               AND result = 'success'
               AND players_left IS NOT NULL
             ORDER BY posted_at DESC NULLS LAST
             LIMIT 1
            """,
            (str(tn),),
        )
    except Exception:
        logger.exception(
            "_resolve_players_left lookup failed tn=%s hand_id=%s",
            tn, hand.get("hand_id") if isinstance(hand, dict) else None,
        )
        return None

    if not rows:
        return None
    val = rows[0].get("players_left") if isinstance(rows[0], dict) else None
    return val if isinstance(val, int) else None


def _build_hrc_script_for_hand(hh_text: str, level_sb: int, level_bb: int):
    """Pipeline novo (Maio 2026): gera `.js` per-hand com SIZES_* substituídos
    pela acção real da HH.

    Substitui o antigo `_try_build_prune_script` — o mecanismo de prune via
    JS (REAL_AGGRESSOR_POS + DOWNSTREAM_POSITIONS) foi removido; o equivalente
    migra para o Bloco 2 do watcher (Selected Subtree + Prune Action manual).

    Devolve `(js_string|None, overrides_dict, effective_stack_bb, error)`:
      - `js_string`: conteúdo final do .js (sempre o template completo;
        `None` apenas se template I/O falhou).
      - `overrides_dict`: `{var_name: [sizings]}` aplicados — vazio quando
        a mão não teve raises preflop (walk-to-BB / limp pot).
      - `effective_stack_bb`: min(stacks_iniciais)/level_bb. None se parse
        falhou.
      - `error`: string descrevendo template I/O failure, ou None.

    A mão sem raises preflop devolve o template intacto — caller decide se
    o escreve no zip (preferimos escrever sempre para consistência).
    """
    from app.services.hrc_script_gen import generate_hrc_script_for_hand
    seats = derive_seats_in_preflop_order(hh_text)
    return generate_hrc_script_for_hand(hh_text, level_sb, level_bb, seats)


def classify_aggressor_source(real_action: Optional[dict], positions: list) -> str:
    """pt36 #HRC-RUN-2-ALWAYS-DISPATCH — classifica a fonte do aggressor para
    decidir o fallback da 2ª run. FONTE ÚNICA usada por `build_queue_zip` e pelo
    selector do painel HRC (`services/hrc_queue.py`) — não duplicar (anti-drift).

    Args:
      real_action: saída de `derive_aggressor_real_action` (dict ou None).
      positions: `strategy_table_positions(seats_at_table)`.

    Devolve:
      "fallback_root"              — sem raise/bet preflop (limp/walk) ou sem blinds.
      "fallback_unusable_position" — houve raise mas position None/"BB"/fora da
                                     Strategy Table.
      "real"                       — raise com position usável.
    """
    if real_action is None:
        return "fallback_root"
    if not (isinstance(real_action, dict) and real_action.get("position") in positions):
        return "fallback_unusable_position"
    return "real"


def build_queue_zip(
    hands: list[dict],
    payouts_by_key: dict[tuple[str, str], Any],
    *,
    include_no_payout: bool = False,
    filters_meta: Optional[dict] = None,
    bounty_by_key: Optional[dict] = None,
) -> bytes:
    """Constroi um zip com pasta por mao + manifest.json no root.

    Args:
      hands: lista de dicts com keys: id, hand_id, site, tournament_number,
             tournament_format, raw, player_names, played_at.
      payouts_by_key: lookup {(site, tournament_number): payouts_json_blob}.
      include_no_payout: se True, mao sem payout entra no zip sem payouts.json.
                         Se False, mao sem payout e excluida (vai para
                         manifest.missing_payouts).
      filters_meta: dict de filters echoado no manifest (observabilidade).
      bounty_by_key: lookup {(site, tn): {"starting_bounty": float|None, ...}}
                     (pt41, espelho de payouts_by_key). Threaded para o conversor
                     via bounty_ctx. GG bounty-format sem base do TS é skipado
                     defensivamente (reason='pko_without_ts_bounty').

    Estrutura:
      <hand_id_1>/hh.txt
      <hand_id_1>/payouts.json    # se houver payouts ou include_no_payout=True
      <hand_id_2>/hh.txt
      ...
      manifest.json
    """
    hands_included = []
    missing_payouts = []
    skipped = []

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for h in hands:
            hand_id = h.get("hand_id")
            site = h.get("site")
            tnum = h.get("tournament_number")

            if not hand_id:
                skipped.append({"hand_id": None, "reason": "no_hand_id"})
                continue

            key = (site, tnum) if site and tnum else None

            # pt41 #HERO-BOUNTY-FROM-TS-DERIVATION: resolve o bounty base do TS
            # antes da conversão. Defensiva — GG bounty-gated (PKO/SuperKO/KO)
            # sem base do TS não devia chegar aqui (o gate do Andar 1 filtra),
            # mas se chegar (per-mão/chamada externa) skipa em vez de inventar.
            bctx = (bounty_by_key or {}).get(key) if key else None
            fmt = (h.get("tournament_format") or "").lower()
            starting_bounty = (bctx or {}).get("starting_bounty")
            if site == "GGPoker" and fmt in TS_GATED_FORMATS and starting_bounty is None:
                skipped.append({"hand_id": hand_id, "reason": "pko_without_ts_bounty"})
                continue

            hh_text = convert_gg_hh_to_pokerstars_compatible(h, bounty_ctx=bctx)
            if not hh_text:
                skipped.append({"hand_id": hand_id, "reason": "no_raw_hh"})
                continue

            payout_blob = payouts_by_key.get(key) if key else None

            if payout_blob is None and not include_no_payout:
                missing_payouts.append({
                    "hand_id": hand_id,
                    "tournament_number": tnum,
                    "site": site,
                    "reason": "no_row_in_tournament_payouts",
                })
                continue

            # pt36 #HRC-RUN-2-ALWAYS-DISPATCH: seats derivados cedo para (a)
            # decidir o fallback do aggressor e (b) skip de HH cuja mesa não
            # parseia (sem button / <2 seats = malformada → não vai ao robot).
            # Import lazy: hrc_node_offset importa de queue_export → evita ciclo.
            from app.services.hrc_node_offset import (
                compute_target_node_offset,
                derive_aggressor_stack_bb,
                strategy_table_positions,
            )
            seats_at_table = len(derive_seats_in_preflop_order(hh_text))
            positions = strategy_table_positions(seats_at_table)
            if not positions:
                skipped.append({"hand_id": hand_id, "reason": "no_seats_at_table"})
                continue

            zf.writestr(f"{hand_id}/hh.txt", hh_text)

            # pt23: merge hints (equity_model, max_players, script_path) com
            # o payout_blob. Hints aplicam-se sempre — mesmo sem blob, escreve
            # payouts.json só com hints para o watcher os ler.
            hints = _build_watcher_hints(h, hh_text)

            # Maio 2026: gera .js per-hand com SIZES_* substituídos pela
            # acção real da HH (open/3-bet/squeeze/4-bet/5-bet). O template
            # canónico é único; o gerador (services/hrc_script_gen.py)
            # decide quais variáveis substituir.
            blinds = _extract_blinds_from_header(hh_text)
            if blinds is not None:
                _sb, _bb = blinds
            else:
                _sb, _bb = None, None

            script_js = None
            script_overrides: dict = {}
            effective_stack_bb = None
            script_error = None
            if _bb is not None:
                try:
                    (script_js, script_overrides,
                     effective_stack_bb, script_error) = _build_hrc_script_for_hand(
                        hh_text, _sb, _bb,
                    )
                except Exception as _e:
                    logger.exception("hrc_script_gen falhou hand_id=%s", hand_id)
                    script_js = None
                    script_overrides = {}
                    script_error = f"unhandled: {type(_e).__name__}: {_e}"

            if script_js is not None:
                zf.writestr(f"{hand_id}/script.js", script_js)
                hints["script_path"] = "script.js"

            # #META-AGGRESSOR-REAL-ACTION + pt36 #HRC-RUN-2-ALWAYS-DISPATCH:
            # garantir 2ª run sempre. derive devolve a acção real; se for None
            # (limp/walk, sem blinds) ou se a position for inutilizável
            # (None / "BB" / fora da Strategy Table), aplica sentinela na raiz.
            real = derive_aggressor_real_action(hh_text, _sb, _bb) if _bb is not None else None
            aggressor_source = classify_aggressor_source(real, positions)

            if aggressor_source == "real":
                aggressor_real_action = real  # estrutura legacy intacta, sem "source"
            else:
                aggressor_real_action = {
                    "type": "fallback_root",
                    "position": positions[0],   # UTG (>=4-handed), BU (3), BU/SB (HU)
                    "size_bb": None,
                    "source": aggressor_source,  # "fallback_root" | "fallback_unusable_position"
                }
            hints["aggressor_real_action"] = aggressor_real_action

            # pt25e Bloco 2 piece 2 + pt36: target_node_offset para o watcher
            # premer seta-para-baixo até pousar na linha do raiser real antes
            # da 2ª run em Selected Subtree. No caso real, offset = linha do
            # raiser; no fallback, offset = 0 (raiz da Strategy Table).
            # aggressor_real_action é sempre dict agora (gate da 2ª run sempre
            # passa); raiser_stack_bb só faz sentido no caso real.
            # pt27: `seats_at_table` (nº real de jogadores sentados, não a
            # redução `max_players` ICM) — derivado na Zona 1 acima.
            #
            # Migração vocab posições: o botão em HU passou a ter label "SB"
            # (positions[0] de _POSITION_LABELS_BY_N[2]=[SB,BB]). Para um
            # fallback, compute_target_node_offset cairia no special-case SB
            # de offset_within_bucket (Complete=0 / raise=1) e devolveria 1 em
            # vez da raiz. O fallback NÃO tem agressão real → forçamos offset 0
            # directamente (invariante "fallback = raiz"), só computando para
            # o caso "real".
            target_node_offset = 0 if aggressor_source != "real" else None
            if aggressor_source == "real":
                try:
                    raiser_stack_bb = (
                        derive_aggressor_stack_bb(hh_text, _bb)
                        if _bb is not None else None
                    )
                    target_node_offset = compute_target_node_offset(
                        aggressor_real_action,
                        seats_at_table,
                        script_overrides,
                        raiser_stack_bb,
                    )
                except Exception:
                    logger.exception(
                        "compute_target_node_offset falhou hand_id=%s", hand_id,
                    )
                    target_node_offset = None

            # pt42c #WN-BOUNTY-NULL-IN-HRC-PIPELINE — sobrescrever
            # `bountyType` + `progressiveFactor` (pt42c) + `name` com sufixo
            # `#<tn>` (pt42d) no payouts.json do zip para WN PKO. Patch é
            # aplicado SÓ NO ZIP (não na BD — audit trail preservado).
            payout_blob_for_zip = payout_blob
            if (site == "Winamax"
                    and fmt in WINAMAX_BOUNTY_FORMATS
                    and payout_blob is not None):
                payout_blob_for_zip = _patch_winamax_payouts_bountytype(
                    payout_blob,
                    progressive_factor=0.5,
                    tournament_number=tnum,
                )

            # pt42d #WN-BOUNTY-NULL-IN-HRC-PIPELINE v2 — payouts.json no zip
            # contém APENAS `{name, folders, structures}` (sem merge com
            # hints top-level). HRC rejeita campos extra (custom.json fica
            # com structure sem bountyType → ICM puro). Hints mudam-se
            # para meta.json (pt42d T5).
            if payout_blob_for_zip is not None:
                zf.writestr(
                    f"{hand_id}/payouts.json",
                    json.dumps(payout_blob_for_zip, indent=2, ensure_ascii=False),
                )
            else:
                # Sem payout_blob — caller (build_queue_zip) já filtra mãos
                # sem payout via `missing_payouts` antes de chegar aqui;
                # esta branch é defensiva.
                zf.writestr(
                    f"{hand_id}/payouts.json",
                    json.dumps({"name": "/", "folders": [], "structures": []},
                               indent=2, ensure_ascii=False),
                )

            # pt25e Bloco 2 piece 2: meta.json passa a ser produzido pelo
            # backend (em vez de input manual do Rui). 4 legacy fields
            # preservados + target_node_offset novo.
            hand_meta = _build_hand_meta(
                h, hh_text,
                equity_model=hints.get("equity_model"),
                payout_blob=payout_blob,
                target_node_offset=target_node_offset,
                # pt42d — hints movidos de payouts.json para meta.json
                # (HRC rejeitava campos extra → ICM puro).
                max_players=hints.get("max_players"),
                script_path=hints.get("script_path"),
                aggressor_real_action=aggressor_real_action,
            )
            zf.writestr(
                f"{hand_id}/meta.json",
                json.dumps(hand_meta, indent=2, ensure_ascii=False),
            )

            # pt41 audit do bounty (paralelo ao aggressor_source): só faz sentido
            # quando houve injecção (GG bounty-gated com base do TS, ou pt42c WN
            # PKO com bounty literal na HH).
            hero_bounty = None
            hero_bounty_source = None
            if site == "GGPoker" and fmt in TS_GATED_FORMATS and starting_bounty is not None:
                _pn = _coerce_player_names(h.get("player_names"))
                hero_bounty, hero_bounty_source = compute_hero_bounty(
                    _pn.get("players_list") or [], _pn.get("anon_map") or {},
                    float(starting_bounty),
                )
            elif site == "Winamax" and fmt in WINAMAX_BOUNTY_FORMATS:
                # pt42c — audit WN: extrair bounties da HH crua (não do
                # hh_text convertido — esse já está em PS-compat e não
                # matcha o regex WN).
                _pn = _coerce_player_names(h.get("player_names"))
                wn_hh_bounties = _extract_winamax_seat_bounties(h.get("raw") or "")
                if wn_hh_bounties:
                    hero_bounty, hero_bounty_source = compute_hero_bounty_from_hh(
                        _pn.get("players_list") or [],
                        _pn.get("anon_map") or {},
                        wn_hh_bounties,
                    )

            hands_included.append({
                "hand_id": hand_id,
                "tournament_number": tnum,
                "site": site,
                "has_payouts": payout_blob is not None,
                "bounty_format": fmt or None,
                "starting_bounty": starting_bounty,
                "hero_bounty": hero_bounty,
                "hero_bounty_source": hero_bounty_source,
                "has_script": script_js is not None,
                "script_overrides": script_overrides,
                "script_generation_error": script_error,
                "effective_stack_bb": effective_stack_bb,
                "aggressor_position": derive_real_aggressor_position(hh_text),
                "aggressor_real_action": aggressor_real_action,
                "target_node_offset": target_node_offset,
                "aggressor_source": aggressor_source,
                "hand_meta": hand_meta,
                "converted_format": (
                    "pokerstars_compat" if (
                        site == "GGPoker"
                        or (site == "Winamax" and fmt in WINAMAX_BOUNTY_FORMATS)
                    ) else "passthrough"
                ),
            })

        manifest = {
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "filters": filters_meta or {},
            "total_hands_queried": len(hands),
            "total_in_zip": len(hands_included),
            "hands_included": hands_included,
            "missing_payouts": missing_payouts,
            "skipped": skipped,
        }
        zf.writestr(
            "manifest.json",
            json.dumps(manifest, indent=2, ensure_ascii=False),
        )

    return buf.getvalue()
