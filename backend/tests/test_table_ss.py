"""Tests para routers/table_ss + integração com queue_export/hrc_queue (pt38).

Pattern de mocks alinhado com test_lobby_sync.py (asyncio.run + unittest.mock).
"""
import asyncio
import json
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock, AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routers import table_ss


CAP = datetime(2026, 5, 23, 16, 4, 0, tzinfo=timezone.utc)


def _cand(hid, tn, secs_off=0):
    return {
        "id": hid, "hand_id": f"WN-{hid}", "tournament_number": tn,
        "tournament_name": "ODYSSEY #013", "site": "Winamax",
        "played_at": CAP,
    }


# ── _resolve_match ───────────────────────────────────────────────────────────

def test_resolve_match_no_candidates():
    m = table_ss._resolve_match(CAP, {"tournament_name": "X"}, "Winamax", [])
    assert m["matched"] is None
    assert m["reason"] == "no_hands_in_window"
    assert m["ambiguous"] is False


def test_resolve_match_single_tn_matches_closest():
    cands = [_cand(10, "T1"), _cand(11, "T1")]
    m = table_ss._resolve_match(CAP, {"tournament_name": "X"}, "Winamax", cands)
    assert m["matched"]["id"] == 10  # primeira (mais próxima)
    assert m["tn"] == "T1"
    assert m["reason"] == "single_tn"


@patch("app.routers.table_ss.resolve_tournament_number", return_value=("T2", []))
def test_resolve_match_multi_tn_disambiguated_by_name(_mock_res):
    cands = [_cand(10, "T1"), _cand(20, "T2")]
    m = table_ss._resolve_match(
        CAP, {"tournament_name": "ODYSSEY #013"}, "Winamax", cands,
    )
    assert m["matched"]["id"] == 20
    assert m["tn"] == "T2"
    assert m["reason"] == "disambiguated_by_name"


@patch("app.routers.table_ss.resolve_tournament_number", return_value=(None, []))
def test_resolve_match_multi_tn_resolver_none_ambiguous(_mock_res):
    cands = [_cand(10, "T1"), _cand(20, "T2")]
    m = table_ss._resolve_match(CAP, {"tournament_name": "X"}, "Winamax", cands)
    assert m["matched"] is None
    assert m["ambiguous"] is True
    assert m["reason"].startswith("multi_tn_unresolved")


@patch("app.routers.table_ss.resolve_tournament_number", return_value=("T9", []))
def test_resolve_match_multi_tn_resolver_outside_set_ambiguous(_mock_res):
    cands = [_cand(10, "T1"), _cand(20, "T2")]
    m = table_ss._resolve_match(CAP, {"tournament_name": "X"}, "Winamax", cands)
    assert m["matched"] is None
    assert m["ambiguous"] is True


# ── _upsert_table_ss_log ─────────────────────────────────────────────────────

def test_upsert_invalid_result_raises():
    with pytest.raises(ValueError, match="invalid result"):
        table_ss._upsert_table_ss_log(
            file_hash="h", source="manual_upload", original_filename=None,
            file_size=None, result="gibberish",
        )


@patch("app.routers.table_ss.get_conn")
def test_upsert_insert_on_conflict_and_links_hand(mock_get_conn):
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_cur.fetchone.return_value = {"id": 7}
    mock_conn.cursor.return_value.__enter__.return_value = mock_cur
    mock_get_conn.return_value = mock_conn

    rid = table_ss._upsert_table_ss_log(
        file_hash="abc", source="manual_upload", original_filename="x.png",
        file_size=123, result="success", site="Winamax",
        tournament_name="ODYSSEY #013", tournament_number="T1",
        players_left=71, total_entries=124, captured_at=CAP,
        matched_hand_id="WN-10", vision_json={"a": 1}, matched_hand_db_id=10,
    )
    assert rid == 7
    sqls = [" ".join(c[0][0].split()) for c in mock_cur.execute.call_args_list]
    assert any("ON CONFLICT (file_hash)" in s for s in sqls)
    assert any(
        "attempt_count = table_ss_processing_log.attempt_count + 1" in s
        for s in sqls
    )
    # Liga a mão na mesma transacção.
    assert any("UPDATE hands SET context_table_ss_id = %s" in s for s in sqls)
    mock_conn.commit.assert_called_once()


