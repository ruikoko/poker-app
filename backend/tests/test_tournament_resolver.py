"""Unit tests para services/tournament_resolver.resolve_tournament_number (FASE A C2).
Mocked DB via patch a app.services.tournament_resolver.query."""
from unittest.mock import patch
from datetime import datetime, timezone

from app.services.tournament_resolver import (
    resolve_tournament_number, _tokenize_name, clean_tournament_name,
    name_tokens_subset, _decide_window,
)


def _row(tn, name, st):
    return {"tournament_number": tn, "tournament_name": name, "start_time": st}


def test_resolve_unique_match_returns_tn():
    rows = [_row("281416137", "Bounty Hunters Big Game $215",
                 datetime(2026, 5, 5, 18, 30))]
    with patch("app.services.tournament_resolver.query", side_effect=[[], rows]):
        tn, candidates = resolve_tournament_number(
            "GGPoker", "Bounty Hunters Big Game $215",
            "2026-05-05T18:30:00Z",
        )
    assert tn == "281416137"
    assert candidates == []


def test_resolve_zero_matches_returns_none_and_empty():
    with patch("app.services.tournament_resolver.query", return_value=[]):
        tn, candidates = resolve_tournament_number(
            "GGPoker", "NonExistent", "2026-05-05T18:30:00Z"
        )
    assert tn is None
    assert candidates == []


def test_resolve_multiple_matches_returns_none_and_list():
    rows = [
        _row("281416137", "Bounty Hunters Big Game $215",
             datetime(2026, 5, 5, 18, 30)),
        _row("281200092", "Bounty Hunters Big Game $215",
             datetime(2026, 5, 5, 19, 30)),
    ]
    with patch("app.services.tournament_resolver.query", side_effect=[[], rows]):
        tn, candidates = resolve_tournament_number(
            "GGPoker", "Bounty Hunters Big Game $215",
            "2026-05-05T18:30:00Z",
        )
    assert tn is None
    assert len(candidates) == 2


def test_resolve_passes_token_array_to_sql():
    """Caller diz 'BBG $215'; SQL recebe ['%bbg%', '%$215%'] como
    array para ILIKE ALL (substitui o antigo substring_match_passes_through)."""
    rows = [_row("281416137", "Bounty Hunters Big Game $215",
                 datetime(2026, 5, 5, 18, 30))]
    with patch("app.services.tournament_resolver.query", side_effect=[[], rows]) as m:
        resolve_tournament_number("GGPoker", "BBG $215", "2026-05-05T18:30:00Z")
    args = m.call_args[0]
    sql_args = args[1]
    assert sql_args[0] == "GGPoker"
    assert sql_args[1] == ["%bbg%", "%$215%"]


def test_resolve_no_start_time_falls_back_to_no_window():
    """Sem start_time_iso, query nao filtra por janela — usa LIMIT 5."""
    rows = [_row("281416137", "Bounty Hunters Big Game $215", None)]
    with patch("app.services.tournament_resolver.query", side_effect=[[], rows]) as m:
        tn, _ = resolve_tournament_number("GGPoker", "BBG $215", None)
    args = m.call_args[0]
    assert len(args[1]) == 2
    assert tn == "281416137"


def test_resolve_invalid_iso_falls_back_gracefully():
    rows = []
    with patch("app.services.tournament_resolver.query", return_value=rows) as m:
        resolve_tournament_number("GGPoker", "BBG $215", "not-iso")
    args = m.call_args[0]
    assert len(args[1]) == 2


def test_resolve_handles_z_suffix_in_iso():
    rows = [_row("281416137", "x",
                 datetime(2026, 5, 5, 18, 30))]
    with patch("app.services.tournament_resolver.query", side_effect=[[], rows]) as m:
        resolve_tournament_number("GGPoker", "x", "2026-05-05T18:30:00Z")
    args = m.call_args[0]
    assert len(args[1]) == 4
    # pt51: convenção Lisboa naive → janela sem tzinfo.
    assert args[1][2].tzinfo is None  # lo
    assert args[1][3].tzinfo is None  # hi


# ── Token-set match — resolver-level (G2 cobertura) ─────────────────────────

def test_resolve_empty_name_returns_early_no_db_call():
    """Nome vazio / None / só whitespace / só pontuação curto-circuita
    antes de qualquer hit à BD. Cobre o early return novo + log FAIL."""
    for empty_input in ("", None, "   ", ",.!?"):
        with patch("app.services.tournament_resolver.query") as m:
            tn, candidates = resolve_tournament_number(
                "GGPoker", empty_input, "2026-05-05T18:30:00Z"
            )
        assert tn is None, f"input={empty_input!r}"
        assert candidates == [], f"input={empty_input!r}"
        m.assert_not_called()


