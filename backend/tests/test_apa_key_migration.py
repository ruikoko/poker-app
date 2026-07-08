"""APA §B.6 (core aprovado 8 Jul) — Fase 1: leitores a `real_name || chave`.

Prova a IDENTIDADE DE COMPORTAMENTO da migração: cada leitor produz a MESMA saída
quando alimentado com o apa no formato ANTIGO (chave == nome real; sem `real_name`)
e no formato NOVO (chave == hash; `real_name` = nome). Nos dados actuais só existe o
formato antigo (ou anón com `real_name` vazio) → a Fase 1 é byte-idêntica; estes
testes garantem-no E provam que o mesmo código fica correcto quando a chave passar a
hash na Fase 2 (writer). Ver `APA_INDEXACAO_E_COLAPSO §B.2/§B.6`.
"""
from app.services import ire
from app.services.villain_rules import _build_candidates
from app.services.hand_service import _resolve_hashes_in_raw


# ── Construção do apa nos dois formatos ──────────────────────────────────────
# villainA: hash 3b4cd0c7 / nome "villainA"  (fez VPIP → candidato)
# villainB: hash 89ef4cba / nome "villainB"  (showdown → candidato)

def _apa(hero_key, a_key, b_key, a_real, b_real):
    return {
        "_meta": {"bb": 1000},
        hero_key:  {"is_hero": True, "stack": 30000, "position": "BTN", "seat": 1,
                    "actions": {"preflop": ["Raise 2000"]}},
        a_key:     {"stack": 20000, "position": "CO", "seat": 2, "cards": ["Qs", "Qd"],
                    "actions": {"preflop": ["Call 2000"]}, "real_name": a_real},
        b_key:     {"stack": 40000, "position": "SB", "seat": 3, "cards": ["Ah", "Kd"],
                    "actions": {"preflop": ["Fold"]}, "real_name": b_real},
    }


# formato ANTIGO: chave == nome real; sem real_name (removido p/ fidelidade)
def _apa_old():
    a = _apa("Hero", "villainA", "villainB", None, None)
    for k in ("villainA", "villainB"):
        a[k].pop("real_name", None)
    return a


# formato NOVO: chave == hash; real_name = nome real
def _apa_new():
    return _apa("Hero", "3b4cd0c7", "89ef4cba", "villainA", "villainB")


# formato NOVO ANÓN: chave == hash; real_name vazio (por mapear) → identidade = hash
def _apa_new_anon():
    return _apa("Hero", "3b4cd0c7", "89ef4cba", None, None)


def _hand(apa):
    return {
        "site": "GGPoker", "tournament_format": "PKO",
        "hm3_tags": ["ICM", "pko"], "discord_tags": None,
        "all_players_actions": apa,
        "pn": {"players_list": [
            {"name": "villainA", "bounty_value_usd": 12.5},
            {"name": "villainB", "bounty_value_usd": 12.5},
        ]},
        "player_names": {"match_method": "position_v3", "players_list": [
            {"name": "villainA", "bounty_value_usd": 12.5},
            {"name": "villainB", "bounty_value_usd": 12.5},
        ]},
    }


def _meta():
    return {"tournament_name": "Bounty Hunters $88", "starting_stack": 20000,
            "buy_in_bounty": 25}


# ── _build_candidates ────────────────────────────────────────────────────────

def test_build_candidates_old_equals_new():
    old = _build_candidates(_hand(_apa_old()))
    new = _build_candidates(_hand(_apa_new()))
    assert old == new
    assert [c["nick"] for c in old] == ["villainA", "villainB"]


def test_build_candidates_new_anon_skips_villains():
    # chave=hash, real_name vazio → identidade continua hash → _is_anon_hash → salta
    cand = _build_candidates(_hand(_apa_new_anon()))
    assert cand == []


# ── ire.compute_ire (via _assemble_ire) ──────────────────────────────────────

def test_compute_ire_old_equals_new():
    old = ire.compute_ire(_hand(_apa_old()), _meta())
    new = ire.compute_ire(_hand(_apa_new()), _meta())
    assert old == new
    assert old is not None
    assert old["main_villain"]["nick"] == "villainA"
    assert [p["nick"] for p in old["per_opponent"]] == ["villainA", "villainB"]


def test_compute_ire_new_anon_no_bounty_match():
    # nicks = hashes → não batem no bounty_by_nick (por nome) → sem KO → IRE escondido
    assert ire.compute_ire(_hand(_apa_new_anon()), _meta()) is None


# ── _resolve_hashes_in_raw ───────────────────────────────────────────────────

_RAW = (
    "Poker Hand #TM1: Tournament #1\n"
    "Table '21' 8-max Seat #1 is the button\n"
    "Seat 1: Hero (30000 in chips)\n"
    "Seat 2: 3b4cd0c7 (20000 in chips)\n"
    "Seat 3: 89ef4cba (40000 in chips)\n"
    "3b4cd0c7: raises 2000\n"
    "89ef4cba: folds\n"
)


def test_resolve_raw_old_equals_new():
    old = _resolve_hashes_in_raw(_RAW, _apa_old())
    new = _resolve_hashes_in_raw(_RAW, _apa_new())
    assert old == new
    # ambos resolvem hash→nome real no raw
    assert "villainA: raises 2000" in new
    assert "villainB: folds" in new
    assert "3b4cd0c7" not in new


def test_resolve_raw_new_anon_leaves_hashes():
    # real_name vazio → seat_to_real = hash == anon → sem substituição (fica anón, honesto)
    out = _resolve_hashes_in_raw(_RAW, _apa_new_anon())
    assert "3b4cd0c7: raises 2000" in out
    assert "89ef4cba: folds" in out


