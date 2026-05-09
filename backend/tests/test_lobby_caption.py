"""Unit tests para _extract_tm_from_caption (FASE A COMMIT C).

Cobre a regex de extracção de TM do texto da mensagem Discord no
canal #lobbys. Helper privado vive em backend/app/discord_bot.py.
"""

from app.discord_bot import _extract_tm_from_caption


def test_extract_tm_basic_with_TM_prefix():
    assert _extract_tm_from_caption("TM 281017175") == "281017175"


def test_extract_tm_no_space_after_TM_prefix():
    assert _extract_tm_from_caption("TM281017175") == "281017175"


def test_extract_tm_lowercase_tm_prefix():
    assert _extract_tm_from_caption("tm 281017175") == "281017175"


def test_extract_tm_hashtag_prefix():
    assert _extract_tm_from_caption("#281017175") == "281017175"


def test_extract_tm_hashtag_with_space():
    assert _extract_tm_from_caption("# 281017175") == "281017175"


def test_extract_tm_in_middle_of_sentence():
    assert _extract_tm_from_caption("is it TM 281017175?") == "281017175"


def test_extract_tm_too_short_returns_none():
    assert _extract_tm_from_caption("TM 12345") is None


def test_extract_tm_too_long_returns_none():
    assert _extract_tm_from_caption("TM 1234567890123") is None


def test_extract_tm_no_prefix_returns_none():
    assert _extract_tm_from_caption("281017175") is None


def test_extract_tm_empty_string_returns_none():
    assert _extract_tm_from_caption("") is None


def test_extract_tm_none_input_returns_none():
    assert _extract_tm_from_caption(None) is None