def test_resolve_subset_match_simulated():
    """G2 happy path: Vision lê nome curto que é subset do BD.
    'Bounty Hunters Hyper Special $108' (Vision) vs
    'Bounty Hunters Sunday Hyper Special $108' (BD) — ILIKE ALL tolera
    palavras extra no lado do BD. Mock devolve a row; documentamos o
    caminho feliz no resolver."""
    rows = [_row("123456789",
                 "Bounty Hunters Sunday Hyper Special $108",
                 datetime(2026, 5, 5, 18, 30))]
    with patch("app.services.tournament_resolver.query", side_effect=[[], rows]):
        tn, candidates = resolve_tournament_number(
            "GGPoker", "Bounty Hunters Hyper Special $108",
            "2026-05-05T18:30:00Z",
        )
    assert tn == "123456789"
    assert candidates == []


def test_resolve_patterns_preserve_input_token_order():
    """Os patterns chegam ao SQL na ordem dos tokens do input. A
    comutatividade real de ILIKE ALL é semântica do Postgres (precisa
    integração para validar) — aqui só fixamos a construção do array."""
    rows = [_row("123", "x", None)]
    with patch("app.services.tournament_resolver.query", side_effect=[[], rows]) as m:
        resolve_tournament_number("GGPoker", "Hunters Bounty $108", None)
    args = m.call_args[0]
    assert args[1][1] == ["%hunters%", "%bounty%", "%$108%"]


def test_resolve_extra_vision_token_excludes_match():
    """G2 outra face: Vision alucina token extra ('NEW') que não bate
    em nenhum tournament_name do BD. ILIKE ALL é estritamente conjuntivo
    → BD devolve 0 rows e resolver propaga (None, []). Confirma que o
    token estranho FOI efectivamente enviado ao SQL (não silenciosamente
    descartado)."""
    with patch("app.services.tournament_resolver.query", return_value=[]) as m:
        tn, candidates = resolve_tournament_number(
            "GGPoker", "NEW Bounty Hunters", "2026-05-05T18:30:00Z"
        )
    args = m.call_args[0]
    sql_args = args[1]
    assert tn is None
    assert candidates == []
    assert "%new%" in sql_args[1]
    assert "%bounty%" in sql_args[1]
    assert "%hunters%" in sql_args[1]


# ── _tokenize_name unit tests ───────────────────────────────────────────────

def test_tokenize_basic_preserves_dollar():
    assert _tokenize_name("Bounty Hunters Sunday Hyper Special $108") == [
        "bounty", "hunters", "sunday", "hyper", "special", "$108"
    ]


def test_tokenize_strips_trailing_comma():
    assert _tokenize_name("GGMasters High Rollers, 750K GTD") == [
        "ggmasters", "high", "rollers", "750k", "gtd"
    ]


def test_tokenize_preserves_hyphen_strips_colon():
    assert _tokenize_name("WSOP-SC HR: $525 Bounty Hunters Circuit HR") == [
        "wsop-sc", "hr", "$525", "bounty", "hunters", "circuit", "hr"
    ]


def test_tokenize_empty_and_none_and_whitespace():
    assert _tokenize_name("") == []
    assert _tokenize_name(None) == []
    assert _tokenize_name("   ") == []
    assert _tokenize_name(",.!?") == []


# ── COMMIT B: posted_at_hint window precedence ──────────────────────────────

def test_resolve_uses_posted_at_window_when_no_start_time():
    """start_time_iso=None + posted_at_hint -> janela [posted-12h, posted-30min]."""
    rows = [_row("X", "x", None)]
    posted = datetime(2026, 5, 9, 14, 0)
    with patch("app.services.tournament_resolver.query", side_effect=[[], rows]) as m:
        resolve_tournament_number(
            "GGPoker", "x", None, posted_at_hint=posted,
        )
    args = m.call_args[0]
    assert len(args[1]) == 4  # site, patterns, lo, hi
    lo, hi = args[1][2], args[1][3]
    assert lo == datetime(2026, 5, 9, 2, 0)   # posted - 12h
    assert hi == datetime(2026, 5, 9, 13, 30)  # posted - 30min


