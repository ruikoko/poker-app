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

# pt42 — Regra universal de sizings (substitui as duas regras anteriores:
# (a) "ALLIN só ≤25 BB nos opens" pré-pt25f; (b) tabela de multiplicadores
# do 3-bet clássico pt25f).
#
# 1ª opção do array de sizings = sizing original da HH (ou "ALLIN" se a
# acção foi all-in). 2ª opção:
#   - Se 1ª não é ALLIN AND `effective_stack_at_action_bb <= 25` → "ALLIN".
#   - Se 1ª é ALLIN AND condições do tipo de aposta satisfeitas → non-all-in
#     default per tipo (ver _compute_default_*).
#
# Threshold do ALLIN como 2ª opção em raises non-all-in.
_OPEN_ALLIN_THRESHOLD_BB = 25

# pt42 — Multiplicadores do non-all-in default por tipo de aposta. Só se
# aplicam quando o sizing original foi ALLIN (caso jam-or-fold com
# alternativa não-jam).
#
# 4-bet / 5-bet / squeeze são fixos; 3-bet clássico varia por efectiva
# (lower inclusivo, upper exclusivo).
_NON_ALL_IN_DEFAULT_OPEN_BB = 2.0          # 2 BB (só se eff > 8 BB e não-blind)
_NON_ALL_IN_OPEN_MIN_EFF_BB = 8.0
_NON_ALL_IN_DEFAULT_4BET_MULT = 2.3        # 2.3 × 3-bet anterior
_NON_ALL_IN_DEFAULT_5BET_MULT = 2.2        # 2.2 × 4-bet anterior
_NON_ALL_IN_DEFAULT_SQUEEZE_MULT = 3.0     # 3 × open original
# 3-bet clássico — multiplicador sobre opener_to_bb por bucket de efectiva.
_NON_ALL_IN_DEFAULT_3BET_MULT_HIGH = 3.0   # eff >= 35
_NON_ALL_IN_DEFAULT_3BET_MULT_MID = 2.7    # 26 <= eff < 35
_NON_ALL_IN_DEFAULT_3BET_MULT_LOW = 2.3    # eff < 26 (inclui 0-25)


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
        # pt42 — campos novos para a regra universal de sizings:
        'previous_raise_to_bb': float|None,   # to_amount_bb da raise anterior;
                                              # None para opens (bet_count=1)
        'opener_to_bb': float|None,           # to_amount_bb do open original;
                                              # None para opens (auto-ref)
        'is_all_in': bool,          # heurística 95%: raiser commits ~all do
                                    # stack inicial (reutiliza threshold de
                                    # hrc_node_offset._ALL_IN_EFFECTIVE_THRESHOLD)
        'effective_stack_at_action_bb': float|None,
            # min(raiser_remaining, max(active_opponents_remaining)) / BB;
            # recalculada por raise (dinâmica). None se faltar info de stacks.
      }

    Não-raises (folds, calls, checks, bets) não geram entry mas contribuem
    para pot tracking + callers_before. Folds removem o nick de active_players
    (usado em effective_stack_at_action_bb).
    """
    from app.services.queue_export import find_preflop_marker  # avoid cycle
    from app.services.hrc_node_offset import _ALL_IN_EFFECTIVE_THRESHOLD

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
    initial_stacks = _parse_seat_stacks(hh_text)

    contributions, pot_total, current_to_call = _init_pot_from_blinds_antes(
        hh_text, seats, level_sb, level_bb,
    )

    # pt42 — set de jogadores activos no momento de cada raise (para
    # effective_stack_at_action). Fold remove. Empty set defensivo.
    active_players: set = {
        s.get("nick") for s in seats if s.get("nick")
    }

    bet_count = 1  # BB is the implicit first "bet"
    last_raiser_idx: Optional[int] = None
    opener_idx: Optional[int] = None
    # pt42 — sizings cumulativos para a regra universal (BB).
    last_raise_to_bb: Optional[float] = None
    opener_to_bb_acc: Optional[float] = None
    callers_since_open = 0

    def _compute_effective_at_action(actor_nick: str) -> Optional[float]:
        """min(raiser_remaining, max(opp_remaining)) / BB, em BB.

        - Remaining = initial_stacks[nick] - contributions[nick] (antes do raise
          actual; reflecte o "que o jogador ainda tem para apostar").
        - Active opponents = `active_players` excluindo o actor.
        - None se faltar info (stack inicial do actor, ou nenhum opp activo).
        """
        actor_initial = initial_stacks.get(actor_nick)
        if actor_initial is None or level_bb <= 0:
            return None
        actor_remaining = actor_initial - contributions.get(actor_nick, 0.0)
        opps_remaining: list = []
        for other in active_players:
            if other == actor_nick:
                continue
            opp_initial = initial_stacks.get(other)
            if opp_initial is None:
                continue
            opps_remaining.append(
                opp_initial - contributions.get(other, 0.0)
            )
        if not opps_remaining:
            return None
        eff_chips = min(actor_remaining, max(opps_remaining))
        return round(eff_chips / float(level_bb), 2)

    def _is_all_in_for_actor(actor_nick: str, to_amount: float) -> bool:
        """True sse to_amount >= initial * 0.95 (raiser commits ~all)."""
        initial = initial_stacks.get(actor_nick)
        if initial is None or initial <= 0:
            return False
        return float(to_amount) >= float(initial) * _ALL_IN_EFFECTIVE_THRESHOLD

    def _append_raise_entry(
        nick: str,
        to_amount: float,
        previous_to_call: float,
    ) -> None:
        """Compõe a entry de uma raise/bet e adiciona-a a `out`.

        Não actualiza state — caller responsável por tudo o que altera
        `contributions`, `pot_total`, `current_to_call`, `bet_count`, etc.
        """
        raise_increment = to_amount - previous_to_call
        pot_after_call_actor = pot_total + max(
            previous_to_call - contributions.get(nick, 0.0), 0.0
        )
        pot_fraction = (
            round(raise_increment / pot_after_call_actor, 2)
            if pot_after_call_actor > 0 else 0.0
        )
        seat = nick_to_seat.get(nick) or {}
        eff_at_action_bb = _compute_effective_at_action(nick)
        is_all_in = _is_all_in_for_actor(nick, to_amount)
        entry = {
            "bet_count": bet_count,
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
            # pt42 — campos novos:
            "previous_raise_to_bb": last_raise_to_bb,
            "opener_to_bb": opener_to_bb_acc if bet_count > 1 else None,
            "is_all_in": is_all_in,
            "effective_stack_at_action_bb": eff_at_action_bb,
        }
        out.append(entry)

    for m in _ACTION_LINE_RE.finditer(preflop):
        nick = m.group("nick").strip()
        verb = m.group("verb")
        arg1 = _to_float(m.group("arg1"))
        arg2 = _to_float(m.group("arg2"))

        # Ignorar linhas que apanham markers como `*** SUMMARY ***` etc
        # (não deve passar o regex `\S+` mas defensivo).
        if nick.startswith("***"):
            continue

        if verb == "folds":
            active_players.discard(nick)
            continue
        if verb == "checks":
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

        if verb in ("bets", "raises"):
            # bets: arg1 = to_amount (preflop é raro/degenerate, trata como open)
            # raises: arg1 = incremento, arg2 = to-amount.
            if verb == "bets":
                if arg1 is None:
                    continue
                to_amount = arg1
            else:
                to_amount = arg2 if arg2 is not None else (arg1 or 0.0)
            previous_to_call = current_to_call
            _append_raise_entry(nick, to_amount, previous_to_call)

            # Atualiza estado depois de gravar a entry (campos novos usam
            # state pré-raise para `previous_raise_to_bb`, `opener_to_bb`,
            # `effective_stack_at_action_bb`).
            add = to_amount - contributions.get(nick, 0.0)
            contributions[nick] = to_amount
            pot_total += add
            current_to_call = to_amount
            seat = nick_to_seat.get(nick) or {}
            last_raiser_idx = seat.get("hrc_idx")
            this_to_bb = round(to_amount / float(level_bb), 2)
            last_raise_to_bb = this_to_bb
            if opener_idx is None:
                opener_idx = last_raiser_idx
                opener_to_bb_acc = this_to_bb
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


# ── Defaults non-all-in (pt42 — só usado quando original foi ALLIN) ────

def _compute_default_for_open(action: dict) -> Optional[float]:
    """Non-all-in default do open: 2 BB, só se efectiva > 8 BB e posição
    ≠ SB ≠ BB. None caso contrário (array fica `["ALLIN"]` só).

    HU: posição é "BU/SB" — não cai em ("SB","BB"), logo o 2 BB aplica-se.
    """
    pos = (action.get("position") or "").upper()
    if pos in ("SB", "BB"):
        return None
    eff = action.get("effective_stack_at_action_bb")
    if eff is None or eff <= _NON_ALL_IN_OPEN_MIN_EFF_BB:
        return None
    return _NON_ALL_IN_DEFAULT_OPEN_BB


def _compute_default_for_classic_3bet(action: dict) -> Optional[float]:
    """2.3/2.7/3 × opener_to_bb por bucket de efectiva.

    - eff < 26  → ×2.3 (inclui 0-25)
    - 26 ≤ eff < 35 → ×2.7
    - eff ≥ 35 → ×3.0

    None se faltar `opener_to_bb` ou efectiva.
    """
    opener_to_bb = action.get("opener_to_bb")
    if opener_to_bb is None:
        return None
    eff = action.get("effective_stack_at_action_bb")
    if eff is None:
        return None
    if eff >= 35:
        mult = _NON_ALL_IN_DEFAULT_3BET_MULT_HIGH
    elif eff >= 26:
        mult = _NON_ALL_IN_DEFAULT_3BET_MULT_MID
    else:
        mult = _NON_ALL_IN_DEFAULT_3BET_MULT_LOW
    return round(opener_to_bb * mult, 2)


def _compute_default_for_squeeze(action: dict) -> Optional[float]:
    """3 × opener_to_bb. None se faltar opener_to_bb."""
    opener_to_bb = action.get("opener_to_bb")
    if opener_to_bb is None:
        return None
    return round(opener_to_bb * _NON_ALL_IN_DEFAULT_SQUEEZE_MULT, 2)


def _compute_default_for_4bet(action: dict) -> Optional[float]:
    """2.3 × previous_raise_to_bb (3-bet anterior). None se faltar."""
    prev = action.get("previous_raise_to_bb")
    if prev is None:
        return None
    return round(prev * _NON_ALL_IN_DEFAULT_4BET_MULT, 2)


def _compute_default_for_5bet(action: dict) -> Optional[float]:
    """2.2 × previous_raise_to_bb (4-bet anterior). None se faltar."""
    prev = action.get("previous_raise_to_bb")
    if prev is None:
        return None
    return round(prev * _NON_ALL_IN_DEFAULT_5BET_MULT, 2)


def _array_for_raise(
    action: dict,
    non_all_in_default: Optional[float],
) -> list:
    """Aplica a regra universal de sizings a uma acção (open / 3-bet
    clássico / squeeze / 4-bet / 5-bet).

    - 1ª opção = sizing original em BB (ou "ALLIN" se a acção foi all-in).
    - 2ª opção:
        * original NÃO é ALLIN + eff ≤ 25 BB → "ALLIN".
        * original NÃO é ALLIN + eff > 25 BB (ou eff None) → sem 2ª opção.
        * original É ALLIN + `non_all_in_default` not None → o default.
        * original É ALLIN + default None → sem 2ª opção (array só `["ALLIN"]`).
    """
    is_all_in = bool(action.get("is_all_in"))
    eff = action.get("effective_stack_at_action_bb")
    to_bb = action.get("to_amount_bb")

    if is_all_in:
        if non_all_in_default is not None:
            return ["ALLIN", non_all_in_default]
        return ["ALLIN"]

    # Original NÃO é ALLIN — 1ª opção é o sizing real.
    if eff is not None and eff <= _OPEN_ALLIN_THRESHOLD_BB:
        return [to_bb, "ALLIN"]
    return [to_bb]


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

    pt42 — Regra universal de sizings:
      * 1ª opção = sizing original em BB (ou `"ALLIN"` se a acção foi
        all-in, detectada via `is_all_in` no parser).
      * 2ª opção:
          - Original NÃO é ALLIN + `effective_stack_at_action_bb <= 25`
            → `"ALLIN"`.
          - Original NÃO é ALLIN + eff > 25 BB ou None → sem 2ª opção
            (array só `[to_amount_bb]`).
          - Original É ALLIN + non-all-in default do tipo aplicável
            → o default (BB para opens/3-bet/squeeze; pot-fraction
            derivada para 4-bet/5-bet).
          - Original É ALLIN + default None → sem 2ª opção (`["ALLIN"]`).

    Non-all-in defaults por tipo (só quando original = ALLIN):
      * Open: 2 BB, só se eff > 8 BB e posição ≠ SB ≠ BB.
      * 3-bet clássico: 2.3 (eff <26) / 2.7 (26-34) / 3.0 (≥35) × opener_to_bb.
      * Squeeze: 3.0 × opener_to_bb.
      * 4-bet: 2.3 × previous_raise_to_bb (3-bet anterior, em BB).
      * 5-bet: 2.2 × previous_raise_to_bb (4-bet anterior, em BB).

    Acções não-realizadas → sem entry no dict → defaults do template ficam.
    Múltiplas acções no mesmo bucket → primeira ganha (raro em real life).

    Nota sobre 4-bet/5-bet: o template canónico continua a usar
    `SIZES_POT_4BET_*` / `SIZES_POT_5BET_*` como pot fractions. A
    conversão BB → pot-fraction é feita aqui via `pot_after_call_chips`
    + `raise_increment` (ver `_array_for_4bet5bet_in_pot_fraction`).

    Parameter `effective_stack_bb` mantido para retrocompatibilidade mas
    NÃO é usado — a efectiva passou a ser dinâmica por acção (campo
    `effective_stack_at_action_bb` no parser).
    """
    if not hh_text or not seats:
        return {}

    overrides: dict = {}
    actions = _parse_preflop_actions(hh_text, seats, level_sb, level_bb)

    for a in actions:
        bc = a["bet_count"]

        if bc == 1:
            var = _bucket_open(a)
            if var and var not in overrides:
                default = _compute_default_for_open(a)
                overrides[var] = _array_for_raise(a, default)
            continue

        if bc == 2:
            opener_position = (
                actions[0].get("position") if actions and actions[0].get("bet_count") == 1
                else None
            )
            var = _bucket_3bet(a, opener_position)
            if var and var not in overrides:
                if var.startswith("SIZES_3BET_SQUEEZE_"):
                    default = _compute_default_for_squeeze(a)
                else:
                    default = _compute_default_for_classic_3bet(a)
                overrides[var] = _array_for_raise(a, default)
            continue

        if bc in (3, 4):
            var = _bucket_4bet5bet(a, len(seats))
            if var and var not in overrides:
                if bc == 3:
                    bb_default = _compute_default_for_4bet(a)
                else:
                    bb_default = _compute_default_for_5bet(a)
                overrides[var] = _array_for_4bet5bet_in_pot_fraction(
                    a, bb_default, level_bb,
                )
            continue

        # bc >= 5: skip (template runtime shove-or-fold em getSizingsPreflop).

    return overrides


