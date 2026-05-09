"""Resolve tournament_number via tournaments_meta lookup (name + start_time).

FASE A COMMIT 2 — bot Discord chama isto apos Vision para descobrir qual
TM da BD corresponde a lobby uploaded. Sem caption obrigatorio.

COMMIT B (FASE A) — adiciona dois caminhos complementares ao resolver:
  (i) fallback a `hands` quando tournaments_meta devolve 0 rows (cobre
      G1 — Winamax/PS sem meta poblada por design).
  (ii) parametro keyword-only posted_at_hint que ancora janela
       [posted_at - 12h, posted_at - 30min] quando Vision nao le
       start_time (cobre G3 parcialmente).
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


def _parse_iso_utc(start_time_iso: Optional[str]) -> Optional[datetime]:
    """Parse ISO 8601 (com/sem 'Z' suffix) -> datetime tz-aware UTC ou None."""
    if not start_time_iso:
        return None
    try:
        st = datetime.fromisoformat(start_time_iso.replace("Z", "+00:00"))
    except ValueError:
        return None
    if st.tzinfo is None:
        st = st.replace(tzinfo=timezone.utc)
    return st


def _decide_window(
    start_time_iso: Optional[str],
    posted_at_hint: Optional[datetime],
    window_hours: float,
) -> Optional[tuple[datetime, datetime]]:
    """Aplica a precedencia de janela temporal.

    Ordem (estricta):
      1. start_time_iso valido -> [start - window_hours, start + window_hours].
      2. posted_at_hint presente -> [posted_at - 12h, posted_at - 30min].
         Justificacao: SS de lobby e tirada DURANTE o torneio. Logo o
         torneio comecou antes do post Discord. -30min evita falsos
         positivos com torneios que mal arrancaram; -12h cobre desde
         Hyper/Turbo (~1-3h ago) ate Slow MTT (~6-12h ago).
      3. nem start_time_iso nem posted_at_hint -> None (sem janela).
    """
    st = _parse_iso_utc(start_time_iso)
    if st:
        return (st - timedelta(hours=window_hours), st + timedelta(hours=window_hours))
    if posted_at_hint is not None:
        if posted_at_hint.tzinfo is None:
            posted_at_hint = posted_at_hint.replace(tzinfo=timezone.utc)
        return (
            posted_at_hint - timedelta(hours=12),
            posted_at_hint - timedelta(minutes=30),
        )
    return None


def resolve_tournament_number(
    site: str,
    tournament_name: str,
    start_time_iso: Optional[str],
    *,
    window_hours: float = 2.0,
    posted_at_hint: Optional[datetime] = None,
) -> tuple[Optional[str], list[dict]]:
    """Procura tournaments_meta por nome similar + janela temporal,
    com fallback a `hands` quando meta devolve 0 rows.

    Args:
        site: 'GGPoker' | 'PokerStars' | 'Winamax'.
        tournament_name: nome lido pela Vision.
        start_time_iso: timestamp ISO 8601 (UTC) lido pela Vision, ou None.
        window_hours: tolerancia +/- em horas para o ramo start_time (default 2h).
        posted_at_hint: timestamp tz-aware do post Discord. Usado como
            ancora quando start_time_iso e ausente/invalido.

    Returns:
        (tn, []) se 1 match unico (de meta OU de hands).
        (None, [candidates]) se 0 ou 2+ matches em meta + 0 ou 2+ em hands.
    """
    tokens = _tokenize_name(tournament_name)
    if not tokens:
        logger.warning("[tm_resolver] FAIL name_empty")
        return (None, [])

    patterns = [f"%{t}%" for t in tokens]
    window = _decide_window(start_time_iso, posted_at_hint, window_hours)

    if window is not None:
        lo, hi = window
        rows_meta = query(
            """SELECT tournament_number, tournament_name, start_time
                 FROM tournaments_meta
                WHERE site = %s
                  AND tournament_name ILIKE ALL (%s::text[])
                  AND start_time BETWEEN %s AND %s
                ORDER BY start_time ASC""",
            (site, patterns, lo, hi),
        )
    else:
        rows_meta = query(
            """SELECT tournament_number, tournament_name, start_time
                 FROM tournaments_meta
                WHERE site = %s
                  AND tournament_name ILIKE ALL (%s::text[])
                ORDER BY start_time DESC NULLS LAST
                LIMIT 5""",
            (site, patterns),
        )

    candidates_meta = [dict(r) for r in rows_meta]
    if candidates_meta:
        if len(candidates_meta) == 1:
            return (candidates_meta[0]["tournament_number"], [])
        return (None, candidates_meta)

    # Fallback: tournaments_meta vazio. Tenta `hands` com a mesma janela.
    # Cobre G1 (Winamax/PS sem meta) e G3 parcial via posted_at_hint.
    if window is not None:
        lo, hi = window
        rows_hands = query(
            """SELECT tournament_number,
                      tournament_name,
                      MIN(played_at) AS start_time
                 FROM hands
                WHERE site = %s
                  AND tournament_name ILIKE ALL (%s::text[])
                  AND tournament_number IS NOT NULL
                  AND played_at >= '2026-01-01'
                  AND study_state != 'mtt_archive'
                GROUP BY tournament_number, tournament_name
               HAVING MIN(played_at) BETWEEN %s AND %s
                ORDER BY MIN(played_at) ASC""",
            (site, patterns, lo, hi),
        )
    else:
        rows_hands = query(
            """SELECT tournament_number,
                      tournament_name,
                      MIN(played_at) AS start_time
                 FROM hands
                WHERE site = %s
                  AND tournament_name ILIKE ALL (%s::text[])
                  AND tournament_number IS NOT NULL
                  AND played_at >= '2026-01-01'
                  AND study_state != 'mtt_archive'
                GROUP BY tournament_number, tournament_name
                ORDER BY MIN(played_at) DESC NULLS LAST
                LIMIT 5""",
            (site, patterns),
        )

    candidates_hands = [dict(r) for r in rows_hands]
    if len(candidates_hands) == 1:
        return (candidates_hands[0]["tournament_number"], [])
    return (None, candidates_hands)