# ═══ Fase 2 — writer: _enrich_all_players_actions NÃO re-indexa por nome ═══════
# A chave da HH mantém-se (hash/nick/"Hero"); real_name = atributo. Ver APA §B.

from app.routers.screenshot import _enrich_all_players_actions


def _hash_apa():
    return {
        "_meta": {"bb": 1000},
        "Hero":     {"is_hero": True, "seat": 1, "position": "BTN", "stack": 30000},
        "3b4cd0c7": {"is_hero": False, "seat": 2, "position": "CO", "stack": 20000, "cards": ["Ah", "Kd"]},
        "89ef4cba": {"is_hero": False, "seat": 3, "position": "SB", "stack": 40000},
    }


def test_enrich_new_gg_hand_keys_are_hashes_realname_empty():
    # mão GG nova, sem desanon → chaves = hashes; real_name vazio
    out = _enrich_all_players_actions(_hash_apa(), {}, {})
    assert set(out) == {"_meta", "Hero", "3b4cd0c7", "89ef4cba"}
    assert out["3b4cd0c7"]["real_name"] == ""
    assert out["89ef4cba"]["real_name"] == ""


def test_enrich_gold_desanon_fills_realname_keeps_key():
    # desanon por Gold → real_name preenche SEM mudar a chave
    out = _enrich_all_players_actions(_hash_apa(), {"3b4cd0c7": "Alice", "89ef4cba": "Bob"}, {})
    assert "3b4cd0c7" in out and "Alice" not in out
    assert out["3b4cd0c7"]["real_name"] == "Alice"
    assert out["89ef4cba"]["real_name"] == "Bob"


def test_enrich_two_players_same_name_two_entries():
    # anti-MaLong07: dois jogadores com o MESMO nome → 2 entradas distintas (sem fusão)
    out = _enrich_all_players_actions(_hash_apa(), {"3b4cd0c7": "MaLong07", "89ef4cba": "MaLong07"}, {})
    assert len([k for k in out if k != "_meta"]) == 3
    assert out["3b4cd0c7"]["real_name"] == "MaLong07"
    assert out["89ef4cba"]["real_name"] == "MaLong07"


def test_enrich_unmapped_seat_stays_on_table():
    # anti-sitting-out: lugar sem nome FICA na mesa, real_name branco honesto
    out = _enrich_all_players_actions(_hash_apa(), {"3b4cd0c7": "Alice"}, {})
    assert "89ef4cba" in out
    assert out["89ef4cba"]["real_name"] == ""
    assert len([k for k in out if k != "_meta"]) == 3


def test_enrich_meta_and_player_fields_preserved():
    out = _enrich_all_players_actions(_hash_apa(), {"3b4cd0c7": "Alice"}, {})
    assert out["_meta"] == {"bb": 1000}
    assert out["3b4cd0c7"]["cards"] == ["Ah", "Kd"]
    assert out["3b4cd0c7"]["seat"] == 2 and out["3b4cd0c7"]["position"] == "CO"


def _has_showdown(apa):
    # espelho exacto de hand_service._insert_hand L339-343 (lê pdata.cards, não a chave)
    return any(isinstance(v, dict) and not v.get("is_hero") and v.get("cards")
               for k, v in apa.items() if k != "_meta")


def test_showdown_detection_key_agnostic():
    new = _enrich_all_players_actions(_hash_apa(), {"3b4cd0c7": "Alice", "89ef4cba": "Bob"}, {})
    old = {"_meta": {"bb": 1000},
           "Hero": {"is_hero": True, "seat": 1},
           "Alice": {"is_hero": False, "seat": 2, "cards": ["Ah", "Kd"], "real_name": "Alice"},
           "Bob": {"is_hero": False, "seat": 3, "real_name": "Bob"}}
    assert _has_showdown(new) is True
    assert _has_showdown(new) == _has_showdown(old)


def test_enrich_old_name_keyed_hand_not_corrupted():
    # ponto 3: reparação sobre mão ANTIGA (chaves=nomes) → mantém formato antigo,
    # sem perda de dados; o leitor mostra a chave (real_name || chave).
    old_apa = {"_meta": {"bb": 1000},
               "Hero": {"is_hero": True, "seat": 1, "real_name": "Hero"},
               "Alice": {"is_hero": False, "seat": 2, "real_name": "Alice", "cards": ["Ah"]}}
    out = _enrich_all_players_actions(old_apa, {"3b4cd0c7": "Zed"}, {})
    assert "Alice" in out
    assert out["Alice"]["cards"] == ["Ah"]
    assert (out["Alice"]["real_name"] or "Alice") == "Alice"


# ═══ Fase 2 — guarda (b) mínima no /set-anon-map (nome-já-usado) ═══════════════
# Único ponto onde um humano introduz o duplicado antes da Fase 3 (quarentena).

def test_set_anon_map_rejects_duplicate_real_name():
    import pytest
    from fastapi import HTTPException
    from app.routers.table_ss import _assert_no_duplicate_real_names
    # nicks distintos → não levanta
    _assert_no_duplicate_real_names({"Hero": "Lauro", "h1": "Karluz", "h2": "iLuckYou"})
    # valores vazios ("" = por mapear) ignorados
    _assert_no_duplicate_real_names({"h1": "", "h2": ""})
    # MESMO nome em 2 chaves → rejeita com erro claro (409, nomeia o duplicado)
    with pytest.raises(HTTPException) as ei:
        _assert_no_duplicate_real_names({"Hero": "Lauro Dermio", "h1": "Lauro Dermio"})
    assert ei.value.status_code == 409
    assert "Lauro Dermio" in ei.value.detail
