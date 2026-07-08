"""APA §B.6 Fase 3 — propagação de nomes por hash. Testes das guardas + motor (puros)."""
from app.services import name_propagation as np


def _hand(hand_id, mm, anon_map, seats, *, tagged=True, verified=False, site="GGPoker", hid=None):
    """Constrói uma linha de mão sintética. `seats` = lista de hashes (Hero implícito)."""
    lines = ["Poker Hand #x", "Table '1' 8-max Seat #1 is the button",
             "Seat 1: Hero (1000 in chips)"]
    for i, h in enumerate(seats, start=2):
        lines.append(f"Seat {i}: {h} (1000 in chips)")
    pn = {"match_method": mm, "anon_map": dict(anon_map)}
    if verified:
        pn["verified_by_user"] = True
    return {
        "id": hid if hid is not None else abs(hash(hand_id)) % 100000,
        "hand_id": hand_id, "site": site, "raw": "\n".join(lines) + "\n",
        "player_names": pn,
        "hm3_tags": (["icm"] if tagged else []), "discord_tags": [],
    }


# ── guarda (a) — só FONTE FORTE semeia ────────────────────────────────────────

def test_guard_a_weak_does_not_seed():
    weak = _hand("GG-1", "table_ss", {"3b4cd0c7": "Alice"}, ["3b4cd0c7"])
    clean, quar = np.build_name_map([weak])
    assert clean == {}            # via fraca não semeia
    assert quar == []


def test_strong_position_v3_seeds():
    strong = _hand("GG-1", "position_v3", {"3b4cd0c7": "Alice"}, ["3b4cd0c7"])
    clean, quar = np.build_name_map([strong])
    assert clean["3b4cd0c7"]["name"] == "Alice"
    assert clean["3b4cd0c7"]["verified"] is False   # position_v3 = por verificar


def test_verified_by_user_seeds_verified():
    s = _hand("GG-1", "table_ss", {"3b4cd0c7": "Alice"}, ["3b4cd0c7"], verified=True)
    clean, _ = np.build_name_map([s])
    assert clean["3b4cd0c7"]["verified"] is True


# ── guarda (b) — nome-já-usado (mesmo nome em 2 hashes) → quarentena ──────────

def test_guard_b_name_two_hashes_quarantines_both():
    h1 = _hand("GG-1", "position_v3", {"3b4cd0c7": "Bob"}, ["3b4cd0c7"])
    h2 = _hand("GG-2", "position_v3", {"89ef4cba": "Bob"}, ["89ef4cba"])
    clean, quar = np.build_name_map([h1, h2])
    assert clean == {}            # nenhum entra no mapa (veneno)
    q = [x for x in quar if x["kind"] == "name_2_hash"]
    assert len(q) == 1 and set(q[0]["candidates"]) == {"3b4cd0c7", "89ef4cba"}


# ── guarda (c) — conflito no mesmo hash: nomes diferentes → quarentena ────────

def test_guard_c_same_hash_different_names_quarantines():
    h1 = _hand("GG-1", "position_v3", {"3b4cd0c7": "Daniel Filipe"}, ["3b4cd0c7"])
    h2 = _hand("GG-2", "position_v3", {"3b4cd0c7": "Mikhail Petrov"}, ["3b4cd0c7"])
    clean, quar = np.build_name_map([h1, h2])
    assert "3b4cd0c7" not in clean
    q = [x for x in quar if x["kind"] == "same_hash"]
    assert len(q) == 1 and set(q[0]["candidates"]) == {"Daniel Filipe", "Mikhail Petrov"}


# ── OCR-merge — variantes do mesmo nome fundem-se (não vão à quarentena) ──────

def test_ocr_merge_truncation_variants():
    h1 = _hand("GG-1", "position_v3", {"3b4cd0c7": "Footloose r.."}, ["3b4cd0c7"])
    h2 = _hand("GG-2", "position_v3", {"3b4cd0c7": "Footlose r.."}, ["3b4cd0c7"])
    clean, quar = np.build_name_map([h1, h2])
    assert clean["3b4cd0c7"]["name"] == "Footloose r.."   # canónico (mais completo)
    assert quar == []


def test_ocr_variant_rejects_first_name_collision():
    # o critério ENDURECIDO NÃO funde nomes diferentes com 1º nome igual
    assert np._ocr_variant("Daniel Filipe", "Daniel Ferreira") is False
    assert np._ocr_variant("Footloose r..", "Footlose r..") is True
    assert np._ocr_variant("KazuyoshiFu..", "KazuyoshiFu...") is True   # truncagem
    assert np._ocr_variant("skinnybig0", "skinnybigb0") is True         # 1 char OCR


# ── guarda (d) — sem semente forte → mapa vazio, zero escrita ────────────────

