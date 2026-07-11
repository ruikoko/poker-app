"""Fase 2 do editor Saúde GG — editar/confirmar coroas. Foco nas guardas: ½-base
intacta p/ seats não-confirmados; `bounty_confirmed` é exceção manual; dry-run não grava;
o valor propaga aos DOIS stores (players_list + apa)."""
from unittest.mock import patch, MagicMock
import pytest
from fastapi import HTTPException

from app.routers import table_ss
from app.services.queue_export import detect_bounty_below_half, detect_bounty_above_3x


# ── Guarda ½-base respeita bounty_confirmed (exceção manual) ─────────────────
def test_below_half_flags_low_crown():
    pn = {"players_list": [{"name": "absi17-", "bounty_value_usd": 43.75}]}
    below = detect_bounty_below_half(pn, 100.0)          # floor 50 → 43.75 < 50
    assert len(below) == 1 and below[0]["name"] == "absi17-"


# ── Grupo "Valor alto — confirmar": coroa > 3×base (simétrico) ───────────────
def test_above_3x_flags_high_crown():
    pn = {"players_list": [
        {"name": "Puntti", "bounty_value_usd": 5324.24},   # 21×base → alto
        {"name": "ok", "bounty_value_usd": 250.0},         # 2.5×base → normal
    ]}
    above = detect_bounty_above_3x(pn, 100.0)              # teto 300 → só Puntti
    assert [a["name"] for a in above] == ["Puntti"]
    assert above[0]["ceil"] == 300.0


def test_above_3x_skips_confirmed_seat():
    pn = {"players_list": [
        {"name": "Puntti", "bounty_value_usd": 5324.24, "bounty_confirmed": True},
        {"name": "outro", "bounty_value_usd": 900.0},      # 9×base, não confirmado → marca
    ]}
    above = detect_bounty_above_3x(pn, 100.0)
    names = [a["name"] for a in above]
    assert "Puntti" not in names                           # carimbado → exceção
    assert "outro" in names


def test_below_half_skips_confirmed_seat():
    pn = {"players_list": [
        {"name": "absi17-", "bounty_value_usd": 43.75, "bounty_confirmed": True},
        {"name": "outro", "bounty_value_usd": 30.0},     # NÃO confirmado → continua a marcar
    ]}
    below = detect_bounty_below_half(pn, 100.0)
    names = [b["name"] for b in below]
    assert "absi17-" not in names                        # confirmado → exceção
    assert "outro" in names                              # guarda intacta p/ o resto


# ── set-bounties: dry-run mostra o plano e NÃO grava ─────────────────────────
def _hand_row():
    return [{"id": 9917, "site": "GGPoker",
             "all_players_actions": {"_meta": {"bb": 1000},
                                     "absi17-": {"seat": 4, "bounty_value_usd": 43.75}},
             "player_names": {"players_list": [{"name": "absi17-", "bounty_value_usd": 43.75}]}}]


def test_set_bounties_dry_run_no_write():
    with patch.object(table_ss, "query", return_value=_hand_row()), \
         patch.object(table_ss, "get_conn") as mconn:
        res = table_ss.set_bounties_override({"hand_id": "GG-1",
                                              "confirm": ["absi17-"], "dry_run": True})
    assert res["dry_run"] is True
    assert res["plan"][0]["name"] == "absi17-" and res["plan"][0]["confirm"] is True
    mconn.assert_not_called()                            # dry-run não grava


def test_set_bounties_confirm_and_edit_writes_both_stores():
    row = _hand_row()
    captured = {}
    conn = MagicMock()
    cur = conn.cursor.return_value.__enter__.return_value
    def _exec(sql, params=None):
        captured["sql"] = sql; captured["params"] = params
    cur.execute.side_effect = _exec
    with patch.object(table_ss, "query", return_value=row), \
         patch.object(table_ss, "get_conn", return_value=conn):
        res = table_ss.set_bounties_override({"hand_id": "GG-1",
                                              "bounties": {"absi17-": 43.75},
                                              "confirm": ["absi17-"]})
    assert res["updated"] == ["absi17-"] and res["confirmed"] == ["absi17-"]
    # grava player_names E all_players_actions (os 2 stores)
    assert "all_players_actions" in captured["sql"] and "player_names" in captured["sql"]


def test_set_bounties_not_found_reported():
    with patch.object(table_ss, "query", return_value=_hand_row()), \
         patch.object(table_ss, "get_conn", return_value=MagicMock()):
        res = table_ss.set_bounties_override({"hand_id": "GG-1",
                                              "bounties": {"fantasma": 10.0}})
    assert res["not_found"] == ["fantasma"] and res["updated"] == []


def test_set_bounties_requires_something():
    with pytest.raises(HTTPException):
        table_ss.set_bounties_override({"hand_id": "GG-1"})
