"""Geração do `script.js` HRC per-hand a partir da HH real.

Substitui o antigo `_try_build_prune_script` + `generate_hrc_script` em
`services/queue_export.py` (que injectava apenas hints de prune-in-gap
no template). O novo gerador:

1. Lê o template canónico em `hrc_scripts/mtt_advanced_canonical_2026.js`.
2. Parseia a HH para extrair cada raise/bet preflop em sequência
   (open / 3-bet / squeeze / 4-bet / 5-bet) com pot tracking.
3. Calcula efectiva (min stack inicial em BB) para decidir se mantém
   `ALLIN` nos arrays `SIZES_OPEN_*` (≤25BB → sim; >25BB → não).
4. Substitui apenas os `SIZES_*` que a mão tocou — os restantes ficam
   com os defaults do template.
5. Devolve o JS pronto a escrever no zip + o dict de overrides
   aplicados (para observabilidade no manifest).

Prune via JS (REAL_AGGRESSOR_POS + DOWNSTREAM_POSITIONS injectados +
guard no template) foi removido — o trabalho equivalente migrou para o
Bloco 2 do watcher (selecção manual de Selected Subtree + Prune Action
linha-a-linha). `derive_real_aggressor_position` continua útil para
observabilidade; `derive_aggressor_real_action` continua a viajar em
`payouts.json` para o futuro click visual do watcher.
"""
from __future__ import annotations

import logging
import os
import re
from typing import Optional

logger = logging.getLogger("hrc_script_gen")


_HRC_TEMPLATE_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "hrc_scripts",
    "mtt_advanced_canonical_2026.js",
)

# ≤ → ALLIN fica como 2ª entrada nos SIZES_OPEN_*; > → só size real.
# Decisão product (Maio 2026): em stacks profundas o jam-only-or-open
# é ruído na árvore HRC.
_OPEN_ALLIN_THRESHOLD_BB = 25


# ── Regra do multiplicador para 3-bets clássicos ──────────────────────
# Decisão product (Maio 2026, extensão pós-9b6e839): para os 5 buckets
# de 3-bet clássico, o sizing real da HH é ignorado. Em vez disso,
# aplica-se um multiplicador ao default do template em função da stack
# efectiva. Squeezes mantêm sizing real.
#
# Convenção dos limiares: lower bound inclusivo, upper bound exclusivo
# (`eff_bb >= threshold` em cascata). Isso resolve as duas perguntas de
# fronteira:
#   - eff_bb == 25  → cai em [25,30), multiplicador ×0.80
#   - eff_bb == 18  → cai em [18,25), multiplicador ×0.70
# Justificação: uma cadeia única `eff_bb >= 35/30/25/18` sem casos
# especiais, lê do mais profundo para o mais raso, e cada tier é
# mutuamente exclusivo sem ambiguidade no ponto-fronteira.
_CLASSIC_3BET_DEFAULTS = {
    "SIZES_3BET_IP": 6,
    "SIZES_3BET_BB_VS_SB": 10,
    "SIZES_3BET_BB_VS_OTHER": 8,
    "SIZES_3BET_SB_VS_BB": 11,
    "SIZES_3BET_SB_VS_OTHER": 8,
}


# ── Regex parsing ───────────────────────────────────────────────────────

# Seat header line: "Seat 1: Hero (40,000 in chips)" (PS/GG/WN) ou
# "Seat 1: Jetsies (448465.00)" (WPN, sem " in chips"). Captura nick + chips.
_SEAT_STACK_RE = re.compile(
    r"^Seat \d+:\s+(?P<nick>.+?)\s+\((?P<chips>[\d,]+(?:\.\d+)?)"
    r"(?:\s+in\s+chips)?",
    re.MULTILINE,
)

# Linhas de "posts" antes do preflop marker. Tolera 3 formatos:
#   - PS: "kokonakueka: posts the ante 3250"
#   - PS: "Hero: posts small blind 150"
#   - WN/WPN: "Beu_Teu posts ante 1000"  (sem colon, sem "the")
# Capture: nick + tipo (ante / small blind / big blind) + amount.
_POST_LINE_RE = re.compile(
    r"^(?P<nick>.+?)(?::)?\s+posts\s+(?:the\s+)?"
    r"(?P<type>small\s+blind|big\s+blind|ante)\s+(?P<amt>[\d,.]+)",
    re.MULTILINE,
)