def test_guard_d_no_strong_seed_blank_honest():
    # mão tagada com hash SEM nome + nenhuma fonte forte → fica branco, zero escrita
    tagged_blank = _hand("GG-1", "table_ss", {}, ["3b4cd0c7"], tagged=True)
    clean, quar = np.build_name_map([tagged_blank])
    assert clean == {}
    plan = np.propagation_plan([tagged_blank], clean)
    assert plan["stats"]["fills_total"] == 0
    assert "3b4cd0c7" in plan["blank_hashes"]   # branco honesto


# ── propagação — só-tagadas + preenche brancos ───────────────────────────────

def test_propagation_fills_only_tagged_blanks():
    seed = _hand("GG-seed", "position_v3", {"3b4cd0c7": "Alice"}, ["3b4cd0c7"])
    tagged = _hand("GG-tag", "table_ss", {}, ["3b4cd0c7"], tagged=True, hid=42)
    untagged = _hand("GG-untag", "table_ss", {}, ["3b4cd0c7"], tagged=False, hid=43)
    clean, _ = np.build_name_map([seed, tagged, untagged])
    plan = np.propagation_plan([seed, tagged, untagged], clean)
    ids = [c["db_id"] for c in plan["changes"]]
    assert 42 in ids and 43 not in ids          # só a tagada é preenchida
    fill = next(c for c in plan["changes"] if c["db_id"] == 42)
    assert fill["fills"]["3b4cd0c7"] == "Alice"


def test_propagation_idempotent_skips_own_names():
    # a mão tagada JÁ tem o hash no seu anon_map → não é branco → não preenche
    seed = _hand("GG-seed", "position_v3", {"3b4cd0c7": "Alice"}, ["3b4cd0c7"])
    tagged = _hand("GG-tag", "table_ss", {"3b4cd0c7": "Alice"}, ["3b4cd0c7"], tagged=True, hid=42)
    clean, _ = np.build_name_map([seed, tagged])
    plan = np.propagation_plan([seed, tagged], clean)
    assert plan["stats"]["fills_total"] == 0
    assert plan["changes"] == []


def test_apply_propagation_dry_run_returns_plan():
    seed = _hand("GG-seed", "position_v3", {"3b4cd0c7": "Alice"}, ["3b4cd0c7"])
    tagged = _hand("GG-tag", "table_ss", {}, ["3b4cd0c7"], tagged=True, hid=42)
    clean, _ = np.build_name_map([seed, tagged])
    res = np.apply_propagation([seed, tagged], clean, dry_run=True)
    assert res["dry_run"] is True and res["fills_total"] == 1


# ── conflict_sides — os DOIS lados com contexto (mãos + fonte) p/ o Rui decidir ─

def test_conflict_sides_name_2_hash_two_sides_with_source():
    h1 = _hand("GG-1", "position_v3", {"3b4cd0c7": "Bob"}, ["3b4cd0c7"], hid=1)
    weak = _hand("GG-3", "table_ss", {"3b4cd0c7": "Bob"}, ["3b4cd0c7"], hid=3)   # via fraca
    h2 = _hand("GG-2", "position_v3", {"89ef4cba": "Bob"}, ["89ef4cba"], hid=2)
    item = {"kind": "name_2_hash", "conflict_key": "Bob",
            "candidates": ["3b4cd0c7", "89ef4cba"]}
    sides = np.conflict_sides([h1, weak, h2], item)
    assert {s["hash"] for s in sides} == {"3b4cd0c7", "89ef4cba"}
    s1 = next(s for s in sides if s["hash"] == "3b4cd0c7")
    assert {a["hand_id"] for a in s1["appearances"]} == {"GG-1", "GG-3"}
    assert {a["source"] for a in s1["appearances"]} == {"strong", "weak"}
    assert s1["appearances"][0]["source"] == "strong"     # fortes primeiro
    assert set(s1["db_ids"]) == {1, 3}
    s2 = next(s for s in sides if s["hash"] == "89ef4cba")
    assert [a["hand_id"] for a in s2["appearances"]] == ["GG-2"]


def test_conflict_sides_same_hash_one_side_per_variant():
    h1 = _hand("GG-1", "position_v3", {"3b4cd0c7": "Daniel Filipe"}, ["3b4cd0c7"], hid=1)
    h2 = _hand("GG-2", "position_v3", {"3b4cd0c7": "Mikhail Petrov"}, ["3b4cd0c7"], hid=2)
    item = {"kind": "same_hash", "conflict_key": "3b4cd0c7",
            "candidates": ["Daniel Filipe", "Mikhail Petrov"]}
    sides = np.conflict_sides([h1, h2], item)
    assert {s["name"] for s in sides} == {"Daniel Filipe", "Mikhail Petrov"}
    sd = next(s for s in sides if s["name"] == "Daniel Filipe")
    assert [a["hand_id"] for a in sd["appearances"]] == ["GG-1"]
    assert sd["db_ids"] == [1]
