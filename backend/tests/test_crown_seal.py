"""SELO das coroas/nomes (invariante do Rui, 18 Jul) — o que o Rui valida fica
selado ('manual'/carimbo) e NENHUM processo automático (re-deanon/re-apply/scrub/
re-leitura) escreve por cima. Prova: corrigir um valor → forçar o re-apply → sobrevive.

Cross-ref: forense 6570 (GG-6104058222); JOURNAL_2026-07-18 §4."""
from app.services.eliminated_bounty import (
    is_bounty_sealed, scrub_eliminated_bounties,
    SOURCE_MANUAL, SOURCE_GREEN_KO, SOURCE_DERIVED_GREEN_KO,
    SEALED_BOUNTY_SOURCES, BOUNTY_SOURCE_KEY,
)
from app.services.table_ss_deanon import _merge_sealed_crowns
from app.routers.screenshot import _enrich_all_players_actions


# ── predicado do selo ─────────────────────────────────────────────────────────

def test_is_bounty_sealed_predicate():
    assert is_bounty_sealed({"bounty_source": SOURCE_MANUAL})
    assert is_bounty_sealed({"bounty_source": SOURCE_GREEN_KO})
    assert is_bounty_sealed({"bounty_source": SOURCE_DERIVED_GREEN_KO})
    assert is_bounty_sealed({"bounty_source": "cross_capture"})   # carimbo em lote (LEI DO CRUZAMENTO)
    assert is_bounty_sealed({"bounty_source": "cross_conflict"})  # conflito resolvido por (B)
    assert is_bounty_sealed({"bounty_confirmed": True})
    # NÃO selados: fontes automáticas (fallback), sem marca, tipos inválidos.
    assert not is_bounty_sealed({"bounty_source": "gold"})
    assert not is_bounty_sealed({"bounty_source": "table_ss"})
    assert not is_bounty_sealed({"bounty_value_usd": 100})
    assert not is_bounty_sealed({})
    assert not is_bounty_sealed(None)
    assert {SOURCE_MANUAL, SOURCE_GREEN_KO, SOURCE_DERIVED_GREEN_KO,
            "cross_capture", "cross_conflict"} == set(SEALED_BOUNTY_SOURCES)


# ── PROVA: re-apply do apa (o culpado da 6570) não pisa o carimbo ─────────────

def test_reapply_apa_preserves_sealed_crown():
    """AVRELIY carimbada a $265.62 (manual); a leitura table-SS guardada diz $50.
    O re-apply (_enrich_all_players_actions) TEM de manter os $265.62."""
    apa = {
        "_meta": {"x": 1},
        "hashA": {"real_name": "AVRELIY", "position": "BTN",
                  "bounty_value_usd": 265.62, "bounty_source": SOURCE_MANUAL},
        "hashB": {"real_name": "Ze Vivo", "position": "SB",
                  "bounty_value_usd": 10},        # NÃO selado
    }
    anon_map = {"hashA": "AVRELIY", "hashB": "Ze Vivo"}
    vision = {"players_list": [
        {"name": "AVRELIY", "bounty_value_usd": 50},     # leitura guardada (errada)
        {"name": "Ze Vivo", "bounty_value_usd": 99},
    ], "players_by_position": {}}

    out = _enrich_all_players_actions(apa, anon_map, vision)
    # selado: sobrevive, com a marca intacta
    assert out["hashA"]["bounty_value_usd"] == 265.62
    assert out["hashA"][BOUNTY_SOURCE_KEY] == SOURCE_MANUAL
    # NÃO selado: o automático continua a funcionar como hoje (leva a Vision)
    assert out["hashB"]["bounty_value_usd"] == 99
    assert out["_meta"] == {"x": 1}


def test_reapply_apa_overwrites_when_not_sealed():
    """Controlo: sem selo, o re-apply escreve a leitura da Vision (comportamento normal
    inalterado) — prova que o mecanismo é o SELO, não um congelamento cego."""
    apa = {"h": {"real_name": "X", "position": "BB", "bounty_value_usd": 265.62}}
    out = _enrich_all_players_actions(
        apa, {"h": "X"},
        {"players_list": [{"name": "X", "bounty_value_usd": 50}], "players_by_position": {}})
    assert out["h"]["bounty_value_usd"] == 50


