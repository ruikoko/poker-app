"""Resolve tournament_number via cascata em 3 tiers.

FASE A COMMIT 2 — bot Discord chama isto apos Vision para descobrir qual
tournament_number na BD corresponde ao lobby uploaded. Sem caption obrigatorio.

COMMIT B (FASE A) — adiciona dois caminhos complementares ao resolver:
  (i) fallback a `hands` quando tournaments_meta devolve 0 rows (cobre
      G1 — Winamax/PS sem meta poblada por design).
  (ii) parametro keyword-only posted_at_hint que ancora janela
       [posted_at - 12h, posted_at - 30min] quando Vision nao le
       start_time (cobre G3 parcialmente).

COMMIT B2 (FASE B) — adiciona TIER 0 antes dos existentes:
  TIER 0  tournament_summaries  ← NOVO (autoritativo)
  TIER 1  tournaments_meta      ← existente
  TIER 2  hands fallback        ← existente

TS contem tournament_number literal (parseado do header do ficheiro
"Tournament #<tn>") — match deterministico para torneios ja terminados.
Janela temporal _decide_window aplica-se igual aos 3 tiers.

Cada tier emite logs INFO uniformes:
  [tournament_resolver] OK    tier=<tier> tn=<tn> site=<site>
  [tournament_resolver] AMBIG tier=<tier> n=<N>   site=<site>
"""
from __future__ import annotations
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from app.db import query

logger = logging.getLogger("tournament_resolver")


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


def _query_summaries(site, patterns, window):
    """TIER 0 — tournament_summaries (autoritativo)."""
    if window is not None:
        lo, hi = window
        return query(
            """SELECT tournament_number, tournament_name, start_time
                 FROM tournament_summaries
                WHERE site = %s
                  AND tournament_name ILIKE ALL (%s::text[])
                  AND start_time BETWEEN %s AND %s
                ORDER BY start_time ASC""",
            (site, patterns, lo, hi),
        )
    return query(
        """SELECT tournament_number, tournament_name, start_time
             FROM tournament_summaries
            WHERE site = %s
              AND tournament_name ILIKE ALL (%s::text[])
            ORDER BY start_time DESC NULLS LAST
            LIMIT 5""",
        (site, patterns),
    )


def _query_meta(site, patterns, window):
    """TIER 1 — tournaments_meta."""
    if window is not None:
        lo, hi = window
        return query(
            """SELECT tournament_number, tournament_name, start_time
                 FROM tournaments_meta
                WHERE site = %s
                  AND tournament_name ILIKE ALL (%s::text[])
                  AND start_time BETWEEN %s AND %s
                ORDER BY start_time ASC""",
            (site, patterns, lo, hi),
        )
    return query(
        """SELECT tournament_number, tournament_name, start_time
             FROM tournaments_meta
            WHERE site = %s
              AND tournament_name ILIKE ALL (%s::text[])
            ORDER BY start_time DESC NULLS LAST
            LIMIT 5""",
        (site, patterns),
    )


def _query_hands(site, patterns, window):
    """TIER 2 — hands fallback. GROUP BY (tn, name), MIN(played_at) aproxima
    start_time. Guard rails: tn IS NOT NULL, played_at >= '2026-01-01',
    study_state != 'mtt_archive'."""
    if window is not None:
        lo, hi = window
        return query(
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
    return query(
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


def resolve_tournament_number(
    site: str,
    tournament_name: str,
    start_time_iso: Optional[str],
    *,
    window_hours: float = 2.0,
    posted_at_hint: Optional[datetime] = None,
) -> tuple[Optional[str], list[dict]]:
    """Cascata em 3 tiers: tournament_summaries -> tournaments_meta -> hands.

    Args:
        site: 'GGPoker' | 'PokerStars' | 'Winamax'.
        tournament_name: nome lido pela Vision.
        start_time_iso: timestamp ISO 8601 (UTC) lido pela Vision, ou None.
        window_hours: tolerancia +/- em horas para o ramo start_time (default 2h).
        posted_at_hint: timestamp tz-aware do post Discord. Usado como
            ancora quando start_time_iso e ausente/invalido.

    Returns:
        (tn, []) se 1 match unico em qualquer tier (paragem imediata).
        (None, [candidates]) se 2+ matches no 1o tier nao-vazio (curto-circuita
            tiers seguintes). (None, []) se todos os tiers vazios.
    """
    tokens = _tokenize_name(tournament_name)
    if not tokens:
        logger.warning("[tournament_resolver] FAIL name_empty")
        return (None, [])

    patterns = [f"%{t}%" for t in tokens]
    window = _decide_window(start_time_iso, posted_at_hint, window_hours)

    # TIER 0 — tournament_summaries (autoritativo)
    candidates_summaries = [dict(r) for r in _query_summaries(site, patterns, window)]
    if candidates_summaries:
        if len(candidates_summaries) == 1:
            tn = candidates_summaries[0]["tournament_number"]
            logger.info(
                f"[tournament_resolver] OK tier=summaries tn={tn} site={site}"
            )
            return (tn, [])
        logger.info(
            f"[tournament_resolver] AMBIG tier=summaries "
            f"n={len(candidates_summaries)} site={site}"
        )
        return (None, candidates_summaries)

    # TIER 1 — tournaments_meta
    candidates_meta = [dict(r) for r in _query_meta(site, patterns, window)]
    if candidates_meta:
        if len(candidates_meta) == 1:
            tn = candidates_meta[0]["tournament_number"]
            logger.info(
                f"[tournament_resolver] OK tier=meta tn={tn} site={site}"
            )
            return (tn, [])
        logger.info(
            f"[tournament_resolver] AMBIG tier=meta "
            f"n={len(candidates_meta)} site={site}"
        )
        return (None, candidates_meta)

    # TIER 2 — hands fallback
    candidates_hands = [dict(r) for r in _query_hands(site, patterns, window)]
    if len(candidates_hands) == 1:
        tn = candidates_hands[0]["tournament_number"]
        logger.info(
            f"[tournament_resolver] OK tier=hands tn={tn} site={site}"
        )
        return (tn, [])
    if candidates_hands:
        logger.info(
            f"[tournament_resolver] AMBIG tier=hands "
            f"n={len(candidates_hands)} site={site}"
        )
    return (None, candidates_hands)
