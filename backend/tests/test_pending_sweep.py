"""Varredor independente de pendentes (#PENDING-SWEEP-GUARANTEED):
re-Vision das SS falhadas + sweep + arranque. Ver lobby_sync.sweep_pending /
start_pending_sweeper e table_ss.retry_failed_table_ss_vision."""
import base64
from unittest.mock import patch, MagicMock

import app.routers.table_ss as ts
from app.services import lobby_sync


# ── retry_failed_table_ss_vision ─────────────────────────────────────────────
# #REVISION-CURE-IN-PLACE (24 Jul): o retry passou a curar NA PRÓPRIA row via
# `_reprocess_failed_row` (o caminho antigo `_process_table_ss` criava gémeas por
# hash-da-cópia) e ganhou o tecto `exhausted`. Testes alinhados ao contrato novo;
# cobertura fina em test_revision_cure.py.

def test_retry_revision_limit_zero_is_noop():
    with patch("app.routers.table_ss.query") as mq:
        res = ts.retry_failed_table_ss_vision(limit=0)
    assert res == {"retried": 0, "now_success": 0, "still_failed": 0,
                   "exhausted": 0}
    mq.assert_not_called()


@patch("app.routers.table_ss._reprocess_failed_row")
@patch("app.routers.table_ss.query")
def test_retry_revision_reads_and_counts(mq, mrep):
    img = base64.b64encode(b"fakejpg").decode()
    mq.return_value = [
        {"id": 1, "original_filename": "f.jpg", "img_b64": img,
         "folder_tag": None, "captured_at": None, "attempt_count": 1},
        {"id": 2, "original_filename": "g.jpg", "img_b64": img,
         "folder_tag": "SpeedRacer", "captured_at": None, "attempt_count": 2},
    ]

    async def _fake(row):
        # cura na PRÓPRIA row (recebe a row inteira, não bytes soltos)
        return {"id": row["id"],
                "result": "success" if row["id"] == 1 else "json_invalid"}

    mrep.side_effect = _fake
    res = ts.retry_failed_table_ss_vision(limit=5)
    assert res == {"retried": 2, "now_success": 1, "still_failed": 1,
                   "exhausted": 0}
    # só re-tenta os estados de falha da Vision, com a imagem guardada
    params = mq.call_args[0][1]
    assert params[0] == list(ts._VISION_RETRY_RESULTS)
    assert params[1] == 5


@patch("app.routers.table_ss._reprocess_failed_row")
@patch("app.routers.table_ss.query")
def test_retry_revision_tolerates_errors(mq, mrep):
    mq.return_value = [
        {"id": 3, "original_filename": "a.jpg", "img_b64": "aa==",
         "folder_tag": None, "captured_at": None, "attempt_count": 1},
    ]

    async def _boom(row):
        raise RuntimeError("vision down")

    mrep.side_effect = _boom
    res = ts.retry_failed_table_ss_vision(limit=3)   # não lança
    assert res == {"retried": 1, "now_success": 0, "still_failed": 1,
                   "exhausted": 0}


# ── sweep_pending ────────────────────────────────────────────────────────────
def test_sweep_pending_runs_all_three_pending_only(monkeypatch):
    calls = []
    monkeypatch.setattr(ts, "reconcile_table_ss",
                        lambda pending_only=False: calls.append(("recon", pending_only)) or {"checked": 1})
    monkeypatch.setattr(lobby_sync, "reconcile_lobby_logs",
                        lambda: calls.append(("lobby",)) or {"resolved": 0})
    monkeypatch.setattr(ts, "retry_failed_table_ss_vision",
                        lambda limit=5: calls.append(("rev", limit)) or {"retried": 0})
    res = lobby_sync.sweep_pending(reason="test")
    assert ("recon", True) in calls          # pending_only no varredor
    assert ("lobby",) in calls
    assert any(c[0] == "rev" for c in calls)
    assert set(res) == {"table_ss", "lobby", "revision"}


def test_sweep_pending_is_defensive(monkeypatch):
    def _boom(*a, **k):
        raise RuntimeError("db down")
    monkeypatch.setattr(ts, "reconcile_table_ss", _boom)
    monkeypatch.setattr(lobby_sync, "reconcile_lobby_logs", _boom)
    monkeypatch.setattr(ts, "retry_failed_table_ss_vision", _boom)
    # cada passo isolado num try/except → não lança, devolve dict (vazio aqui)
    assert lobby_sync.sweep_pending(reason="test") == {}


# ── start_pending_sweeper ────────────────────────────────────────────────────
def test_start_sweeper_disabled_by_env(monkeypatch):
    monkeypatch.setenv("PENDING_SWEEP_ENABLED", "false")
    started = []
    monkeypatch.setattr(lobby_sync.threading, "Thread",
                        lambda *a, **k: started.append(1) or MagicMock())
    lobby_sync.start_pending_sweeper()
    assert started == []


def test_start_sweeper_launches_two_daemon_threads(monkeypatch):
    monkeypatch.setenv("PENDING_SWEEP_ENABLED", "true")
    monkeypatch.setenv("PENDING_SWEEP_INTERVAL_MIN", "20")
    made = []

    class _FakeThread:
        def __init__(self, *a, **k):
            made.append(k.get("daemon"))
        def start(self):
            pass

    monkeypatch.setattr(lobby_sync.threading, "Thread", _FakeThread)
    lobby_sync.start_pending_sweeper()
    assert made == [True, True]   # arranque + tick, ambos daemon
