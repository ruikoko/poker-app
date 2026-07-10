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

# pt41 Track A (#LOBBY-ANCHOR-PRESTART-REGRESSION) — janelas source-aware.
# 'during_play' (table-ss, default): SS tirada durante o jogo → start é PASSADO
#   → janela [anchor−24h, anchor] + "closest" (≡ DESC LIMIT 1 anterior).
# 'prestart' (lobby): SS tirada na inscrição → start é FUTURO próximo (~+30min)
#   → janela [anchor−12h, anchor+2h] + "closest" (mata o mis-resolve do dia
#   anterior, em que um instance já-começado dentro das 24h era apanhado).
_PRESTART_BACK_HOURS = 12
_PRESTART_FWD_HOURS = 2
# #META-START-TIME (item 9) — tolerância late-reg SÓ para GG, no INTERVALO SEM TS.
# tournaments_meta.start_time (TIER 1) e MIN(played_at) (TIER 2) são a 1ª MÃO, não o
# arranque agendado; num lobby GG (prestart) a 1ª mão entra depois do post por
# (agendado−post)+late-reg — pode passar de 2h em campos fundos. As não-GG não sofrem
# (o lobby traz start_time_iso da Vision → ramo-1, ancora no arranque real). +6h cobre
# o late-reg profundo e fica muito aquém do 2×/dia GG (~12h): um irmão só-por-nome cai
# fora, ou (se <6h) gera AMBIG→None honesto (nunca mis-resolve). TIER 0/TS intocado
# (usa `anchor` próprio); só toca o window dos TIER 1/2, i.e. o intervalo sem TS.
_GG_PRESTART_FWD_HOURS = 6
# Ramo-1 do _decide_window (start-centered, TIER 1/2): forward alargado de 2h
# para 4h — a 1ª hand importada entra ~1-2h depois do start (late-reg/deep MTT;
# empírico pt41), e ±2h era marginal.
_RAMO1_FWD_HOURS = 4

# ── RAIZ 2 (11 Jul) — desambiguação de EDIÇÕES do mesmo torneio no mesmo dia ───
# GG corre o mesmo torneio 2×/dia (ex.: Daily Hyper $60 às 17:45 E 20:45). O
# TIER 0 escolhia a edição "mais próxima" às cegas (LIMIT 1) → cola o lobby na
# edição errada → payout errado no ICM. A Raiz 2 exige PROVA para colar; sem
# prova que separe as edições → QUARENTENA (não cola). Ver docs Raiz 2.
#
# GG-ONLY: a Winamax identifica o torneio sem ambiguidade na própria HH e não
# repete edições no mesmo dia (decisão do Rui, 11 Jul) → fora do âmbito.
#
# PROVAS DURAS (podem decidir uma cola), por ordem:
#   H1  nome EXACTO ("Speed Racer $108" ≠ "Speed Racer Europe $108").
#   H2  impossibilidade: entrants do print > campo FINAL da edição (+tol OCR) →
#       impossível (mais inscritos do que o total final) → exclui. UNIDIRECIONAL:
#       entrants < campo final é NORMAL (print antes de fechar inscrições) e
#       NUNCA é prova (ressalva do Rui).
#   H3  não-arrancada-com-eliminações: a edição ainda não tinha começado à hora
#       do print (anchor < start) MAS o print mostra eliminações (players_left <
#       entrants) → impossível (um torneio por arrancar não tem gente eliminada).
#   H4  janela de mãos: anchor tem de cair em [1ª mão − REG_BACK, última mão +
#       POST_SLACK] (mãos reais do Hero nessa edição; start do TS se não houver).
# Se as provas duras deixarem 2+ e só o "entrants mais próximo do campo" as
# separasse → QUARENTENA (o desempate por proximidade de entrants NÃO cola só
# por si — ressalva do Rui).
_EDITION_REG_BACK_MIN = 45      # print pré-arranque observado até −26min → 45 folga
_EDITION_POST_SLACK_MIN = 120   # o Rui vê o lobby muito depois de bustar (obs. >60min)
_EDITION_NO_HANDS_DUR_MIN = 360  # sem mãos do Hero: assume duração generosa p/ a janela
_EDITION_ENTRANTS_TOL = 0.05    # folga de OCR na régua da impossibilidade (H2)


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


