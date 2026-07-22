# -*- coding: utf-8 -*-
"""RÉGUA DOS 6s — endpoint move-to-prev (imagem + tag para a mão anterior).
Prova: link SEM re-desanon (deanon=False) · tag sai da atual e entra na anterior
pelo selo · pipeline corre · cruzamento disparado · a imagem nunca reescreve
nomes por si."""
from unittest.mock import patch

from app.routers import table_ss


class FakeCursor:
    def __init__(self, store):
        self.store = store

    def execute(self, sql, params=None):
        self.store.append((sql, params))

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class FakeConn:
    def __init__(self, store):
        self.store = store

    def cursor(self):
        return FakeCursor(self.store)

    def commit(self):
        pass

    def close(self):
        pass


def test_manual_link_deanon_false_salta_desanon_mas_aplica_folder_tag(monkeypatch):
    calls = []
    monkeypatch.setattr(table_ss, "query", lambda sql, params=None:
                        [{"id": 5, "site": "GGPoker", "vision_json": {}, "folder_tag": "nota",
                          "result": "success", "matched_hand_id": "GG-CUR"}]
                        if "table_ss_processing_log" in sql else
                        [{"id": 9, "hand_id": "GG-PREV", "tournament_number": "T1"}])
    monkeypatch.setattr(table_ss, "_persist_table_ss_match",
                        lambda *a, **k: calls.append("persist"))
    monkeypatch.setattr(table_ss, "_deanon_after_match",
                        lambda *a, **k: calls.append("deanon"))
    monkeypatch.setattr(table_ss, "_apply_folder_tag_to_hand",
                        lambda *a, **k: calls.append("folder_tag"))
    res = table_ss._manual_link_ss(5, "GG-PREV", deanon=False)
    assert res["result"] == "success"
    assert calls == ["persist", "folder_tag"]          # SEM 'deanon'
    calls.clear()
    table_ss._manual_link_ss(5, "GG-PREV")             # default: comportamento antigo
    assert calls == ["persist", "deanon", "folder_tag"]


def _wire_move(monkeypatch, folder_tag, store, sealed, fired, crossing):
    def q(sql, params=None):
        if "table_ss_processing_log" in sql:
            return [{"id": 5, "folder_tag": folder_tag, "matched_hand_id": "GG-CUR"}]
        if "FROM hands WHERE hand_id=" in sql:
            hid = params[0]
            return [{"id": 77 if hid == "GG-CUR" else 88, "hand_id": hid}]
        raise AssertionError(sql)
    monkeypatch.setattr(table_ss, "query", q)
    monkeypatch.setattr(table_ss, "get_conn", lambda: FakeConn(store))
    monkeypatch.setattr(table_ss, "_manual_link_ss",
                        lambda ss, hid, deanon=True: store.append(("link", ss, hid, deanon))
                        or {"result": "success", "matched_hand_id": hid})
    import app.services.tag_decisions as td
    monkeypatch.setattr(td, "seal_and_recompute",
                        lambda cur, hid, tag, action, actor=None, origin=None:
                        sealed.append((hid, tag, action, origin)) or [1])
    import app.services.study_pipeline as sp
    monkeypatch.setattr(sp, "on_hand_tagged", lambda hid, **kw: fired.append(hid))
    import app.routers.gg_health as gh
    monkeypatch.setattr(gh, "run_crossing_auto",
                        lambda reason="": crossing.append(reason) or {})
    import threading
    monkeypatch.setattr(threading, "Thread",
                        lambda target=None, kwargs=None, daemon=None:
                        type("T", (), {"start": lambda self: target(**(kwargs or {}))})())


def test_move_com_folder_tag(monkeypatch):
    store, sealed, fired, crossing = [], [], [], []
    _wire_move(monkeypatch, "pos-pko", store, sealed, fired, crossing)
    res = table_ss.move_table_ss_to_prev(5, {"prev_hand_id": "GG-PREV"},
                                         current_user={"email": "rui"})
    # tag SAI da atual pelo selo; a entrada na anterior vem da folder-tag no link
    assert ("GG-CUR", "pos-pko", "remove", "regra6s.move") in sealed
    assert ("link", 5, "GG-PREV", False) in store      # imagem movida SEM re-desanon
    assert 77 in fired                                  # pipeline na atual (pós-remove)
    assert crossing == ["regra6s_move"]                 # testemunha → cruzamento
    assert res["status"] == "moved" and res["to"] == "GG-PREV"
    assert res["tag_applied_to_prev"] == "pos-pko"


def test_move_sem_tag_com_tag_escolhida(monkeypatch):
    store, sealed, fired, crossing = [], [], [], []
    _wire_move(monkeypatch, None, store, sealed, fired, crossing)
    res = table_ss.move_table_ss_to_prev(5, {"prev_hand_id": "GG-PREV", "tag": "nota"},
                                         current_user={"email": "rui"})
    assert ("GG-PREV", "nota", "add", "regra6s.move") in sealed
    assert not any(s for s in sealed if s[2] == "remove")   # nada a remover na atual
    assert ("link", 5, "GG-PREV", False) in store
    assert 88 in fired                                  # pipeline na anterior
    assert res["tag_applied_to_prev"] == "nota"


