"""pt85 C' (ii) — `_verify_export_zip` do watcher (validade do export logo após Save).

Após o [SAVE-AS], o watcher espera o ficheiro estabilizar e corre testzip(), logando
`[SAVE-AS-CHECK] OK` / `INVÁLIDO` para apanhar recorrência do export corrompido
(GG-6082958318). Observabilidade — não bloqueia nem altera o fluxo.
"""
from __future__ import annotations

import sys
import zipfile
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_WATCHER_SRC = _HERE.parent.parent / "tools" / "watcher_src"
sys.path.insert(0, str(_WATCHER_SRC))


def _pf():
    if "patched_funcs" in sys.modules:
        del sys.modules["patched_funcs"]
    import patched_funcs as p  # noqa: E402
    return p


def test_save_as_check_logs_ok_for_valid_zip(tmp_path, capsys):
    p = _pf()
    z = tmp_path / "GG-OK.zip"
    with zipfile.ZipFile(z, "w") as zf:
        zf.writestr("nodes/0.json", "{}")
    p._verify_export_zip(str(z), settle_s=0.1, wait_total_s=5.0)
    out = capsys.readouterr().out
    assert "[SAVE-AS-CHECK] OK" in out
    assert "INVÁLIDO" not in out


def test_save_as_check_logs_invalid_for_bad_zip(tmp_path, capsys):
    p = _pf()
    z = tmp_path / "GG-BAD.zip"
    z.write_bytes(b"isto nao e um zip valido")     # o caso GG-6082958318
    p._verify_export_zip(str(z), settle_s=0.1, wait_total_s=5.0)
    out = capsys.readouterr().out
    assert "[SAVE-AS-CHECK] INVÁLIDO" in out


def test_save_as_check_invalid_when_file_never_appears(tmp_path, capsys):
    p = _pf()
    z = tmp_path / "GG-MISSING.zip"                # nunca criado
    p._verify_export_zip(str(z), settle_s=0.1, wait_total_s=1.0)
    out = capsys.readouterr().out
    assert "[SAVE-AS-CHECK] INVÁLIDO" in out
