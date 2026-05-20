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
    _expand_prize_ranges,
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


# -- B2.1: prize_pool field (opcional, sem validacao especifica) -------------

def test_parse_accepts_prize_pool_when_present():
    """Vision le 'Total Prize Pool'; campo opcional novo no schema."""
    raw = json.dumps({
        "site": "GGPoker",
        "tournament_name": "Bounty Hunters Big Game $215",
        "prize_pool": 644713.55,
        "entrants": 2996,
        "prizes": {"1": 9119.22},
    })
    result = parse_and_validate_lobby_json(raw)
    assert result is not None
    assert result["prize_pool"] == 644713.55


def test_parse_accepts_when_prize_pool_missing():
    """Compat: JSONs sem prize_pool (Vision falhou ler) ainda validam."""
    raw = json.dumps({
        "tournament_name": "Daily Hyper $80",
        "prizes": {"1": 100.0},
    })
    result = parse_and_validate_lobby_json(raw)
    assert result is not None
    assert "prize_pool" not in result or result.get("prize_pool") is None


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


# ── pt29 Fase A extension: prize_ranges expansion ──────────────────────────

def test_expand_prize_ranges_singles_only_passthrough():
    """Sem ranges -> singles passam intactos (cast para float)."""
    out = _expand_prize_ranges({"1": 1000.0, "2": 500.0}, [])
    assert out == {"1": 1000.0, "2": 500.0}


def test_expand_prize_ranges_simple_range():
    """`11 ~ 12: 3880.46` -> {"11": 3880.46, "12": 3880.46}."""
    out = _expand_prize_ranges(
        {},
        [{"rank_from": 11, "rank_to": 12, "amount": 3880.46}],
    )
    assert out == {"11": 3880.46, "12": 3880.46}


def test_expand_prize_ranges_combines_singles_and_ranges():
    """Singles + ranges em conjunto. Singles override ranges para mesma rank."""
    out = _expand_prize_ranges(
        {"1": 10000.0, "2": 5000.0, "11": 9999.0},  # 11 e single, override
        [
            {"rank_from": 11, "rank_to": 12, "amount": 3880.46},  # 11 vai ser overrided
            {"rank_from": 13, "rank_to": 16, "amount": 2938.95},
        ],
    )
    assert out["1"] == 10000.0
    assert out["2"] == 5000.0
    assert out["11"] == 9999.0   # single ganha
    assert out["12"] == 3880.46
    assert out["13"] == 2938.95
    assert out["14"] == 2938.95
    assert out["15"] == 2938.95
    assert out["16"] == 2938.95


def test_expand_prize_ranges_invalid_skipped_silently():
    """Ranges com tipos errados / valores invalidos sao skippadas."""
    out = _expand_prize_ranges(
        {"1": 1000.0},
        [
            {"rank_from": "x", "rank_to": 5, "amount": 100.0},  # rank_from non-int
            {"rank_from": 5, "rank_to": 3, "amount": 100.0},     # rank_to < rank_from
            {"rank_from": 0, "rank_to": 2, "amount": 100.0},     # rank_from < 1
            {"rank_from": 2, "rank_to": 3, "amount": None},      # amount None
            {"rank_from": 2, "rank_to": 3, "amount": "bad"},     # amount non-float
            {"not_a_dict": True},                                  # not dict
            "string",                                              # not dict
        ],
    )
    # Apenas o single foi preservado.
    assert out == {"1": 1000.0}


def test_expand_prize_ranges_full_GG_5944816316_payout_structure():
    """Mao baseline pt27-pt29: ranks 1-10 individuais + 8 ranges agrupados
    cobrindo 11-180. Total: 180 entries."""
    singles = {
        "1": 50000.0, "2": 35000.0, "3": 25000.0, "4": 18000.0, "5": 13000.0,
        "6": 9500.0, "7": 7000.0, "8": 5500.0, "9": 4500.0, "10": 3800.0,
    }
    ranges = [
        {"rank_from": 11, "rank_to": 12, "amount": 3880.46},
        {"rank_from": 13, "rank_to": 16, "amount": 2938.95},
        {"rank_from": 17, "rank_to": 22, "amount": 2225.84},
        {"rank_from": 23, "rank_to": 32, "amount": 1685.84},
        {"rank_from": 33, "rank_to": 48, "amount": 1276.91},
        {"rank_from": 49, "rank_to": 72, "amount": 967.07},
        {"rank_from": 73, "rank_to": 114, "amount": 732.31},
        {"rank_from": 115, "rank_to": 180, "amount": 554.65},
    ]
    out = _expand_prize_ranges(singles, ranges)
    assert len(out) == 180
    # Sanity: amostra de ranks dentro de varios ranges
    assert out["1"] == 50000.0
    assert out["10"] == 3800.0
    assert out["11"] == 3880.46
    assert out["12"] == 3880.46
    assert out["13"] == 2938.95
    assert out["22"] == 2225.84
    assert out["72"] == 967.07
    assert out["73"] == 732.31
    assert out["114"] == 732.31
    assert out["115"] == 554.65
    assert out["180"] == 554.65


