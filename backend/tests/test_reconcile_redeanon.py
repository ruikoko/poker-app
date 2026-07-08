"""#HRC-REIMPORT-REDEANON-CASADAS — o reconcile re-desanoniza + re-tag as capturas
casadas MESMO quando o match não `changed` (no reimport o hand_id é o mesmo mas a mão
em BD é nova e anónima). Testa a WIRING (mock dos primitivos DB)."""
from app.routers import table_ss as ts


def _one_success_row():
    return [{
        "id": 1, "captured_at": None, "site": "GGPoker",
        "vision_json": {"seats": [{"nick": "Alice"}]},
        "result": "success", "matched_hand_id": "GG-1",
        "original_filename": "Shot1-GGPoker-x.png", "folder_tag": "icm",
    }]


def _wire(monkeypatch, persisted_changed):
    calls = {"deanon": [], "tag": []}
    monkeypatch.setattr(ts, "query", lambda *a, **k: _one_success_row())
    monkeypatch.setattr(ts, "parse_table_ss_filename",
                        lambda f: {"tournament_number": None, "site": "GGPoker"})
    monkeypatch.setattr(ts, "compute_table_ss_match", lambda *a, **k: {
        "result": "success", "reason_detail": "", "site": "GGPoker",
        "tournament_number": "1", "matched_hand_id": "GG-1", "matched_hand_db_id": 42})
    monkeypatch.setattr(ts, "_persist_table_ss_match", lambda *a, **k: persisted_changed)
    monkeypatch.setattr(ts, "_deanon_after_match", lambda db, vj: calls["deanon"].append(db))
    monkeypatch.setattr(ts, "_apply_folder_tag_to_hand",
                        lambda db, t, vj: calls["tag"].append((db, t)))
    return calls


def test_reconcile_redeanons_when_match_unchanged(monkeypatch):
    # reimport: hand_id igual → _persist devolve False (unchanged); o re-desanon TEM de correr
    calls = _wire(monkeypatch, persisted_changed=False)
    res = ts.reconcile_table_ss(hand_ids=None)
    assert calls["deanon"] == [42]              # re-desanon apesar de changed=False
    assert calls["tag"] == [(42, "icm")]        # re-tag também
    assert res["success"] == 1 and res["changed"] == 0


def test_reconcile_redeanons_when_match_changed(monkeypatch):
    # comportamento antigo preservado: quando muda, também re-desanoniza
    calls = _wire(monkeypatch, persisted_changed=True)
    res = ts.reconcile_table_ss(hand_ids=None)
    assert calls["deanon"] == [42] and calls["tag"] == [(42, "icm")]
    assert res["changed"] == 1
