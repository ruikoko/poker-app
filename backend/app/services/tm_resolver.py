"""Resolve tournament_number via tournaments_meta lookup (name + start_time).

FASE A COMMIT 2 — bot Discord chama isto apos Vision para descobrir qual
TM da BD corresponde a lobby uploaded. Sem caption obrigatorio.
"""
from __future__ import annotations
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from app.db import query

logger = logging.getLogger("tm_resolver")


def _tokenize_name(name: Optional[str]) -> list[str]:
    """Quebra um nome de torneio em tokens prontos para ILIKE match.

    Split por whitespace, lowercase, strip de pontuação leve trailing/leading
    (",.;:!?"). Preserva ``$`` e ``-`` que carregam significado (ex: "$108",
    "WSOP-SC"). Tokens vazios após strip são descartados. ``None`` / ``""`` /
    só whitespace / só pontuação devolvem lista vazia.
    """
    if not name:
        return []
    tokens: list[str] = []
    for raw in name.split():
        t = raw.strip(",.;:!?").lower()
        if t:
            tokens.append(t)
    return tokens


def resolve_tournament_number(
    site: str,
    tournament_name: str,
    start_time_iso: Optional[str],
    *,
    window_hours: float = 2.0,
) -> tuple[Optional[str], list[dict]]:
    """Procura tournaments_meta por nome similar + janela temporal.

    Args:
        site: 'GGPoker' | 'PokerStars' | 'Winamax'.
        tournament_name: nome lido pela Vision.
        start_time_iso: timestamp ISO 8601 (UTC) lido pela Vision, ou None.
        window_hours: tolerancia +/- em horas (default 2h).

    Returns:
        (tn, []) se 1 match unico.
        (None, [candidates]) se 0 ou 2+ matches (caller pede clarificacao).
    """
    tokens = _tokenize_name(tournament_name)
    if not tokens:
        logger.warning("[tm_resolver] FAIL name_empty")
        return (None, [])

    patterns = [f"%{t}%" for t in tokens]

    st = None
    if start_time_iso:
        try:
            st = datetime.fromisoformat(start_time_iso.replace("Z", "+00:00"))
            if st.tzinfo is None:
                st = st.replace(tzinfo=timezone.utc)
        except ValueError:
            st = None

    if st:
        lo = st - timedelta(hours=window_hours)
        hi = st + timedelta(hours=window_hours)
        rows = query(
            """SELECT tournament_number, tournament_name, start_time
                 FROM tournaments_meta
                WHERE site = %s
                  AND tournament_name ILIKE ALL (%s::text[])
                  AND start_time BETWEEN %s AND %s
                ORDER BY start_time ASC""",
            (site, patterns, lo, hi),
        )
    else:
        rows = query(
            """SELECT tournament_number, tournament_name, start_time
                 FROM tournaments_meta
                WHERE site = %s
                  AND tournament_name ILIKE ALL (%s::text[])
                ORDER BY start_time DESC NULLS LAST
                LIMIT 5""",
            (site, patterns),
        )

    candidates = [dict(r) for r in rows]
    if len(candidates) == 1:
        return (candidates[0]["tournament_number"], [])
    return (None, candidates)
