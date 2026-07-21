"""Detetor de bounties recuperáveis (#CROWN-RECOVERY).

Varre as mãos GG KO/PKO com Gold e classifica coroas NULL em dois grupos
(desenho do Rui, 14 Jul):

- **GRUPO 1 (recuperável):** um jogador BUSTOU nesta mão (all-in + perdeu no
  showdown) E a coroa dele ficou NULL. É a pegada honesta do verde-KO — a coroa
  dourada própria desaparece ao ser eliminado; o valor recupera-se lendo o VERDE
  na coroa do matador (bounty = verde × 2), NUNCA mexendo no matador.
- **GRUPO 2 (falha real):** coroa NULL num jogador que NÃO bustou e NÃO é Hero →
  candidata ao fallback SS (balde das coroas existente).

Guardas (das 2 condições de produção validadas):
1. Posições via `parsers.gg_hands._get_position` (a MESMA do parser que escreveu
   `players_list.position`) — não re-derivar.
2. Mãos com `Seat lines != extraídos` (over-read do Cheque 1) são marcadas
   `over_read` e ficam FORA do grupo-1 automático (revisão à parte).

Read-only puro (classify_hand); a escrita é o fluxo (A)+(B) gated pelo carimbo
do Rui, noutro sítio. Ver `docs/JOURNAL_2026-07-14`."""
from __future__ import annotations
import json
import re

from app.parsers.gg_hands import _get_position
from app.hero_names import HERO_NAMES_ALL
# FONTE ÚNICA do "quem morreu nesta mão?" (#BUST-NO-COVERAGE-GUARD, #LEI-FIX-NA-CAUSA).
# Este módulo TINHA cópia própria da régua (all-in / perdeu / resto-em-BB) e era a única
# que aplicava a guarda da sobra — o detetor que ESCREVE as coroas não a tinha. As duas
# cópias colapsaram em `eliminated_bounty.allin_outcomes`; aqui já não se decide morte.
from app.services.eliminated_bounty import allin_outcomes

# Só as linhas de SENTAR (topo da HH): "Seat N: <hash> (X in chips)". Exigir
# "in chips" é crucial — senão as linhas do SUMMARY "Seat N: <hash> (button)
# showed ... and lost" também casavam e o `continue` impedia o _LOST_RE de correr
# (o eliminado com posição rotulada — SB/BB/BTN — nunca entrava em `lost`).
_SEAT_RE = re.compile(r"^Seat (\d+): (\S+) \([\d,]+ in chips\)")
_BUTTON_RE = re.compile(r"Seat #(\d+) is the button")
# vencedor do pote (o matador — onde está o verde do KO)
_WON_COLLECTED_RE = re.compile(r"^(\S+) collected\b")
_WON_SUMMARY_RE = re.compile(r"^Seat \d+: (\S+)\b.*\band won\b")
_TABLE_RE = re.compile(r"^Table '([^']+)'")

# NOTA (#BUST-NO-COVERAGE-GUARD): as réguas do all-in, do "perdeu" e do resto-em-BB
# viviam AQUI (`_ALLIN_RE`/`_LOST_RE`/`_BB_RE`/`_UNCALLED_RE`/`_ALIVE_MIN_BB`/
# `_parse_bb`/`_returned_by_hash`) e mudaram-se para `eliminated_bounty` — a casa do
# detetor que ESCREVE. Quem precisar delas importa de lá; não se re-cria cópia aqui.


def _parse_table(raw: str):
    for ln in (raw or "").splitlines():
        m = _TABLE_RE.match(ln.strip())
        if m:
            return m.group(1)
    return None


def seated_hashes(raw: str) -> set:
    """Hashes SENTADOS numa HH (linhas 'Seat N: <hash> (X in chips)'). Usado pela
    contraprova da mão-seguinte (o eliminado não se senta na mão a seguir)."""
    return set(_SEAT_RE.match(ln.strip()).group(2)
               for ln in (raw or "").splitlines() if _SEAT_RE.match(ln.strip()))


def _norm_pos(p) -> str:
    if not p:
        return ""
    return str(p).upper().replace("UTG+", "UTG").replace("MP+", "MP")


def _is_hero_name(name) -> bool:
    if not name:
        return False
    low = str(name).strip().lower()
    if low in HERO_NAMES_ALL:
        return True
    # nomes truncados na players_list ("Lauro Der..") — prefixo (mín 4 chars)
    base = low.rstrip(". ").strip()
    if len(base) >= 4:
        return any(h.startswith(base) or base.startswith(h) for h in HERO_NAMES_ALL)
    return False