def test_resolve_start_time_takes_precedence_over_posted_at():
    """Ambos passados -> janela final e a do start_time, nao a do posted_at."""
    rows = [_row("X", "x", None)]
    posted = datetime(2026, 5, 9, 14, 0)
    with patch("app.services.tournament_resolver.query", side_effect=[[], rows]) as m:
        resolve_tournament_number(
            "GGPoker", "x", "2026-05-09T18:30:00Z", posted_at_hint=posted,
        )
    args = m.call_args[0]
    lo, hi = args[1][2], args[1][3]
    # pt41 ramo-1: back=window_hours(2h), forward=4h -> [16:30, 22:30] em torno de 18:30.
    assert lo == datetime(2026, 5, 9, 16, 30)
    assert hi == datetime(2026, 5, 9, 22, 30)


def test_resolve_no_hints_falls_back_to_limit_5():
    """Nem start_time nem posted_at -> SQL com LIMIT 5 e 2 args."""
    rows = [_row("X", "x", None)]
    with patch("app.services.tournament_resolver.query", side_effect=[[], rows]) as m:
        resolve_tournament_number("GGPoker", "x", None)
    args = m.call_args[0]
    assert "LIMIT 5" in args[0]
    assert len(args[1]) == 2  # site, patterns


# ── COMMIT B: fallback to `hands` when meta empty ───────────────────────────

def test_resolve_falls_back_to_hands_when_meta_empty():
    """Winamax: meta retorna []; 2a query (hands) devolve row; resolver retorna tn."""
    meta_rows: list[dict] = []
    hands_rows = [_row("987654321", "Winamax Daily $50",
                       datetime(2026, 5, 9, 12, 0))]
    with patch("app.services.tournament_resolver.query",
               side_effect=[[], meta_rows, hands_rows]) as m:
        tn, candidates = resolve_tournament_number(
            "Winamax", "Winamax Daily $50", "2026-05-09T13:30:00Z",
        )
    assert tn == "987654321"
    assert candidates == []
    assert m.call_count == 3


def test_resolve_prefers_meta_when_meta_has_match():
    """Meta retorna 1 row -> hands query NAO e chamada (call_count == 2 pos-B2:
    TS empty + meta hit)."""
    meta_rows = [_row("281416137", "BBG $215",
                      datetime(2026, 5, 5, 18, 30))]
    with patch("app.services.tournament_resolver.query",
               side_effect=[[], meta_rows]) as m:
        tn, candidates = resolve_tournament_number(
            "GGPoker", "BBG $215", "2026-05-05T18:30:00Z",
        )
    assert tn == "281416137"
    assert candidates == []
    assert m.call_count == 2


def test_resolve_fallback_query_uses_group_by_against_hands():
    """SQL da 3a call: FROM hands, GROUP BY, study_state filter, regra 2026.
    (Pos-B2: 1a call e TS, 2a meta, 3a hands.)"""
    with patch("app.services.tournament_resolver.query",
               side_effect=[[], [], []]) as m:
        resolve_tournament_number(
            "Winamax", "Winamax Daily $50", "2026-05-09T13:30:00Z",
        )
    assert m.call_count == 3
    sql_3rd = m.call_args_list[2][0][0]
    assert "FROM hands" in sql_3rd
    assert "GROUP BY tournament_number" in sql_3rd
    assert "study_state != 'mtt_archive'" in sql_3rd
    assert "played_at >= '2026-01-01'" in sql_3rd


def test_resolve_winamax_with_posted_at_hint_only():
    """Combinado: Winamax + meta vazio + posted_at_hint -> fallback hands
    com janela [posted-12h, posted-30min] aplicada a hands."""
    meta_rows: list[dict] = []
    hands_rows = [_row("987654321", "Winamax Daily $50",
                       datetime(2026, 5, 9, 8, 0))]
    posted = datetime(2026, 5, 9, 14, 0)
    with patch("app.services.tournament_resolver.query",
               side_effect=[[], meta_rows, hands_rows]) as m:
        tn, candidates = resolve_tournament_number(
            "Winamax", "Winamax Daily $50", None,
            posted_at_hint=posted,
        )
    assert tn == "987654321"
    assert candidates == []
    assert m.call_count == 3
    sql_args_3rd = m.call_args_list[2][0][1]
    lo, hi = sql_args_3rd[2], sql_args_3rd[3]
    assert lo == datetime(2026, 5, 9, 2, 0)
    assert hi == datetime(2026, 5, 9, 13, 30)


# ── B2: tier 0 (tournament_summaries) ───────────────────────────────────────

