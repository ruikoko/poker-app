"""pt85 (#HRC-VERIFY) — verificação HH-vs-HRC (C1-C5). Função pura + zips sintéticos."""
from __future__ import annotations

import io
import json
import zipfile

from app.services.hrc_verify import (
    parse_hh_blinds, _hh_seat_stacks, _derive_scale, verify_hand,
)

_GG_RAW = (
    "Poker Hand #TM1: Tournament #1, Daily - Level17(800/1,600(200)) - 2026/06/16 / "
    "Table '11' 6-max Seat #6 is the button / "
    "Seat 1: 9b50a853 (37,371 in chips) / Seat 3: Hero (5,562 in chips) / "
    "Seat 4: x (15,550 in chips)"
)
_WN_RAW = (
    'Winamax Poker - Tournament "GRAVITY" buyIn: 232€ level: 1 - HandId: #1 - Holdem\n'
    "Seat 1: a (19775, 125€ bounty)\nSeat 2: b (1075, 125€ bounty)\n"
)


def _zip(settings, meta=None):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("settings.json", json.dumps(settings))
        zf.writestr("meta.json", json.dumps(meta or {}))
        zf.writestr("nodes/0.json", "{}")
    return buf.getvalue()


def test_parse_hh_blinds_gg():
    assert parse_hh_blinds(_GG_RAW) == (800.0, 1600.0, 200.0)


def test_parse_hh_blinds_wn_none():
    assert parse_hh_blinds(_WN_RAW) is None    # WN não tem level no header


def test_seat_stacks_gg_and_wn():
    assert _hh_seat_stacks(_GG_RAW) == [37371.0, 5562.0, 15550.0]
    assert _hh_seat_stacks(_WN_RAW) == [19775.0, 1075.0]


def test_derive_scale_from_stacks_when_no_blinds():
    # WN: sem blinds parseáveis → scale do rácio dos maiores (×100)
    assert _derive_scale([], None, [1977500, 107500], [19775, 1075]) == 100.0


def test_verify_ok_gg():
    settings = {"handdata": {"stacks": [3737100, 556200, 1555000],
                             "blinds": [160000, 80000, 20000]}}
    h = {"hand_id": "GG-X", "raw": _GG_RAW, "tournament_format": "vanilla",
         "all_players_actions": {}}
    res = verify_hand(h, _zip(settings, {"max_players": 3}))
    assert res["verdict"] == "ok"
    assert res["scale"] == 100.0


def test_verify_fail_blinds_mismatch():
    # blinds HRC não-proporcionais às da HH → C3 FAIL
    settings = {"handdata": {"stacks": [3737100, 556200, 1555000],
                             "blinds": [160000, 999999, 20000]}}
    h = {"hand_id": "GG-X", "raw": _GG_RAW, "tournament_format": "vanilla"}
    res = verify_hand(h, _zip(settings, {"max_players": 3}))
    assert res["verdict"] == "fail"
    assert any(c["check"] == "C3_blinds" and c["status"] == "fail" for c in res["checks"])


def test_verify_fail_stack_no_match():
    # um stack HRC sem correspondência na HH → C2 FAIL
    settings = {"handdata": {"stacks": [3737100, 556200, 9999900],
                             "blinds": [160000, 80000, 20000]}}
    h = {"hand_id": "GG-X", "raw": _GG_RAW, "tournament_format": "vanilla"}
    res = verify_hand(h, _zip(settings, {"max_players": 3}))
    assert res["verdict"] == "fail"
    assert any(c["check"] == "C2_stacks" and c["status"] == "fail" for c in res["checks"])


def test_verify_pko_bounty_ok_and_missing():
    base = {"handdata": {"stacks": [3737100, 556200, 1555000],
                         "blinds": [160000, 80000, 20000], "bounties": [15.0, 15.0, 15.0]}}
    h = {"hand_id": "GG-X", "raw": _GG_RAW, "tournament_format": "pko"}
    assert verify_hand(h, _zip(base, {"max_players": 3}))["verdict"] == "ok"
    # sem bounties num PKO → C5 FAIL
    nob = {"handdata": {"stacks": [3737100, 556200, 1555000], "blinds": [160000, 80000, 20000]}}
    res = verify_hand(h, _zip(nob, {"max_players": 3}))
    assert any(c["check"] == "C5_bounty" and c["status"] == "fail" for c in res["checks"])


def test_verify_c4_equity_warn():
    # equity FT mas players_left >> seats → C4 warn
    settings = {"handdata": {"stacks": [3737100, 556200, 1555000],
                             "blinds": [160000, 80000, 20000]}}
    h = {"hand_id": "GG-X", "raw": _GG_RAW, "tournament_format": "vanilla"}
    res = verify_hand(h, _zip(settings, {"max_players": 3,
                                         "equity_model": "malmuth_harville_icm",
                                         "players_left": 200}))
    assert res["verdict"] == "warn"


def test_verify_bad_zip():
    h = {"hand_id": "GG-X", "raw": _GG_RAW}
    res = verify_hand(h, b"not a zip")
    assert res["verdict"] == "fail"