# Linha de acção preflop. PS/GG têm colon (`Hero: raises ...`); WN/WPN
# não (`blueballs67 raises ...`). Capture nick + verbo + argumentos.
# IMPORTANTE: usar `[ \t]+` em vez de `\s+` para não consumir `\n` — `\s+`
# greedy + arg1/arg2 opcionais faz `finditer` saltar a linha seguinte.
_ACTION_LINE_RE = re.compile(
    r"^(?P<nick>.+?)(?::)?[ \t]+"
    r"(?P<verb>folds|checks|calls|raises|bets)"
    r"(?:[ \t]+(?P<arg1>[\d,.]+))?"
    r"(?:[ \t]+to[ \t]+(?P<arg2>[\d,.]+))?",
    re.MULTILINE,
)


def _to_float(s: str) -> Optional[float]:
    """Converte string com vírgulas de milhar e/ou decimais para float.
    `None` se não conseguir."""
    if s is None:
        return None
    try:
        return float(s.replace(",", ""))
    except (ValueError, AttributeError):
        return None


def _parse_seat_stacks(hh_text: str) -> dict:
    """Mapa `{nick: chips_float}` lido dos Seat lines do header.

    Devolve `{}` se nada encontrado (HH inválida).
    """
    if not hh_text:
        return {}
    out: dict = {}
    for m in _SEAT_STACK_RE.finditer(hh_text):
        nick = m.group("nick").strip()
        chips = _to_float(m.group("chips"))
        if nick and chips is not None:
            out[nick] = chips
    return out


def compute_effective_stack_bb(
    hh_text: str, level_bb: int
) -> Optional[float]:
    """Stack efectiva da mão = min stack inicial dos sentados, em BB.

    Devolve `None` se HH não tiver seats parseáveis ou `level_bb` inválido.
    """
    if not hh_text or not isinstance(level_bb, (int, float)) or level_bb <= 0:
        return None
    stacks = _parse_seat_stacks(hh_text)
    if not stacks:
        return None
    return round(min(stacks.values()) / float(level_bb), 2)


def _position_bucket_open(position: Optional[str]) -> str:
    """Mapeia label de posição → bucket de SIZES_OPEN_*.

    Labels canónicos de `_POSITION_LABELS_BY_N` em queue_export.py.
    BU/SB (HU label composto) → trata como BU (o jogador é botão).
    """
    if not position:
        return "OTHERS"
    p = position.strip().upper()
    if p in ("BU", "BTN", "BU/SB"):
        return "BU"
    if p == "SB":
        return "SB"
    if p == "BB":
        return "BB"
    return "OTHERS"


def _postflop_rank(preflop_idx: int, n: int) -> int:
    """Rank de actuação postflop (asc = mais OOP). SB=0, BB=1, UTG=2, ..., BU=N-1.

    Usado para IP/OOP no 4-bet/5-bet. Player com rank mais alto = IP.
    """
    if preflop_idx == n - 2:  # SB
        return 0
    if preflop_idx == n - 1:  # BB
        return 1
    return preflop_idx + 2


def _is_in_position(actor_idx: int, opponent_idx: int, n: int) -> bool:
    """True sse `actor_idx` actua DEPOIS de `opponent_idx` no postflop
    (i.e., está IP relativamente ao opponent)."""
    return _postflop_rank(actor_idx, n) > _postflop_rank(opponent_idx, n)


def _init_pot_from_blinds_antes(
    hh_text: str,
    seats: list,
    level_sb: int,
    level_bb: int,
) -> tuple:
    """Compõe estado inicial do pot a partir de "posts" lines + blinds/antes
    derivadas do level header.

    Devolve (`contributions`, `pot_total`, `current_to_call`).
    - `contributions`: {nick: chips_total_contributed}
    - `pot_total`: soma de tudo.
    - `current_to_call`: amount que o próximo a falar deve igualar (= BB inicial).

    Estratégia:
    - Lê todas as "posts" lines (ante / small blind / big blind) na secção
      antes do preflop marker (e tolera linhas no início do preflop section
      em algumas variantes).
    - Se nenhuma "small blind" / "big blind" line existir mas tivermos seats
      com labels SB/BB, fallback para level_sb/level_bb.
    """
    from app.services.queue_export import find_preflop_marker  # avoid cycle

    contributions: dict = {}
    seen_sb = False
    seen_bb = False

    # Pré-preflop section.
    end = find_preflop_marker(hh_text)
    pre = hh_text[:end] if end is not None else hh_text
    for m in _POST_LINE_RE.finditer(pre):
        nick = m.group("nick").strip()
        kind = re.sub(r"\s+", " ", m.group("type").strip().lower())
        amt = _to_float(m.group("amt"))
        if not nick or amt is None:
            continue
        contributions[nick] = contributions.get(nick, 0.0) + amt
        if kind == "small blind":
            seen_sb = True
        elif kind == "big blind":
            seen_bb = True

    # Fallback: se blinds não estavam explícitos, assume level_sb / level_bb
    # nos seats com labels SB / BB.
    if not seen_sb or not seen_bb:
        for s in seats:
            pos = (s.get("position") or "").upper()
            nick = s.get("nick")
            if not nick:
                continue
            if pos == "SB" and not seen_sb:
                contributions[nick] = contributions.get(nick, 0.0) + float(level_sb)
            elif pos == "BB" and not seen_bb:
                contributions[nick] = contributions.get(nick, 0.0) + float(level_bb)

    pot_total = sum(contributions.values())
    return contributions, pot_total, float(level_bb)