# ── PROVA: re-deanon do players_list (a 6570) preserva o carimbo ──────────────

def test_merge_sealed_crowns_preserves_and_persists_seal():
    """Phil carimbado a $375 (derived_green_ko) no players_list ANTERIOR; o re-deanon
    reconstrói o players_list da leitura guardada ($50). O merge repõe $375 E mantém a
    marca (para o selo PERSISTIR nos próximos re-deanons)."""
    prev = [
        {"name": "Phil", "bounty_value_usd": 375, "bounty_source": SOURCE_DERIVED_GREEN_KO},
        {"name": "NaoSelado", "bounty_value_usd": 20},        # sem selo
    ]
    new = [
        {"name": "Phil", "bounty_value_usd": 50, "crown_review": "flame_below_half"},
        {"name": "NaoSelado", "bounty_value_usd": 30},
        {"name": "Outro", "bounty_value_usd": 80},
    ]
    n = _merge_sealed_crowns(prev, new)
    assert n == 1
    assert new[0]["bounty_value_usd"] == 375
    assert new[0]["bounty_source"] == SOURCE_DERIVED_GREEN_KO
    assert "crown_review" not in new[0]                       # herança 'por rever' limpa
    assert new[1]["bounty_value_usd"] == 30                   # não selado — automático manda
    assert new[2]["bounty_value_usd"] == 80

    # idempotente: correr de novo mantém tudo
    assert _merge_sealed_crowns(new, new) >= 0
    assert new[0]["bounty_value_usd"] == 375


def test_merge_sealed_crowns_confirmed_flag_seals():
    prev = [{"name": "Y", "bounty_value_usd": 111, "bounty_confirmed": True}]
    new = [{"name": "Y", "bounty_value_usd": 9}]
    assert _merge_sealed_crowns(prev, new) == 1
    assert new[0]["bounty_value_usd"] == 111
    assert new[0]["bounty_confirmed"] is True


def test_merge_no_prev_is_noop():
    new = [{"name": "Z", "bounty_value_usd": 5}]
    assert _merge_sealed_crowns(None, new) == 0
    assert _merge_sealed_crowns([], new) == 0
    assert new[0]["bounty_value_usd"] == 5


# ── PROVA: o funil scrub (verde-KO) não desfaz um carimbo manual ──────────────

_HH_BUST = (
    "Poker Hand #TM1: Tournament #1, Bounty Hunters $150\n"
    "Seat 5: Hero (87,283 in chips)\n"
    "Hero: bets 47,944 and is all-in\n"
    "ccc84511: calls 47,944\n"
    "*** SHOWDOWN ***\n"
    "ccc84511 collected 180,816 from pot\n"
    "*** SUMMARY ***\n"
    "Seat 5: Hero showed [Qd Js] and lost with Ace high\n"
)


def test_scrub_preserves_manual_on_busted_seat():
    """O Hero está bustado (HH) mas o Rui carimbou a coroa dele a $170.63 (manual).
    O scrub MUST-only anularia um bustado sem verde — mas um carimbo manual é intocável."""
    apa = {"_meta": {}, "Hero": {"real_name": "",
                                 "bounty_value_usd": 170.63, "bounty_source": SOURCE_MANUAL}}
    touched = scrub_eliminated_bounties(apa, {}, _HH_BUST, tagged=True)
    assert touched == 0
    assert apa["Hero"]["bounty_value_usd"] == 170.63
    assert apa["Hero"][BOUNTY_SOURCE_KEY] == SOURCE_MANUAL


def test_scrub_still_nulls_unsealed_busted_seat():
    """Controlo: um bustado SEM selo e sem verde continua a ir a NULL (cura inalterada)."""
    apa = {"_meta": {}, "Hero": {"real_name": "", "bounty_value_usd": 999}}
    touched = scrub_eliminated_bounties(apa, {}, _HH_BUST, tagged=True)
    assert touched == 1
    assert apa["Hero"]["bounty_value_usd"] is None
