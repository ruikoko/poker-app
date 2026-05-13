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

from app.services.derive_max_players import derive_max_players

logger = logging.getLogger("queue_export")

# pt25: caminho canónico do JS template usado por generate_hrc_script.
# Resolve-se relativo a este ficheiro (backend/app/services/queue_export.py)
# → <repo>/tools/hrc_scripts/...bvb.js. Mudar nome do template aqui se a
# variante canónica mudar.
_PRUNE_JS_TEMPLATE_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "..", "..", "..", "tools", "hrc_scripts",
    "mtt_advanced_20211029 - 2 flats + bb close action size open 2x - 3x bvb.js",
)


# pt23 fix Bug A: tags que disparam Malmuth-Harville ICM (FT-style equity).
# Restantes mãos default → multi_table_icm. HM3 usa nomes capitalizados;
# Discord usa nomes lowercase hyphenated.
_EQUITY_FT_HM3 = {"ICM FT", "ICM PKO FT"}
_EQUITY_FT_DISCORD = {"icm-ft", "icm-pko-ft"}


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


# pt25: helpers para #HRC-PRUNE-IN-GAP-DOWNSTREAM
# HRC scripting convention: índices 0..N-1 onde SB=0, BB=1, UTG=2, ..., BTN=N-1.
# Preflop turn order = [UTG, UTG+1, ..., BTN, SB, BB] = [2, 3, ..., N-1, 0, 1].
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


# pt25b: labels canónicos por número de jogadores sentados na mão. HRC convention
# SB=0, BB=1, UTG=2, ... — labels post-UTG variam consoante o N (mesa "regular"
# de N-max). Para tables com seats vazios (e.g. 6-max com 5 sentados após
# eliminação), tratamos como N-handed (CO desaparece em 5-handed).
_POSITION_LABELS_BY_N: dict = {
    2: ["BTN/SB", "BB"],
    3: ["SB", "BB", "BTN"],
    4: ["SB", "BB", "UTG", "BTN"],
    5: ["SB", "BB", "UTG", "HJ", "BTN"],
    6: ["SB", "BB", "UTG", "HJ", "CO", "BTN"],
    7: ["SB", "BB", "UTG", "EP", "MP", "CO", "BTN"],
    8: ["SB", "BB", "UTG", "EP", "MP", "HJ", "CO", "BTN"],
    9: ["SB", "BB", "UTG", "EP1", "EP2", "MP", "HJ", "CO", "BTN"],
}


def derive_seats_in_preflop_order(hh_text: str) -> list:
    """pt25b — fonte canónica do mapping seat ↔ HRC player index ↔ position
    label ↔ nick, ordenado pre-flop (SB primeiro = hrc_idx 0).

    Parsing:
    - Header (pre `find_preflop_marker`): Seat lines com nick + chip stack
    - Button: `Seat #N is the button` (universal nos 4 sites)
    - SB = seat imediatamente clockwise após button

    Posições labelled por convenção `_POSITION_LABELS_BY_N[N]` onde N é o
    nº de jogadores sentados na mão (não o table_format). Mesa 6-max com
    5 sentados → tratada como 5-handed (CO desaparece).

    Devolve `[]` se parsing falhar (sem button, sem seats, button fora do
    seat list). Cada entry: `{seat: int, position: str, hrc_idx: int, nick: str}`.
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
    sb_idx_in_list = (btn_idx_in_list + 1) % n

    labels = _POSITION_LABELS_BY_N.get(n) or [f"POS{i}" for i in range(n)]

    out: list = []
    for hrc_idx in range(n):
        seat_in_list = (sb_idx_in_list + hrc_idx) % n
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
    """pt25 — devolve o HRC player index do primeiro a abrir o pot preflop
    com raise/bet voluntário.

    Excepções (devolvem None per regra pt23):
    - Nenhum raise/bet preflop (limp pot, walk-to-BB)
    - Primeiro raiser é SB (HRC idx 0) — "SB-aberto", excepção da regra
    - Parsing falha (sem button, sem marker preflop, etc.)

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
    if idx == 0:
        return None  # SB-aberto excepção
    return idx


