"""pt80 (#EQUITY-MODEL-FT-VS-MTT-VALIDATION) — testes para
`validate_equity_model_vs_table_ss` em services/queue_export.py.

A TAG decide o equity model; a SS de mesa do IT VALIDA (não decide). "Parece FT"
= players_left <= jogadores na mesa (len(seats)). Alarme só assinala; o modelo
segue a tag. Sem dados → sem alarme. Estrutura de pagamentos NÃO entra.
"""
from __future__ import annotations

from unittest.mock import patch

from app.services.queue_export import validate_equity_model_vs_table_ss

FT = "malmuth_harville_icm"
MTT = "multi_table_icm"


def _rows(players_left, n_seats, *, vision_str=False):
    seats = [{"nick": f"p{i}"} for i in range(n_seats)] if n_seats is not None else None
    vj = {"seats": seats, "players_left": players_left}
    if vision_str:
        import json
        vj = json.dumps(vj)
    return [{"players_left": players_left, "vision_json": vj}]


def _validate(hand, equity_model, rows):
    with patch("app.db.query", return_value=rows) as q:
        out = validate_equity_model_vs_table_ss(hand, equity_model)
    return out, q


# ── regra 5 / sem dados → None, sem query sequer quando não há ctx ──────────

def test_no_context_table_ss_returns_none_no_query():
    out, q = _validate({"context_table_ss_id": None}, FT, _rows(8, 8))
    assert out is None
    q.assert_not_called()  # sem SS de mesa → nem chega à query


def test_hand_not_dict_returns_none():
    assert validate_equity_model_vs_table_ss(None, FT) is None


def test_missing_players_left_no_alarm():
    out, _ = _validate({"context_table_ss_id": 5}, FT, _rows(None, 6))
    assert out is None  # sem players_left → não valida


def test_missing_seats_no_alarm():
    out, _ = _validate({"context_table_ss_id": 5}, MTT, _rows(120, None))
    assert out is None


def test_empty_seats_no_alarm():
    out, _ = _validate({"context_table_ss_id": 5}, FT, _rows(8, 0))
    assert out is None  # seats_at_table == 0 → não valida


def test_no_rows_returns_none():
    out, _ = _validate({"context_table_ss_id": 5}, FT, [])
    assert out is None


# ── bate certo → None ──────────────────────────────────────────────────────

def test_ft_tag_and_looks_ft_match():
    """FT + players_left <= seats (8<=8) → bate, sem alarme."""
    out, _ = _validate({"context_table_ss_id": 5}, FT, _rows(8, 8))
    assert out is None


def test_mtt_tag_and_not_looks_ft_match():
    """MTT + várias mesas (players_left=120 > seats=6) → bate, sem alarme."""
    out, _ = _validate({"context_table_ss_id": 5}, MTT, _rows(120, 6))
    assert out is None


# ── alarmes ────────────────────────────────────────────────────────────────

def test_ft_tag_but_multi_table_alarms():
    """FT mas players_left=120 > seats=6 (várias mesas) → ALARME."""
    out, _ = _validate({"context_table_ss_id": 5}, FT, _rows(120, 6))
    assert out is not None
    assert out["kind"] == "ft_tag_but_multi_table"
    assert out["equity_model"] == FT
    assert out["players_left"] == 120 and out["seats_at_table"] == 6
    assert out["looks_ft"] is False


def test_mtt_tag_but_single_table_alarms():
    """MTT mas players_left=6 <= seats=8 (todos numa mesa) → ALARME."""
    out, _ = _validate({"context_table_ss_id": 5}, MTT, _rows(6, 8))
    assert out is not None
    assert out["kind"] == "mtt_tag_but_single_table"
    assert out["looks_ft"] is True


def test_boundary_players_left_equals_seats_is_ft():
    """players_left == seats → parece FT (<=). MTT nesse caso → alarme."""
    out, _ = _validate({"context_table_ss_id": 5}, MTT, _rows(7, 7))
    assert out is not None and out["kind"] == "mtt_tag_but_single_table"


def test_vision_json_as_string_is_parsed():
    """vision_json guardado como string JSON é parseado na mesma."""
    out, _ = _validate({"context_table_ss_id": 5}, FT, _rows(120, 6, vision_str=True))
    assert out is not None and out["kind"] == "ft_tag_but_multi_table"


def test_alarm_never_changes_model():
    """O alarme é só sinalização: o dict reflecte o equity_model recebido,
    não um 'corrigido'."""
    out, _ = _validate({"context_table_ss_id": 5}, FT, _rows(120, 6))
    assert out["equity_model"] == FT   # não vira MTT
