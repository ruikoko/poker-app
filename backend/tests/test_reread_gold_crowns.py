"""#CROWN-VISIBLE-READ-ZERO parte 2 — re-leitura das coroas do Gold (Vision mockada)."""
import asyncio
from unittest.mock import patch
from app.routers import screenshot


def _run(base, hands, vision_players):
    def q(sql, params=None):
        return base if "tournament_summaries" in sql else hands
    with patch.object(screenshot, "query", side_effect=q), \
         patch.object(screenshot, "get_conn"), \
         patch.object(screenshot, "_extract_hand_data_from_image_claude", return_value="txt"), \
         patch.object(screenshot, "_parse_vision_response",
                      return_value={"players_list": vision_players}):
        return asyncio.run(screenshot.reread_gold_crowns(dry_run=True))


def test_reread_recovers_zero_crown_valid():
    base = [{"tournament_number": "T1", "buy_in_bounty": 15.0}]        # floor 7.5
    hands = [{"id": 1, "hand_id": "GG-1", "tournament_number": "T1",
              "apa": {"_meta": {}, "hashA": {"real_name": "RaresSD", "bounty_value_usd": 0.0}},
              "pn": {"players_list": [{"name": "RaresSD", "bounty_value_usd": 0.0}]},
              "img": "AAAA"}]
    res = _run(base, hands, [{"name": "RaresSD", "bounty_value_usd": 13.12}])
    assert res["targets"] == 1 and res["crowns_recovered"] == 1
    assert hands[0]["apa"]["hashA"]["bounty_value_usd"] == 13.12
    assert hands[0]["pn"]["players_list"][0]["bounty_value_usd"] == 13.12


def test_reread_rejects_below_half():
    base = [{"tournament_number": "T1", "buy_in_bounty": 250.0}]       # floor 125
    hands = [{"id": 1, "hand_id": "GG-1", "tournament_number": "T1",
              "apa": {"_meta": {}, "hashA": {"real_name": "X", "bounty_value_usd": 0.0}},
              "pn": {"players_list": [{"name": "X", "bounty_value_usd": 0.0}]},
              "img": "AAAA"}]
    res = _run(base, hands, [{"name": "X", "bounty_value_usd": 100.0}])   # 100 < 125
    assert res["crowns_recovered"] == 0
    assert hands[0]["apa"]["hashA"]["bounty_value_usd"] == 0.0


def test_reread_does_not_invert_valid_gold():
    base = [{"tournament_number": "T1", "buy_in_bounty": 15.0}]
    hands = [{"id": 1, "hand_id": "GG-1", "tournament_number": "T1",
              "apa": {"_meta": {}, "hashA": {"real_name": "Y", "bounty_value_usd": 200.0}},
              "pn": {"players_list": [{"name": "Y", "bounty_value_usd": 200.0}]},
              "img": "AAAA"}]
    res = _run(base, hands, [{"name": "Y", "bounty_value_usd": 8.0}])
    assert res["targets"] == 0                    # sem coroa $0 → nem entra
    assert hands[0]["apa"]["hashA"]["bounty_value_usd"] == 200.0
