"""Unit tests para services/queue_export.py — FASE 1 conversor HH."""
from app.services.queue_export import (
    convert_gg_hh_to_pokerstars_compatible,
    _format_level_line,
    _replace_hashes,
)


# ── Sample 1: GG raw HH com anon_map cheio ────────────────────────────────────
# Baseado em hand prod id=21384 (GG-5891642943, $54 BBG Daily Main).
# Header level: 350/700/100 (ante embutido nos parens externos).
SAMPLE_GG_RAW_FULL = """Poker Hand #TM5891642943: Tournament #280446581, Bounty Hunters Daily Main $54 Hold'em No Limit - Level7(350/700(100)) - 2026/04/30 19:08:52
Table '118' 8-max Seat #2 is the button
Seat 1: Hero (40,492 in chips)
Seat 2: 96c226b8 (26,167 in chips)
Seat 3: d2ca5b9a (32,511 in chips)
e0627537: posts the ante 100
96c226b8: posts the ante 100
*** HOLE CARDS ***
Dealt to Hero [3h 8d]
96c226b8: folds
d2ca5b9a: raises 1400 to 2100
Hero: folds
*** SUMMARY ***
Seat 2: 96c226b8 folded before Flop
Seat 3: d2ca5b9a collected (3500)
"""

SAMPLE_GG_ANON_MAP = {
    "Hero": "Lauro Dermio",
    "96c226b8": "msthtb66",
    "d2ca5b9a": "EitAAn",
    "e0627537": "habibi777",
}


def test_format_level_drops_ante_and_commas():
    s = "Level17(2,500/5,000(600))"
    assert _format_level_line(s) == "Level17 (2500/5000)"


def test_format_level_handles_small_numbers():
    s = "Level7(350/700(100))"
    assert _format_level_line(s) == "Level7 (350/700)"


def test_format_level_no_match_passthrough():
    s = "Level XXII (6000/12000)"  # PS-style ja convertido
    assert _format_level_line(s) == s


def test_replace_hashes_substitutes_known_only():
    text = "Seat 2: 96c226b8 (26,167 in chips)\nSeat 3: unknown123 (...)"
    out = _replace_hashes(text, {"96c226b8": "msthtb66"})
    assert "msthtb66" in out
    assert "96c226b8" not in out
    assert "unknown123" in out  # nao mapeado, fica


def test_replace_hashes_skips_hero_and_empty():
    text = "Seat 1: Hero (...)\nSeat 2: deadbeef (...)"
    out = _replace_hashes(text, {"Hero": "Lauro", "deadbeef": "msthtb66"})
    assert "Hero" in out  # Hero permanece literal
    assert "deadbeef" not in out
    assert "msthtb66" in out


def test_replace_hashes_no_map_passthrough():
    text = "Seat 2: 96c226b8 (...)"
    assert _replace_hashes(text, {}) == text


def test_convert_gg_full_pipeline():
    hand = {
        "site": "GGPoker",
        "raw": SAMPLE_GG_RAW_FULL,
        "player_names": {"anon_map": SAMPLE_GG_ANON_MAP},
    }
    out = convert_gg_hh_to_pokerstars_compatible(hand)

    # Level reformatado.
    assert "Level7 (350/700)" in out
    assert "Level7(350/700(100))" not in out

    # Hashes substituidos.
    assert "msthtb66" in out
    assert "EitAAn" in out
    assert "habibi777" in out
    assert "96c226b8" not in out
    assert "d2ca5b9a" not in out
    assert "e0627537" not in out

    # Hero + estrutura preservados.
    assert "Seat 1: Hero" in out
    assert "*** HOLE CARDS ***" in out
    assert "*** SUMMARY ***" in out


def test_convert_gg_without_anon_map_keeps_hashes():
    hand = {
        "site": "GGPoker",
        "raw": SAMPLE_GG_RAW_FULL,
        "player_names": {},  # sem anon_map
    }
    out = convert_gg_hh_to_pokerstars_compatible(hand)
    # Level ainda reformata.
    assert "Level7 (350/700)" in out
    # Hashes intactos (degrade graceful).
    assert "96c226b8" in out
    assert "d2ca5b9a" in out