def test_b2_match_via_summaries_unique():
    """1 row em TS -> resolve directo, nao toca em meta nem hands."""
    ts_rows = [_row("281416137", "BBG $215",
                    datetime(2026, 5, 5, 18, 30))]
    with patch("app.services.tournament_resolver.query",
               side_effect=[ts_rows]) as m:
        tn, candidates = resolve_tournament_number(
            "GGPoker", "BBG $215", "2026-05-05T18:30:00Z",
        )
    assert tn == "281416137"
    assert candidates == []
    assert m.call_count == 1  # so TS, sem fallback


def test_b2_match_via_summaries_ambiguous():
    """2 rows em TS -> tm_ambiguous, nao toca em meta nem hands
    (preserva semantica do commit B: ambig curto-circuita tiers seguintes)."""
    ts_rows = [
        _row("281416137", "BBG $215",
             datetime(2026, 5, 5, 18, 30)),
        _row("281200092", "BBG $215",
             datetime(2026, 5, 5, 19, 30)),
    ]
    with patch("app.services.tournament_resolver.query",
               side_effect=[ts_rows]) as m:
        tn, candidates = resolve_tournament_number(
            "GGPoker", "BBG $215", "2026-05-05T18:30:00Z",
        )
    assert tn is None
    assert len(candidates) == 2
    assert m.call_count == 1


def test_b2_no_match_summaries_falls_back_to_meta():
    """0 rows em TS, 1 row em meta -> resolve via meta, sem tocar hands."""
    meta_rows = [_row("Y", "y", None)]
    with patch("app.services.tournament_resolver.query",
               side_effect=[[], meta_rows]) as m:
        tn, candidates = resolve_tournament_number(
            "GGPoker", "y", "2026-05-05T18:30:00Z",
        )
    assert tn == "Y"
    assert candidates == []
    assert m.call_count == 2  # TS + meta


def test_b2_no_match_summaries_no_meta_falls_back_to_hands():
    """0 em TS, 0 em meta, 1 em hands -> resolve via hands."""
    hands_rows = [_row("Z", "z", None)]
    with patch("app.services.tournament_resolver.query",
               side_effect=[[], [], hands_rows]) as m:
        tn, candidates = resolve_tournament_number(
            "GGPoker", "z", "2026-05-05T18:30:00Z",
        )
    assert tn == "Z"
    assert candidates == []
    assert m.call_count == 3  # TS + meta + hands


def test_b2_summaries_match_takes_precedence_over_meta():
    """TS devolve 1 row com tn=AAA. Meta nunca e chamado mesmo que
    tivesse outro tn — TS ganha e curto-circuita."""
    ts_rows = [_row("AAA", "tournament", None)]
    with patch("app.services.tournament_resolver.query",
               side_effect=[ts_rows]) as m:
        tn, candidates = resolve_tournament_number(
            "GGPoker", "tournament", "2026-05-05T18:30:00Z",
        )
    assert tn == "AAA"
    assert candidates == []
    assert m.call_count == 1  # so TS — meta nao foi chamado


def test_b2_summaries_query_targets_correct_table():
    """Defensivo: garante que a 1a call do resolver vai a tournament_summaries.
    Protege contra refactor que troque tabela inadvertidamente."""
    ts_rows = [_row("X", "x", None)]
    with patch("app.services.tournament_resolver.query",
               side_effect=[ts_rows]) as m:
        resolve_tournament_number("GGPoker", "x", "2026-05-05T18:30:00Z")
    sql_1st = m.call_args_list[0][0][0]
    assert "FROM tournament_summaries" in sql_1st


# ── pt39: TIER 0 = nome + buy_in + janela start_time ancorada (posted_at) ───
# Substitui a secção B2.1 (prize_pool/total_players removidos do TIER 0).
# Ver #RESOLVER-TIER0-STRICT-EQUALITY.

def test_pt39_tier0_match_name_buyin_anchor_unique():
    """Cenário 1 — os 3 GG vanilla pt37 passam a resolver: nome + buy_in +
    âncora único. Confirma params buy_in (NULL-permissivo) + currency derivada
    do site + LIMIT 1 + janela make_interval."""
    posted = datetime(2026, 5, 19, 16, 7)
    ts_rows = [_row("284491487", "Daily Deepstack Special $125",
                    datetime(2026, 5, 19, 15, 5))]
    with patch("app.services.tournament_resolver.query", side_effect=[ts_rows]) as m:
        tn, candidates = resolve_tournament_number(
            "GGPoker", "Daily Deepstack Special $125", None,
            posted_at_hint=posted, buy_in=125.0,
        )
    assert tn == "284491487"
    assert candidates == []
    assert m.call_count == 1
    sql, sql_args = m.call_args_list[0][0]
    assert "LIMIT 1" in sql and "make_interval" in sql
    assert "ORDER BY abs(" in sql                              # pt41: closest (era DESC)
    # ordem anchored pt41: site,patterns, buy,buy, cur,cur, pp,pp, tp,tp, anchor,back_h, anchor,fwd_h, anchor
    assert sql_args[2] == 125.0 and sql_args[3] == 125.0       # buy_in
    assert sql_args[4] == "USD" and sql_args[5] == "USD"        # currency do site
    assert sql_args[6] is None and sql_args[8] is None         # pool/players NULL (lobby)
    assert sql_args[10] == posted                              # anchor (limite back)
    assert sql_args[11] == 24 and sql_args[13] == 0            # during_play: back=24h, fwd=0


