"""--only <canal>: corre SÓ esse canal (cano-a-cano). Valida o gating em main()
sem rede nem ficheiros reais (monkeypatch dos processadores por canal)."""
import os, tempfile
import pytest
import app_import as A

_EMPTY_IT = {"mesa": 0, "lobby": 0, "nonlobby": 0, "skip": 0, "retry": 0,
             "fail": 0, "fora": 0, "untagged_folder": 0}


def _patch(monkeypatch, calls):
    monkeypatch.setattr(A, "process_type",
                        lambda *a, **k: calls.append(("type", a[1])) or (0, 0, 0, 0))
    monkeypatch.setattr(A, "process_it_mixed",
                        lambda *a, **k: calls.append(("it", None)) or dict(_EMPTY_IT))
    monkeypatch.setattr(A, "process_lobby_subdir",
                        lambda *a, **k: calls.append(("lobby", None)) or (0, 0, 0, 0))
    monkeypatch.setattr(A, "process_gold_dir",
                        lambda *a, **k: calls.append(("gold", None)) or None)
    monkeypatch.setattr(A, "process_lobby_dir",
                        lambda *a, **k: calls.append(("lobby_dir", None)) or None)


def _run(monkeypatch, argv):
    calls = []
    _patch(monkeypatch, calls)
    tmp = tempfile.mkdtemp()
    monkeypatch.setattr(A, "PARENT_DIR", tmp)
    A.main(argv)                       # dry-run (sem --ao-vivo)
    return [c[0] for c in calls]


def test_only_it_runs_only_it(monkeypatch):
    chans = _run(monkeypatch, ["--only", "it"])
    assert "it" in chans
    assert "type" not in chans          # gg_hh/gg_ts/manual saltados
    assert "gold" not in chans
    assert "lobby" not in chans


def test_only_gold_runs_only_gold(monkeypatch):
    chans = _run(monkeypatch, ["--only", "gold"])
    assert chans == ["gold"]


def test_no_only_runs_all(monkeypatch):
    chans = _run(monkeypatch, [])
    # os 3 TYPES + it + lobby(subdir) + gold correm
    assert chans.count("type") == 3
    assert "it" in chans and "lobby" in chans and "gold" in chans


def test_only_rejects_unknown_channel(monkeypatch):
    # validação passou do argparse (choices) para o main() (aceita 'it/<subpasta>')
    with pytest.raises(SystemExit):
        _run(monkeypatch, ["--only", "banana"])


def test_only_it_subfolder_runs_only_it(monkeypatch):
    chans = _run(monkeypatch, ["--only", "it/SpeedRacer"])
    assert chans == ["it"]              # só o it; a subpasta é filtrada dentro do process_it_mixed


def test_subfolder_only_allowed_on_it(monkeypatch):
    with pytest.raises(SystemExit):    # subpasta num canal != it é erro claro
        _run(monkeypatch, ["--only", "manual/x"])
