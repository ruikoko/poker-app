"""pt61 (#HRC-EXPORT-WRITES-BUT-FINALIZE-HANGS) — tests para o handshake
`replied/` do adaptador HRC: `_move_to_replied` (desbloqueia o arquivar+avançar
do watcher Baltazar) + `prune_replied` (retention, sem acumular). Importa
`hrc_adapter` (puxa requests) — skip se ausente."""
import sys
import time
from pathlib import Path

import pytest

pytest.importorskip("requests")

_HERE = Path(__file__).resolve().parent
_TOOLS = _HERE.parent.parent / "tools" / "hrc_adapter"
sys.path.insert(0, str(_TOOLS))

import hrc_adapter as ha  # noqa: E402


def test_move_to_replied_exports_layout(tmp_path):
    """Layout do watcher: zip em done/Exports/<hand>.zip → move para
    done/Exports/replied/<hand>.zip (= o que `zip_is_ready` observa:
    dirname(export)/replied/). Original some; replied passa a existir."""
    exports = tmp_path / "done" / "Exports"
    exports.mkdir(parents=True)
    zp = exports / "GG-6027751209.zip"
    zp.write_bytes(b"PK\x03\x04 fake zip")

    ha._move_to_replied(zp)

    assert not zp.exists()                                   # saiu de Exports
    dest = exports / "replied" / "GG-6027751209.zip"
    assert dest.exists()                                     # aterrou em replied/
    assert dest.read_bytes() == b"PK\x03\x04 fake zip"


def test_move_to_replied_not_visible_to_detect_done_zips(tmp_path):
    """Guardrail (i) — sem loop: após mover p/ replied/, `detect_done_zips` já
    NÃO encontra o zip (só varre done/*.zip + done/Exports/*.zip, não replied/)
    → 0 re-POST."""
    exports = tmp_path / "done" / "Exports"
    exports.mkdir(parents=True)
    zp = exports / "GG-1.zip"
    zp.write_bytes(b"x")
    assert ha.detect_done_zips(tmp_path) == [zp]             # antes: detectável

    ha._move_to_replied(zp)

    assert ha.detect_done_zips(tmp_path) == []               # depois: fora do radar


def test_prune_replied_removes_old_keeps_fresh(tmp_path):
    """Guardrail (ii) — replied/ não acumula: prune apaga zips mais velhos que
    max_age_s, mantém os frescos (o watcher ainda pode não os ter consumido)."""
    replied = tmp_path / "done" / "Exports" / "replied"
    replied.mkdir(parents=True)
    old = replied / "GG-old.zip"
    old.write_bytes(b"old")
    fresh = replied / "GG-fresh.zip"
    fresh.write_bytes(b"fresh")
    # Envelhece o `old` 2h para trás (mtime).
    two_h_ago = time.time() - 7200
    import os
    os.utime(old, (two_h_ago, two_h_ago))

    ha.prune_replied(tmp_path, max_age_s=3600)

    assert not old.exists()       # > 1h → apagado
    assert fresh.exists()         # fresco → mantido


def test_prune_replied_noop_when_no_replied_dir(tmp_path):
    """Sem pasta replied/ → no-op silencioso (não cria, não rebenta)."""
    (tmp_path / "done").mkdir()
    ha.prune_replied(tmp_path)    # não levanta
    assert not (tmp_path / "done" / "replied").exists()