def _parse_preflop_actions(
    hh_text: str, seats: list, level_sb: int, level_bb: int,
) -> list:
    """Walk preflop section. Devolve lista ordenada de raises com pot context.

    Entry shape:
      {
        'bet_count': int,           # 1=open, 2=3-bet, 3=4-bet, 4=5-bet, ...
        'nick': str,
        'hrc_idx': int|None,
        'position': str|None,
        'to_amount_chips': float,
        'to_amount_bb': float,      # round 2
        'raise_increment_chips': float,
        'pot_after_call_chips': float,   # pot se actor tivesse só called
        'pot_fraction': float,      # raise_increment / pot_after_call, round 2
        'callers_before': int,      # nº de calls entre o open e este raise
                                    #   (preenchido só para bet_count >= 2)
        'opener_idx': int|None,     # hrc_idx do primeiro raiser (bet_count=1)
        'previous_raiser_idx': int|None,  # idx do last raiser (bet_count-1)
      }

    Não-raises (folds, calls, checks, bets) não geram entry mas contribuem
    para pot tracking + callers_before.
    """
    from app.services.queue_export import find_preflop_marker  # avoid cycle

    out: list = []
    if not hh_text:
        return out

    start = find_preflop_marker(hh_text)
    if start is None:
        return out
    end_flop = hh_text.find("*** FLOP ***", start)
    end_summary = hh_text.find("*** SUMMARY ***", start)
    ends = [e for e in (end_flop, end_summary) if e > 0]
    end = min(ends) if ends else len(hh_text)
    preflop = hh_text[start:end]

    nick_to_seat = {s.get("nick"): s for s in seats}

    contributions, pot_total, current_to_call = _init_pot_from_blinds_antes(
        hh_text, seats, level_sb, level_bb,
    )

    bet_count = 1  # BB is the implicit first "bet"
    last_raiser_nick: Optional[str] = None
    last_raiser_idx: Optional[int] = None
    opener_idx: Optional[int] = None
    callers_since_open = 0

    for m in _ACTION_LINE_RE.finditer(preflop):
        nick = m.group("nick").strip()
        verb = m.group("verb")
        arg1 = _to_float(m.group("arg1"))
        arg2 = _to_float(m.group("arg2"))

        # Ignorar linhas que apanham markers como `*** SUMMARY ***` etc
        # (não deve passar o regex `\S+` mas defensivo).
        if nick.startswith("***"):
            continue

        if verb == "folds" or verb == "checks":
            continue

        if verb == "calls":
            # arg1 = amount called (incremento). Se ausente (raro), assume
            # current_to_call - contribution.
            current = contributions.get(nick, 0.0)
            if arg1 is None:
                add = max(current_to_call - current, 0.0)
            else:
                add = arg1
            contributions[nick] = current + add
            pot_total += add
            if opener_idx is not None:
                callers_since_open += 1
            continue

        if verb == "bets":
            # Bet preflop é raro (e.g., só no caso degenerate). Trata como
            # open: to_amount = arg1.
            if arg1 is None:
                continue
            to_amount = arg1
            raise_increment = to_amount - current_to_call
            pot_after_call_actor = pot_total + max(
                current_to_call - contributions.get(nick, 0.0), 0.0
            )
            pot_fraction = (
                round(raise_increment / pot_after_call_actor, 2)
                if pot_after_call_actor > 0 else 0.0
            )
            seat = nick_to_seat.get(nick) or {}
            entry = {
                "bet_count": bet_count + 0,  # bets is a fresh open
                "nick": nick,
                "hrc_idx": seat.get("hrc_idx"),
                "position": seat.get("position"),
                "to_amount_chips": to_amount,
                "to_amount_bb": round(to_amount / float(level_bb), 2),
                "raise_increment_chips": raise_increment,
                "pot_after_call_chips": pot_after_call_actor,
                "pot_fraction": pot_fraction,
                "callers_before": callers_since_open,
                "opener_idx": opener_idx,
                "previous_raiser_idx": last_raiser_idx,
            }
            out.append(entry)
            # Atualiza estado
            add = to_amount - contributions.get(nick, 0.0)
            contributions[nick] = to_amount
            pot_total += add
            current_to_call = to_amount
            last_raiser_nick = nick
            last_raiser_idx = seat.get("hrc_idx")
            if opener_idx is None:
                opener_idx = last_raiser_idx
            bet_count += 1
            callers_since_open = 0
            continue

        if verb == "raises":
            # arg1 = incremento, arg2 = to-amount.
            to_amount = arg2 if arg2 is not None else (arg1 or 0.0)
            previous_to_call = current_to_call
            raise_increment = to_amount - previous_to_call
            pot_after_call_actor = pot_total + max(
                previous_to_call - contributions.get(nick, 0.0), 0.0
            )
            pot_fraction = (
                round(raise_increment / pot_after_call_actor, 2)
                if pot_after_call_actor > 0 else 0.0
            )

            seat = nick_to_seat.get(nick) or {}
            this_bet_count = bet_count  # 1 = open, 2 = 3-bet, ...

            entry = {
                "bet_count": this_bet_count,
                "nick": nick,
                "hrc_idx": seat.get("hrc_idx"),
                "position": seat.get("position"),
                "to_amount_chips": to_amount,
                "to_amount_bb": round(to_amount / float(level_bb), 2),
                "raise_increment_chips": raise_increment,
                "pot_after_call_chips": pot_after_call_actor,
                "pot_fraction": pot_fraction,
                "callers_before": callers_since_open,
                "opener_idx": opener_idx,
                "previous_raiser_idx": last_raiser_idx,
            }
            out.append(entry)

            # Atualiza estado
            add = to_amount - contributions.get(nick, 0.0)
            contributions[nick] = to_amount
            pot_total += add
            current_to_call = to_amount
            last_raiser_nick = nick
            last_raiser_idx = seat.get("hrc_idx")
            if opener_idx is None:
                opener_idx = last_raiser_idx
            bet_count += 1
            callers_since_open = 0
            continue

    return out


