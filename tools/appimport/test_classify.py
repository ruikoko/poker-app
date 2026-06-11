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


# ── MESA — formato ANTIGO `Shot<N>-<Site>-<YYYYMMDDHHMMSS>` (pt68) ─────────────
# Coexiste com o NOVO. Site do token APÓS `Shot<N>-`; captured do timestamp; sem
# tn (backend casa por janela temporal). Sites não-mapeados → site None (Vision).

def test_shot_legacy_gg_mesa():
    k, site, cap = ai.classify_it_file("Shot21-GGPoker-20260604205243.png")
    assert k == "MESA"
    assert site == "GGPoker"
    assert cap == "2026-06-04T20:52:43"


def test_shot_legacy_wpn_mesa():
    k, site, cap = ai.classify_it_file("Shot18-WPN-20260601202136.png")
    assert k == "MESA"
    assert site == "WPN"
    assert cap == "2026-06-01T20:21:36"


def test_shot_legacy_stars_mesa():
    k, site, cap = ai.classify_it_file("Shot7-Stars-20260605193012.png")
    assert k == "MESA"
    assert site == "PokerStars"     # token antigo 'Stars' → PokerStars
    assert cap == "2026-06-05T19:30:12"


def test_shot_legacy_winamax_mesa():
    k, site, cap = ai.classify_it_file("Shot3-Winamax-20260604210000.png")
    assert k == "MESA"
    assert site == "Winamax"
    assert cap == "2026-06-04T21:00:00"


def test_shot_legacy_coinpoker_mesa_site_none():
    # CoinPoker não está no mapa de sites → site None (backend usa Vision p/ site).
    # Roteia na mesma como MESA (o formato antigo é sempre captura de mesa).
    k, site, cap = ai.classify_it_file("Shot5-CoinPoker-20260605194501.png")
    assert k == "MESA"
    assert site is None
    assert cap == "2026-06-05T19:45:01"


# ── SKIP (verdadeiramente desconhecido: nem cauda nova nem `Shot<N>-…`) ────────

def test_unknown_format_skip():
    k, site, cap = ai.classify_it_file("captura_aleatoria.png")
    assert k == "SKIP"
    assert (site, cap) == (None, None)


def test_shot_without_timestamp_skip():
    # 'Shot<N>-<Site>' sem os 14 dígitos → não é o formato antigo válido → SKIP.
    k, _site, _cap = ai.classify_it_file("Shot9-GGPoker.png")
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
