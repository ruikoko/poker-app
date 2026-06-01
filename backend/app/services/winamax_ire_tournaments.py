"""Tabela curada (interna, sem UI) dos torneios Winamax PKO para o IRE-WN.
Análoga a app/hero_names.py: dados de referência hardcoded.

WN não tem pipeline de tournament_summaries (parser GG-only), por isso o
starting_stack/entry/bounty NÃO vêm da BD — vêm desta tabela. Chave =
tournament_name EXACTO em uppercase (como aparece em hands.tournament_name).
Stack inicial 20000 em todos; bounty = metade do buy-in; todos PKO.

Acrescentar torneio: nova linha {starting_stack, buy_in_entry, buy_in_bounty}.
(buy_in_rake guardado só p/ referência — NÃO entra na fórmula: o KOP_fraction é
bounty/(entry+bounty), líquido de rake.)
"""
from typing import Optional

WINAMAX_IRE_TOURNAMENTS = {
    # nome            stack  entry bounty rake
    "HORIZON":        {"starting_stack": 20000, "buy_in_entry": 20,  "buy_in_bounty": 25,  "buy_in_rake": 5},
    "ZENITH":         {"starting_stack": 20000, "buy_in_entry": 40,  "buy_in_bounty": 50,  "buy_in_rake": 10},
    "ODYSSEY":        {"starting_stack": 20000, "buy_in_entry": 20,  "buy_in_bounty": 25,  "buy_in_rake": 5},
    "GRAVITY":        {"starting_stack": 20000, "buy_in_entry": 107, "buy_in_bounty": 125, "buy_in_rake": 18},
    "EXPLORER":       {"starting_stack": 20000, "buy_in_entry": 20,  "buy_in_bounty": 25,  "buy_in_rake": 5},
    "INTERSTELLAR":   {"starting_stack": 20000, "buy_in_entry": 40,  "buy_in_bounty": 50,  "buy_in_rake": 10},
    "PRIME TIME":     {"starting_stack": 20000, "buy_in_entry": 20,  "buy_in_bounty": 25,  "buy_in_rake": 5},
    "HIGHROLLER":     {"starting_stack": 20000, "buy_in_entry": 107, "buy_in_bounty": 125, "buy_in_rake": 18},
    "BATTLE ROYALE":  {"starting_stack": 20000, "buy_in_entry": 40,  "buy_in_bounty": 50,  "buy_in_rake": 10},
    "RUSH HOUR":      {"starting_stack": 20000, "buy_in_entry": 20,  "buy_in_bounty": 25,  "buy_in_rake": 5},
}


def lookup_winamax_ire_tournament(tournament_name: Optional[str]) -> Optional[dict]:
    """Config do torneio WN curado por nome exacto (uppercase). None se fora da tabela."""
    if not tournament_name:
        return None
    return WINAMAX_IRE_TOURNAMENTS.get(tournament_name.strip().upper())
