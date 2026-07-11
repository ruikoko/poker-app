"""#CROWN-VISIBLE-READ-ZERO — o filtro separa 'coroa por ler ($0)' de 'valor impossível'."""
from unittest.mock import patch
from app.routers import suspicious


def _rows(pn, base=100.0):
    return [{"id": 1, "hand_id": "GG-1", "tournament_name": "T",
             "played_at": "2026-07-02", "pn": pn, "base": base}]


def test_kind_unread_when_all_zero():
    pn = {"players_list": [{"name": "A", "bounty_value_usd": 0.0, "has_cards": True}]}
    with patch.object(suspicious, "query", return_value=_rows(pn)):
        out = suspicious._bounty_below_half_hands()
    assert out and out[0]["kind"] == "unread"


def test_kind_impossible_when_positive_below_half():
    pn = {"players_list": [{"name": "A", "bounty_value_usd": 30.0, "has_cards": True}]}
    with patch.object(suspicious, "query", return_value=_rows(pn)):
        out = suspicious._bounty_below_half_hands()
    assert out and out[0]["kind"] == "impossible"


# ── Veneno 3: Hero alheio (pn.hero ∉ HERO_NAMES_ALL) — #DESANON-HERO-ANCHOR-VALIDATION ──

def _arow(pn, apa):
    return [{"id": 1, "hand_id": "GG-1", "tournament_name": "T",
             "played_at": "2026-06-30", "pn": pn, "apa": apa}]


def test_hero_alheio_cosmetic_when_apa_hero_is_rui():
    # pn.hero é um vilão, mas o apa['Hero'] já tem o Rui → só o rótulo desincronizou.
    pn = {"hero": "bl0ndie", "anon_map": {"Hero": "Lauro Dermio"}}
    apa = {"Hero": {"real_name": "Lauro Dermio", "is_hero": True}}
    with patch.object(suspicious, "query", return_value=_arow(pn, apa)):
        out = suspicious._hero_alheio_hands()
    assert len(out) == 1
    assert out[0]["detail"]["kind"] == "cosmetic"
    assert out[0]["detail"]["apa_hero"] == "Lauro Dermio"


def test_hero_alheio_poison_when_apa_hero_also_villain():
    # print pós-bust: nem o pn.hero nem o apa['Hero'] são o Rui → veneno real.
    pn = {"hero": "aaooiu", "anon_map": {"Hero": "aaooiu"}}
    apa = {"Hero": {"real_name": "aaooiu", "is_hero": True}}
    with patch.object(suspicious, "query", return_value=_arow(pn, apa)):
        out = suspicious._hero_alheio_hands()
    assert len(out) == 1
    assert out[0]["detail"]["kind"] == "poison"


def test_hero_alheio_skips_legit_hero_and_friend():
    # pn.hero = conta do Rui OU friend-hero → NÃO é suspeita (0 resultados).
    for hero in ("Lauro Dermio", "Karluz", "lauro derm"):
        pn = {"hero": hero}
        apa = {"Hero": {"real_name": hero, "is_hero": True}}
        with patch.object(suspicious, "query", return_value=_arow(pn, apa)):
            assert suspicious._hero_alheio_hands() == []