def test_expand_prize_ranges_empty_inputs():
    """Ambos vazios -> dict vazio (caller decide)."""
    assert _expand_prize_ranges({}, []) == {}
    assert _expand_prize_ranges(None, None) == {}


# ── pt29 Fase A extension: chips = average_stack * players_left ──────────

def test_build_blob_chips_uses_average_stack_times_players_left():
    """Mid-tournament: chips reais = avg × left. Preferido vs starting × entrants."""
    vj = {
        "tournament_name": "Bounty Hunters Big Game $215",
        "average_stack": 179530,
        "players_left": 365,
        # Nao usados quando avg+left presentes
        "starting_stack": 25000,
        "entrants": 1552,
        "prizes": {"1": 100.0},
    }
    blob = build_hrc_payouts_blob(vj)
    assert blob["structures"][0]["chips"] == 179530 * 365  # 65_528_450


def test_build_blob_chips_fallback_to_starting_times_entrants():
    """Sem avg_stack ou players_left -> fallback legacy."""
    vj = {
        "tournament_name": "Bounty Hunters Big Game $215",
        "starting_stack": 25000,
        "entrants": 1552,
        "prizes": {"1": 100.0},
    }
    blob = build_hrc_payouts_blob(vj)
    assert blob["structures"][0]["chips"] == 25000 * 1552  # 38_800_000


def test_build_blob_chips_fallback_when_only_avg_present():
    """avg_stack mas players_left ausente -> fallback (precisamos dos dois)."""
    vj = {
        "tournament_name": "Daily $50",
        "average_stack": 50000,
        "players_left": None,
        "starting_stack": 10000,
        "entrants": 500,
        "prizes": {"1": 100.0},
    }
    blob = build_hrc_payouts_blob(vj)
    assert blob["structures"][0]["chips"] == 10000 * 500


def test_build_blob_chips_none_when_no_source_available():
    """Sem fonte alguma -> None (graceful)."""
    vj = {
        "tournament_name": "Daily $50",
        "prizes": {"1": 100.0},
    }
    blob = build_hrc_payouts_blob(vj)
    assert blob["structures"][0]["chips"] is None


def test_build_blob_prizes_expanded_from_ranges():
    """prize_ranges sao expandidos no blob final (HRC ve a lista completa)."""
    vj = {
        "tournament_name": "Big Game $215",
        "prizes": {"1": 50000.0, "2": 35000.0},
        "prize_ranges": [
            {"rank_from": 3, "rank_to": 5, "amount": 20000.0},
        ],
    }
    blob = build_hrc_payouts_blob(vj)
    prizes = blob["structures"][0]["prizes"]
    assert prizes == {"1": 50000.0, "2": 35000.0, "3": 20000.0, "4": 20000.0, "5": 20000.0}


def test_build_blob_places_paid_mismatch_logs_warn_but_continues(caplog):
    """places_paid declarado != entries pos-expansao -> WARN log mas blob
    continua a sair (graceful, nao raise)."""
    import logging as _logging
    caplog.set_level(_logging.WARNING, logger="lobby_vision")
    vj = {
        "tournament_name": "Big Game $215",
        "places_paid": 180,  # declarado mas so vamos ter 5 entries
        "prizes": {"1": 50000.0, "2": 35000.0},
        "prize_ranges": [
            {"rank_from": 3, "rank_to": 5, "amount": 20000.0},
        ],
    }
    blob = build_hrc_payouts_blob(vj)
    # Blob saiu mesmo assim
    assert len(blob["structures"][0]["prizes"]) == 5
    # WARN registado
    assert any("places_paid mismatch" in r.message for r in caplog.records)


def test_build_blob_places_paid_match_no_warn(caplog):
    """places_paid == entries -> sem WARN."""
    import logging as _logging
    caplog.set_level(_logging.WARNING, logger="lobby_vision")
    vj = {
        "tournament_name": "Daily $50",
        "places_paid": 2,
        "prizes": {"1": 100.0, "2": 50.0},
    }
    build_hrc_payouts_blob(vj)
    assert not any("places_paid mismatch" in r.message for r in caplog.records)


# ── pt29 Fase A extension: parse_and_validate accepts new fields ──────────

