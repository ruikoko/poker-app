"""Painel 'Imagens sem tag — Gold e capturas' (read-only). Duas populações disjuntas
(gold_no_tag vs marcadas) + vizinha tagada mais próxima (hipótese do print atrasado)."""
from datetime import datetime
from unittest.mock import patch
from app.routers import gg_health


def _idx():
    return {"T1": [
        (datetime.fromisoformat("2026-06-25 17:32:00"), "GG-A", 101, ["pos-pko"]),
        (datetime.fromisoformat("2026-06-25 17:40:00"), "GG-B", 102, ["nota"]),
    ]}


def test_nearest_within_cap_after():
    # mão sem tag às 17:31:00 → vizinha tagada GG-A às 17:32:00 (60 s DEPOIS)
    n = gg_health._nearest_tagged("T1", "2026-06-25 17:31:00", _idx())
    assert n["hand_id"] == "GG-A" and n["diff_seconds"] == 60 and n["is_after"] is True
    assert n["tags"] == ["pos-pko"]


def test_nearest_before():
    # 17:32:30 → GG-A às 17:32:00 (30 s ANTES)
    n = gg_health._nearest_tagged("T1", "2026-06-25 17:32:30", _idx())
    assert n["hand_id"] == "GG-A" and n["diff_seconds"] == 30 and n["is_after"] is False


def test_nearest_beyond_cap_is_none():
    # 17:36:00 → GG-A a 240 s, GG-B a 240 s → ambos > 180 s → vazio
    assert gg_health._nearest_tagged("T1", "2026-06-25 17:36:00", _idx()) is None


def test_nearest_no_tagged_in_tournament():
    assert gg_health._nearest_tagged("T_SEM", "2026-06-25 17:31:00", _idx()) is None


def test_untagged_row_hero_position_from_apa():
    r = {"id": 1, "hand_id": "GG-X", "tournament_name": "Daily", "buy_in": "$46+$4",
         "played_at": "2026-06-25 17:31:00", "tn": "T1",
         "apa": {"Hero": {"real_name": "Lauro Dermio", "position": "BTN"}}}
    out = gg_health._untagged_row(r, "gold", "/api/screenshots/image/9", _idx())
    assert out["hero_position"] == "BTN" and out["source"] == "gold"
    assert out["nearest_tagged"]["hand_id"] == "GG-A"     # vizinha a 60 s


def test_endpoint_two_disjoint_lists():
    tagged = [{"tn": "T1", "hand_id": "GG-A", "db_id": 101, "pa": "2026-06-25 17:32:00",
               "discord_tags": ["pos-pko"], "hm3_tags": None}]
    gold_rows = [{"id": 10, "hand_id": "GG-G1", "tournament_name": "Daily", "tn": "T1",
                  "played_at": "2026-06-25 17:31:00", "all_players_actions": {}, "ss_id": 5,
                  "buy_in": "$46+$4"}]
    cap_rows = [{"id": 20, "hand_id": "GG-C1", "tournament_name": "Speed Racer", "tn": "T1",
                 "played_at": "2026-06-25 18:00:00", "all_players_actions": {},
                 "ss_id": 7, "vj": {"hero_position": "CO"}, "buy_in": "$32"}]
    with patch.object(gg_health, "query", side_effect=[tagged, gold_rows, cap_rows]):
        res = gg_health.untagged_images(current_user={})
    assert res["counts"] == {"gold": 1, "captures": 1}
    assert res["gold"][0]["source"] == "gold"
    assert res["gold"][0]["image_url"] == "/api/screenshots/image/5"
    assert res["gold"][0]["nearest_tagged"]["hand_id"] == "GG-A"   # 60 s da tagada
    assert res["captures"][0]["source"] == "table_ss"
    assert res["captures"][0]["hero_position"] == "CO"             # da vision_json
    assert res["captures"][0]["nearest_tagged"] is None            # 18:00 > 180 s da tagada
