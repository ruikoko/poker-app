"""#IMPORT-MODAL-MISROUTES-TS-RESULTS — routing do /api/import por conteúdo.

Sem DB real: mock de get_conn + funções de persistência. Asserta a DECISÃO de
encaminhamento (TS GG → ambos; TS WN → só P&L; HH → hands; unknown → 400),
não o trabalho de BD. Padrão de mocks alinhado com test_tournament_summaries.py.
"""
import asyncio
import io
import zipfile
from unittest.mock import patch, MagicMock

import pytest
from fastapi import HTTPException

from app.routers.import_ import import_file


class _FakeUpload:
    def __init__(self, filename, content):
        self.filename = filename
        self._content = content

    async def read(self):
        return self._content


def _zip_bytes(files):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, text in files:
            zf.writestr(name, text)
    return buf.getvalue()


# ── TS GGPoker → AMBOS (tournament_summaries operacional + P&L) ──────────────

@patch("app.routers.tournament_summaries._extract_txt_files", return_value=[("ts.txt", b"x")])
@patch("app.routers.tournament_summaries.persist_tournament_summaries",
       return_value={"total": 1, "inserted": 1, "updated": 0, "skipped_pre_2026": 0, "failed": []})
@patch("app.routers.import_._update_log")
@patch("app.routers.import_._run_tournament_import", return_value=(2, 0))
@patch("app.routers.import_._create_log", return_value=42)
@patch("app.routers.import_.get_conn")
@patch("app.routers.import_.create_entry", return_value={"id": 7})
@patch("app.routers.import_._detect_zip_content_type", return_value="tournament_summary")
@patch("app.routers.import_._detect_site", return_value="ggpoker")
def test_ts_gg_populates_both(_site, _ctype, _entry, _conn, _clog, m_run, _ulog, m_persist, _extract):
    with patch.dict("app.routers.import_.SUMMARY_PARSERS",
                    {"ggpoker": MagicMock(return_value=([{"x": 1}, {"x": 2}], []))}, clear=True):
        r = asyncio.run(import_file(file=_FakeUpload("results.zip", b"PK\x03\x04"),
                                    site=None, current_user=object()))
    assert r["import_type"] == "tournament_summary"
    assert r["ts_applicable"] is True
    assert r["ts_inserted"] == 1
    assert r["pnl_inserted"] == 2
    assert r["status"] == "ok"
    m_persist.assert_called_once()      # operacional correu
    m_run.assert_called_once()          # P&L correu


# ── TS Winamax → só P&L (operacional é GG-only) ──────────────────────────────

@patch("app.routers.tournament_summaries.persist_tournament_summaries")
@patch("app.routers.import_._update_log")
@patch("app.routers.import_._run_tournament_import", return_value=(3, 1))
@patch("app.routers.import_._create_log", return_value=99)
@patch("app.routers.import_.get_conn")
@patch("app.routers.import_.create_entry", return_value={"id": 8})
@patch("app.routers.import_._detect_zip_content_type", return_value="tournament_summary")
@patch("app.routers.import_._detect_site", return_value="winamax")
def test_ts_winamax_pnl_only(_site, _ctype, _entry, _conn, _clog, m_run, _ulog, m_persist):
    with patch.dict("app.routers.import_.SUMMARY_PARSERS",
                    {"winamax": MagicMock(return_value=([{"x": 1}], []))}, clear=True):
        r = asyncio.run(import_file(file=_FakeUpload("wn.zip", b"PK\x03\x04"),
                                    site=None, current_user=object()))
    assert r["import_type"] == "tournament_summary"
    assert r["ts_applicable"] is False     # operacional NÃO aplicável a WN
    assert r["pnl_inserted"] == 3
    m_persist.assert_not_called()          # operacional NÃO correu


# ── HH ZIP → hands (regressão: não toca o pipeline TS) ───────────────────────

@patch("app.routers.tournament_summaries.persist_tournament_summaries")
@patch("app.routers.import_._insert_hand", return_value=True)
@patch("app.routers.import_._parse_hh_file", return_value=([{"hand_id": "GG-1", "played_at": "2026-05-01"}], []))
@patch("app.routers.import_.is_pre_2026", return_value=False)
@patch("app.routers.import_.get_conn")
@patch("app.routers.import_.create_entry", return_value={"id": 9})
@patch("app.routers.import_._detect_zip_content_type", return_value="hand_history")
@patch("app.routers.import_._detect_site", return_value="ggpoker")
def test_hh_zip_goes_to_hands(_site, _ctype, _entry, _conn, _pre, _parse, _ins, m_persist):
    content = _zip_bytes([("h.txt", "Poker Hand #1: ...")])
    r = asyncio.run(import_file(file=_FakeUpload("hh.zip", content),
                                site=None, current_user=object()))
    assert r["import_type"] == "hands"
    assert r["hands_inserted"] == 1
    m_persist.assert_not_called()          # TS pipeline intocado


# ── HH .txt → hands (regressão) ──────────────────────────────────────────────

@patch("app.routers.tournament_summaries.persist_tournament_summaries")
@patch("app.routers.import_._insert_hand", return_value=True)
@patch("app.routers.import_._parse_hh_file", return_value=([{"hand_id": "GG-2", "played_at": "2026-05-01"}], []))
@patch("app.routers.import_.is_pre_2026", return_value=False)
@patch("app.routers.import_.get_conn")
@patch("app.routers.import_.create_entry", return_value={"id": 10})
@patch("app.routers.import_.classify_entry", return_value={"entry_type": "hand_history"})
@patch("app.routers.import_._detect_site", return_value="pokerstars")
def test_hh_txt_goes_to_hands(_site, _classify, _entry, _conn, _pre, _parse, _ins, m_persist):
    r = asyncio.run(import_file(file=_FakeUpload("hand.txt", b"PokerStars Hand #1: ..."),
                                site=None, current_user=object()))
    assert r["import_type"] == "hands"
    assert r["hands_inserted"] == 1
    m_persist.assert_not_called()


# ── Conteúdo não reconhecido → 400 claro (decisão #1, nunca "Importado") ─────

@patch("app.routers.import_.create_entry", return_value={"id": 11})
@patch("app.routers.import_._detect_zip_content_type", return_value="unknown")
@patch("app.routers.import_._detect_site", return_value=None)
@patch("app.routers.import_._detect_site_from_zip", return_value=None)
def test_unknown_zip_rejected_400(_sitezip, _site, _ctype, _entry):
    with pytest.raises(HTTPException) as exc:
        asyncio.run(import_file(file=_FakeUpload("mystery.zip", b"PK\x03\x04"),
                                site=None, current_user=object()))
    assert exc.value.status_code == 400
    assert "não reconhecido" in exc.value.detail.lower()
