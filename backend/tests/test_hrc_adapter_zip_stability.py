"""pt85 C' (i, #HRC-ADAPTER-ZIP-STABILITY) — guarda de estabilidade do adapter.

Antes de POSTar, o adapter exige zip com tamanho ESTÁVEL (2 leituras) + válido
(testzip). Robusto a ler o export a meio da escrita do HRC (causa-raiz candidata
do GG-6082958318 corrompido). Instável/inválido → skip este tick (retry), NÃO
marca failed (o watcher/Peça-A trata do permanentemente-mau).
"""
from __future__ import annotations

import sys
import zipfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

_HERE = Path(__file__).resolve().parent
_TOOLS = _HERE.parent.parent / "tools" / "hrc_adapter"
sys.path.insert(0, str(_TOOLS))

import hrc_adapter  # noqa: E402


def _valid_zip(p: Path) -> Path:
    with zipfile.ZipFile(p, "w") as z:
        z.writestr("hh.txt", "PokerStars Hand #1")
    return p


# ── _zip_is_stable_and_valid ────────────────────────────────────────────────
def test_stable_valid_zip_ok(tmp_path):
    p = _valid_zip(tmp_path / "GG-1.zip")
    ok, why = hrc_adapter._zip_is_stable_and_valid(p, settle_s=0.0)
    assert ok and why == "ok"


def test_invalid_not_a_zip(tmp_path):
    p = tmp_path / "GG-2.zip"
    p.write_bytes(b"isto nao e um zip")          # estável mas inválido
    ok, why = hrc_adapter._zip_is_stable_and_valid(p, settle_s=0.0)
    assert not ok and why == "invalid"


def test_zero_byte_unstable(tmp_path):
    p = tmp_path / "GG-3.zip"
    p.write_bytes(b"")                            # 0 bytes = ainda a escrever
    ok, why = hrc_adapter._zip_is_stable_and_valid(p, settle_s=0.0)
    assert not ok and why == "unstable"


def test_growing_file_unstable(tmp_path, monkeypatch):
    p = tmp_path / "GG-4.zip"
    p.write_bytes(b"PK\x03\x04partial")
    # o "sleep" entre as 2 leituras faz o ficheiro CRESCER → tamanho muda → instável
    def _grow(_s):
        p.write_bytes(p.read_bytes() + b"mais-bytes")
    monkeypatch.setattr(hrc_adapter, "time", SimpleNamespace(sleep=_grow))
    ok, why = hrc_adapter._zip_is_stable_and_valid(p, settle_s=2.0)
    assert not ok and why == "unstable"


# ── post_done respeita a guarda ─────────────────────────────────────────────
def _sess_200():
    s = MagicMock()
    s.post.return_value = MagicMock(status_code=200, text="{}")
    s.post.return_value.json = MagicMock(return_value={"action": "insert"})
    return s


def test_post_done_skips_unstable(tmp_path, monkeypatch):
    monkeypatch.setattr(hrc_adapter, "_zip_is_stable_and_valid",
                        lambda *_a, **_k: (False, "unstable"))
    s = _sess_200()
    p = _valid_zip(tmp_path / "GG-5.zip")
    assert hrc_adapter.post_done(s, "http://x", "GG-5", p) is False
    s.post.assert_not_called()                    # não POSTou, retry no próximo tick


def test_post_done_skips_invalid(tmp_path, monkeypatch):
    monkeypatch.setattr(hrc_adapter, "_zip_is_stable_and_valid",
                        lambda *_a, **_k: (False, "invalid"))
    s = _sess_200()
    p = tmp_path / "GG-6.zip"
    p.write_bytes(b"lixo")
    assert hrc_adapter.post_done(s, "http://x", "GG-6", p) is False
    s.post.assert_not_called()


def test_post_done_proceeds_when_ok(tmp_path, monkeypatch):
    monkeypatch.setattr(hrc_adapter, "_zip_is_stable_and_valid",
                        lambda *_a, **_k: (True, "ok"))
    s = _sess_200()
    p = _valid_zip(tmp_path / "GG-7.zip")
    assert hrc_adapter.post_done(s, "http://x", "GG-7", p) is True
    s.post.assert_called_once()                   # estável+válido → POSTou
