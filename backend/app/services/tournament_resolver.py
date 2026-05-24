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
import re
from datetime import datetime, timedelta, timezone
from typing import Optional

from app.db import query

logger = logging.getLogger("tournament_resolver")

# pt39 — janela do TIER 0 ancorada no posted_at/captured_at. A SS é tirada
# durante o torneio, logo a instância certa já arrancou; 24h cobre slow MTT que
# atravessa a meia-noite. Ver #RESOLVER-TIER0-STRICT-EQUALITY.
_TIER0_WINDOW_HOURS = 24


def _currency_for_site(site: Optional[str]) -> Optional[str]:
    """Moeda canónica por sala (para o filtro buy_in_currency do TIER 0)."""
    if site in ("GGPoker", "PokerStars", "WPN"):
        return "USD"
    if site == "Winamax":
        return "EUR"
    return None


# pt39 (#TABLE-SS-RESOLVER-COLLISION) — sufixo de nº de mesa do cliente Winamax
# ("ZENITH #005"), lido pela Vision na SS de mesa, que NÃO existe em
# hands.tournament_name (lá o nome é bare). Só apara um '#NNN' TRAILING.
_TABLE_SUFFIX_RE = re.compile(r"\s*#\d+\s*$")


def clean_tournament_name(name: Optional[str]) -> Optional[str]:
    """Remove o sufixo '#NNN' trailing (nº de mesa do cliente) antes de tokenizar.

    Só apara um ``#\\d+`` ancorado no FIM. Preserva '#NNN' em prefixo
    (W SERIES Winamax, ex.: '#220 - W SERIES ...' — o nº é o discriminador do
    evento) e hashtags não-numéricas (ex.: 'Daily $100,000 #ThanksGG Flipout').
    ``$80`` não é tocado (é ``$`` não ``#``). None / '' passam intactos.
    """
    if not name:
        return name
    return _TABLE_SUFFIX_RE.sub("", name).strip()


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


def name_tokens_subset(short_name: Optional[str], full_name: Optional[str]) -> bool:
    """pt39 (#TABLE-SS-RESOLVER-COLLISION parte 2) — True sse todos os tokens do
    ``short_name`` (após clean_tournament_name) estão, como substring, no
    ``full_name`` (cleaned + lowercased). Mesma semântica do ILIKE ALL do
    resolver, tolerante a palavras extra do lado longo.

    Usado para validar o nome no fast-path single_tn de
    ``table_ss._resolve_match`` antes de aceitar a mão. Conservador:
    ``short_name`` vazio/None / só-sufixo → False (o caller decide a leniência
    quando não há nome lido).
    """
    toks = _tokenize_name(clean_tournament_name(short_name))
    if not toks:
        return False
    full = (clean_tournament_name(full_name) or "").lower()
    return all(tok in full for tok in toks)


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


