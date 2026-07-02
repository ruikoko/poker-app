"""Tests do #DESANON-GOLD-SCRAMBLE — re-enrich das mãos Gold baralhadas:
  - _same_player exclui truncagem/OCR do baralhamento
  - _final_chips_by_token deriva fichas do FIM (inicial−ante−apostas+uncalled+collected)
  - _stack_gate_ok compara Gold(fim) vs HH-final
  - reenrich_scrambled_gold só escreve as partidas que passam o gate
"""
from unittest.mock import patch

from app.routers import screenshot
from app.routers.screenshot import (
    _same_player, _seats_from_raw, _final_chips_by_token,
    _scramble_state, _stack_gate_ok,
)

RAW = """Poker Hand #TM1: Tournament #123, TEST Hold'em No Limit - Level5(100/200)
Table 'x' 6-max Seat #1 is the button
Seat 1: aaaa (5,000 in chips)
Seat 2: bbbb (3,000 in chips)
Seat 3: Hero (4,000 in chips)
aaaa: posts the ante 20
bbbb: posts the ante 20
Hero: posts the ante 20
bbbb: posts small blind 100
Hero: posts big blind 200
*** HOLE CARDS ***
Dealt to Hero [Ah Kh]
aaaa: raises 400 to 600
bbbb: folds
Hero: calls 400
*** FLOP *** [2c 7d 9s]
Hero: checks
aaaa: bets 800
Hero: folds
Uncalled bet (800) returned to aaaa
aaaa collected 1360 from pot
*** SUMMARY ***
"""


def test_same_player_truncation_and_ocr_not_scramble():
    assert _same_player("vunzigeviktor", "vunzigevikt..")     # truncagem
    assert _same_player("Renato Pozzetto", "Renato Pozz..")
    assert _same_player("KazuyoshiFunaki", "KazuyoshiFu..")
    assert not _same_player("Kotik2013", "feifeimadrid")      # troca real
    assert not _same_player("Lauro Dermio", "Karluz")


def test_final_chips_end_of_hand():
    seats = _seats_from_raw(RAW)
    fc = _final_chips_by_token(RAW, seats)
    # aaaa: 5000 −20 ante −600 (uncalled 800 devolvido) +1360 collected
    assert fc["aaaa"] == 5000 - 20 - 600 + 1360
    # bbbb (SB, foldou): 3000 −20 −100
    assert fc["bbbb"] == 3000 - 20 - 100
    # Hero (BB+call 600, foldou no flop): 4000 −20 −600
    assert fc["Hero"] == 4000 - 20 - 600


def test_scramble_state_truncation_not_broken():
    seats = _seats_from_raw(RAW)
    anon = {"Hero": "Lauro Dermio", "aaaa": "vunzigevikt..", "bbbb": "ChicoBento"}
    apa = {"_meta": {"bb": 200},
           "vunzigeviktor": {"seat": 1}, "ChicoBento": {"seat": 2},
           "Lauro Dermio": {"seat": 3}}
    broken, incomplete = _scramble_state(RAW, anon, apa, seats)
    assert not broken            # 'vunzigeviktor' ~ 'vunzigevikt..' → não é baralhamento
    assert not incomplete


def test_scramble_state_swap_and_drop_broken():
    seats = _seats_from_raw(RAW)
    anon = {"Hero": "Lauro Dermio", "aaaa": "Kotik2013", "bbbb": "feifeimadrid"}
    # seat1/seat2 trocados
    apa_swap = {"_meta": {}, "feifeimadrid": {"seat": 1}, "Kotik2013": {"seat": 2},
                "Lauro Dermio": {"seat": 3}}
    broken, _ = _scramble_state(RAW, anon, apa_swap, seats)
    assert broken
    # seat2 largado (vilão a hash)
    apa_drop = {"_meta": {}, "Kotik2013": {"seat": 1}, "Lauro Dermio": {"seat": 3}}
    broken2, _ = _scramble_state(RAW, anon, apa_drop, seats)
    assert broken2


def test_scramble_state_incomplete_anon_map():
    seats = _seats_from_raw(RAW)
    anon = {"Hero": "Lauro Dermio", "aaaa": "Kotik2013"}     # falta bbbb
    apa = {"_meta": {}, "Kotik2013": {"seat": 2}}
    _broken, incomplete = _scramble_state(RAW, anon, apa, seats)
    assert incomplete


