"""Guarda 4 da âncora (#DESANON-ANCHOR-REQUIRES-HERO-IN-IMAGE, 12 Jul).

A desanon do table-SS ancora nos NOMES da imagem; se o Rui NÃO está entre os seats
da Vision (print pós-bust), a imagem não pode nomear ninguém → casa a imagem mas NÃO
escreve nomes (status 'deanon_skipped_no_hero_in_image'). Cobre o pós-bust, onde
nenhum seat é o Rui (mais forte que a guarda do PONTO de âncora).
"""
from unittest.mock import patch
from app.services import table_ss_deanon as D

_HAND = {
    "id": 1, "hand_id": "GG-1", "site": "GGPoker",
    "raw": "PokerStars Hand #GG-1: Tournament\nSeat 1: Hero (100 in chips)\n",
    "all_players_actions": {"_meta": {}},   # só _meta → 'no_map' se passar a guarda
    "player_names": {},                      # sem match real → não salta na guarda 3
}


def test_guard4_skips_when_no_rui_in_seats():
    # Vision marcou um vilão como is_hero e o Rui não está em lugar nenhum (pós-bust).
    seats = [{"nick": "bl0ndie", "is_hero": True}, {"nick": "Ward E"},
             {"nick": "Artur Berg"}]
    with patch("app.db.query", return_value=[_HAND]):
        res = D.deanonymize_hand_from_table_ss(1, seats, None)
    assert res["status"] == "deanon_skipped_no_hero_in_image"


def test_guard4_passes_when_rui_present():
    # O Rui (Lauro Dermio) está num seat → a guarda deixa passar (segue o fluxo normal;
    # com apa só-_meta cai em 'no_map', o que prova que NÃO foi bloqueada pela guarda 4).
    seats = [{"nick": "bl0ndie"}, {"nick": "Lauro Dermio", "is_hero": True}]
    with patch("app.db.query", return_value=[_HAND]):
        res = D.deanonymize_hand_from_table_ss(1, seats, None)
    assert res["status"] != "deanon_skipped_no_hero_in_image"
    assert res["status"] == "no_map"


def test_guard4_tolerates_truncated_rui_nick():
    # A Vision corta nicks com '..'; 'Lauro Der..' tem de casar 'Lauro Dermio'.
    seats = [{"nick": "Sava_Kov"}, {"nick": "Lauro Der..", "is_hero": True}]
    with patch("app.db.query", return_value=[_HAND]):
        res = D.deanonymize_hand_from_table_ss(1, seats, None)
    assert res["status"] != "deanon_skipped_no_hero_in_image"
