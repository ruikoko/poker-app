"""Painel 'Prints fora de tempo' (read-only): capturas em mãos com flop tiradas <9s do
início (régua física: a mão nem chegou ao flop). Secção única. prev = heurística de dona.
A faixa 10-20s foi verificada pelo Rui (27 capturas, 0 erros) → removida."""
from unittest.mock import patch
from app.routers import gg_health


def _row(ssid, iv_s, hid, db_id, folder="pos-pko", reason="filename_hand_id"):
    return {"ssid": ssid, "folder_tag": folder, "cap": f"2026-07-12 10:00:{iv_s:02d}",
            "reason_detail": reason, "db_id": db_id, "hand_id": hid,
            "pa": "2026-07-12 10:00:00", "tn": "T1", "discord_tags": [folder],
            "hm3_tags": None, "raw": "Table '5' 8-max\n*** FLOP *** [Ah 2c 3d]"}


def test_keeps_under_9s_excludes_9_and_over():
    main = [_row(1, 8, "GG-A", 11),                     # 8s → dentro
            _row(2, 9, "GG-B", 12, folder="icm"),       # 9s → FORA (>=9)
            _row(3, 15, "GG-C", 13, folder="nota")]     # 15s → fora
    with patch.object(gg_health, "query", side_effect=[main, []]):  # 1 prev p/ GG-A
        res = gg_health.late_prints(current_user={})
    assert res["count"] == 1
    assert res["hands"][0]["hand_id"] == "GG-A" and res["hands"][0]["interval_s"] == 8
    assert all(h["hand_id"] not in ("GG-B", "GG-C") for h in res["hands"])


def test_no_suspect_section_in_response():
    with patch.object(gg_health, "query", side_effect=[[_row(1, 3, "GG-X", 5)], []]):
        res = gg_health.late_prints(current_user={})
    assert "hands" in res and "count" in res
    assert "suspect" not in res and "impossible" not in res      # secção única


def test_row_fields_and_image():
    with patch.object(gg_health, "query", side_effect=[[_row(7, 5, "GG-Y", 9)], []]):
        res = gg_health.late_prints(current_user={})
    h = res["hands"][0]
    assert h["match_method"] == "filename_hand_id"
    assert h["image_url"] == "/api/table-ss/image/7"
    assert h["tags"] == ["pos-pko"]


def test_prev_hand_is_heuristic_candidate():
    main = [_row(1, 5, "GG-A", 11)]
    prev = [{"id": 99, "hand_id": "GG-PREV", "pa": "2026-07-12 09:58:00",
             "raw": "Table '5' 8-max\n*** FLOP *** [..]"}]
    with patch.object(gg_health, "query", side_effect=[main, prev]):
        res = gg_health.late_prints(current_user={})
    p = res["hands"][0]["prev"]
    assert p["hand_id"] == "GG-PREV" and p["hand_db_id"] == 99 and p["had_flop"] is True


def test_prev_wrong_table_is_skipped():
    main = [_row(1, 5, "GG-A", 11)]                     # mesa '5'
    prev = [{"id": 77, "hand_id": "GG-OTHER", "pa": "2026-07-12 09:59:00",
             "raw": "Table '9' 8-max\n*** FLOP ***"}]   # mesa '9' → não casa
    with patch.object(gg_health, "query", side_effect=[main, prev]):
        res = gg_health.late_prints(current_user={})
    assert res["hands"][0]["prev"] is None
