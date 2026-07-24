"""#REVISION-CURE-IN-PLACE + #SWEEP-ROW-ISOLATION + #SWEEP-TRACE +
#REVISION-TWIN-CLEANUP (24 Jul 2026) — a releitura cura NA PRÓPRIA row (fim das
gémeas por hash-da-cópia), tecto de tentativas, proteção por-linha no reconcile
completo, rasto persistente das passagens e limpeza única das gémeas com ensaio.
"""
import base64
import hashlib
from datetime import datetime
from unittest.mock import patch, MagicMock

from app.routers import table_ss


# ── Fix 1: retry cura na própria row (via _reprocess_failed_row) ─────────────
def _failed_row(rid=10, attempts=1):
    return {"id": rid, "original_filename": "Winamax-X(1)(#0)-20260719222036-1.png",
            "img_b64": "aGVsbG8=", "folder_tag": None,
            "captured_at": datetime(2026, 7, 19, 22, 20), "attempt_count": attempts}


def test_retry_uses_in_place_cure_not_new_rows():
    rows = [_failed_row(10)]
    with patch.object(table_ss, "query", return_value=rows), \
         patch.object(table_ss, "_reprocess_failed_row",
                      return_value={"id": 10, "result": "success"}) as mrep, \
         patch.object(table_ss, "_process_table_ss") as mproc:
        res = table_ss.retry_failed_table_ss_vision(limit=5)
    mrep.assert_called_once()
    assert mrep.call_args.args[0]["id"] == 10          # a PRÓPRIA row
    mproc.assert_not_called()                          # nunca o caminho das gémeas
    assert res == {"retried": 1, "now_success": 1, "still_failed": 0, "exhausted": 0}


def test_retry_still_failed_counts():
    with patch.object(table_ss, "query", return_value=[_failed_row(11)]), \
         patch.object(table_ss, "_reprocess_failed_row",
                      return_value={"id": 11, "result": "json_invalid"}):
        res = table_ss.retry_failed_table_ss_vision(limit=5)
    assert res["still_failed"] == 1 and res["now_success"] == 0


# ── Fix 3: tecto de tentativas ───────────────────────────────────────────────
def test_retry_exhausts_at_cap_without_vision():
    rows = [_failed_row(12, attempts=table_ss._REVISION_MAX_ATTEMPTS)]
    with patch.object(table_ss, "query", return_value=rows), \
         patch.object(table_ss, "_reprocess_failed_row") as mrep, \
         patch.object(table_ss, "_update_failed_reason") as mupd:
        res = table_ss.retry_failed_table_ss_vision(limit=5)
    mrep.assert_not_called()                           # sem gastar Vision
    assert mupd.call_args.args[0] == 12
    assert mupd.call_args.kwargs["result"] == "revision_exhausted"
    assert "precisa do ficheiro original" in mupd.call_args.args[1]
    assert res["exhausted"] == 1 and res["retried"] == 0


def test_retry_below_cap_still_retries():
    rows = [_failed_row(13, attempts=table_ss._REVISION_MAX_ATTEMPTS - 1)]
    with patch.object(table_ss, "query", return_value=rows), \
         patch.object(table_ss, "_reprocess_failed_row",
                      return_value={"id": 13, "result": "vision_failed"}) as mrep:
        table_ss.retry_failed_table_ss_vision(limit=5)
    mrep.assert_called_once()


def test_retry_limit_zero_noop():
    res = table_ss.retry_failed_table_ss_vision(limit=0)
    assert res == {"retried": 0, "now_success": 0, "still_failed": 0, "exhausted": 0}


def test_revision_exhausted_is_valid_result():
    assert "revision_exhausted" in table_ss._VALID_RESULTS


# ── Fix 4: proteção por-linha no reconcile completo ──────────────────────────
def test_reconcile_row_explosion_does_not_kill_pass():
    rows = [
        {"id": 1, "captured_at": None, "site": "Winamax", "vision_json": {"x": 1},
         "result": "no_match_to_hand", "matched_hand_id": None,
         "original_filename": "f1.png", "folder_tag": None},
        {"id": 2, "captured_at": datetime(2026, 7, 19, 22, 20), "site": "Winamax",
         "vision_json": {"x": 2}, "result": "no_match_to_hand",
         "matched_hand_id": None, "original_filename": "f2.png", "folder_tag": None},
    ]
    calls = []

    def _compute(captured_at, site, vj, filename_tn=None, filename=None):
        calls.append(filename)
        if filename == "f1.png":
            raise RuntimeError("row podre")
        return {"result": "no_match_to_hand", "reason_detail": None, "site": site,
                "tournament_number": None, "matched_hand_id": None,
                "matched_hand_db_id": None}

    with patch.object(table_ss, "query", return_value=rows), \
         patch.object(table_ss, "compute_table_ss_match", side_effect=_compute), \
         patch.object(table_ss, "_persist_table_ss_match", return_value=False), \
         patch.object(table_ss, "parse_table_ss_filename",
                      return_value={"tournament_number": None, "site": None}):
        res = table_ss.reconcile_table_ss(pending_only=True)
    assert calls == ["f1.png", "f2.png"]               # a 2ª row FOI processada
    assert res["errors"] == 1 and res["checked"] == 2 and res["orphan"] == 1


