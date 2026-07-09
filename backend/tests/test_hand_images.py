"""GET /api/hands/<id>/images — imagens da mão agrupadas por tipo (regra 9 Jul)."""
import datetime
from unittest.mock import patch

import pytest
from fastapi import HTTPException

from app.routers import hands


def _q(sql, params=None):
    if "FROM hands WHERE id" in sql:
        return [{"id": 1, "hand_id": "GG-1", "site": "GGPoker",
                 "tournament_number": "T1", "entry_id": 115, "context_table_ss_id": 195}]
    if "FROM entries" in sql:
        return [{"id": 115, "entry_type": "screenshot"}]
    if "table_ss_processing_log" in sql:
        return [{"ss_id": 195, "captured_at": datetime.datetime(2026, 7, 2, 21, 38, 46),
                 "players_left": 148}]
    if "lobby_processing_log" in sql:
        return [{"posted_at": None, "players_left": 34,
                 "vision_json": {"open_tab": "Prize Pool", "final_table_size": None}}]
    return []


def test_hand_images_groups_by_type():
    with patch.object(hands, "query", side_effect=_q):
        out = hands.get_hand_images(1, current_user=None)
    assert [g["entry_id"] for g in out["gold"]] == [115]
    assert out["gold"][0]["image_url"] == "/api/screenshots/image/115"
    assert [t["ss_id"] for t in out["table_ss"]] == [195]
    assert out["table_ss"][0]["image_url"] == "/api/table-ss/image/195"
    assert out["table_ss"][0]["players_left"] == 148
    assert out["lobby"][0]["open_tab"] == "Prize Pool"
    assert out["lobby"][0]["note"] == "imagem não guardada"


def test_hand_images_404_missing_hand():
    with patch.object(hands, "query", side_effect=lambda *a, **k: []):
        with pytest.raises(HTTPException) as ei:
            hands.get_hand_images(999, current_user=None)
    assert ei.value.status_code == 404