def test_convert_non_gg_passthrough():
    raw = "PokerStars Hand #123: Tournament ..."
    hand = {"site": "PokerStars", "raw": raw, "player_names": {}}
    assert convert_gg_hh_to_pokerstars_compatible(hand) == raw


def test_convert_empty_raw_returns_empty():
    hand = {"site": "GGPoker", "raw": "", "player_names": {}}
    assert convert_gg_hh_to_pokerstars_compatible(hand) == ""


def test_player_names_as_string_is_parsed():
    """player_names em BD pode vir como JSON string (nao decoded). Cobertura
    do _coerce_player_names."""
    import json as _json
    hand = {
        "site": "GGPoker",
        "raw": SAMPLE_GG_RAW_FULL,
        "player_names": _json.dumps({"anon_map": SAMPLE_GG_ANON_MAP}),
    }
    out = convert_gg_hh_to_pokerstars_compatible(hand)
    assert "msthtb66" in out
    assert "96c226b8" not in out


# ── build_queue_zip ───────────────────────────────────────────────────────────

import io as _io
import json as _json
import zipfile as _zipfile

from app.services.queue_export import build_queue_zip


def _fake_payout_blob():
    return {
        "name": "/",
        "folders": [],
        "structures": [{
            "name": "Test BBG $54",
            "chips": 1000000.0,
            "prizes": {"1": 100.0, "2": 50.0},
            "bountyType": "PKO",
            "progressiveFactor": 0.5,
        }],
    }


def test_build_queue_zip_basic_includes_hh_payouts_manifest():
    hand = {
        "id": 1, "hand_id": "GG-X", "site": "GGPoker",
        "tournament_number": "111",
        "raw": SAMPLE_GG_RAW_FULL,
        "player_names": {"anon_map": SAMPLE_GG_ANON_MAP},
    }
    blob = build_queue_zip([hand], {("GGPoker", "111"): _fake_payout_blob()})
    zf = _zipfile.ZipFile(_io.BytesIO(blob))
    names = set(zf.namelist())
    assert "GG-X/hh.txt" in names
    assert "GG-X/payouts.json" in names
    assert "manifest.json" in names
    manifest = _json.loads(zf.read("manifest.json"))
    assert manifest["total_in_zip"] == 1
    assert manifest["hands_included"][0]["has_payouts"] is True
    assert manifest["hands_included"][0]["converted_format"] == "pokerstars_compat"


def test_build_queue_zip_excludes_missing_payouts_by_default():
    hand = {
        "id": 1, "hand_id": "GG-Y", "site": "GGPoker",
        "tournament_number": "999",
        "raw": SAMPLE_GG_RAW_FULL,
        "player_names": {"anon_map": SAMPLE_GG_ANON_MAP},
    }
    blob = build_queue_zip([hand], {})
    zf = _zipfile.ZipFile(_io.BytesIO(blob))
    assert "GG-Y/hh.txt" not in set(zf.namelist())
    manifest = _json.loads(zf.read("manifest.json"))
    assert manifest["total_in_zip"] == 0
    assert manifest["missing_payouts"][0]["hand_id"] == "GG-Y"
    assert manifest["missing_payouts"][0]["reason"] == "no_row_in_tournament_payouts"


