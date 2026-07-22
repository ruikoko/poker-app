# -*- coding: utf-8 -*-
"""Fonte (T) — TRANSIÇÃO DO -max NA HH (22 Jul) + fonte única `hand_ft_state`.

Régua do Rui validada em prod (read-only, 22 Jul): na GG a mesa final forma numa
mesa MAIOR (6-max→7-max, 8-max→9-max); 490/490 torneios GG 2026 com TS concordam
HH↔TS; interleaving 0. A 1ª mão na mesa maior É a fronteira, ao segundo."""
from datetime import datetime, timedelta
from unittest.mock import patch

from app.services import ft_boundary as fb

T0 = datetime(2026, 6, 15, 2, 0, 0)


def _rows(*sizes_by_minute):
    return [{"played_at": T0 + timedelta(minutes=i), "tsize": s}
            for i, s in enumerate(sizes_by_minute)]


# ── _hh_transition_info ──────────────────────────────────────────────────────
def test_transition_clean_6max_to_7max():
    with patch.object(fb, "query", return_value=_rows(6, 6, 6, 7, 7)):
        t = fb._hh_transition_info("T")
    assert t["applicable"] and t["clean"]
    assert t["boundary"] == T0 + timedelta(minutes=3)     # 1ª mão 7-max
    assert t["moda"] == 6 and t["n_big"] == 2


def test_transition_blind_on_9max_moda():
    with patch.object(fb, "query", return_value=_rows(9, 9, 9)):
        t = fb._hh_transition_info("T")
    assert t["applicable"] is False and t["boundary"] is None


def test_transition_absent_when_no_bigger_table():
    with patch.object(fb, "query", return_value=_rows(6, 6, 6)):
        t = fb._hh_transition_info("T")
    assert t["applicable"] is True and t["boundary"] is None   # não chegou à FT


def test_transition_dirty_interleaving_flagged():
    with patch.object(fb, "query", return_value=_rows(6, 7, 6, 7)):
        t = fb._hh_transition_info("T")
    assert t["boundary"] is not None and t["clean"] is False


def test_single_ft_hand_still_caught():
    # caso real 287863839: 1 única mão de FT (bustou 7º logo à 1ª) — apanha na mesma
    with patch.object(fb, "query", return_value=_rows(6, 6, 7)):
        t = fb._hh_transition_info("T")
    assert t["boundary"] == T0 + timedelta(minutes=2) and t["n_big"] == 1


# ── compute_ft_boundary: (T) à cabeça da cascata ─────────────────────────────
def _patch_compute(monkey, t, lobby=(None, None), ts=None, seats=7):
    monkey.setattr(fb, "_hh_transition_info", lambda tn: t)
    monkey.setattr(fb, "_lobby_ft_boundary", lambda tn: lobby)
    monkey.setattr(fb, "_ts_hero_position", lambda tn: ts)
    monkey.setattr(fb, "_first_hand_seats_after", lambda tn, b: seats)
    monkey.setattr(fb, "_manual_ft_boundary", lambda tn: None)
    monkey.setattr(fb, "_it_ft_boundary", lambda tn: (None, True, None))
    monkey.setattr(fb, "_snap_to_n", lambda tn, b, n: b)


def test_compute_transition_primary(monkeypatch):
    t = {"applicable": True, "moda": 6, "boundary": T0, "n_big": 3, "clean": True}
    _patch_compute(monkeypatch, t, ts=1)
    d = fb.compute_ft_boundary("T")
    assert d["status"] == "transition" and d["source"] == "hh_table_transition"
    assert d["boundary"] == T0 and d["n"] == 7
    assert d["cross_check"]["ts_agrees"] is True
    assert fb.review_status(d["status"], d["cross_check"]) == "match"


def test_compute_transition_ts_disagrees_goes_quarantine(monkeypatch):
    # TS diz bust 15º num 6-max → contradiz a transição → quarentena, nunca às cegas
    t = {"applicable": True, "moda": 6, "boundary": T0, "n_big": 3, "clean": True}
    _patch_compute(monkeypatch, t, ts=15)
    d = fb.compute_ft_boundary("T")
    assert d["status"] == "quarantine_disagreement" and d["boundary"] is None


def test_compute_dirty_transition_goes_quarantine(monkeypatch):
    t = {"applicable": True, "moda": 6, "boundary": T0, "n_big": 3, "clean": False}
    _patch_compute(monkeypatch, t)
    d = fb.compute_ft_boundary("T")
    assert d["status"] == "quarantine_disagreement"