def _bucket_open(action: dict) -> Optional[str]:
    """Devolve nome da variável SIZES_OPEN_* a substituir, ou None."""
    if action["bet_count"] != 1:
        return None
    bucket = _position_bucket_open(action.get("position"))
    return f"SIZES_OPEN_{bucket}"


def _bucket_3bet(action: dict, opener_position: Optional[str]) -> Optional[str]:
    """Devolve nome do SIZES_3BET_* / SIZES_3BET_SQUEEZE_* aplicável."""
    if action["bet_count"] != 2:
        return None
    threebetter_pos = (action.get("position") or "").upper()
    is_squeeze = (action.get("callers_before") or 0) > 0
    if is_squeeze:
        if threebetter_pos == "SB":
            return "SIZES_3BET_SQUEEZE_SB"
        if threebetter_pos == "BB":
            return "SIZES_3BET_SQUEEZE_BB"
        return "SIZES_3BET_SQUEEZE_IP"
    opener = (opener_position or "").upper()
    if threebetter_pos == "SB":
        if opener == "BB":
            return "SIZES_3BET_SB_VS_BB"
        return "SIZES_3BET_SB_VS_OTHER"
    if threebetter_pos == "BB":
        if opener == "SB":
            return "SIZES_3BET_BB_VS_SB"
        return "SIZES_3BET_BB_VS_OTHER"
    return "SIZES_3BET_IP"


def _bucket_4bet5bet(action: dict, n_seated: int) -> Optional[str]:
    """SIZES_POT_4BET_* / SIZES_POT_5BET_*, IP/OOP vs previous raiser."""
    bc = action["bet_count"]
    if bc not in (3, 4):
        return None
    actor_idx = action.get("hrc_idx")
    prev_idx = action.get("previous_raiser_idx")
    if actor_idx is None or prev_idx is None or n_seated < 2:
        return None
    ip = _is_in_position(actor_idx, prev_idx, n_seated)
    suffix = "IP" if ip else "OOP"
    if bc == 3:
        return f"SIZES_POT_4BET_{suffix}"
    return f"SIZES_POT_5BET_{suffix}"


