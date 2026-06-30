"""Testes do Estágio 3 — desanonimização por table-SS (núcleo puro, sem BD).

Foca o risco real: o map hash→nick a partir dos `seats` do table-SS, reutilizando
a maquinaria do pt7. Não toca BD (testa `build_anon_map_from_seats` +
`_seats_to_vision_data` + `_existing_match_method`).
"""
import json

from app.services.table_ss_deanon import (
    _seats_to_vision_data,
    _existing_match_method,
    _filter_ambiguous_stackless,
    build_anon_map_from_seats,
    cluster_vote,
    vote_tournament_maps,
    _rekey_apa_to_hashes,
)


# ── HH GG anonimizada sintética (3-handed) ───────────────────────────────────
# Hero (BTN) 10000 · aaaa1111 (folda) 8000 · bbbb2222 (call) 12000.
# Level 5: 100/200 (25 ante). Stacks no INÍCIO da mão (formato GG→PS).
_RAW_HH = (
    "PokerStars Hand #GG-9: Tournament Level 5 (100/200(25))\n"
    "Table '9' 9-max Seat #1 is the button\n"
    "Seat 1: Hero (10000 in chips)\n"
    "Seat 2: aaaa1111 (8000 in chips)\n"
    "Seat 3: bbbb2222 (12000 in chips)\n"
    "aaaa1111: posts the ante 25\n"
)

_MATCHED_HAND = {
    "id": 9,
    "hand_id": "GG-9",
    "site": "GGPoker",
    "raw": _RAW_HH,
    "all_players_actions": {
        "_meta": {"num_players": 3, "bb": 200, "sb": 100, "ante": 25},
        "Hero": {"position": "BTN", "is_hero": True,
                  "actions": {"preflop": ["Raise to 400"]}},
        "aaaa1111": {"position": "SB", "actions": {"preflop": ["Fold"]}},
        "bbbb2222": {"position": "BB", "actions": {"preflop": ["Call 200"]}},
    },
}

# Bancos lidos pela Vision do table-SS (stack em BB). bb_size=200.
# Hero 9980 (≈49.9 BB) · FoldGuy 7975 (39.875 BB = 8000-25 ante) · ActiveGuy 12000 (60 BB).
_SEATS = [
    {"nick": "Lauro Dermio", "stack_bb": 49.9, "bounty_usd": 125.0, "is_hero": True},
    {"nick": "FoldGuy", "stack_bb": 39.875, "bounty_usd": 50.0, "is_hero": False},
    {"nick": "ActiveGuy", "stack_bb": 60.0, "bounty_usd": None, "is_hero": False},
]


def test_seats_to_vision_data_shape():
    vd = _seats_to_vision_data(_SEATS, "Lauro Dermio")
    assert vd["hero"] == "Lauro Dermio"
    assert vd["vision_sb"] is None and vd["vision_bb"] is None
    pl = vd["players_list"]
    assert [p["name"] for p in pl] == ["Lauro Dermio", "FoldGuy", "ActiveGuy"]
    # BB → stack_unit/raw para o normalizador do pt7 converter com bb_size.
    assert pl[0]["stack_unit"] == "bb" and pl[0]["stack_raw"] == 49.9
    assert pl[0]["bounty_value_usd"] == 125.0
    assert "bounty_value_usd" not in pl[2]  # bounty None não vira chave


def test_seats_to_vision_data_allin_and_empty():
    seats = [
        {"nick": "AllInGuy", "stack_bb": "ALLIN"},
        {"nick": "", "stack_bb": 10.0},            # nick vazio → descartado
        {"nick": "NullStack", "stack_bb": None},
        {"nick": "Zero", "stack_bb": 0},           # 0 não é stack válido
    ]
    pl = _seats_to_vision_data(seats, None)["players_list"]
    names = [p["name"] for p in pl]
    assert names == ["AllInGuy", "NullStack", "Zero"]  # vazio fora
    # sem stack numérico → sem stack_unit (resolve por eliminação)
    assert "stack_unit" not in pl[0]
    assert "stack_unit" not in pl[1]
    assert "stack_unit" not in pl[2]


def test_build_anon_map_three_handed():
    """Hero ancora por nick; folder casa por stack (esperado=hh-ante);
    activo restante cai na eliminação 1-1."""
    anon_map = build_anon_map_from_seats(_MATCHED_HAND, _SEATS, "Lauro Dermio")
    assert anon_map["Hero"] == "Lauro Dermio"
    assert anon_map["aaaa1111"] == "FoldGuy"      # fold por stack 7975
    assert anon_map["bbbb2222"] == "ActiveGuy"    # eliminação
    assert "_meta" not in anon_map


