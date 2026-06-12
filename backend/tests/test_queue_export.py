"""Unit tests para services/queue_export.py — FASE 1 + FASE 2 (pt29) conversor HH."""
from app.services.queue_export import (
    convert_gg_hh_to_pokerstars_compatible,
    _format_level_line,
    _replace_hashes,
    # pt29 Fase 2: 8 transformacoes PS-compat
    _rewrite_header_to_pokerstars,
    _normalize_level_spacing,
    _inject_bounties_ps_format,
    _format_bounty_amount,
    _drop_showdown_if_no_show,
    _add_doesnt_show_after_collected,
    _drop_dealt_to_non_hero,
    _trim_total_pot_trailing_fields,
    _strip_commas_from_amounts,
    compute_hero_bounty,
    _crown_to_total_factor,
    build_queue_zip,
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

    # pt29 Fase 2 passo 1: header PokerStars.
    assert "PokerStars Hand #5891642943:" in out
    assert "Poker Hand #TM5891642943:" not in out

    # pt29 Fase 2 passo 2: Level com espaco.
    assert "Level 7 (350/700)" in out
    assert "Level7(350/700(100))" not in out

    # Hashes substituidos.
    assert "msthtb66" in out
    assert "EitAAn" in out
    assert "habibi777" in out
    assert "96c226b8" not in out
    assert "d2ca5b9a" not in out
    assert "e0627537" not in out

    # pt41: sem tournament_format/bounty_ctx → formato não-bounty → SEM token
    # de bounty (Opção A). O hardcode €250 foi removido.
    assert "Seat 1: Hero (40492 in chips)" in out
    assert "bounty)" not in out

    # Estrutura preservada.
    assert "*** HOLE CARDS ***" in out
    assert "*** SUMMARY ***" in out


def test_convert_gg_without_anon_map_keeps_hashes():
    hand = {
        "site": "GGPoker",
        "raw": SAMPLE_GG_RAW_FULL,
        "player_names": {},  # sem anon_map
    }
    out = convert_gg_hh_to_pokerstars_compatible(hand)
    # Level ainda reformata com espaco.
    assert "Level 7 (350/700)" in out
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


# ── pt24 bounty injection REMOVIDO em pt28-v3 (#HRC-GG-KOS-EXTRACTION reabre).
# Smoke 20 Maio: HRC parser rejeita HH com ", $X.XX bounty)" nas Seat lines.
# `_inject_bounties_into_seat_lines` foi apagada. Bounties continuam em
# payouts.json paralelo (HRC le por essa via). Tests pt24 abaixo removidos.


# ── pt29 Fase 2: 8 transformacoes PS-compat para HRC aceitar HH GG ──────────

# Passo 1: header
def test_rewrite_header_to_pokerstars_replaces_tm_prefix():
    assert _rewrite_header_to_pokerstars(
        "Poker Hand #TM5944816316: Tournament #999, ..."
    ) == "PokerStars Hand #5944816316: Tournament #999, ..."


def test_rewrite_header_to_pokerstars_only_first_line():
    """Replace count=1 — so a 1a linha."""
    s = "Poker Hand #TM123: a\nPoker Hand #TM456: b"
    out = _rewrite_header_to_pokerstars(s)
    assert "PokerStars Hand #123:" in out
    assert "Poker Hand #TM456:" in out  # 2a linha intacta


def test_rewrite_header_no_match_passthrough():
    s = "PokerStars Hand #999: ja convertida"
    assert _rewrite_header_to_pokerstars(s) == s


# Passo 2: Level spacing
def test_normalize_level_spacing_inserts_space():
    assert _normalize_level_spacing("Level14 (1750/3500)") == "Level 14 (1750/3500)"


def test_normalize_level_spacing_idempotent_with_existing_space():
    """`Level 14` ja tem espaco -> nao muda (regex pede `Level<digit>` directo)."""
    s = "Level 14 (1750/3500)"
    assert _normalize_level_spacing(s) == s


# Passo 3: bounty PS format
def test_format_bounty_amount_integer_drops_decimals():
    assert _format_bounty_amount(250.0) == "250"
    assert _format_bounty_amount(100) == "100"


def test_format_bounty_amount_fractional_keeps_two_decimals():
    assert _format_bounty_amount(112.5) == "112.50"
    assert _format_bounty_amount(75.25) == "75.25"


# pt41: _inject_bounties_ps_format passou a receber starting_bounty (base do TS).
# Hardcode €250 removido. Hero = max(Vision, base); vilões = Vision real OU base.
def test_inject_bounties_hero_uses_ts_base_when_not_in_players_list():
    """Hero sem Vision -> base do TS (não 250). starting_bounty=100 -> €100."""
    hh = "Seat 1: Hero (40,492 in chips)\n"
    out = _inject_bounties_ps_format(
        hh, [], {"Hero": "Lauro Dermio"}, starting_bounty=100.0,
    )
    assert "Seat 1: Hero (40,492 in chips, €100 bounty)" in out


def test_inject_bounties_hero_keeps_ts_base_when_vision_below():
    """Vision do Hero < base -> usa base (max)."""
    hh = "Seat 1: Hero (40,492 in chips)\n"
    out = _inject_bounties_ps_format(
        hh, [{"name": "Lauro Dermio", "bounty_value_usd": 75}],
        {"Hero": "Lauro Dermio"}, starting_bounty=100.0,
    )
    assert "Seat 1: Hero (40,492 in chips, €100 bounty)" in out


def test_inject_bounties_hero_keeps_vision_when_above_base():
    """Vision do Hero > base (post-KOs) -> usa Vision."""
    hh = "Seat 1: Hero (40,492 in chips)\n"
    out = _inject_bounties_ps_format(
        hh, [{"name": "Lauro Dermio", "bounty_value_usd": 500}],
        {"Hero": "Lauro Dermio"}, starting_bounty=100.0,
    )
    assert "Seat 1: Hero (40,492 in chips, €500 bounty)" in out


def test_inject_bounties_non_hero_uses_players_list_value():
    """Vilão com Vision real -> usa o valor por-nick (SS-matched)."""
    hh = "Seat 2: msthtb66 (26,167 in chips)\n"
    out = _inject_bounties_ps_format(
        hh, [{"name": "msthtb66", "bounty_value_usd": 50}], {},
        starting_bounty=100.0,
    )
    assert "Seat 2: msthtb66 (26,167 in chips, €50 bounty)" in out


def test_inject_bounties_non_hero_decimal_value():
    hh = "Seat 8: Dennis (272,264 in chips)\n"
    out = _inject_bounties_ps_format(
        hh, [{"name": "Dennis", "bounty_value_usd": 112.5}], {},
        starting_bounty=100.0,
    )
    assert "Seat 8: Dennis (272,264 in chips, €112.50 bounty)" in out


def test_inject_bounties_non_hero_missing_falls_back_to_ts_base():
    """pt41: vilão sem Vision (GG anon) -> base do TS, não €0."""
    hh = "Seat 7: Unknown (50,000 in chips)\n"
    out = _inject_bounties_ps_format(hh, [], {}, starting_bounty=40.0)
    assert "Seat 7: Unknown (50,000 in chips, €40 bounty)" in out


def test_inject_bounties_currency_is_always_euro():
    """Validado empiricamente pelo Rui: HRC aceita € e rejeita $."""
    hh = "Seat 1: Hero (1000 in chips)\n"
    out = _inject_bounties_ps_format(hh, [], {"Hero": "X"}, starting_bounty=50.0)
    assert "€" in out
    assert "$" not in out


# pt41 — compute_hero_bounty (fonte única Hero bounty + source)
def test_compute_hero_bounty_ts_wins_when_no_vision():
    val, src = compute_hero_bounty([], {"Hero": "Lauro"}, 100.0)
    assert val == 100.0 and src == "ts"


def test_compute_hero_bounty_vision_wins_when_above():
    val, src = compute_hero_bounty(
        [{"name": "Lauro", "bounty_value_usd": 250}], {"Hero": "Lauro"}, 100.0)
    assert val == 250.0 and src == "vision"


# ── #KO-CROWN-INSTANT-FIX — coroa = parte instantânea (metade); recuperar total ─
def test_crown_to_total_factor_gates_pko_only():
    """PKO → ×2 (coroa ÷ instant_fraction 0.5); Super KO / KO / Mystery / Vanilla
    → 1.0 (coroa inalterada)."""
    assert _crown_to_total_factor("PKO") == 2.0
    assert _crown_to_total_factor("pko") == 2.0
    assert _crown_to_total_factor("Super KO") == 1.0
    assert _crown_to_total_factor("KO") == 1.0
    assert _crown_to_total_factor("Mystery KO") == 1.0
    assert _crown_to_total_factor("Vanilla") == 1.0
    assert _crown_to_total_factor(None) == 1.0


def test_compute_hero_bounty_pko_doubles_crown_but_stays_at_base_when_fresh():
    """#KO-CROWN-INSTANT-FIX: Hero fresco — coroa $10 × 2 = $20 = base do TS.
    `max(coroa×2, starting)` = max(20, 20) = 20 (mantém-se a $20)."""
    val, src = compute_hero_bounty(
        [{"name": "Lauro", "bounty_value_usd": 10}], {"Hero": "Lauro"}, 20.0,
        crown_factor=2.0)
    assert val == 20.0   # max(10×2, 20) = 20 — Hero continua a $20


def test_convert_gg_pko_fresh_crown_doubles_to_total():
    """REGRESSÃO: Forty Stack $44 (PKO 50/50), vilão FRESCO. A coroa Vision é $10
    (parte instantânea); o HRC precisa do total $20. Antes: €10 (KO-T$=10, com
    progressiveFactor 0.5 → KO-P$=5). Depois: €20 (KO-T$=20 → KO-P$=10)."""
    hand = {
        "site": "GGPoker", "raw": SAMPLE_GG_RAW_FULL,
        "tournament_format": "PKO",
        "player_names": {
            "anon_map": SAMPLE_GG_ANON_MAP,
            "players_list": [{"name": "msthtb66", "bounty_value_usd": 10}],
        },
    }
    out = convert_gg_hh_to_pokerstars_compatible(
        hand, bounty_ctx={"starting_bounty": 20.0})
    # vilão fresco: coroa 10 × 2 = €20 (KO-T$=20)
    assert "Seat 2: msthtb66 (26167 in chips, €20 bounty)" in out
    # Hero sem coroa: base do TS €20 (não escala) — continua a 20
    assert "Seat 1: Hero (40492 in chips, €20 bounty)" in out


def test_convert_gg_superko_crown_not_doubled():
    """GUARDA: Super KO (instant_fraction não confirmado) NÃO duplica a coroa.
    msthtb66 coroa $10 → €10 (inalterado), apesar de passar pela injecção; o
    Hero (sem coroa) usa a base €20 — contraste que prova a coroa intocada."""
    hand = {
        "site": "GGPoker", "raw": SAMPLE_GG_RAW_FULL,
        "tournament_format": "Super KO",
        "player_names": {
            "anon_map": SAMPLE_GG_ANON_MAP,
            "players_list": [{"name": "msthtb66", "bounty_value_usd": 10}],
        },
    }
    out = convert_gg_hh_to_pokerstars_compatible(
        hand, bounty_ctx={"starting_bounty": 20.0})
    assert "Seat 2: msthtb66 (26167 in chips, €10 bounty)" in out   # NÃO €20
    assert "Seat 1: Hero (40492 in chips, €20 bounty)" in out       # base, não coroa


def test_convert_winamax_passthrough_crown_unchanged():
    """GUARDA: Winamax é passthrough total (HRC lê WN nativo). A coroa/bounty da
    HH WN NÃO é tocada pelo fix GG, mesmo com tournament_format=PKO + bounty_ctx."""
    wn_raw = (
        'Winamax Poker - Tournament "X" buyIn: 90€ + 10€ - 2026/05/11 21:45:00 UTC\n'
        "Seat 1: thinvalium (351657, 244.20€ bounty)\n"
    )
    hand = {"site": "Winamax", "raw": wn_raw, "tournament_format": "PKO",
            "player_names": {}}
    out = convert_gg_hh_to_pokerstars_compatible(
        hand, bounty_ctx={"starting_bounty": 20.0})
    assert out == wn_raw   # idêntico, sem duplicar 244.20€


# pt41 — gate de formato no conversor
def test_convert_gg_pko_with_ts_bounty_injects():
    hand = {
        "site": "GGPoker", "raw": SAMPLE_GG_RAW_FULL,
        "tournament_format": "PKO",
        "player_names": {"anon_map": SAMPLE_GG_ANON_MAP},
    }
    out = convert_gg_hh_to_pokerstars_compatible(
        hand, bounty_ctx={"starting_bounty": 100.0})
    # Hero sem Vision -> base TS 100; vilões (nicks reais via anon_map) -> base 100.
    assert "Seat 1: Hero (40492 in chips, €100 bounty)" in out
    assert "€100 bounty" in out


def test_convert_gg_vanilla_no_bounty_token():
    hand = {
        "site": "GGPoker", "raw": SAMPLE_GG_RAW_FULL,
        "tournament_format": "Vanilla",
        "player_names": {"anon_map": SAMPLE_GG_ANON_MAP},
    }
    out = convert_gg_hh_to_pokerstars_compatible(
        hand, bounty_ctx={"starting_bounty": None})
    assert "bounty)" not in out
    assert "Seat 1: Hero (40492 in chips)" in out


def test_convert_gg_pko_without_ctx_no_token():
    """PKO mas sem bounty_ctx (base None) -> sem token (defensiva no conversor)."""
    hand = {
        "site": "GGPoker", "raw": SAMPLE_GG_RAW_FULL,
        "tournament_format": "PKO",
        "player_names": {"anon_map": SAMPLE_GG_ANON_MAP},
    }
    out = convert_gg_hh_to_pokerstars_compatible(hand, bounty_ctx=None)
    assert "bounty)" not in out


# pt41 — defensiva no build_queue_zip: GG PKO sem TS -> skip pko_without_ts_bounty
def test_build_queue_zip_skips_pko_without_ts_bounty():
    import json
    import zipfile
    import io as _io
    hand = {
        "id": 1, "hand_id": "GG-1", "site": "GGPoker", "tournament_number": "T1",
        "tournament_format": "PKO", "raw": SAMPLE_GG_RAW_FULL,
        "player_names": {"anon_map": SAMPLE_GG_ANON_MAP},
    }
    zb = build_queue_zip(
        [hand], {("GGPoker", "T1"): {"x": 1}},
        bounty_by_key={},  # sem base do TS
    )
    with zipfile.ZipFile(_io.BytesIO(zb)) as zf:
        manifest = json.loads(zf.read("manifest.json"))
    assert manifest["total_in_zip"] == 0
    assert manifest["skipped"][0]["reason"] == "pko_without_ts_bounty"


# Passo 4: drop SHOWDOWN sem shows
def test_drop_showdown_when_no_shows_between_markers():
    hh = (
        "Hero: folds\n"
        "*** SHOWDOWN ***\n"
        "*** SUMMARY ***\n"
        "Total pot 100 | Rake 0\n"
    )
    out = _drop_showdown_if_no_show(hh)
    assert "*** SHOWDOWN ***" not in out
    assert "*** SUMMARY ***" in out


def test_keep_showdown_when_player_shows():
    hh = (
        "*** SHOWDOWN ***\n"
        "Hero: shows [Ah Kh] (high card Ace)\n"
        "*** SUMMARY ***\n"
    )
    out = _drop_showdown_if_no_show(hh)
    assert "*** SHOWDOWN ***" in out


def test_drop_showdown_no_op_when_marker_absent():
    hh = "Hero: folds\n*** SUMMARY ***\n"
    assert _drop_showdown_if_no_show(hh) == hh


# Passo 5: add "doesn't show hand"
def test_add_doesnt_show_after_collected_from_pot():
    hh = (
        "msthtb66: folds\n"
        "Hero collected 3500 from pot\n"
        "*** SUMMARY ***\n"
    )
    out = _add_doesnt_show_after_collected(hh)
    assert "Hero: doesn't show hand" in out
    # Linha "doesn't show" vem DEPOIS do collected
    lines = out.split("\n")
    collected_idx = next(i for i, l in enumerate(lines) if "collected 3500" in l)
    doesnt_idx = next(i for i, l in enumerate(lines) if "doesn't show" in l)
    assert doesnt_idx == collected_idx + 1


def test_add_doesnt_show_skips_when_already_present():
    """Se ja existe 'doesn't show hand' a seguir, nao duplica."""
    hh = (
        "Hero collected 3500 from pot\n"
        "Hero: doesn't show hand\n"
        "*** SUMMARY ***\n"
    )
    out = _add_doesnt_show_after_collected(hh)
    assert out.count("Hero: doesn't show hand") == 1


def test_add_doesnt_show_skips_inside_summary():
    """`Seat N: <player> collected (X)` dentro do SUMMARY usa formato diferente
    e nao deve disparar a injeccao."""
    hh = (
        "*** SUMMARY ***\n"
        "Seat 3: msthtb66 collected (3500)\n"
    )
    out = _add_doesnt_show_after_collected(hh)
    assert "doesn't show" not in out


# Passo 6: drop "Dealt to" non-Hero
def test_drop_dealt_to_non_hero_removes_no_cards_lines():
    hh = (
        "*** HOLE CARDS ***\n"
        "Dealt to Hero [3h 8d]\n"
        "Dealt to msthtb66 \n"
        "Dealt to EitAAn \n"
        "msthtb66: folds\n"
    )
    out = _drop_dealt_to_non_hero(hh)
    assert "Dealt to Hero [3h 8d]" in out
    assert "Dealt to msthtb66" not in out
    assert "Dealt to EitAAn" not in out
    assert "msthtb66: folds" in out  # outras linhas intactas


def test_drop_dealt_to_keeps_non_hero_with_cards():
    """Se por acaso houver `Dealt to <player> [cards]` non-Hero (raro mas
    possivel em showdown HHs), mantemos."""
    hh = "Dealt to msthtb66 [As Kh]\n"
    out = _drop_dealt_to_non_hero(hh)
    assert "Dealt to msthtb66 [As Kh]" in out


# Passo 7: total pot trim
def test_trim_total_pot_drops_jackpot_bingo_fortune_tax():
    hh = "Total pot 3500 | Rake 0 | Jackpot 0 | Bingo 0 | Fortune 0 | Tax 0\n"
    out = _trim_total_pot_trailing_fields(hh)
    assert "Total pot 3500 | Rake 0\n" in out
    assert "Jackpot" not in out
    assert "Bingo" not in out
    assert "Fortune" not in out
    assert "Tax" not in out


def test_trim_total_pot_no_op_when_already_trimmed():
    hh = "Total pot 3500 | Rake 0\n"
    assert _trim_total_pot_trailing_fields(hh) == hh


# Passo 8: strip commas from amounts
def test_strip_commas_from_thousands():
    assert _strip_commas_from_amounts("40,492 in chips") == "40492 in chips"
    assert _strip_commas_from_amounts("raises 1,400 to 2,100") == "raises 1400 to 2100"


def test_strip_commas_handles_millions():
    """`1,234,567` -> `1234567` (3+ grupos de virgulas)."""
    assert _strip_commas_from_amounts("1,234,567 chips") == "1234567 chips"


def test_strip_commas_keeps_single_comma_in_natural_text():
    """`Hold em No Limit, Level 7` — virgula natural (sem digits a seguir) nao
    e tocada."""
    s = "Hold em No Limit, Level 7"
    assert _strip_commas_from_amounts(s) == s


def test_strip_commas_idempotent():
    s = "40492 in chips"
    assert _strip_commas_from_amounts(s) == s


# End-to-end: mao GG-5944816316 (baseline do briefing pt27-pt29)
_HH_GG_5944816316_RAW = """Poker Hand #TM5944816316: Tournament #283300918, Bounty Hunters Big Game $525 Hold em No Limit - Level13(1,500/3,000(400)) - 2026/05/12 21:26:18
Table '97-H' 8-max Seat #5 is the button
Seat 1: aaaa1111 (45,123 in chips)
Seat 2: bbbb2222 (52,400 in chips)
Seat 3: cccc3333 (38,800 in chips)
Seat 4: Hero (44,250 in chips)
Seat 5: dddd4444 (60,000 in chips)
Seat 6: eeee5555 (28,500 in chips)
Seat 7: ffff6666 (33,900 in chips)
Seat 8: gggg7777 (41,200 in chips)
aaaa1111: posts the ante 400
bbbb2222: posts the ante 400
cccc3333: posts the ante 400
Hero: posts the ante 400
dddd4444: posts the ante 400
eeee5555: posts the ante 400
ffff6666: posts the ante 400
gggg7777: posts the ante 400
eeee5555: posts small blind 1,500
ffff6666: posts big blind 3,000
*** HOLE CARDS ***
Dealt to aaaa1111
Dealt to bbbb2222
Dealt to cccc3333
Dealt to Hero [Ah Kc]
Dealt to dddd4444
Dealt to eeee5555
Dealt to ffff6666
Dealt to gggg7777
gggg7777: folds
aaaa1111: folds
bbbb2222: raises 6,000 to 6,000
cccc3333: folds
Hero: raises 38,250 to 44,250 and is all-in
dddd4444: folds
eeee5555: folds
ffff6666: folds
bbbb2222: folds
Uncalled bet (38,250) returned to Hero
Hero collected 21,200 from pot
*** SHOWDOWN ***
*** SUMMARY ***
Total pot 21,200 | Rake 0 | Jackpot 0 | Bingo 0 | Fortune 0 | Tax 0
Seat 4: Hero collected (21,200)
"""


def test_end_to_end_gg_5944816316_passes_all_8_transformations():
    """Mao baseline pt27-pt29 (GG-5944816316, 97-H Bounty Hunters Daily Main,
    Hero HJ 3-bet jam, eff 6.64BB). Confirma que o output do exporter passa
    todas as 8 transformacoes em ordem correcta — o que o HRC parser engole
    pos-pt29 Fase 2."""
    hand = {
        "site": "GGPoker",
        "raw": _HH_GG_5944816316_RAW,
        "tournament_format": "PKO",
        "player_names": {
            "anon_map": {
                "Hero": "Lauro Dermio",
                "aaaa1111": "playerA",
                "bbbb2222": "playerB",
                "cccc3333": "playerC",
                "dddd4444": "playerD",
                "eeee5555": "playerE",
                "ffff6666": "playerF",
                "gggg7777": "playerG",
            },
            "players_list": [
                {"name": "playerA", "bounty_value_usd": 50},
                {"name": "playerB", "bounty_value_usd": 75},
                {"name": "playerD", "bounty_value_usd": 100},
            ],
        },
    }
    # pt41: Big Game $525 = PKO, bounty base $250 do TS (via bounty_ctx).
    out = convert_gg_hh_to_pokerstars_compatible(
        hand, bounty_ctx={"starting_bounty": 250.0})

    # 1. Header PS
    assert "PokerStars Hand #5944816316:" in out
    assert "Poker Hand #TM5944816316:" not in out

    # 2. Level com espaco
    assert "Level 13 (1500/3000)" in out

    # 3. Bounty pt41 + #KO-CROWN-INSTANT-FIX: Hero sem Vision -> base TS €250;
    # vilões com Vision -> coroa × 2 (coroa = parte instantânea no PKO 50/50);
    # vilões sem Vision (GG anon) -> base TS €250 (já não €0; base não escala).
    assert "Seat 4: Hero (44250 in chips, €250 bounty)" in out
    assert "Seat 1: playerA (45123 in chips, €100 bounty)" in out   # 50 × 2
    assert "Seat 2: playerB (52400 in chips, €150 bounty)" in out   # 75 × 2
    assert "Seat 5: playerD (60000 in chips, €200 bounty)" in out   # 100 × 2
    # Players sem bounty no players_list -> base do TS (€250), não €0 nem ×2.
    assert "Seat 3: playerC (38800 in chips, €250 bounty)" in out

    # 4. SHOWDOWN removido (Hero ganhou por uncalled bet, sem shows)
    assert "*** SHOWDOWN ***" not in out

    # 5. doesn't show adicionado apos collected from pot
    assert "Hero: doesn't show hand" in out

    # 6. Dealt to non-Hero removido; Hero mantido
    assert "Dealt to Hero [Ah Kc]" in out
    for hash_id in ("aaaa1111", "bbbb2222", "cccc3333", "dddd4444",
                     "eeee5555", "ffff6666", "gggg7777"):
        assert f"Dealt to {hash_id}" not in out
    # Tambem nao deve haver "Dealt to playerA" etc (sem cartas)
    for nick in ("playerA", "playerB", "playerC", "playerD",
                 "playerE", "playerF", "playerG"):
        assert f"Dealt to {nick}" not in out

    # 7. Total pot trim
    assert "Total pot 21200 | Rake 0" in out
    assert "Jackpot" not in out
    assert "Bingo" not in out
    assert "Fortune" not in out
    assert "Tax" not in out

    # 8. Virgulas removidas em todos os amounts
    assert "1,500" not in out
    assert "44,250" not in out
    assert "21,200" not in out
    assert "38,250" not in out


# ── pt25: #HRC-PRUNE-IN-GAP-DOWNSTREAM helpers ─────────────────────────────

import os as _os
from app.services.queue_export import (
    derive_real_aggressor_position,
)


# ── derive_real_aggressor_position ──────────────────────────────────────────

# Helper builder para HHs de teste. 8-max, button configurável.
# pt25d HRC docs convention (UTG=0 first-to-act preflop, BB=N-1) para 8-max
# com button=Seat #4:
#   UTG=Seat 7 (idx 0), EP=Seat 8 (idx 1), MP=Seat 1 (idx 2), HJ=Seat 2 (idx 3),
#   CO=Seat 3 (idx 4), BU=Seat 4 (idx 5), SB=Seat 5 (idx 6), BB=Seat 6 (idx 7).

def _hh_8max_btn4(preflop_actions: list[str]) -> str:
    """Constrói uma HH 8-max minimal com button Seat #4 e acções preflop
    customizáveis."""
    lines = [
        "Poker Hand #TM1: Tournament #100, Test - Level5 (200/400) - 2026/05/01 00:00:00",
        "Table 'A' 8-max Seat #4 is the button",
        "Seat 1: MPplayer (10000 in chips)",      # MP, HRC idx 2
        "Seat 2: HJplayer (10000 in chips)",      # HJ, HRC idx 3
        "Seat 3: COplayer (10000 in chips)",      # CO, HRC idx 4
        "Seat 4: Hero (10000 in chips)",          # BU, HRC idx 5
        "Seat 5: SBplayer (10000 in chips)",      # SB, HRC idx 6
        "Seat 6: BBplayer (10000 in chips)",      # BB, HRC idx 7
        "Seat 7: UTGplayer (10000 in chips)",     # UTG, HRC idx 0
        "Seat 8: EPplayer (10000 in chips)",      # EP, HRC idx 1
        "SBplayer: posts small blind 200",
        "BBplayer: posts big blind 400",
        "*** HOLE CARDS ***",
        "Dealt to Hero [As Kd]",
    ]
    lines.extend(preflop_actions)
    lines.append("*** SUMMARY ***")
    return "\n".join(lines) + "\n"


def test_aggressor_UTG_opens():
    """8-max, UTG raise first → HRC idx 0 (pt25d convention)."""
    hh = _hh_8max_btn4(["UTGplayer: raises 800 to 1200"])
    assert derive_real_aggressor_position(hh) == 0


def test_aggressor_EP_opens():
    """UTG folds, EP raises → HRC idx 1."""
    hh = _hh_8max_btn4([
        "UTGplayer: folds",
        "EPplayer: raises 800 to 1200",
    ])
    assert derive_real_aggressor_position(hh) == 1


def test_aggressor_MP_opens():
    """UTG/EP fold, MP raises → HRC idx 2."""
    hh = _hh_8max_btn4([
        "UTGplayer: folds",
        "EPplayer: folds",
        "MPplayer: raises 800 to 1200",
    ])
    assert derive_real_aggressor_position(hh) == 2


def test_aggressor_HJ_opens():
    """UTG/EP/MP fold, HJ raises → HRC idx 3."""
    hh = _hh_8max_btn4([
        "UTGplayer: folds",
        "EPplayer: folds",
        "MPplayer: folds",
        "HJplayer: raises 800 to 1200",
    ])
    assert derive_real_aggressor_position(hh) == 3


def test_aggressor_CO_opens():
    """UTG/EP/MP/HJ fold, CO raises → HRC idx 4."""
    hh = _hh_8max_btn4([
        "UTGplayer: folds",
        "EPplayer: folds",
        "MPplayer: folds",
        "HJplayer: folds",
        "COplayer: raises 800 to 1200",
    ])
    assert derive_real_aggressor_position(hh) == 4


def test_aggressor_SB_completes_returns_None():
    """Limp pot — todos foldam até SB, SB completa, BB checks → None
    (sem raise voluntário; também não é SB-opens-excepção, é literalmente
    sem aggressor)."""
    hh = _hh_8max_btn4([
        "UTGplayer: folds",
        "EPplayer: folds",
        "MPplayer: folds",
        "HJplayer: folds",
        "COplayer: folds",
        "Hero: folds",
        "SBplayer: calls 200",
        "BBplayer: checks",
    ])
    assert derive_real_aggressor_position(hh) is None


def test_aggressor_SB_opens_returns_idx6():
    """pt25d: todos foldam até SB, SB raises → SB idx (N-2 = 6 em 8-handed).
    Não há mais early-return None desde pt25d (era heurística da convenção
    velha onde SB=0). `derive_prune_downstream` devolve [] naturalmente
    para esse caso (downstream vazio porque só BB sobra)."""
    hh = _hh_8max_btn4([
        "UTGplayer: folds",
        "EPplayer: folds",
        "MPplayer: folds",
        "HJplayer: folds",
        "COplayer: folds",
        "Hero: folds",
        "SBplayer: raises 600 to 1200",
        "BBplayer: folds",
    ])
    assert derive_real_aggressor_position(hh) == 6


def test_aggressor_BU_opens_returns_idx5():
    """UTG..CO fold, BU (Hero, idx 5 em 8-handed = N-3) raises → 5.
    Test crítico para GG-5914506215 real (Hero=BU opens, smoke pt23)."""
    hh = _hh_8max_btn4([
        "UTGplayer: folds",
        "EPplayer: folds",
        "MPplayer: folds",
        "HJplayer: folds",
        "COplayer: folds",
        "Hero: raises 800 to 1200",
    ])
    assert derive_real_aggressor_position(hh) == 5


# ── pt25b: cross-site marker + action format compat ────────────────────────

from app.services.queue_export import find_preflop_marker


def test_find_preflop_marker_PS_GG_HOLE_CARDS():
    """PS/GG: `*** HOLE CARDS ***`."""
    hh = "... header ...\n*** HOLE CARDS ***\nDealt to Hero [As Kd]\n..."
    pos = find_preflop_marker(hh)
    assert pos is not None
    assert hh[pos:pos + 18] == "*** HOLE CARDS ***"


def test_find_preflop_marker_WN_PRE_FLOP():
    """Winamax: `*** PRE-FLOP ***`."""
    hh = "... header ...\n*** ANTE/BLINDS ***\n[antes]\n*** PRE-FLOP ***\nplayer raises 100\n..."
    pos = find_preflop_marker(hh)
    assert pos is not None
    assert hh[pos:pos + 16] == "*** PRE-FLOP ***"


def test_find_preflop_marker_none_returns_None():
    """Sem nenhum marker → None."""
    assert find_preflop_marker("just header text\nno markers here\n") is None
    assert find_preflop_marker("") is None
    assert find_preflop_marker(None) is None  # type: ignore[arg-type]


def test_find_preflop_marker_both_returns_earlier():
    """Se ambos markers existirem (defensive), devolve o mais cedo."""
    # PS marker primeiro
    hh1 = "x\n*** HOLE CARDS ***\nstuff\n*** PRE-FLOP ***\nmore\n"
    assert find_preflop_marker(hh1) == hh1.find("*** HOLE CARDS ***")
    # WN marker primeiro (improvável real, mas testa o min())
    hh2 = "y\n*** PRE-FLOP ***\nstuff\n*** HOLE CARDS ***\nmore\n"
    assert find_preflop_marker(hh2) == hh2.find("*** PRE-FLOP ***")


# Samples reais (snippets minimalistas) de cada site para validar end-to-end.
# Estrutura essencial preservada: header com Seat #N is the button + N-max,
# Seat lines com nicks, marker preflop, primeira action raise/bet.

_HH_PS_REAL = """PokerStars Hand #260299428000: Tournament #3983882920, €45+€45+€10 EUR Hold'em No Limit - Level XXVI (12500/25000) - 2026/03/31 23:40:45 WET [2026/03/31 18:40:45 ET]
Table '3983882920 23' 6-max Seat #5 is the button
Seat 1: kokonakueka (736340 in chips, €196.87 bounty)
Seat 2: carlos8surf (925129 in chips, €292.50 bounty)
Seat 4: QuimDiamond (763155 in chips, €163.12 bounty)
Seat 5: Votsarrr (633451 in chips, €323.43 bounty)
Seat 6: UltraLoubard (391164 in chips, €191.25 bounty)
kokonakueka: posts the ante 3250
*** HOLE CARDS ***
Dealt to Hero [Ah As]
carlos8surf: folds
QuimDiamond: folds
Votsarrr: raises 605201 to 630201 and is all-in
UltraLoubard: folds
kokonakueka: folds
*** SUMMARY ***
"""


_HH_GG_REAL = """Poker Hand #TM5939385803: Tournament #282699155, Bounty Hunters Forty Stack $44 Hold'em No Limit - Level3(150/300(45)) - 2026/05/11 17:16:38
Table '155' 8-max Seat #1 is the button
Seat 1: Hero (40,000 in chips)
Seat 5: b839c780 (90,299 in chips)
Seat 6: 3343ebc6 (47,788 in chips)
Seat 7: 8db88342 (44,636 in chips)
Seat 8: 221ebf0d (42,483 in chips)
*** HOLE CARDS ***
Dealt to Hero [As Kd]
8db88342: folds
221ebf0d: raises 300 to 600
Hero: calls 600
b839c780: folds
*** SUMMARY ***
"""


_HH_WN_REAL = """Winamax Poker - Tournament "INTERSTELLAR" buyIn: 90€ + 10€ level: 22 - HandId: #4699459877053923331-277-1778535900 - Holdem no limit (1000/4000/8000) - 2026/05/11 21:45:00 UTC
Table: 'INTERSTELLAR(1094178268)#002' 6-max (real money) Seat #2 is the button
Seat 1: yousnouf75 (163754, 194.40€ bounty)
Seat 2: imbagosu (615675, 532.70€ bounty)
Seat 3: Beu_Teu (663845, 311.97€ bounty)
Seat 4: thinvalium (351657, 244.20€ bounty)
Seat 5: blueballs67 (354758, 140€ bounty)
*** ANTE/BLINDS ***
Beu_Teu posts ante 1000
*** PRE-FLOP ***
blueballs67 raises 8000 to 16000
yousnouf75 calls 16000
imbagosu folds
Beu_Teu raises 48000 to 64000
*** SUMMARY ***
"""


_HH_WPN_REAL = """Game Hand #2735377673 - $60,000 GTD Tournament #35005597 - Holdem (No Limit) - Level 4 (800.00/1600.00) - 2026/05/11 16:51:23 UTC
Table '39' 8-max Seat #1 is the button
Seat 1: Jetsies (448465.00)
Seat 2: cringemeariver (130314.00)
Seat 3: AbamaAbezyana (100200.00)
Seat 4: TuuusTuuuuus (89400.00)
Seat 5: egegey1 (112340.00)
Seat 6: pocahontas94 (79244.00)
Seat 7: DAVIDSBAGOFICE (110968.00)
Seat 8: eagle47 (34502.00)
Jetsies posts ante 200.00
*** HOLE CARDS ***
TuuusTuuuuus folds
egegey1 folds
pocahontas94 folds
DAVIDSBAGOFICE raises 1600.00 to 3200.00
*** SUMMARY ***
"""


def test_aggressor_PS_real_sample():
    """PS sample (PS-260299428000, 6-max BU=Seat 5, 5 sentados):
    Votsarrr@Seat5=BU opens → idx 2 (pt25d: BU em 5-handed = N-3 = 2)."""
    out = derive_real_aggressor_position(_HH_PS_REAL)
    assert out is not None
    # pt25d: button=Seat5; seat_list=[1,2,4,5,6]; btn_idx_in_list=3; n=5;
    # first_to_act_offset=3 → hrc0=seat_list[(3+3+0)%5=1]=Seat2(carlos8surf,UTG),
    # hrc1=Seat4(QuimDiamond,HJ), hrc2=Seat5(Votsarrr,BU),
    # hrc3=Seat6(UltraLoubard,SB), hrc4=Seat1(kokonakueka,BB).
    # Votsarrr opens → idx 2. ✓
    assert out == 2


def test_aggressor_GG_real_sample():
    """GG sample (GG real, 8-max BU=Seat 1, 5 sentados): 1º raise é
    221ebf0d@Seat8 após 8db88342@Seat7 fold. pt25d: HJ em 5-handed = idx 1."""
    out = derive_real_aggressor_position(_HH_GG_REAL)
    assert out is not None
    # pt25d: button=Seat1; seat_list=[1,5,6,7,8]; btn_idx_in_list=0; n=5;
    # first_to_act_offset=3 → hrc0=seat_list[3]=Seat7(8db88342,UTG),
    # hrc1=Seat8(221ebf0d,HJ), hrc2=Seat1(Hero,BU),
    # hrc3=Seat5(b839c780,SB), hrc4=Seat6(3343ebc6,BB).
    # 8db88342 folds (UTG=0), 221ebf0d raises (HJ=1). Aggressor=1.
    assert out == 1


def test_aggressor_WN_real_sample_INTERSTELLAR():
    """Winamax INTERSTELLAR (smoke target pt25b+pt25d): 6-max 5-sentados
    BU=Seat 2; blueballs67@Seat5=UTG raises first → idx 0 (pt25d)."""
    out = derive_real_aggressor_position(_HH_WN_REAL)
    assert out is not None
    # pt25d: seat_list=[1,2,3,4,5]; btn_idx_in_list=1; n=5;
    # first_to_act_offset=3 → hrc0=seat_list[(1+3+0)%5=4]=Seat5(blueballs67,UTG),
    # hrc1=Seat1(yousnouf75,HJ), hrc2=Seat2(imbagosu,BU),
    # hrc3=Seat3(Beu_Teu,SB), hrc4=Seat4(thinvalium,BB).
    # blueballs67 raises = idx 0 (UTG). ✓
    assert out == 0


def test_aggressor_WPN_real_sample():
    """WPN sample (8-max BU=Seat 1, 8 sentados full): DAVIDSBAGOFICE@Seat7
    raises após 3 folds. pt25d: HJ em 8-handed = idx 3."""
    out = derive_real_aggressor_position(_HH_WPN_REAL)
    assert out is not None
    # pt25d: 8 sentados, seat_list=[1..8], btn_idx_in_list=0, first_offset=3 →
    # hrc0=Seat4(TuuusTuuuuus,UTG), hrc1=Seat5(egegey1,EP),
    # hrc2=Seat6(pocahontas94,MP), hrc3=Seat7(DAVIDSBAGOFICE,HJ),
    # hrc4=Seat8(eagle47,CO), hrc5=Seat1(Jetsies,BU),
    # hrc6=Seat2(cringemeariver,SB), hrc7=Seat3(AbamaAbezyana,BB).
    # TuuusTuuuuus/egegey1/pocahontas94 fold (idx 0/1/2), DAVIDSBAGOFICE raises (idx 3).
    assert out == 3


# ── pt25b ETAPA 3: derive_seats_in_preflop_order + derive_table_format ──────

from app.services.queue_export import (
    derive_seats_in_preflop_order,
    derive_table_format,
)


def test_seats_PS_real_sample():
    """PS-260299428000: 6-max BU=Seat 5, 5 sentados (Seat 3 missing).
    order (vocab Rui): HJ, CO, BTN, SB, BB (HJ=idx 0)."""
    seats = derive_seats_in_preflop_order(_HH_PS_REAL)
    assert len(seats) == 5
    assert seats[0] == {"seat": 2, "position": "HJ", "hrc_idx": 0, "nick": "carlos8surf"}
    assert seats[1] == {"seat": 4, "position": "CO",  "hrc_idx": 1, "nick": "QuimDiamond"}
    assert seats[2] == {"seat": 5, "position": "BTN", "hrc_idx": 2, "nick": "Votsarrr"}
    assert seats[3] == {"seat": 6, "position": "SB",  "hrc_idx": 3, "nick": "UltraLoubard"}
    assert seats[4] == {"seat": 1, "position": "BB",  "hrc_idx": 4, "nick": "kokonakueka"}


def test_seats_GG_real_sample():
    """GG-5939385803: 8-max BU=Seat 1, 5 sentados (Seats 2,3,4 missing).
    pt25d order: UTG, HJ, BU, SB, BB."""
    seats = derive_seats_in_preflop_order(_HH_GG_REAL)
    assert len(seats) == 5
    nicks = [s["nick"] for s in seats]
    assert nicks == ["8db88342", "221ebf0d", "Hero", "b839c780", "3343ebc6"]
    positions = [s["position"] for s in seats]
    assert positions == ["HJ", "CO", "BTN", "SB", "BB"]


def test_seats_WN_real_sample_INTERSTELLAR():
    """WN-INTERSTELLAR (smoke target pt25b+pt25d): 6-max BU=Seat 2, 5 sentados.
    pt25d order: UTG, HJ, BU, SB, BB. blueballs67=UTG=idx 0 (era idx 2)."""
    seats = derive_seats_in_preflop_order(_HH_WN_REAL)
    assert len(seats) == 5
    nicks = [s["nick"] for s in seats]
    assert nicks == ["blueballs67", "yousnouf75", "imbagosu", "Beu_Teu", "thinvalium"]
    positions = [s["position"] for s in seats]
    assert positions == ["HJ", "CO", "BTN", "SB", "BB"]
    # blueballs67 = HJ = hrc_idx 0 (1ª posição em 5-handed)
    assert next(s for s in seats if s["nick"] == "blueballs67")["hrc_idx"] == 0


def test_seats_WPN_real_sample():
    """WPN: 8-max BU=Seat 1, 8 sentados full.
    pt25d order: UTG, EP, MP, HJ, CO, BU, SB, BB."""
    seats = derive_seats_in_preflop_order(_HH_WPN_REAL)
    assert len(seats) == 8
    nicks = [s["nick"] for s in seats]
    assert nicks[0] == "TuuusTuuuuus"     # UTG
    assert nicks[1] == "egegey1"           # UTG1
    assert nicks[2] == "pocahontas94"      # MP
    assert nicks[3] == "DAVIDSBAGOFICE"    # HJ (aggressor)
    assert nicks[5] == "Jetsies"           # BTN
    assert nicks[6] == "cringemeariver"    # SB
    assert nicks[7] == "AbamaAbezyana"     # BB
    positions = [s["position"] for s in seats]
    assert positions == ["UTG", "UTG1", "MP", "HJ", "CO", "BTN", "SB", "BB"]


def test_seats_no_button_returns_empty():
    """Defensive: header sem 'Seat #N is the button' → []."""
    hh = "Some HH header without button info\nSeat 1: Foo (100 in chips)\nSeat 2: Bar (200 in chips)\n*** HOLE CARDS ***\n"
    assert derive_seats_in_preflop_order(hh) == []


def test_seats_no_seats_returns_empty():
    """Defensive: HH sem seat lines parseable → []."""
    assert derive_seats_in_preflop_order("") == []
    assert derive_seats_in_preflop_order("Just a header\n*** HOLE CARDS ***\n") == []


# ── dead button (botão num seat vazio) ──────────────────────────────────────

from pathlib import Path as _Path

_FIXTURES_DIR = _Path(__file__).parent / "fixtures"


def test_seats_dead_button_winamax_real_sample():
    """Mão real WN-4627029952301105208-84 (W SERIES 3M, dead button): 6-max,
    `Seat #6 is the button` mas Seat 6 está vazio (eliminado). 4 sentados
    (Seats 1,3,4,5). Ancorando nas blinds + distância geométrica ao botão
    morto: Seat1=SB, Seat3=BB, Seat5=CO (1 antes do botão), Seat4=HJ (2
    antes). Ordem de acção preflop [Seat4, Seat5, Seat1, Seat3] confere com
    as acções reais (River_Judge folds, thinvalium raises, Dvstrr/SB folds,
    KipitKiet/BB calls)."""
    hh = (_FIXTURES_DIR / "winamax_hh_deadbutton.txt").read_text(encoding="utf-8")
    seats = derive_seats_in_preflop_order(hh)
    assert len(seats) == 4
    by_seat = {s["seat"]: s["position"] for s in seats}
    assert by_seat == {1: "SB", 3: "BB", 4: "HJ", 5: "CO"}
    # hrc_idx em ordem de acção preflop.
    assert [s["seat"] for s in seats] == [4, 5, 1, 3]
    assert [s["position"] for s in seats] == ["HJ", "CO", "SB", "BB"]
    assert [s["nick"] for s in seats] == [
        "River_Judge", "thinvalium", "Dvstrr", "KipitKiet",
    ]


def test_seats_dead_button_rejects_adulterated_blinds():
    """Cross-check de blinds: se o montante postado não bate com o nível do
    header (HH adulterada / corrompida), a derivação dead button rejeita
    (`[]`) em vez de fabricar posições erradas. Header é (250/1000/2000) →
    SB=1000; mudar o post de SB para 999 desalinha e deve devolver []."""
    hh = (_FIXTURES_DIR / "winamax_hh_deadbutton.txt").read_text(encoding="utf-8")
    bad = hh.replace("posts small blind 1000", "posts small blind 999")
    assert "posts small blind 999" in bad  # sanity: a mutação aplicou-se
    assert derive_seats_in_preflop_order(bad) == []


# ── derive_table_format ─────────────────────────────────────────────────────

def test_table_format_PS():
    assert derive_table_format(_HH_PS_REAL) == 6


def test_table_format_GG():
    assert derive_table_format(_HH_GG_REAL) == 8


def test_table_format_WN():
    assert derive_table_format(_HH_WN_REAL) == 6


def test_table_format_WPN():
    assert derive_table_format(_HH_WPN_REAL) == 8


def test_table_format_no_N_max_fallback_8():
    assert derive_table_format("Just some text without max format\n") == 8
    assert derive_table_format("") == 8
    assert derive_table_format(None) == 8  # type: ignore[arg-type]


# ── hrc_script_gen: gerador novo per-hand (Maio 2026) ───────────────────────
# Substitui os antigos tests de derive_prune_downstream + generate_hrc_script
# (mecanismo de prune via JS removido — migra para Bloco 2 do watcher).

from app.services.hrc_script_gen import (
    apply_sizings_overrides,
    build_sizings_overrides,
    compute_effective_stack_bb,
    generate_hrc_script_for_hand,
    _NON_ALL_IN_DEFAULT_OPEN_BB,
    _NON_ALL_IN_OPEN_MIN_EFF_BB,
    _NON_ALL_IN_DEFAULT_4BET_MULT,
    _NON_ALL_IN_DEFAULT_5BET_MULT,
    _NON_ALL_IN_DEFAULT_SQUEEZE_MULT,
    _NON_ALL_IN_DEFAULT_3BET_MULT_HIGH,
    _NON_ALL_IN_DEFAULT_3BET_MULT_MID,
    _NON_ALL_IN_DEFAULT_3BET_MULT_LOW,
    _OPEN_ALLIN_THRESHOLD_BB,
    _array_for_raise,
    _array_for_4bet5bet_in_pot_fraction,
    _bucket_3bet,
    _bucket_4bet5bet,
    _bucket_open,
    _compute_default_for_4bet,
    _compute_default_for_5bet,
    _compute_default_for_classic_3bet,
    _compute_default_for_open,
    _compute_default_for_squeeze,
    _candidate_3bet_positions_ip,
    _canonical_3bet_position,
    _default_3bet_for_candidate,
    _eff_spot_specific_bb,
    _blind_open_size_by_eff,
    _bb_3bet_default_vs_open,
    _eff_3bettor_vs_live_nonallin,
    _ISO_RAISE_OVER_ALLIN_MULT,
    _format_sizing_array,
    _parse_preflop_actions,
    _parse_seat_stacks,
    _position_bucket_open,
    _postflop_rank,
)
from app.services.queue_export import derive_seats_in_preflop_order


# ── _parse_seat_stacks + compute_effective_stack_bb (cross-site) ────────────

def test_parse_seat_stacks_PS_real():
    """PS: chips com vírgula opcional + ' in chips'."""
    out = _parse_seat_stacks(_HH_PS_REAL)
    assert out["Votsarrr"] == 633451.0
    assert out["UltraLoubard"] == 391164.0


def test_parse_seat_stacks_GG_real():
    out = _parse_seat_stacks(_HH_GG_REAL)
    assert out["Hero"] == 40000.0
    assert out["221ebf0d"] == 42483.0


def test_parse_seat_stacks_WN_real():
    """WN: chips sem ' in chips', com bounty depois — regex pára em ')'."""
    out = _parse_seat_stacks(_HH_WN_REAL)
    assert out["blueballs67"] == 354758.0
    assert out["imbagosu"] == 615675.0


def test_parse_seat_stacks_WPN_real():
    """WPN: chips com 2 decimais."""
    out = _parse_seat_stacks(_HH_WPN_REAL)
    assert out["Jetsies"] == 448465.0
    assert out["eagle47"] == 34502.0


def test_compute_effective_stack_bb_PS():
    """PS sample: BB=25000; min stack = UltraLoubard 391164 → 391164/25000 = 15.65 BB."""
    eff = compute_effective_stack_bb(_HH_PS_REAL, level_bb=25000)
    assert eff == 15.65


def test_compute_effective_stack_bb_GG():
    """GG sample: BB=300; min stack = Hero 40000 → 40000/300 ≈ 133.33 BB."""
    eff = compute_effective_stack_bb(_HH_GG_REAL, level_bb=300)
    assert eff == 133.33


def test_compute_effective_stack_bb_no_seats_returns_None():
    assert compute_effective_stack_bb("nope nothing", level_bb=100) is None


def test_compute_effective_stack_bb_invalid_bb_returns_None():
    assert compute_effective_stack_bb(_HH_GG_REAL, level_bb=0) is None
    assert compute_effective_stack_bb(_HH_GG_REAL, level_bb=None) is None


# ── _position_bucket_open ─────────────────────────────────────────────────

def test_position_bucket_open_returns_BU_for_BU_BTN_HU():
    assert _position_bucket_open("BU") == "BU"
    assert _position_bucket_open("BTN") == "BU"
    assert _position_bucket_open("BU/SB") == "BU"


def test_position_bucket_open_returns_SB_BB():
    assert _position_bucket_open("SB") == "SB"
    assert _position_bucket_open("BB") == "BB"


def test_position_bucket_open_returns_OTHERS_for_everything_else():
    for pos in ("UTG", "EP", "MP", "EP1", "EP2", "HJ", "CO"):
        assert _position_bucket_open(pos) == "OTHERS"


def test_position_bucket_open_None_or_empty_returns_OTHERS():
    assert _position_bucket_open(None) == "OTHERS"
    assert _position_bucket_open("") == "OTHERS"


# ── _postflop_rank — IP/OOP lookup ─────────────────────────────────────────

def test_postflop_rank_5handed():
    """5-handed (UTG=0, HJ=1, BU=2, SB=3, BB=4): postflop order = SB=0, BB=1,
    UTG=2, HJ=3, BU=4 (BU most IP)."""
    assert _postflop_rank(0, 5) == 2   # UTG
    assert _postflop_rank(1, 5) == 3   # HJ
    assert _postflop_rank(2, 5) == 4   # BU
    assert _postflop_rank(3, 5) == 0   # SB
    assert _postflop_rank(4, 5) == 1   # BB


def test_postflop_rank_6handed():
    """6-handed: BU=3 → rank 5 (most IP)."""
    assert _postflop_rank(3, 6) == 5
    assert _postflop_rank(4, 6) == 0   # SB
    assert _postflop_rank(5, 6) == 1   # BB


# ── _parse_preflop_actions ─────────────────────────────────────────────────

def test_parse_preflop_actions_GG_CO_open():
    """GG sample: 221ebf0d (CO, idx 1 em 5-handed) opens to 600. Stack 42483 /
    BB 300 → eff ~141 BB. Cobre bet_count=1 + position resolution."""
    seats = derive_seats_in_preflop_order(_HH_GG_REAL)
    actions = _parse_preflop_actions(_HH_GG_REAL, seats, level_sb=150, level_bb=300)
    assert len(actions) == 1
    a = actions[0]
    assert a["bet_count"] == 1
    assert a["nick"] == "221ebf0d"
    assert a["hrc_idx"] == 1
    assert a["position"] == "CO"
    assert a["to_amount_bb"] == 2.0
    assert a["callers_before"] == 0


def test_parse_preflop_actions_PS_BTN_jam():
    """PS sample: Votsarrr (BTN, idx 2 em 5-handed) raises 605201 to 630201
    (jam). BB 25000 → 630201/25000 ≈ 25.21 BB."""
    seats = derive_seats_in_preflop_order(_HH_PS_REAL)
    actions = _parse_preflop_actions(_HH_PS_REAL, seats, level_sb=12500, level_bb=25000)
    assert len(actions) == 1
    a = actions[0]
    assert a["bet_count"] == 1
    assert a["nick"] == "Votsarrr"
    assert a["position"] == "BTN"
    assert a["to_amount_bb"] == 25.21


def test_parse_preflop_actions_WN_squeeze():
    """WN INTERSTELLAR: blueballs67 (HJ) raises to 16000, yousnouf75 calls,
    imbagosu folds, Beu_Teu (SB) 3-bets to 64000. SB 3-bet com 1 caller
    inbetween → callers_before=1 (squeeze)."""
    seats = derive_seats_in_preflop_order(_HH_WN_REAL)
    actions = _parse_preflop_actions(_HH_WN_REAL, seats, level_sb=4000, level_bb=8000)
    assert len(actions) == 2
    open_action = actions[0]
    sqz_action = actions[1]
    assert open_action["bet_count"] == 1
    assert open_action["nick"] == "blueballs67"
    assert open_action["position"] == "HJ"
    assert open_action["to_amount_bb"] == 2.0
    assert sqz_action["bet_count"] == 2
    assert sqz_action["nick"] == "Beu_Teu"
    assert sqz_action["position"] == "SB"
    assert sqz_action["to_amount_bb"] == 8.0
    assert sqz_action["callers_before"] == 1


def test_parse_preflop_actions_walk_to_BB_returns_empty():
    """HH sem nenhum raise → list vazio."""
    hh = (
        "Hand #X: Test - Level1 (50/100) - 2026/01/01\n"
        "Table 'T' 6-max Seat #1 is the button\n"
        "Seat 1: A (10000 in chips)\n"
        "Seat 2: B (10000 in chips)\n"
        "B: posts small blind 50\n"
        "A: posts big blind 100\n"
        "*** HOLE CARDS ***\n"
        "B: folds\n"
        "*** SUMMARY ***\n"
    )
    seats = derive_seats_in_preflop_order(hh)
    actions = _parse_preflop_actions(hh, seats, level_sb=50, level_bb=100)
    assert actions == []


# ── _bucket_open / _bucket_3bet / _bucket_4bet5bet ─────────────────────────

def test_bucket_open_mapping():
    assert _bucket_open({"bet_count": 1, "position": "UTG"}) == "SIZES_OPEN_OTHERS"
    assert _bucket_open({"bet_count": 1, "position": "BU"}) == "SIZES_OPEN_BU"
    assert _bucket_open({"bet_count": 1, "position": "SB"}) == "SIZES_OPEN_SB"
    assert _bucket_open({"bet_count": 1, "position": "BB"}) == "SIZES_OPEN_BB"


def test_bucket_open_returns_None_for_non_open():
    assert _bucket_open({"bet_count": 2, "position": "BU"}) is None


def test_bucket_3bet_squeeze_buckets():
    # Squeeze IP (HJ 3-bets after open + 1 caller)
    a = {"bet_count": 2, "position": "HJ", "callers_before": 1}
    assert _bucket_3bet(a, opener_position="UTG") == "SIZES_3BET_SQUEEZE_IP"
    # Squeeze SB
    a = {"bet_count": 2, "position": "SB", "callers_before": 1}
    assert _bucket_3bet(a, opener_position="UTG") == "SIZES_3BET_SQUEEZE_SB"
    # Squeeze BB
    a = {"bet_count": 2, "position": "BB", "callers_before": 1}
    assert _bucket_3bet(a, opener_position="UTG") == "SIZES_3BET_SQUEEZE_BB"


def test_bucket_3bet_non_squeeze_buckets():
    # SB 3-bets BB
    a = {"bet_count": 2, "position": "SB", "callers_before": 0}
    assert _bucket_3bet(a, opener_position="BB") == "SIZES_3BET_SB_VS_BB"
    # SB 3-bets other
    a = {"bet_count": 2, "position": "SB", "callers_before": 0}
    assert _bucket_3bet(a, opener_position="UTG") == "SIZES_3BET_SB_VS_OTHER"
    # BB 3-bets SB
    a = {"bet_count": 2, "position": "BB", "callers_before": 0}
    assert _bucket_3bet(a, opener_position="SB") == "SIZES_3BET_BB_VS_SB"
    # BB 3-bets other
    a = {"bet_count": 2, "position": "BB", "callers_before": 0}
    assert _bucket_3bet(a, opener_position="UTG") == "SIZES_3BET_BB_VS_OTHER"
    # Other 3-bets IP (pt42b — dispatch por posição canónica)
    a = {"bet_count": 2, "position": "HJ", "callers_before": 0}
    assert _bucket_3bet(a, opener_position="UTG") == "SIZES_3BET_HJ"


def test_bucket_4bet5bet_IP_OOP():
    # 4-bet by BU (idx 5) vs 3-better SB (idx 6) em 8-handed → BU postflop
    # rank 7 > SB rank 0 → IP.
    a = {"bet_count": 3, "hrc_idx": 5, "previous_raiser_idx": 6}
    assert _bucket_4bet5bet(a, n_seated=8) == "SIZES_POT_4BET_IP"
    # 5-bet by SB (idx 6) vs 4-better BU (idx 5) → SB rank 0 < BU rank 7 → OOP.
    a = {"bet_count": 4, "hrc_idx": 6, "previous_raiser_idx": 5}
    assert _bucket_4bet5bet(a, n_seated=8) == "SIZES_POT_5BET_OOP"


def test_bucket_4bet5bet_returns_None_for_non_4bet5bet():
    assert _bucket_4bet5bet({"bet_count": 1, "hrc_idx": 0, "previous_raiser_idx": None}, n_seated=6) is None
    assert _bucket_4bet5bet({"bet_count": 2, "hrc_idx": 0, "previous_raiser_idx": 0}, n_seated=6) is None


# ── pt42b — Helpers para 3-bet IP por posição ───────────────────────────

def test_canonical_3bet_position_passthrough():
    """UTG1/UTG/MP/HJ/CO/BU passam directamente."""
    assert _canonical_3bet_position("UTG1") == "UTG1"
    assert _canonical_3bet_position("UTG") == "UTG"
    assert _canonical_3bet_position("MP") == "MP"
    assert _canonical_3bet_position("HJ") == "HJ"
    assert _canonical_3bet_position("CO") == "CO"
    assert _canonical_3bet_position("BU") == "BU"


def test_canonical_3bet_position_UTG2_collapse_to_UTG1():
    """9-handed: UTG2 partilha SIZES_3BET_UTG1 (provisório, vocab Rui)."""
    assert _canonical_3bet_position("UTG2") == "UTG1"


def test_canonical_3bet_position_BTN_alias():
    """BTN (tabela) → BU (nome HRC); o botão é o único com nome próprio."""
    assert _canonical_3bet_position("BTN") == "BU"
    assert _canonical_3bet_position("BU/SB") == "BU"


def test_canonical_3bet_position_excluded_returns_None():
    """SB/BB/labels inexistentes → None (não cobertos pela proposta B)."""
    for pos in ("SB", "BB", "LJ", "Unknown", "", None):
        assert _canonical_3bet_position(pos) is None


def test_candidate_3bet_positions_ip_HU_returns_empty():
    """HU (2-handed): labels=[BU/SB, BB]. Opener BU/SB → []. BB-3-bet via
    SIZES_3BET_BB_VS_SB (fora do scope)."""
    seats = [{"position": "BU/SB"}, {"position": "BB"}]
    assert _candidate_3bet_positions_ip(seats, "BU/SB") == []


def test_candidate_3bet_positions_ip_3handed_opener_BTN_returns_empty():
    """3-handed [BTN, SB, BB]: opener=BTN → [] (sem candidatos IP)."""
    seats = [{"position": p} for p in ("BTN", "SB", "BB")]
    assert _candidate_3bet_positions_ip(seats, "BTN") == []


def test_candidate_3bet_positions_ip_4handed_opener_CO():
    """4-handed [CO, BTN, SB, BB]: opener=CO → 1 candidato = BU (BTN→BU)."""
    seats = [{"position": p} for p in ("CO", "BTN", "SB", "BB")]
    assert _candidate_3bet_positions_ip(seats, "CO") == ["BU"]


def test_candidate_3bet_positions_ip_6handed_opener_MP():
    """6-handed [MP, HJ, CO, BTN, SB, BB]: opener=MP → [HJ, CO, BU]."""
    seats = [{"position": p} for p in ("MP", "HJ", "CO", "BTN", "SB", "BB")]
    assert _candidate_3bet_positions_ip(seats, "MP") == ["HJ", "CO", "BU"]


def test_candidate_3bet_positions_ip_6handed_opener_HJ():
    """6-handed: opener=HJ → só [CO, BU] são candidatos IP."""
    seats = [{"position": p} for p in ("MP", "HJ", "CO", "BTN", "SB", "BB")]
    assert _candidate_3bet_positions_ip(seats, "HJ") == ["CO", "BU"]


def test_candidate_3bet_positions_ip_8handed_opener_UTG():
    """8-handed [UTG, UTG1, MP, HJ, CO, BTN, SB, BB]: opener=UTG →
    [UTG1, MP, HJ, CO, BU] (5 candidatos; BTN→BU)."""
    seats = [{"position": p} for p in
             ("UTG", "UTG1", "MP", "HJ", "CO", "BTN", "SB", "BB")]
    assert _candidate_3bet_positions_ip(seats, "UTG") == ["UTG1", "MP", "HJ", "CO", "BU"]


def test_candidate_3bet_positions_ip_9handed_opener_UTG2():
    """9-handed [UTG2, UTG1, UTG, MP, HJ, CO, BTN, SB, BB]: opener=UTG2 →
    [UTG1, UTG, MP, HJ, CO, BU] (UTG2 colapsa para UTG1 só no canonical de
    sizing; aqui é o opener, não candidato)."""
    seats = [{"position": p} for p in
             ("UTG2", "UTG1", "UTG", "MP", "HJ", "CO", "BTN", "SB", "BB")]
    assert _candidate_3bet_positions_ip(seats, "UTG2") == ["UTG1", "UTG", "MP", "HJ", "CO", "BU"]


def test_candidate_3bet_positions_ip_invalid_opener_returns_empty():
    """Opener não está em labels → [] (defensivo)."""
    seats = [{"position": p} for p in ("MP", "HJ", "CO", "BTN", "SB", "BB")]
    assert _candidate_3bet_positions_ip(seats, "NotAPos") == []
    assert _candidate_3bet_positions_ip(seats, None) == []


def test_candidate_3bet_positions_ip_empty_seats_returns_empty():
    assert _candidate_3bet_positions_ip([], "UTG") == []


def test_eff_spot_specific_bb_deep_vs_deep():
    """Opener 100 BB, candidato 100 BB, BB=100 chips. min=100 BB."""
    assert _eff_spot_specific_bb(10000.0, 10000.0, 100) == 100.0


def test_eff_spot_specific_bb_short_dominates():
    """Opener 50 BB, candidato 22 BB → eff = 22 BB (short)."""
    assert _eff_spot_specific_bb(5000.0, 2200.0, 100) == 22.0


def test_eff_spot_specific_bb_None_inputs():
    """Qualquer input None ou BB inválido → None."""
    assert _eff_spot_specific_bb(None, 1000.0, 100) is None
    assert _eff_spot_specific_bb(1000.0, None, 100) is None
    assert _eff_spot_specific_bb(1000.0, 1000.0, 0) is None
    assert _eff_spot_specific_bb(1000.0, 1000.0, None) is None


def test_default_3bet_for_candidate_low_bucket():
    """eff < 26 → 2.3 × opener_to_bb. Ex.: opener 2 BB, eff 20 → 4.6 BB."""
    assert _default_3bet_for_candidate(2.0, 20.0) == 4.6
    assert _default_3bet_for_candidate(2.0, 25.99) == 4.6  # boundary <26


def test_default_3bet_for_candidate_mid_bucket():
    """26 ≤ eff < 35 → 2.7 × opener_to_bb."""
    assert _default_3bet_for_candidate(2.0, 26.0) == 5.4   # boundary
    assert _default_3bet_for_candidate(2.0, 34.99) == 5.4


def test_default_3bet_for_candidate_high_bucket():
    """eff ≥ 35 → 3.0 × opener_to_bb."""
    assert _default_3bet_for_candidate(2.0, 35.0) == 6.0   # boundary
    assert _default_3bet_for_candidate(2.0, 100.0) == 6.0


def test_default_3bet_for_candidate_None_inputs_returns_None():
    assert _default_3bet_for_candidate(None, 30.0) is None
    assert _default_3bet_for_candidate(2.0, None) is None
    assert _default_3bet_for_candidate(None, None) is None


# ── _format_sizing_array — JS literal ───────────────────────────────────────

def test_format_sizing_array_ints_and_ALLIN():
    assert _format_sizing_array([2, "ALLIN"]) == "[2, ALLIN]"


def test_format_sizing_array_floats():
    assert _format_sizing_array([2.5, "ALLIN"]) == "[2.5, ALLIN]"
    # 2.0 → "2" (drop trailing zero)
    assert _format_sizing_array([2.0, "ALLIN"]) == "[2, ALLIN]"


def test_format_sizing_array_single_value():
    assert _format_sizing_array([3.5]) == "[3.5]"


# ── apply_sizings_overrides — substituição no template ─────────────────────

_CANONICAL_TEMPLATE_PATH = _os.path.join(
    _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))),
    "app", "services", "hrc_scripts", "mtt_advanced_canonical_2026.js",
)