# pt54 (#WN-TOURNAMENT-NAME-NORMALIZE) — nome canónico Winamax = só o NOME.
# '#NNN' é o nº de MESA (varia por mesa dentro do MESMO torneio — provado:
# "EXPLORER 150K #076" e "#235" têm o mesmo ID 1104093788). '(NNNNNNN)' é o ID
# do torneio. Removem-se ambos; garantias sem '#' ("150K", "80K") preservam-se.
_WN_ID_PARENS_RE = re.compile(r"\(\s*(\d+)\s*\)")
_WN_TABLE_NUM_RE = re.compile(r"#\s*\d+")


def clean_winamax_tournament_name(
    name: Optional[str],
) -> tuple[Optional[str], Optional[str]]:
    """Winamax: devolve (nome_limpo, tournament_id).

    Remove '#NNN' (nº de mesa) e '(NNNNNNN)' (ID do torneio) de qualquer posição.
    PRESERVA garantias sem '#' ('150K', '80K') e o resto do nome. O ID extraído
    (ou None) é para PRESERVAR em ``tournament_number`` ANTES de sair do nome —
    nunca se perde. None / '' → (name, None).

    Ex.: 'EXPLORER 150K #076 (1104093788)' → ('EXPLORER 150K', '1104093788')
         'GALACTICA #034'                  → ('GALACTICA', None)
         'GRAVITY 80K #0006'               → ('GRAVITY 80K', None)
         'MAIN EVENT SPACE KO 120K'        → ('MAIN EVENT SPACE KO 120K', None)
    """
    if not name:
        return name, None
    m = _WN_ID_PARENS_RE.search(name)
    tid = m.group(1) if m else None
    cleaned = _WN_ID_PARENS_RE.sub(" ", name)
    cleaned = _WN_TABLE_NUM_RE.sub(" ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned, tid


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

    pt58 — tolerância a TRUNCAÇÃO: o cliente GG corta títulos longos na SS de
    mesa (ex.: '… [Mystery Bo...]'). Se o ÚLTIMO token vier cortado (contém
    '...'), trata-se como PREFIXO: os tokens RESTANTES têm de bater EXACTAMENTE
    (substring) e o prefixo (>=2 chars) como substring. Nunca se relaxam os
    restantes → a unicidade (1 só candidato) é garantida pelo caller, sem falsos
    matches. (Um corte sem parênteses '… Bo...' já fica 'bo' no tokenizer e bate
    pela via normal — esta é só para o caso com bracket onde o '...' sobrevive.)
    """
    toks = _tokenize_name(clean_tournament_name(short_name))
    if not toks:
        return False
    full = (clean_tournament_name(full_name) or "").lower()
    last = toks[-1]
    if "..." in last:
        if not all(t in full for t in toks[:-1]):
            return False
        prefix = last.split("...", 1)[0].strip("[]()")
        return len(prefix) < 2 or prefix in full
    return all(tok in full for tok in toks)


def _parse_iso_naive(start_time_iso: Optional[str]) -> Optional[datetime]:
    """Parse ISO 8601 -> datetime NAIVE em hora de Lisboa, ou None (convenção
    pt51). A referência da app é Lisboa naive; qualquer tzinfo no input é
    descartado (assume-se que já vem em Lisboa, como `tournament_summaries.
    start_time` e `hands.played_at`)."""
    if not start_time_iso:
        return None
    try:
        st = datetime.fromisoformat(start_time_iso.replace("Z", "+00:00"))
    except ValueError:
        return None
    return st.replace(tzinfo=None)


def _edition_hand_window(site: str, tn: str):
    """(1ª mão, última mão) do Hero nessa edição (Lisboa naive), ou (None, None).
    É a "janela de mãos do torneio" da prova H4 — só temos as mãos do Hero, mas
    marcam quando ele esteve NAQUELA edição."""
    rows = query(
        "SELECT MIN(played_at) AS mn, MAX(played_at) AS mx FROM hands "
        "WHERE site = %s AND tournament_number = %s",
        (site, tn),
    )
    if not rows:
        return None, None
    return rows[0].get("mn"), rows[0].get("mx")


def _disambiguate_editions(site, candidates, anchor_lisbon, entrants,
                           players_left, lobby_name=None):
    """RAIZ 2 — escolhe a edição certa por PROVA DURA, ou devolve None (quarentena).

    candidates: list de dicts com tournament_number, tournament_name, start_time,
      total_players (start_time em Lisboa naive, como o TS).
    anchor_lisbon: hora do print em Lisboa naive (posted_at convertido UTC→Lisboa).
    entrants / players_left: do vision_json do lobby (int|None).
    lobby_name: nome lido pela Vision (para a prova H1 nome-exacto).

    Devolve (tournament_number, decision, survivors). tournament_number None =
    quarentena. `decision` é uma etiqueta curta p/ auditoria/painel.
    """
    if anchor_lisbon is not None and getattr(anchor_lisbon, "tzinfo", None) is not None:
        anchor_lisbon = anchor_lisbon.replace(tzinfo=None)

    ent = entrants if isinstance(entrants, (int, float)) and entrants > 0 else None
    pl = players_left if isinstance(players_left, (int, float)) and players_left > 0 else None
    # eliminações provadas no print → só possível numa edição JÁ arrancada (H3).
    has_eliminations = bool(ent and pl and pl < ent)

    # H1 — nome EXACTO. Se algum candidato casa exactamente o nome (cleaned,
    # lowercase) do lobby, restringe a esses (mata "…Europe…" que o match por
    # tokens deixa entrar como superset).
    ln = (clean_tournament_name(lobby_name) or "").strip().lower()
    exact = [c for c in candidates
             if ln and (clean_tournament_name(c.get("tournament_name")) or "").strip().lower() == ln]
    pool = exact if exact else list(candidates)

    survivors = []
    for c in pool:
        tn = c["tournament_number"]
        start = c.get("start_time")
        total = c.get("total_players")
        # H2 — impossibilidade (unidirecional): entrants > campo final → exclui.
        if ent is not None and total and ent > total * (1 + _EDITION_ENTRANTS_TOL):
            continue
        # H3 — não-arrancada mas com eliminações → impossível.
        if start is not None and anchor_lisbon is not None and anchor_lisbon < start \
           and has_eliminations:
            continue
        # H4 — janela de mãos.
        fh, lh = _edition_hand_window(site, tn)
        base_lo = fh if fh is not None else start
        base_hi = lh if lh is not None else (
            (start + timedelta(minutes=_EDITION_NO_HANDS_DUR_MIN)) if start else None)
        if base_lo is None or base_hi is None or anchor_lisbon is None:
            # sem sinal temporal utilizável — não exclui nem prova; deixa passar
            # p/ os outros crivos decidirem (raro em GG, que tem start do TS).
            survivors.append({**c, "_fh": fh, "_lh": lh})
            continue
        lo = base_lo - timedelta(minutes=_EDITION_REG_BACK_MIN)
        hi = base_hi + timedelta(minutes=_EDITION_POST_SLACK_MIN)
        if lo <= anchor_lisbon <= hi:
            survivors.append({**c, "_fh": fh, "_lh": lh})

    if len(survivors) == 1:
        return survivors[0]["tournament_number"], "hard_unique", survivors
    if not survivors:
        return None, "no_edition_consistent", survivors

    # 2+ sobrevivem às provas duras de exclusão. Última prova DURA: containment
    # estrito na janela de mãos (o Hero estava DEMONSTRAVELMENTE a jogar essa
    # edição à hora do print). Se exactamente 1 → cola; senão → quarentena
    # (só o desempate por proximidade de entrants sobraria, e esse NÃO cola).
    contained = [
        c for c in survivors
        if c.get("_fh") is not None and c.get("_lh") is not None
        and c["_fh"] <= anchor_lisbon <= c["_lh"]
    ]
    if len(contained) == 1:
        return contained[0]["tournament_number"], "hand_window_contained", survivors
    return None, "ambiguous_editions", survivors


def _decide_window(
    start_time_iso: Optional[str],
    posted_at_hint: Optional[datetime],
    window_hours: float,
    anchor_mode: str = "during_play",
    site: Optional[str] = None,
) -> Optional[tuple[datetime, datetime]]:
    """Aplica a precedencia de janela temporal (TIER 1/2).

    Ordem (estricta):
      1. start_time_iso valido (ramo-1) -> [start - window_hours, start + 4h].
         pt41: forward alargado de 2h para 4h — a 1ª hand importada entra
         ~1-2h depois do start (late-reg/deep MTT); ±2h era marginal.
      2. posted_at_hint presente (ramo-2), source-aware (pt41):
         - prestart (lobby): [posted - 12h, posted + 2h]. A SS é tirada na
           inscricao → o torneio comeca DEPOIS do post.
         - during_play (table-ss, default): [posted - 12h, posted - 30min].
           SS tirada durante o jogo → torneio comecou antes do post; -30min
           evita falsos positivos com torneios que mal arrancaram.
      3. nem start_time_iso nem posted_at_hint -> None (sem janela).
    """
    st = _parse_iso_naive(start_time_iso)
    if st:
        return (st - timedelta(hours=window_hours),
                st + timedelta(hours=_RAMO1_FWD_HOURS))
    if posted_at_hint is not None:
        # Convenção pt51: tudo em Lisboa naive. Descarta tzinfo se vier (mantém o
        # wall-clock de Lisboa) p/ comparar naive↔naive com as colunas.
        if posted_at_hint.tzinfo is not None:
            posted_at_hint = posted_at_hint.replace(tzinfo=None)
        if anchor_mode == "prestart":
            # #META-START-TIME (item 9): GG usa forward alargado (late-reg) porque
            # a coluna start_time dos TIER 1/2 é a 1ª mão, não o arranque agendado.
            fwd = _GG_PRESTART_FWD_HOURS if site == "GGPoker" else _PRESTART_FWD_HOURS
            return (
                posted_at_hint - timedelta(hours=_PRESTART_BACK_HOURS),
                posted_at_hint + timedelta(hours=fwd),
            )
        return (
            posted_at_hint - timedelta(hours=12),
            posted_at_hint - timedelta(minutes=30),
        )
    return None


def _query_summaries(site, patterns, buy_in=None, buy_in_currency=None,
                     prize_pool=None, total_players=None,
                     anchor=None, window_hours=_TIER0_WINDOW_HOURS,
                     anchor_mode="during_play", return_all=False):
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
        # pt41 Track A: janela source-aware + selecção "closest" (ORDER BY abs)
        # em vez de "start<=anchor DESC". during_play: [anchor−24h, anchor]
        # (fwd=0 ≡ comportamento anterior). prestart: [anchor−12h, anchor+2h].
        if anchor_mode == "prestart":
            back_h, fwd_h = _PRESTART_BACK_HOURS, _PRESTART_FWD_HOURS
        else:
            back_h, fwd_h = window_hours, 0
        # return_all (RAIZ 2): devolve TODAS as edições da janela (não LIMIT 1
        # "closest às cegas") para o resolver as desambiguar por prova. total_players
        # vai no SELECT p/ a régua da impossibilidade (H2).
        limit_sql = "" if return_all else "LIMIT 1"
        return query(
            """SELECT tournament_number, tournament_name, start_time, total_players
                 FROM tournament_summaries
                WHERE site = %s
                  AND tournament_name ILIKE ALL (%s::text[])
                  AND (%s::numeric IS NULL OR buy_in_total = %s::numeric)
                  AND (%s::text IS NULL OR buy_in_currency = %s)
                  AND (%s::numeric IS NULL OR prize_pool = %s::numeric)
                  AND (%s::integer IS NULL OR total_players = %s::integer)
                  AND start_time >= %s - make_interval(hours => %s)
                  AND start_time <= %s + make_interval(hours => %s)
                ORDER BY abs(EXTRACT(EPOCH FROM (start_time - %s))) ASC
                """ + limit_sql,
            (site, patterns, buy_in, buy_in, buy_in_currency, buy_in_currency,
             prize_pool, prize_pool, total_players, total_players,
             anchor, back_h, anchor, fwd_h, anchor),
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
    anchor_mode: str = "during_play",
    return_tier: bool = False,
    disambiguate_editions: bool = False,
    disambig_anchor_lisbon: Optional[datetime] = None,
    disambig_entrants: Optional[int] = None,
    disambig_players_left: Optional[int] = None,
):
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

        return_tier=True (opt-in, não-default — não parte callers existentes):
            devolve um 3º elemento `tier` ∈ {'summaries','meta','hands',None}
            indicando ONDE matchou (ou onde ficou ambíguo). None se nenhum tier
            produziu candidatos. Usado pela página Lobbys (detalhe "como resolveu").
    """
    def _ret(tn, cands, tier):
        return (tn, cands, tier) if return_tier else (tn, cands)

    tokens = _tokenize_name(clean_tournament_name(tournament_name))
    if not tokens:
        logger.warning("[tournament_resolver] FAIL name_empty")
        return _ret(None, [], None)

    patterns = [f"%{t}%" for t in tokens]
    window = _decide_window(start_time_iso, posted_at_hint, window_hours, anchor_mode, site)

    # TIER 0 — tournament_summaries (autoritativo). pt39: nome + buy_in +
    # janela start_time ancorada no posted_at_hint (instância em curso).
    # Convenção pt51: anchor em Lisboa naive (compara naive↔naive com
    # tournament_summaries.start_time). Descarta tzinfo se vier.
    anchor = posted_at_hint
    if anchor is not None and anchor.tzinfo is not None:
        anchor = anchor.replace(tzinfo=None)
    ts_currency = (
        (buy_in_currency or _currency_for_site(site)) if buy_in is not None else None
    )
    # RAIZ 2 (11 Jul) — só GG, só quando o caller pede (lobby prestart). Traz
    # TODAS as edições da janela (não LIMIT 1 às cegas) para desambiguar por prova.
    disambig_on = (
        disambiguate_editions and site == "GGPoker" and anchor is not None
    )
    candidates_summaries = [dict(r) for r in _query_summaries(
        site, patterns, buy_in=buy_in, buy_in_currency=ts_currency,
        prize_pool=prize_pool, total_players=total_players, anchor=anchor,
        anchor_mode=anchor_mode, return_all=disambig_on,
    )]
    if candidates_summaries:
        if len(candidates_summaries) == 1:
            tn = candidates_summaries[0]["tournament_number"]
            logger.info(
                f"[tournament_resolver] OK tier=summaries tn={tn} site={site}"
            )
            return _ret(tn, [], "summaries")
        if disambig_on:
            # 2+ edições do mesmo torneio/dia: exige PROVA DURA para colar; sem
            # prova que as separe → quarentena (tier='edition_quarantine').
            chosen, decision, _surv = _disambiguate_editions(
                site, candidates_summaries, disambig_anchor_lisbon,
                disambig_entrants, disambig_players_left,
                lobby_name=tournament_name,
            )
            if chosen is not None:
                logger.info(
                    f"[tournament_resolver] OK tier=summaries_disambiguated "
                    f"tn={chosen} decision={decision} site={site}"
                )
                return _ret(chosen, [], "summaries")
            logger.info(
                f"[tournament_resolver] EDITION_QUARANTINE decision={decision} "
                f"n={len(candidates_summaries)} site={site}"
            )
            return _ret(None, candidates_summaries, "edition_quarantine")
        logger.info(
            f"[tournament_resolver] AMBIG tier=summaries "
            f"n={len(candidates_summaries)} site={site}"
        )
        return _ret(None, candidates_summaries, "summaries")

    # TIER 1 — tournaments_meta
    candidates_meta = [dict(r) for r in _query_meta(site, patterns, window)]
    if candidates_meta:
        if len(candidates_meta) == 1:
            tn = candidates_meta[0]["tournament_number"]
            logger.info(
                f"[tournament_resolver] OK tier=meta tn={tn} site={site}"
            )
            return _ret(tn, [], "meta")
        logger.info(
            f"[tournament_resolver] AMBIG tier=meta "
            f"n={len(candidates_meta)} site={site}"
        )
        return _ret(None, candidates_meta, "meta")

    # TIER 2 — hands fallback
    candidates_hands = [dict(r) for r in _query_hands(site, patterns, window)]
    if len(candidates_hands) == 1:
        tn = candidates_hands[0]["tournament_number"]
        logger.info(
            f"[tournament_resolver] OK tier=hands tn={tn} site={site}"
        )
        return _ret(tn, [], "hands")
    if candidates_hands:
        logger.info(
            f"[tournament_resolver] AMBIG tier=hands "
            f"n={len(candidates_hands)} site={site}"
        )
        return _ret(None, candidates_hands, "hands")
    return _ret(None, [], None)
