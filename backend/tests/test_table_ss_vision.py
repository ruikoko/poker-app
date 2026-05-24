"""Unit tests para services/table_ss_vision (pt38 Fase A).

Cobre funcoes puras: parse_and_validate_table_ss_json, derive_captured_at,
coercoes. NAO chama Anthropic API (extract_table_ss_json fica para smoke).
"""
import json
from datetime import datetime, timezone

from app.services.table_ss_vision import (
    parse_and_validate_table_ss_json,
    derive_captured_at,
    _coerce_pos_int,
    _coerce_float,
)


# ── derive_captured_at (TZ Europe/Lisbon) ───────────────────────────────────

def test_derive_captured_at_winamax_west_dst():
    """23 Mai 2026 → WEST (UTC+1). 17:04:00 local = 16:04:00 UTC."""
    dt = derive_captured_at("Shot1-Winamax-20260523170400.png")
    assert dt == datetime(2026, 5, 23, 16, 4, 0, tzinfo=timezone.utc)


def test_derive_captured_at_gg():
    dt = derive_captured_at("Shot2-GGPoker-20260523172943.png")
    assert dt == datetime(2026, 5, 23, 16, 29, 43, tzinfo=timezone.utc)


def test_derive_captured_at_winter_no_dst():
    """15 Jan 2026 → WET (UTC+0). 12:00:00 local = 12:00:00 UTC."""
    dt = derive_captured_at("Shot-20260115120000.png")
    assert dt == datetime(2026, 1, 15, 12, 0, 0, tzinfo=timezone.utc)


def test_derive_captured_at_no_digits():
    assert derive_captured_at("no_timestamp_here.png") is None


def test_derive_captured_at_invalid_date():
    # 14 dígitos mas mês 99 -> strptime falha
    assert derive_captured_at("Shot-20269923170400.png") is None


def test_derive_captured_at_none_filename():
    assert derive_captured_at(None) is None


# ── coercoes ─────────────────────────────────────────────────────────────────

def test_coerce_pos_int():
    assert _coerce_pos_int(71) == 71
    assert _coerce_pos_int("71") == 71
    assert _coerce_pos_int(0) is None
    assert _coerce_pos_int(-3) is None
    assert _coerce_pos_int(True) is None
    assert _coerce_pos_int(None) is None
    assert _coerce_pos_int("abc") is None


def test_coerce_float():
    assert _coerce_float(100.8) == 100.8
    assert _coerce_float(101) == 101.0
    assert _coerce_float("100.8") == 100.8
    assert _coerce_float(True) is None
    assert _coerce_float(None) is None
    assert _coerce_float("x") is None


# ── parse_and_validate_table_ss_json ────────────────────────────────────────

def _winamax_json():
    return json.dumps({
        "site": "Winamax",
        "tournament_name": "ODYSSEY #013",
        "tournament_buy_in": "€50",
        "blinds_level": {"small_blind": 100, "big_blind": 200, "ante": 25},
        "players_left": 71,
        "total_entries": 124,
        "itm_places": 16,
        "average_stack_bb": 100.8,
        "hero_stack_bb": 98.6,
        "hero_position": "BB",
        "hero_nick": "thinvalium",
    })


def test_parse_valid_round_trip_and_coerces():
    r = parse_and_validate_table_ss_json(_winamax_json())
    assert r is not None
    assert r["site"] == "Winamax"
    assert r["tournament_name"] == "ODYSSEY #013"
    assert r["players_left"] == 71
    assert r["total_entries"] == 124
    assert r["itm_places"] == 16
    assert r["average_stack_bb"] == 100.8
    assert r["hero_stack_bb"] == 98.6


def test_parse_malformed_json():
    assert parse_and_validate_table_ss_json("{not valid") is None


def test_parse_non_dict_top_level():
    assert parse_and_validate_table_ss_json("[1,2,3]") is None


def test_parse_none_or_empty():
    assert parse_and_validate_table_ss_json(None) is None
    assert parse_and_validate_table_ss_json("") is None


def test_parse_no_useful_fields_rejected():
    bad = json.dumps({"foo": 1, "blinds_level": {}})
    assert parse_and_validate_table_ss_json(bad) is None


def test_parse_only_players_left_accepted():
    """Sem name nem site, mas com players_left -> aceite (campo crítico)."""
    raw = json.dumps({"players_left": 313})
    r = parse_and_validate_table_ss_json(raw)
    assert r is not None
    assert r["players_left"] == 313


def test_parse_only_site_accepted():
    raw = json.dumps({"site": "GGPoker"})
    r = parse_and_validate_table_ss_json(raw)
    assert r is not None
    assert r["site"] == "GGPoker"


def test_parse_negative_players_left_coerced_to_none_but_name_keeps_row():
    raw = json.dumps({"tournament_name": "X", "players_left": -5})
    r = parse_and_validate_table_ss_json(raw)
    assert r is not None
    assert r["players_left"] is None


def test_parse_players_left_as_string():
    raw = json.dumps({"tournament_name": "X", "players_left": "71"})
    r = parse_and_validate_table_ss_json(raw)
    assert r is not None
    assert r["players_left"] == 71