def _read_template():
    with open(_CANONICAL_TEMPLATE_PATH, "r", encoding="utf-8") as f:
        return f.read()


def test_apply_overrides_substitutes_SIZES_OPEN_OTHERS():
    tpl = _read_template()
    out = apply_sizings_overrides(tpl, {"SIZES_OPEN_OTHERS": [2.5, "ALLIN"]})
    assert "let SIZES_OPEN_OTHERS = [2.5, ALLIN];" in out
    # Default original do template foi substituído
    assert "let SIZES_OPEN_OTHERS = [2, ALLIN];" not in out
    # 1 ocorrência apenas
    assert out.count("let SIZES_OPEN_OTHERS") == 1


def test_apply_overrides_leaves_untouched_vars_alone():
    tpl = _read_template()
    out = apply_sizings_overrides(tpl, {"SIZES_OPEN_OTHERS": [2.5, "ALLIN"]})
    # SIZES_OPEN_BU não foi tocado → fica no default do template.
    # pt29 tree-size control: default dos arrays OPEN passou a [N] sem ALLIN.
    assert "let SIZES_OPEN_BU = [2];" in out


def test_apply_overrides_handles_multiple():
    tpl = _read_template()
    out = apply_sizings_overrides(tpl, {
        "SIZES_OPEN_OTHERS": [2.5, "ALLIN"],
        "SIZES_3BET_BB_VS_OTHER": [9, "ALLIN"],
        "SIZES_POT_4BET_OOP": [0.45, "ALLIN"],
    })
    assert "let SIZES_OPEN_OTHERS = [2.5, ALLIN];" in out
    assert "let SIZES_3BET_BB_VS_OTHER = [9, ALLIN];" in out
    assert "let SIZES_POT_4BET_OOP = [0.45, ALLIN];" in out


