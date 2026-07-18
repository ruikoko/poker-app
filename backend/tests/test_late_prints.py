"""Painel 'Prints fora de tempo' (read-only): capturas em mãos com flop tiradas <20s do
início. Duas secções: impossible (<10s) e suspect (10-20s). prev = heurística de dona."""
from unittest.mock import patch
from app.routers import gg_health


def _row(ssid, iv_s, hid, db_id, folder="pos-pko", reason="filename_hand_id"):
    return {"ssid": ssid, "folder_tag": folder, "cap": f"2026-07-12 10:00:{iv_s:02d}",
            "reason_detail": reason, "db_id": db_id, "hand_id": hid,
            "pa": "2026-07-12 10:00:00", "tn": "T1", "discord_tags": [folder],
            "hm3_tags": None, "raw": "Table '5' 8-max\n*** FLOP *** [Ah 2c 3d]"}


def test_split_impossible_suspect_and_exclude_20plus():
    main = [_row(1, 5, "GG-A", 11), _row(2, 15, "GG-B", 12, folder="icm", reason="single_tn"),
            _row(3, 25, "GG-C", 13, folder="nota")]  # 25s → excluída (>=20)
    # main query, depois 1 prev por linha que passa (<20s): A e B → 2 prev
    with patch.object(gg_health, "query", side_effect=[main, [], []]):
        res = gg_health.late_prints(current_user={})
    assert res["counts"] == {"impossible": 1, "suspect": 1}
    assert res["impossible"][0]["hand_id"] == "GG-A" and res["impossible"][0]["interval_s"] == 5
    assert res["impossible"][0]["match_method"] == "filename_hand_id"
    assert res["impossible"][0]["image_url"] == "/api/table-ss/image/1"
    assert res["suspect"][0]["hand_id"] == "GG-B" and res["suspect"][0]["interval_s"] == 15
    # a 25s não aparece em lado nenhum
    assert all(x["hand_id"] != "GG-C" for x in res["impossible"] + res["suspect"])


def test_boundary_10s_is_suspect_not_impossible():
    with patch.object(gg_health, "query", side_effect=[[_row(1, 10, "GG-X", 5)], []]):
        res = gg_health.late_prints(current_user={})
    assert res["counts"] == {"impossible": 0, "suspect": 1}   # 10s → suspect


def test_prev_hand_is_heuristic_candidate():
    main = [_row(1, 5, "GG-A", 11)]
    prev = [{"id": 99, "hand_id": "GG-PREV", "pa": "2026-07-12 09:58:00",
             "raw": "Table '5' 8-max\n*** FLOP *** [..]"}]
    with patch.object(gg_health, "query", side_effect=[main, prev]):
        res = gg_health.late_prints(current_user={})
    p = res["impossible"][0]["prev"]
    assert p["hand_id"] == "GG-PREV" and p["hand_db_id"] == 99 and p["had_flop"] is True


def test_prev_wrong_table_is_skipped():
    main = [_row(1, 5, "GG-A", 11)]  # mesa '5'
    prev = [{"id": 77, "hand_id": "GG-OTHER", "pa": "2026-07-12 09:59:00",
             "raw": "Table '9' 8-max\n*** FLOP ***"}]  # mesa '9' → não casa
    with patch.object(gg_health, "query", side_effect=[main, prev]):
        res = gg_health.late_prints(current_user={})
    assert res["impossible"][0]["prev"] is None
