"""Tests do #GOLD-BOUNTY-CARRY: enrich copia a coroa + backfill preenche/guarda."""
from unittest.mock import patch, MagicMock

from app.routers import screenshot
from app.routers.screenshot import _enrich_all_players_actions


def test_enrich_carries_bounty_value_usd():
    apa = {"_meta": {"bb": 100}, "hashA": {"position": "BTN", "stack": 5}}
    anon_map = {"hashA": "Xatab4ik"}
    vision = {"players_list": [
        {"name": "Xatab4ik", "bounty_value_usd": 40.0, "bounty_pct": 40, "country": "RU"}]}
    out = _enrich_all_players_actions(apa, anon_map, vision)
    assert out["Xatab4ik"]["bounty_value_usd"] == 40.0     # coroa copiada
    assert out["Xatab4ik"]["real_name"] == "Xatab4ik"      # nome mantido
    assert out["_meta"] == {"bb": 100}                     # _meta intacto


def test_enrich_defaults_bounty_zero_when_absent():
    apa = {"hashA": {"position": "BTN"}}
    out = _enrich_all_players_actions(apa, {"hashA": "X"}, {"players_list": []})
    assert out["X"]["bounty_value_usd"] == 0               # sem vision → 0 (não parte)


def _run_backfill(base_rows, hands):
    def q(sql, params=None):
        return base_rows if "tournament_summaries" in sql else hands
    with patch.object(screenshot, "query", side_effect=q), \
         patch.object(screenshot, "get_conn") as mc:
        res = screenshot.backfill_gold_bounties(dry_run=True)
    return res, mc


def test_backfill_fills_guards_halfbase_and_skips_hero0():
    base_rows = [{"tournament_number": "T1", "buy_in_bounty": 40.0}]   # floor = 20
    apa = {"_meta": {}, "Xatab4ik": {"real_name": "Xatab4ik"},
           "Danick_": {"real_name": "Danick_"}, "Lauro": {"real_name": "Lauro"}}
    entry = [{"name": "Xatab4ik", "bounty_value_usd": 40.0},   # ok
             {"name": "Danick_", "bounty_value_usd": 10.0},    # 10 < 20 → rejeitado
             {"name": "Lauro", "bounty_value_usd": 0.0}]       # Hero-a-0 → salta
    hands = [{"id": 1, "hand_id": "GG-1", "tournament_number": "T1",
              "all_players_actions": apa, "entry_players": entry}]
    res, mc = _run_backfill(base_rows, hands)
    assert res["players_filled"] == 1                      # só Xatab4ik
    assert res["players_rejected_below_half"] == 1         # Danick_ (10 < 20)
    assert res["hands_filled"] == 1
    assert apa["Xatab4ik"]["bounty_value_usd"] == 40.0     # escrito no dict
    assert "bounty_value_usd" not in apa["Danick_"]        # rejeitado, não escrito
    assert "bounty_value_usd" not in apa["Lauro"]          # Hero-0 saltado
    mc.assert_not_called()                                 # dry_run NÃO escreve


def test_backfill_no_base_still_fills_but_flags():
    # sem TS base → não há floor; escreve cru, mas conta em hands_without_ts_base.
    apa = {"A": {"real_name": "A"}}
    hands = [{"id": 2, "hand_id": "GG-2", "tournament_number": "T9",
              "all_players_actions": apa,
              "entry_players": [{"name": "A", "bounty_value_usd": 5.0}]}]
    res, _ = _run_backfill([], hands)                      # base map vazio
    assert res["players_filled"] == 1
    assert res["hands_without_ts_base"] == 1
    assert apa["A"]["bounty_value_usd"] == 5.0