def test_apply_overrides_unknown_var_logs_and_skips():
    tpl = _read_template()
    # Var inexistente → log warning, output igual ao input
    out = apply_sizings_overrides(tpl, {"SIZES_NONEXISTENT": [1, "ALLIN"]})
    assert out == tpl


def test_apply_overrides_substitutes_SIZES_3BET_HJ():
    """pt42b — apply_sizings_overrides substitui SIZES_3BET_HJ no template."""
    tpl = _read_template()
    out = apply_sizings_overrides(tpl, {"SIZES_3BET_HJ": [5.4, "ALLIN"]})
    assert "let SIZES_3BET_HJ = [5.4, ALLIN];" in out
    # Default original do template foi substituído
    assert "let SIZES_3BET_HJ = [6];" not in out
    # 1 ocorrência apenas
    assert out.count("let SIZES_3BET_HJ") == 1


def test_apply_overrides_substitutes_multiple_3bet_positions():
    """pt42b — apply_sizings_overrides substitui várias SIZES_3BET_<POS>
    em conjunto, sem interferência entre si."""
    tpl = _read_template()
    out = apply_sizings_overrides(tpl, {
        "SIZES_3BET_UTG1": [4.6, "ALLIN"],
        "SIZES_3BET_MP": [4.6, "ALLIN"],
        "SIZES_3BET_HJ": [5.4],
        "SIZES_3BET_CO": [5.4],
        "SIZES_3BET_BU": [6],
    })
    assert "let SIZES_3BET_UTG1 = [4.6, ALLIN];" in out
    assert "let SIZES_3BET_MP = [4.6, ALLIN];" in out
    assert "let SIZES_3BET_HJ = [5.4];" in out
    assert "let SIZES_3BET_CO = [5.4];" in out
    assert "let SIZES_3BET_BU = [6];" in out