def test_compute_lobby_contradicted_by_absent_transition(monkeypatch):
    # HH prova que NÃO houve FT (transição aplicável ausente) + lobby com fronteira
    # → a via (a) cai em quarentena (não nasce outra fronteira atrasada/errada)
    t = {"applicable": True, "moda": 6, "boundary": None, "n_big": 0, "clean": True}
    _patch_compute(monkeypatch, t, lobby=(T0, 7))
    d = fb.compute_ft_boundary("T")
    assert d["status"] == "quarantine_disagreement"
    assert d["cross_check"]["hh_transition_absent"] is True


def test_compute_blind_moda_falls_through_to_lobby(monkeypatch):
    # mesa-9: fonte (T) cega → cascata antiga intacta (via a)
    t = {"applicable": False, "moda": 9, "boundary": None, "n_big": 0, "clean": True}
    _patch_compute(monkeypatch, t, lobby=(T0, 9), seats=9)
    d = fb.compute_ft_boundary("T")
    assert d["status"] == "lobby" and d["boundary"] == T0


# ── hand_ft_state: fonte única «esta mão é FT?» ──────────────────────────────
def test_hand_ft_state_tag_manda():
    assert fb.hand_ft_state("T", T0, ["icm-pko-ft"]) == "ft"


def test_hand_ft_state_registered_boundary(monkeypatch):
    monkeypatch.setattr(fb, "query", lambda sql, p=None:
                        [{"boundary": T0, "override_boundary": None, "decision": "promoted"}])
    cache = {}
    assert fb.hand_ft_state("T", T0 + timedelta(minutes=1), [], cache=cache) == "ft"
    assert fb.hand_ft_state("T", T0 - timedelta(minutes=1), [], cache=cache) == "not_ft"
    assert cache["T"] == ("boundary", T0)              # 1 ida à BD, resto por cache


def test_hand_ft_state_override_wins(monkeypatch):
    ob = T0 - timedelta(minutes=30)
    monkeypatch.setattr(fb, "query", lambda sql, p=None:
                        [{"boundary": T0, "override_boundary": ob, "decision": "corrected"}])
    assert fb.hand_ft_state("T", T0 - timedelta(minutes=10), []) == "ft"


def test_hand_ft_state_transition_beats_dismissed(monkeypatch):
    # caso 289176860: dispensado à data (detetor cego) mas a HH prova a FT
    monkeypatch.setattr(fb, "query", lambda sql, p=None:
                        [{"boundary": None, "override_boundary": None, "decision": "dismissed"}])
    monkeypatch.setattr(fb, "_hh_transition_info", lambda tn:
                        {"applicable": True, "moda": 6, "boundary": T0, "n_big": 3, "clean": True})
    assert fb.hand_ft_state("T", T0 + timedelta(minutes=1), []) == "ft"


def test_hand_ft_state_no_ft_when_transition_absent(monkeypatch):
    monkeypatch.setattr(fb, "query", lambda sql, p=None: [])
    monkeypatch.setattr(fb, "_hh_transition_info", lambda tn:
                        {"applicable": True, "moda": 6, "boundary": None, "n_big": 0, "clean": True})
    assert fb.hand_ft_state("T", T0, []) == "not_ft"


def test_hand_ft_state_blind_guard(monkeypatch):
    # guarda (c): fonte cega (mesa-9) — TS prova bust pré-FT → not_ft; sem TS → unknown
    monkeypatch.setattr(fb, "query", lambda sql, p=None: [])
    blind = {"applicable": False, "moda": 9, "boundary": None, "n_big": 0, "clean": True}
    monkeypatch.setattr(fb, "_hh_transition_info", lambda tn: blind)
    monkeypatch.setattr(fb, "_ts_hero_position", lambda tn: 55)
    assert fb.hand_ft_state("T", T0, []) == "not_ft"
    monkeypatch.setattr(fb, "_ts_hero_position", lambda tn: None)
    assert fb.hand_ft_state("T", T0, []) == "unknown"


def test_table_max_size_parse():
    assert fb.table_max_size("Table '51' 8-max Seat #3 is the button") == 8
    assert fb.table_max_size("sem tabela") is None
    assert fb.table_max_size(None) is None
