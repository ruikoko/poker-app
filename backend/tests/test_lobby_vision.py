"""Unit tests para services/lobby_vision (FASE A COMMIT 2).

Cobre funcoes puras: apply_ratio_lookup, parse_and_validate_lobby_json,
build_hrc_payouts_blob. NAO chama Anthropic API — extract_lobby_payout_json
fica para integration tests/manual smoke.
"""
import json

from app.services.lobby_vision import (
    apply_ratio_lookup,
    parse_and_validate_lobby_json,
    build_hrc_payouts_blob,
)


# -- apply_ratio_lookup ------------------------------------------------------

def test_lookup_monster_bounties():
    assert apply_ratio_lookup(
        "$215 Sunday Bounty Overload [Monster Bounties]"
    ) == ("PKO", 0.75)


def test_lookup_monster_ko():
    assert apply_ratio_lookup("Sunday Monster KO $50") == ("PKO", 0.75)


def test_lookup_super_ko():
    assert apply_ratio_lookup("Super KO $215") == ("PKO", 0.40)


def test_lookup_mystery_bounty_explicit():
    assert apply_ratio_lookup(
        "$108 Sunday Showdown [Mystery Bounty]"
    ) == ("KO", 0.33)


def test_lookup_mystery_big_bounty_edge_case():
    # "Mystery Big Bounty" — substring "mystery bounty" nao casa exacto,
    # mas a regra eh "mystery" AND ("bounty" or "ko"). Apanha como KO 33%.
    assert apply_ratio_lookup(
        "$150 Wednesday Golden Vault [Mystery Big Bounty]"
    ) == ("KO", 0.33)


def test_lookup_bounty_hunters():
    assert apply_ratio_lookup("Bounty Hunters Big Game $215") == ("PKO", 0.50)


def test_lookup_knockout():
    assert apply_ratio_lookup("Saturday Knockout $150 [Bounty]") == ("PKO", 0.50)


def test_lookup_bracket_bounty():
    assert apply_ratio_lookup("Thursday Throwdown $150 [Bounty]") == ("PKO", 0.50)


def test_lookup_bounty_catchall():
    assert apply_ratio_lookup("$44 Bounty Forty Stack") == ("PKO", 0.50)


def test_lookup_vanilla_no_keyword():
    assert apply_ratio_lookup("Daily Hyper $30") == ("None", 0.0)


def test_lookup_empty_name_defaults_to_none():
    assert apply_ratio_lookup("") == ("None", 0.0)


def test_lookup_is_case_insensitive():
    assert apply_ratio_lookup("BOUNTY HUNTERS DEEPSTACK $54") == ("PKO", 0.50)


# -- parse_and_validate_lobby_json -------------------------------------------

def _good_json():
    return json.dumps({
        "site": "GGPoker",
        "tournament_name": "Bounty Hunters Big Game $215",
        "start_time_iso": "2026-05-05T18:30:00Z",
        "starting_stack": 25000,
        "entrants": 2996,
        "buy_in": 215.0,
        "prizes": {"1": 9119.22, "2": 9118.84},
        "bounty_type_text": "PKO 50%",
    })


def test_parse_valid_json_round_trip():
    result = parse_and_validate_lobby_json(_good_json())
    assert result is not None
    assert result["tournament_name"] == "Bounty Hunters Big Game $215"
    assert result["prizes"]["1"] == 9119.22


def test_parse_returns_none_for_malformed_json():
    assert parse_and_validate_lobby_json("{not valid json") is None


def test_parse_returns_none_for_non_dict_top_level():
    assert parse_and_validate_lobby_json("[1, 2, 3]") is None


def test_parse_returns_none_for_missing_tournament_name():
    bad = json.dumps({"prizes": {"1": 100}})
    assert parse_and_validate_lobby_json(bad) is None


def test_parse_returns_none_for_empty_prizes():
    bad = json.dumps({"tournament_name": "X", "prizes": {}})
    assert parse_and_validate_lobby_json(bad) is None


def test_parse_returns_none_for_non_digit_prize_key():
    bad = json.dumps({"tournament_name": "X", "prizes": {"1st": 100.0}})
    assert parse_and_validate_lobby_json(bad) is None


def test_parse_returns_none_for_empty_or_none_input():
    assert parse_and_validate_lobby_json(None) is None
    assert parse_and_validate_lobby_json("") is None


# -- build_hrc_payouts_blob --------------------------------------------------

def test_build_blob_pko_with_full_chips_calc():
    vj = json.loads(_good_json())
    blob = build_hrc_payouts_blob(vj)
    assert blob["name"] == "/"
    assert blob["folders"] == []
    assert len(blob["structures"]) == 1
    s = blob["structures"][0]
    assert s["name"] == "Bounty Hunters Big Game $215"
    assert s["bountyType"] == "PKO"
    assert s["progressiveFactor"] == 0.5
    assert s["chips"] == 25000.0 * 2996.0  # 74_900_000.0
    assert s["prizes"] == {"1": 9119.22, "2": 9118.84}


def test_build_blob_vanilla_returns_none_bounty():
    vj = {
        "tournament_name": "Daily Hyper $30",
        "starting_stack": 5000,
        "entrants": 100,
        "prizes": {"1": 100.0},
    }
    blob = build_hrc_payouts_blob(vj)
    s = blob["structures"][0]
    assert s["bountyType"] == "None"
    assert s["progressiveFactor"] == 0.0


def test_build_blob_chips_none_when_entrants_missing():
    vj = {
        "tournament_name": "Bounty Hunters $54",
        "starting_stack": 25000,
        "entrants": None,
        "prizes": {"1": 100.0},
    }
    blob = build_hrc_payouts_blob(vj)
    assert blob["structures"][0]["chips"] is None


def test_build_blob_mystery_classifies_as_KO_33():
    vj = {
        "tournament_name": "$108 Sunday Showdown [Mystery Bounty]",
        "starting_stack": 25000,
        "entrants": 1000,
        "prizes": {"1": 100.0},
    }
    blob = build_hrc_payouts_blob(vj)
    s = blob["structures"][0]
    assert s["bountyType"] == "KO"
    assert s["progressiveFactor"] == 0.33