# ── pt42c #WN-BOUNTY-NULL-IN-HRC-PIPELINE — extracção bounty WN + patch ────

import json

from app.services.queue_export import (
    WINAMAX_BOUNTY_FORMATS,
    _extract_winamax_seat_bounties,
    _format_winamax_structure_name,
    _patch_winamax_payouts_bountytype,
    compute_hero_bounty_from_hh,
)


def test_winamax_bounty_formats_constant():
    """pt42c — formatos WN com pipeline de bounty via HH (subset de
    BOUNTY_FORMATS sem mystery)."""
    assert WINAMAX_BOUNTY_FORMATS == ("pko", "super ko", "ko")
    # Mystery KO continua fora (já gated em MYSTERY_FORMATS).
    assert "mystery ko" not in WINAMAX_BOUNTY_FORMATS
    assert "mystery" not in WINAMAX_BOUNTY_FORMATS


def test_extract_winamax_seat_bounties_W_SERIES_sample():
    """W SERIES SPACE KO 6-handed: 4 seats com bounty 10€, 2 com 12€
    (pós-KO accumulator)."""
    hh = (
        "Table: '#304 - W SERIES - SPACE KO(1084517198)#0495' 6-max "
        "(real money) Seat #1 is the button\n"
        "Seat 1: oRosei- (75308, 10€ bounty)\n"
        "Seat 2: Spaks (93565, 10€ bounty)\n"
        "Seat 3: LHommePuma (256878, 12€ bounty)\n"
        "Seat 4: P0isSheEeesH (103432, 10€ bounty)\n"
        "Seat 5: wonderb0y (170188, 12€ bounty)\n"
        "Seat 6: thinvalium (122943, 10€ bounty)\n"
    )
    out = _extract_winamax_seat_bounties(hh)
    assert out == {
        "oRosei-": 10.0,
        "Spaks": 10.0,
        "LHommePuma": 12.0,
        "P0isSheEeesH": 10.0,
        "wonderb0y": 12.0,
        "thinvalium": 10.0,
    }


def test_extract_winamax_seat_bounties_LEGACY_DAY1_decimal():
    """LEGACY MILLION DAY 1 5-handed: bounties com 2 decimais pós-KO."""
    hh = (
        "Seat 1: JMaestro (461388, 68.75€ bounty)\n"
        "Seat 2: thinvalium (607387, 322.86€ bounty)\n"
        "Seat 3: RoyalKata (117958, 89.25€ bounty)\n"
        "Seat 4: Cumua Pulia (1011890, 213.25€ bounty)\n"
        "Seat 5: PurrfectCaos (881474, 234.52€ bounty)\n"
    )
    out = _extract_winamax_seat_bounties(hh)
    assert out["JMaestro"] == 68.75
    assert out["thinvalium"] == 322.86
    assert out["Cumua Pulia"] == 213.25  # nick com espaço
    assert out["PurrfectCaos"] == 234.52
    assert len(out) == 5


def test_extract_winamax_seat_bounties_no_bounty_returns_empty():
    """HH non-bounty (Vanilla) ou Seat lines sem token bounty → dict vazio."""
    hh_vanilla = (
        "Seat 1: PlayerA (10000)\n"  # WPN-like (sem 'in chips' e sem bounty)
        "Seat 2: PlayerB (12000 in chips)\n"  # PS-like sem bounty
    )
    assert _extract_winamax_seat_bounties(hh_vanilla) == {}
    assert _extract_winamax_seat_bounties("") == {}
    assert _extract_winamax_seat_bounties(None) == {}


def test_patch_winamax_payouts_bountytype_overwrites_None_to_PKO():
    """pt42c — patch sobrescreve bountyType="None" + progressiveFactor=0.0
    para PKO + 0.5 (default WN PKO 50%)."""
    blob = {
        "name": "/",
        "folders": [],
        "structures": [
            {
                "name": "GRAVITY",
                "chips": 4259922.0,
                "prizes": {"1": 4185.3, "2": 4185.17},
                "bountyType": "None",
                "progressiveFactor": 0.0,
            }
        ],
    }
    out = _patch_winamax_payouts_bountytype(blob)
    assert out["structures"][0]["bountyType"] == "PKO"
    assert out["structures"][0]["progressiveFactor"] == 0.5
    # Outros campos preservados
    assert out["structures"][0]["name"] == "GRAVITY"
    assert out["structures"][0]["chips"] == 4259922.0
    assert out["structures"][0]["prizes"] == {"1": 4185.3, "2": 4185.17}


def test_patch_winamax_payouts_bountytype_deep_copy_does_not_mutate():
    """pt42c — input não pode ser mutado (deep-copy via json round-trip)."""
    blob = {
        "structures": [
            {"bountyType": "None", "progressiveFactor": 0.0}
        ]
    }
    original = json.loads(json.dumps(blob))  # snapshot pré-patch
    _ = _patch_winamax_payouts_bountytype(blob)
    assert blob == original  # input intacto


def test_patch_winamax_payouts_bountytype_multi_structures():
    """pt42c — patch aplica-se a TODAS as structures (raríssimo ter >1,
    mas defensivo)."""
    blob = {
        "structures": [
            {"name": "A", "bountyType": "None", "progressiveFactor": 0.0},
            {"name": "B", "bountyType": "Other", "progressiveFactor": 0.25},
        ]
    }
    out = _patch_winamax_payouts_bountytype(blob)
    for s in out["structures"]:
        assert s["bountyType"] == "PKO"
        assert s["progressiveFactor"] == 0.5


def test_patch_winamax_payouts_bountytype_handles_missing_structures():
    """pt42c — defensivo: blob sem `structures` → devolve cópia sem alterar
    (não-crash)."""
    blob_no_structs = {"name": "/", "folders": []}
    out = _patch_winamax_payouts_bountytype(blob_no_structs)
    assert out == blob_no_structs

    blob_none = None
    out = _patch_winamax_payouts_bountytype(blob_none)
    assert out is None


def test_patch_winamax_payouts_with_tn_applies_name_format():
    """pt42d — com `tournament_number`, sobrescreve `structures[i].name`
    para "<Name>  #<tn>" via `_format_winamax_structure_name`."""
    blob = {
        "structures": [
            {
                "name": "GRAVITY",
                "chips": 4259922.0,
                "prizes": {"1": 4185.3},
                "bountyType": "None",
                "progressiveFactor": 0.0,
            }
        ]
    }
    out = _patch_winamax_payouts_bountytype(
        blob, tournament_number="1101080235",
    )
    assert out["structures"][0]["name"] == "GRAVITY  #1101080235"
    # bountyType + progressiveFactor continuam aplicados (pt42c)
    assert out["structures"][0]["bountyType"] == "PKO"
    assert out["structures"][0]["progressiveFactor"] == 0.5
    # Outros campos preservados
    assert out["structures"][0]["chips"] == 4259922.0
    assert out["structures"][0]["prizes"] == {"1": 4185.3}


def test_patch_winamax_payouts_without_tn_preserves_name():
    """pt42d — sem `tournament_number` (default None), name original
    preservado (compat pt42c — backward compat antes do switch ao novo
    flow em build_queue_zip)."""
    blob = {
        "structures": [
            {
                "name": "GRAVITY",
                "bountyType": "None",
                "progressiveFactor": 0.0,
            }
        ]
    }
    out = _patch_winamax_payouts_bountytype(blob)  # tn não passado
    assert out["structures"][0]["name"] == "GRAVITY"
    # bountyType + progressiveFactor ainda aplicados
    assert out["structures"][0]["bountyType"] == "PKO"
    assert out["structures"][0]["progressiveFactor"] == 0.5


def test_format_winamax_structure_name_basic():
    """pt42d — formato HRC-aceite: <Name> + 2 espaços + #<tn>."""
    out = _format_winamax_structure_name("GRAVITY", "1101080235")
    assert out == "GRAVITY  #1101080235"


def test_format_winamax_structure_name_two_spaces_not_one():
    """pt42d — 2 espaços literais (não 1) entre nome e #. Empírico do HRC."""
    out = _format_winamax_structure_name("INTERSTELLAR", "1094178268")
    # Garantir que há exactamente 2 espaços antes do #
    assert "INTERSTELLAR  #1094178268" in out
    assert "INTERSTELLAR #1094178268" not in out  # 1 espaço NÃO basta


def test_format_winamax_structure_name_missing_tn_returns_name():
    """pt42d — sem tournament_number → devolve name original (sem sufixo)."""
    assert _format_winamax_structure_name("GRAVITY", None) == "GRAVITY"
    assert _format_winamax_structure_name("GRAVITY", "") == "GRAVITY"
    assert _format_winamax_structure_name("GRAVITY", 0) == "GRAVITY"


def test_format_winamax_structure_name_None_name_returns_None():
    """pt42d — name None → None (caller decide o que fazer)."""
    assert _format_winamax_structure_name(None, "1101080235") is None
    assert _format_winamax_structure_name(None, None) is None


def test_format_winamax_structure_name_preserves_spaces_and_special_chars():
    """pt42d — tolera nomes com espaços, caracteres especiais, e numeric tn
    com underscore/letras (defensivo embora WN só tenha int tn)."""
    out = _format_winamax_structure_name("W SERIES - SPACE KO", "1084517198")
    assert out == "W SERIES - SPACE KO  #1084517198"


def test_convert_gg_hh_winamax_pko_passthrough():
    """pt42d — Winamax PKO: HRC lê HH WN nativa; converter faz passthrough
    total. Branch WN PKO de pt42c foi removido (HRC aceita formato WN
    directamente; bounty entra via patch ao payouts.json, não via reescrita
    Seat lines)."""
    hh_raw = (
        'Winamax Poker - Tournament "INTERSTELLAR" buyIn: 90€ + 10€ '
        'level: 22 - HandId: #4699459877053923331-277-1778535900 - '
        'Holdem no limit (1000/4000/8000) - 2026/05/11 21:45:00 UTC\n'
        "Table: 'INTERSTELLAR(1094178268)#002' 6-max (real money) "
        "Seat #2 is the button\n"
        "Seat 1: yousnouf75 (163754, 194.40€ bounty)\n"
        "Seat 2: imbagosu (615675, 532.70€ bounty)\n"
        "*** ANTE/BLINDS ***\n"
        "Beu_Teu posts ante 1000\n"
        "*** PRE-FLOP ***\n"
        "blueballs67 raises 8000 to 16000\n"
    )
    hand = {
        "raw": hh_raw,
        "site": "Winamax",
        "tournament_format": "PKO",
        "player_names": {"anon_map": {"Hero": "thinvalium"}, "players_list": []},
    }
    out = convert_gg_hh_to_pokerstars_compatible(hand)
    # Passthrough total — formato WN preservado, sem reescrita.
    assert out == hh_raw
    # Formato Seat original WN preservado (NÃO transformado para PS-compat).
    assert "(163754, 194.40€ bounty)" in out
    assert "in chips" not in out


def test_convert_gg_hh_winamax_vanilla_passthrough():
    """pt42c — Winamax Vanilla (non-bounty): passthrough total, sem
    transformações. Format `Vanilla` (não está em WINAMAX_BOUNTY_FORMATS)."""
    hh_raw = (
        'Winamax Poker - Tournament "NONKO TEST" buyIn: 10€ + 1€ level: 5\n'
        "Seat 1: PlayerA (10000)\n"
        "Seat 2: PlayerB (12000)\n"
        "*** PRE-FLOP ***\n"
        "PlayerA raises 200 to 300\n"
    )
    hand = {
        "raw": hh_raw,
        "site": "Winamax",
        "tournament_format": "Vanilla",
        "player_names": {},
    }
    out = convert_gg_hh_to_pokerstars_compatible(hand)
    assert out == hh_raw  # passthrough total


def test_convert_gg_hh_pokerstars_passthrough_unchanged():
    """pt42c — PokerStars passa tal qual (sem branch dedicado; HH PS já
    está em formato nativo)."""
    out = convert_gg_hh_to_pokerstars_compatible({
        "raw": _HH_PS_REAL,
        "site": "PokerStars",
        "tournament_format": "PKO",
        "player_names": {},
    })
    assert out == _HH_PS_REAL


# ── build_sizings_overrides — end-to-end ──────────────────────────────────

def test_build_sizings_overrides_GG_HJ_open_deep():
    """GG sample: HJ opens 2bb, eff stack ~141bb (>25) → SIZES_OPEN_OTHERS=[2]
    (sem ALLIN porque deep)."""
    seats = derive_seats_in_preflop_order(_HH_GG_REAL)
    eff = compute_effective_stack_bb(_HH_GG_REAL, level_bb=300)
    out = build_sizings_overrides(
        _HH_GG_REAL, level_sb=150, level_bb=300, seats=seats,
        effective_stack_bb=eff,
    )
    assert "SIZES_OPEN_OTHERS" in out
    assert out["SIZES_OPEN_OTHERS"] == [2.0]  # sem ALLIN — eff > 25
    # Nenhum 3-bet/4-bet na mão
    assert "SIZES_3BET_IP" not in out
    # pt42b — CASO B: HJ open em 5-handed → candidato IP único = BU.
    # Eff(HJ, BU) = min(42483-600, 40000)/300 = 133.33 BB > 35 → 3.0×opener.
    assert out["SIZES_3BET_BU"] == [6.0]


def test_build_sizings_overrides_PS_BU_jam_shallow():
    """PS sample: Votsarrr@BU jam to 630201 = 25.21 BB. Stack inicial 633451,
    25.34 BB. is_all_in (630201 >= 633451×0.95) → True.
    eff_at_action: min(BU_remaining=633451, max_opp_remaining=kokonakueka
    after ante+BB = 708090) = 633451 → 25.34 BB.

    pt42 universal rule: original=ALLIN, pos=BU (não-blind), eff>8 →
    `["ALLIN", 2.0]` (default 2 BB do open).
    """
    seats = derive_seats_in_preflop_order(_HH_PS_REAL)
    eff = compute_effective_stack_bb(_HH_PS_REAL, level_bb=25000)
    out = build_sizings_overrides(
        _HH_PS_REAL, level_sb=12500, level_bb=25000, seats=seats,
        effective_stack_bb=eff,
    )
    assert out["SIZES_OPEN_BU"] == [2.0, "ALLIN"]  # pt70 ordem [size, ALLIN]


def test_build_sizings_overrides_WN_squeeze_3bet():
    """WN: HJ opens 2bb + SB squeeze 3-bet 8bb. pt42 efectiva dinâmica:
    - HJ (blueballs67) opens: raiser remaining 354758, max_opp=Beu_Teu
      após ante+SB = 658845 → eff=354758/8000 ≈ 44.34 BB > 25 → opens [2.0].
    - SB (Beu_Teu) squeezes: max_opp=blueballs67 after raise = 338758,
      Beu_Teu remaining = 658845 → eff=338758/8000 ≈ 42.34 BB > 25 →
      squeeze NÃO é all-in (64000 << 663845×0.95) → [8.0].
    """
    seats = derive_seats_in_preflop_order(_HH_WN_REAL)
    eff = compute_effective_stack_bb(_HH_WN_REAL, level_bb=8000)
    out = build_sizings_overrides(
        _HH_WN_REAL, level_sb=4000, level_bb=8000, seats=seats,
        effective_stack_bb=eff,
    )
    assert out["SIZES_OPEN_OTHERS"] == [2.0]
    assert out["SIZES_3BET_SQUEEZE_SB"] == [8.0]
    # pt42b — CASO B: HJ open em 5-handed → candidatos IP = [CO, BU].
    # Eff(HJ, CO) = min(338758, 163754)/8000 = 20.47 BB < 26 → 2.3×opener + ALLIN.
    # Eff(HJ, BU) = min(338758, 615675)/8000 = 42.34 BB >= 35 → 3.0×opener.
    assert out["SIZES_3BET_CO"] == [4.6, "ALLIN"]
    assert out["SIZES_3BET_BU"] == [6.0]


def test_build_sizings_overrides_WPN_HJ_open_deep():
    """WPN sample: DAVIDSBAGOFICE@Seat7=HJ opens 1600→3200 = 2 BB. pt42
    efectiva dinâmica: raiser remaining 110968, max_opp=Jetsies after ante
    = 448265 → eff=110968/1600 ≈ 69.36 BB > 25 → opens [2.0] (sem ALLIN).
    """
    seats = derive_seats_in_preflop_order(_HH_WPN_REAL)
    eff = compute_effective_stack_bb(_HH_WPN_REAL, level_bb=1600)
    out = build_sizings_overrides(
        _HH_WPN_REAL, level_sb=800, level_bb=1600, seats=seats,
        effective_stack_bb=eff,
    )
    assert out["SIZES_OPEN_OTHERS"] == [2.0]
    # pt42b — CASO B: HJ open em 8-handed → candidatos IP = [CO, BU].
    # Eff(HJ, CO) = min(107768, 34502)/1600 = 21.56 BB < 26 → 2.3×opener + ALLIN.
    # Eff(HJ, BU) = min(107768, 448265)/1600 = 67.36 BB >= 35 → 3.0×opener.
    assert out["SIZES_3BET_CO"] == [4.6, "ALLIN"]
    assert out["SIZES_3BET_BU"] == [6.0]


def test_build_sizings_overrides_no_raises_returns_empty():
    """Walk-to-BB → dict vazio (template inalterado)."""
    hh = (
        "Hand #X: Test - Level1 (50/100) - 2026/01/01\n"
        "Table 'T' 6-max Seat #1 is the button\n"
        "Seat 1: A (10000 in chips)\n"
        "Seat 2: B (10000 in chips)\n"
        "B: posts small blind 50\n"
        "A: posts big blind 100\n"
        "*** HOLE CARDS ***\n"
        "B: folds\n"
        "*** SUMMARY ***\n"
    )
    seats = derive_seats_in_preflop_order(hh)
    out = build_sizings_overrides(hh, level_sb=50, level_bb=100, seats=seats,
                                  effective_stack_bb=100.0)
    assert out == {}


def test_build_sizings_overrides_drops_ALLIN_when_eff_at_action_above_threshold():
    """pt42 — ALLIN como 2ª opção quando `effective_stack_at_action_bb <= 25`.
    Cenário: stacks = 2500/level=100 = 25 BB (no threshold, inclusivo) vs
    stacks = 2550/100 = 25.5 BB (acima). HH sintética com UTG-open só.
    """
    hh_at_threshold = (
        "Hand #X: Test - Level1 (50/100) - 2026/01/01\n"
        "Table 'T' 5-max Seat #5 is the button\n"
        "Seat 1: A (2500 in chips)\n"
        "Seat 2: B (2500 in chips)\n"
        "Seat 3: C (2500 in chips)\n"
        "Seat 4: D (2500 in chips)\n"
        "Seat 5: E (2500 in chips)\n"
        "A: posts small blind 50\n"
        "B: posts big blind 100\n"
        "*** HOLE CARDS ***\n"
        "C: raises 100 to 200\n"
        "D: folds\nE: folds\nA: folds\nB: folds\n"
        "*** SUMMARY ***\n"
    )
    seats = derive_seats_in_preflop_order(hh_at_threshold)
    out_below = build_sizings_overrides(
        hh_at_threshold, level_sb=50, level_bb=100, seats=seats,
        effective_stack_bb=25.0,
    )
    # eff_at_action = min(2500, max(2500-50, 2500-100, 2500, 2500)) = 2450 → 24.5 BB ≤ 25.
    assert out_below["SIZES_OPEN_OTHERS"] == [2.0, "ALLIN"]

    hh_above_threshold = hh_at_threshold.replace("2500 in chips", "2600 in chips")
    seats = derive_seats_in_preflop_order(hh_above_threshold)
    out_above = build_sizings_overrides(
        hh_above_threshold, level_sb=50, level_bb=100, seats=seats,
        effective_stack_bb=26.0,
    )
    # eff_at_action = min(2600, 2600-50=2550) = 2550 → 25.5 BB > 25.
    assert out_above["SIZES_OPEN_OTHERS"] == [2.0]


def test_build_sizings_overrides_classic_3bet_uses_real_sizing_when_deep():
    """pt42 — classic 3-bet usa o sizing REAL da HH como 1ª opção (antes,
    pt25f, ignorava-o em favor do multiplier).

    BU opens 3 BB, SB 3-bets 10 BB vs BU. Stacks 10000/100 = 100 BB.
    eff_at_action no 3-bet: SB remaining 10000-50=9950, max_opp=BB 10000-100=9900.
    eff = 9900/100 = 99 BB > 25 → 3-bet sem ALLIN: `[10.0]`.
    """
    hh = (
        "Hand #X: Test - Level1 (50/100) - 2026/01/01\n"
        "Table 'T' 5-max Seat #5 is the button\n"
        "Seat 1: A (10000 in chips)\n"
        "Seat 2: B (10000 in chips)\n"
        "Seat 3: C (10000 in chips)\n"
        "Seat 4: D (10000 in chips)\n"
        "Seat 5: E (10000 in chips)\n"
        "A: posts small blind 50\n"
        "B: posts big blind 100\n"
        "*** HOLE CARDS ***\n"
        "C: folds\n"
        "D: folds\n"
        "E: raises 200 to 300\n"
        "A: raises 700 to 1000\n"
        "B: folds\n"
        "*** SUMMARY ***\n"
    )
    seats = derive_seats_in_preflop_order(hh)
    out = build_sizings_overrides(hh, level_sb=50, level_bb=100, seats=seats,
                                  effective_stack_bb=100.0)
    assert out["SIZES_OPEN_BU"] == [3.0]
    # SB 3-bets BU → bucket SIZES_3BET_SB_VS_OTHER. Sizing real (10 BB) é
    # agora a 1ª opção (não há override do multiplier nem se ignora).
    assert out["SIZES_3BET_SB_VS_OTHER"] == [10.0]