def _wire_sweep(monkeypatch, caps, prevs_by_tn, reviewed=None, ft_states=None):
    """caps: rows do scan; prevs_by_tn: tn→prev dict|None; ft_states: tn→estado
    forçado do `hand_ft_state` (default 'not_ft'; a tag -ft continua a mandar,
    como na fonte única real)."""
    import app.routers.gg_health as gh
    moved = []

    def q(sql, params=None):
        if "FROM late_print_review" in sql:
            return [{"ssid": s} for s in (reviewed or [])]
        if "table_ss_processing_log l" in sql:
            return caps
        raise AssertionError(sql)
    monkeypatch.setattr(table_ss, "query", q)
    monkeypatch.setattr(table_ss, "hand_ft_state",
                        lambda tn, pa, tags=None, cache=None:
                        "ft" if any(str(t).endswith("-ft") for t in (tags or []))
                        else (ft_states or {}).get(tn, "not_ft"))
    monkeypatch.setattr(gh, "_hh_table", lambda raw: "5")
    monkeypatch.setattr(gh, "_prev_hand_same_table",
                        lambda tn, pa, t: prevs_by_tn.get(tn))
    monkeypatch.setattr(table_ss, "_move_capture_to_prev_core",
                        lambda cap, prev, tag, actor, origin, decision:
                        moved.append((cap["id"], cap["folder_tag"], prev, decision, origin))
                        or {"status": "moved"})
    return moved


def _cap(ssid, folder, tags, tn="T1"):
    return {"id": ssid, "folder_tag": folder, "matched_hand_id": f"GG-{ssid}",
            "hand_db_id": 1, "pa": "2026-07-12 10:00:00", "tn": tn, "raw": "x",
            "dt": tags, "ht": None}


def test_sweep_move_com_e_sem_tag_e_deixa_indecisos(monkeypatch):
    caps = [
        _cap(1, "pos-pko", ["pos-pko"]),                 # com tag → move tag+imagem
        _cap(2, None, [], tn="T1"),                      # sem tag → move imagem
        _cap(3, None, [], tn="SEM_PREV"),                # sem anterior → fica
        _cap(4, "pos-pko", ["pos-pko-ft", "pos-pko"]),   # FT → fora de tudo
        _cap(5, "pos-pko", []),                          # tag já saiu → move SÓ imagem
    ]
    prev = {"hand_id": "GG-PREV", "tags": []}
    moved = _wire_sweep(monkeypatch, caps, {"T1": prev, "SEM_PREV": None})
    res = table_ss.apply_regra_6s()
    assert res["moved_tagged"] == 1                      # tag+imagem (cap 1)
    assert res["moved_untagged"] == 2                    # só-imagem (cap 2 sem tag + cap 5 tag-já-saída)
    assert res["undecided"] == 1 and res["skipped_reviewed_or_ft"] == 1
    assert (1, "pos-pko", "GG-PREV", "auto_moved", "regra6s.auto") in moved
    assert (2, None, "GG-PREV", "auto_moved", "regra6s.auto") in moved
    # tag já fora da mão → o core recebe folder None (não re-sela remove), imagem move
    assert (5, None, "GG-PREV", "auto_moved", "regra6s.auto") in moved


def test_sweep_consulta_fronteira_ft_e_guarda_conservadora(monkeypatch):
    """22 Jul: a régua consulta a fonte única «é FT?» — FT por FRONTEIRA (sem tag
    nenhuma) → fora; 'unknown' (fonte cega sem prova) → indeciso, nunca move."""
    caps = [
        _cap(1, None, [], tn="FT_SEM_TAG"),     # FT pela fronteira, SEM tag → fora
        _cap(2, None, [], tn="CEGO"),           # fonte cega sem prova → indeciso
        _cap(3, None, [], tn="T1"),             # normal → move
    ]
    prev = {"hand_id": "GG-PREV", "played_at": "2026-07-12 09:58:00", "tags": []}
    moved = _wire_sweep(monkeypatch, caps,
                        {"FT_SEM_TAG": prev, "CEGO": prev, "T1": prev},
                        ft_states={"FT_SEM_TAG": "ft", "CEGO": "unknown"})
    res = table_ss.apply_regra_6s()
    assert res["skipped_reviewed_or_ft"] == 1        # FT sem tag agora é vista
    assert res["undecided"] == 1                     # unknown nunca move sozinho
    assert res["moved_untagged"] == 1
    assert [m[0] for m in moved] == [3]


def test_sweep_idempotente_e_dry_run(monkeypatch):
    caps = [_cap(1, None, [])]
    prev = {"hand_id": "GG-PREV", "tags": []}
    moved = _wire_sweep(monkeypatch, caps, {"T1": prev}, reviewed=[1])
    res = table_ss.apply_regra_6s()
    assert moved == [] and res["skipped_reviewed_or_ft"] == 1   # já tratada → não repete
    moved2 = _wire_sweep(monkeypatch, caps, {"T1": prev})
    res2 = table_ss.apply_regra_6s(dry_run=True)
    assert moved2 == [] and res2["dry_run"] and len(res2["plan"]) == 1  # ensaio: 0 escritas


def test_move_recusa_tag_desconhecida_e_prev_igual(monkeypatch):
    import pytest
    from fastapi import HTTPException
    store, sealed, fired, crossing = [], [], [], []
    _wire_move(monkeypatch, None, store, sealed, fired, crossing)
    with pytest.raises(HTTPException):
        table_ss.move_table_ss_to_prev(5, {"prev_hand_id": "GG-PREV",
                                           "tag": "tag-inventada"}, current_user={})
    with pytest.raises(HTTPException):
        table_ss.move_table_ss_to_prev(5, {"prev_hand_id": "GG-CUR"}, current_user={})
