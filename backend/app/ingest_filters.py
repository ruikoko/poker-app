"""
Barreiras de ingest: rejeitar dados anteriores a 2026.

PRE_2026_CUTOFF = datetime fixo (2026-01-01 UTC). Rui só estuda mãos de
2026 em diante; histórico anterior é ruído. Filter aplicado em todos os
pipelines de ingest (import HH, HM3, screenshot, Discord).

is_pre_2026(dt) → True se dt < 2026-01-01 UTC, False caso contrário (incl.
None, parse-fail, datas futuras). NULL aceito porque alguns paths legítimos
têm played_at desconhecido (ex: placeholder SS upload sem filename com data).
"""
from datetime import datetime, timezone
import logging

logger = logging.getLogger("ingest_filters")

PRE_2026_CUTOFF = datetime(2026, 1, 1, tzinfo=timezone.utc)


def is_pre_2026(dt) -> bool:
    """True se dt for anterior a 2026-01-01 UTC. False para None ou parse-fail."""
    if dt is None:
        return False
    if isinstance(dt, str):
        try:
            dt = datetime.fromisoformat(dt.replace('Z', '+00:00'))
        except (ValueError, TypeError):
            return False
    if not isinstance(dt, datetime):
        return False
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt < PRE_2026_CUTOFF
