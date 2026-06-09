"""Testes do classificador por nome da pasta única `it` (pt62).

Corre standalone (não precisa de config_local — o import de config foi movido
para `load_config()`, só chamado em main()):

    python -m pytest tools/appimport/test_classify.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
import app_import as ai   # noqa: E402


# ── MESA ──────────────────────────────────────────────────────────────────────

def test_gg_mesa_clean_prefix():
    k, site, cap = ai.classify_it_file(
        "GGPoker-Bounty Hunters Hyper Special $108 _ Buy-in $108 - Blinds 1,000 "
        "_ 2,000 - Table 2_!)@(#_$&%^_60564155-20260608231443-57.png")
    assert k == "MESA"
    assert site == "GGPoker"
    assert cap == "2026-06-08T23:14:43"


def test_gg_mesa_exe_prefix():
    # prefixo do executável do IT, mas é MESA (marcador " - Blinds "/" - Table ")
    k, site, cap = ai.classify_it_file(
        "GGnet.exe-Bounty Hunters Hyper Special $108 _ Buy-in $108 - Blinds 250 "
        "_ 500 - Table 24_!)@(#_$&%^_6057220262-20260608223525-49.png")
    assert k == "MESA"
    assert site == "GGPoker"
    assert cap == "2026-06-08T22:35:25"


def test_winamax_mesa():
    k, site, cap = ai.classify_it_file(
        "Winamax-Winamax HIGHROLLER(1108710761)(#001)-20260609002319-68.png")
    assert k == "MESA"          # marcador Winamax (#001)
    assert site == "Winamax"
    assert cap == "2026-06-09T00:23:19"


# ── LOBBY ─────────────────────────────────────────────────────────────────────

def test_gg_lobby():
    k, site, cap = ai.classify_it_file(
        "GGnet.exe-Bounty Hunters Hyper Special $108-20260608231449-58.png")
    assert k == "LOBBY"         # sem marcador de mesa
    assert site == "GGPoker"
    assert cap == "2026-06-08T23:14:49"


def test_winamax_lobby():
    k, site, cap = ai.classify_it_file(
        "Winamax.exe-Winamax-20260608223716-50.png")
    assert k == "LOBBY"
    assert site == "Winamax"
    assert cap == "2026-06-08T22:37:16"


# ── SKIP (legado / sem cauda nova do IT) ──────────────────────────────────────

def test_shot_legacy_skip():
    k, site, cap = ai.classify_it_file("Shot21-GGPoker-20260604205243.png")
    assert k == "SKIP"          # tem timestamp mas não tem o sufixo `-NN`
    assert (site, cap) == (None, None)


def test_shot_wpn_legacy_skip():
    k, _site, _cap = ai.classify_it_file("Shot18-WPN-20260601202136.png")
    assert k == "SKIP"


# ── normalize_site ─────────────────────────────────────────────────────────────

def test_normalize_site_exe_and_clean():
    assert ai.normalize_site("GGPoker") == "GGPoker"
    assert ai.normalize_site("GGnet.exe") == "GGPoker"
    assert ai.normalize_site("Winamax.exe") == "Winamax"
    assert ai.normalize_site("Stars") == "PokerStars"
    assert ai.normalize_site("CoinPoker") is None
    assert ai.normalize_site(None) is None


# ── lobby_name_hint (pt63) ────────────────────────────────────────────────────

def test_lobby_name_hint_gg():
    # GG: o título no filename é o nome real do torneio → hint útil.
    assert ai.lobby_name_hint(
        "GGnet.exe-Bounty Hunters Hyper Special $108-20260608231449-58.png"
    ) == "Bounty Hunters Hyper Special $108"


def test_lobby_name_hint_gg_clean_prefix():
    assert ai.lobby_name_hint(
        "GGPoker-Daily Hyper $50-20260608231449-58.png"
    ) == "Daily Hyper $50"


def test_lobby_name_hint_winamax_is_none():
    # Winamax lobby: título é só a palavra da app ('Winamax') → sem hint.
    assert ai.lobby_name_hint("Winamax.exe-Winamax-20260608223716-50.png") is None


def test_lobby_name_hint_legacy_none():
    # Sem a cauda nova do IT → None (não é ficheiro de lobby do IT).
    assert ai.lobby_name_hint("Shot21-GGPoker-20260604205243.png") is None
