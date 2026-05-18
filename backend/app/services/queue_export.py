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
      (pt24: REVISTO — `_inject_bounties_into_seat_lines` injecta bounty $
      em cada Seat line quando `players_list[].bounty_value_usd` existe.
      Fecha `#HRC-GG-KOS-EXTRACTION` para mãos GG com Vision pt24+ ingestion.)
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


# pt24: regex para Seat lines no HH GG. Captura prefix + nick (lazy, tolera
# espaços em nomes pós-_replace_hashes, ex: "Vlad Martyn.." ou "R Aziz Alves")
# + " (CHIPS in chips" — o `)` final fica fora dos grupos para podermos
# injectar conteúdo antes de o fechar.
_SEAT_RE = re.compile(r"^(Seat \d+: )(.+?)( \([\d,]+ in chips)\)", re.MULTILINE)


# pt25d: helpers para seat ↔ HRC player index ↔ position label.
# HRC scripting convention oficial (docs): índices 0..N-1 onde
# 0 = first-to-act preflop (UTG em N>=3; BU/SB em HU), N-2 = SB, N-1 = BB.
# Compatível com `ctx.getPlayerIndex*()` e `ctx.getActivePlayer()` do HRC
# engine. Preflop turn order = [0, 1, ..., N-1] sequencial (BB sempre último).
_SEAT_ALL_RE = re.compile(r"^Seat (\d+): (.+?) \(\d", re.MULTILINE)
_BUTTON_RE = re.compile(r"Seat #(\d+) is the button")
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


# pt25d: labels canónicos por número de jogadores sentados na mão. HRC docs
# convention: idx 0 = first-to-act preflop (UTG em N>=3, BU/SB em HU), idx
# N-2 = SB, idx N-1 = BB. Labels variam consoante o N (mesa "regular" de
# N-max). Para tables com seats vazios (e.g. 6-max com 5 sentados após
# eliminação), tratamos como N-handed (CO desaparece em 5-handed).
_POSITION_LABELS_BY_N: dict = {
    2: ["BU/SB", "BB"],
    3: ["BU", "SB", "BB"],
    4: ["UTG", "BU", "SB", "BB"],
    5: ["UTG", "HJ", "BU", "SB", "BB"],
    6: ["UTG", "HJ", "CO", "BU", "SB", "BB"],
    7: ["UTG", "EP", "MP", "CO", "BU", "SB", "BB"],
    8: ["UTG", "EP", "MP", "HJ", "CO", "BU", "SB", "BB"],
    9: ["UTG", "EP1", "EP2", "MP", "HJ", "CO", "BU", "SB", "BB"],
}


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

    Devolve `[]` se parsing falhar (sem button, sem seats, button fora do
    seat list). Cada entry: `{seat: int, position: str, hrc_idx: int, nick: str}`.

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
        return []

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


def _detect_currency_symbol(hh_text: str) -> str:
    """Detecta currency a partir do tournament header (1ª linha).

    GG headers tipicamente: '... Bounty Hunters Big Game $215 ...' → USD;
    PS/WN-style adaptado: '€45+€45+€10 EUR' → EUR. Default $: a maioria
    dos GG PKO em prod é USD."""
    first_line = hh_text.split("\n", 1)[0] if hh_text else ""
    return "€" if "€" in first_line else "$"