@patch("app.routers.table_ss.get_conn")
def test_upsert_no_link_when_not_success(mock_get_conn):
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_cur.fetchone.return_value = {"id": 8}
    mock_conn.cursor.return_value.__enter__.return_value = mock_cur
    mock_get_conn.return_value = mock_conn

    table_ss._upsert_table_ss_log(
        file_hash="abc", source="manual_upload", original_filename="x.png",
        file_size=1, result="no_match_to_hand", matched_hand_db_id=10,
    )
    sqls = [" ".join(c[0][0].split()) for c in mock_cur.execute.call_args_list]
    assert not any("UPDATE hands" in s for s in sqls)


# ── _process_table_ss (orquestração) ─────────────────────────────────────────

def _run_process(**patches):
    return asyncio.run(table_ss._process_table_ss(
        b"\x89PNG\r\n\x1a\nx", "Shot1-Winamax-20260523170400.png",
    ))


@patch("app.routers.table_ss._upsert_table_ss_log", return_value=1)
@patch("app.routers.table_ss.tv.extract_table_ss_json", return_value=None)
@patch("app.routers.table_ss.query", return_value=[])
def test_process_vision_failed(_q, _ex, _up):
    out = _run_process()
    assert out["result"] == "vision_failed"
    _up.assert_called_once()


@patch("app.routers.table_ss._upsert_table_ss_log", return_value=1)
@patch("app.routers.table_ss.tv.extract_table_ss_json", return_value="not json at all")
@patch("app.routers.table_ss.query", return_value=[])
def test_process_json_invalid(_q, _ex, _up):
    out = _run_process()
    assert out["result"] == "json_invalid"


@patch("app.routers.table_ss._upsert_table_ss_log", return_value=1)
@patch("app.routers.table_ss.tv.extract_table_ss_json",
       return_value='{"site":"PartyPoker","tournament_name":"X","players_left":50}')
@patch("app.routers.table_ss.query", return_value=[])
def test_process_site_undetected(_q, _ex, _up):
    out = _run_process()
    assert out["result"] == "site_undetected"
    assert out["site"] == "PartyPoker"


@patch("app.routers.table_ss._upsert_table_ss_log", return_value=1)
@patch("app.routers.table_ss._find_candidate_hands",
       return_value=[{"id": 10, "hand_id": "WN-10", "tournament_number": "T1",
                      "tournament_name": "ODYSSEY #013", "site": "Winamax",
                      "played_at": CAP}])
@patch("app.routers.table_ss.tv.extract_table_ss_json",
       return_value='{"site":"Winamax","tournament_name":"ODYSSEY #013",'
                    '"players_left":71,"total_entries":124}')
@patch("app.routers.table_ss.query", return_value=[])
def test_process_success_links_hand(_q, _ex, _find, _up):
    out = _run_process()
    assert out["result"] == "success"
    assert out["hand_matched"] == "WN-10"
    assert out["players_left"] == 71
    assert out["tournament_number"] == "T1"
    # _upsert chamado com matched_hand_db_id=10 (liga a mão)
    assert _up.call_args.kwargs["matched_hand_db_id"] == 10


@patch("app.routers.table_ss._upsert_table_ss_log", return_value=1)
@patch("app.routers.table_ss.resolve_tournament_number", return_value=("T9", []))
@patch("app.routers.table_ss._find_candidate_hands", return_value=[])
@patch("app.routers.table_ss.tv.extract_table_ss_json",
       return_value='{"site":"Winamax","tournament_name":"ODYSSEY #013","players_left":71}')