def _classic_3bet_band(
    effective_stack_bb: Optional[float],
) -> tuple:
    """Devolve `(mult, shove_only)` para os 5 buckets de 3-bet clássico.

    - `eff >= 35`  → `(None, False)` — defaults intactos, sem override.
    - `[30, 35)`   → `(0.90, False)`
    - `[25, 30)`   → `(0.80, False)`
    - `[18, 25)`   → `(0.70, False)`
    - `eff < 18`   → `(None, True)`  — array `[ALLIN]` só (jam-or-fold).
    - `None`       → `(None, False)` — defensivo, sem override.
    """
    if effective_stack_bb is None:
        return None, False
    if effective_stack_bb >= 35:
        return None, False
    if effective_stack_bb >= 30:
        return 0.90, False
    if effective_stack_bb >= 25:
        return 0.80, False
    if effective_stack_bb >= 18:
        return 0.70, False
    return None, True


def _compute_classic_3bet_overrides(
    effective_stack_bb: Optional[float],
) -> dict:
    """Compõe `{var: sizings}` para os 5 buckets de 3-bet clássico.

    - eff >= 35 ou None → `{}` (defaults do template ficam).
    - eff < 18           → `{var: ["ALLIN"]}` para os 5 buckets.
    - Bandas intermédias → `{var: [round(default * mult, 2), "ALLIN"]}`.
    """
    mult, shove_only = _classic_3bet_band(effective_stack_bb)
    if shove_only:
        return {var: ["ALLIN"] for var in _CLASSIC_3BET_DEFAULTS}
    if mult is None:
        return {}
    return {
        var: [round(default * mult, 2), "ALLIN"]
        for var, default in _CLASSIC_3BET_DEFAULTS.items()
    }


def build_sizings_overrides(
    hh_text: str,
    level_sb: int,
    level_bb: int,
    seats: list,
    effective_stack_bb: Optional[float],
) -> dict:
    """Constrói `{var_name: [sizings...]}` para substituir no template.

    Argumentos:
      hh_text          — HH raw (preferivelmente já pokerstars-compat).
      level_sb,level_bb — chip values dos blinds para esta mão.
      seats            — `derive_seats_in_preflop_order(hh_text)` cached.
      effective_stack_bb — min stack inicial em BB. None → assume ≤25 (defensivo).

    Para cada raise/bet preflop walked:
      * 1º raise (bet_count=1) → SIZES_OPEN_<bucket>
      * 2º raise (bet_count=2) → SIZES_3BET_<bucket> ou SIZES_3BET_SQUEEZE_<bucket>
      * 3º raise (bet_count=3) → SIZES_POT_4BET_<IP|OOP>
      * 4º raise (bet_count=4) → SIZES_POT_5BET_<IP|OOP>
      * ≥ 5º raise (6-bet+)   → ignorado (template runtime devolve shove)

    Sizings:
      * Opens em BB: `[to_amount_bb, ALLIN]` se efectiva ≤25BB; `[to_amount_bb]`
        senão. `ALLIN` é o token literal `"ALLIN"` (não 9999) — fica no .js
        como nome da const já declarada no template.
      * 3-bets em BB: sempre `[to_amount_bb, ALLIN]`.
      * Squeezes em BB: sempre `[to_amount_bb, ALLIN]`.
      * 4-bet / 5-bet pot-fraction: sempre `[pot_fraction, ALLIN]`.

    Acções não-realizadas → sem entry no dict → defaults do template ficam.
    Múltiplas acções no mesmo bucket → primeira ganha (rare em real life).

    Excepção: os 5 buckets de 3-bet clássico (SIZES_3BET_IP / _BB_VS_SB /
    _BB_VS_OTHER / _SB_VS_BB / _SB_VS_OTHER) **ignoram o sizing real da HH**
    — recebem sempre o sizing derivado de `_compute_classic_3bet_overrides`
    (regra do multiplicador por efectiva). Squeezes não estão nesta excepção
    e continuam a usar o sizing real da HH.
    """
    if not hh_text or not seats:
        return {}

    overrides: dict = {}
    actions = _parse_preflop_actions(hh_text, seats, level_sb, level_bb)
    opener_position: Optional[str] = None
    n_seated = len(seats)
    keep_open_allin = (
        effective_stack_bb is None or effective_stack_bb <= _OPEN_ALLIN_THRESHOLD_BB
    )

    for a in actions:
        bc = a["bet_count"]

        if bc == 1:
            var = _bucket_open(a)
            opener_position = a.get("position")
            if var and var not in overrides:
                size = a["to_amount_bb"]
                if keep_open_allin:
                    overrides[var] = [size, "ALLIN"]
                else:
                    overrides[var] = [size]
            continue

        if bc == 2:
            var = _bucket_3bet(a, opener_position)
            # Squeezes mantêm sizing real da HH. Classic 3-bets ignoram —
            # a regra do multiplicador aplica-se post-loop.
            if (var and var.startswith("SIZES_3BET_SQUEEZE_")
                    and var not in overrides):
                overrides[var] = [a["to_amount_bb"], "ALLIN"]
            continue

        if bc in (3, 4):
            var = _bucket_4bet5bet(a, n_seated)
            if var and var not in overrides:
                overrides[var] = [a["pot_fraction"], "ALLIN"]
            continue

        # bc >= 5: skip (template runtime shove-or-fold).

    # Regra do multiplicador para os 5 buckets de 3-bet clássico.
    # Aplica-se sempre, independentemente de a HH ter (ou não) um 3-bet
    # clássico. Vazio se eff >= 35 BB (defaults do template ficam).
    overrides.update(_compute_classic_3bet_overrides(effective_stack_bb))

    return overrides


