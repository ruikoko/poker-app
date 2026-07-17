"""PEÇA 2 — ponte de truncatura no casamento de nomes entre as 2 gavetas
(players_list ↔ all_players_actions). Nome cortado ('..'/'…') casa por PREFIXO
contra a outra gaveta, SÓ se houver UM único candidato; com ambiguidade não adivinha."""
from app.routers import table_ss


def test_match_store_exact():
    store = {"Alice": {"n": 1}}
    assert table_ss._match_store("Alice", store) is store["Alice"]


def test_match_store_normalized_unique_ocr():
    # variância de OCR (corridas de letras iguais) → normalizado único
    store = {"BroooooK": {"n": 1}}
    assert table_ss._match_store("BrooooK", store) is store["BroooooK"]


def test_match_store_truncation_bridge_both_directions():
    apa = {"Manooundergr..": {"who": "apa"}}   # gaveta apa: nome cortado
    pl = {"Manounderground": {"who": "pl"}}     # gaveta players_list: nome inteiro
    # o nome CORTADO casa por prefixo contra a gaveta com o nome inteiro
    assert table_ss._match_store("Manooundergr..", pl) is pl["Manounderground"]
    # e o nome INTEIRO casa contra a gaveta com o nome cortado (direcção inversa)
    assert table_ss._match_store("Manounderground", apa) is apa["Manooundergr.."]


def test_match_store_truncation_ambiguous_no_guess():
    store = {"Manounderground": {"n": 1}, "Manounderground2": {"n": 2}}
    # "Manoundergr.." tem DOIS candidatos com o mesmo prefixo → NÃO adivinha
    assert table_ss._match_store("Manoundergr..", store) is None


def test_match_store_no_false_prefix_without_trunc():
    store = {"Alexander": {"n": 1}}
    # "Alex" NÃO termina em '..'/'…' → não faz ponte de prefixo (senão casava tudo)
    assert table_ss._match_store("Alex", store) is None


def test_match_store_absent_returns_none():
    assert table_ss._match_store("Ghost", {"Alice": {}}) is None
