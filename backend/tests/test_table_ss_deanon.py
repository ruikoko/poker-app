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
    """APA §B (Fase 2): o `_enrich_all_players_actions` já NÃO renomeia hash→name —
    mantém a chave-hash e põe o nome em `real_name`. Logo `_rekey_apa_to_hashes`
    passa a NO-OP em formato novo (chaves já são hashes). Isto FECHA por desenho a
    corrupção de idempotência (GG-6113994321): re-correr a desanon nunca usa nomes
    como chave, porque a chave nunca deixou de ser o hash."""
    from app.routers.screenshot import _enrich_all_players_actions
    apa_hash = {
        "_meta": {"bb": 100, "sb": 50},
        "5e26839e": {"position": "BTN", "vpip": True},
        "b6b2d9ab": {"position": "CO", "vpip": False},
    }
    anon_map = {"5e26839e": "Karluz", "b6b2d9ab": "Galego"}
    vision = {"players_list": [{"name": "Karluz", "bounty_pct": 5},
                               {"name": "Galego", "bounty_pct": 3}]}
    # 1) enrich MANTÉM as chaves-hash; o nome vai para real_name (não re-indexa)
    enriched = _enrich_all_players_actions(apa_hash, anon_map, vision)
    assert set(k for k in enriched if k != "_meta") == {"5e26839e", "b6b2d9ab"}
    assert enriched["5e26839e"]["real_name"] == "Karluz"
    assert enriched["b6b2d9ab"]["real_name"] == "Galego"
    # 2) o re-key é NO-OP (já hash-keyed) — idempotência estrutural
    back = _rekey_apa_to_hashes(enriched, anon_map)
    assert set(k for k in back if k != "_meta") == {"5e26839e", "b6b2d9ab"}
    # 3) _meta preservado + os dados por banco mantêm-se
    assert back["_meta"] == {"bb": 100, "sb": 50}
    assert back["5e26839e"]["position"] == "BTN"


# ── pt95 — override por blinds: garantia anti-fusão de seats ──────────────────
def test_enrich_mapa_distinto_nao_funde_seats():
    """APA §B (Fase 2): a fusão de seats (bug 4321: vilão = nome do Hero) fica
    ESTRUTURALMENTE impossível — o enrich mantém a chave-hash, nunca re-indexa por
    nome. Mapa com nicks distintos OU com nick repetido → o MESMO nº de seats
    (nenhum cai); o nome repetido fica em `real_name` nos 2 hashes (veneno a apanhar
    na quarentena de nomes da Fase 3, mas o LUGAR não desaparece)."""
    from app.routers.screenshot import _enrich_all_players_actions
    apa = {"_meta": {"bb": 4000},
           "Hero": {"position": "MP"}, "5e26839e": {"position": "UTG"},
           "d6e6f5c9": {"position": "SB"}}
    vision = {"players_list": []}
    good = {"Hero": "Lauro Dermio", "5e26839e": "Karluz", "d6e6f5c9": "iLuckYou3000"}
    e = _enrich_all_players_actions(apa, good, vision)
    assert sorted(k for k in e if k != "_meta") == ["5e26839e", "Hero", "d6e6f5c9"]
    assert e["5e26839e"]["real_name"] == "Karluz"
    # nick repetido: SEM colapso (o seat NÃO cai — o coração da mudança anti-4321)
    bad = {"Hero": "Lauro Dermio", "5e26839e": "Lauro Dermio", "d6e6f5c9": "iLuckYou3000"}
    eb = _enrich_all_players_actions(apa, bad, vision)
    assert len([k for k in eb if k != "_meta"]) == 3
    assert eb["Hero"]["real_name"] == "Lauro Dermio"
    assert eb["5e26839e"]["real_name"] == "Lauro Dermio"  # veneno, mas 2 seats distintos


# ── pt96 (#DESANON-HERO-BUTTON-ANCHOR) — âncora Hero+botão + propagação circular ──
def _seat(nick, hero=False, btn=False):
    return {"nick": nick, "is_hero": hero, "is_button": btn}

