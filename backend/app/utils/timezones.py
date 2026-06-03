"""Conversão de hora-local-de-Lisboa → UTC (#GG-PLAYED-AT-LOCAL-NOT-UTC).

A GGPoker e a PokerStars gravam a hora da HH em hora LOCAL (Lisboa/WET-WEST),
sem normalizar para UTC — GG sem marcador de fuso; PS com a 1ª timestamp em WET
(seguida do bracket ET). O Rui joga sempre de Portugal. Normalizamos para UTC de
forma DST-aware pela data da própria mão — NUNCA offset fixo, NUNCA a data de
"agora". Winamax e WPN trazem a hora já em UTC explícito (não passam por aqui).
Storage = UTC; a UI reconverte UTC→Lisboa para mostrar.
"""
from datetime import datetime
from zoneinfo import ZoneInfo

_LISBON_TZ = ZoneInfo("Europe/Lisbon")
_UTC_TZ = ZoneInfo("UTC")


def lisbon_local_to_utc(naive_local: datetime) -> datetime:
    """Interpreta um datetime naive (hora local de Lisboa lida da HH) e devolve o
    instante equivalente em UTC (tz-aware), DST-aware pela data da própria mão.
    Uma mão de Verão (WEST) recua 1h; uma de Inverno (WET) fica igual."""
    return naive_local.replace(tzinfo=_LISBON_TZ).astimezone(_UTC_TZ)
