"""Varrimento de integridade de lugares (READ-ONLY) — padrão da GG-6118579134."""
from app.routers.table_ss import _scan_hand_integrity, _integrity_sanity_6118579134


def _raw(hashes):
    return "\n".join(f"Seat {i+1}: {h} ({(i+1)*1000} in chips)" for i, h in enumerate(hashes))


# ── SANIDADE: a forma partida da GG-6118579134 dispara A+B+C ─────────────────
def test_sanity_broken_6118579134_fires_all_three():
    sc = _integrity_sanity_6118579134()
    assert sc["a"] and sc["b"] and sc["c"]           # o método TE-LA-IA apanhado
    assert sc["seats_raw"] == 5 and sc["seats_apa"] == 4
    assert "a3f63bd" in sc["unmapped_hashes"]
    assert "MaLong07" in sc["loose_names"]


# ── mão sã (5 hashes, 5 lugares, tudo mapeado) → nada ────────────────────────
def test_clean_hand_no_flags():
    raw = _raw(["Hero", "aaa", "bbb", "ccc", "ddd"])
    apa = {"_meta": {}, "Hero": {}, "A": {}, "B": {}, "C": {}, "D": {}}
    pn = {"anon_map": {"Hero": "Hero", "aaa": "A", "bbb": "B", "ccc": "C", "ddd": "D"},
          "players_list": [{"name": "A"}, {"name": "B"}]}
    sc = _scan_hand_integrity(raw, apa, pn)
    assert not sc["a"] and not sc["b"] and not sc["c"]


# ── anónima (apa hash-keyed, sem anon_map) → NÃO dispara B/C (não é 'partida') ─
def test_anonymous_hand_not_flagged():
    raw = _raw(["Hero", "aaa", "bbb"])
    apa = {"_meta": {}, "Hero": {}, "aaa": {}, "bbb": {}}       # hash-keyed, 3 lugares
    pn = {}                                                     # sem anon_map
    sc = _scan_hand_integrity(raw, apa, pn)
    assert not sc["a"] and not sc["b"] and not sc["c"]         # seats batem, sem anon_map


# ── colapso (2 hashes → mesmo nome) → A dispara ──────────────────────────────
def test_collapse_flags_A():
    raw = _raw(["Hero", "aaa", "bbb"])
    apa = {"_meta": {}, "Hero": {}, "dup": {}}                  # 2 lugares (colapso)
    pn = {"anon_map": {"Hero": "Hero", "aaa": "dup", "bbb": "dup"}}
    sc = _scan_hand_integrity(raw, apa, pn)
    assert sc["a"] and sc["seats_raw"] == 3 and sc["seats_apa"] == 2


# ── hash por mapear (anon_map não-vazio mas falta 1) → B dispara ─────────────
def test_unmapped_hash_flags_B():
    raw = _raw(["Hero", "aaa", "bbb"])
    apa = {"_meta": {}, "Hero": {}, "A": {}, "bbb": {}}
    pn = {"anon_map": {"Hero": "Hero", "aaa": "A"}}             # bbb em falta
    sc = _scan_hand_integrity(raw, apa, pn)
    assert sc["b"] and "bbb" in sc["unmapped_hashes"]


# ── nome solto (players_list não ligado a hash) → C dispara ──────────────────
def test_loose_name_flags_C():
    raw = _raw(["Hero", "aaa"])
    apa = {"_meta": {}, "Hero": {}, "A": {}}
    pn = {"anon_map": {"Hero": "Hero", "aaa": "A"},
          "players_list": [{"name": "A"}, {"name": "Fantasma"}]}
    sc = _scan_hand_integrity(raw, apa, pn)
    assert sc["c"] and "Fantasma" in sc["loose_names"]


# ── propagação por hash no torneio (hash fixo por jogador; conflito não propõe) ─
from app.routers.table_ss import _propose_from_names


def test_propagation_single_name_proposes():
    r = _propose_from_names({"hangfish": ["GG-1", "GG-2", "GG-1"]})
    assert r["propose"] == "hangfish" and r["from"] == ["GG-1", "GG-2"]


def test_propagation_conflict_does_not_propose():
    r = _propose_from_names({"hangfish": ["GG-1"], "outro": ["GG-2"]})
    assert "conflict" in r and "propose" not in r
    assert set(r["conflict"]) == {"hangfish", "outro"}


def test_propagation_unknown_none():
    assert _propose_from_names({}) is None