def derive_prune_downstream(
    aggressor_pos: Optional[int],
    max_players: Optional[int],
    players_left: Optional[int],
    seated_hrc_indices: Optional[list] = None,
    table_format: int = 8,
) -> list:
    """pt25 — devolve lista de HRC player indexes a prune (opens-in-gap downstream).

    Regra Rui pt23:
    - aggressor_pos None ou SB (idx 0) → [] (excepção, nada a prune)
    - players_left <= 3 * max_players → [] (FT phase, prune não vale a pena)
    - max_players None → [] (defensivo, sem threshold)
    - Senão → posições downstream do aggressor em ordem preflop, até SB
      inclusive (BB excluído porque é tipicamente o respondedor/hero).

    pt25b: `seated_hrc_indices` (list[int]) é a fonte canónica do tamanho da
    mesa em uso na mão (N-handed). Vem de `derive_seats_in_preflop_order`.
    Se fornecido, walk pelos sentados em ordem preflop. Caso contrário cai
    em `table_format` (default 8) — usado pelos tests sintéticos pt25 e por
    callers legacy.

    Exemplos:
    - 8-max full (seated=[0..7]): aggressor UTG (2) → [3, 4, 5, 6, 7, 0]
    - 6-max 5-sentados (seated=[0..4], e.g. INTERSTELLAR pós-eliminação):
        aggressor UTG (2) → [3, 4, 0]  (HJ, BTN, SB — sem CO em 5-handed)
    - 6-max full (seated=[0..5]): aggressor UTG (2) → [3, 4, 5, 0]
    """
    if aggressor_pos is None or aggressor_pos == 0:
        return []
    if max_players is None or players_left is None:
        return []
    if players_left <= 3 * max_players:
        return []

    # N = número de sentados (canónico) ou table_format (fallback legacy)
    if seated_hrc_indices is not None:
        n = len(seated_hrc_indices)
    else:
        n = table_format

    # Preflop turn order excluindo BB (idx 1):
    # [UTG=2, 3, ..., N-1, SB=0]
    preflop_order: list = []
    for offset in range(n):
        idx = (2 + offset) % n
        if idx == 1:
            continue
        preflop_order.append(idx)

    if aggressor_pos not in preflop_order:
        return []
    i = preflop_order.index(aggressor_pos)
    return preflop_order[i + 1:]


# pt25b: regex que match as 2 linhas do bloco placeholder no template B2.
# `[^;\\n]+` captura qualquer valor entre `=` e `;` (null/int para AGGRESSOR;
# []/lista para DOWNSTREAM). Permite re-substituir após injecção prévia →
# idempotência ao rodar `generate_hrc_script` 2× com mesmos args.
_PRUNE_PLACEHOLDER_RE = re.compile(
    r"^let REAL_AGGRESSOR_POS = [^;\n]+;[\t ]*\n"
    r"let DOWNSTREAM_POSITIONS = [^;\n]+;",
    re.MULTILINE,
)


