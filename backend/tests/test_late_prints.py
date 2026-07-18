"""Painel 'Prints fora de tempo' (read-only): régua na TAG (não na mão), print <9s, MESA
FINAL fora de tudo. DUAS listas: pos (impossível, com ou sem flop) e nota (facto, sem
impossibilidade). Outras tags (icm/speed-racer) ficam de fora. prev = heurística de dona."""
from unittest.mock import patch
from app.routers import gg_health


def _row(ssid, iv_s, hid, db_id, folder="pos-pko", reason="filename_hand_id",
         hand_tags=None, flop=True):
    raw = "Table '5' 8-max\n" + ("*** FLOP *** [Ah 2c 3d]" if flop else "*** SHOWDOWN ***")
    return {"ssid": ssid, "folder_tag": folder, "cap": f"2026-07-12 10:00:{iv_s:02d}",
            "reason_detail": reason, "db_id": db_id, "hand_id": hid,
            "pa": "2026-07-12 10:00:00", "tn": "T1",
            "discord_tags": hand_tags if hand_tags is not None else [folder],
            "hm3_tags": None, "raw": raw}


def test_pos_regardless_of_flop_and_nota_split():
    main = [
        _row(1, 7, "GG-POS-NOFLOP", 11, folder="pos-pko", flop=False),   # pos SEM flop → entra em pos
        _row(2, 3, "GG-POS-FLOP", 12, folder="pos-nko", flop=True),      # pos com flop → pos
        _row(3, 1, "GG-NOTA", 13, folder="nota", flop=False),           # nota → nota (sem impossibilidade)
        _row(4, 5, "GG-ICM", 14, folder="icm-pko", flop=True),          # icm → FORA das duas listas
    ]
    # 1 prev por linha que passa (<9s, não-FT): 4 linhas → 4 prev
    with patch.object(gg_health, "query", side_effect=[main, [], [], [], []]):
        res = gg_health.late_prints(current_user={})
    assert res["counts"] == {"pos": 2, "nota": 1}
    pos_ids = {h["hand_id"] for h in res["pos"]}
    assert pos_ids == {"GG-POS-NOFLOP", "GG-POS-FLOP"}       # pos entra com OU sem flop
    assert res["pos"][0]["had_flop"] in (True, False)        # had_flop mostrado, não filtra
    assert res["nota"][0]["hand_id"] == "GG-NOTA"
    assert all(h["hand_id"] != "GG-ICM" for h in res["pos"] + res["nota"])  # icm fora


def test_final_table_excluded_from_all():
    main = [
        _row(1, 5, "GG-FT", 20, folder="pos-pko-ft", hand_tags=["pos-pko-ft"]),  # -ft → FORA
        _row(2, 5, "GG-OK", 21, folder="pos-pko", hand_tags=["pos-pko"]),        # não-FT → pos
    ]
    with patch.object(gg_health, "query", side_effect=[main, []]):   # só GG-OK precisa de prev
        res = gg_health.late_prints(current_user={})
    assert res["counts"] == {"pos": 1, "nota": 0}
    assert res["pos"][0]["hand_id"] == "GG-OK"                       # o -ft não entra


def test_9s_boundary_excluded():
    with patch.object(gg_health, "query", side_effect=[[_row(1, 9, "GG-X", 5)], []]):
        res = gg_health.late_prints(current_user={})
    assert res["counts"] == {"pos": 0, "nota": 0}                     # 9s → fora (>=9)


def test_row_fields_image_and_prev_heuristic():
    main = [_row(1, 5, "GG-A", 11, folder="pos-pko")]
    prev = [{"id": 99, "hand_id": "GG-PREV", "pa": "2026-07-12 09:58:00",
             "raw": "Table '5' 8-max\n*** FLOP *** [..]"}]
    with patch.object(gg_health, "query", side_effect=[main, prev]):
        res = gg_health.late_prints(current_user={})
    h = res["pos"][0]
    assert h["folder_tag"] == "pos-pko" and h["tags"] == ["pos-pko"]
    assert h["match_method"] == "filename_hand_id"
    assert h["image_url"] == "/api/table-ss/image/1"
    assert h["prev"]["hand_id"] == "GG-PREV" and h["prev"]["had_flop"] is True
