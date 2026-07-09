"""#CROWN-VISIBLE-READ-ZERO (Opção C, parte 1) — backfill da coroa table-SS→mão.
Regra: Gold manda, mas $0 do Gold cai para a table-SS SE ≥ base÷2; nunca inverte
uma leitura válida do Gold."""
from unittest.mock import patch
from app.routers import table_ss


def _run(base_rows, hands):
    def q(sql, params=None):
        return base_rows if "tournament_summaries" in sql else hands
    with patch.object(table_ss, "query", side_effect=q), \
         patch.object(table_ss, "get_conn"):
        return table_ss.backfill_crowns_from_capture(dry_run=True)


def test_fills_from_capture_when_gold_zero_and_not_invert_valid():
    base = [{"tournament_number": "T1", "buy_in_bounty": 15.0}]        # floor 7.5
    apa = {"_meta": {"bb": 100},
           "hashA": {"real_name": "RaresSD", "bounty_value_usd": 0.0},        # Gold $0
           "hashB": {"real_name": "Lauro Dermio", "bounty_value_usd": 250.0}}  # Gold válido
    pn = {"players_list": [{"name": "RaresSD", "bounty_value_usd": 0.0},
                           {"name": "Lauro Dermio", "bounty_value_usd": 250.0}]}
    tvj = {"seats": [{"nick": "RaresSD", "bounty_usd": 13.12},
                     {"nick": "Lauro Dermio", "bounty_usd": 250.0}]}
    res = _run(base, [{"id": 1, "hand_id": "GG-1", "tournament_number": "T1",
                       "apa": apa, "pn": pn, "tvj": tvj}])
    assert res["hands_filled"] == 1 and res["crowns_filled"] == 1
    assert apa["hashA"]["bounty_value_usd"] == 13.12                  # $0 preenchido
    assert apa["hashB"]["bounty_value_usd"] == 250.0                  # válido NÃO invertido
    assert pn["players_list"][0]["bounty_value_usd"] == 13.12         # player_names também


def test_rejects_capture_below_half():
    base = [{"tournament_number": "T1", "buy_in_bounty": 250.0}]      # floor 125
    apa = {"_meta": {}, "hashA": {"real_name": "X", "bounty_value_usd": 0.0}}
    pn = {"players_list": [{"name": "X", "bounty_value_usd": 0.0}]}
    tvj = {"seats": [{"nick": "X", "bounty_usd": 100.0}]}             # 100 < 125 → rejeita
    res = _run(base, [{"id": 1, "hand_id": "GG-1", "tournament_number": "T1",
                       "apa": apa, "pn": pn, "tvj": tvj}])
    assert res["hands_filled"] == 0 and res["rejected_below_half"] == 1
    assert apa["hashA"]["bounty_value_usd"] == 0.0


def test_skips_without_ts_base():
    base = []                                                          # sem TS
    apa = {"_meta": {}, "hashA": {"real_name": "X", "bounty_value_usd": 0.0}}
    pn = {"players_list": [{"name": "X", "bounty_value_usd": 0.0}]}
    tvj = {"seats": [{"nick": "X", "bounty_usd": 375.0}]}
    res = _run(base, [{"id": 1, "hand_id": "GG-1", "tournament_number": "T1",
                       "apa": apa, "pn": pn, "tvj": tvj}])
    assert res["hands_without_ts_base"] == 1 and res["hands_filled"] == 0


def test_capture_zero_crown_ignored():
    # a table-SS também leu $0 nesse seat → nada a preencher (fica p/ re-leitura do Gold)
    base = [{"tournament_number": "T1", "buy_in_bounty": 40.0}]
    apa = {"_meta": {}, "hashA": {"real_name": "Cornel", "bounty_value_usd": 0.0}}
    pn = {"players_list": [{"name": "Cornel", "bounty_value_usd": 0.0}]}
    tvj = {"seats": [{"nick": "Cornel", "bounty_usd": None}]}
    res = _run(base, [{"id": 1, "hand_id": "GG-1", "tournament_number": "T1",
                       "apa": apa, "pn": pn, "tvj": tvj}])
    assert res["hands_filled"] == 0
    assert apa["hashA"]["bounty_value_usd"] == 0.0