# ── Substituição no template ──────────────────────────────────────────

# Captura `let VAR = [...];` (ou trailing `;` no fim) para substituir o
# array inteiro. Usa-se com `re.escape(var)` no nome.
_VAR_LITERAL_RE_TEMPLATE = r"^let\s+{var}\s*=\s*\[[^\]]*\]\s*;\s*$"


def _format_sizing_array(values: list) -> str:
    """`[2, "ALLIN"]` → `"[2, ALLIN]"` (ALLIN sem aspas — é uma const JS)."""
    parts: list = []
    for v in values:
        if v == "ALLIN":
            parts.append("ALLIN")
        elif isinstance(v, float):
            # Preserva decimal mas remove .0 desnecessário
            if v == int(v):
                parts.append(str(int(v)))
            else:
                parts.append(str(v))
        else:
            parts.append(str(v))
    return "[" + ", ".join(parts) + "]"


def apply_sizings_overrides(template_text: str, overrides: dict) -> str:
    """Substitui cada `let VAR = [...];` no template pelo novo array.

    Variáveis em `overrides` que não existem no template ficam ignoradas
    (log warning). Variáveis no template que não estão em `overrides`
    ficam intactas.
    """
    out = template_text
    for var, values in overrides.items():
        pattern = re.compile(
            _VAR_LITERAL_RE_TEMPLATE.format(var=re.escape(var)),
            re.MULTILINE,
        )
        replacement = f"let {var} = {_format_sizing_array(values)};"
        new_out, n = pattern.subn(replacement, out, count=1)
        if n == 0:
            logger.warning(
                "apply_sizings_overrides: var %s não encontrada no template",
                var,
            )
            continue
        out = new_out
    return out


def generate_hrc_script_for_hand(
    hh_text: str,
    level_sb: int,
    level_bb: int,
    seats: list,
    template_path: Optional[str] = None,
) -> tuple:
    """Pipeline completo: ler template + parsear HH + aplicar overrides.

    Devolve `(js_string, overrides_dict, effective_stack_bb, error)`.

    - `js_string`: conteúdo final do .js, pronto para escrever no zip.
      `None` se template I/O falhou.
    - `overrides_dict`: `{var_name: [sizings]}` aplicados. Pode ser `{}` se
      a mão não teve raises preflop (walk-to-BB, limp pot) — o template
      é devolvido cru.
    - `effective_stack_bb`: float ou None (se parse de stacks falhou).
    - `error`: str descrevendo a falha do template I/O, ou None.

    No-raise scenarios devolvem template inalterado (não-erro).
    """
    path = template_path or _HRC_TEMPLATE_PATH
    try:
        with open(path, "r", encoding="utf-8") as f:
            template = f.read()
    except OSError as e:
        err = f"{type(e).__name__}: {e}"
        logger.error("template I/O falhou path=%s err=%s", path, err)
        return None, {}, None, err

    effective_bb = compute_effective_stack_bb(hh_text, level_bb)
    overrides = build_sizings_overrides(
        hh_text, level_sb, level_bb, seats, effective_bb,
    )
    if not overrides:
        return template, {}, effective_bb, None

    out = apply_sizings_overrides(template, overrides)
    return out, overrides, effective_bb, None