def test_hero_button_anchor_4321_horario_e_invertido():
    """A roda alinha 8/8 (ground-truth 4321). O botão (2ª âncora) detecta e corrige a
    direcção quando a Vision lê ao contrário."""
    from app.services.table_ss_deanon import build_anon_map_by_hero_button
    hh_pos = {"d6e6f5c9":"SB","bd3f7c55":"BB","5e26839e":"UTG","ff3d6eb4":"UTG1",
              "Hero":"MP","b6b2d9ab":"MP1","d24da2fa":"CO","dc7499e7":"BTN"}
    gold = {"Hero":"Lauro Dermio","b6b2d9ab":"Galeguinhoo","d24da2fa":"ajolotee",
            "dc7499e7":"theheroguy","d6e6f5c9":"iLuckYou3000","bd3f7c55":"rickzera",
            "5e26839e":"Karluz","ff3d6eb4":"MIRALINE"}
    img_ok = [_seat("Lauro Dermio", hero=True), _seat("Galeguinhoo"), _seat("ajolotee"),
              _seat("theheroguy", btn=True), _seat("iLuckYou3000"), _seat("rickzera"),
              _seat("Karluz"), _seat("MIRALINE")]
    m, alarm = build_anon_map_by_hero_button(img_ok, hh_pos, 8)
    assert alarm is None and m == gold
    img_inv = [img_ok[0]] + img_ok[1:][::-1]          # Vision leu ao contrário
    m2, a2 = build_anon_map_by_hero_button(img_inv, hh_pos, 8)
    assert a2 is None and m2 == gold                  # botão reverte -> 8/8

def test_hero_button_regra_dura_hero_fixo():
    """Hero fica no índice 0 -> nunca a um vilão (o bug dos 15)."""
    from app.services.table_ss_deanon import build_anon_map_by_hero_button
    hh_pos = {"d6e6f5c9":"SB","bd3f7c55":"BB","5e26839e":"UTG","ff3d6eb4":"UTG1",
              "Hero":"MP","b6b2d9ab":"MP1","d24da2fa":"CO","dc7499e7":"BTN"}
    img = [_seat("Lauro Dermio", hero=True), _seat("Galeguinhoo"), _seat("ajolotee"),
           _seat("theheroguy", btn=True), _seat("iLuckYou3000"), _seat("rickzera"),
           _seat("Karluz"), _seat("MIRALINE")]
    m, _ = build_anon_map_by_hero_button(img, hh_pos, 8)
    assert m["Hero"] == "Lauro Dermio"                # Hero nunca a vilão
    assert list(m.values()).count("Lauro Dermio") == 1  # sem duplicado do Hero

def test_hero_button_salvaguarda_sitting_out():
    """Contagens diferem (sitting-out/mesa incompleta) -> alarme, NÃO desanon às cegas."""
    from app.services.table_ss_deanon import build_anon_map_by_hero_button
    hh_pos = {"h1":"SB","h2":"BB","Hero":"UTG","h3":"CO","h4":"BTN"}  # 5 na HH
    img = [_seat("A", hero=True), _seat("B"), _seat("C")]              # 3 na imagem
    m, alarm = build_anon_map_by_hero_button(img, hh_pos, 5)
    assert m == {} and alarm and "seat_count_mismatch" in alarm

def test_hero_button_headsup():
    """Heads-up (2-max, SB=botão): sem BTN label -> salta checagem do botão, 2 seats ok."""
    from app.services.table_ss_deanon import build_anon_map_by_hero_button
    hh_pos = {"Hero":"BB","h1":"SB"}
    img = [_seat("Lauro Dermio", hero=True), _seat("Villain", btn=True)]
    m, alarm = build_anon_map_by_hero_button(img, hh_pos, 2)
    assert alarm is None and m == {"Hero":"Lauro Dermio","h1":"Villain"}


def test_direcao_por_stacks_sem_botao():
    """Sem botão fiável, os STACKS desempatam a direcção (1 de 2). Hero fixo; nomes pela
    ordem. Inócuo — os stacks não atribuem nicks."""
    from app.services.table_ss_deanon import build_anon_map_by_hero_button
    hh_pos = {"h1":"SB","h2":"BB","Hero":"UTG","h3":"MP","h4":"CO","h5":"BTN"}  # 6-max
    hh_st = {"h1":10.0,"h2":20.0,"Hero":30.0,"h3":40.0,"h4":50.0,"h5":60.0}
    # wheel=[Hero,h3,h4,h5,h1,h2] stacks [30,40,50,60,10,20]
    img = [{"nick":"Lauro Dermio","is_hero":True,"stack_bb":30},{"nick":"B","stack_bb":40},
           {"nick":"C","stack_bb":50},{"nick":"D","stack_bb":60},
           {"nick":"E","stack_bb":10},{"nick":"F","stack_bb":20}]
    m,a = build_anon_map_by_hero_button(img, hh_pos, 6, hh_st)
    assert a is None and m == {"Hero":"Lauro Dermio","h3":"B","h4":"C","h5":"D","h1":"E","h2":"F"}
    img_rev = [img[0]] + img[1:][::-1]                 # Vision leu ao contrário
    m2,a2 = build_anon_map_by_hero_button(img_rev, hh_pos, 6, hh_st)
    assert a2 is None and m2 == m                      # stacks revertem -> mesmo mapa

