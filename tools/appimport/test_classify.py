"""Testes do classificador por nome da pasta única `it` (pt62).

Corre standalone (não precisa de config_local — o import de config foi movido
para `load_config()`, só chamado em main()):

    python -m pytest tools/appimport/test_classify.py
"""
import os
import sys
import tempfile
from datetime import datetime

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


# ── Janela de datas das IMAGENS (dia-de-jogo 15:00→15:00) ─────────────────────

def test_window_bounds_both():
    lo, hi = ai.window_bounds("2026-06-08", "2026-06-11")
    assert lo == datetime(2026, 6, 8, 15, 0)      # desde 15:00 inclusive
    assert hi == datetime(2026, 6, 12, 15, 0)     # (ate+1) 15:00 exclusivo → cobre dia 11


def test_window_bounds_desde_only():
    lo, hi = ai.window_bounds("2026-06-08", None)
    assert lo == datetime(2026, 6, 8, 15, 0)
    assert hi is None


def test_window_bounds_ate_only():
    lo, hi = ai.window_bounds("", "2026-06-11")
    assert lo is None
    assert hi == datetime(2026, 6, 12, 15, 0)


def test_window_bounds_none():
    assert ai.window_bounds(None, None) == (None, None)
    assert ai.window_bounds("", "") == (None, None)


def test_window_bounds_invalid_is_none():
    # data inválida → None desse lado (não rebenta)
    lo, hi = ai.window_bounds("2026-13-99", "2026-06-11")
    assert lo is None
    assert hi == datetime(2026, 6, 12, 15, 0)


def test_date_in_window_inside():
    w = ai.window_bounds("2026-06-08", "2026-06-11")
    dentro, motivo = ai.date_in_window(datetime(2026, 6, 8, 23, 14, 43), w)
    assert dentro is True and motivo is None


def test_date_in_window_lo_boundary_inclusive():
    w = ai.window_bounds("2026-06-08", "2026-06-11")
    assert ai.date_in_window(datetime(2026, 6, 8, 15, 0), w)[0] is True       # 15:00 entra
    assert ai.date_in_window(datetime(2026, 6, 8, 14, 59), w)[0] is False     # 14:59 fora (dia anterior)


def test_date_in_window_hi_boundary_exclusive():
    w = ai.window_bounds("2026-06-08", "2026-06-11")
    assert ai.date_in_window(datetime(2026, 6, 12, 14, 59), w)[0] is True     # ainda dia-de-jogo 11
    assert ai.date_in_window(datetime(2026, 6, 12, 15, 0), w)[0] is False     # já dia-de-jogo 12


def test_date_in_window_before_reason():
    w = ai.window_bounds("2026-06-08", "2026-06-11")
    dentro, motivo = ai.date_in_window(datetime(2026, 6, 7, 20, 0), w)
    assert dentro is False and "desde" in motivo


def test_date_in_window_after_reason():
    w = ai.window_bounds("2026-06-08", "2026-06-11")
    dentro, motivo = ai.date_in_window(datetime(2026, 6, 13, 10, 0), w)
    assert dentro is False and "fim" in motivo


def test_date_in_window_iso_string():
    w = ai.window_bounds("2026-06-08", "2026-06-11")
    assert ai.date_in_window("2026-06-09T00:23:19", w)[0] is True


def test_date_in_window_no_window_passes_all():
    # sem janela → tudo dentro (comportamento de sempre)
    assert ai.date_in_window(datetime(2020, 1, 1), (None, None)) == (True, None)
    assert ai.date_in_window(datetime(2020, 1, 1), None) == (True, None)


def test_date_in_window_bad_date_passes():
    # dt inparseável com janela activa → não filtra (defensivo)
    w = ai.window_bounds("2026-06-08", "2026-06-11")
    assert ai.date_in_window("lixo", w) == (True, None)


def test_img_date_captured_wins():
    # captured_iso (do nome do IT) ganha; sem acesso a ficheiro
    assert ai._img_date("/inexistente.png", "2026-06-08T23:14:43") == datetime(2026, 6, 8, 23, 14, 43)


def test_img_date_falls_back_to_mtime():
    # sem captured_iso → mtime do ficheiro real
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tf:
        path = tf.name
    try:
        ts = datetime(2026, 6, 9, 12, 0, 0).timestamp()
        os.utime(path, (ts, ts))
        assert ai._img_date(path) == datetime(2026, 6, 9, 12, 0, 0)
    finally:
        os.unlink(path)


def test_img_date_bad_captured_falls_back_to_mtime():
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tf:
        path = tf.name
    try:
        ts = datetime(2026, 6, 9, 12, 0, 0).timestamp()
        os.utime(path, (ts, ts))
        assert ai._img_date(path, "data-invalida") == datetime(2026, 6, 9, 12, 0, 0)
    finally:
        os.unlink(path)


# ── pt72 — pasta-como-tag: subpasta de it\ → tag base ─────────────────────────

def test_folder_tag_known_folders():
    assert ai._folder_tag_for("ICM") == "icm"
    assert ai._folder_tag_for("ICM PKO") == "icm-pko"
    assert ai._folder_tag_for("PKO Pos") == "pos-pko"
    assert ai._folder_tag_for("NPKO Pos") == "pos-nko"


def test_folder_tag_case_and_space_insensitive():
    assert ai._folder_tag_for("icm pko") == "icm-pko"
    assert ai._folder_tag_for("  ICM   PKO  ") == "icm-pko"
    assert ai._folder_tag_for("npko  pos") == "pos-nko"


def test_folder_tag_unknown_returns_none():
    assert ai._folder_tag_for("Qualquer Outra") is None
    assert ai._folder_tag_for("") is None
    assert ai._folder_tag_for(None) is None


# ── pt73 — tabela alargada: FT manual, SpeedRacer, Nota ───────────────────────

def test_folder_tag_manual_ft_folders():
    # pastas que JÁ trazem '-ft' no nome → tag já-FT (FT manual, confirmado)
    assert ai._folder_tag_for("ICM PKO FT") == "icm-pko-ft"
    assert ai._folder_tag_for("PKO Pos FT") == "pos-pko-ft"
    assert ai._folder_tag_for("  icm  pko  ft ") == "icm-pko-ft"


def test_folder_tag_speedracer():
    assert ai._folder_tag_for("SpeedRacer") == "speed-racer"
    assert ai._folder_tag_for("speedracer") == "speed-racer"
    assert ai._folder_tag_for("Speed Racer") == "speed-racer"   # tolera espaço


def test_folder_tag_nota():
    assert ai._folder_tag_for("Nota") == "nota"
    assert ai._folder_tag_for("nota") == "nota"