def _inject_bounties_into_seat_lines(
    hh_text: str, players_list, anon_map: dict
) -> str:
    """pt24 fix `#HRC-GG-KOS-EXTRACTION`.

    Injecta `, $X.XX bounty` em cada Seat line do HH PS-compat quando o player
    correspondente tem `bounty_value_usd > 0` em `players_list` (extraído por
    Vision pt24 da coroa dourada na SS).

    Resolução de nomes:
    - Pós-`_replace_hashes`, Seat lines têm nicks reais excepto `Hero` (que fica
      literal). Para a linha do Hero, resolvemos via `anon_map["Hero"]`.
    - Lookup em players_list é case-sensitive, name-exact match. Nomes sem
      match em bounty_by_name → linha intacta (graceful: GG players ainda
      em jogo às vezes não têm crown visível na SS, ou Vision falhou crown
      para esse seat).

    Currency: $ por defeito (GG USD); € se header contém '€'.

    No-op se `players_list` vazio ou todos os bounty_value_usd <= 0.
    """
    if not hh_text or not players_list:
        return hh_text

    bounty_by_name: dict = {}
    for p in players_list:
        name = (p.get("name") or "").strip()
        bv = p.get("bounty_value_usd")
        if name and isinstance(bv, (int, float)) and bv > 0:
            bounty_by_name[name] = float(bv)

    if not bounty_by_name:
        return hh_text

    hero_real = (anon_map or {}).get("Hero")
    currency = _detect_currency_symbol(hh_text)

    def _repl(m: re.Match) -> str:
        prefix, nick, mid = m.group(1), m.group(2), m.group(3)
        lookup = hero_real if (nick == "Hero" and hero_real) else nick
        bounty = bounty_by_name.get(lookup)
        if bounty is None:
            return m.group(0)
        return f"{prefix}{nick}{mid}, {currency}{bounty:.2f} bounty)"

    return _SEAT_RE.sub(_repl, hh_text)


def convert_gg_hh_to_pokerstars_compatible(hand: dict) -> str:
    """Converte raw HH GG para formato compativel com HRC.

    Hands non-GG (PokerStars, Winamax) passam tal e qual (pass-through) —
    Fase 2 tratara conversoes especificas se HRC reclamar de Winamax.

    Hands com `raw` vazio devolvem string vazia (caller deve filtrar).

    pt24: adicionada injecção de bounty_value_usd nas Seat lines pós-replace
    via `_inject_bounties_into_seat_lines` (fecha `#HRC-GG-KOS-EXTRACTION`)."""
    raw = (hand.get("raw") or "").strip()
    if not raw:
        return ""
    if hand.get("site") != "GGPoker":
        return hand.get("raw") or ""

    pn = _coerce_player_names(hand.get("player_names"))
    anon_map = pn.get("anon_map") or {}
    players_list = pn.get("players_list") or []

    out = _format_level_line(raw)
    out = _replace_hashes(out, anon_map)
    out = _inject_bounties_into_seat_lines(out, players_list, anon_map)
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