def _parse_busts(raw: str):
    """(seats{seat:hash}, button_seat, num_players, mortos, vivos_que_perderam) da HH GG.

    A MESA (seats/botão) lê-se aqui; a MORTE **não** — os dois conjuntos vêm da fonte
    única `eliminated_bounty.allin_outcomes` (all-in por frase ou post forçado, sem
    coletar pote, separados pela régua do resto-em-BB). Este módulo já não tem régua
    própria: era a divergência que produziu o `#BUST-NO-COVERAGE-GUARD`."""
    seats: dict[int, str] = {}
    button_seat = None
    for ln in (raw or "").splitlines():
        s = ln.strip()
        m = _SEAT_RE.match(s)
        if m:
            seats[int(m.group(1))] = m.group(2)
            continue
        b = _BUTTON_RE.search(s)
        if b:
            button_seat = int(b.group(1))
    mortos, vivos = allin_outcomes(raw)
    return seats, button_seat, len(seats), mortos, vivos


def _winners_with_hash(raw: str, seats: dict, button_seat, num_players) -> list:
    """[(posição, hash)] dos vencedores do pote (o matador — na coroa dele mora o
    verde). Mantém o HASH para distinguir o Hero (hash literal 'Hero') — cuja
    entrada em players_list vem SEM posição, logo não casa pelo mapa posição→nome."""
    wins: set = set()
    for ln in (raw or "").splitlines():
        s = ln.strip()
        m = _WON_COLLECTED_RE.match(s)
        if not m and "in chips" not in s:
            m = _WON_SUMMARY_RE.match(s)
        if m:
            wins.add(m.group(1))
    out: list = []
    if button_seat and seats:
        for seat_num, h in seats.items():
            if h in wins:
                p = _get_position(seat_num, button_seat, list(seats.keys()), num_players)
                if p and p != "?":
                    out.append((_norm_pos(p), h))
    return out


def _players_list(pn):
    if isinstance(pn, str):
        try:
            pn = json.loads(pn or "{}")
        except Exception:
            pn = {}
    return (pn or {}).get("players_list") or []


def classify_hand(raw: str, pn) -> dict:
    """Classifica UMA mão. Devolve
    {num_hh, num_extracted, over_read, group1, misread, group2, matadores,
     bust_hashes, table}.
    - group1 = bustou de VERDADE (all-in + perdeu + resto < 1 BB) + coroa NULL →
      recuperável por verde × 2.
    - misread = all-in que perdeu MAS ficou com >= 1 BB (VIVO) + coroa NULL →
      leitura falhada da placa própria (re-ler), NUNCA verde × 2.
    - group2 = coroa NULL num não-bustado não-Hero (folded/etc) → balde das coroas.
    `bust_hashes`/`table` servem a contraprova da mão-seguinte no router. Puro."""
    # Os dois baldes vêm JÁ separados da fonte única (régua do resto-em-BB lá dentro):
    # `busted_real` = morreu mesmo · `alive_lost` = perdeu o all-in mas cobria e sobreviveu.
    seats, button_seat, num_hh, busted_real, alive_lost = _parse_busts(raw)
    plist = _players_list(pn)
    num_extracted = len(plist)
    over_read = (num_hh > 0 and num_extracted != num_hh)

    # posição de cada hash (via a função do parser) — separada por balde
    all_seat_nums = list(seats.keys())
    busted_positions: set[str] = set()
    misread_positions: set[str] = set()
    if button_seat and all_seat_nums:
        for seat_num, h in seats.items():
            if h in busted_real or h in alive_lost:
                pos = _get_position(seat_num, button_seat, all_seat_nums, num_hh)
                if pos and pos != "?":
                    (misread_positions if h in alive_lost
                     else busted_positions).add(_norm_pos(pos))

    # matador(es) — onde ler o verde do KO (coroa do vencedor do pote).
    # Se o vencedor é o Hero (hash 'Hero'), resolve pelo NOME REAL do Hero — a
    # entrada dele em players_list vem sem posição, logo não casa pelo mapa.
    pos_to_name = {_norm_pos(e.get("position")): e.get("name") for e in plist}
    hero_name = next((e.get("name") for e in plist if _is_hero_name(e.get("name"))), "Hero")
    matadores = []
    for pos, h in _winners_with_hash(raw, seats, button_seat, num_hh):
        if h == "Hero":
            matadores.append({"name": hero_name, "position": pos, "is_hero": True})
        else:
            matadores.append({"name": pos_to_name.get(pos), "position": pos, "is_hero": False})

    group1, misread, group2 = [], [], []
    for e in plist:
        name = e.get("name")
        if e.get("bounty_value_usd") is not None:
            continue                      # tem coroa → não é NULL
        if _is_hero_name(name):
            continue                      # Hero sem coroa = benigno
        pos = _norm_pos(e.get("position"))
        entry = {"name": name, "position": e.get("position")}
        if pos and pos in busted_positions:
            group1.append(entry)          # bustou (resto <1BB) + NULL = recuperável
        elif pos and pos in misread_positions:
            misread.append(entry)         # all-in perdido MAS vivo → re-ler placa
        else:
            group2.append(entry)          # não-bustou + não-Hero + NULL = falha real
    return {
        "num_hh": num_hh, "num_extracted": num_extracted, "over_read": over_read,
        "group1": group1, "misread": misread, "group2": group2, "matadores": matadores,
        "bust_hashes": sorted(busted_real), "table": _parse_table(raw),
    }