def test_stack_guard_apanha_rotacao():
    """#DESANON-ROTATION-STACK-GUARD — a Vision leu os seats numa ordem RODADA (nick+stack
    deslocados após o Hero); a direção fwd/rev não apanha uma rotação de 1 cadeira, o mapa
    constrói-se, mas os STACKS desmentem-no (cada hash recebe o nick da cadeira ao lado) →
    alarme, não escreve. É a família da captura 782 do tn 292179612."""
    from app.services.table_ss_deanon import build_anon_map_by_hero_button
    hh_pos = {"h1": "SB", "h2": "BB", "Hero": "UTG", "h3": "MP", "h4": "CO", "h5": "BTN"}  # 6-max
    hh_st = {"h1": 10.0, "h2": 20.0, "Hero": 30.0, "h3": 40.0, "h4": 50.0, "h5": 60.0}
    # wheel=[Hero,h3,h4,h5,h1,h2] stacks [30,40,50,60,10,20]; Vision leu C,D,E,F,B (rodado).
    img = [{"nick": "Lauro Dermio", "is_hero": True, "stack_bb": 30}, {"nick": "C", "stack_bb": 50},
           {"nick": "D", "stack_bb": 60}, {"nick": "E", "stack_bb": 10},
           {"nick": "F", "stack_bb": 20}, {"nick": "B", "stack_bb": 40}]
    m, a = build_anon_map_by_hero_button(img, hh_pos, 6, hh_st)
    assert m == {} and a and a.startswith("stack_map_mismatch")


def test_stack_guard_deixa_passar_mapa_certo():
    """Mapa alinhado (stacks batem) → SEM alarme de stacks (não falsos-positivos)."""
    from app.services.table_ss_deanon import build_anon_map_by_hero_button
    hh_pos = {"h1": "SB", "h2": "BB", "Hero": "UTG", "h3": "MP", "h4": "CO", "h5": "BTN"}
    hh_st = {"h1": 10.0, "h2": 20.0, "Hero": 30.0, "h3": 40.0, "h4": 50.0, "h5": 60.0}
    img = [{"nick": "Lauro Dermio", "is_hero": True, "stack_bb": 30}, {"nick": "B", "stack_bb": 40},
           {"nick": "C", "stack_bb": 50}, {"nick": "D", "stack_bb": 60},
           {"nick": "E", "stack_bb": 10}, {"nick": "F", "stack_bb": 20}]
    m, a = build_anon_map_by_hero_button(img, hh_pos, 6, hh_st)
    assert a is None and m["Hero"] == "Lauro Dermio"


def test_botao_stacks_discordam_alarme():
    """Botão diz uma direcção, stacks dizem outra → ALARME (não escreve)."""
    from app.services.table_ss_deanon import build_anon_map_by_hero_button
    hh_pos = {"h1":"SB","h2":"BB","Hero":"UTG","h4":"CO","h5":"BTN"}  # 5-max
    hh_st = {"h1":10.0,"h2":20.0,"Hero":30.0,"h4":40.0,"h5":50.0}
    # wheel=[Hero,h4,h5,h1,h2] stacks [30,40,50,10,20]; btn(h5) idx 2
    # stacks -> fwd; botão colocado no idx 3 -> rev  => discordam
    img = [{"nick":"Lauro Dermio","is_hero":True,"stack_bb":30},{"nick":"B","stack_bb":40},
           {"nick":"C","stack_bb":50},{"nick":"D","stack_bb":10,"is_button":True},
           {"nick":"E","stack_bb":20}]
    m,a = build_anon_map_by_hero_button(img, hh_pos, 5, hh_st)
    assert m == {} and a == "button_stack_direction_disagree"


# ── #FLAME-AS-CROWN-GUARD (base÷2 SÓ — decisão A; grelha removida) ────────────
def _patch_query(monkeypatch, base):
    import app.db as dbmod
    monkeypatch.setattr(dbmod, "query",
                        lambda *a, **k: [{"buy_in_bounty": base}])