# Default CI Target da 1ª run (semântica legacy do `setup_hand`).
_DEFAULT_CI_TARGET_FIRST_RUN = 5.0


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
) -> dict:
    """Compõe o `meta.json` per-hand: 4 legacy fields + target_node_offset.

    Legacy schema (consumido pelo `setup_hand` do watcher antes de pt25e
    Bloco 2):
      - `stage`           : "FT" ou "MTT" (deriva de equity_model).
      - `players_left`    : int | None (lookup em lobby_processing_log).
      - `total_chips`     : int | None (legacy: input manual do Rui na
                            página MTT Stacks; auto-derivação per-hand
                            não-fidedigna → None).
      - `ci`              : float (default 5.0, CI Target da 1ª run).

    Extensão pt25e Bloco 2 piece 2:
      - `target_node_offset`: int | None — nº de seta-para-baixo presses
                              que o watcher faz na Strategy Table HRC após
                              a 1ª run, para pousar na linha do raiser
                              real antes da 2ª run em Selected Subtree.

    Defensivo: campos individuais que falham na derivação caem para None
    (graceful — `setup_hand` legacy tem fallbacks para cada um).
    """
    return {
        "stage": _derive_stage_from_equity_model(equity_model),
        "players_left": _resolve_players_left(hand, payout_blob),
        "total_chips": None,
        "ci": _DEFAULT_CI_TARGET_FIRST_RUN,
        "target_node_offset": target_node_offset,
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


def build_queue_zip(
    hands: list[dict],
    payouts_by_key: dict[tuple[str, str], Any],
    *,
    include_no_payout: bool = False,
    filters_meta: Optional[dict] = None,
) -> bytes:
    """Constroi um zip com pasta por mao + manifest.json no root.

    Args:
      hands: lista de dicts com keys: id, hand_id, site, tournament_number,
             raw, player_names, played_at.
      payouts_by_key: lookup {(site, tournament_number): payouts_json_blob}.
      include_no_payout: se True, mao sem payout entra no zip sem payouts.json.
                         Se False, mao sem payout e excluida (vai para
                         manifest.missing_payouts).
      filters_meta: dict de filters echoado no manifest (observabilidade).

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

            hh_text = convert_gg_hh_to_pokerstars_compatible(h)
            if not hh_text:
                skipped.append({"hand_id": hand_id, "reason": "no_raw_hh"})
                continue

            key = (site, tnum) if site and tnum else None
            payout_blob = payouts_by_key.get(key) if key else None

            if payout_blob is None and not include_no_payout:
                missing_payouts.append({
                    "hand_id": hand_id,
                    "tournament_number": tnum,
                    "site": site,
                    "reason": "no_row_in_tournament_payouts",
                })
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

            # #META-AGGRESSOR-REAL-ACTION mantém-se em payouts.json para o
            # Bloco 2 do watcher (Selected Subtree + click por position match).
            if _bb is not None:
                aggressor_real_action = derive_aggressor_real_action(
                    hh_text, _sb, _bb,
                )
            else:
                aggressor_real_action = None
            hints["aggressor_real_action"] = aggressor_real_action

            # pt25e Bloco 2 piece 2: target_node_offset para o watcher
            # premer seta-para-baixo até pousar na linha do raiser real
            # antes da 2ª run em Selected Subtree.
            target_node_offset = None
            if aggressor_real_action is not None and _bb is not None:
                try:
                    from app.services.hrc_node_offset import (
                        compute_target_node_offset, derive_aggressor_stack_bb,
                    )
                    raiser_stack_bb = derive_aggressor_stack_bb(hh_text, _bb)
                    target_node_offset = compute_target_node_offset(
                        aggressor_real_action,
                        hints.get("max_players"),
                        script_overrides,
                        raiser_stack_bb,
                    )
                except Exception:
                    logger.exception(
                        "compute_target_node_offset falhou hand_id=%s", hand_id,
                    )
                    target_node_offset = None

            if payout_blob is not None:
                merged: dict = dict(payout_blob) if isinstance(payout_blob, dict) else {"_blob": payout_blob}
                merged.update(hints)
                zf.writestr(
                    f"{hand_id}/payouts.json",
                    json.dumps(merged, indent=2, ensure_ascii=False),
                )
            else:
                zf.writestr(
                    f"{hand_id}/payouts.json",
                    json.dumps(hints, indent=2, ensure_ascii=False),
                )

            # pt25e Bloco 2 piece 2: meta.json passa a ser produzido pelo
            # backend (em vez de input manual do Rui). 4 legacy fields
            # preservados + target_node_offset novo.
            hand_meta = _build_hand_meta(
                h, hh_text,
                equity_model=hints.get("equity_model"),
                payout_blob=payout_blob,
                target_node_offset=target_node_offset,
            )
            zf.writestr(
                f"{hand_id}/meta.json",
                json.dumps(hand_meta, indent=2, ensure_ascii=False),
            )

            hands_included.append({
                "hand_id": hand_id,
                "tournament_number": tnum,
                "site": site,
                "has_payouts": payout_blob is not None,
                "has_script": script_js is not None,
                "script_overrides": script_overrides,
                "script_generation_error": script_error,
                "effective_stack_bb": effective_stack_bb,
                "aggressor_position": derive_real_aggressor_position(hh_text),
                "aggressor_real_action": aggressor_real_action,
                "target_node_offset": target_node_offset,
                "hand_meta": hand_meta,
                "converted_format": (
                    "pokerstars_compat" if site == "GGPoker" else "passthrough"
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
