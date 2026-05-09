"""Unit tests para services/tm_resolver.resolve_tournament_number (FASE A C2).
Mocked DB via patch a app.services.tm_resolver.query."""
from unittest.mock import patch
from datetime import datetime, timezone

from app.services.tm_resolver import resolve_tournament_number, _tokenize_name


def _row(tn, name, st):
    return {"tournament_number": tn, "tournament_name": name, "start_time": st}


def test_resolve_unique_match_returns_tn():
    rows = [_row("281416137", "Bounty Hunters Big Game $215",
                 datetime(2026, 5, 5, 18, 30, tzinfo=timezone.utc))]
    with patch("app.services.tm_resolver.query", return_value=rows):
        tn, candidates = resolve_tournament_number(
            "GGPoker", "Bounty Hunters Big Game $215",
            "2026-05-05T18:30:00Z",
        )
    assert tn == "281416137"
    assert candidates == []


def test_resolve_zero_matches_returns_none_and_empty():
    with patch("app.services.tm_resolver.query", return_value=[]):
        tn, candidates = resolve_tournament_number(
            "GGPoker", "NonExistent", "2026-05-05T18:30:00Z"
        )
    assert tn is None
    assert candidates == []


def test_resolve_multiple_matches_returns_none_and_list():
    rows = [
        _row("281416137", "Bounty Hunters Big Game $215",
             datetime(2026, 5, 5, 18, 30, tzinfo=timezone.utc)),
        _row("281200092", "Bounty Hunters Big Game $215",
             datetime(2026, 5, 5, 19, 30, tzinfo=timezone.utc)),
    ]
    with patch("app.services.tm_resolver.query", return_value=rows):
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
                 datetime(2026, 5, 5, 18, 30, tzinfo=timezone.utc))]
    with patch("app.services.tm_resolver.query", return_value=rows) as m:
        resolve_tournament_number("GGPoker", "BBG $215", "2026-05-05T18:30:00Z")
    args = m.call_args[0]
    sql_args = args[1]
    assert sql_args[0] == "GGPoker"
    assert sql_args[1] == ["%bbg%", "%$215%"]


def test_resolve_no_start_time_falls_back_to_no_window():
    """Sem start_time_iso, query nao filtra por janela — usa LIMIT 5."""
    rows = [_row("281416137", "Bounty Hunters Big Game $215", None)]
    with patch("app.services.tm_resolver.query", return_value=rows) as m:
        tn, _ = resolve_tournament_number("GGPoker", "BBG $215", None)
    args = m.call_args[0]
    assert len(args[1]) == 2
    assert tn == "281416137"


def test_resolve_invalid_iso_falls_back_gracefully():
    rows = []
    with patch("app.services.tm_resolver.query", return_value=rows) as m:
        resolve_tournament_number("GGPoker", "BBG $215", "not-iso")
    args = m.call_args[0]
    assert len(args[1]) == 2


def test_resolve_handles_z_suffix_in_iso():
    rows = [_row("281416137", "x",
                 datetime(2026, 5, 5, 18, 30, tzinfo=timezone.utc))]
    with patch("app.services.tm_resolver.query", return_value=rows) as m:
        resolve_tournament_number("GGPoker", "x", "2026-05-05T18:30:00Z")
    args = m.call_args[0]
    assert len(args[1]) == 4
    assert args[1][2].tzinfo is not None  # lo
    assert args[1][3].tzinfo is not None  # hi


# ── Token-set match — resolver-level (G2 cobertura) ─────────────────────────

def test_resolve_empty_name_returns_early_no_db_call():
    """Nome vazio / None / só whitespace / só pontuação curto-circuita
    antes de qualquer hit à BD. Cobre o early return novo + log FAIL."""
    for empty_input in ("", None, "   ", ",.!?"):
        with patch("app.services.tm_resolver.query") as m:
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
                 datetime(2026, 5, 5, 18, 30, tzinfo=timezone.utc))]
    with patch("app.services.tm_resolver.query", return_value=rows):
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
    with patch("app.services.tm_resolver.query", return_value=rows) as m:
        resolve_tournament_number("GGPoker", "Hunters Bounty $108", None)
    args = m.call_args[0]
    assert args[1][1] == ["%hunters%", "%bounty%", "%$108%"]


def test_resolve_extra_vision_token_excludes_match():
    """G2 outra face: Vision alucina token extra ('NEW') que não bate
    em nenhum tournament_name do BD. ILIKE ALL é estritamente conjuntivo
    → BD devolve 0 rows e resolver propaga (None, []). Confirma que o
    token estranho FOI efectivamente enviado ao SQL (não silenciosamente
    descartado)."""
    with patch("app.services.tm_resolver.query", return_value=[]) as m:
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
    posted = datetime(2026, 5, 9, 14, 0, tzinfo=timezone.utc)
    with patch("app.services.tm_resolver.query", return_value=rows) as m:
        resolve_tournament_number(
            "GGPoker", "x", None, posted_at_hint=posted,
        )
    args = m.call_args[0]
    assert len(args[1]) == 4  # site, patterns, lo, hi
    lo, hi = args[1][2], args[1][3]
    assert lo == datetime(2026, 5, 9, 2, 0, tzinfo=timezone.utc)   # posted - 12h
    assert hi == datetime(2026, 5, 9, 13, 30, tzinfo=timezone.utc)  # posted - 30min