def test_stack_gate_matches_on_final_chips():
    seats = _seats_from_raw(RAW)
    anon = {"Hero": "Lauro Dermio", "aaaa": "Kotik2013", "bbbb": "feifeimadrid"}
    fc = _final_chips_by_token(RAW, seats)
    gold = {"kotik2013": fc["aaaa"], "feifeimadrid": fc["bbbb"],
            "lauro dermio": fc["Hero"]}
    ok, checked, matched = _stack_gate_ok(seats, anon, gold, fc, 200)
    assert ok and checked == 3 and matched == 3
    # Gold em BB também bate (unit-agnóstico)
    gold_bb = {"kotik2013": fc["aaaa"] / 200, "feifeimadrid": fc["bbbb"] / 200,
               "lauro dermio": fc["Hero"] / 200}
    ok2, _c, m2 = _stack_gate_ok(seats, anon, gold_bb, fc, 200)
    assert ok2 and m2 == 3


def _mock_query_rows(hands, base_rows):
    def q(sql, params=None):
        if "tournament_summaries" in sql:
            return base_rows
        return hands
    return q


def test_reenrich_writes_only_broken_passers_dry_run():
    seats = _seats_from_raw(RAW)
    anon = {"Hero": "Lauro Dermio", "aaaa": "Kotik2013", "bbbb": "feifeimadrid"}
    fc = _final_chips_by_token(RAW, seats)
    gold = [{"name": "Kotik2013", "stack_chips": fc["aaaa"], "bounty_value_usd": 40.0},
            {"name": "feifeimadrid", "stack_chips": fc["bbbb"], "bounty_value_usd": 5.0},
            {"name": "Lauro Dermio", "stack_chips": fc["Hero"], "bounty_value_usd": 0.0}]
    # apa STALE: seat1/seat2 trocados
    apa_stale = {"_meta": {"bb": 200},
                 "feifeimadrid": {"seat": 1}, "Kotik2013": {"seat": 2},
                 "Lauro Dermio": {"seat": 3}}
    hand = {"id": 1, "hand_id": "GG-1", "raw": RAW, "tournament_number": "T1",
            "player_names": {"anon_map": anon, "match_method": "position_v3"},
            "all_players_actions": apa_stale, "entry_players": gold}
    base_rows = [{"tournament_number": "T1", "buy_in_bounty": 40.0}]   # floor=20

    with patch.object(screenshot, "query", side_effect=_mock_query_rows([hand], base_rows)), \
         patch.object(screenshot, "get_conn") as mc:
        res = screenshot.reenrich_scrambled_gold(dry_run=True)

    assert res["written"] == 1
    assert res["written_ids"] == ["GG-1"]
    assert res["crowns_carried"] == 1          # Kotik2013 40 ok
    assert res["crowns_rejected_below_half"] == 1  # feifeimadrid 5 < 20 → 0
    mc.assert_not_called()                     # dry_run não escreve


def test_reenrich_skips_not_broken_and_gate_fail():
    seats = _seats_from_raw(RAW)
    anon = {"Hero": "Lauro Dermio", "aaaa": "Kotik2013", "bbbb": "feifeimadrid"}
    fc = _final_chips_by_token(RAW, seats)
    # (a) já-certa: apa bate anon_map+seat → não tocar
    apa_ok = {"_meta": {"bb": 200}, "Kotik2013": {"seat": 1},
              "feifeimadrid": {"seat": 2}, "Lauro Dermio": {"seat": 3}}
    ok_hand = {"id": 1, "hand_id": "GG-OK", "raw": RAW, "tournament_number": "T1",
               "player_names": {"anon_map": anon}, "all_players_actions": apa_ok,
               "entry_players": []}
    # (b) partida mas gate reprova (stacks Gold não batem)
    apa_bad = {"_meta": {"bb": 200}, "feifeimadrid": {"seat": 1},
               "Kotik2013": {"seat": 2}, "Lauro Dermio": {"seat": 3}}
    bad_gold = [{"name": "Kotik2013", "stack_chips": 999999},
                {"name": "feifeimadrid", "stack_chips": 111111},
                {"name": "Lauro Dermio", "stack_chips": 222222}]
    bad_hand = {"id": 2, "hand_id": "GG-BAD", "raw": RAW, "tournament_number": "T1",
                "player_names": {"anon_map": anon}, "all_players_actions": apa_bad,
                "entry_players": bad_gold}

    with patch.object(screenshot, "query",
                      side_effect=_mock_query_rows([ok_hand, bad_hand], [])), \
         patch.object(screenshot, "get_conn"):
        res = screenshot.reenrich_scrambled_gold(dry_run=True)

    assert res["written"] == 0
    assert res["not_broken_untouched"] == 1        # GG-OK
    assert res["skipped_gate_diverge"] == 1        # GG-BAD