def test_build_sizings_overrides_4bet_with_ratio():
    """4-bet OOP, original NÃO ALLIN. HH sintética: SB opens, BB 3-bets,
    SB 4-bets. Stacks 10000/100 = 100 BB (deep). 4-bet sai com pot_fraction
    real (0.43) como 1ª opção; sem ALLIN como 2ª porque eff_at_action > 25.
    """
    hh = (
        "Hand #X: Test - Level1 (50/100) - 2026/01/01\n"
        "Table 'T' 5-max Seat #5 is the button\n"
        "Seat 1: A (10000 in chips)\n"
        "Seat 2: B (10000 in chips)\n"
        "Seat 3: C (10000 in chips)\n"
        "Seat 4: D (10000 in chips)\n"
        "Seat 5: E (10000 in chips)\n"
        "A: posts small blind 50\n"
        "B: posts big blind 100\n"
        "*** HOLE CARDS ***\n"
        "C: folds\n"
        "D: folds\n"
        "E: folds\n"
        "A: raises 200 to 250\n"
        "B: raises 450 to 700\n"
        "A: raises 600 to 1300\n"
        "*** SUMMARY ***\n"
    )
    seats = derive_seats_in_preflop_order(hh)
    out = build_sizings_overrides(hh, level_sb=50, level_bb=100, seats=seats,
                                  effective_stack_bb=100.0)
    # Open by SB → SIZES_OPEN_SB.
    assert out["SIZES_OPEN_SB"] == [2.5]
    # 3-bet by BB vs SB → SIZES_3BET_BB_VS_SB. Sizing real (7 BB) 1ª opção,
    # sem ALLIN (eff > 25).
    assert out["SIZES_3BET_BB_VS_SB"] == [7.0]
    # 4-bet by SB (OOP vs BB). Pot fraction 0.43 (raise_inc 600 / pot_after_call 1400).
    assert out["SIZES_POT_4BET_OOP"] == [0.43]


# ── pt42 — regra universal de sizings ────────────────────────────────────

def _hh_5max(stacks_chips: list, action_lines: str, sb: int = 50, bb: int = 100) -> str:
    """Constrói HH 5-max com `stacks_chips` (5 valores) e bloco de acções
    custom. Player A=SB, B=BB, C/D=UTG/HJ, E=BU.

    Fallback de `_init_pot_from_blinds_antes` adiciona SB/BB às contributions
    de A/B porque o bloco usa `posts small/big blind` explícito.
    """
    if len(stacks_chips) != 5:
        raise ValueError("need 5 stacks for 5-max helper")
    seat_lines = "\n".join(
        f"Seat {i+1}: {chr(ord('A')+i)} ({s} in chips)"
        for i, s in enumerate(stacks_chips)
    )
    return (
        f"Hand #X: Test - Level1 ({sb}/{bb}) - 2026/01/01\n"
        f"Table 'T' 5-max Seat #5 is the button\n"
        f"{seat_lines}\n"
        f"A: posts small blind {sb}\n"
        f"B: posts big blind {bb}\n"
        f"*** HOLE CARDS ***\n"
        f"{action_lines}"
        f"*** SUMMARY ***\n"
    )


# Universal rule — defaults por tipo de aposta ----------------------------

def test_default_for_open_returns_2bb_when_eff_above_8_non_blind():
    a = {"position": "UTG", "effective_stack_at_action_bb": 8.5}
    assert _compute_default_for_open(a) == 2.0


def test_default_for_open_returns_None_when_eff_at_threshold():
    """eff == 8 → boundary INCLUSIVO no gate `eff <= 8` → None (sem default)."""
    a = {"position": "UTG", "effective_stack_at_action_bb": 8.0}
    assert _compute_default_for_open(a) is None


def test_default_for_open_SB_uses_blind_table():
    """pt70 (LEI §18): SB usa a tabela de open da blind por eff (eff 50 BB →
    31≤eff≤100 → 3.5), já não None."""
    a = {"position": "SB", "effective_stack_at_action_bb": 50.0}
    assert _compute_default_for_open(a) == 3.5


def test_default_for_open_BB_uses_blind_table():
    """pt70 (LEI §18, assunção #1): BB sobre limpers usa a mesma tabela da SB."""
    a = {"position": "BB", "effective_stack_at_action_bb": 50.0}
    assert _compute_default_for_open(a) == 3.5


def test_default_for_open_HU_position_BU_SB_keeps_default():
    """HU label composto `BU/SB` não cai em ('SB','BB') → 2 BB aplica."""
    a = {"position": "BU/SB", "effective_stack_at_action_bb": 15.0}
    assert _compute_default_for_open(a) == 2.0


# ── pt70 (LEI do Rui §18) — tabela open blinds + 3-bet BB + B1 + ordem ────────

def test_blind_open_size_by_eff_boundaries():
    """pt70: fronteiras contínuas da tabela de open da blind."""
    assert _blind_open_size_by_eff(None) is None
    assert _blind_open_size_by_eff(8.0) is None       # <= 8 → None
    assert _blind_open_size_by_eff(8.01) == 2.5
    assert _blind_open_size_by_eff(13.73) == 2.5      # WN-…1780604663
    assert _blind_open_size_by_eff(19.99) == 2.5
    assert _blind_open_size_by_eff(20.0) == 3.0       # 20 <= eff < 31
    assert _blind_open_size_by_eff(30.99) == 3.0
    assert _blind_open_size_by_eff(31.0) == 3.5       # 31 <= eff <= 100
    assert _blind_open_size_by_eff(100.0) == 3.5      # 100 inclusivo
    assert _blind_open_size_by_eff(100.01) == 4.0     # > 100


def test_bb_3bet_default_vs_open_buckets():
    """pt70: 3-bet da BB = mult(open size) × opener_to_bb."""
    assert _bb_3bet_default_vs_open({"opener_to_bb": 2.5}) == round(2.5 * 2.1, 2)   # 5.25
    assert _bb_3bet_default_vs_open({"opener_to_bb": 3.0}) == round(3.0 * 2.5, 2)   # 7.5
    assert _bb_3bet_default_vs_open({"opener_to_bb": 3.5}) == round(3.5 * 2.7, 2)   # 9.45
    assert _bb_3bet_default_vs_open({"opener_to_bb": 4.0}) == round(4.0 * 3.3, 2)   # 13.2
    assert _bb_3bet_default_vs_open({"opener_to_bb": None}) is None


def test_eff_3bettor_vs_live_nonallin_excludes_allin_opener():
    """pt70 (B1): eff = min(stack do 3-bettor, MAIOR vivo não-all-in)/BB.
    O opener all-in é excluído pelo caller (não entra em others)."""
    # 3-bettor 5000, outro vivo 5000, BB 100 → min(5000,5000)/100 = 50.
    assert _eff_3bettor_vs_live_nonallin(5000, [5000, 3000], 100) == 50.0
    # Sem outros vivos → usa o próprio stack (HU vs all-in).
    assert _eff_3bettor_vs_live_nonallin(2000, [], 100) == 20.0
    # 3-bettor curto: min(1500, 5000)/100 = 15.
    assert _eff_3bettor_vs_live_nonallin(1500, [5000], 100) == 15.0
    assert _eff_3bettor_vs_live_nonallin(None, [5000], 100) is None


def test_array_for_raise_allin_order_is_size_first():
    """pt70: ramo all-in devolve [size, ALLIN] (não ["ALLIN", size])."""
    a = {"is_all_in": True, "to_amount_bb": 15.0,
         "effective_stack_at_action_bb": 15.0}
    assert _array_for_raise(a, 2.0) == [2.0, "ALLIN"]
    assert _array_for_raise(a, None) == ["ALLIN"]


def test_sb_allin_open_in_band_gets_size_and_allin():
    """pt70 ponto-5 (mão real WN-…1780604663, 13.73 BB): SB shove 8<eff<20 →
    [2.5, ALLIN]. Antes: ["ALLIN"] só."""
    hh = _hh_5max(
        [1373, 5000, 5000, 5000, 5000],   # SB ~13.73 BB; restantes deep
        "C: folds\nD: folds\nE: folds\nA: raises 1323 to 1373\nB: folds\n",
    )
    seats = derive_seats_in_preflop_order(hh)
    out = build_sizings_overrides(hh, level_sb=50, level_bb=100, seats=seats,
                                  effective_stack_bb=13.73)
    assert out["SIZES_OPEN_SB"] == [2.5, "ALLIN"]


def test_3bet_over_allin_open_eff_below_25_is_jam():
    """pt70 B1 (mão real GG-6041006979): 3-bet sobre open ALL-IN com eff do
    3-bettor ≤ 25 → ["ALLIN"] (já não 2.3×shove). Todos os candidatos curtos."""
    hh = (
        "Hand #X: Test - Level1 (50/100) - 2026/01/01\n"
        "Table 'T' 6-max Seat #4 is the button\n"
        "Seat 1: UTG_p (700 in chips)\n"      # UTG jam ~7 BB
        "Seat 2: HJ_p (2000 in chips)\n"      # candidatos ~20 BB → eff vs si ≤ 25
        "Seat 3: CO_p (2000 in chips)\n"
        "Seat 4: BU_p (2000 in chips)\n"
        "Seat 5: SB_p (2000 in chips)\n"
        "Seat 6: BB_p (2000 in chips)\n"
        "SB_p: posts small blind 50\n"
        "BB_p: posts big blind 100\n"
        "*** HOLE CARDS ***\n"
        "UTG_p: raises 600 to 700\n"
        "HJ_p: folds\nCO_p: folds\nBU_p: folds\nSB_p: folds\nBB_p: folds\n"
        "*** SUMMARY ***\n"
    )
    seats = derive_seats_in_preflop_order(hh)
    out = build_sizings_overrides(hh, level_sb=50, level_bb=100, seats=seats,
                                  effective_stack_bb=7.0)
    for var in ("SIZES_3BET_HJ", "SIZES_3BET_CO", "SIZES_3BET_BU"):
        assert out[var] == ["ALLIN"], (var, out.get(var))


def test_3bet_over_allin_open_eff_above_25_is_iso_size():
    """pt70 B1: 3-bet sobre open ALL-IN com eff do 3-bettor > 25 →
    [iso] = [2.5 × opener_to_bb], sem ALLIN. Candidatos deep."""
    hh = (
        "Hand #X: Test - Level1 (50/100) - 2026/01/01\n"
        "Table 'T' 6-max Seat #4 is the button\n"
        "Seat 1: UTG_p (1000 in chips)\n"     # UTG jam 10 BB → opener_to_bb=10
        "Seat 2: HJ_p (6000 in chips)\n"      # candidatos 60 BB → eff 60 > 25
        "Seat 3: CO_p (6000 in chips)\n"
        "Seat 4: BU_p (6000 in chips)\n"
        "Seat 5: SB_p (6000 in chips)\n"
        "Seat 6: BB_p (6000 in chips)\n"
        "SB_p: posts small blind 50\n"
        "BB_p: posts big blind 100\n"
        "*** HOLE CARDS ***\n"
        "UTG_p: raises 900 to 1000\n"
        "HJ_p: folds\nCO_p: folds\nBU_p: folds\nSB_p: folds\nBB_p: folds\n"
        "*** SUMMARY ***\n"
    )
    seats = derive_seats_in_preflop_order(hh)
    out = build_sizings_overrides(hh, level_sb=50, level_bb=100, seats=seats,
                                  effective_stack_bb=10.0)
    iso = round(_ISO_RAISE_OVER_ALLIN_MULT * 10.0, 2)   # 25.0
    for var in ("SIZES_3BET_HJ", "SIZES_3BET_CO", "SIZES_3BET_BU"):
        assert out[var] == [iso], (var, out.get(var))


def test_default_for_classic_3bet_high_band_x3():
    """eff >= 35 → 3.0 × opener_to_bb."""
    a = {"opener_to_bb": 2.5, "effective_stack_at_action_bb": 35.0}
    assert _compute_default_for_classic_3bet(a) == 7.5


def test_default_for_classic_3bet_mid_band_x27():
    """26 <= eff < 35 → 2.7 × opener_to_bb."""
    a = {"opener_to_bb": 2.5, "effective_stack_at_action_bb": 26.0}
    assert _compute_default_for_classic_3bet(a) == 6.75
    a2 = {"opener_to_bb": 2.5, "effective_stack_at_action_bb": 34.99}
    assert _compute_default_for_classic_3bet(a2) == 6.75


def test_default_for_classic_3bet_low_band_x23():
    """eff < 26 → 2.3 × opener_to_bb (cobre 0-25 e fronteira 25.99)."""
    a = {"opener_to_bb": 2.5, "effective_stack_at_action_bb": 25.99}
    assert _compute_default_for_classic_3bet(a) == 5.75
    a2 = {"opener_to_bb": 2.5, "effective_stack_at_action_bb": 10.0}
    assert _compute_default_for_classic_3bet(a2) == 5.75


def test_default_for_classic_3bet_returns_None_without_opener_or_eff():
    assert _compute_default_for_classic_3bet({"effective_stack_at_action_bb": 30}) is None
    assert _compute_default_for_classic_3bet({"opener_to_bb": 2.5}) is None


def test_default_for_squeeze_x3_of_opener():
    a = {"opener_to_bb": 2.5}
    assert _compute_default_for_squeeze(a) == 7.5


def test_default_for_squeeze_None_without_opener():
    assert _compute_default_for_squeeze({}) is None


def test_default_for_4bet_x23_of_previous_raise():
    a = {"previous_raise_to_bb": 8.0}
    assert _compute_default_for_4bet(a) == 18.4


def test_default_for_5bet_x22_of_previous_raise():
    a = {"previous_raise_to_bb": 18.4}
    assert _compute_default_for_5bet(a) == 40.48


# Universal rule — arrays compostos ---------------------------------------

def test_array_for_raise_original_not_allin_eff_below_25_appends_ALLIN():
    a = {
        "is_all_in": False, "to_amount_bb": 12.0,
        "effective_stack_at_action_bb": 20.0,
    }
    assert _array_for_raise(a, None) == [12.0, "ALLIN"]


def test_array_for_raise_original_not_allin_eff_above_25_drops_ALLIN():
    a = {
        "is_all_in": False, "to_amount_bb": 3.0,
        "effective_stack_at_action_bb": 50.0,
    }
    assert _array_for_raise(a, None) == [3.0]


def test_array_for_raise_original_allin_with_default_appends_default():
    a = {
        "is_all_in": True, "to_amount_bb": 15.0,
        "effective_stack_at_action_bb": 15.0,
    }
    assert _array_for_raise(a, 2.0) == [2.0, "ALLIN"]  # pt70 ordem [size, ALLIN]


def test_array_for_raise_original_allin_no_default_only_ALLIN():
    a = {
        "is_all_in": True, "to_amount_bb": 6.0,
        "effective_stack_at_action_bb": 6.0,
    }
    assert _array_for_raise(a, None) == ["ALLIN"]


def test_array_for_raise_eff_None_drops_ALLIN_as_second_option():
    """Defensivo — eff None com original NÃO ALLIN → só `[original]`."""
    a = {
        "is_all_in": False, "to_amount_bb": 2.0,
        "effective_stack_at_action_bb": None,
    }
    assert _array_for_raise(a, None) == [2.0]


# Universal rule — end-to-end (open) --------------------------------------

def test_open_allin_jam_with_eff_above_8_adds_2bb_default():
    """UTG jam (~15 BB) com efectiva ~15 BB. Original=ALLIN, eff>8, não-blind →
    `["ALLIN", 2.0]`.
    """
    hh = _hh_5max(
        [1500, 1500, 1500, 1500, 1500],  # 15 BB cada
        "C: raises 1400 to 1500\nD: folds\nE: folds\nA: folds\nB: folds\n",
    )
    seats = derive_seats_in_preflop_order(hh)
    out = build_sizings_overrides(hh, level_sb=50, level_bb=100, seats=seats,
                                  effective_stack_bb=15.0)
    # UTG (C) hrc_idx 0 → SIZES_OPEN_OTHERS.
    assert out["SIZES_OPEN_OTHERS"] == [2.0, "ALLIN"]  # pt70 ordem [size, ALLIN]


def test_open_allin_jam_with_eff_below_8_no_default():
    """UTG jam ~7 BB. Original=ALLIN, eff<=8 → só `["ALLIN"]`."""
    hh = _hh_5max(
        [700, 700, 700, 700, 700],
        "C: raises 600 to 700\nD: folds\nE: folds\nA: folds\nB: folds\n",
    )
    seats = derive_seats_in_preflop_order(hh)
    out = build_sizings_overrides(hh, level_sb=50, level_bb=100, seats=seats,
                                  effective_stack_bb=7.0)
    assert out["SIZES_OPEN_OTHERS"] == ["ALLIN"]


def test_open_allin_jam_position_SB_uses_blind_table():
    """pt70 (LEI §18): SB jam — original=ALLIN, eff 15 BB (8<eff<20) → a tabela
    de open da blind dá 2.5 BB como alternativa não-jam → [2.5, ALLIN].
    (Antes de pt70: `["ALLIN"]` só — bug "ponto 5".)"""
    hh = _hh_5max(
        [1500, 1500, 1500, 1500, 1500],
        "C: folds\nD: folds\nE: folds\nA: raises 1450 to 1500\nB: folds\n",
    )
    seats = derive_seats_in_preflop_order(hh)
    out = build_sizings_overrides(hh, level_sb=50, level_bb=100, seats=seats,
                                  effective_stack_bb=15.0)
    assert out["SIZES_OPEN_SB"] == [2.5, "ALLIN"]


# Universal rule — end-to-end (3-bet clássico) ----------------------------

def test_classic_3bet_allin_high_eff_uses_3x_opener():
    """BU opens 2.5 BB, SB jams (3-bet clássico). Stacks deep (~50 BB
    cada). eff_at_action no SB > 35 → default = 3.0 × 2.5 = 7.5 BB.
    """
    hh = _hh_5max(
        [5000, 5000, 5000, 5000, 5000],
        "C: folds\nD: folds\n"
        "E: raises 200 to 250\n"
        "A: raises 4700 to 5000\n"
        "B: folds\n",
    )
    seats = derive_seats_in_preflop_order(hh)
    out = build_sizings_overrides(hh, level_sb=50, level_bb=100, seats=seats,
                                  effective_stack_bb=50.0)
    assert out["SIZES_OPEN_BU"] == [2.5]
    # SB jam (5000 chips ≈ 5000 inicial × 0.95=4750 OK). 3-bet clássico
    # vs BU → SIZES_3BET_SB_VS_OTHER. Default = 3 × 2.5 = 7.5.
    assert out["SIZES_3BET_SB_VS_OTHER"] == [7.5, "ALLIN"]  # pt70 ordem


def test_classic_3bet_allin_mid_eff_uses_27x_opener():
    """eff bucket 26-35 → 2.7 × opener. Stacks ~30 BB."""
    hh = _hh_5max(
        [3000, 3000, 3000, 3000, 3000],
        "C: folds\nD: folds\n"
        "E: raises 200 to 250\n"
        "A: raises 2700 to 3000\n"
        "B: folds\n",
    )
    seats = derive_seats_in_preflop_order(hh)
    out = build_sizings_overrides(hh, level_sb=50, level_bb=100, seats=seats,
                                  effective_stack_bb=30.0)
    # Default = 2.7 × 2.5 = 6.75.
    assert out["SIZES_3BET_SB_VS_OTHER"] == [6.75, "ALLIN"]  # pt70 ordem


def test_classic_3bet_allin_low_eff_uses_23x_opener():
    """eff < 26 → 2.3 × opener. Stacks ~20 BB."""
    hh = _hh_5max(
        [2000, 2000, 2000, 2000, 2000],
        "C: folds\nD: folds\n"
        "E: raises 200 to 250\n"
        "A: raises 1700 to 2000\n"
        "B: folds\n",
    )
    seats = derive_seats_in_preflop_order(hh)
    out = build_sizings_overrides(hh, level_sb=50, level_bb=100, seats=seats,
                                  effective_stack_bb=20.0)
    # Default = 2.3 × 2.5 = 5.75.
    assert out["SIZES_3BET_SB_VS_OTHER"] == [5.75, "ALLIN"]  # pt70 ordem


# Universal rule — end-to-end (squeeze) -----------------------------------

def test_squeeze_allin_uses_3x_opener():
    """UTG opens 2.5 BB, HJ flats, BU squeeze-jam. eff > 8 e default = 3 × opener.

    Para o BU jammar (mesmo deep), stacks ~30 BB. Original=ALLIN.
    """
    hh = _hh_5max(
        [3000, 3000, 3000, 3000, 3000],
        "C: raises 200 to 250\n"
        "D: calls 250\n"
        "E: raises 2750 to 3000\n"
        "A: folds\nB: folds\n",
    )
    seats = derive_seats_in_preflop_order(hh)
    out = build_sizings_overrides(hh, level_sb=50, level_bb=100, seats=seats,
                                  effective_stack_bb=30.0)
    # BU squeeze (callers_before=1 → SIZES_3BET_SQUEEZE_IP). Default = 7.5.
    assert out["SIZES_3BET_SQUEEZE_IP"] == [7.5, "ALLIN"]  # pt70 ordem


def test_squeeze_non_allin_uses_real_sizing():
    """Squeeze não-jam mantém sizing real. eff>25 → sem ALLIN como 2ª."""
    hh = _hh_5max(
        [10000, 10000, 10000, 10000, 10000],
        "C: raises 200 to 250\n"
        "D: calls 250\n"
        "E: raises 750 to 1000\n"
        "A: folds\nB: folds\n",
    )
    seats = derive_seats_in_preflop_order(hh)
    out = build_sizings_overrides(hh, level_sb=50, level_bb=100, seats=seats,
                                  effective_stack_bb=100.0)
    # BU squeeze to 10 BB. Sizing real 1ª opção; sem ALLIN 2ª (deep).
    assert out["SIZES_3BET_SQUEEZE_IP"] == [10.0]


# Universal rule — end-to-end (4-bet / 5-bet em pot fraction) -------------