def test_resolve_start_time_takes_precedence_over_posted_at():
    """Ambos passados -> janela final e a do start_time, nao a do posted_at."""
    rows = [_row("X", "x", None)]
    posted = datetime(2026, 5, 9, 14, 0, tzinfo=timezone.utc)
    with patch("app.services.tm_resolver.query", return_value=rows) as m:
        resolve_tournament_number(
            "GGPoker", "x", "2026-05-09T18:30:00Z", posted_at_hint=posted,
        )
    args = m.call_args[0]
    lo, hi = args[1][2], args[1][3]
    # window_hours default = 2.0 -> [16:30, 20:30] em torno de 18:30.
    assert lo == datetime(2026, 5, 9, 16, 30, tzinfo=timezone.utc)
    assert hi == datetime(2026, 5, 9, 20, 30, tzinfo=timezone.utc)


def test_resolve_no_hints_falls_back_to_limit_5():
    """Nem start_time nem posted_at -> SQL com LIMIT 5 e 2 args."""
    rows = [_row("X", "x", None)]
    with patch("app.services.tm_resolver.query", return_value=rows) as m:
        resolve_tournament_number("GGPoker", "x", None)
    args = m.call_args[0]
    assert "LIMIT 5" in args[0]
    assert len(args[1]) == 2  # site, patterns


# ── COMMIT B: fallback to `hands` when meta empty ───────────────────────────

def test_resolve_falls_back_to_hands_when_meta_empty():
    """Winamax: meta retorna []; 2a query (hands) devolve row; resolver retorna tn."""
    meta_rows: list[dict] = []
    hands_rows = [_row("987654321", "Winamax Daily $50",
                       datetime(2026, 5, 9, 12, 0, tzinfo=timezone.utc))]
    with patch("app.services.tm_resolver.query",
               side_effect=[meta_rows, hands_rows]) as m:
        tn, candidates = resolve_tournament_number(
            "Winamax", "Winamax Daily $50", "2026-05-09T13:30:00Z",
        )
    assert tn == "987654321"
    assert candidates == []
    assert m.call_count == 2


def test_resolve_prefers_meta_when_meta_has_match():
    """Meta retorna 1 row -> hands query NAO e chamada (call_count == 1)."""
    meta_rows = [_row("281416137", "BBG $215",
                      datetime(2026, 5, 5, 18, 30, tzinfo=timezone.utc))]
    with patch("app.services.tm_resolver.query", return_value=meta_rows) as m:
        tn, candidates = resolve_tournament_number(
            "GGPoker", "BBG $215", "2026-05-05T18:30:00Z",
        )
    assert tn == "281416137"
    assert candidates == []
    assert m.call_count == 1


def test_resolve_fallback_query_uses_group_by_against_hands():
    """SQL da 2a call: FROM hands, GROUP BY, study_state filter, regra 2026."""
    with patch("app.services.tm_resolver.query",
               side_effect=[[], []]) as m:
        resolve_tournament_number(
            "Winamax", "Winamax Daily $50", "2026-05-09T13:30:00Z",
        )
    assert m.call_count == 2
    sql_2nd = m.call_args_list[1][0][0]
    assert "FROM hands" in sql_2nd
    assert "GROUP BY tournament_number" in sql_2nd
    assert "study_state != 'mtt_archive'" in sql_2nd
    assert "played_at >= '2026-01-01'" in sql_2nd


def test_resolve_winamax_with_posted_at_hint_only():
    """Combinado: Winamax + meta vazio + posted_at_hint -> fallback hands
    com janela [posted-12h, posted-30min] aplicada a hands."""
    meta_rows: list[dict] = []
    hands_rows = [_row("987654321", "Winamax Daily $50",
                       datetime(2026, 5, 9, 8, 0, tzinfo=timezone.utc))]
    posted = datetime(2026, 5, 9, 14, 0, tzinfo=timezone.utc)
    with patch("app.services.tm_resolver.query",
               side_effect=[meta_rows, hands_rows]) as m:
        tn, candidates = resolve_tournament_number(
            "Winamax", "Winamax Daily $50", None,
            posted_at_hint=posted,
        )
    assert tn == "987654321"
    assert candidates == []
    assert m.call_count == 2
    sql_args_2nd = m.call_args_list[1][0][1]
    lo, hi = sql_args_2nd[2], sql_args_2nd[3]
    assert lo == datetime(2026, 5, 9, 2, 0, tzinfo=timezone.utc)
    assert hi == datetime(2026, 5, 9, 13, 30, tzinfo=timezone.utc)
