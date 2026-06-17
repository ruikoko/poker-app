"""Wiring por-mão no enrich do replayer: gold image COM siglas → position_v3;
SEM siglas → stack-elimination legacy. Lacuna honesta nunca preenchida por stack
dentro de uma mão com gold image (usa-se o anon_map do position_v3 tal-e-qual)."""
import json
from unittest.mock import MagicMock, patch
from app.routers import screenshot as S


def _run_enrich(players_list):
    matched_hand = {
        "id": 10, "hand_id": "GG-1", "all_players_actions": {"89ef4cba": {"actions": []}},
        "position": None, "raw": "Poker Hand #TM1: ...", "stakes": "x",
        "hero_cards": [], "board": [], "player_names": {},
    }
    raw_json = {"hero": "Hero", "players_list": players_list, "file_meta": {},
                "vision_sb": None, "vision_bb": None}
    captured = []

    class _Cur:
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def execute(self, sql, params=None): captured.append((sql, params))
    conn = MagicMock(); conn.cursor.return_value = _Cur()

    with patch("app.routers.screenshot.query", return_value=[matched_hand]), \
         patch("app.routers.screenshot.get_conn", return_value=conn), \
         patch("app.routers.screenshot._build_anon_to_real_map_by_position",
               return_value={"anon_map": {"89ef4cba": "Alice", "Hero": "Hero"}}) as bypos, \
         patch("app.routers.screenshot._build_anon_to_real_map",
               return_value={"89ef4cba": "StackName", "Hero": "Hero"}) as bystack, \
         patch("app.routers.screenshot._enrich_all_players_actions", return_value={}), \
         patch("app.discord_bot._resolve_channel_name_for_entry", return_value=None), \
         patch("app.services.villain_rules.apply_villain_rules",
               return_value={"n_villains_created": 0, "n_villain_notes_upserts": 0}):
        S._enrich_hand_from_orphan_entry(entry_id=9, hand_db_id=10, raw_json=raw_json)

    upd = next((p for (s, p) in captured if "UPDATE hands SET player_names" in s), None)
    pn = json.loads(upd[0])  # 1º param = player_names_json
    return pn, bypos, bystack


def test_com_siglas_usa_position_v3():
    pn, bypos, bystack = _run_enrich(
        [{"name": "Alice", "position": "UTG"}, {"name": "Hero", "position": None}]
    )
    assert pn["match_method"] == "position_v3"
    bypos.assert_called_once()
    bystack.assert_not_called()
    assert pn["anon_map"]["89ef4cba"] == "Alice"   # nome por posição, não por stack


def test_sem_siglas_cai_no_stack_elimination():
    pn, bypos, bystack = _run_enrich(
        [{"name": "Alice", "position": None}, {"name": "Hero", "position": None}]
    )
    assert pn["match_method"] == "anchors_stack_elimination_v2"
    bystack.assert_called_once()
    bypos.assert_not_called()
    assert pn["anon_map"]["89ef4cba"] == "StackName"
