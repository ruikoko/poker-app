"""Baseline T0 (#IRE-MB) — congela o comportamento ACTUAL de `ire.py` (constante
0,25 hardcoded) ANTES do refactor da constante dinâmica (T1+).

Sem DB: `compute_ire` recebe `hand` + `tournament_meta` como dicts. Valores
capturados por execução read-only das funções actuais em 2026-05-29. Se algum
destes asserts partir num refactor futuro, é regressão no caminho 0,25 — não
alterar os números sem decisão explícita.
"""
import pytest

from app.services import ire


# ── lookup_ire_pct — células da tabela W3cray (ratio 25%) ────────────────────

def test_lookup_table_cells_exact():
    assert ire.lookup_ire_pct(1.0, 1) == 5.1
    assert ire.lookup_ire_pct(0.25, 1) == 13.0
    assert ire.lookup_ire_pct(7.0, 1) == 0.2
    assert ire.lookup_ire_pct(0.5, 2) == 13.0


def test_lookup_none_when_ko_units_nonpositive():
    assert ire.lookup_ire_pct(1.0, 0) is None
    assert ire.lookup_ire_pct(1.0, -1) is None
    assert ire.lookup_ire_pct(0.0, 1) is None


def test_lookup_offtable_high_clamps_then_falls_back_to_formula():
    # (20, 10) cai fora da tabela -> _nearest_idx clampa a rows[-1]=7.0,cols[-1]=5
    # -> célula None -> _formula_fallback(20,10) com bounty_si=10*0.25=2.5.
    assert ire.lookup_ire_pct(20.0, 10.0) == pytest.approx(2.941176, abs=1e-4)


# ── _formula_fallback — constante 0,25 hardcoded (ALVO do T1) ────────────────

def test_formula_fallback_known_points():
    # bounty_si = ko_units * 0.25 ; IRE = bounty_si/(4*stack_si+2*bounty_si)*100
    assert ire._formula_fallback(1.0, 1.0) == pytest.approx(5.555556, abs=1e-4)
    assert ire._formula_fallback(2.0, 3.0) == pytest.approx(7.894737, abs=1e-4)


def test_formula_fallback_none_on_nonpositive():
    assert ire._formula_fallback(1.0, 0.0) is None
    assert ire._formula_fallback(0.0, 1.0) is None


# ── compute_ire — caminho PKO 50/50 (GG) end-to-end ──────────────────────────

def _hand_5050(bounty_usd=12.5):
    """Mão GG PKO standard: 2 vilões frescos. #KO-CROWN-INSTANT-FIX — a coroa
    (`bounty_value_usd`) é a parte INSTANTÂNEA do bounty (metade no 50/50), logo
    num fresco coroa = buy_in_bounty/2 = 25/2 = 12.5 -> ko_units = 12.5/(25×0.5)
    = 1.0. starting_stack=20000 -> villainA stack_si=1.0 (activo), villainB 2.0
    (foldou). bounty_value_usd vive em players_list (a coroa); o apa já não
    carrega bounty (era VPIP). #BOUNTY-PCT-VPIP-FIX."""
    return {
        "site": "GGPoker",
        "tournament_format": "PKO",
        "hm3_tags": ["ICM", "pko"],
        "discord_tags": None,
        "player_names": {"match_method": "anchor_stack", "players_list": [
            {"name": "villainA", "bounty_value_usd": bounty_usd},
            {"name": "villainB", "bounty_value_usd": bounty_usd},
        ]},
        "all_players_actions": {
            "_meta": {"bb": 1000},
            "Hero":     {"is_hero": True, "stack": 30000, "position": "BTN",
                         "actions": {"preflop": ["Raise 2000"]}},
            "villainA": {"stack": 20000, "position": "CO",
                         "actions": {"preflop": ["Call 2000"]}},
            "villainB": {"stack": 40000, "position": "SB",
                         "actions": {"preflop": ["Fold"]}},
        },
    }


def _meta(name="Bounty Hunters $88", stack=20000, buy_in_bounty=25):
    return {"tournament_name": name, "starting_stack": stack,
            "buy_in_bounty": buy_in_bounty}


def test_compute_ire_5050_main_villain():
    out = ire.compute_ire(_hand_5050(), _meta())
    assert out is not None
    mv = out["main_villain"]
    assert mv["nick"] == "villainA"
    assert mv["stack_si"] == 1.0
    assert mv["ko_units"] == 1.0
    assert mv["ire_pct"] == 5.1          # tabela [1.0][1]
    assert mv["is_covered"] is True