def test_4bet_allin_writes_pot_fraction_of_2_3x_3bet():
    """SB opens 2.5 BB, BB 3-bets 7 BB, SB 4-bet-jams ~30 BB. Original=ALLIN.

    Esperado (cálculo do default em pot fraction):
      previous_raise_to_bb (3-bet) = 7.0 → bb_default = 16.1 BB = 1610 chips.
      Pot antes da 4-bet: 250 (SB) + 700 (BB) = 950.
      Call necessário pelo SB: 700-250 = 450.
      pot_after_call no 4-bet = 950 + 450 = 1400 chips.
      raise_inc target = 1610 - 700 = 910. fraction = 910 / 1400 = 0.65.
    """
    hh = _hh_5max(
        [3000, 3000, 3000, 3000, 3000],
        "C: folds\nD: folds\nE: folds\n"
        "A: raises 200 to 250\n"
        "B: raises 450 to 700\n"
        "A: raises 2300 to 3000\n",
    )
    seats = derive_seats_in_preflop_order(hh)
    out = build_sizings_overrides(hh, level_sb=50, level_bb=100, seats=seats,
                                  effective_stack_bb=30.0)
    assert out["SIZES_POT_4BET_OOP"] == [0.65, "ALLIN"]  # pt70 ordem


def test_5bet_allin_writes_pot_fraction_of_2_2x_4bet():
    """Cadeia open-3bet-4bet-5bet-jam. Stacks fundos suficientes (~70 BB)
    para o 5-bet-jam não ser ALLIN logo no 4-bet.

    Open SB 2.5 BB, 3-bet BB 7 BB, 4-bet SB 16 BB, 5-bet BB ALLIN 70 BB.
    previous_raise_to_bb (4-bet) = 16.0 → bb_default 5-bet = 35.2.
    """
    hh = _hh_5max(
        [7000, 7000, 7000, 7000, 7000],
        "C: folds\nD: folds\nE: folds\n"
        "A: raises 200 to 250\n"
        "B: raises 450 to 700\n"
        "A: raises 900 to 1600\n"
        "B: raises 5400 to 7000\n",
    )
    seats = derive_seats_in_preflop_order(hh)
    out = build_sizings_overrides(hh, level_sb=50, level_bb=100, seats=seats,
                                  effective_stack_bb=70.0)
    # BB 5-bet ALLIN. IP/OOP: BB postflop rank=1, SB=0 → BB IP relativo a SB.
    # pt70 ordem [size, ALLIN]: size (pot fraction) primeiro, ALLIN segundo.
    assert isinstance(out["SIZES_POT_5BET_IP"][0], float)
    assert out["SIZES_POT_5BET_IP"][1] == "ALLIN"


# Efectiva dinâmica por raise ---------------------------------------------

def test_effective_stack_recalculated_per_action():
    """Cenário multi-seat com efectivas diferentes em opens vs 3-bets.

    Stacks: UTG=13 BB / HJ=35 / BU=46 / SB=16 / BB=23 (todos em BB×100).
    UTG opens 2.5 BB (1300/100). Não é all-in (250 << 1300×0.95).
    eff_at_action UTG = min(1300, max(35-, 46-, 16-50, 23-100)=4500)
                      = 1300 chips → 13 BB.
    → Open com eff<=25 → [2.5, "ALLIN"].

    SB 3-bets (1550 to 1600 chips, ALLIN). previous_raise=2.5 BB.
    eff_at_action SB = min(SB_remaining=1600-50=1550,
                            max_opp_remaining=max(UTG=1300-250=1050,
                                                  HJ=3500, BU=4600, BB=2200))
                     = min(1550, 4600) = 1550 → 15.5 BB.
    is_all_in: 1600 >= 1600×0.95 → True. eff>8, pos SB → sem default.
    → ["ALLIN"].
    """
    hh = _hh_5max(
        [1600, 2300, 1300, 3500, 4600],  # A=SB=16, B=BB=23, C=UTG=13, D=HJ=35, E=BU=46
        "C: raises 150 to 250\n"
        "D: folds\nE: folds\n"
        "A: raises 1350 to 1600\n"
        "B: folds\n",
    )
    seats = derive_seats_in_preflop_order(hh)
    actions = _parse_preflop_actions(hh, seats, level_sb=50, level_bb=100)
    assert len(actions) == 2
    open_a, threebet_a = actions[0], actions[1]
    # UTG open: eff_at_action determinada por UTG's stack (13 BB), depth.
    assert open_a["effective_stack_at_action_bb"] == 13.0
    # SB 3-bet: SB's remaining = 1550, max_opp=BU 4600 → eff=15.5.
    assert threebet_a["effective_stack_at_action_bb"] == 15.5
    assert threebet_a["is_all_in"] is True
    assert open_a["is_all_in"] is False


def test_previous_raise_to_bb_and_opener_to_bb_chain():
    """Cadeia open → 3-bet → 4-bet popula previous_raise_to_bb correctamente."""
    hh = _hh_5max(
        [10000, 10000, 10000, 10000, 10000],
        "C: folds\nD: folds\nE: folds\n"
        "A: raises 200 to 250\n"
        "B: raises 450 to 700\n"
        "A: raises 600 to 1300\n",
    )
    seats = derive_seats_in_preflop_order(hh)
    actions = _parse_preflop_actions(hh, seats, level_sb=50, level_bb=100)
    assert len(actions) == 3
    open_a, threebet_a, fourbet_a = actions
    # Open — sem previous (raise anterior é a BB implícita).
    assert open_a["previous_raise_to_bb"] is None
    assert open_a["opener_to_bb"] is None
    # 3-bet — previous = open's to_bb.
    assert threebet_a["previous_raise_to_bb"] == 2.5
    assert threebet_a["opener_to_bb"] == 2.5
    # 4-bet — previous = 3-bet's to_bb.
    assert fourbet_a["previous_raise_to_bb"] == 7.0
    assert fourbet_a["opener_to_bb"] == 2.5


# Edge cases (Q6 da investigação pt42) ------------------------------------

def test_edge_case_seats_below_2_returns_empty():
    """E1: HH com <2 seats → overrides vazios (parser não consegue trabalhar)."""
    hh = (
        "Hand #X: Test - Level1 (50/100) - 2026/01/01\n"
        "Table 'T' 6-max Seat #1 is the button\n"
        "Seat 1: A (10000 in chips)\n"
        "*** HOLE CARDS ***\n"
        "*** SUMMARY ***\n"
    )
    seats = derive_seats_in_preflop_order(hh)
    out = build_sizings_overrides(hh, level_sb=50, level_bb=100, seats=seats,
                                  effective_stack_bb=None)
    assert out == {}


def test_edge_case_to_amount_within_5pct_treated_as_allin():
    """E3: to_amount=950 com initial=1000 → 95% → is_all_in=True (threshold
    inclusivo). 949 → False.
    """
    hh_at_95 = _hh_5max(
        [1000, 1000, 1000, 1000, 1000],
        "C: raises 850 to 950\nD: folds\nE: folds\nA: folds\nB: folds\n",
    )
    seats = derive_seats_in_preflop_order(hh_at_95)
    actions = _parse_preflop_actions(hh_at_95, seats, level_sb=50, level_bb=100)
    assert actions[0]["is_all_in"] is True

    hh_below = _hh_5max(
        [1000, 1000, 1000, 1000, 1000],
        "C: raises 849 to 949\nD: folds\nE: folds\nA: folds\nB: folds\n",
    )
    seats2 = derive_seats_in_preflop_order(hh_below)
    actions2 = _parse_preflop_actions(hh_below, seats2, level_sb=50, level_bb=100)
    assert actions2[0]["is_all_in"] is False


def test_edge_case_4bet_after_squeeze_uses_previous_raise_literally():
    """E4: 4-bet sobre squeeze (não sobre 3-bet clássico). previous_raise_to_bb
    aponta para o squeeze; rule 2.3× squeeze."""
    hh = _hh_5max(
        [10000, 10000, 10000, 10000, 10000],
        "C: raises 200 to 250\n"  # UTG open 2.5
        "D: calls 250\n"           # HJ flats
        "E: raises 750 to 1000\n"  # BU squeeze 10
        "C: raises 1500 to 2500\n"  # UTG 4-bet 25
        "D: folds\nE: folds\nA: folds\nB: folds\n",
    )
    seats = derive_seats_in_preflop_order(hh)
    actions = _parse_preflop_actions(hh, seats, level_sb=50, level_bb=100)
    fourbet = actions[2]
    assert fourbet["bet_count"] == 3
    assert fourbet["previous_raise_to_bb"] == 10.0


def test_edge_case_walk_to_BB_returns_empty_overrides():
    """E10: limp-pot / walk-to-BB → overrides vazios."""
    hh = _hh_5max(
        [10000, 10000, 10000, 10000, 10000],
        "C: folds\nD: folds\nE: folds\nA: folds\n",
    )
    seats = derive_seats_in_preflop_order(hh)
    out = build_sizings_overrides(hh, level_sb=50, level_bb=100, seats=seats,
                                  effective_stack_bb=100.0)
    assert out == {}


# Template — POSTFLOP_FORCE_CHECKDOWN_AFTER cuts turn/river (T4) ----------

def test_template_postflop_force_checkdown_after_FLOP_for_all_lives():
    """pt42 — variante 'pré-flop + flop only': todos os live counts (2..9)
    têm checkdown forçado após FLOP, eliminando betting em turn/river.
    """
    tpl = _read_template()
    # Confirma o bloco existe com a chave FLOP em todos os entries.
    assert "POSTFLOP_FORCE_CHECKDOWN_AFTER" in tpl
    # Não deve haver `: RIVER` ou `: TURN` na atribuição do dict (todos FLOP).
    # Procurar dentro do bloco { ... }.
    import re as _re
    m = _re.search(
        r"POSTFLOP_FORCE_CHECKDOWN_AFTER\s*=\s*\{([^}]+)\}",
        tpl, _re.DOTALL,
    )
    assert m is not None
    block = m.group(1)
    for n in (2, 3, 4, 5, 6, 7, 8, 9):
        assert _re.search(rf"\b{n}\s*:\s*FLOP\b", block), (
            f"esperado `{n}: FLOP` no POSTFLOP_FORCE_CHECKDOWN_AFTER"
        )
    # Nenhuma chave TURN ou RIVER no dict.
    assert "TURN" not in block
    assert "RIVER" not in block


# ── pt42b — CASO A / CASO B / edge cases (3-bet IP por posição) ────────────


def test_build_sizings_overrides_caso_B_no_3bet_real():
    """pt42b — CASO B sozinho: 6-handed UTG open só (sem 3-bet real).
    Esperar SIZES_3BET_<POS> para todos os candidatos IP [HJ, CO, BU].
    Stacks 5000/BB=100 → 50 BB (bucket >=35) → 3.0×2 = 6.0 BB sem ALLIN.
    """
    hh = (
        "Hand #X: Test - Level1 (50/100) - 2026/01/01\n"
        "Table 'T' 6-max Seat #4 is the button\n"
        "Seat 1: UTG_p (5000 in chips)\n"
        "Seat 2: HJ_p (5000 in chips)\n"
        "Seat 3: CO_p (5000 in chips)\n"
        "Seat 4: BU_p (5000 in chips)\n"
        "Seat 5: SB_p (5000 in chips)\n"
        "Seat 6: BB_p (5000 in chips)\n"
        "SB_p: posts small blind 50\n"
        "BB_p: posts big blind 100\n"
        "*** HOLE CARDS ***\n"
        "UTG_p: raises 100 to 200\n"
        "HJ_p: folds\nCO_p: folds\nBU_p: folds\nSB_p: folds\nBB_p: folds\n"
        "*** SUMMARY ***\n"
    )
    seats = derive_seats_in_preflop_order(hh)
    out = build_sizings_overrides(
        hh, level_sb=50, level_bb=100, seats=seats,
        effective_stack_bb=50.0,
    )
    # Open caught — eff > 25 → só [2.0].
    assert out["SIZES_OPEN_OTHERS"] == [2.0]
    # CASO B — 3 candidatos IP, todos com eff(opener,candidate) ~= 48 BB (>=35).
    assert out["SIZES_3BET_HJ"] == [6.0]
    assert out["SIZES_3BET_CO"] == [6.0]
    assert out["SIZES_3BET_BU"] == [6.0]
    # CASO B só gera para IP — SB/BB ficam intocados.
    assert "SIZES_3BET_SB_VS_OTHER" not in out
    assert "SIZES_3BET_BB_VS_OTHER" not in out


def test_build_sizings_overrides_caso_A_overrides_caso_B_in_3bettor_position():
    """pt42b — CASO A sobrescreve CASO B. 6-handed: UTG open 2 BB + HJ 3-bet
    6 BB. Esperar:
    - SIZES_3BET_HJ = [6.0] (CASO A — sizing original da HH; eff > 25 → sem ALLIN).
    - SIZES_3BET_CO/BU = [6.0] (CASO B — bucket default, eff >=35).
    """
    hh = (
        "Hand #X: Test - Level1 (50/100) - 2026/01/01\n"
        "Table 'T' 6-max Seat #4 is the button\n"
        "Seat 1: UTG_p (5000 in chips)\n"
        "Seat 2: HJ_p (5000 in chips)\n"
        "Seat 3: CO_p (5000 in chips)\n"
        "Seat 4: BU_p (5000 in chips)\n"
        "Seat 5: SB_p (5000 in chips)\n"
        "Seat 6: BB_p (5000 in chips)\n"
        "SB_p: posts small blind 50\n"
        "BB_p: posts big blind 100\n"
        "*** HOLE CARDS ***\n"
        "UTG_p: raises 100 to 200\n"
        "HJ_p: raises 400 to 600\n"
        "CO_p: folds\nBU_p: folds\nSB_p: folds\nBB_p: folds\nUTG_p: folds\n"
        "*** SUMMARY ***\n"
    )
    seats = derive_seats_in_preflop_order(hh)
    out = build_sizings_overrides(
        hh, level_sb=50, level_bb=100, seats=seats,
        effective_stack_bb=50.0,
    )
    assert out["SIZES_OPEN_OTHERS"] == [2.0]
    # CASO A — HJ 3-betou (sizing real 6 BB; eff spot >25 → só [6.0]).
    assert out["SIZES_3BET_HJ"] == [6.0]
    # CASO B — CO/BU ficaram, bucket >=35 → 6.0 também.
    assert out["SIZES_3BET_CO"] == [6.0]
    assert out["SIZES_3BET_BU"] == [6.0]


def test_build_sizings_overrides_eff_dual_short_vs_deep():
    """pt42b — eff dual: 6-handed UTG opens 2 BB. CO tem stack short (20 BB);
    BU deep (60 BB). Esperar buckets diferentes por candidato:
    - SIZES_3BET_CO: eff(UTG, CO) = min(UTG_remaining, CO=2000)/100 = 20 BB
      < 26 → 2.3×2 = 4.6 + ALLIN.
    - SIZES_3BET_BU: eff(UTG, BU) = min(UTG_remaining=4800, BU=6000)/100 = 48
      BB >=35 → 3.0×2 = 6.0.
    """
    hh = (
        "Hand #X: Test - Level1 (50/100) - 2026/01/01\n"
        "Table 'T' 6-max Seat #4 is the button\n"
        "Seat 1: UTG_p (5000 in chips)\n"
        "Seat 2: HJ_p (5000 in chips)\n"
        "Seat 3: CO_p (2000 in chips)\n"
        "Seat 4: BU_p (6000 in chips)\n"
        "Seat 5: SB_p (5000 in chips)\n"
        "Seat 6: BB_p (5000 in chips)\n"
        "SB_p: posts small blind 50\n"
        "BB_p: posts big blind 100\n"
        "*** HOLE CARDS ***\n"
        "UTG_p: raises 100 to 200\n"
        "HJ_p: folds\nCO_p: folds\nBU_p: folds\nSB_p: folds\nBB_p: folds\n"
        "*** SUMMARY ***\n"
    )
    seats = derive_seats_in_preflop_order(hh)
    out = build_sizings_overrides(
        hh, level_sb=50, level_bb=100, seats=seats,
        effective_stack_bb=20.0,
    )
    # HJ_p stack 5000 → eff(UTG, HJ) = min(4800, 5000)/100 = 48 BB >=35.
    assert out["SIZES_3BET_HJ"] == [6.0]
    # CO short → bucket <26 → 4.6 + ALLIN.
    assert out["SIZES_3BET_CO"] == [4.6, "ALLIN"]
    # BU deep → bucket >=35 → 6.0.
    assert out["SIZES_3BET_BU"] == [6.0]


def test_build_sizings_overrides_HU_no_caso_B():
    """pt42b — HU (2-handed): labels=[BU/SB, BB]. Opener BU/SB → candidates=[].
    Esperar NENHUM SIZES_3BET_<POS> IP. (BB-3-bet vai para SIZES_3BET_BB_VS_SB
    legacy, mas neste teste não há 3-bet, logo só verifica ausência.)
    """
    hh = (
        "Hand #X: Test - Level1 (50/100) - 2026/01/01\n"
        "Table 'T' 2-max Seat #1 is the button\n"
        "Seat 1: BUSB_p (5000 in chips)\n"
        "Seat 2: BB_p (5000 in chips)\n"
        "BUSB_p: posts small blind 50\n"
        "BB_p: posts big blind 100\n"
        "*** HOLE CARDS ***\n"
        "BUSB_p: raises 150 to 200\n"
        "BB_p: folds\n"
        "*** SUMMARY ***\n"
    )
    seats = derive_seats_in_preflop_order(hh)
    out = build_sizings_overrides(
        hh, level_sb=50, level_bb=100, seats=seats,
        effective_stack_bb=50.0,
    )
    # HU não gera CASO B.
    for var in ("SIZES_3BET_EP", "SIZES_3BET_MP", "SIZES_3BET_HJ",
                "SIZES_3BET_CO", "SIZES_3BET_BU"):
        assert var not in out


def test_build_sizings_overrides_open_jam_caso_B_still_generated():
    """pt42b/pt70 — open-jam UTG ainda gera CASO B (decisão #3 do Web), mas
    com a LEI B1 (3-bet sobre open ALL-IN): o size já NÃO é 2.3×shove.
    6-handed, UTG abre ALLIN (1500/BB=100 = 15 BB → jam). Candidatos HJ/CO/BU
    têm 5000 (50 BB). eff do 3-bettor vs vivos não-all-in (exclui o opener
    all-in) = min(5000, 5000)/100 = 50 BB > 25 → iso = 2.5 × 15 = 37.5 (sem
    ALLIN, eff>25). SIZES_OPEN_OTHERS = [2.0, ALLIN] (ordem pt70).
    """
    hh = (
        "Hand #X: Test - Level1 (50/100) - 2026/01/01\n"
        "Table 'T' 6-max Seat #4 is the button\n"
        "Seat 1: UTG_p (1500 in chips)\n"
        "Seat 2: HJ_p (5000 in chips)\n"
        "Seat 3: CO_p (5000 in chips)\n"
        "Seat 4: BU_p (5000 in chips)\n"
        "Seat 5: SB_p (5000 in chips)\n"
        "Seat 6: BB_p (5000 in chips)\n"
        "SB_p: posts small blind 50\n"
        "BB_p: posts big blind 100\n"
        "*** HOLE CARDS ***\n"
        "UTG_p: raises 1400 to 1500\n"
        "HJ_p: folds\nCO_p: folds\nBU_p: folds\nSB_p: folds\nBB_p: folds\n"
        "*** SUMMARY ***\n"
    )
    seats = derive_seats_in_preflop_order(hh)
    out = build_sizings_overrides(
        hh, level_sb=50, level_bb=100, seats=seats,
        effective_stack_bb=15.0,
    )
    # Open ALLIN (1500 = 100% stack) + default 2 BB (ordem pt70 [size, ALLIN]).
    assert out["SIZES_OPEN_OTHERS"] == [2.0, "ALLIN"]
    # pt70 LEI B1: CASO B sobre open ALL-IN → iso = 2.5 × opener_to_bb(15) = 37.5
    # (eff do 3-bettor 50 BB > 25 → sem ALLIN). Já NÃO é 2.3×shove.
    assert out["SIZES_3BET_HJ"] == [37.5]
    assert out["SIZES_3BET_CO"] == [37.5]
    assert out["SIZES_3BET_BU"] == [37.5]


def test_build_sizings_overrides_3bet_squeeze_does_not_trigger_caso_A_dispatch():
    """pt42b — squeeze IP cai em SIZES_3BET_SQUEEZE_IP, NÃO em SIZES_3BET_<POS>.
    Logo CASO B gera SIZES_3BET_<POS> com bucket default mesmo na posição
    do squeezer.

    6-handed: UTG open + CO call + BU squeeze (3-bet com callers_before=1).
    """
    hh = (
        "Hand #X: Test - Level1 (50/100) - 2026/01/01\n"
        "Table 'T' 6-max Seat #4 is the button\n"
        "Seat 1: UTG_p (5000 in chips)\n"
        "Seat 2: HJ_p (5000 in chips)\n"
        "Seat 3: CO_p (5000 in chips)\n"
        "Seat 4: BU_p (5000 in chips)\n"
        "Seat 5: SB_p (5000 in chips)\n"
        "Seat 6: BB_p (5000 in chips)\n"
        "SB_p: posts small blind 50\n"
        "BB_p: posts big blind 100\n"
        "*** HOLE CARDS ***\n"
        "UTG_p: raises 100 to 200\n"
        "HJ_p: folds\n"
        "CO_p: calls 200\n"
        "BU_p: raises 600 to 800\n"
        "SB_p: folds\nBB_p: folds\nUTG_p: folds\nCO_p: folds\n"
        "*** SUMMARY ***\n"
    )
    seats = derive_seats_in_preflop_order(hh)
    out = build_sizings_overrides(
        hh, level_sb=50, level_bb=100, seats=seats,
        effective_stack_bb=50.0,
    )
    # BU foi squeezer (callers_before=1) → SIZES_3BET_SQUEEZE_IP (legacy).
    assert "SIZES_3BET_SQUEEZE_IP" in out
    # CASO B continua a gerar SIZES_3BET_HJ/CO/BU (BU NÃO recebe CASO A
    # porque foi squeeze, não 3-bet clássico) — só CASO B com bucket default.
    assert out["SIZES_3BET_HJ"] == [6.0]
    assert out["SIZES_3BET_CO"] == [6.0]
    assert out["SIZES_3BET_BU"] == [6.0]


# ── generate_hrc_script_for_hand — pipeline completo ──────────────────────

def test_generate_hrc_script_for_hand_GG_HJ_open():
    """Pipeline completo GG sample. Eff ~133 BB → opens sem ALLIN."""
    seats = derive_seats_in_preflop_order(_HH_GG_REAL)
    js, overrides, eff, err = generate_hrc_script_for_hand(
        _HH_GG_REAL, level_sb=150, level_bb=300, seats=seats,
    )
    assert err is None
    assert eff == 133.33
    assert overrides["SIZES_OPEN_OTHERS"] == [2.0]
    assert "let SIZES_OPEN_OTHERS = [2];" in js
    # Outras vars não tocadas → default do template.
    # pt29 tree-size control: default dos arrays OPEN passou a [N] sem ALLIN.
    assert "let SIZES_OPEN_BU = [2];" in js


