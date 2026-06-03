"""Convenção de fuso da app: o ponto de encontro de TODAS as horas-de-evento é
hora de LISBOA (Europe/Lisbon), gravada como datetime **NAIVE** (coluna
`timestamp WITHOUT TIME ZONE`) = wall-clock de Lisboa. Nenhuma conversão na
leitura / matching / display — o que se grava é o que se lê.

Decisão (pt51, Rui): a referência passou de UTC para Lisboa. Vantagem dura: as
mãos locais (GG/PokerStars) gravam-se VERBATIM, sem qualquer aritmética de fuso
→ a ambiguidade da hora de Inverno (fall-back) deixa de existir por não haver
conversão. A única conversão DST que sobra é UTC→Lisboa (Winamax/WPN/Discord),
que é sempre bem definida (UTC→local nunca é ambíguo).

Por fonte:
  - GG / PokerStars : a HH já vem em Lisboa → `lisbon_naive_verbatim` (identidade).
  - Winamax / WPN   : a HH vem em UTC      → `utc_to_lisbon_naive`.
  - Discord posted_at: vem em UTC          → `utc_to_lisbon_naive`.
  - table-SS captured_at: filename já é Lisboa → naive verbatim (no vision helper).
"""
from datetime import datetime
from zoneinfo import ZoneInfo

_LISBON = ZoneInfo("Europe/Lisbon")
_UTC = ZoneInfo("UTC")


def lisbon_naive_verbatim(dt: datetime) -> datetime:
    """GG/PS/table-SS: o valor já está em hora de Lisboa → devolve-o NAIVE tal e
    qual (descarta tzinfo se existir; NUNCA faz aritmética de fuso). É o que
    elimina a ambiguidade de Inverno nas mãos locais."""
    return dt.replace(tzinfo=None)


def utc_to_lisbon_naive(dt_utc: datetime) -> datetime:
    """Winamax/WPN/Discord: instante em UTC (aware, ou naive assumido UTC) →
    wall-clock NAIVE de Lisboa, DST-aware. UTC→local é sempre não-ambíguo."""
    if dt_utc.tzinfo is None:
        dt_utc = dt_utc.replace(tzinfo=_UTC)
    return dt_utc.astimezone(_LISBON).replace(tzinfo=None)
