"""Tests para `_hm3_tag_names_for_migration()` em app.routers.hands.

Substitui dependência directa do snapshot estático `HM3_REAL_TAG_NAMES`
(frozen pre-2026, com nomes como 'PKO pos', 'ICM PKO') por união com
DISTINCT actual de `hands.hm3_tags` em DB (cobre renames feitos pelo
Rui no HM3: 'PKO pos' → 'pos-pko', 'ICM PKO' → 'icm-pko').

Garantia: re-runs de /admin/migrate-hm3-tags continuam a funcionar
com dados legacy (snapshot) E com tags modernas (DB DISTINCT).
"""
from __future__ import annotations

from unittest.mock import patch

from app.routers.hands import (
    HM3_REAL_TAG_NAMES,
    _hm3_tag_names_for_migration,
)


def test_returns_union_of_snapshot_and_db_distinct():
    """DB devolve um mix de tags modernas + algumas legacy → união
    cobre ambas as eras."""
    fake_rows = [
        {"t": "pos-pko"},      # moderna, não está no snapshot
        {"t": "icm-pko"},      # moderna
        {"t": "ICM"},          # legacy (também no snapshot)
        {"t": "mw-pko"},       # moderna
    ]
    with patch("app.routers.hands.query", return_value=fake_rows):
        names = _hm3_tag_names_for_migration()
    # Snapshot legacy preservado
    assert "ICM" in names
    assert "For Review" in names      # snapshot only
    assert "PKO pos" in names         # snapshot only — legacy
    # Modernas adicionadas
    assert "pos-pko" in names
    assert "icm-pko" in names
    assert "mw-pko" in names


def test_falls_back_to_snapshot_when_db_query_fails():
    """Se a query DB rebenta (rede, schema corrupto), devolve só o snapshot
    — não rebenta o endpoint inteiro."""
    with patch("app.routers.hands.query", side_effect=RuntimeError("simulated db error")):
        names = _hm3_tag_names_for_migration()
    assert names == HM3_REAL_TAG_NAMES
    assert "ICM" in names
    assert "For Review" in names


def test_handles_empty_db_gracefully():
    """DB existe mas hm3_tags é tudo NULL → devolve apenas snapshot."""
    with patch("app.routers.hands.query", return_value=[]):
        names = _hm3_tag_names_for_migration()
    assert names == HM3_REAL_TAG_NAMES


def test_filters_out_none_and_empty_from_db():
    """unnest pode devolver linhas com t=None se o array tiver elementos NULL.
    Função deve fazer skip silencioso (snapshot já assegura nomes válidos)."""
    fake_rows = [
        {"t": "pos-pko"},
        {"t": None},
        {"t": ""},
        {"t": "icm-pko"},
    ]
    with patch("app.routers.hands.query", return_value=fake_rows):
        names = _hm3_tag_names_for_migration()
    assert "pos-pko" in names
    assert "icm-pko" in names
    assert None not in names
    # String vazia: o `if r.get("t")` filtra (falsy).
    assert "" not in names


def test_snapshot_remains_immutable_after_call():
    """_hm3_tag_names_for_migration() não pode mutar HM3_REAL_TAG_NAMES."""
    snapshot_before = set(HM3_REAL_TAG_NAMES)
    fake_rows = [{"t": "new-modern-tag"}]
    with patch("app.routers.hands.query", return_value=fake_rows):
        _ = _hm3_tag_names_for_migration()
    snapshot_after = set(HM3_REAL_TAG_NAMES)
    assert snapshot_before == snapshot_after
    assert "new-modern-tag" not in HM3_REAL_TAG_NAMES