def test_build_queue_zip_includes_no_payout_when_flag_set():
    """pt23: mesmo sem payout_blob, escrevemos payouts.json só com os 3 hints
    do watcher (equity_model, max_players, script_path). `has_payouts` no
    manifest reflecte a presença do blob, não do hints-file."""
    hand = {
        "id": 1, "hand_id": "GG-Z", "site": "GGPoker",
        "tournament_number": "999",
        "raw": SAMPLE_GG_RAW_FULL,
        "player_names": {"anon_map": SAMPLE_GG_ANON_MAP},
    }
    blob = build_queue_zip([hand], {}, include_no_payout=True)
    zf = _zipfile.ZipFile(_io.BytesIO(blob))
    names = set(zf.namelist())
    assert "GG-Z/hh.txt" in names
    # pt23: payouts.json escrito SEMPRE (mesmo sem blob) para entregar hints
    assert "GG-Z/payouts.json" in names
    payouts = _json.loads(zf.read("GG-Z/payouts.json"))
    # hints presentes, sem dados de payout
    assert payouts["equity_model"] in ("malmuth_harville_icm", "multi_table_icm")
    assert isinstance(payouts["max_players"], int)
    assert payouts["script_path"] is None
    assert "CompletedTournament" not in payouts  # sem blob, só hints
    manifest = _json.loads(zf.read("manifest.json"))
    assert manifest["total_in_zip"] == 1
    assert manifest["hands_included"][0]["has_payouts"] is False


def test_build_queue_zip_hints_merged_with_payouts():
    """pt23: quando há payout_blob, hints são merged como top-level keys
    no payouts.json (sem destruir CompletedTournament/structures)."""
    hand = {
        "id": 1, "hand_id": "GG-HINT", "site": "GGPoker",
        "tournament_number": "111",
        "raw": SAMPLE_GG_RAW_FULL,
        "player_names": {"anon_map": SAMPLE_GG_ANON_MAP},
        "hm3_tags": ["ICM FT"],          # → equity_model = malmuth_harville_icm
        "discord_tags": None,
    }
    blob = build_queue_zip([hand], {("GGPoker", "111"): _fake_payout_blob()})
    zf = _zipfile.ZipFile(_io.BytesIO(blob))
    payouts = _json.loads(zf.read("GG-HINT/payouts.json"))
    # payout blob preservado
    assert payouts["structures"][0]["name"] == "Test BBG $54"
    assert payouts["structures"][0]["bountyType"] == "PKO"
    # hints presentes
    assert payouts["equity_model"] == "malmuth_harville_icm"
    assert isinstance(payouts["max_players"], int)
    assert payouts["script_path"] is None


def test_build_queue_zip_default_equity_when_no_FT_tags():
    """pt23: sem tags FT (HM3 ou Discord), default = multi_table_icm."""
    hand = {
        "id": 1, "hand_id": "GG-DEF", "site": "GGPoker",
        "tournament_number": "111",
        "raw": SAMPLE_GG_RAW_FULL,
        "player_names": {"anon_map": SAMPLE_GG_ANON_MAP},
        "hm3_tags": ["icm-pko"],         # tag não-FT
        "discord_tags": ["sqz-pko"],     # tag não-FT
    }
    blob = build_queue_zip([hand], {("GGPoker", "111"): _fake_payout_blob()})
    zf = _zipfile.ZipFile(_io.BytesIO(blob))
    payouts = _json.loads(zf.read("GG-DEF/payouts.json"))
    assert payouts["equity_model"] == "multi_table_icm"


def test_build_queue_zip_skips_hand_without_raw():
    hand = {
        "id": 1, "hand_id": "GG-NORAW", "site": "GGPoker",
        "tournament_number": "111", "raw": "", "player_names": {},
    }
    blob = build_queue_zip(
        [hand], {("GGPoker", "111"): _fake_payout_blob()},
    )
    zf = _zipfile.ZipFile(_io.BytesIO(blob))
    manifest = _json.loads(zf.read("manifest.json"))
    assert manifest["total_in_zip"] == 0
    assert manifest["skipped"][0]["reason"] == "no_raw_hh"


def test_build_queue_zip_manifest_filters_echo():
    blob = build_queue_zip(
        [], {},
        filters_meta={"tags": ["icm-pko"], "include_no_payout": False},
    )
    zf = _zipfile.ZipFile(_io.BytesIO(blob))
    manifest = _json.loads(zf.read("manifest.json"))
    assert manifest["filters"] == {
        "tags": ["icm-pko"], "include_no_payout": False,
    }
    assert manifest["total_hands_queried"] == 0
    assert manifest["hands_included"] == []