def test_compute_ire_5050_per_opponent_order_and_foldado():
    out = ire.compute_ire(_hand_5050(), _meta())
    per = out["per_opponent"]
    assert [p["nick"] for p in per] == ["villainA", "villainB"]  # CO antes de SB
    folded = per[1]
    assert folded["nick"] == "villainB"
    assert folded["is_active"] is False      # foldou
    assert folded["ire_pct"] == 2.6          # ire_pct calculado mesmo foldado (stack_si=2.0)
    assert folded["is_main"] is False


# ── compute_ire — gates que devolvem None (esconder IRE) ─────────────────────

def test_gate_super_ko_hidden():
    assert ire.compute_ire(_hand_5050(), _meta(name="Super KO Daily $50")) is None


def test_gate_non_allowed_format_hidden():
    h = _hand_5050()
    h["tournament_format"] = "Vanilla"
    assert ire.compute_ire(h, _meta()) is None


def test_gate_non_gg_site_hidden():
    h = _hand_5050()
    h["site"] = "PokerStars"
    assert ire.compute_ire(h, _meta()) is None


def test_gate_no_ko_tag_hidden():
    h = _hand_5050()
    h["hm3_tags"] = ["ICM"]
    h["discord_tags"] = ["nota"]
    assert ire.compute_ire(h, _meta()) is None


def test_gate_placeholder_match_method_hidden():
    h = _hand_5050()
    h["player_names"] = {"match_method": "discord_placeholder_tm"}
    assert ire.compute_ire(h, _meta()) is None


def test_gate_no_starting_stack_hidden():
    assert ire.compute_ire(_hand_5050(), {"tournament_name": "X", "starting_stack": 0}) is None
    assert ire.compute_ire(_hand_5050(), None) is None


def test_gate_no_opponent_bounty_hidden():
    # Sem coroa ($0) em nenhum vilão -> ko_units=0 -> escondido.
    assert ire.compute_ire(_hand_5050(bounty_usd=0), _meta()) is None


def test_gate_no_buy_in_bounty_hidden():
    # Sem buy_in_bounty (TS) não há base p/ converter $ -> KO_inicial -> escondido.
    assert ire.compute_ire(_hand_5050(), _meta(buy_in_bounty=None)) is None
    assert ire.compute_ire(_hand_5050(), _meta(buy_in_bounty=0)) is None


# ── #BOUNTY-PCT-VPIP-FIX pacote IRE: tag speed-racer + 1→N ───────────────────

def test_has_ko_tag_accepts_speed_racer():
    """Família speed-racer conta como tag de estudo PKO (sem "ko")."""
    assert ire._has_ko_tag(["ICM"], ["speed-racer"]) is True
    assert ire._has_ko_tag(["ICM"], ["speed-racer-ft"]) is True
    assert ire._has_ko_tag(["speed racer"], None) is True      # já normalizado
    assert ire._has_ko_tag(["icm-pko"], None) is True          # ainda apanha "ko"
    assert ire._has_ko_tag(["ICM"], ["nota"]) is False         # nem ko nem speed-racer


def test_gate_speed_racer_tag_accepted():
    """Mão PKO com tag speed-racer (sem "ko") passa o gate da tag e mostra IRE."""
    h = _hand_5050()
    h["hm3_tags"] = ["ICM"]; h["discord_tags"] = ["speed-racer"]
    assert ire.compute_ire(h, _meta()) is not None
    h["discord_tags"] = ["speed-racer-ft"]
    assert ire.compute_ire(h, _meta()) is not None


def test_compute_ire_1toN_folded_only_crown_shows_headline():
    """1→N: se o único oponente com coroa foldou, o IRE já NÃO esconde — calcula
    per-opponent e o main_villain é o headline (maior ire_pct, foldado incluído)."""
    h = _hand_5050()
    # villainA passa a foldar também -> ambos os vilões com coroa foldaram.
    h["all_players_actions"]["villainA"]["actions"] = {"preflop": ["Fold"]}
    out = ire.compute_ire(h, _meta())
    assert out is not None
    # headline = villainA (stack_si 1.0 -> ire_pct 5.1 > villainB 2.6).
    assert out["main_villain"] is not None
    assert out["main_villain"]["nick"] == "villainA"
    # per_opponent inclui ambos com ire_pct calculado (foldados incluídos).
    assert {op["nick"] for op in out["per_opponent"]} == {"villainA", "villainB"}
    assert all(op["ire_pct"] is not None for op in out["per_opponent"])


