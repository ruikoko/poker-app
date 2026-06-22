"""pt86 (#HRC-VERIFY) — vista legível HH-vs-HRC: nó central por sequence-match
+ ramos. Função pura + zips/HH sintéticos."""
from __future__ import annotations

import io
import json
import zipfile

from app.services.hrc_verify_tree import build_verify_tree, _combos

# 3-handed: idx0=BTN, idx1=SB, idx2=BB (preflop order). Hero = "Hero" (idx2/BB
# via brackets). Stacks em chips; BB=200 chips.
_SETTINGS = {"handdata": {"stacks": [10000, 8000, 6000], "blinds": [200, 100, 25]}}


def _node(player, actions, sequence=None, hands=None):
    return {"player": player, "street": 0, "sequence": sequence or [],
            "actions": actions, "hands": hands or {}}


def _hands_5050(n):
    """5 classes, cada uma 'played' [1,0,...] / [0,1,...] alternado p/ dar ~50/50
    por combos (par/suited/offsuit pesados)."""
    keys = ["AA", "AKs", "AKo", "72o", "22"]
    out = {}
    for i, k in enumerate(keys):
        played = [0.0] * n
        played[i % n] = 1.0
        out[k] = {"weight": 1.0, "played": played}
    return out


def _zip(nodes):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("settings.json", json.dumps(_SETTINGS))
        zf.writestr("meta.json", "{}")
        for i, nd in nodes.items():
            zf.writestr(f"nodes/{i}.json", json.dumps(nd))
    return buf.getvalue()


def test_combos_pair_suited_offsuit():
    assert _combos("22") == 6 and _combos("AKs") == 4 and _combos("AKo") == 12


def test_central_is_first_aggressor_node():
    # BTN (idx0) abre; SB (idx1) responde. Hero = SB. 1ª acção = BTN raise.
    nodes = {
        0: _node(0, [{"type": "F", "amount": 0, "node": 2},
                     {"type": "R", "amount": 400, "node": 1}], [], _hands_5050(2)),
        1: _node(1, [{"type": "F", "amount": 0},
                     {"type": "C", "amount": 0}],
                 [{"player": 0, "type": "R", "amount": 400}], _hands_5050(2)),
        2: _node(2, [{"type": "F"}, {"type": "C"}],
                 [{"player": 0, "type": "F", "amount": 0}], _hands_5050(2)),
    }
    raw = ("Room - Level1(100/200) Seat #1 is the button\n"
           "Seat 1: Villain (10000 in chips)\nSeat 2: Hero (8000 in chips)\n"
           "Seat 3: BBp (6000 in chips)\n*** PRE-FLOP ***\n"
           "Villain: raises 200 to 400\nDealt to Hero [As Kd]\n")
    tree = build_verify_tree({"hand_id": "X", "raw": raw}, _zip(nodes))
    assert tree["central_node"] == 0
    assert tree["nodes"][0]["is_central"] is True
    # acções do nó central trazem percentagens
    labels = [a["label"] for a in tree["nodes"][0]["actions"]]
    assert any(l.startswith("R ") for l in labels) and "FOLD" in labels


def test_central_folds_to_hero():
    # BTN (idx0) folda; Hero (idx1) é o próximo → central = nó do Hero, não a raiz.
    nodes = {
        0: _node(0, [{"type": "F", "amount": 0, "node": 1},
                     {"type": "R", "amount": 400, "node": 9}], [], _hands_5050(2)),
        1: _node(1, [{"type": "F", "amount": 0},
                     {"type": "R", "amount": 400, "node": 2}],
                 [{"player": 0, "type": "F", "amount": 0}], _hands_5050(2)),
        2: _node(2, [{"type": "F"}, {"type": "C"}],
                 [{"player": 0, "type": "F"}, {"player": 1, "type": "R", "amount": 400}], _hands_5050(2)),
    }
    raw = ("Room - Level1(100/200) Seat #1 is the button\n"
           "Seat 1: Villain (10000 in chips)\nSeat 2: Hero (8000 in chips)\n"
           "Seat 3: BBp (6000 in chips)\n*** PRE-FLOP ***\n"
           "Villain: folds\nDealt to Hero [As Kd]\n")
    tree = build_verify_tree({"hand_id": "X", "raw": raw}, _zip(nodes))
    assert tree["central_node"] == 1            # nó do Hero, não 0
    assert tree["hero_idx"] == 1


def test_bad_zip_returns_error():
    assert "error" in build_verify_tree({"hand_id": "X", "raw": ""}, b"not a zip")


def test_pcts_sum_to_100_per_node():
    nodes = {0: _node(0, [{"type": "F", "amount": 0, "node": 1},
                          {"type": "R", "amount": 400}], [], _hands_5050(2))}
    raw = ("Room - Level1(100/200) Seat #1 is the button\n"
           "Seat 1: Hero (10000 in chips)\nSeat 2: x (8000 in chips)\n"
           "Seat 3: y (6000 in chips)\n*** PRE-FLOP ***\nDealt to Hero [As Kd]\n")
    tree = build_verify_tree({"hand_id": "X", "raw": raw}, _zip(nodes))
    s = sum(a["pct"] for a in tree["nodes"][0]["actions"])
    assert abs(s - 100.0) < 0.5