def test_pt39_tier0_two_per_day_picks_running_instance():
    """Cenário 2 — torneio 2x/dia (16:45 e 19:45); SS às 18:00 (table-ss, default
    during_play). A DB (LIMIT 1, [anchor−24h, anchor], ORDER BY abs = closest)
    devolve a das 16:45 (em curso, a mais próxima ≤ anchor); o mock simula essa
    selecção. Aqui fixamos o contrato SQL + propagação do tn."""
    posted = datetime(2026, 5, 19, 18, 0)
    running = [_row("284939948", "Daily Hyper $50",
                    datetime(2026, 5, 19, 16, 45))]
    with patch("app.services.tournament_resolver.query", side_effect=[running]) as m:
        tn, candidates = resolve_tournament_number(
            "GGPoker", "Daily Hyper $50", None,
            posted_at_hint=posted, buy_in=50.0,
        )
    assert tn == "284939948"
    assert candidates == []
    sql, sql_args = m.call_args_list[0][0]
    assert "ORDER BY abs(" in sql and "LIMIT 1" in sql
    assert sql_args[10] == posted             # anchor (limite back)
    assert sql_args[11] == 24 and sql_args[13] == 0   # during_play: back=24h, fwd=0


def test_pt39_tier0_anchor_before_starts_falls_through():
    """Cenário 3 — SS antes de qualquer instância arrancar: a DB devolve 0
    (start<=anchor vazio) → cascata para o TIER 1."""
    posted = datetime(2026, 5, 19, 15, 0)
    meta_rows = [_row("X", "Daily Hyper $50",
                      datetime(2026, 5, 19, 16, 45))]
    with patch("app.services.tournament_resolver.query",
               side_effect=[[], meta_rows]) as m:
        tn, candidates = resolve_tournament_number(
            "GGPoker", "Daily Hyper $50", None,
            posted_at_hint=posted, buy_in=50.0,
        )
    assert tn == "X"
    assert m.call_count == 2  # TS vazio -> meta


def test_pt39_tier0_buyin_none_name_and_anchor_only():
    """Cenário 4 — Vision não leu buy_in: filtro NULL-permissivo (buy_in e
    currency a None), resolve por nome + janela."""
    posted = datetime(2026, 5, 19, 18, 0)
    ts_rows = [_row("Y", "Daily Hyper $50",
                    datetime(2026, 5, 19, 16, 45))]
    with patch("app.services.tournament_resolver.query", side_effect=[ts_rows]) as m:
        tn, _ = resolve_tournament_number(
            "GGPoker", "Daily Hyper $50", None, posted_at_hint=posted,  # buy_in None
        )
    assert tn == "Y"
    sql_args = m.call_args_list[0][0][1]
    assert sql_args[2] is None and sql_args[3] is None   # buy_in NULL
    assert sql_args[4] is None and sql_args[5] is None   # currency NULL quando buy_in None


def test_pt39_tier0_currency_strict_then_fallthrough():
    """Cenário 5 — currency divergente: a moeda estrita é enviada ao SQL (a DB
    excluiria); mock devolve 0 → cascata. Currency explícita ganha sobre o site."""
    posted = datetime(2026, 5, 19, 18, 0)
    with patch("app.services.tournament_resolver.query",
               side_effect=[[], [], []]) as m:
        tn, candidates = resolve_tournament_number(
            "GGPoker", "x", None,
            posted_at_hint=posted, buy_in=50.0, buy_in_currency="EUR",
        )
    sql_args_ts = m.call_args_list[0][0][1]
    assert sql_args_ts[4] == "EUR" and sql_args_ts[5] == "EUR"  # estrita, explícita
    assert tn is None
    assert m.call_count == 3  # TS vazio -> meta vazio -> hands vazio