# ── T2: derive_kop_fraction / derive_constant (helpers puros) ────────────────

def test_kop_fraction_gg_big_bounty():
    # $525 Big Bounty: PP=150, rake=25, KOP=350 -> 350/(150+350)=0.70
    assert ire.derive_kop_fraction("GGPoker", buy_in_entry=150, buy_in_bounty=350) \
        == pytest.approx(0.70, abs=1e-9)


def test_constant_gg_big_bounty_is_035():
    assert ire.derive_constant("GGPoker", buy_in_entry=150, buy_in_bounty=350) \
        == pytest.approx(0.35, abs=1e-9)


def test_kop_fraction_gg_none_without_bounty():
    assert ire.derive_kop_fraction("GGPoker", buy_in_entry=80, buy_in_bounty=None) is None
    assert ire.derive_kop_fraction("GGPoker", buy_in_entry=80, buy_in_bounty=0) is None


def test_kop_fraction_winamax_wpn_none():
    assert ire.derive_kop_fraction("Winamax", buy_in_bounty=20) is None
    assert ire.derive_kop_fraction("WPN", buy_in_bounty=20) is None


def test_kop_fraction_ps_5050_from_header():
    raw = "PokerStars Hand #123: ... €22.50+€22.50+€5.00 EUR ...\nSeat 1: x (1000 in chips)"
    assert ire.derive_kop_fraction("PokerStars", raw_hh=raw) == pytest.approx(0.5, abs=1e-9)


def test_kop_fraction_ps_superko_bounty_gt_prize():
    # B>A (KOP>PP): header $10+$40+$5 -> 40/50 = 0.8. Função agnóstica ao gate.
    raw = "PokerStars Hand #9: ... $10+$40+$5 USD ..."
    assert ire.derive_kop_fraction("PokerStars", raw_hh=raw) == pytest.approx(0.8, abs=1e-9)


def test_constant_defaults_to_025_when_kop_none():
    assert ire.derive_constant("Winamax", buy_in_bounty=20) == 0.25
    assert ire.derive_constant("GGPoker") == 0.25
    assert ire.derive_constant(None) == 0.25


def test_compute_ire_t3_activation_big_bounty():
    """T3 wiring: tournament_meta com buy_in_entry/buy_in_bounty do TS
    deve propagar para constant=0.35 e usar a fórmula (não a tabela 0.25)."""
    hand = _hand_5050(bounty_usd=175)   # coroa = metade do bounty inicial (fresco) -> ko_units=1.0
    meta = {
        "tournament_name": "Big Bounty Hunters $525",
        "starting_stack": 20000,
        "buy_in_entry": 150,
        "buy_in_bounty": 350,
    }
    out = ire.compute_ire(hand, meta)
    assert out is not None
    mv = out["main_villain"]
    # constant = 350/(150+350) * 0.5 = 0.35 ; bounty_si = 1.0 * 0.35 = 0.35
    # IRE bruto = 0.35 / (4 + 0.7) * 100 = 7.446808... ; armazenado a 1 casa -> 7.4
    assert ire._formula_fallback(1.0, 1.0, 0.35) == pytest.approx(7.446808, abs=1e-4)
    assert mv["ire_pct"] == pytest.approx(7.4, abs=0.05)   # valor armazenado (round 1 casa)
    # Sanity: diferente de 5.1 (PKO standard via tabela) -> wiring vivo
    assert mv["ire_pct"] != 5.1


def test_compute_ire_mystery_ko_stays_legacy_025():
    """T5: Mystery KO NÃO usa a constante derivada (bounty aleatório). Mesmo com
    split 33/67 no TS, mantém-se em 0.25 -> tabela -> 5.1 (legacy, não 7.1)."""
    # #KO-CROWN-INSTANT-FIX: Mystery KO tem instant_fraction=1.0 (não-progressivo,
    # bounty inteiro pago) -> coroa = bounty inicial completo = 30 -> ko_units=1.0
    # (NÃO dividido por 0.5; o guard mantém o cálculo legacy coroa/bib no Mystery).
    hand = _hand_5050(bounty_usd=30)   # coroa = bounty inicial (Mystery: instant=1.0)
    hand["tournament_format"] = "Mystery KO"
    meta = {"tournament_name": "Sunday Mystery", "starting_stack": 20000,
            "buy_in_entry": 15, "buy_in_bounty": 30}   # 30/(15+30)=0.667 -> seria 0.333
    out = ire.compute_ire(hand, meta)
    assert out["main_villain"]["ire_pct"] == 5.1   # legacy, derivação NÃO aplicada


