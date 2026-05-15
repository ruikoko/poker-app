"""Tests para create_entry — caminho 'hm3_synthetic' idempotente
(#ORFA-HM3-SYNTHETIC-ENTRIES Peca 1)."""
from __future__ import annotations

from unittest.mock import patch

from app.services.entry_service import create_entry


def test_create_entry_synthetic_happy_path_insert():
    """1ª chamada: INSERT bem-sucedido, devolve a row inserida."""
    inserted = {
        "id": 42,
        "source": "hm3_synthetic",
        "entry_type": "hand_history",
        "external_id": "GG-1234",
        "site": "GGPoker",
        "file_name": None,
        "status": "new",
        "created_at": None,
    }
    with patch(
        "app.services.entry_service.execute_returning",
        return_value=inserted,
    ) as exec_mock, patch(
        "app.services.entry_service.query"
    ) as query_mock:
        result = create_entry(
            source="hm3_synthetic",
            entry_type="hand_history",
            external_id="GG-1234",
            site="GGPoker",
        )
    assert result == inserted
    # Verifica que o SQL usou o caminho dedicado synthetic — ON CONFLICT em external_id.
    sql_used = exec_mock.call_args[0][0]
    assert "ON CONFLICT (external_id) WHERE source = 'hm3_synthetic'" in sql_used
    # Nao precisou de fallback SELECT.
    query_mock.assert_not_called()


def test_create_entry_synthetic_conflict_returns_existing():
    """2ª chamada (re-run do .bat): ON CONFLICT DO NOTHING devolve None,
    fallback SELECT devolve a row existente."""
    existing = {
        "id": 42,
        "source": "hm3_synthetic",
        "entry_type": "hand_history",
        "external_id": "GG-1234",
        "site": "GGPoker",
        "file_name": None,
        "status": "new",
        "created_at": None,
    }
    with patch(
        "app.services.entry_service.execute_returning",
        return_value=None,  # ON CONFLICT DO NOTHING
    ), patch(
        "app.services.entry_service.query",
        return_value=[existing],
    ) as query_mock:
        result = create_entry(
            source="hm3_synthetic",
            entry_type="hand_history",
            external_id="GG-1234",
            site="GGPoker",
        )
    assert result == existing
    # Fallback SELECT foi chamado com external_id certo.
    args, _ = query_mock.call_args
    assert args[1] == ("GG-1234",)


def test_create_entry_synthetic_sem_external_id_cai_caminho_normal():
    """source='hm3_synthetic' mas external_id None → cai no caminho normal
    (sem ON CONFLICT em external_id)."""
    inserted = {
        "id": 99,
        "source": "hm3_synthetic",
        "entry_type": "hand_history",
        "external_id": None,
        "site": "GGPoker",
        "file_name": None,
        "status": "new",
        "created_at": None,
    }
    with patch(
        "app.services.entry_service.execute_returning",
        return_value=inserted,
    ) as exec_mock, patch(
        "app.services.entry_service.query"
    ) as query_mock:
        result = create_entry(
            source="hm3_synthetic",
            entry_type="hand_history",
            external_id=None,
            site="GGPoker",
        )
    assert result == inserted
    sql_used = exec_mock.call_args[0][0]
    # Caminho normal usa ON CONFLICT em discord_message_id, nao external_id.
    assert "ON CONFLICT (discord_message_id)" in sql_used
    assert "ON CONFLICT (external_id)" not in sql_used
    query_mock.assert_not_called()


def test_create_entry_discord_inalterado_pelo_caminho_synthetic():
    """source='discord' continua a usar o caminho original ON CONFLICT
    (discord_message_id) — sem regressao."""
    inserted = {
        "id": 7,
        "source": "discord",
        "entry_type": "replayer_link",
        "external_id": None,
        "site": "GGPoker",
        "file_name": None,
        "status": "new",
        "created_at": None,
    }
    with patch(
        "app.services.entry_service.execute_returning",
        return_value=inserted,
    ) as exec_mock, patch(
        "app.services.entry_service.query"
    ) as query_mock:
        result = create_entry(
            source="discord",
            entry_type="replayer_link",
            site="GGPoker",
            discord_message_id="msg123",
        )
    assert result == inserted
    sql_used = exec_mock.call_args[0][0]
    assert "ON CONFLICT (discord_message_id)" in sql_used
    assert "hm3_synthetic" not in sql_used
    query_mock.assert_not_called()