def generate_hrc_script(
    template_path: str,
    aggressor_pos: Optional[int],
    downstream_positions: list,
) -> str:
    """pt25 — gera JS HRC com hint REAL_AGGRESSOR_POS + DOWNSTREAM_POSITIONS
    para a mão actual.

    Se aggressor_pos é None ou downstream_positions é empty (SB-aberto, FT
    phase, parsing falha): injecta defaults null/[] → JS comporta-se idêntico
    ao original (no-op, sem prune).

    pt25b: usa `_PRUNE_PLACEHOLDER_RE.subn` para SUBSTITUIR o bloco placeholder
    existente do template (introduzido em B2 com defaults null/[]). Evita
    duplicate `let` declarations que causariam JS SyntaxError no Nashorn/HRC.
    **Idempotente**: chamar 2× consecutivas com mesmos args produz output
    byte-idêntico.

    Fallback legacy: se template não tem o placeholder (versão antiga ou
    template alternativo), insere bloco hint antes de `let ALLIN = 9999;`.
    Se nem o marker ALLIN existir, prepend no topo (degrade gracioso).
    """
    with open(template_path, "r", encoding="utf-8") as f:
        template = f.read()

    if aggressor_pos is None or not downstream_positions:
        agg_val = "null"
        ds_val = "[]"
    else:
        agg_val = str(aggressor_pos)
        ds_val = "[" + ", ".join(str(p) for p in downstream_positions) + "]"

    replacement = (
        f"let REAL_AGGRESSOR_POS = {agg_val};\n"
        f"let DOWNSTREAM_POSITIONS = {ds_val};"
    )

    new_template, n_subs = _PRUNE_PLACEHOLDER_RE.subn(
        replacement, template, count=1,
    )
    if n_subs > 0:
        return new_template

    # Fallback: template sem placeholder. Insere bloco hint (com header
    # comment próprio) antes de `let ALLIN = 9999;`. Sem ALLIN → prepend.
    hint = (
        "// pt25 prune-in-gap-downstream hints (injected by backend per-hand)\n"
        + replacement + "\n\n"
    )
    marker = "let ALLIN = 9999;"
    if marker in template:
        return template.replace(marker, hint + marker, 1)
    return hint + template


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

    Devolve 'malmuth_harville_icm' se houver tag FT (HM3 ou Discord);
    caso contrário 'multi_table_icm' (default p/ mid-MTT).
    """
    hm3 = set(hm3_tags or [])
    disc = set(discord_tags or [])
    if hm3 & _EQUITY_FT_HM3 or disc & _EQUITY_FT_DISCORD:
        return "malmuth_harville_icm"
    return "multi_table_icm"


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

    Devolve None quando nenhuma fonte fornece valor — `derive_prune_downstream`
    com `None` → [] → prune off para a mão (graceful).

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


def _try_build_prune_script(hand: dict, hh_text: str, hints: dict, payout_blob):
    """pt25 — devolve (aggressor_pos, downstream, js_string|None).

    Não tem side-effects; o caller (build_queue_zip) decide se escreve no
    zip + actualiza `hints['script_path']`. None no js_string significa "não
    há prune para esta mão" (SB-aberto, FT phase, players_left missing,
    parsing falha, etc.) — caller mantém comportamento default (sem JS no
    zip, script_path mantém valor pre-existente).

    pt25b: passa `seated_hrc_indices` derivado de `derive_seats_in_preflop_order`
    para `derive_prune_downstream`. Suporta mesas com seats vazios (e.g.
    6-max com 5 sentados pós-eliminação) cross-site (GG/PS/WN/WPN).
    """
    aggressor = derive_real_aggressor_position(hh_text)
    max_players = hints.get("max_players")
    players_left = _resolve_players_left(hand, payout_blob)
    seats = derive_seats_in_preflop_order(hh_text)
    seated_indices = [s["hrc_idx"] for s in seats] if seats else None
    downstream = derive_prune_downstream(
        aggressor, max_players, players_left,
        seated_hrc_indices=seated_indices,
    )
    if not downstream:
        return aggressor, [], None
    try:
        js = generate_hrc_script(_PRUNE_JS_TEMPLATE_PATH, aggressor, downstream)
    except OSError as e:
        logger.warning("generate_hrc_script falhou (template I/O): %s", e)
        return aggressor, downstream, None
    return aggressor, downstream, js


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

            # pt25 prune-in-gap-downstream: se há aggressor identificado e
            # condições da regra batem (players_left > 3 × max_players, etc.),
            # gera JS dinâmico com hints REAL_AGGRESSOR_POS + DOWNSTREAM_POSITIONS
            # injectados; escreve no zip + override do hint script_path para
            # path relativo "script.js" (adapter no Beelink reescreve para
            # absoluto antes do watcher ler).
            try:
                prune_aggressor, prune_downstream, prune_script = _try_build_prune_script(
                    h, hh_text, hints, payout_blob,
                )
            except Exception:
                logger.exception("prune-in-gap build falhou hand_id=%s", hand_id)
                prune_aggressor, prune_downstream, prune_script = None, [], None
            if prune_script is not None:
                zf.writestr(f"{hand_id}/script.js", prune_script)
                hints["script_path"] = "script.js"

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

            hands_included.append({
                "hand_id": hand_id,
                "tournament_number": tnum,
                "site": site,
                "has_payouts": payout_blob is not None,
                "prune_aggressor": prune_aggressor,
                "prune_downstream": prune_downstream,
                "has_prune_script": prune_script is not None,
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