def test_pt39_tier0_no_anchor_multiple_returns_candidates():
    """Cenário 6 — sem âncora + múltiplos: ramo LIMIT 5, devolve candidatos
    (contrato preservado, ambiguidade sobe)."""
    ts_rows = [
        _row("A", "Daily Hyper $50", None),
        _row("B", "Daily Hyper $50", None),
    ]
    with patch("app.services.tournament_resolver.query", side_effect=[ts_rows]) as m:
        tn, candidates = resolve_tournament_number(
            "GGPoker", "Daily Hyper $50", None, buy_in=50.0,  # sem posted_at_hint
        )
    assert tn is None
    assert len(candidates) == 2
    sql = m.call_args_list[0][0][0]
    assert "LIMIT 5" in sql
    assert "make_interval" not in sql


def test_pt39_tier0_backfill_event_contemporary_with_anchor():
    """Cenário 7 — backfill: TS importado tarde, mas start_time = instante real
    do evento, contemporâneo do posted_at → dentro da janela 24h → match."""
    posted = datetime(2026, 5, 19, 17, 0)
    event_start = datetime(2026, 5, 19, 16, 45)
    ts_rows = [_row("284939948", "Daily Hyper $80", event_start)]
    with patch("app.services.tournament_resolver.query", side_effect=[ts_rows]) as m:
        tn, candidates = resolve_tournament_number(
            "GGPoker", "Daily Hyper $80", None,
            posted_at_hint=posted, buy_in=80.0,
        )
    assert tn == "284939948"
    assert candidates == []
    assert m.call_count == 1


def test_pt39_tier1_unchanged_when_tier0_empty():
    """Cenário 8 — regressão: TIER 0 vazio → TIER 1 windowed inalterado
    (BETWEEN presente, 4 args site/patterns/lo/hi)."""
    rows = [_row("281416137", "BBG $215",
                 datetime(2026, 5, 5, 18, 30))]
    with patch("app.services.tournament_resolver.query", side_effect=[[], rows]) as m:
        tn, _ = resolve_tournament_number(
            "GGPoker", "BBG $215", "2026-05-05T18:30:00Z", buy_in=215.0,
        )
    assert tn == "281416137"
    sql_meta, sql_args_meta = m.call_args_list[1][0]
    assert "BETWEEN" in sql_meta          # janela TIER 1 intacta
    assert len(sql_args_meta) == 4        # site, patterns, lo, hi


def test_pt39_tier0_naive_anchor_stays_naive():
    """pt51: convenção Lisboa naive — o anchor vai ao SQL como naive (compara
    naive↔naive com tournament_summaries.start_time, sem coerção de fuso)."""
    posted_naive = datetime(2026, 5, 19, 18, 0)  # Lisboa naive
    ts_rows = [_row("Z", "x", datetime(2026, 5, 19, 16, 45))]
    with patch("app.services.tournament_resolver.query", side_effect=[ts_rows]) as m:
        resolve_tournament_number("GGPoker", "x", None,
                                  posted_at_hint=posted_naive, buy_in=10.0)
    # ordem anchored: anchor está no índice 10 (índices 6/8 são pool/players).
    anchor_param = m.call_args_list[0][0][1][10]
    assert anchor_param.tzinfo is None
    assert anchor_param == posted_naive


def test_pt39_tier0_backoffice_pool_players_no_anchor():
    """Backoffice (pós-jogo): pool/players FINAIS chegam ao SQL como filtros
    NULL-permissivos no ramo sem âncora (posted_at_hint=None). Preserva o
    discriminador correcto do pipeline tournament_results (reversão parcial da
    decisão #4 — pool/players coexistem com buy_in). Ver #RESOLVER-TIER0-STRICT-EQUALITY."""
    ts_rows = [_row("283542054", "Daily Hyper $80", None)]
    with patch("app.services.tournament_resolver.query", side_effect=[ts_rows]) as m:
        tn, candidates = resolve_tournament_number(
            "GGPoker", "Daily Hyper $80", None,
            prize_pool=9420.80, total_players=128,
        )
    assert tn == "283542054"
    assert candidates == []
    sql, sql_args = m.call_args_list[0][0]
    assert "LIMIT 5" in sql and "make_interval" not in sql
    # ordem no-anchor: site,patterns, buy_in,buy_in, cur,cur, pp,pp, tp,tp
    assert sql_args[2] is None                              # buy_in não passado
    assert sql_args[6] == 9420.80 and sql_args[7] == 9420.80  # prize_pool
    assert sql_args[8] == 128 and sql_args[9] == 128         # total_players


