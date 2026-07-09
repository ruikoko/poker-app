"""Cura verde-KO — deteção de eliminado (HH) + chokepoint do bounty por-seat."""
from app.services.eliminated_bounty import (
    busted_keys_from_hh, busted_real_names, parse_green_kos, resolve_seat_bounty,
    scrub_eliminated_bounties,
    REVIEW_NO_GREEN, REVIEW_AMBIGUOUS, SOURCE_GREEN_KO,
    BOUNTY_REVIEW_KEY, BOUNTY_SOURCE_KEY,
)

# HH real (GG-6140169166): Hero all-in no river e perde; ccc84511 coleta.
_HH = """Poker Hand #TM6140169166: Tournament #295203310, Bounty Hunters Special $150
Seat 5: Hero (87,283 in chips)
Hero: bets 47,944 and is all-in
ccc84511: calls 47,944
*** SHOWDOWN ***
ccc84511 collected 180,816 from pot
*** SUMMARY ***
Seat 5: Hero showed [Qd Js] and lost with Ace high
"""


def test_busted_detects_allin_loser_only():
    assert busted_keys_from_hh(_HH) == {"Hero"}          # Hero all-in+perdeu
    # ccc84511 foi all-in? não — só o Hero. E coletou → nunca bustado.


def test_busted_regex_stays_on_one_line():
    # O bug apanhado (9 Jul): [^:]+ engolia newlines e capturava lixo multi-linha.
    for k in busted_keys_from_hh(_HH):
        assert "\n" not in k and "Dealt to" not in k


def test_busted_real_names_maps_via_apa():
    apa = {"_meta": {}, "Hero": {"real_name": "Lauro Dermio"},
           "ccc84511": {"real_name": "YanayB"}}
    assert busted_real_names(_HH, apa) == {"Lauro Dermio"}


def test_resolve_non_eliminated_passthrough():
    # Seat normal → coroa da Vision INALTERADA (convenção normal preservada), sem source.
    val, rev, src = resolve_seat_bounty("YanayB", 253.75, busted_names={"Lauro Dermio"})
    assert val == 253.75 and rev is None and src is None


def test_resolve_eliminated_one_green_derives_instant():
    # 1 eliminado + 1 verde → grava o verde (instantâneo, source green_ko); ×2 → total.
    greens = [{"winner": "YanayB", "value": 102.27}]
    val, rev, src = resolve_seat_bounty("Lauro Dermio", 170.63,
                                        busted_names={"Lauro Dermio"}, green_kos=greens)
    assert val == 102.27 and rev is None and src == SOURCE_GREEN_KO   # NUNCA 170.63


def test_resolve_eliminated_no_green_is_review():
    val, rev, src = resolve_seat_bounty("Lauro Dermio", 170.63,
                                        busted_names={"Lauro Dermio"}, green_kos=[])
    assert val is None and rev == REVIEW_NO_GREEN and src is None


def test_resolve_eliminated_multiway_ambiguous():
    greens = [{"winner": "A", "value": 50.0}, {"winner": "B", "value": 60.0}]
    val, rev, src = resolve_seat_bounty("X", 99.0,
                                        busted_names={"X", "Y"}, green_kos=greens)
    assert val is None and rev == REVIEW_AMBIGUOUS and src is None


def test_parse_green_kos():
    vd = {"green_kos": [{"winner": "YanayB", "value": "102.27"}, {"winner": "Z", "value": 0}]}
    out = parse_green_kos(vd)
    assert out == [{"winner": "YanayB", "value": 102.27}]   # ignora 0


# ── Funil scrub_eliminated_bounties (4 garantias) ─────────────────────────────
def _apa_pn():
    apa = {"_meta": {"bb": 5000},
           "Hero": {"real_name": "Lauro Dermio", "position": "UTG1", "stack": 87283,
                    "cards": ["Qd", "Js"], "bounty_value_usd": 170.63},
           "ccc84511": {"real_name": "YanayB", "position": "BB", "bounty_value_usd": 253.75}}
    pn = {"players_list": [
        {"name": "Lauro Dermio", "stack": 0, "country": "BR", "bounty_value_usd": 170.63},
        {"name": "YanayB", "stack": 100, "bounty_value_usd": 253.75}]}
    return apa, pn


def test_scrub_no_green_nulls_and_reviews_both():
    apa, pn = _apa_pn()
    n = scrub_eliminated_bounties(apa, pn, _HH, vision_data=None)   # MUST sem verde
    assert n == 1
    assert apa["Hero"]["bounty_value_usd"] is None
    assert apa["Hero"][BOUNTY_REVIEW_KEY] == REVIEW_NO_GREEN
    assert pn["players_list"][0]["bounty_value_usd"] is None        # apa↔pn coerentes
    assert pn["players_list"][0][BOUNTY_REVIEW_KEY] == REVIEW_NO_GREEN
    # normal INTACTO
    assert apa["ccc84511"]["bounty_value_usd"] == 253.75


def test_scrub_with_green_derives_both_with_source():
    apa, pn = _apa_pn()
    vd = {"green_kos": [{"winner": "YanayB", "value": 102.27}]}
    scrub_eliminated_bounties(apa, pn, _HH, vision_data=vd)
    assert apa["Hero"]["bounty_value_usd"] == 102.27                # NUNCA 170.63
    assert apa["Hero"][BOUNTY_SOURCE_KEY] == SOURCE_GREEN_KO
    assert pn["players_list"][0]["bounty_value_usd"] == 102.27
    assert pn["players_list"][0][BOUNTY_SOURCE_KEY] == SOURCE_GREEN_KO


def test_scrub_surgical_preserves_desanon():
    apa, pn = _apa_pn()
    scrub_eliminated_bounties(apa, pn, _HH, vision_data=None)
    h = apa["Hero"]
    assert h["real_name"] == "Lauro Dermio" and h["position"] == "UTG1"
    assert h["stack"] == 87283 and h["cards"] == ["Qd", "Js"]      # nada além do bounty
    assert pn["players_list"][0]["country"] == "BR"


def test_scrub_without_raw_is_safe_noop():
    apa, pn = _apa_pn()
    n = scrub_eliminated_bounties(apa, pn, raw=None)               # Guarantee 2
    assert n == 0 and apa["Hero"]["bounty_value_usd"] == 170.63    # não scruba às cegas


def test_scrub_skips_untagged():
    # SÓ-TAGADAS (garantia 0): mão não-marcada → funil não toca nada.
    apa, pn = _apa_pn()
    n = scrub_eliminated_bounties(apa, pn, _HH, vision_data=None, tagged=False)
    assert n == 0 and apa["Hero"]["bounty_value_usd"] == 170.63