@patch("app.routers.table_ss.query", return_value=[])
def test_process_no_match_stores_resolver_tn(_q, _ex, _find, _res, _up):
    out = _run_process()
    assert out["result"] == "no_match_to_hand"
    assert out["tournament_number"] == "T9"  # guardado p/ limbo linkável
    assert out["hand_matched"] is None


@patch("app.routers.table_ss.tv.extract_table_ss_json")
@patch("app.routers.table_ss.query",
       return_value=[{"result": "success", "site": "Winamax",
                      "tournament_name": "ODYSSEY #013", "tournament_number": "T1",
                      "players_left": 71, "total_entries": 124,
                      "matched_hand_id": "WN-10", "captured_at": CAP,
                      "vision_json": {"a": 1}}])
def test_process_dedup_success_short_circuits(_q, _ex):
    out = _run_process()
    assert out["dedup"] is True
    assert out["result"] == "success"
    assert out["players_left"] == 71
    _ex.assert_not_called()  # não re-corre a Vision


# ── Endpoint ─────────────────────────────────────────────────────────────────

def _make_app():
    from app.auth import require_auth
    app = FastAPI()
    app.include_router(table_ss.router)
    app.dependency_overrides[require_auth] = lambda: {"id": 1, "email": "t@t"}
    return app


def test_endpoint_unauthorized_401():
    app = FastAPI()
    app.include_router(table_ss.router)
    client = TestClient(app)
    r = client.post("/api/table-ss/upload",
                    files={"file": ("x.png", b"x", "image/png")})
    assert r.status_code == 401


def test_endpoint_empty_file_400():
    app = _make_app()
    client = TestClient(app)
    r = client.post("/api/table-ss/upload",
                    files={"file": ("x.png", b"", "image/png")})
    assert r.status_code == 400


@patch("app.routers.table_ss._process_table_ss", new_callable=AsyncMock)
def test_endpoint_success_returns_process_dict(mock_proc):
    mock_proc.return_value = {"result": "success", "hand_matched": "WN-10",
                             "players_left": 71}
    app = _make_app()
    client = TestClient(app)
    r = client.post("/api/table-ss/upload",
                    files={"file": ("x.png", b"\x89PNGdata", "image/png")})
    assert r.status_code == 200
    assert r.json()["result"] == "success"
    assert r.json()["hand_matched"] == "WN-10"


# ── Integração _resolve_players_left (queue_export) ──────────────────────────

def test_resolve_players_left_prefers_context_table_ss():
    from app.services import queue_export
    with patch("app.db.query", return_value=[{"players_left": 71}]) as mq:
        v = queue_export._resolve_players_left(
            {"context_table_ss_id": 5, "tournament_number": "T1"}, None,
        )
    assert v == 71
    # query foi à table_ss_processing_log
    assert "table_ss_processing_log" in mq.call_args[0][0]


def test_resolve_players_left_falls_back_to_lobby_when_no_context():
    from app.services import queue_export
    with patch("app.db.query", return_value=[{"players_left": 99}]) as mq:
        v = queue_export._resolve_players_left(
            {"tournament_number": "T1"}, None,
        )
    assert v == 99
    assert "lobby_processing_log" in mq.call_args[0][0]


def test_resolve_players_left_none_when_nothing():
    from app.services import queue_export
    v = queue_export._resolve_players_left({}, None)
    assert v is None


# ── hrc_queue SELECT inclui context_table_ss_id ─────────────────────────────

def test_select_andar1_selects_context_table_ss_id():
    from app.services import hrc_queue
    from datetime import timedelta
    now = datetime.now(timezone.utc)
    with patch("app.services.hrc_queue.query", return_value=[]) as mq:
        hrc_queue.select_andar1_rows(["icm"], ["new"], now - timedelta(days=1), now)
    sql = mq.call_args[0][0]
    assert "context_table_ss_id" in sql
