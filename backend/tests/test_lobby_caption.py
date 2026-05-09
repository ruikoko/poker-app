"""Unit tests para _extract_tn_from_caption (FASE A COMMIT C + refactor).

Cobre a regex de extracção de tournament_number do texto da mensagem
Discord no canal #lobbys. Helper privado vive em backend/app/discord_bot.py.
"""

from app.discord_bot import _extract_tn_from_caption


def test_extract_tn_basic_with_TM_prefix():
    assert _extract_tn_from_caption("TM 281017175") == "281017175"


def test_extract_tn_no_space_after_TM_prefix():
    assert _extract_tn_from_caption("TM281017175") == "281017175"


def test_extract_tn_lowercase_tm_prefix():
    assert _extract_tn_from_caption("tm 281017175") == "281017175"


def test_extract_tn_hashtag_prefix():
    assert _extract_tn_from_caption("#281017175") == "281017175"


def test_extract_tn_hashtag_with_space():
    assert _extract_tn_from_caption("# 281017175") == "281017175"


def test_extract_tn_in_middle_of_sentence():
    assert _extract_tn_from_caption("is it TM 281017175?") == "281017175"


def test_extract_tn_too_short_returns_none():
    assert _extract_tn_from_caption("TM 12345") is None


def test_extract_tn_too_long_returns_none():
    assert _extract_tn_from_caption("TM 1234567890123") is None


# INVERTIDO: era no_prefix_returns_none; agora number_alone_matches.
# Refactor relaxou a regex: prefixo opcional, numero sozinho aceito.
def test_extract_tn_number_alone_matches():
    assert _extract_tn_from_caption("281017175") == "281017175"


def test_extract_tn_empty_string_returns_none():
    assert _extract_tn_from_caption("") is None


def test_extract_tn_none_input_returns_none():
    assert _extract_tn_from_caption(None) is None


# NOVOS — TN como prefixo aceito (refactor terminológico).

def test_extract_tn_TN_prefix_uppercase():
    assert _extract_tn_from_caption("TN 281017175") == "281017175"


def test_extract_tn_TN_prefix_lowercase():
    assert _extract_tn_from_caption("tn 281017175") == "281017175"


def test_extract_tn_in_middle_of_sentence_no_prefix():
    assert _extract_tn_from_caption("see 281017175 here") == "281017175"


# DEFENSIVO — protege contra regressao da regex (lookarounds vs \b).
# 13 digitos puros, sem prefixo: nao deve matchar 12 sub-string.
def test_extract_tn_long_number_alone_returns_none():
    assert _extract_tn_from_caption("1234567890123") is None