# ── Fix 2: rasto persistente das passagens ───────────────────────────────────
def test_sweep_pending_records_trace():
    from app.services import lobby_sync
    with patch.object(lobby_sync, "_record_sweep_run") as mrec, \
         patch.object(lobby_sync, "reconcile_lobby_logs",
                      return_value={"scanned": 1, "resolved": 0, "written": 0,
                                    "still_unresolved": 1}), \
         patch("app.routers.table_ss.reconcile_table_ss",
               return_value={"checked": 2, "errors": 0}), \
         patch("app.routers.table_ss.retry_failed_table_ss_vision",
               return_value={"retried": 0, "exhausted": 0}):
        lobby_sync.sweep_pending(reason="tick")
    mrec.assert_called_once()
    kind, stats = mrec.call_args.args[0], mrec.call_args.args[1]
    assert kind == "tick"
    assert stats["table_ss"]["checked"] == 2
    assert stats["lobby"]["scanned"] == 1
    assert "revision" in stats


def test_sweep_pending_records_step_errors():
    from app.services import lobby_sync
    with patch.object(lobby_sync, "_record_sweep_run") as mrec, \
         patch.object(lobby_sync, "reconcile_lobby_logs",
                      side_effect=RuntimeError("lobby rebentou")), \
         patch("app.routers.table_ss.reconcile_table_ss", return_value={}), \
         patch("app.routers.table_ss.retry_failed_table_ss_vision",
               return_value={}):
        lobby_sync.sweep_pending(reason="startup")
    errs = mrec.call_args.args[2]
    assert any("lobby" in e and "rebentou" in e for e in errs)


def test_import_trigger_records_trace():
    from app.services import lobby_sync
    ran = {}

    class _FakeThread:
        def __init__(self, target=None, daemon=None):
            ran["target"] = target

        def start(self):
            ran["target"]()                             # corre inline no teste

    with patch("threading.Thread", _FakeThread), \
         patch.object(lobby_sync, "_record_sweep_run") as mrec, \
         patch.object(lobby_sync, "reconcile_lobby_logs",
                      return_value={"scanned": 0, "resolved": 0, "written": 0,
                                    "still_unresolved": 0}), \
         patch("app.routers.table_ss.relink_orphan_table_ss",
               return_value={"checked": 3, "success": 1}), \
         patch("app.routers.table_ss.apply_regra_6s", return_value={}), \
         patch("app.routers.gg_health.run_crossing_auto", return_value=None):
        lobby_sync.trigger_import_reconciles(reason="import_hm3")
    mrec.assert_called_once()
    assert mrec.call_args.args[0] == "import:import_hm3"
    assert mrec.call_args.args[1]["table_ss"]["checked"] == 3


# ── Fix 5: famílias de gémeas — prova da relação + plano ─────────────────────
def _member(rid, content: bytes, uploaded, result, hand=None):
    return {"id": rid, "file_hash": hashlib.sha256(content).hexdigest(),
            "uploaded_at": uploaded, "result": result, "reason_detail": None,
            "matched_hand_id": hand, "site": "Winamax", "tournament_name": "X",
            "tournament_number": "1", "players_left": 35, "total_entries": None,
            "vision_json": {"k": 1},
            "img_b64": base64.b64encode(content).decode()}


def test_twin_family_linked_by_decode_hash():
    # o img do membro A descodifica para os bytes cujo hash é o file_hash do B
    a = _member(1, b"original", datetime(2026, 7, 10), "json_invalid")
    b = _member(2, b"copia", datetime(2026, 7, 14), "success", hand="WN-1")
    a["img_b64"] = base64.b64encode(b"copia").decode()   # decode(A.img) → hash(B)
    assert table_ss._twin_family_linked([a, b]) is True
    # sem a relação (imgs sem correspondência) → False
    c = _member(3, b"outra", datetime(2026, 7, 15), "success")
    d = _member(4, b"solo", datetime(2026, 7, 16), "json_invalid")
    assert table_ss._twin_family_linked([d, c]) is False


def test_cleanup_dry_run_plan_and_no_writes():
    a = _member(1, b"original", datetime(2026, 7, 10), "json_invalid")
    a["img_b64"] = base64.b64encode(b"copia").decode()
    b = _member(2, b"copia", datetime(2026, 7, 14), "success", hand="WN-9")

    def _q(sql, params=None):
        if "DISTINCT original_filename" in sql:
            return [{"original_filename": "f.png"}]
        if "WHERE original_filename" in sql:
            return [a, b]
        if "FROM hands" in sql:
            return [{"n": 1}]
        return []

    with patch.object(table_ss, "query", side_effect=_q), \
         patch.object(table_ss, "get_conn") as mconn:
        res = table_ss.revision_twins_cleanup(dry_run=True)
    mconn.assert_not_called()                          # ensaio NUNCA escreve
    assert res["dry_run"] is True and res["deleted"] == 0
    fam = res["families"][0]
    assert fam["keeper_id"] == 1 and fam["donor_id"] == 2
    assert fam["donor_hand"] == "WN-9"
    assert fam["delete_ids"] == [2] and fam["hands_to_repoint"] == 1
    assert fam["action"] == "cure_keeper_and_delete_twins"


def test_cleanup_untouched_without_twin_proof():
    # 2 uploads legítimos com o mesmo nome mas SEM relação de hash → intactos
    a = _member(1, b"v1", datetime(2026, 7, 10), "json_invalid")
    b = _member(2, b"v2", datetime(2026, 7, 14), "success", hand="WN-9")

    def _q(sql, params=None):
        if "DISTINCT original_filename" in sql:
            return [{"original_filename": "f.png"}]
        if "WHERE original_filename" in sql:
            return [a, b]
        return []

    with patch.object(table_ss, "query", side_effect=_q):
        res = table_ss.revision_twins_cleanup(dry_run=True)
    assert res["families"] == []