def test_generate_hrc_script_for_hand_walk_to_BB_returns_template_intact():
    """Sem raises → template devolvido cru, overrides={}."""
    hh = (
        "Hand #X: Test - Level1 (50/100) - 2026/01/01\n"
        "Table 'T' 6-max Seat #1 is the button\n"
        "Seat 1: A (10000 in chips)\n"
        "Seat 2: B (10000 in chips)\n"
        "B: posts small blind 50\n"
        "A: posts big blind 100\n"
        "*** HOLE CARDS ***\n"
        "B: folds\n"
        "*** SUMMARY ***\n"
    )
    seats = derive_seats_in_preflop_order(hh)
    js, overrides, eff, err = generate_hrc_script_for_hand(
        hh, level_sb=50, level_bb=100, seats=seats,
    )
    assert err is None
    assert overrides == {}
    # Template default em SIZES_OPEN_OTHERS.
    # pt29 tree-size control: default dos arrays OPEN passou a [N] sem ALLIN.
    assert "let SIZES_OPEN_OTHERS = [2];" in js


def test_generate_hrc_script_for_hand_template_io_failure_returns_error():
    """Path inexistente → js=None, error populated."""
    seats = derive_seats_in_preflop_order(_HH_GG_REAL)
    js, overrides, eff, err = generate_hrc_script_for_hand(
        _HH_GG_REAL, level_sb=150, level_bb=300, seats=seats,
        template_path="/nonexistent/template.js",
    )
    assert js is None
    assert err is not None
    assert "FileNotFoundError" in err


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
    """pt42d: sem payout_blob + `include_no_payout=True` → payouts.json no
    zip é defensivo `{name, folders, structures: []}` (formato HRC-aceite).
    Hints (equity_model, max_players, script_path) vivem em meta.json
    desde pt42d (HRC rejeitava campos extra no payouts.json → ICM puro)."""
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
    assert "GG-Z/payouts.json" in names
    assert "GG-Z/meta.json" in names
    # pt42d: payouts.json sem hints — só layout HRC-aceite
    payouts = _json.loads(zf.read("GG-Z/payouts.json"))
    assert set(payouts.keys()) == {"name", "folders", "structures"}
    assert "equity_model" not in payouts
    assert "script_path" not in payouts
    # pt42d: hints em meta.json
    meta = _json.loads(zf.read("GG-Z/meta.json"))
    assert meta["equity_model"] in ("malmuth_harville_icm", "multi_table_icm")
    assert isinstance(meta["max_players"], int)
    # script_path apontará para script.js (gerado sempre em Maio 2026+)
    assert meta["script_path"] == "script.js"
    manifest = _json.loads(zf.read("manifest.json"))
    assert manifest["total_in_zip"] == 1
    assert manifest["hands_included"][0]["has_payouts"] is False


def test_build_queue_zip_hints_in_meta_not_payouts():
    """pt42d (substitui pt23 _hints_merged_with_payouts): hints saem do
    payouts.json (HRC rejeita campos extra → ICM puro) e ficam em
    meta.json. payouts.json preserva apenas o payout blob (name, folders,
    structures)."""
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
    # payout blob preservado em payouts.json
    assert payouts["structures"][0]["name"] == "Test BBG $54"
    assert payouts["structures"][0]["bountyType"] == "PKO"
    # pt42d: hints NÃO estão em payouts.json
    assert "equity_model" not in payouts
    assert "max_players" not in payouts
    assert "script_path" not in payouts
    # pt42d: hints estão em meta.json
    meta = _json.loads(zf.read("GG-HINT/meta.json"))
    assert meta["equity_model"] == "malmuth_harville_icm"
    assert isinstance(meta["max_players"], int)
    # script.js gerado sempre (Maio 2026+) — script_path relativo "script.js"
    assert meta["script_path"] == "script.js"


def test_build_queue_zip_default_equity_when_no_FT_tags():
    """pt23: sem tags FT (HM3 ou Discord), default = multi_table_icm.
    pt42d: assertion movida de payouts.json para meta.json."""
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
    meta = _json.loads(zf.read("GG-DEF/meta.json"))
    assert meta["equity_model"] == "multi_table_icm"


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


# ── Integration: script.js per-hand no zip (gerador novo Maio 2026) ────────

# HH UTG-open com 8 seats, 6 voluntários (UTG raise + 5 calls), hero=BB.
# Eff ~25 BB (stacks 10000 / BB 400). Cobre opens com ALLIN.
_HH_UTG_OPEN_8MAX = """Poker Hand #TM999: Tournament #99999, Test Tournament $100 - Level5 (200/400) - 2026/05/01 00:00:00
Table 'X' 8-max Seat #4 is the button
Seat 1: P1 (10000 in chips)
Seat 2: P2 (10000 in chips)
Seat 3: P3 (10000 in chips)
Seat 4: P4 (10000 in chips)
Seat 5: P5 (10000 in chips)
Seat 6: Hero (10000 in chips)
Seat 7: UTGopener (10000 in chips)
Seat 8: P8 (10000 in chips)
P5: posts small blind 200
Hero: posts big blind 400
*** HOLE CARDS ***
Dealt to Hero [As Kd]
UTGopener: raises 800 to 1200
P8: calls 1200
P1: calls 1200
P2: calls 1200
P3: calls 1200
P4: calls 1200
P5: folds
Hero: folds
*** SUMMARY ***
"""


def test_build_queue_zip_writes_script_js_for_hand_with_open():
    """Mão com pelo menos 1 raise preflop → script.js escrito + payouts.json
    script_path='script.js'. Manifest tem `has_script=True` e
    `script_overrides` populated."""
    hand = {
        "id": 1, "hand_id": "GG-OPEN", "site": "GGPoker",
        "tournament_number": "111",
        "raw": _HH_UTG_OPEN_8MAX,
        "player_names": {},
    }
    blob = build_queue_zip([hand], {("GGPoker", "111"): _fake_payout_blob()})
    zf = _zipfile.ZipFile(_io.BytesIO(blob))
    names = set(zf.namelist())
    assert "GG-OPEN/script.js" in names

    # pt42d: script_path movido para meta.json
    meta = _json.loads(zf.read("GG-OPEN/meta.json"))
    assert meta["script_path"] == "script.js"

    js = zf.read("GG-OPEN/script.js").decode("utf-8")
    # UTGopener é UTG (idx 0 em 8-handed) → SIZES_OPEN_OTHERS substituído.
    # Open size = 1200/400 = 3 BB. Eff stack = 10000/400 = 25 → override do
    # gerador inclui ALLIN (eff ≤ 25). ALLIN aqui vem do override, não do default.
    assert "let SIZES_OPEN_OTHERS = [3, ALLIN];" in js
    # Outras vars intactas → default do template.
    # pt29 tree-size control: default dos arrays OPEN passou a [N] sem ALLIN.
    assert "let SIZES_OPEN_BU = [2];" in js

    manifest = _json.loads(zf.read("manifest.json"))
    entry = manifest["hands_included"][0]
    assert entry["has_script"] is True
    assert entry["script_overrides"]["SIZES_OPEN_OTHERS"] == [3.0, "ALLIN"]
    assert entry["effective_stack_bb"] == 25.0
    assert entry["aggressor_position"] == 0  # UTG=0 em 8-handed (HRC docs conv)
    assert entry["aggressor_source"] == "real"  # pt36: open real → "real"
    assert entry["script_generation_error"] is None


def test_build_queue_zip_writes_script_js_for_walk_to_BB():
    """Mão sem raises (walk-to-BB) → script.js ainda é escrito com template
    intacto. Decisão: consistência > optimização. Overrides vazio."""
    hh = (
        "Hand #X: Test - Level1 (50/100) - 2026/01/01\n"
        "Table 'T' 6-max Seat #1 is the button\n"
        "Seat 1: A (10000 in chips)\n"
        "Seat 2: B (10000 in chips)\n"
        "B: posts small blind 50\n"
        "A: posts big blind 100\n"
        "*** HOLE CARDS ***\n"
        "B: folds\n"
        "*** SUMMARY ***\n"
    )
    hand = {
        "id": 1, "hand_id": "GG-WALK", "site": "GGPoker",
        "tournament_number": "111",
        "raw": hh,
        "player_names": {},
    }
    blob = build_queue_zip([hand], {("GGPoker", "111"): _fake_payout_blob()})
    zf = _zipfile.ZipFile(_io.BytesIO(blob))
    names = set(zf.namelist())
    assert "GG-WALK/script.js" in names

    js = zf.read("GG-WALK/script.js").decode("utf-8")
    # Template intacto — defaults canónicos.
    # pt29 tree-size control: default dos arrays OPEN passou a [N] sem ALLIN.
    assert "let SIZES_OPEN_OTHERS = [2];" in js

    manifest = _json.loads(zf.read("manifest.json"))
    entry = manifest["hands_included"][0]
    assert entry["has_script"] is True
    assert entry["script_overrides"] == {}
    assert entry["aggressor_position"] is None


def test_build_queue_zip_script_generation_error_on_template_io_failure(monkeypatch):
    """Força OSError no read do template → manifest captura `script_generation_error`
    e `has_script=False`."""
    from app.services import hrc_script_gen as gen
    monkeypatch.setattr(
        gen, "_HRC_TEMPLATE_PATH", "/nonexistent/path/to/template.js",
    )

    hand = {
        "id": 1, "hand_id": "GG-FAIL", "site": "GGPoker",
        "tournament_number": "111",
        "raw": _HH_UTG_OPEN_8MAX,
        "player_names": {},
    }
    blob = build_queue_zip([hand], {("GGPoker", "111"): _fake_payout_blob()})
    zf = _zipfile.ZipFile(_io.BytesIO(blob))
    names = set(zf.namelist())
    assert "GG-FAIL/script.js" not in names

    manifest = _json.loads(zf.read("manifest.json"))
    entry = manifest["hands_included"][0]
    assert entry["has_script"] is False
    assert entry["script_generation_error"] is not None
    assert "FileNotFoundError" in entry["script_generation_error"]


# ── pt42c #WN-BOUNTY-NULL-IN-HRC-PIPELINE — end-to-end build_queue_zip ────


def test_build_queue_zip_wn_pko_patches_payouts_and_audits_hero():
    """pt42c/pt42d end-to-end — WN PKO: zip ganha (a) payouts.json com
    bountyType="PKO" + progressiveFactor=0.5 + name "<Name>  #<tn>" (pt42d);
    (b) audit Hero com `hero_bounty_source="hh"`; (c) payouts.json sem
    hints top-level (pt42d); (d) hints em meta.json (pt42d)."""
    hh_raw = (
        'Winamax Poker - Tournament "INTERSTELLAR" buyIn: 90€ + 10€ '
        'level: 22 - HandId: #X-1-1 - Holdem no limit (1000/4000/8000) '
        '- 2026/05/11 21:45:00 UTC\n'
        "Table: 'INTERSTELLAR(1)#001' 6-max (real money) Seat #2 is the button\n"
        "Seat 1: yousnouf75 (163754, 194.40€ bounty)\n"
        "Seat 2: imbagosu (615675, 532.70€ bounty)\n"
        "Seat 3: Beu_Teu (663845, 311.97€ bounty)\n"
        "Seat 4: thinvalium (351657, 244.20€ bounty)\n"
        "Seat 5: blueballs67 (354758, 140€ bounty)\n"
        "*** ANTE/BLINDS ***\n"
        "Beu_Teu posts ante 1000\n"
        "*** PRE-FLOP ***\n"
        "blueballs67 raises 8000 to 16000\n"
        "yousnouf75 folds\nimbagosu folds\nBeu_Teu folds\nthinvalium folds\n"
    )
    hand = {
        "id": 1,
        "hand_id": "WN-TEST-PT42C-1",
        "site": "Winamax",
        "tournament_number": "999111",
        "tournament_format": "PKO",
        "raw": hh_raw,
        "player_names": {"anon_map": {"Hero": "thinvalium"}, "players_list": []},
    }
    # Payout blob simula o que o lobby vision escreveu (bountyType="None"
    # para nomes WN não-branded). Formato canónico com name/folders/structures
    # top-level (idêntico ao que escreve `tournament_payouts.payouts_json`).
    payout_blob = {
        "name": "/",
        "folders": [],
        "structures": [
            {
                "name": "INTERSTELLAR",
                "chips": 1000000.0,
                "prizes": {"1": 5000.0, "2": 3000.0},
                "bountyType": "None",
                "progressiveFactor": 0.0,
            }
        ]
    }
    payouts_by_key = {("Winamax", "999111"): payout_blob}

    zip_bytes = build_queue_zip([hand], payouts_by_key)

    with _zipfile.ZipFile(_io.BytesIO(zip_bytes)) as zf:
        # (a) payouts.json patched: bountyType + progressiveFactor + name#tn
        po = _json.loads(zf.read("WN-TEST-PT42C-1/payouts.json"))
        assert po["structures"][0]["bountyType"] == "PKO"
        assert po["structures"][0]["progressiveFactor"] == 0.5
        # pt42d: name com sufixo #<tn>
        assert po["structures"][0]["name"] == "INTERSTELLAR  #999111"
        # (c) pt42d: payouts.json sem hints top-level (HRC-aceite)
        assert set(po.keys()) == {"name", "folders", "structures"}
        assert "equity_model" not in po
        assert "aggressor_real_action" not in po
        # (d) pt42d: hints em meta.json
        meta = _json.loads(zf.read("WN-TEST-PT42C-1/meta.json"))
        assert "equity_model" in meta
        assert "aggressor_real_action" in meta
        # (b) manifest: hero_bounty=244.20 (HH literal) + source="hh"
        manifest = _json.loads(zf.read("manifest.json"))
        included = manifest["hands_included"]
        assert len(included) == 1
        m = included[0]
        assert m["hero_bounty"] == 244.20
        assert m["hero_bounty_source"] == "hh"
    # BD não mutada — blob original ainda tem "None"+0.0
    assert payout_blob["structures"][0]["bountyType"] == "None"
    assert payout_blob["structures"][0]["progressiveFactor"] == 0.0


def test_build_queue_zip_payouts_json_in_zip_has_only_three_keys():
    """pt42d — payouts.json no zip contém APENAS name, folders, structures.
    Hints (equity_model, max_players, script_path, aggressor_real_action)
    estão em meta.json. HRC rejeita campos extra no payouts.json (cai em
    ICM puro) — esta restrição é a essência da pt42d."""
    hand = {
        "id": 1, "hand_id": "GG-LAYOUT", "site": "GGPoker",
        "tournament_number": "111",
        "raw": _HH_UTG_OPEN_8MAX,
        "player_names": {},
    }
    blob = build_queue_zip([hand], {("GGPoker", "111"): _fake_payout_blob()})
    zf = _zipfile.ZipFile(_io.BytesIO(blob))
    payouts = _json.loads(zf.read("GG-LAYOUT/payouts.json"))
    # Layout HRC-aceite: apenas estes 3 top-level keys.
    assert set(payouts.keys()) == {"name", "folders", "structures"}
    # Hints NÃO em payouts.json
    assert "equity_model" not in payouts
    assert "max_players" not in payouts
    assert "script_path" not in payouts
    assert "aggressor_real_action" not in payouts
    # Hints estão em meta.json
    meta = _json.loads(zf.read("GG-LAYOUT/meta.json"))
    assert "equity_model" in meta
    assert "max_players" in meta
    assert "script_path" in meta
    assert "aggressor_real_action" in meta


def test_build_queue_zip_wn_vanilla_no_patch_no_audit():
    """pt42c — WN Vanilla: zip mantém payouts.json original (sem patch
    pt42c); manifest sem audit Hero; converted_format="passthrough"."""
    hh_raw = (
        'Winamax Poker - Tournament "NONKO TEST" buyIn: 10€ + 1€ level: 5\n'
        "Table: 'T(1)#001' 6-max (real money) Seat #1 is the button\n"
        "Seat 1: PlayerA (10000)\n"
        "Seat 2: PlayerB (12000)\n"
        "*** PRE-FLOP ***\n"
        "PlayerA raises 200 to 300\nPlayerB folds\n"
    )
    hand = {
        "id": 2,
        "hand_id": "WN-TEST-VANILLA-1",
        "site": "Winamax",
        "tournament_number": "888222",
        "tournament_format": "Vanilla",
        "raw": hh_raw,
        "player_names": {},
    }
    payout_blob = {
        "structures": [
            {"name": "X", "bountyType": "None", "progressiveFactor": 0.0}
        ]
    }
    payouts_by_key = {("Winamax", "888222"): payout_blob}

    zip_bytes = build_queue_zip([hand], payouts_by_key)
    with _zipfile.ZipFile(_io.BytesIO(zip_bytes)) as zf:
        manifest = _json.loads(zf.read("manifest.json"))
        included = manifest.get("hands_included", [])
        if included:
            m = included[0]
            # Sem audit (não passou em WINAMAX_BOUNTY_FORMATS)
            assert m["hero_bounty"] is None
            assert m["hero_bounty_source"] is None
            assert m["converted_format"] == "passthrough"
            # payouts.json no zip NÃO é patchado (Vanilla não tem patch)
            po = _json.loads(zf.read("WN-TEST-VANILLA-1/payouts.json"))
            assert po["structures"][0]["bountyType"] == "None"
            assert po["structures"][0]["progressiveFactor"] == 0.0
        else:
            # Skipped por outro gate (ex.: no_seats_at_table). Aceitável —
            # o pipeline pt42c não é invocado para vanilla, é o que importa.
            skipped = manifest.get("skipped", [])
            assert any(s.get("hand_id") == "WN-TEST-VANILLA-1" for s in skipped)


# ── pt36 #HRC-RUN-2-ALWAYS-DISPATCH: fallback do aggressor + skip no-seats ──

def test_build_queue_zip_fallback_root_on_walk():
    """Walk-to-BB (sem raiser) → aggressor sentinela fallback_root na raiz.
    Garante que o robot passa o gate da 2ª run mesmo sem agressão real."""
    hh = (
        "Hand #FR1: Test - Level1 (50/100) - 2026/01/01\n"
        "Table 'T' 6-max Seat #1 is the button\n"
        "Seat 1: A (10000 in chips)\n"
        "Seat 2: B (10000 in chips)\n"
        "A: posts small blind 50\n"
        "B: posts big blind 100\n"
        "*** HOLE CARDS ***\n"
        "A: folds\n"
        "*** SUMMARY ***\n"
    )
    hand = {
        "id": 1, "hand_id": "GG-FR", "site": "GGPoker",
        "tournament_number": "111", "raw": hh, "player_names": {},
    }
    blob = build_queue_zip([hand], {("GGPoker", "111"): _fake_payout_blob()})
    zf = _zipfile.ZipFile(_io.BytesIO(blob))
    # pt42d: aggressor_real_action movido para meta.json
    meta = _json.loads(zf.read("GG-FR/meta.json"))
    ara = meta["aggressor_real_action"]
    assert ara is not None
    assert ara["source"] == "fallback_root"
    assert ara["position"] == "SB"   # positions[0] em HU (2 seated): _POSITION_LABELS_BY_N[2][0]
    assert ara["size_bb"] is None
    manifest = _json.loads(zf.read("manifest.json"))
    entry = manifest["hands_included"][0]
    assert entry["aggressor_source"] == "fallback_root"
    assert entry["target_node_offset"] == 0


def test_build_queue_zip_fallback_unusable_position_bb_raise():
    """1º raiser preflop é o BB (raise sobre limps) → position "BB" não está
    na Strategy Table de opens → fallback_unusable_position na raiz."""
    hh = (
        "Hand #BB1: Test - Level1 (50/100) - 2026/01/01\n"
        "Table 'T' 6-max Seat #1 is the button\n"
        "Seat 1: BUp (10000 in chips)\n"
        "Seat 2: SBp (10000 in chips)\n"
        "Seat 3: BBp (10000 in chips)\n"
        "SBp: posts small blind 50\n"
        "BBp: posts big blind 100\n"
        "*** HOLE CARDS ***\n"
        "BUp: calls 100\n"
        "SBp: calls 50\n"
        "BBp: raises 300 to 400\n"
        "BUp: folds\n"
        "SBp: folds\n"
        "*** SUMMARY ***\n"
    )
    hand = {
        "id": 1, "hand_id": "GG-BB", "site": "GGPoker",
        "tournament_number": "111", "raw": hh, "player_names": {},
    }
    blob = build_queue_zip([hand], {("GGPoker", "111"): _fake_payout_blob()})
    zf = _zipfile.ZipFile(_io.BytesIO(blob))
    # pt42d: aggressor_real_action movido para meta.json
    meta = _json.loads(zf.read("GG-BB/meta.json"))
    ara = meta["aggressor_real_action"]
    assert ara is not None
    assert ara["source"] == "fallback_unusable_position"
    assert ara["position"] == "BTN"   # positions[0] em 3-handed: _POSITION_LABELS_BY_N[3][0]
    manifest = _json.loads(zf.read("manifest.json"))
    entry = manifest["hands_included"][0]
    assert entry["aggressor_source"] == "fallback_unusable_position"
    assert entry["target_node_offset"] == 0


def test_build_queue_zip_skips_hand_with_no_seats():
    """HH sem 'is the button' → derive_seats devolve [] →
    strategy_table_positions [] → mão skipped (não vai ao robot)."""
    hh = (
        "Hand #NS1: Test - Level1 (50/100) - 2026/01/01\n"
        "Table 'T' 6-max\n"   # sem 'Seat #N is the button'
        "Seat 1: A (10000 in chips)\n"
        "Seat 2: B (10000 in chips)\n"
        "A: posts small blind 50\n"
        "B: posts big blind 100\n"
        "*** HOLE CARDS ***\n"
        "A: folds\n"
        "*** SUMMARY ***\n"
    )
    hand = {
        "id": 1, "hand_id": "GG-NS", "site": "GGPoker",
        "tournament_number": "111", "raw": hh, "player_names": {},
    }
    blob = build_queue_zip([hand], {("GGPoker", "111"): _fake_payout_blob()})
    zf = _zipfile.ZipFile(_io.BytesIO(blob))
    names = set(zf.namelist())
    assert "GG-NS/hh.txt" not in names
    manifest = _json.loads(zf.read("manifest.json"))
    assert manifest["total_in_zip"] == 0
    assert any(
        s["hand_id"] == "GG-NS" and s["reason"] == "no_seats_at_table"
        for s in manifest["skipped"]
    )


