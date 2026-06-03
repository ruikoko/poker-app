"""pt54 — normalização do nome de torneio Winamax (#WN-TOURNAMENT-NAME-NORMALIZE).

Nome canónico = só o NOME. Remove '#NNN' (nº de mesa) e '(NNNNNNN)' (ID do
torneio), preserva garantias sem '#' (150K/80K). O ID extraído sai no 2º
elemento para preservar em tournament_number.
"""
from app.services.tournament_resolver import clean_winamax_tournament_name as cw


def test_strip_table_num_and_id_parens():
    assert cw("EXPLORER 150K #076 (1104093788)") == ("EXPLORER 150K", "1104093788")


def test_strip_table_num_only():
    assert cw("GALACTICA #034") == ("GALACTICA", None)


def test_strip_id_parens_no_table_num():
    assert cw("HIGHROLLER (1104094519)") == ("HIGHROLLER", "1104094519")


def test_preserve_guarantee_80k():
    assert cw("GRAVITY 80K #0006") == ("GRAVITY 80K", None)


def test_preserve_guarantee_in_full_name():
    # 150K/120K fazem parte do nome (sem '#') → preservados.
    assert cw("MAIN EVENT SPACE KO 120K") == ("MAIN EVENT SPACE KO 120K", None)


def test_four_digit_table_num():
    assert cw("PRIME TIME #0006") == ("PRIME TIME", None)


def test_already_clean_is_noop():
    assert cw("ODYSSEY") == ("ODYSSEY", None)


def test_id_only_in_parens_pure_digits():
    # '(150K)' NÃO é ID (tem 'K') → preservado; só '(\d+)' puro é ID.
    assert cw("FOO (150K) #03") == ("FOO (150K)", None)


def test_extracts_id_before_stripping():
    # garante que o ID NÃO se perde — sai no 2º elemento.
    clean, tid = cw("ZENITH #017 (1103535939)")
    assert clean == "ZENITH"
    assert tid == "1103535939"


def test_none_and_empty():
    assert cw(None) == (None, None)
    assert cw("") == ("", None)


def test_real_table_ss_examples():
    assert cw("EXPLORER 150K #235")[0] == "EXPLORER 150K"
    assert cw("HIGHROLLER #000")[0] == "HIGHROLLER"
    assert cw("INTERSTELLAR #003")[0] == "INTERSTELLAR"