# ── pt39 parte 1/2: clean_tournament_name (drop trailing #NNN) ───────────────
# #TABLE-SS-RESOLVER-COLLISION — o sufixo #NNN (nº de mesa Winamax lido na SS de
# mesa) envenenava o ILIKE ALL. clean_tournament_name apara só o trailing #\d+.

# ── pt41 Track A: anchor_mode source-aware (#LOBBY-ANCHOR-PRESTART-REGRESSION) ──

def test_trackA_tier0_prestart_window_and_closest_order():
    """Lobby (anchor_mode='prestart'): TIER 0 usa [anchor−12h, anchor+2h] +
    ORDER BY abs (closest) → resolve para o start futuro próximo."""
    posted = datetime(2026, 5, 19, 16, 17)
    ts_rows = [_row("284939948", "Daily Hyper $80",
                    datetime(2026, 5, 19, 16, 45))]  # +28min
    with patch("app.services.tournament_resolver.query", side_effect=[ts_rows]) as m:
        tn, candidates = resolve_tournament_number(
            "GGPoker", "Daily Hyper $80", None,
            posted_at_hint=posted, buy_in=80.0, anchor_mode="prestart",
        )
    assert tn == "284939948" and candidates == []
    sql, sql_args = m.call_args_list[0][0]
    assert "ORDER BY abs(" in sql and "LIMIT 1" in sql
    assert sql_args[11] == 12 and sql_args[13] == 2   # prestart: back=12h, fwd=2h


def test_trackA_tier0_during_play_is_default():
    """Default (sem anchor_mode) = during_play: back=24h, fwd=0 (table-ss inalterado)."""
    posted = datetime(2026, 5, 19, 18, 0)
    ts_rows = [_row("Z", "x", datetime(2026, 5, 19, 16, 0))]
    with patch("app.services.tournament_resolver.query", side_effect=[ts_rows]) as m:
        resolve_tournament_number(
            "GGPoker", "x", None, posted_at_hint=posted, buy_in=50.0)
    sql_args = m.call_args_list[0][0][1]
    assert sql_args[11] == 24 and sql_args[13] == 0


def test_trackA_decide_window_ramo1_forward_4h():
    """Ramo-1 (start_time válido): [start−2h, start+4h]; hand a +3h ainda dentro."""
    lo, hi = _decide_window("2026-05-19T16:45:00Z", None, 2.0)
    assert lo == datetime(2026, 5, 19, 14, 45)
    assert hi == datetime(2026, 5, 19, 20, 45)   # +4h
    assert lo <= datetime(2026, 5, 19, 19, 45) <= hi


def test_trackA_decide_window_ramo2_prestart_forward():
    """Ramo-2 sem start_time + prestart: [posted−12h, posted+2h]."""
    posted = datetime(2026, 5, 19, 16, 0)
    lo, hi = _decide_window(None, posted, 2.0, anchor_mode="prestart")
    assert lo == datetime(2026, 5, 19, 4, 0)
    assert hi == datetime(2026, 5, 19, 18, 0)


def test_trackA_decide_window_ramo2_during_play_unchanged():
    """Ramo-2 sem start_time + during_play (default): [posted−12h, posted−30min]."""
    posted = datetime(2026, 5, 19, 16, 0)
    lo, hi = _decide_window(None, posted, 2.0)
    assert lo == datetime(2026, 5, 19, 4, 0)
    assert hi == datetime(2026, 5, 19, 15, 30)


def test_clean_drops_trailing_table_suffix():
    assert clean_tournament_name("ZENITH #005") == "ZENITH"
    assert clean_tournament_name("GALACTICA #000") == "GALACTICA"


def test_clean_preserves_prefix_hash_w_series():
    assert clean_tournament_name("#220 - W SERIES - SPACE KO") == "#220 - W SERIES - SPACE KO"


def test_clean_preserves_non_digit_hashtag():
    assert clean_tournament_name("Daily $100,000 #ThanksGG Flipout") == \
        "Daily $100,000 #ThanksGG Flipout"


def test_clean_does_not_touch_dollar_amount():
    assert clean_tournament_name("Daily Hyper $80") == "Daily Hyper $80"


def test_clean_drops_only_trailing_in_compound():
    assert clean_tournament_name("#220 - W SERIES #007") == "#220 - W SERIES"


def test_clean_idempotent_and_edge_inputs():
    assert clean_tournament_name("ZENITH") == "ZENITH"        # idempotente
    assert clean_tournament_name("ZENITH #005 ") == "ZENITH"  # trailing space
    assert clean_tournament_name("") == ""
    assert clean_tournament_name(None) is None


