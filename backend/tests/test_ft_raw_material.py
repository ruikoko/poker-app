"""Tests do endpoint GET /api/gg-health/ft/raw-material (matéria-prima da 4b FT).

Só leitura; a BD é mockada (as 3 queries discriminadas por substring do SQL)."""
from datetime import date
from unittest.mock import patch

from app.routers import gg_health as ggh


def _raw(n_header, n_summary=0):
    """Raw GG sintético: n_header linhas Seat no bloco de seats + n_summary no SUMMARY."""
    seats = "".join(f"Seat {i}: p{i} ({i}000 in chips)\n" for i in range(1, n_header + 1))
    out = seats + "*** HOLE CARDS ***\naction\n"
    if n_summary:
        out += "*** SUMMARY ***\n" + "".join(
            f"Seat {i}: p{i} folded\n" for i in range(1, n_summary + 1))
    return out


# ── _count_seats: conta o bloco de seats, ignora o SUMMARY ───────────────────
def test_count_seats_ignores_summary():
    assert ggh._count_seats(_raw(5, n_summary=5)) == 5      # não conta a dobrar
    assert ggh._count_seats(_raw(9)) == 9
    assert ggh._count_seats("") is None
    assert ggh._count_seats(None) is None


def test_count_seats_no_hole_cards_marker():
    # sem '*** HOLE CARDS ***' corta no 1º '*** ' (evita apanhar o SUMMARY)
    raw = "Seat 1: a (1)\nSeat 2: b (2)\n*** SUMMARY ***\nSeat 1: a\nSeat 2: b\n"
    assert ggh._count_seats(raw) == 2


# ── endpoint: agrupa por dia, ordena n_hands desc, sinaliza ft_candidate ──────
def _dispatch(aggs, lobby_rows, latest_rows):
    def _q(sql, params=None):
        if "lobby_processing_log" in sql:
            return lobby_rows
        if "DISTINCT ON" in sql:
            return latest_rows
        return aggs                                # (A) agregados por torneio
    return _q


def test_raw_material_groups_sorts_and_flags():
    D1, D2 = date(2026, 6, 25), date(2026, 6, 26)
    aggs = [
        {"tn": "GG-A", "day": D1, "name": "ALPHA", "n_hands": 120, "min_pl_it": 6},
        {"tn": "GG-B", "day": D1, "name": "BETA", "n_hands": 50, "min_pl_it": None},
        {"tn": "GG-C", "day": D2, "name": "GAMMA", "n_hands": 200, "min_pl_it": None},
    ]
    lobby_rows = [{"tn": "GG-B", "min_pl": 40}, {"tn": "GG-C", "min_pl": None}]
    latest_rows = [
        {"tn": "GG-A", "raw": _raw(5, n_summary=5)},
        {"tn": "GG-B", "raw": _raw(8)},
        {"tn": "GG-C", "raw": _raw(9)},
    ]
    with patch.object(ggh, "query", side_effect=_dispatch(aggs, lobby_rows, latest_rows)):
        res = ggh.ft_raw_material(current_user=None)

    assert res["scope"] == "GGPoker 2026"
    assert res["total_tournaments"] == 3
    assert res["total_ft_candidates"] == 2                  # A (pl 6) + C (9 sentados)

    # dias em ordem ascendente
    assert [d["day"] for d in res["days"]] == ["2026-06-25", "2026-06-26"]

    d1 = res["days"][0]["tournaments"]
    assert [t["tournament_number"] for t in d1] == ["GG-A", "GG-B"]   # n_hands desc

    a = d1[0]
    assert a["min_players_left"] == 6 and a["latest_hand_seats"] == 5  # SUMMARY ignorado
    assert a["has_lobby"] is False and a["ft_candidate"] is True

    b = d1[1]
    assert b["min_players_left"] == 40 and b["has_lobby"] is True
    assert b["ft_candidate"] is False                       # 40 > FT_CAP, sem via seats

    c = res["days"][1]["tournaments"][0]
    assert c["min_players_left"] is None and c["latest_hand_seats"] == 9
    assert c["has_lobby"] is True and c["ft_candidate"] is True   # via sentados <= 9