def test_guard_suspect_crowns_below_half(monkeypatch):
    """base 100: $27<½→NULL(below_half). $80 (off-grid mas ≥½) FICA — a grelha
    saiu (259.37 real provou que NULLava coroas verdadeiras). $50/$0/$75 intactos;
    bounty_confirmed intacto mesmo <½."""
    from app.services.table_ss_deanon import _guard_suspect_crowns
    _patch_query(monkeypatch, 100)
    pl = [
        {"name": "A", "bounty_value_usd": 27},                 # <½ → below_half
        {"name": "B", "bounty_value_usd": 80},                 # ≥½ off-grid → FICA
        {"name": "C", "bounty_value_usd": 50},                 # ok (fresca)
        {"name": "D", "bounty_value_usd": 259.37},             # progressiva real → FICA
        {"name": "E", "bounty_value_usd": 0},                  # omissão → fica
        {"name": "F", "bounty_value_usd": 20, "bounty_confirmed": True},  # exceção <½
    ]
    out = _guard_suspect_crowns(pl, "T1")
    assert out == {"below_half": 1}
    assert pl[0]["bounty_value_usd"] is None and pl[0]["crown_review"] == "flame_below_half"
    assert pl[1]["bounty_value_usd"] == 80 and "crown_review" not in pl[1]
    assert pl[2]["bounty_value_usd"] == 50
    assert pl[3]["bounty_value_usd"] == 259.37
    assert pl[4]["bounty_value_usd"] == 0
    assert pl[5]["bounty_value_usd"] == 20          # confirmado fica mesmo <½


def test_guard_suspect_crowns_no_base_noop(monkeypatch):
    """Sem base (TS ausente) → NO-OP (não anula nada)."""
    from app.services.table_ss_deanon import _guard_suspect_crowns
    _patch_query(monkeypatch, None)
    pl = [{"name": "A", "bounty_value_usd": 27}]
    out = _guard_suspect_crowns(pl, "T1")
    assert out == {"below_half": 0}
    assert pl[0]["bounty_value_usd"] == 27


# ── #DESANON-HERO-ANCHOR-VALIDATION: is_hero da Vision tem de ser o Rui ───────
def test_vision_hero_nick_is_rui_tolerant():
    from app.services.table_ss_deanon import _vision_hero_nick_is_rui
    assert _vision_hero_nick_is_rui("Lauro Dermio")
    assert _vision_hero_nick_is_rui("Lauro Der..")      # truncado pela Vision
    assert _vision_hero_nick_is_rui("koumpounophobia")
    assert not _vision_hero_nick_is_rui("R Sanchez")    # vilão (o bug 2223abd8)
    assert not _vision_hero_nick_is_rui("buildthepot")  # vilão (a 7ª)
    assert not _vision_hero_nick_is_rui("")
    assert not _vision_hero_nick_is_rui("R S")           # prefixo curto não casa


def test_anchor_alarms_when_hero_not_rui():
    """Vision marcou 'R Sanchez' como is_hero (baixo-centro) → alarme, não ancora
    (senão Hero↔vilão trocam nomes)."""
    from app.services.table_ss_deanon import build_anon_map_by_hero_button
    hh_pos = {"Hero": "BTN", "h2": "SB", "h3": "BB"}     # 3-handed
    img = [{"nick": "R Sanchez", "is_hero": True}, {"nick": "vilao1"}, {"nick": "vilao2"}]
    m, a = build_anon_map_by_hero_button(img, hh_pos, 3, {"Hero": 30.0, "h2": 20.0, "h3": 10.0})
    assert m == {} and a and a.startswith("hero_not_rui_account")


def test_anchor_ok_when_hero_is_rui_truncated():
    """is_hero = 'Lauro Der..' (truncado) → passa a guarda (não alarma)."""
    from app.services.table_ss_deanon import build_anon_map_by_hero_button
    hh_pos = {"Hero": "BTN", "h2": "SB", "h3": "BB"}
    img = [{"nick": "Lauro Der..", "is_hero": True, "is_button": True},
           {"nick": "villA"}, {"nick": "villB"}]
    m, a = build_anon_map_by_hero_button(img, hh_pos, 3, {"Hero": 30.0, "h2": 20.0, "h3": 10.0})
    assert a != "hero_not_rui_account" and (a is None or not str(a).startswith("hero_not_rui"))
