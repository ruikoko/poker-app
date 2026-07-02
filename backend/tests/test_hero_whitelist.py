"""#DESANON-HERO-FRIEND-NICK-ACCEPTED: os FRIEND_HEROES (Karluz/flightrisk) são
vilões — não podem estar na whitelist de verificação do Hero, senão a Vision a
ler 'HERO: Karluz' é aceite e mete o nick de um vilão no seat do Hero."""
from app.hero_names import HERO_NAMES, FRIEND_HEROES
from app.routers.screenshot import _KNOWN_HERO_NICKS


def test_friend_heroes_excluded_from_hero_whitelist():
    for fh in FRIEND_HEROES:
        assert fh.strip().lower() not in _KNOWN_HERO_NICKS, \
            f"{fh} (friend-hero/vilão) não devia validar como Hero"


def test_real_hero_nicks_still_in_whitelist():
    assert any(n.strip().lower() in _KNOWN_HERO_NICKS for n in HERO_NAMES), \
        "os nicks reais do Hero têm de continuar a validar"


def test_karluz_specifically_not_hero():
    assert "karluz" not in _KNOWN_HERO_NICKS
