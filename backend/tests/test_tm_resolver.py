"""Unit tests para services/tm_resolver.resolve_tournament_number (FASE A C2).
Mocked DB via patch a app.services.tm_resolver.query."""
from unittest.mock import patch
from datetime import datetime, timezone

from app.services.tm_resolver import resolve_tournament_number


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


def test_resolve_substring_match_passes_through_to_sql():
    """Caller diz 'BBG $215'; SQL recebe '%BBG $215%' como ILIKE pattern."""
    rows = [_row("281416137", "Bounty Hunters Big Game $215",
                 datetime(2026, 5, 5, 18, 30, tzinfo=timezone.utc))]
    with patch("app.services.tm_resolver.query", return_value=rows) as m:
        resolve_tournament_number("GGPoker", "BBG $215", "2026-05-05T18:30:00Z")
    args = m.call_args[0]
    sql_args = args[1]
    assert sql_args[0] == "GGPoker"
    assert sql_args[1] == "%BBG $215%"


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
