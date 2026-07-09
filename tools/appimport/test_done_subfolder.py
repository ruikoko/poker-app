"""#ICM-FT-TAG-NOT-LANDING — o move para o done PRESERVA a subpasta (a subpasta é a
tag). Testa os DOIS sentidos: (1) destino no done mantém a subpasta; (2) esse nome
de subpasta volta a bater no _folder_tag_for → mesma tag (reimporte não perde nada)."""
import os
from app_import import (
    _done_subdir, _folder_tag_for, CANONICAL_FOLDER_FOR_TAG, IT_FOLDER_TAGS,
)


def test_done_subdir_root_stays_root():
    assert _done_subdir(r"C:\d\done\it", "") == r"C:\d\done\it"


def test_done_subdir_preserves_subfolder():
    assert _done_subdir(r"C:\d\done\it", "ICM PKO") == os.path.join(r"C:\d\done\it", "ICM PKO")
    assert _done_subdir(r"C:\d\done\it", "SpeedRacer") == os.path.join(r"C:\d\done\it", "SpeedRacer")


def test_canonical_folder_roundtrips_to_same_tag():
    # sentido 2: cada nome canónico do done tem de reconhecer a MESMA tag no reimporte.
    for tag, folder in CANONICAL_FOLDER_FOR_TAG.items():
        assert _folder_tag_for(folder) == tag, f"{folder!r} → {_folder_tag_for(folder)!r} != {tag!r}"


def test_every_tag_has_a_canonical_folder():
    # todas as tags que uma pasta produz têm de ter nome canónico p/ reconstruir o done.
    tags_from_folders = set(IT_FOLDER_TAGS.values())
    assert tags_from_folders <= set(CANONICAL_FOLDER_FOR_TAG), (
        tags_from_folders - set(CANONICAL_FOLDER_FOR_TAG))


def test_live_subfolder_name_roundtrips():
    # sentido 1→2: qualquer nome de subpasta VIVA reconhecido preserva-se e volta a bater.
    for folder_key in IT_FOLDER_TAGS:
        tag = _folder_tag_for(folder_key)
        assert tag is not None
        # o move preserva o basename tal-e-qual → reler a mesma subpasta dá a mesma tag
        assert _folder_tag_for(folder_key) == tag


# ── tidy_done_it.plan_moves (arrumação do done achatado) ──────────────────────
def test_plan_moves_rehouses_known_leaves_unknown():
    from tidy_done_it import plan_moves
    name2tag = {"a.png": "icm-pko", "b.png": "speed-racer", "c.png": "nota"}
    files = ["a.png", "b.png", "c.png", "loose.png"]   # loose.png não está na BD
    plan, no_ev = plan_moves(files, name2tag)
    assert no_ev == ["loose.png"]                       # sem tag → fica na raiz
    subs = {f: sub for f, _, sub in plan}
    assert subs == {"a.png": "ICM PKO", "b.png": "SpeedRacer", "c.png": "Nota"}


def test_plan_moves_unknown_tag_not_in_canonical_stays_root():
    from tidy_done_it import plan_moves
    # tag existe na BD mas não tem pasta canónica (defensivo) → fica na raiz
    plan, no_ev = plan_moves(["x.png"], {"x.png": "tag-desconhecida"})
    assert plan == [] and no_ev == ["x.png"]


# ── tidy: resolução da pasta-mãe (bug do 1º dry-run: PARENT_DIR=None → TypeError) ──
import pytest


def test_resolve_done_it_guards_missing_parent(monkeypatch):
    import app_import as ai
    import tidy_done_it as t
    monkeypatch.setattr(ai, "load_config", lambda: None)   # não sobrepõe PARENT_DIR
    monkeypatch.setattr(ai, "PARENT_DIR", None)            # simula config por preencher
    with pytest.raises(SystemExit):                        # mensagem clara, NÃO TypeError
        t.resolve_done_it()


def test_resolve_done_it_builds_path_when_configured(monkeypatch):
    import app_import as ai
    import tidy_done_it as t
    monkeypatch.setattr(ai, "load_config", lambda: None)
    monkeypatch.setattr(ai, "PARENT_DIR", r"C:\Batmen")
    assert t.resolve_done_it() == os.path.join(r"C:\Batmen", "done", ai.IT_SUB)


def test_reconcile_db_categorizes_missing():
    from tidy_done_it import reconcile_db
    db = ["a.png", "b.png", "c.png", "d.png"]
    root = ["a.png"]                                    # só a.png na raiz do done
    sub_index = {"b.png": r"ICM PKO\b.png"}             # b.png já numa subpasta
    em_sub, ausentes = reconcile_db(db, root, sub_index)
    assert em_sub == [("b.png", r"ICM PKO\b.png")]      # em subpasta
    assert ausentes == ["c.png", "d.png"]               # nem raiz nem subpasta


def test_canonical_pos_nko_is_live_folder_npko():
    import app_import as ai
    assert ai.CANONICAL_FOLDER_FOR_TAG["pos-nko"] == "NPKO Pos"      # pasta VIVA do disco
    assert ai._folder_tag_for("NPKO Pos") == "pos-nko"              # round-trip real


# ── --only it/<subpasta> (filtro por subpasta) ───────────────────────────────
def test_parse_only_channel_and_subfolder():
    from app_import import _parse_only
    assert _parse_only("it/SpeedRacer") == ("it", "SpeedRacer")
    assert _parse_only("it\ICM PKO") == ("it", "ICM PKO")   # backslash tolerado
    assert _parse_only("it") == ("it", "")
    assert _parse_only(None) == (None, "")


def test_it_subfolder_matches_exact_and_by_tag():
    from app_import import _it_subfolder_matches
    assert _it_subfolder_matches("SpeedRacer", "SpeedRacer")     # exacto
    assert _it_subfolder_matches("SpeedRacer", "speedracer")     # case-insensitive
    assert _it_subfolder_matches("SpeedRacer", "Speed Racer")    # mesma tag (espaço)
    assert _it_subfolder_matches("NPKO Pos", "NKO Pos")          # mesma tag pos-nko
    assert not _it_subfolder_matches("ICM PKO", "SpeedRacer")    # tags diferentes
    assert not _it_subfolder_matches("Random", "SpeedRacer")     # sem tag + nomes != 