def _array_for_4bet5bet_in_pot_fraction(
    action: dict,
    non_all_in_default_bb: Optional[float],
    level_bb: int,
) -> list:
    """Variante de `_array_for_raise` para 4-bet/5-bet: a regra universal
    expressa-se em BB, mas o template usa SIZES_POT_*BET_* como pot-fraction
    (a JS function aplica `ctx.sizingPot(s)`). Esta função traduz BB→fração
    para os 4-bet/5-bet.

    Mantém a mesma lógica de 1ª/2ª opção; só altera a UNIDADE escrita no
    .js para que o consumidor (HRC) gere a aposta esperada.
    """
    is_all_in = bool(action.get("is_all_in"))
    eff = action.get("effective_stack_at_action_bb")
    pot_fr_real = action.get("pot_fraction") or 0.0

    def _bb_to_pot_fraction(target_bb: Optional[float]) -> Optional[float]:
        if target_bb is None or level_bb <= 0:
            return None
        pot_after_call = action.get("pot_after_call_chips") or 0.0
        if pot_after_call <= 0:
            return None
        target_chips = float(target_bb) * float(level_bb)
        # raise_increment = target_chips - previous_to_call_chips.
        # previous_to_call_chips = to_amount_chips - raise_increment_chips.
        prev_to_call_chips = (
            (action.get("to_amount_chips") or 0.0)
            - (action.get("raise_increment_chips") or 0.0)
        )
        inc = target_chips - prev_to_call_chips
        if inc <= 0:
            return None
        return round(inc / pot_after_call, 2)

    if is_all_in:
        default_pot_fr = _bb_to_pot_fraction(non_all_in_default_bb)
        if default_pot_fr is not None:
            return ["ALLIN", default_pot_fr]
        return ["ALLIN"]

    if eff is not None and eff <= _OPEN_ALLIN_THRESHOLD_BB:
        return [pot_fr_real, "ALLIN"]
    return [pot_fr_real]


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
