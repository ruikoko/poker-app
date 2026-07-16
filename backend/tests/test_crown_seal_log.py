"""RASTO DOS SELOS DE COROA (`crown_seal_log`, 16 Jul 2026) — ordem do Rui.

O que estes testes protegem (o defeito que o rasto fecha): um selo escrito sem data,
sem valor anterior e sem origem = auditoria impossível (caso Anton Efimov + as 14 mesas
irreconciliáveis do journal 16.2). Aqui prova-se que CADA caminho que sela deixa linha,
com o valor ANTES e DEPOIS, e que o rasto NUNCA parte o carimbo.
"""
from unittest.mock import MagicMock, patch

from app.routers import gg_health, table_ss
from app.services import crown_seal_log
from app.services.crown_seal_log import log_seals, seal_row


# ── seal_row: a linha do rasto ───────────────────────────────────────────────
def test_seal_row_normaliza_valores_e_guarda_o_antes():
    r = seal_row("GG-1", "Anton Efimov", None, "70", new_source="manual")
    assert r["hand_id"] == "GG-1" and r["player"] == "Anton Efimov"
    assert r["old_value"] is None                       # não havia coroa → NULL honesto
    assert r["new_value"] == 70.0
    assert r["new_source"] == "manual" and r["confirmed"] is False


def test_seal_row_valor_ilegivel_fica_nulo_nao_rebenta():
    r = seal_row("GG-1", "x", "lixo", 25.6667)
    assert r["old_value"] is None and r["new_value"] == 25.67   # arredonda a cêntimos


# ── log_seals: defensivo por desenho — o rasto nunca parte o carimbo ─────────
def test_log_seals_sem_linhas_nao_toca_na_bd():
    with patch("app.db.get_conn") as gc:
        assert log_seals([], origin="x") == 0
        gc.assert_not_called()


def test_log_seals_engole_falha_da_bd_e_devolve_zero():
    with patch("app.db.get_conn", side_effect=RuntimeError("bd em baixo")):
        assert log_seals([seal_row("GG-1", "p", 1, 2)], origin="x") == 0   # não levanta


def test_log_seals_grava_uma_linha_por_selo_com_origem_e_actor():
    conn = MagicMock()
    cur = conn.cursor.return_value.__enter__.return_value
    with patch("app.db.get_conn", return_value=conn):
        n = log_seals([seal_row("GG-1", "p", None, 70, new_source="manual")],
                      origin="table_ss.set_bounties", actor="rui@x.pt")
    assert n == 1
    args = cur.executemany.call_args[0][1]
    assert args[0]["origin"] == "table_ss.set_bounties" and args[0]["actor"] == "rui@x.pt"
    assert args[0]["new_value"] == 70.0 and args[0]["old_value"] is None
    conn.commit.assert_called_once()


# ── /set-bounties: o carimbo do card deixa rasto (valor ANTES + DEPOIS) ──────
def _hand_row():
    return [{"id": 9917,
             "all_players_actions": {"_meta": {}, "hash1": {"real_name": "Anton Efimov",
                                                            "bounty_value_usd": 36.0}},
             "player_names": {"players_list": [{"name": "Anton Efimov",
                                                "bounty_value_usd": 36.0}]}}]


def test_set_bounties_regista_o_carimbo_com_antes_e_depois():
    with patch.object(table_ss, "query", return_value=_hand_row()), \
         patch.object(table_ss, "get_conn", return_value=MagicMock()), \
         patch.object(crown_seal_log, "log_seals") as log:
        table_ss.set_bounties_override(
            payload={"hand_id": "GG-6114944742", "bounties": {"Anton Efimov": 70.0}},
            current_user={"email": "rui@x.pt"})
    rows, kw = log.call_args[0][0], log.call_args[1]
    assert len(rows) == 1
    assert rows[0]["hand_id"] == "GG-6114944742" and rows[0]["player"] == "Anton Efimov"
    assert rows[0]["old_value"] == 36.0 and rows[0]["new_value"] == 70.0
    assert rows[0]["new_source"] == "manual"
    assert kw["origin"] == "table_ss.set_bounties" and kw["actor"] == "rui@x.pt"


def test_set_bounties_dry_run_nao_regista_nada():
    with patch.object(table_ss, "query", return_value=_hand_row()), \
         patch.object(table_ss, "get_conn", return_value=MagicMock()), \
         patch.object(crown_seal_log, "log_seals") as log:
        table_ss.set_bounties_override(
            payload={"hand_id": "GG-1", "bounties": {"Anton Efimov": 70.0}, "dry_run": True},
            current_user={"email": "rui@x.pt"})
    log.assert_not_called()                     # ensaio não escreve → não há selo a registar


def test_set_bounties_desfazer_selo_gera_linha_nova_nao_apaga():
    rows_db = [{"id": 1, "all_players_actions": {},
                "player_names": {"players_list": [{"name": "p", "bounty_value_usd": 50.0,
                                                   "bounty_confirmed": True}]}}]
    with patch.object(table_ss, "query", return_value=rows_db), \
         patch.object(table_ss, "get_conn", return_value=MagicMock()), \
         patch.object(crown_seal_log, "log_seals") as log:
        table_ss.set_bounties_override(payload={"hand_id": "GG-1", "unconfirm": ["p"]},
                                       current_user={"email": "rui@x.pt"})
    rows = log.call_args[0][0]
    assert len(rows) == 1 and rows[0]["confirmed"] is False    # o selo caiu → linha NOVA
    assert rows[0]["old_value"] == 50.0                        # a antiga fica na tabela


# ── o olho dos conflitos ("Mantém $X" / campo livre) deixa rasto ─────────────
def test_olho_regista_selo_manual_com_origem_propria():
    rows_db = [{"id": 5, "hand_id": "GG-6116735632",
                "pn": {"players_list": [{"name": "wakefulcheong", "bounty_value_usd": 121.87}]},
                "apa": {}}]
    with patch.object(gg_health, "query", return_value=rows_db), \
         patch.object(gg_health, "get_conn", return_value=MagicMock()), \
         patch.object(crown_seal_log, "log_seals") as log:
        gg_health.crossing_conflicts_apply_selected(
            payload={"items": [{"hand_id": "GG-6116735632", "seat": "wakefulcheong",
                                "value": 50.0}]},
            current_user={"email": "rui@x.pt"})
    rows, kw = log.call_args[0][0], log.call_args[1]
    assert rows[0]["old_value"] == 121.87 and rows[0]["new_value"] == 50.0
    assert kw["origin"] == "gg_health.crossing_conflicts_eye"


def test_olho_nao_regista_seat_ja_selado():
    rows_db = [{"id": 5, "hand_id": "GG-1",
                "pn": {"players_list": [{"name": "p", "bounty_value_usd": 70.0,
                                         "bounty_source": "manual"}]}, "apa": {}}]
    with patch.object(gg_health, "query", return_value=rows_db), \
         patch.object(gg_health, "get_conn", return_value=MagicMock()), \
         patch.object(crown_seal_log, "log_seals") as log:
        gg_health.crossing_conflicts_apply_selected(
            payload={"items": [{"hand_id": "GG-1", "seat": "p", "value": 99.0}]},
            current_user={"email": "rui@x.pt"})
    assert log.call_args[0][0] == []            # selado não se pisa → nada a registar
