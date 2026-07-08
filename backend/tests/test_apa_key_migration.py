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
