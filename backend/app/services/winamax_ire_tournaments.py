"""Mapa por PREÇO (buy_in total) dos torneios Winamax PKO para o IRE-WN.
Análogo a app/hero_names.py: dados de referência hardcoded.

#IRE-WN passou de casar por NOME de torneio para casar por PREÇO (`hands.buy_in`):
o buy_in é 100% fiável na WN (219 mãos WN PKO 2026, 0 NULL; preços {50,100,125,
250}). O número nos nomes ("80K"/"120K"/"150K") é a GARANTIA, não o preço. Todos
os WN PKO (incluindo os "SPACE KO") são PKO 50/50, stack inicial 20000 — por isso
o preço chega e não há manutenção de nomes. Retroactivo: o IRE é calculado na
hora, não guardado.

WN não tem pipeline de tournament_summaries (parser GG-only), por isso o
starting_stack/entry/bounty NÃO vêm da BD — vêm deste mapa. Chave = buy_in TOTAL
(entry+bounty+rake) normalizado a 2 casas, como em `hands.buy_in`.

Acrescentar preço: nova entrada {starting_stack, buy_in_entry, buy_in_bounty}.
(buy_in_rake guardado só p/ referência — NÃO entra na fórmula: o KOP_fraction é
bounty/(entry+bounty), líquido de rake.)

Excepção futura por NOME (ex.: um deepstack com stack != 20000 ao mesmo preço):
ver proposta no fim do ficheiro — por agora o preço é o único caminho.
"""
from typing import Optional

# Stack inicial 20000 + bounty 50/50 em todos. Chave = buy_in TOTAL.
WINAMAX_IRE_BY_PRICE = {
    #  total   stack         entry          bounty           rake
    50.0:  {"starting_stack": 20000, "buy_in_entry": 20.0,  "buy_in_bounty": 25.0,  "buy_in_rake": 5.0},
    100.0: {"starting_stack": 20000, "buy_in_entry": 40.0,  "buy_in_bounty": 50.0,  "buy_in_rake": 10.0},
    125.0: {"starting_stack": 20000, "buy_in_entry": 51.5,  "buy_in_bounty": 62.5,  "buy_in_rake": 11.0},
    250.0: {"starting_stack": 20000, "buy_in_entry": 107.0, "buy_in_bounty": 125.0, "buy_in_rake": 18.0},
}


def lookup_winamax_ire_by_price(buy_in) -> Optional[dict]:
    """Config do torneio WN PKO por PREÇO (buy_in total, normalizado a 2 casas).
    None se o preço não estiver no mapa (IRE escondido — nunca inventar)."""
    if buy_in is None:
        return None
    try:
        key = round(float(buy_in), 2)
    except (TypeError, ValueError):
        return None
    return WINAMAX_IRE_BY_PRICE.get(key)