def _query_summaries(site, patterns, buy_in=None, buy_in_currency=None,
                     prize_pool=None, total_players=None,
                     anchor=None, window_hours=_TIER0_WINDOW_HOURS):
    """TIER 0 — tournament_summaries (autoritativo).

    pt39 (#RESOLVER-TIER0-STRICT-EQUALITY): TIER 0 suporta DOIS conjuntos de
    discriminadores, todos NULL-permissivos, conforme o consumidor:

      - buy_in (igualdade exacta em buy_in_total) + buy_in_currency (estrito) +
        janela em start_time ANCORADA no `anchor` (posted_at/captured_at):
        usado pelos pipelines LIVE (lobby, table-ss). A SS é tirada durante o
        torneio → selecciona a instância EM CURSO = maior start_time <= anchor
        dentro de [anchor - window_hours, anchor] (resolve 2x/dia, ~18% TS GG).

      - prize_pool + total_players (igualdade exacta): usado pelo pipeline
        PÓS-JOGO (tournament_results backoffice), cujos valores são FINAIS e
        batem com o TS — único discriminador entre instâncias em dias
        diferentes quando não há âncora.

    Sem anchor → sem janela, LIMIT 5 (deixa a ambiguidade subir). NB: ancorar
    em start_time NÃO quebra backfill — start_time é o instante real do evento,
    independente de quando o TS foi importado.

    NULL no parametro = sem filtro. Valor = filtro estricto (=).
    """
    if anchor is not None:
        return query(
            """SELECT tournament_number, tournament_name, start_time
                 FROM tournament_summaries
                WHERE site = %s
                  AND tournament_name ILIKE ALL (%s::text[])
                  AND (%s::numeric IS NULL OR buy_in_total = %s::numeric)
                  AND (%s::text IS NULL OR buy_in_currency = %s)
                  AND (%s::numeric IS NULL OR prize_pool = %s::numeric)
                  AND (%s::integer IS NULL OR total_players = %s::integer)
                  AND start_time <= %s
                  AND start_time >= %s - make_interval(hours => %s)
                ORDER BY start_time DESC
                LIMIT 1""",
            (site, patterns, buy_in, buy_in, buy_in_currency, buy_in_currency,
             prize_pool, prize_pool, total_players, total_players,
             anchor, anchor, window_hours),
        )
    return query(
        """SELECT tournament_number, tournament_name, start_time
             FROM tournament_summaries
            WHERE site = %s
              AND tournament_name ILIKE ALL (%s::text[])
              AND (%s::numeric IS NULL OR buy_in_total = %s::numeric)
              AND (%s::text IS NULL OR buy_in_currency = %s)
              AND (%s::numeric IS NULL OR prize_pool = %s::numeric)
              AND (%s::integer IS NULL OR total_players = %s::integer)
            ORDER BY start_time DESC NULLS LAST
            LIMIT 5""",
        (site, patterns, buy_in, buy_in, buy_in_currency, buy_in_currency,
         prize_pool, prize_pool, total_players, total_players),
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
    buy_in: Optional[float] = None,
    buy_in_currency: Optional[str] = None,
    prize_pool: Optional[float] = None,
    total_players: Optional[int] = None,
) -> tuple[Optional[str], list[dict]]:
    """Cascata em 3 tiers: tournament_summaries -> tournaments_meta -> hands.

    Args:
        site: 'GGPoker' | 'PokerStars' | 'Winamax'.
        tournament_name: nome lido pela Vision.
        start_time_iso: timestamp ISO 8601 (UTC) lido pela Vision, ou None.
        window_hours: tolerancia +/- em horas para o ramo start_time (default 2h).
        posted_at_hint: timestamp tz-aware do post Discord. Usado como
            ancora para tiers 1+2 quando start_time_iso e ausente/invalido.
        buy_in: pt39 — discriminador do TIER 0 (igualdade exacta em
            buy_in_total, NULL-permissivo). Total stake+fee+bounty. Lobby:
            vj['buy_in']. None = sem filtro.
        buy_in_currency: moeda do buy_in ('USD'/'EUR'). None → derivada do
            site. Só aplicada quando buy_in não-None.
        prize_pool: discriminador TIER 0 do pipeline PÓS-JOGO (backoffice
            results), igualdade exacta NULL-permissiva. Valores finais que
            batem com o TS. None = sem filtro.
        total_players: idem prize_pool (entrants finais do backoffice).

    Returns:
        (tn, []) se 1 match unico em qualquer tier (paragem imediata).
        (None, [candidates]) se 2+ matches no 1o tier nao-vazio (curto-circuita
            tiers seguintes). (None, []) se todos os tiers vazios.
    """
    tokens = _tokenize_name(clean_tournament_name(tournament_name))
    if not tokens:
        logger.warning("[tournament_resolver] FAIL name_empty")
        return (None, [])

    patterns = [f"%{t}%" for t in tokens]
    window = _decide_window(start_time_iso, posted_at_hint, window_hours)

    # TIER 0 — tournament_summaries (autoritativo). pt39: nome + buy_in +
    # janela start_time ancorada no posted_at_hint (instância em curso).
    anchor = posted_at_hint
    if anchor is not None and anchor.tzinfo is None:
        anchor = anchor.replace(tzinfo=timezone.utc)
    ts_currency = (
        (buy_in_currency or _currency_for_site(site)) if buy_in is not None else None
    )
    candidates_summaries = [dict(r) for r in _query_summaries(
        site, patterns, buy_in=buy_in, buy_in_currency=ts_currency,
        prize_pool=prize_pool, total_players=total_players, anchor=anchor,
    )]
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
