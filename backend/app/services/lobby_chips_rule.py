"""#WN-TOTAL-CHIPS-FROM-LOBBY (24 Jul 2026) — total de fichas Winamax pelo print de lobby.

Regra do Rui (aprovada 24 Jul; o TS Winamax NÃO se importa — decisão 22 Jul mantida):
o total de fichas do torneio WN vem do PRINT DE LOBBY, assim:

  • estado do print (palavra por baixo do nome, lida pela Vision em `reg_open`):
    False → RUNNING · True → LATE_REG · ausente/None → UNKNOWN (histórico sem
    imagem guardada não se re-lê; SEM inferência de fecho por entradas estáticas,
    por decisão explícita do Rui);
  • escolha do print: o RUNNING mais tardio se existir; senão o mais tardio;
  • total = entradas totais (2º número de «Players X / Y», campo `entrants`)
    × `starting_stack` do print escolhido;
  • guarda «não-desce»: as entradas NUNCA descem no tempo — se o print escolhido
    tiver menos entradas que um anterior, usa-se o MÁXIMO e marca-se por-rever
    (`entrants_drop`); medido em 205 prints reais: 0 ocorrências;
  • a incoerência `average×restantes > entradas×stack` (fisicamente impossível)
    é SINALIZADOR de misread do average/restantes (`avg_incoherent`) — NUNCA
    veto às entradas (as entradas não usam esses campos);
  • `provisional=True` quando o print escolhido não é RUNNING (late-reg ou
    estado desconhecido) — «fichas provisórias — falta print pós-fecho»;
  • `re_entries`: valor mais tardio lido do lobby — INFO-ONLY (não entra em
    contas, não dispara nada; guarda-se para estatística futura).

Função pura, UM sítio só (LEI 3): consumida pelo live (`process_lobby_message`),
pelo reconcile (`reconcile_lobby_logs`) e pelo recálculo retroativo
(`wn_chips_recalc`). SÓ Winamax — a GG nunca passa por aqui (chips GG:
`build_hrc_payouts_blob` + override TS `#ICM-CHIPS-USE-TS-FINAL-FIELD-GG`).
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

STATE_RUNNING = "running"
STATE_LATE_REG = "late_reg"
STATE_UNKNOWN = "unknown"

# tolerância do sinalizador avg×left vs entradas×stack (arredondamento do avg)
_AVG_COHERENCE_TOL = 0.001


def print_state(vision_json: Optional[dict]) -> str:
    """Estado do torneio no print, pela leitura `reg_open` da Vision."""
    ro = (vision_json or {}).get("reg_open")
    if ro is False:
        return STATE_RUNNING
    if ro is True:
        return STATE_LATE_REG
    return STATE_UNKNOWN


def _naive(dt):
    """Descarta tzinfo p/ ordenação (o log mistura naive Lisboa e tz-aware)."""
    if dt is None:
        return None
    return dt.replace(tzinfo=None) if getattr(dt, "tzinfo", None) else dt


def _sort_key(p: dict):
    dt = _naive(p.get("posted_at"))
    return (dt is not None, dt or datetime.min)


def compute_wn_total_chips(prints: list[dict]) -> Optional[dict]:
    """Aplica a regra a TODOS os prints de um torneio WN.

    `prints` = [{"posted_at": datetime|None, "vision_json": dict}, ...]
    (todos os prints `success` do torneio, incluindo o corrente).

    Devolve None se nenhum print tiver entradas+stack; senão:
    {chips, entrants, starting_stack, state, provisional, review (list[str]),
     chosen_posted_at, re_entries}.
    """
    all_sorted = sorted((p for p in prints or [] if p.get("vision_json")),
                        key=_sort_key)
    usable = [
        p for p in all_sorted
        if isinstance(p["vision_json"].get("entrants"), int)
        and p["vision_json"]["entrants"] > 0
        and isinstance(p["vision_json"].get("starting_stack"), (int, float))
        and p["vision_json"]["starting_stack"] > 0
    ]
    if not usable:
        return None

    running = [p for p in usable
               if print_state(p["vision_json"]) == STATE_RUNNING]
    chosen = running[-1] if running else usable[-1]
    cvj = chosen["vision_json"]
    state = print_state(cvj)
    entrants = cvj["entrants"]
    starting_stack = cvj["starting_stack"]
    review: list[str] = []

    # guarda «não-desce» — entradas são monotónicas no tempo
    max_entrants = max(p["vision_json"]["entrants"] for p in usable)
    if entrants < max_entrants:
        review.append(f"entrants_drop:{entrants}<{max_entrants}")
        entrants = max_entrants

    # sinalizador (nunca veto): avg×restantes acima de entradas×stack é impossível
    avg = cvj.get("average_stack")
    left = cvj.get("players_left")
    if (isinstance(avg, (int, float)) and avg > 0
            and isinstance(left, int) and left > 0
            and avg * left > entrants * starting_stack * (1 + _AVG_COHERENCE_TOL)):
        review.append("avg_incoherent")

    # stacks divergentes entre prints do mesmo torneio = misread nalgum deles
    stacks = {p["vision_json"]["starting_stack"] for p in usable}
    if len(stacks) > 1:
        review.append("stack_mismatch:" + ",".join(str(s) for s in sorted(stacks)))

    # re_entries: o valor mais tardio lido (info-only, pode vir de print sem entradas)
    re_entries = None
    for p in all_sorted:
        v = p["vision_json"].get("re_entries")
        if isinstance(v, int) and v >= 0:
            re_entries = v

    return {
        "chips": float(entrants * starting_stack),
        "entrants": entrants,
        "starting_stack": starting_stack,
        "state": state,
        "provisional": state != STATE_RUNNING,
        "review": review,
        "chosen_posted_at": _naive(chosen.get("posted_at")),
        "re_entries": re_entries,
    }
