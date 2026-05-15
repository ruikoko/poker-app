"""Tests para o helper upsert_synthetic_entry do backfill script
(scripts/backfill_hm3_synthetic_entries.py — #ORFA-HM3-SYNTHETIC-ENTRIES Peca 5).

Garantem que o backfill e' idempotente (re-run nao duplica entries) via
o partial unique index criado na Peca 1.
"""
from __future__ import annotations

import os
import sys
from unittest.mock import MagicMock

# Adicionar scripts/ ao sys.path para importar o backfill.
HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.normpath(os.path.join(HERE, "..", "..", "scripts"))
sys.path.insert(0, SCRIPTS)

from backfill_hm3_synthetic_entries import upsert_synthetic_entry, link_hand_to_entry


class _MockCursor:
    def __init__(self, insert_returns: dict | None = None, select_returns: dict | None = None):
        self.insert_returns = insert_returns
        self.select_returns = select_returns
        self.executed: list[tuple] = []
        self._next_one = None

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def execute(self, sql, params=None):
        self.executed.append((sql.strip(), params))
        s = sql.lower()
        if "insert into entries" in s and "on conflict" in s:
            self._next_one = self.insert_returns
        elif "select id from entries" in s:
            self._next_one = self.select_returns
        elif "update hands" in s:
            self._next_one = None

    def fetchone(self):
        return self._next_one


class _MockConn:
    def __init__(self, cur):
        self.cur = cur

    def cursor(self):
        return self.cur


def test_upsert_synthetic_entry_insert_path():
    """1ª chamada: INSERT bem-sucedido devolve nova id."""
    cur = _MockCursor(insert_returns={"id": 100})
    conn = _MockConn(cur)
    result = upsert_synthetic_entry(conn, hand_id="WN-1234", site="Winamax")
    assert result == 100
    # Verifica que houve INSERT.
    assert any("insert into entries" in sql.lower() for sql, _ in cur.executed)


def test_upsert_synthetic_entry_conflict_path_returns_existing():
    """Re-run: ON CONFLICT DO NOTHING devolve None, fallback SELECT
    devolve a id existente."""
    cur = _MockCursor(insert_returns=None, select_returns={"id": 99})
    conn = _MockConn(cur)
    result = upsert_synthetic_entry(conn, hand_id="WN-1234", site="Winamax")
    assert result == 99
    # Deve haver INSERT + SELECT fallback.
    sqls = [sql.lower() for sql, _ in cur.executed]
    assert any("insert into entries" in s for s in sqls)
    assert any("select id from entries" in s for s in sqls)


def test_upsert_synthetic_entry_uses_partial_unique_constraint():
    """SQL usa ON CONFLICT (external_id) WHERE source='hm3_synthetic'
    para bater no partial unique index."""
    cur = _MockCursor(insert_returns={"id": 1})
    conn = _MockConn(cur)
    upsert_synthetic_entry(conn, hand_id="x", site="GGPoker")
    insert_sql = next(sql for sql, _ in cur.executed if "insert into entries" in sql.lower())
    # Critical: clause sintetica para idempotencia.
    assert "ON CONFLICT (external_id)" in insert_sql or "on conflict (external_id)" in insert_sql.lower()
    assert "hm3_synthetic" in insert_sql


def test_link_hand_to_entry_skip_se_ja_tem_entry_id():
    """UPDATE inclui guard `AND entry_id IS NULL` — nao sobrescreve
    entry_id ja populado por outra fonte (e.g., Discord enrichment)."""
    cur = _MockCursor()
    conn = _MockConn(cur)
    link_hand_to_entry(conn, hand_db_id=42, entry_id=99)
    sql, params = cur.executed[0]
    assert "entry_id IS NULL" in sql or "entry_id is null" in sql.lower()
    assert params == (99, 42)