def test_build_anon_map_empty_seats():
    assert build_anon_map_from_seats(_MATCHED_HAND, [], "Lauro Dermio") == {}


# ── Caso ambíguo (afinação Web): ≥2 bancos sem stack → não forçar ────────────
# HH 4-handed: Hero(BTN) 10000 · aaaa1111 (fold) 8000 · bbbb2222 (call) 5000 ·
# cccc3333 (call) 6000. Os 2 activos (bbbb2222/cccc3333) caem na fase de
# eliminação; os bancos da Vision que lhes corresponderiam estão AMBOS em ALL-IN
# (sem stack) → não desambiguáveis.
_RAW_HH_4 = (
    "PokerStars Hand #GG-4: Tournament Level 5 (100/200(25))\n"
    "Table '4' 9-max Seat #1 is the button\n"
    "Seat 1: Hero (10000 in chips)\n"
    "Seat 2: aaaa1111 (8000 in chips)\n"
    "Seat 3: bbbb2222 (5000 in chips)\n"
    "Seat 4: cccc3333 (6000 in chips)\n"
)
_MATCHED_HAND_4 = {
    "id": 4, "hand_id": "GG-4", "site": "GGPoker", "raw": _RAW_HH_4,
    "all_players_actions": {
        "_meta": {"num_players": 4},
        "Hero": {"position": "BTN", "is_hero": True,
                  "actions": {"preflop": ["Raise to 400"]}},
        "aaaa1111": {"position": "UTG", "actions": {"preflop": ["Fold"]}},
        "bbbb2222": {"position": "SB", "actions": {"preflop": ["Call 200"]}},
        "cccc3333": {"position": "BB", "actions": {"preflop": ["Call 200"]}},
    },
}
_SEATS_4 = [
    {"nick": "Lauro Dermio", "stack_bb": 49.9, "is_hero": True},
    {"nick": "FoldGuy", "stack_bb": 39.875, "is_hero": False},   # fold por stack
    {"nick": "AllinA", "stack_bb": "ALLIN", "is_hero": False},   # sem stack
    {"nick": "AllinB", "stack_bb": "ALLIN", "is_hero": False},   # sem stack
]


def test_filter_ambiguous_stackless():
    kept, dropped = _filter_ambiguous_stackless(_SEATS_4)
    assert dropped is True
    names = [s["nick"] for s in kept]
    assert names == ["Lauro Dermio", "FoldGuy"]  # 2 ALL-IN não-herói fora
    # 1 só banco sem stack NÃO é ambíguo (eliminação 1-1 segura) → mantém-se.
    one = [{"nick": "Hero", "stack_bb": 50.0, "is_hero": True},
           {"nick": "X", "stack_bb": "ALLIN"}]
    kept1, dropped1 = _filter_ambiguous_stackless(one)
    assert dropped1 is False and len(kept1) == 2


def test_current_helper_WOULD_force_without_filter():
    """Documenta o comportamento ACTUAL do helper pt7: sem o filtro, a atribuição
    óptima FORÇA os 2 ALL-IN (mapeia bbbb2222/cccc3333 por palpite)."""
    from app.routers.screenshot import _build_anon_to_real_map
    vd = _seats_to_vision_data(_SEATS_4, "Lauro Dermio")  # SEM filtro
    forced = _build_anon_to_real_map(_MATCHED_HAND_4, vd)
    # Sem o filtro, ambos os hashes activos são mapeados (por palpite) → o mal.
    assert "bbbb2222" in forced and "cccc3333" in forced


def test_ambiguous_leaves_unmapped_with_filter():
    """Com o filtro: os 2 ALL-IN ficam por mapear (hash mantido); só Hero+fold
    mapeiam → deanon_partial implícito (mapped < total)."""
    anon_map = build_anon_map_from_seats(_MATCHED_HAND_4, _SEATS_4, "Lauro Dermio")
    assert anon_map["Hero"] == "Lauro Dermio"
    assert anon_map["aaaa1111"] == "FoldGuy"
    assert "bbbb2222" not in anon_map   # ambíguo → POR MAPEAR (honesto)
    assert "cccc3333" not in anon_map
    total_hh = 3  # Hero + aaaa1111 + bbbb2222 + cccc3333 = 4; _meta fora → 4? não:
    # apa tem 4 jogadores não-_meta (Hero,aaaa1111,bbbb2222,cccc3333)
    assert len(anon_map) == 2  # parcial: 2 de 4 mapeados


# ── Votação cross-mão por torneio ────────────────────────────────────────────

def test_cluster_vote_basico():
    assert cluster_vote(["a", "a", "a"]) == ("a", "unanimous")
    # grafias OCR semelhantes colapsam num cluster (ratio>=0.88)
    nick, kind = cluster_vote(["justdoitttttt", "justdoittttt", "justdoittttt"])
    assert nick == "justdoittttt" and kind == "unanimous"
    assert cluster_vote(["x", "x", "y"]) == ("x", "majority")
    assert cluster_vote(["x", "y"]) == (None, "tie")  # 1-1 → por mapear


