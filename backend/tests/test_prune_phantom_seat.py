"""Apagar lugar FANTASMA (nome NONE/vazio + sem dados) do players_list.
Guarda: um lugar com QUALQUER valor nunca é fantasma (não se apaga)."""
from unittest.mock import patch, MagicMock
from app.routers import gg_health


def test_phantom_true_for_empty_none():
    assert gg_health._is_phantom_seat(
        {"name": "NONE", "seat": None, "position": None,
         "bounty_value_usd": None, "stack_bb": None, "stack_chips": None}) is True
    assert gg_health._is_phantom_seat({"name": ""}) is True
    assert gg_health._is_phantom_seat({"name": "null"}) is True


def test_phantom_false_for_real_seat():
    assert gg_health._is_phantom_seat(
        {"name": "Kuruzslo", "position": "MP", "bounty_value_usd": 22.5}) is False


def test_guard_none_name_but_has_value_is_not_phantom():
    # nome NONE mas com coroa/seat/posição → NÃO é fantasma (não se apaga um valor)
    assert gg_health._is_phantom_seat({"name": "NONE", "bounty_value_usd": 11.25}) is False
    assert gg_health._is_phantom_seat({"name": "none", "seat": 6}) is False
    assert gg_health._is_phantom_seat({"name": "NONE", "position": "BB"}) is False


def test_endpoint_removes_only_phantom_and_writes():
    pl = [{"name": "Bruno Carbonera", "position": "UTG", "bounty_value_usd": 11.25},
          {"name": "Kuruzslo", "position": "MP", "bounty_value_usd": 22.5},
          {"name": "NONE", "seat": None, "position": None, "bounty_value_usd": None,
           "stack_bb": None, "stack_chips": None}]
    row = [{"id": 4903, "player_names": {"players_list": pl, "match_method": "position_v3"}}]
    captured = {}
    conn = MagicMock()
    cur = conn.cursor.return_value.__enter__.return_value
    cur.execute.side_effect = lambda sql, params=None: captured.update(sql=sql, params=params)
    with patch.object(gg_health, "query", return_value=row), \
         patch.object(gg_health, "get_conn", return_value=conn):
        res = gg_health.prune_phantom_seats({"hand_id": "GG-6113716239"})
    assert res["before"] == 3 and res["removed"] == 1 and res["after"] == 2
    assert "player_names" in captured["sql"]                 # escreveu players_list saneado


def test_endpoint_dry_run_does_not_write():
    pl = [{"name": "Kuruzslo", "bounty_value_usd": 22.5},
          {"name": "NONE", "bounty_value_usd": None}]
    row = [{"id": 1, "player_names": {"players_list": pl}}]
    with patch.object(gg_health, "query", return_value=row), \
         patch.object(gg_health, "get_conn") as mconn:
        res = gg_health.prune_phantom_seats({"hand_id": "GG-1", "dry_run": True})
    assert res["dry_run"] is True and res["removed"] == 1
    mconn.assert_not_called()