def test_parse_accepts_prize_ranges_without_singles():
    """Schema novo: prizes pode ser vazio se prize_ranges populado."""
    raw = json.dumps({
        "tournament_name": "Big Game $215",
        "prizes": {},
        "prize_ranges": [
            {"rank_from": 1, "rank_to": 10, "amount": 1000.0},
        ],
    })
    result = parse_and_validate_lobby_json(raw)
    assert result is not None
    assert result["prize_ranges"][0]["rank_from"] == 1


def test_parse_accepts_singles_without_prize_ranges():
    """Compat: schema antigo (so prizes singles) continua a validar."""
    raw = json.dumps({
        "tournament_name": "Daily $30",
        "prizes": {"1": 100.0},
    })
    result = parse_and_validate_lobby_json(raw)
    assert result is not None


def test_parse_rejects_both_empty():
    """prizes={} e prize_ranges=[] -> rejeita (nao ha payout info nenhum)."""
    raw = json.dumps({
        "tournament_name": "X",
        "prizes": {},
        "prize_ranges": [],
    })
    assert parse_and_validate_lobby_json(raw) is None


def test_parse_rejects_prize_ranges_wrong_type():
    """prize_ranges deve ser lista; dict ou string -> rejeita."""
    raw = json.dumps({
        "tournament_name": "X",
        "prizes": {"1": 100.0},
        "prize_ranges": "should be a list",
    })
    assert parse_and_validate_lobby_json(raw) is None


def test_parse_accepts_average_stack_and_places_paid():
    """Campos opcionais novos preservados no dict de retorno."""
    raw = json.dumps({
        "tournament_name": "Big Game $215",
        "average_stack": 179530,
        "places_paid": 180,
        "players_left": 365,
        "prizes": {"1": 50000.0},
        "prize_ranges": [
            {"rank_from": 2, "rank_to": 180, "amount": 1000.0},
        ],
    })
    result = parse_and_validate_lobby_json(raw)
    assert result is not None
    assert result["average_stack"] == 179530
    assert result["places_paid"] == 180


# ── End-to-end: mao baseline GG-5944816316 ──────────────────────────────

def test_end_to_end_GG_5944816316_full_pipeline():
    """Smoke real do briefing pt29 Fase A: a partir do JSON Vision que o
    Sonnet devolveria para o screenshot do lobby de GG-5944816316,
    validar que build_hrc_payouts_blob produz:
      - chips = 179,530 × 365 = 65,528,450 (avg_stack × players_left)
      - prizes com 180 entries (10 singles + 170 expandidos de 8 ranges)
      - bountyType="PKO", progressiveFactor=0.5 ("Bounty Hunters")
      - places_paid bate com prize count -> sem WARN
    """
    vision_json = {
        "site": "GGPoker",
        "tournament_name": "Bounty Hunters Big Game $525",
        "start_time_iso": "2026-05-12T21:00:00Z",
        "starting_stack": 30000,
        "entrants": 1552,
        "players_left": 365,
        "average_stack": 179530,
        "places_paid": 180,
        "prize_pool": 776000.00,
        "buy_in": 525.0,
        "prizes": {
            "1": 50000.0, "2": 35000.0, "3": 25000.0, "4": 18000.0, "5": 13000.0,
            "6": 9500.0, "7": 7000.0, "8": 5500.0, "9": 4500.0, "10": 3800.0,
        },
        "prize_ranges": [
            {"rank_from": 11, "rank_to": 12, "amount": 3880.46},
            {"rank_from": 13, "rank_to": 16, "amount": 2938.95},
            {"rank_from": 17, "rank_to": 22, "amount": 2225.84},
            {"rank_from": 23, "rank_to": 32, "amount": 1685.84},
            {"rank_from": 33, "rank_to": 48, "amount": 1276.91},
            {"rank_from": 49, "rank_to": 72, "amount": 967.07},
            {"rank_from": 73, "rank_to": 114, "amount": 732.31},
            {"rank_from": 115, "rank_to": 180, "amount": 554.65},
        ],
        "bounty_type_text": "PKO 50%",
    }
    blob = build_hrc_payouts_blob(vision_json)
    s = blob["structures"][0]

    # chips real mid-tournament
    assert s["chips"] == 179530 * 365 == 65_528_450

    # 180 entries (10 + 2 + 4 + 6 + 10 + 16 + 24 + 42 + 66 = 180)
    assert len(s["prizes"]) == 180

    # Amostra
    assert s["prizes"]["1"] == 50000.0
    assert s["prizes"]["180"] == 554.65
    assert s["prizes"]["72"] == 967.07
    assert s["prizes"]["73"] == 732.31

    # Bounty classification
    assert s["bountyType"] == "PKO"
    assert s["progressiveFactor"] == 0.5

    # Tournament name preservado
    assert s["name"] == "Bounty Hunters Big Game $525"