def test_build_queue_zip_aggressor_source_real_on_open():
    """Open real (UTG) → aggressor_source 'real'; o dict mantém a estrutura
    legacy de derive_aggressor_real_action (SEM chave 'source')."""
    hand = {
        "id": 1, "hand_id": "GG-REAL", "site": "GGPoker",
        "tournament_number": "111", "raw": _HH_UTG_OPEN_8MAX, "player_names": {},
    }
    blob = build_queue_zip([hand], {("GGPoker", "111"): _fake_payout_blob()})
    zf = _zipfile.ZipFile(_io.BytesIO(blob))
    # pt42d: aggressor_real_action movido para meta.json
    meta = _json.loads(zf.read("GG-REAL/meta.json"))
    ara = meta["aggressor_real_action"]
    assert ara is not None
    assert "source" not in ara          # caso real preserva estrutura legacy
    assert ara["position"] == "UTG"
    assert ara["type"] == "raise"
    manifest = _json.loads(zf.read("manifest.json"))
    entry = manifest["hands_included"][0]
    assert entry["aggressor_source"] == "real"
    assert entry["target_node_offset"] == 0   # UTG = first-to-act → raiz


# ── pt25-revisado: _resolve_players_left via lobby_processing_log ───────────

from app.services.queue_export import _resolve_players_left


def test_resolve_players_left_inline_hand_wins():
    """Branch 1: se hand['players_left'] tem int → devolve directo, sem DB."""
    assert _resolve_players_left({"players_left": 87}, None) == 87
    # Mesmo com tournament_number presente, inline tem prioridade.
    assert _resolve_players_left(
        {"players_left": 50, "tournament_number": "ZZZ"}, None,
    ) == 50


def test_resolve_players_left_via_lobby_lookup(monkeypatch):
    """Branch 2: hand sem players_left inline → query lobby_processing_log
    por tournament_number; mock devolve row com players_left."""
    calls: list = []

    def fake_query(sql, params=None):
        calls.append((sql, params))
        return [{"players_left": 42}]

    monkeypatch.setattr("app.db.query", fake_query)

    out = _resolve_players_left({"tournament_number": "281416137"}, None)
    assert out == 42
    # Confirma que query foi disparada com o tn correcto.
    assert len(calls) == 1
    assert calls[0][1] == ("281416137",)
    assert "lobby_processing_log" in calls[0][0]
    assert "result = 'success'" in calls[0][0]
    assert "players_left IS NOT NULL" in calls[0][0]


def test_resolve_players_left_no_lobby_row(monkeypatch):
    """Branch 2 mas 0 rows → None (prune off, graceful)."""
    monkeypatch.setattr("app.db.query", lambda *a, **kw: [])
    out = _resolve_players_left({"tournament_number": "281416137"}, None)
    assert out is None


def test_resolve_players_left_no_tournament_number():
    """Sem tn → None imediato (não chega a tocar DB)."""
    assert _resolve_players_left({"hand_id": "GG-X"}, None) is None
    assert _resolve_players_left({}, None) is None
    assert _resolve_players_left(None, None) is None


def test_resolve_players_left_db_error_returns_None(monkeypatch):
    """Excepção no query (BD down, schema mismatch) → None (graceful)."""

    def raising(*a, **kw):
        raise RuntimeError("simulated DB error")

    monkeypatch.setattr("app.db.query", raising)
    out = _resolve_players_left({"tournament_number": "281416137"}, None)
    assert out is None


def test_resolve_players_left_non_int_row_returns_None(monkeypatch):
    """Row devolve coluna mas com tipo inesperado → None (defensivo)."""
    monkeypatch.setattr("app.db.query", lambda *a, **kw: [{"players_left": "not_an_int"}])
    out = _resolve_players_left({"tournament_number": "281416137"}, None)
    assert out is None


# ── pt25-revisado: lobby_vision parse passa por players_left ────────────────

from app.services.lobby_vision import parse_and_validate_lobby_json


def test_lobby_vision_parses_players_left():
    """Vision JSON com players_left int → parser preserva-o intacto."""
    raw = (
        '{"site": "GGPoker", "tournament_name": "Bounty Hunters Big Game $215",'
        ' "prizes": {"1": 100.0, "2": 50.0},'
        ' "entrants": 500, "players_left": 87, "starting_stack": 10000}'
    )
    parsed = parse_and_validate_lobby_json(raw)
    assert parsed is not None
    assert parsed["players_left"] == 87
    assert parsed["entrants"] == 500


def test_lobby_vision_players_left_optional():
    """Vision JSON sem players_left (campo omitted) → parser ainda devolve
    dict válido (field é opcional, não invalida)."""
    raw = (
        '{"site": "GGPoker", "tournament_name": "X",'
        ' "prizes": {"1": 100.0}, "entrants": 500}'
    )
    parsed = parse_and_validate_lobby_json(raw)
    assert parsed is not None
    assert parsed.get("players_left") is None


# ── pt25e #META-AGGRESSOR-REAL-ACTION ───────────────────────────────────────

from app.services.queue_export import (
    derive_aggressor_real_action,
    _extract_blinds_from_header,
)


# Cross-site real samples — reaproveita _HH_*_REAL definidos acima.

def test_aggressor_real_action_PS_sample():
    """PS-260299428000: Level XXVI (12500/25000), Votsarrr raises 605201 to
    630201 and is all-in → size_bb = 630201/25000 ≈ 25.21.

    pt25e #META-AGGRESSOR-POSITION: 6-max BU=Seat 5, 5 sentados; Votsarrr
    (Seat 5) = BTN no preflop order de 5-handed (hrc_idx=2)."""
    blinds = _extract_blinds_from_header(_HH_PS_REAL)
    assert blinds == (12500, 25000)
    out = derive_aggressor_real_action(_HH_PS_REAL, 12500, 25000)
    assert out is not None
    assert out["type"] == "raise"
    assert out["size_bb"] == round(630201 / 25000, 2)
    assert out["position"] == "BTN"


def test_aggressor_real_action_GG_sample():
    """GG-5939385803: Level3(150/300(45)), 221ebf0d raises 300 to 600 →
    size_bb = 600/300 = 2.0 (canónico UTG open 2bb).

    pt25e #META-AGGRESSOR-POSITION: 8-max BU=Seat 1, 5 sentados (Seats
    2/3/4 missing); 221ebf0d (Seat 8) = CO em 5-handed (hrc_idx=1)."""
    blinds = _extract_blinds_from_header(_HH_GG_REAL)
    assert blinds == (150, 300)
    out = derive_aggressor_real_action(_HH_GG_REAL, 150, 300)
    assert out == {"type": "raise", "size_bb": 2.0, "position": "CO"}


def test_aggressor_real_action_WN_sample_INTERSTELLAR():
    """Winamax INTERSTELLAR: Holdem no limit (1000/4000/8000) — ante/sb/bb;
    blueballs67 raises 8000 to 16000 → size_bb = 16000/8000 = 2.0.

    pt25e #META-AGGRESSOR-POSITION: 6-max BU=Seat 2, 5 sentados; blueballs67
    (Seat 5) = HJ em 5-handed (hrc_idx=0)."""
    blinds = _extract_blinds_from_header(_HH_WN_REAL)
    assert blinds == (4000, 8000)
    out = derive_aggressor_real_action(_HH_WN_REAL, 4000, 8000)
    assert out == {"type": "raise", "size_bb": 2.0, "position": "HJ"}


def test_aggressor_real_action_WPN_sample():
    """WPN: Level 4 (800.00/1600.00); DAVIDSBAGOFICE raises 1600.00 to 3200.00
    → size_bb = 3200/1600 = 2.0 (decimais WPN tolerados).

    pt25e #META-AGGRESSOR-POSITION: 8-max BU=Seat 1, 8 sentados full;
    DAVIDSBAGOFICE (Seat 7) = HJ em 8-handed (hrc_idx=3)."""
    blinds = _extract_blinds_from_header(_HH_WPN_REAL)
    assert blinds == (800, 1600)
    out = derive_aggressor_real_action(_HH_WPN_REAL, 800, 1600)
    assert out == {"type": "raise", "size_bb": 2.0, "position": "HJ"}


# Sintéticos cobrindo cenários canónicos do plano.

def test_aggressor_real_action_UTG_raise_2bb():
    """8-max UTG raise to 800 com BB=400 → 2.0bb (open canónico) + UTG."""
    hh = _hh_8max_btn4(["UTGplayer: raises 400 to 800"])
    out = derive_aggressor_real_action(hh, 200, 400)
    assert out == {"type": "raise", "size_bb": 2.0, "position": "UTG"}


def test_aggressor_real_action_raise_2_5bb():
    """UTG raise to 1000 com BB=400 → 2.5bb open."""
    hh = _hh_8max_btn4(["UTGplayer: raises 600 to 1000"])
    out = derive_aggressor_real_action(hh, 200, 400)
    assert out == {"type": "raise", "size_bb": 2.5, "position": "UTG"}


def test_aggressor_real_action_raise_3bb():
    """UTG raise to 1200 com BB=400 → 3.0bb open."""
    hh = _hh_8max_btn4(["UTGplayer: raises 800 to 1200"])
    out = derive_aggressor_real_action(hh, 200, 400)
    assert out == {"type": "raise", "size_bb": 3.0, "position": "UTG"}


def test_aggressor_real_action_all_in_shove():
    """UTG raise to 10000 and is all-in com BB=400 → 25bb shove."""
    hh = _hh_8max_btn4(["UTGplayer: raises 9600 to 10000 and is all-in"])
    out = derive_aggressor_real_action(hh, 200, 400)
    assert out == {"type": "raise", "size_bb": 25.0, "position": "UTG"}


def test_aggressor_real_action_limp_completion_returns_None():
    """Limp pot: todos foldam até SB, SB completa, BB checks — sem raise/bet
    → None (consistente com derive_real_aggressor_position)."""
    hh = _hh_8max_btn4([
        "UTGplayer: folds",
        "EPplayer: folds",
        "MPplayer: folds",
        "HJplayer: folds",
        "COplayer: folds",
        "Hero: folds",
        "SBplayer: calls 200",
        "BBplayer: checks",
    ])
    out = derive_aggressor_real_action(hh, 200, 400)
    assert out is None


# pt25e #META-AGGRESSOR-POSITION: sintéticos por N de jogadores sentados,
# cobrindo as labels de `_POSITION_LABELS_BY_N` em casos canónicos. N=8 já
# coberto pelo bloco _hh_8max_btn4 acima (UTG, HJ, ..., BU/SB labels).

def _hh_5max_btn1(preflop_actions: list[str]) -> str:
    """5-handed minimal HH: BU=Seat 1; preflop order (vocab Rui):
    HJ=Seat 4, CO=Seat 5, BTN=Seat 1, SB=Seat 2, BB=Seat 3."""
    lines = [
        "Poker Hand #TM5: Tournament #100, Test - Level5 (200/400) - 2026/05/01 00:00:00",
        "Table '5max' 6-max Seat #1 is the button",
        "Seat 1: BUplayer (10000 in chips)",
        "Seat 2: SBplayer (10000 in chips)",
        "Seat 3: BBplayer (10000 in chips)",
        "Seat 4: UTGplayer (10000 in chips)",
        "Seat 5: HJplayer (10000 in chips)",
        "SBplayer: posts small blind 200",
        "BBplayer: posts big blind 400",
        "*** HOLE CARDS ***",
        "Dealt to Hero [As Kd]",
    ]
    lines.extend(preflop_actions)
    lines.append("*** SUMMARY ***")
    return "\n".join(lines) + "\n"


def _hh_4max_btn1(preflop_actions: list[str]) -> str:
    """4-handed minimal HH: BU=Seat 1; preflop order (vocab Rui): n=4,
    first_offset=3, btn_idx=0 → hrc0=seat_list[3]=Seat 4, hrc1=Seat 1,
    hrc2=Seat 2, hrc3=Seat 3.
    Labels: CO, BTN, SB, BB → CO@Seat 4, BTN@Seat 1, SB@Seat 2, BB@Seat 3."""
    lines = [
        "Poker Hand #TM4: Tournament #100, Test - Level5 (200/400) - 2026/05/01 00:00:00",
        "Table '4max' 6-max Seat #1 is the button",
        "Seat 1: BUplayer (10000 in chips)",
        "Seat 2: SBplayer (10000 in chips)",
        "Seat 3: BBplayer (10000 in chips)",
        "Seat 4: UTGplayer (10000 in chips)",
        "SBplayer: posts small blind 200",
        "BBplayer: posts big blind 400",
        "*** HOLE CARDS ***",
        "Dealt to Hero [As Kd]",
    ]
    lines.extend(preflop_actions)
    lines.append("*** SUMMARY ***")
    return "\n".join(lines) + "\n"


def _hh_hu(preflop_actions: list[str]) -> str:
    """HU 2-handed minimal: BU=Seat 1 (BU/SB age primeiro preflop)."""
    lines = [
        "Poker Hand #TMHU: Tournament #100, Test - Level5 (200/400) - 2026/05/01 00:00:00",
        "Table 'HU' 2-max Seat #1 is the button",
        "Seat 1: SBplayer (10000 in chips)",
        "Seat 2: BBplayer (10000 in chips)",
        "SBplayer: posts small blind 200",
        "BBplayer: posts big blind 400",
        "*** HOLE CARDS ***",
        "Dealt to Hero [As Kd]",
    ]
    lines.extend(preflop_actions)
    lines.append("*** SUMMARY ***")
    return "\n".join(lines) + "\n"


def test_aggressor_real_action_5handed_UTG_open():
    """5-handed first-to-act open → position HJ (hrc_idx 0; labels
    HJ/CO/BTN/SB/BB)."""
    hh = _hh_5max_btn1(["UTGplayer: raises 400 to 800"])
    out = derive_aggressor_real_action(hh, 200, 400)
    assert out == {"type": "raise", "size_bb": 2.0, "position": "HJ"}


def test_aggressor_real_action_5handed_HJ_open():
    """5-handed first-to-act folds, second raises → position CO (hrc_idx 1)."""
    hh = _hh_5max_btn1([
        "UTGplayer: folds",
        "HJplayer: raises 400 to 800",
    ])
    out = derive_aggressor_real_action(hh, 200, 400)
    assert out == {"type": "raise", "size_bb": 2.0, "position": "CO"}


def test_aggressor_real_action_5handed_BU_open():
    """5-handed first two fold, button raises → position BTN (hrc_idx 2)."""
    hh = _hh_5max_btn1([
        "UTGplayer: folds",
        "HJplayer: folds",
        "BUplayer: raises 600 to 1000",
    ])
    out = derive_aggressor_real_action(hh, 200, 400)
    assert out == {"type": "raise", "size_bb": 2.5, "position": "BTN"}


def test_aggressor_real_action_5handed_SB_open():
    """5-handed todos foldam até SB, SB raises → position SB (hrc_idx N-2=3)."""
    hh = _hh_5max_btn1([
        "UTGplayer: folds",
        "HJplayer: folds",
        "BUplayer: folds",
        "SBplayer: raises 600 to 1000",
    ])
    out = derive_aggressor_real_action(hh, 200, 400)
    assert out == {"type": "raise", "size_bb": 2.5, "position": "SB"}


def test_aggressor_real_action_4handed_UTG_open():
    """4-handed first-to-act raises → position CO (hrc_idx 0; labels
    CO/BTN/SB/BB). Pt25d convention: first_offset=3, btn_idx=0, n=4 →
    first-to-act=seat_list[3]=Seat 4."""
    hh = _hh_4max_btn1(["UTGplayer: raises 400 to 800"])
    out = derive_aggressor_real_action(hh, 200, 400)
    assert out == {"type": "raise", "size_bb": 2.0, "position": "CO"}


def test_aggressor_real_action_4handed_BU_open():
    """4-handed first-to-act folds, button raises → position BTN (hrc_idx 1)."""
    hh = _hh_4max_btn1([
        "UTGplayer: folds",
        "BUplayer: raises 400 to 800",
    ])
    out = derive_aggressor_real_action(hh, 200, 400)
    assert out == {"type": "raise", "size_bb": 2.0, "position": "BTN"}


def test_aggressor_real_action_4handed_SB_open():
    """4-handed UTG/BU fold, SB raises → position SB (hrc_idx N-2=2)."""
    hh = _hh_4max_btn1([
        "UTGplayer: folds",
        "BUplayer: folds",
        "SBplayer: raises 600 to 1000",
    ])
    out = derive_aggressor_real_action(hh, 200, 400)
    assert out == {"type": "raise", "size_bb": 2.5, "position": "SB"}


def test_aggressor_real_action_HU_BB_3bet_after_SB_call():
    """HU SB completa (call), BB raises → position BB (hrc_idx N-1=1).
    Confirma que para HU o aggressor pode ser BB quando SB começa por
    completar."""
    hh = _hh_hu([
        "SBplayer: calls 200",
        "BBplayer: raises 800 to 1200",
    ])
    out = derive_aggressor_real_action(hh, 200, 400)
    assert out == {"type": "raise", "size_bb": 3.0, "position": "BB"}


def test_aggressor_real_action_HU_SB_raise_synthetic():
    """HU SB raise (SB/button age primeiro). Cobre o caso degenerate onde o
    label canónico em N=2 é 'SB' (_POSITION_LABELS_BY_N[2] = [SB, BB])."""
    hh = _hh_hu(["SBplayer: raises 600 to 800"])
    out = derive_aggressor_real_action(hh, 200, 400)
    assert out == {"type": "raise", "size_bb": 2.0, "position": "SB"}


def test_aggressor_real_action_HU_SB_raise():
    """HU 2-handed: SB age primeiro preflop. SB raise to 800 com BB=400
    → 2.0bb open. Position = "SB" (label canónico HU em
    `_POSITION_LABELS_BY_N[2]` = [SB, BB])."""
    hu_hh = (
        "Poker Hand #TM2: Tournament #100, Test - Level5 (200/400) - 2026/05/01 00:00:00\n"
        "Table 'HU' 2-max Seat #1 is the button\n"
        "Seat 1: SBplayer (10000 in chips)\n"
        "Seat 2: BBplayer (10000 in chips)\n"
        "SBplayer: posts small blind 200\n"
        "BBplayer: posts big blind 400\n"
        "*** HOLE CARDS ***\n"
        "Dealt to Hero [As Kd]\n"
        "SBplayer: raises 600 to 800\n"
        "*** SUMMARY ***\n"
    )
    out = derive_aggressor_real_action(hu_hh, 200, 400)
    assert out == {"type": "raise", "size_bb": 2.0, "position": "SB"}


def test_aggressor_real_action_no_preflop_marker_returns_None():
    """HH sem marker preflop (`*** HOLE CARDS ***` ou `*** PRE-FLOP ***`) →
    None (graceful, mão truncada / cancelled)."""
    truncated = "Some header\nSeat 1: X (100 in chips)\n(no hole cards section)\n"
    out = derive_aggressor_real_action(truncated, 200, 400)
    assert out is None


def test_aggressor_real_action_invalid_bb_returns_None():
    """level_bb 0 ou None → None (defensivo, evita ZeroDivisionError)."""
    hh = _hh_8max_btn4(["UTGplayer: raises 400 to 800"])
    assert derive_aggressor_real_action(hh, 200, 0) is None
    assert derive_aggressor_real_action(hh, 200, None) is None  # type: ignore[arg-type]


def test_aggressor_real_action_empty_hh_returns_None():
    """Defensivo: hh_text vazio/None → None."""
    assert derive_aggressor_real_action("", 200, 400) is None
    assert derive_aggressor_real_action(None, 200, 400) is None  # type: ignore[arg-type]


def test_extract_blinds_unknown_header_returns_None():
    """Header sem padrão reconhecível → None (caller cai em aggressor=None)."""
    assert _extract_blinds_from_header("just a plain text line") is None
    assert _extract_blinds_from_header("") is None
    assert _extract_blinds_from_header(None) is None  # type: ignore[arg-type]


# Integração build_queue_zip: aggressor_real_action no manifest + payouts.json.

def test_build_queue_zip_injects_aggressor_real_action_in_manifest_and_meta():
    """pt25e + pt42d: hand com raise preflop → manifest entry + meta.json têm
    `aggressor_real_action={type, size_bb, position}`. _HH_UTG_OPEN_8MAX usa
    Level5 (200/400) e UTGopener (Seat 7, BU=Seat 4 → UTG em 8-handed)
    raises 800 to 1200 → 3.0bb + position UTG. pt42d: campo movido de
    payouts.json para meta.json (HRC rejeitava campos extra)."""
    hand = {
        "id": 1, "hand_id": "GG-AGG", "site": "GGPoker",
        "tournament_number": "111",
        "raw": _HH_UTG_OPEN_8MAX,
        "player_names": {},
        "players_left": 200,
    }
    blob = build_queue_zip([hand], {("GGPoker", "111"): _fake_payout_blob()})
    zf = _zipfile.ZipFile(_io.BytesIO(blob))
    manifest = _json.loads(zf.read("manifest.json"))
    entry = manifest["hands_included"][0]
    expected = {"type": "raise", "size_bb": 3.0, "position": "UTG"}
    assert entry["aggressor_real_action"] == expected
    # pt42d: aggressor_real_action em meta.json (não em payouts.json)
    meta = _json.loads(zf.read("GG-AGG/meta.json"))
    assert meta["aggressor_real_action"] == expected


def test_build_queue_zip_fallback_root_for_limp_pot():
    """pt36 #HRC-RUN-2-ALWAYS-DISPATCH (substitui o antigo _None_for_limp_pot):
    limp pot (sem raise/bet preflop) → o derive devolve None, mas
    build_queue_zip aplica a sentinela fallback_root na raiz para garantir a
    2ª run. Antes (pt25e) o campo ficava None."""
    limp_hh = """Poker Hand #TM3: Tournament #100, Test - Level5 (200/400) - 2026/05/01 00:00:00
Table 'X' 8-max Seat #4 is the button
Seat 1: P1 (10000 in chips)
Seat 4: Hero (10000 in chips)
Seat 5: SBplayer (10000 in chips)
Seat 6: BBplayer (10000 in chips)
SBplayer: posts small blind 200
BBplayer: posts big blind 400
*** HOLE CARDS ***
Dealt to Hero [As Kd]
P1: folds
Hero: folds
SBplayer: calls 200
BBplayer: checks
*** SUMMARY ***
"""
    hand = {
        "id": 1, "hand_id": "GG-LIMP", "site": "GGPoker",
        "tournament_number": "111",
        "raw": limp_hh,
        "player_names": {},
        "players_left": 200,
    }
    blob = build_queue_zip([hand], {("GGPoker", "111"): _fake_payout_blob()})
    zf = _zipfile.ZipFile(_io.BytesIO(blob))
    manifest = _json.loads(zf.read("manifest.json"))
    entry = manifest["hands_included"][0]
    assert entry["aggressor_source"] == "fallback_root"
    assert entry["target_node_offset"] == 0
    ara = entry["aggressor_real_action"]
    assert ara is not None
    assert ara["source"] == "fallback_root"
    assert ara["position"] == "CO"   # positions[0] em 4 seats: _POSITION_LABELS_BY_N[4] = [CO, BTN, SB, BB]
    # pt42d: aggressor_real_action movido para meta.json
    meta = _json.loads(zf.read("GG-LIMP/meta.json"))
    assert meta["aggressor_real_action"]["source"] == "fallback_root"
