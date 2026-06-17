"""Sinais do NOME do ficheiro fora do match GG e do played_at.

Doutrina (CLAUDE.md + DESANON_ANATOMIA §2 + `#GG-DOWNLOAD-IMG-FILENAME-TIME-
AND-BLINDS-UNRELIABLE`): no screenshot GG, a data/hora do nome é o instante do
DOWNLOAD (não a hora-de-jogo) e as blinds do nome não são de confiança. A chave
do match é o hand-id (TM). Estes testes blindam dois pontos:

  1. `_enrich_hand_from_orphan_entry` NÃO escreve `played_at` derivado do
     `file_meta` (date+time do nome) — fica como está na BD (NULL sem HH).
  2. `_match_screenshot` casa SÓ pelo TM; hora e blinds do nome não entram no
     desempate (e nem sequer são parâmetros da função).
"""
from __future__ import annotations

import inspect
from unittest.mock import MagicMock, patch

from app.routers.mtt import _match_screenshot
from app.routers import screenshot as ss


# ── Ponto 1 — played_at não vem do nome do ficheiro ─────────────────────


def _run_enrich_capturing_update(file_meta):
    """Corre _enrich_hand_from_orphan_entry com mocks mínimos e devolve
    (update_sql, update_params) do UPDATE hands principal."""
    matched_hand = {
        "id": 10,
        "hand_id": "GG-1234567890",
        # all_players_actions com chave real (não-_meta) para passar o assert
        # defensivo #B-NOVO-2.
        "all_players_actions": {"89ef4cba": {"actions": []}},
        "position": None,
        "raw": "Poker Hand #TM1234567890: ...",   # HH real presente
        "stakes": None,
        "hero_cards": ["As", "Kh"],
        "board": [],
        "player_names": {},   # sem match_method → não cai no guard idempotência
        # NOTA: o SELECT da função nem sequer traz `played_at` → .get devolve None
    }
    raw_json = {
        "hero": "Hero",
        "tournament": "Bounty Hunters Big Game $215",
        "players_list": [],
        "vision_sb": None,
        "vision_bb": None,
        "file_meta": file_meta,
        "screenshot_url": None,
    }

    captured = []

    class _Cur:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def execute(self, sql, params=None):
            captured.append((sql, params))

    conn = MagicMock()
    conn.cursor.return_value = _Cur()

    with patch("app.routers.screenshot.query", return_value=[matched_hand]), \
         patch("app.routers.screenshot.get_conn", return_value=conn), \
         patch("app.routers.screenshot._build_anon_to_real_map",
               return_value={"Hero": "Hero"}), \
         patch("app.routers.screenshot._enrich_all_players_actions",
               return_value={}), \
         patch("app.discord_bot._resolve_channel_name_for_entry",
               return_value=None), \
         patch("app.services.villain_rules.apply_villain_rules",
               return_value={"n_villains_created": 0, "n_villain_notes_upserts": 0}):
        ss._enrich_hand_from_orphan_entry(entry_id=99, hand_db_id=10, raw_json=raw_json)

    # O UPDATE principal é o que mexe em player_names.
    upd = [(s, p) for (s, p) in captured if "UPDATE hands SET player_names" in s]
    assert upd, f"UPDATE hands principal não encontrado. SQLs: {[s for s,_ in captured]}"
    return upd[0]


def test_played_at_nao_e_derivado_do_nome_mesmo_com_date_e_time():
    sql, params = _run_enrich_capturing_update(
        {"date": "2026-03-26", "time": "15:35",
         "tournament": "Bounty Hunters Big Game $215"}
    )
    assert "played_at" not in sql, (
        "played_at NÃO deve ser escrito a partir do file_meta (date/time do nome "
        "= hora do download, não hora-de-jogo)."
    )


def test_enrich_ainda_preenche_outros_campos_do_vision():
    """Sanidade: a remoção do played_at-fallback não tira os outros extras
    (ex.: stakes a partir do nome do torneio do Vision)."""
    sql, params = _run_enrich_capturing_update(
        {"date": "2026-03-26", "time": "15:35"}
    )
    assert "stakes = %s" in sql, "stakes (nome do torneio Vision) deve continuar a ser preenchido"
    assert "played_at" not in sql


# ── Ponto 2 — _match_screenshot casa só pelo TM ─────────────────────────


def test_match_screenshot_assinatura_nao_aceita_hora_nem_blinds():
    sig = inspect.signature(_match_screenshot)
    params = list(sig.parameters)
    assert params == ["tm_number"], (
        f"_match_screenshot deve receber só tm_number; recebeu {params}"
    )


def test_match_screenshot_um_unico_screenshot_casa_pelo_tm():
    rows = [{"id": 7, "raw_json": {"tm": "TM1234567890"}}]
    with patch("app.routers.mtt.query", return_value=rows), \
         patch("app.routers.mtt._extract_screenshot_data",
               side_effect=lambda raw, eid: {"entry_id": eid}):
        out = _match_screenshot("TM1234567890")
    assert out == {"entry_id": 7}


def test_match_screenshot_multiplos_ignora_blinds_e_hora_e_pega_menor_id():
    """Dois screenshots com o MESMO TM mas blinds/hora diferentes no nome:
    a função não desempata por esses campos — pega no determinístico (1º da
    query, ORDER BY id)."""
    rows = [
        # 1º (menor id) — blinds/hora "diferentes" de qualquer HH; devem ser ignorados
        {"id": 3, "raw_json": {
            "tm": "TM1234567890",
            "file_meta": {"blinds": "999/1999", "date": "2026-03-26", "time": "23:59"},
        }},
        {"id": 8, "raw_json": {
            "tm": "TM1234567890",
            "file_meta": {"blinds": "500/1000", "date": "2026-03-26", "time": "15:35"},
        }},
    ]
    captured = {}

    def fake_extract(raw, eid):
        captured["eid"] = eid
        return {"entry_id": eid}

    with patch("app.routers.mtt.query", return_value=rows), \
         patch("app.routers.mtt._extract_screenshot_data", side_effect=fake_extract):
        out = _match_screenshot("TM1234567890")

    assert out == {"entry_id": 3}, "deve pegar no screenshot de menor id, sem desempate por blinds/hora"
    assert captured["eid"] == 3


def test_match_screenshot_sem_rows_devolve_none():
    with patch("app.routers.mtt.query", return_value=[]):
        assert _match_screenshot("TM1234567890") is None


def test_match_screenshot_tm_sem_digitos_devolve_none():
    # _extract_tm_digits sem dígitos → None, sem sequer ir à BD.
    with patch("app.routers.mtt.query") as q:
        assert _match_screenshot("sem-numero") is None
        q.assert_not_called()
