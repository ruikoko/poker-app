"""#CROWN-VISIBLE-READ-ZERO — o filtro separa 'coroa por ler ($0)' de 'valor impossível'."""
from unittest.mock import patch
from app.routers import suspicious


def _rows(pn, base=100.0):
    return [{"id": 1, "hand_id": "GG-1", "tournament_name": "T",
             "played_at": "2026-07-02", "pn": pn, "base": base}]


def test_kind_unread_when_all_zero():
    pn = {"players_list": [{"name": "A", "bounty_value_usd": 0.0, "has_cards": True}]}
    with patch.object(suspicious, "query", return_value=_rows(pn)):
        out = suspicious._bounty_below_half_hands()
    assert out and out[0]["kind"] == "unread"


def test_kind_impossible_when_positive_below_half():
    pn = {"players_list": [{"name": "A", "bounty_value_usd": 30.0, "has_cards": True}]}
    with patch.object(suspicious, "query", return_value=_rows(pn)):
        out = suspicious._bounty_below_half_hands()
    assert out and out[0]["kind"] == "impossible"