def test_vote_tournament_maps_corrige_swap_881():
    """Os 3 mapas reais do Daily Hyper (dry-run): a maioria corrige o swap do
    881 (4d2df37c hxnniUb→justdoittttt); 44d9e3c1 fica POR MAPEAR (1-1)."""
    maps = [
        # GG-6066749894
        {"Hero": "Lauro Dermio", "37bb0e2a": "DWilliams", "44d9e3c1": "hxnniUb",
         "4d2df37c": "justdoitttttt", "3aa60ee0": "I GRIND THIS", "c18b8c5d": "TennEggGuy"},
        # GG-6066749881 (o swap)
        {"Hero": "Lauro Dermio", "37bb0e2a": "DWilliams", "3aa60ee0": "I GRIND THIS",
         "c18b8c5d": "TennEggGuy", "44d9e3c1": "justdoittttt", "4d2df37c": "hxnniUb"},
        # GG-6066749680
        {"Hero": "Lauro Dermio", "435c8617": "Augusto Hagen", "4d2df37c": "justdoittttt",
         "c18b8c5d": "TennEggGuy", "efa85a54": "Andre Marques"},
    ]
    canon, stats = vote_tournament_maps(maps)
    # ★ swap do 881 corrigido: 4d2df37c deixa de ser 'hxnniUb' → cluster justdoit*
    # (a votação unifica a grafia em todas as mãos; o nº de 't' é variância OCR).
    assert canon["4d2df37c"].lower().startswith("justdoit")
    assert canon["4d2df37c"].lower() != "hxnniub"
    assert canon["c18b8c5d"] == "TennEggGuy"      # unânime 3/3
    assert canon["37bb0e2a"] == "DWilliams"
    assert "44d9e3c1" not in canon                # 1-1 → empate → por mapear
    assert canon["435c8617"] == "Augusto Hagen"   # singleton mantém-se
    assert stats["tie"] >= 1 and stats["majority"] >= 1


def test_rekey_apa_to_hashes():
    anon_map = {"hash1": "Nick1", "Hero": "HeroNick"}
    apa = {"_meta": {"x": 1}, "Nick1": {"a": 1}, "HeroNick": {"b": 2}}
    out = _rekey_apa_to_hashes(apa, anon_map)
    assert out == {"_meta": {"x": 1}, "hash1": {"a": 1}, "Hero": {"b": 2}}


def test_existing_match_method_variants():
    assert _existing_match_method({"match_method": "table_ss"}) == "table_ss"
    assert _existing_match_method(
        json.dumps({"match_method": "anchors_stack_elimination_v2"})
    ) == "anchors_stack_elimination_v2"
    assert _existing_match_method(None) is None
    assert _existing_match_method({}) is None
    assert _existing_match_method("not json") is None


# ── pt95 (#REDEANON-NOT-IDEMPOTENT) — round-trip do re-key ────────────────────
def test_rekey_apa_round_trip_restaura_hashes():
    """O fix de idempotência: o `_enrich_all_players_actions` renomeia o apa
    hash→name; `_rekey_apa_to_hashes` (via o anon_map) tem de RESTAURAR as chaves
    hash. Sem isto, re-correr a desanon usaria os NOMES como chave → mapa
    name→name (o que partiu a GG-6113994321). Testa a invariante do fix."""
    from app.routers.screenshot import _enrich_all_players_actions
    apa_hash = {
        "_meta": {"bb": 100, "sb": 50},
        "5e26839e": {"position": "BTN", "vpip": True},
        "b6b2d9ab": {"position": "CO", "vpip": False},
    }
    anon_map = {"5e26839e": "Karluz", "b6b2d9ab": "Galego"}
    vision = {"players_list": [{"name": "Karluz", "bounty_pct": 5},
                               {"name": "Galego", "bounty_pct": 3}]}
    # 1) enrich renomeia hash→name (a causa da corrupção)
    name_apa = _enrich_all_players_actions(apa_hash, anon_map, vision)
    assert set(k for k in name_apa if k != "_meta") == {"Karluz", "Galego"}
    # 2) o re-key restaura as chaves hash (o fix de idempotência)
    back = _rekey_apa_to_hashes(name_apa, anon_map)
    assert set(k for k in back if k != "_meta") == {"5e26839e", "b6b2d9ab"}
    # 3) _meta preservado + os dados por banco mantêm-se
    assert back["_meta"] == {"bb": 100, "sb": 50}
    assert back["5e26839e"]["position"] == "BTN"