def test_clean_then_tokenize_drops_suffix_token():
    assert _tokenize_name(clean_tournament_name("ZENITH #005")) == ["zenith"]


def test_clean_then_tokenize_keeps_prefix_hash():
    toks = _tokenize_name(clean_tournament_name("#220 - W SERIES - SPACE KO"))
    assert "#220" in toks


def test_resolve_strips_table_suffix_before_sql():
    """Winamax 'ZENITH #005': o resolver tokeniza 'ZENITH' (sem '#005') →
    patterns ['%zenith%'] chegam ao SQL em todos os tiers; '%#005%' NUNCA.
    (TS/meta Winamax vazios → resolve via TIER 2 hands.)"""
    rows = [_row("1099830438", "ZENITH", None)]
    with patch("app.services.tournament_resolver.query",
               side_effect=[[], [], rows]) as m:
        tn, _ = resolve_tournament_number(
            "Winamax", "ZENITH #005", None,
            posted_at_hint=datetime(2026, 5, 23, 17, 46, 58),
        )
    assert tn == "1099830438"
    patterns_seen = [c[0][1][1] for c in m.call_args_list]  # params[1] = patterns
    assert ["%zenith%"] in patterns_seen
    assert all("%#005%" not in p for plist in patterns_seen for p in plist)


def test_resolve_w_series_not_over_merged():
    """'#220 - W SERIES' preserva '%#220%' nos patterns (discriminador do evento
    — drop global parti-lo-ia)."""
    with patch("app.services.tournament_resolver.query",
               side_effect=[[], [], []]) as m:
        resolve_tournament_number("Winamax", "#220 - W SERIES", "2026-05-23T18:00:00Z")
    patterns = m.call_args_list[0][0][1][1]
    assert "%#220%" in patterns


# ── pt39 parte 2/2: name_tokens_subset (validação de nome single_tn) ─────────
# #TABLE-SS-RESOLVER-COLLISION — usado por table_ss._resolve_match.

def test_name_tokens_subset_basic_match_and_mismatch():
    assert name_tokens_subset("INTERSTELLAR #005", "INTERSTELLAR") is True
    assert name_tokens_subset("EXPLORER #010", "INTERSTELLAR") is False
    assert name_tokens_subset("ODYSSEY #013", "ZENITH") is False


def test_name_tokens_subset_tolerates_extra_words_in_full():
    assert name_tokens_subset("Hyper Special $108",
                              "Sunday Hyper Special $108") is True


def test_name_tokens_subset_empty_short_is_false():
    assert name_tokens_subset("", "INTERSTELLAR") is False
    assert name_tokens_subset(None, "INTERSTELLAR") is False
    assert name_tokens_subset("#000", "ZENITH") is False  # só sufixo → 0 tokens


# ── pt58: tolerância a truncação do título (cliente GG corta títulos longos) ──

def test_name_tokens_subset_truncated_last_token_prefix_match():
    """'… [Mystery Bo...]' (id=134): restantes batem exacto + 'bo' como prefixo
    de 'bounty' → bate o título completo."""
    ss = "268-M: $150 Saturday Secret KO [Mystery Bo...]"
    assert name_tokens_subset(ss, "268-M: $150 Saturday Secret KO [Mystery Bounty]") is True


def test_name_tokens_subset_truncated_does_not_match_unrelated():
    """Os tokens RESTANTES continuam exactos — truncação não relaxa o resto."""
    ss = "268-M: $150 Saturday Secret KO [Mystery Bo...]"
    assert name_tokens_subset(ss, "Saturday Session: GGMasters Bounty $108") is False
    assert name_tokens_subset(ss, "Bounty Hunters Deepstack Turbo $54") is False


def test_name_tokens_subset_truncated_prefixes_two_tournaments():
    """'Bounty Hunters Deepstack Tu...' prefixa Turbo $54 E Turbo $88 → bate
    ambos (o caller fica ambíguo, não inventa match)."""
    ss = "Bounty Hunters Deepstack Tu..."
    assert name_tokens_subset(ss, "Bounty Hunters Deepstack Turbo $54") is True
    assert name_tokens_subset(ss, "Bounty Hunters Deepstack Turbo $88") is True


def test_name_tokens_subset_w_series_suffix_and_case():
    # sufixo de mesa #007 cai; prefixo #220 casa; case-insensitive.
    assert name_tokens_subset("#220 - W SERIES #007",
                              "#220 - W SERIES - SPACE KO") is True
    assert name_tokens_subset("zenith", "ZENITH") is True