# ── #KO-CROWN-INSTANT-FIX — regressão: coroa = parte instantânea (metade) ─────

def test_ire_fresh_pko_kounits_one_canonical_forty_stack():
    """REGRESSÃO da guarda: Forty Stack $44 (PKO 50/50), vilão FRESCO. A coroa
    lida pela Vision é $10 (parte instantânea = metade do bounty total $20). O
    bug antigo fazia ko_units = coroa/bib = 10/20 = 0.5 (fresco subestimado 2×);
    o fix recupera ko_units = coroa/(bib×0.5) = 10/10 = 1.0 / ko_pct = 100."""
    hand = _hand_5050(bounty_usd=10)   # coroa $10 = parte instantânea
    meta = _meta(name="Bounty Hunters Forty Stack $44", buy_in_bounty=20)  # bounty total $20
    out = ire.compute_ire(hand, meta)
    assert out is not None
    mv = out["main_villain"]
    assert mv["ko_units"] == 1.0   # era 0.5 (10/20) antes do fix
    assert mv["ko_pct"] == 100     # era 50 antes do fix


def test_ire_mystery_ko_crown_not_halved_guard():
    """REGRESSÃO da guarda: no Mystery KO a coroa NÃO é dividida por
    instant_fraction (bounty inteiro, instant=1.0). Com coroa = bib = 20,
    ko_units fica 1.0 (e não 2.0 como ficaria se a lógica PKO escapasse)."""
    hand = _hand_5050(bounty_usd=20)
    hand["tournament_format"] = "Mystery KO"
    meta = _meta(name="Sunday Mystery", buy_in_bounty=20)
    out = ire.compute_ire(hand, meta)
    assert out is not None
    assert out["main_villain"]["ko_units"] == 1.0   # NÃO 2.0 → guard Mystery intacto


# ── T6: fórmula com constants diferentes, decisão (a), edge cases ────────────

def test_formula_monotonic_in_constant():
    """IRE cresce monotonicamente com a constante (mais bounty pool -> mais
    equity reduction), para (stack_si, ko_units) fixos."""
    a = ire._formula_fallback(1.0, 1.0, 0.10)
    b = ire._formula_fallback(1.0, 1.0, 0.25)
    c = ire._formula_fallback(1.0, 1.0, 0.50)
    assert a < b < c
    assert (a, b, c) == pytest.approx((2.380952, 5.555556, 10.0), abs=1e-4)


def test_lookup_nonstandard_constant_bypasses_table():
    """Decisão (a): numa célula que EXISTE na tabela (1.0,1 -> 5.1), uma constante
    fora da banda usa a fórmula, não a tabela."""
    assert ire.lookup_ire_pct(1.0, 1, 0.35) == pytest.approx(7.446808, abs=1e-4)
    assert ire.lookup_ire_pct(1.0, 1, 0.35) != 5.1


def test_lookup_inside_band_uses_table():
    """Constante dentro da banda ±0.01 (ruído do rake) usa a tabela calibrada."""
    assert ire.lookup_ire_pct(1.0, 1, 0.255) == 5.1
    assert ire.lookup_ire_pct(1.0, 1, 0.25) == 5.1


def test_ps_header_edge_cases_none():
    """PS header não parseável -> None (cai no default 0.25 no caller)."""
    assert ire._kop_from_ps_header("sem montantes aqui") is None
    assert ire._kop_from_ps_header("buy-in $10+$5 (so 2 componentes)") is None
    assert ire._kop_from_ps_header("") is None
    assert ire._kop_from_ps_header(None) is None


def test_kop_from_parts_pure_bounty_edge():
    """entry=0 (toda a contribuição vai para o bounty pool) -> KOP_fraction=1.0."""
    assert ire._kop_from_parts(0, 50) == pytest.approx(1.0, abs=1e-9)


def test_derive_kop_fraction_unknown_site_none():
    """Site não reconhecido -> None -> default 0.25 no caller."""
    assert ire.derive_kop_fraction("888poker", buy_in_bounty=10) is None
    assert ire.derive_kop_fraction("", buy_in_bounty=10) is None


def test_compute_ire_ps_dormant_despite_valid_header():
    """O ramo PS de derive_kop_fraction existe e é testado, mas compute_ire está
    gated a GGPoker -> uma mão PS com header válido continua escondida (None).
    Documenta que o ramo PS está DORMANTE até o gate de site ser relaxado."""
    hand = _hand_5050()
    hand["site"] = "PokerStars"
    hand["raw"] = "PokerStars Hand #1: ... €22.50+€22.50+€5.00 EUR ..."
    assert ire.compute_ire(hand, _meta()) is None


# ── #IRE-WN — Winamax (tabela curada + bounty literal da HH) ─────────────────

def _hand_wn(name="EXPLORER", villain_bounty="25", villain_stack=20000, fmt="PKO"):
    """WN PKO: 2 vilões + Hero (nick real, is_hero). Bounty literal na HH (TOTAL
    na cabeça). EXPLORER: entry 20 / bounty 25 / stack 20000."""
    return {
        "site": "Winamax",
        "tournament_format": fmt,
        "tournament_name": name,
        "player_names": {},   # WN: vazio, sem match_method
        "raw": (
            'Winamax Poker - Tournament "%s" buyIn: 20€ + 5€ - HandId: #x\n'
            "Seat 1: villainA (%s, %s€ bounty)\n"
            "Seat 2: villainB (18000, 25€ bounty)\n"
            "Seat 3: thinvalium (30000, 25€ bounty)\n"
            "*** ANTE/BLINDS ***\n"
        ) % (name, villain_stack, villain_bounty),
        "all_players_actions": {
            "_meta": {"bb": 200},
            "thinvalium": {"is_hero": True, "stack": 30000, "position": "BTN",
                           "actions": {"preflop": ["Raise 400"]}},
            "villainA": {"stack": villain_stack, "position": "CO",
                         "actions": {"preflop": ["Call 400"]}},
            "villainB": {"stack": 18000, "position": "SB",
                         "actions": {"preflop": ["Fold"]}},
        },
    }


def test_ire_wn_explorer_fresh_ko_units_one_constant_278():
    out = ire.compute_ire(_hand_wn(), None)   # tournament_meta ignorado p/ WN
    assert out is not None
    mv = out["main_villain"]
    assert mv["nick"] == "villainA"
    assert mv["stack_si"] == 1.0          # 20000/20000
    assert mv["ko_units"] == 1.0          # 25/25 (sem ×2)
    assert mv["ko_pct"] == 100
    # constant = (25/45)*0.5 = 0.27778 -> fórmula (fora da banda 0.25), não tabela
    assert ire.lookup_ire_pct(1.0, 1.0, 0.27778) != 5.1
    assert mv["ire_pct"] == 6.1           # 0.27778/(4+0.55556)*100


def test_ire_wn_accumulated_bounty_ko_units_above_one():
    # EXPLORER, vilão com 62.50€ (2.5× o bounty inicial 25)
    out = ire.compute_ire(_hand_wn(villain_bounty="62.50"), None)
    assert out["main_villain"]["ko_units"] == 2.5


def test_ire_wn_constant_250_buyin_is_269():
    # GRAVITY: entry 107 / bounty 125 -> (125/232)*0.5 = 0.26940
    assert ire._kop_from_parts(107, 125) * ire._INSTANT_FRACTION == \
        pytest.approx(0.26940, abs=1e-4)


def test_ire_wn_tournament_not_in_table_hidden():
    assert ire.compute_ire(_hand_wn(name="MEGA RUSH XPTO"), None) is None


def test_ire_wn_non_pko_hidden():
    assert ire.compute_ire(_hand_wn(fmt="KO"), None) is None


def test_ire_wn_no_match_method_required():
    # player_names vazio (sem match_method) NÃO esconde no WN (≠ GG).
    h = _hand_wn()
    assert h["player_names"] == {}
    assert ire.compute_ire(h, None) is not None


def test_ire_wn_no_hh_bounties_hidden():
    # HH sem token de bounty -> _extract devolve {} -> ko_units 0 -> None
    h = _hand_wn()
    h["raw"] = 'Winamax Poker - Tournament "EXPLORER"\nSeat 1: villainA (20000)\n'
    assert ire.compute_ire(h, None) is None


def test_ire_gg_still_works_after_refactor():
    # sanidade: a GG continua a devolver o mesmo (fixtures GG existentes cobrem).
    out = ire.compute_ire(_hand_5050(), _meta())
    assert out["main_villain"]["ire_pct"] == 5.1
