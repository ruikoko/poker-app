"""APA §B.6 Fase 3 — propagação de nomes por hash. Testes das guardas + motor (puros)."""
from datetime import datetime

from app.services import name_propagation as np


def _hand(hand_id, mm, anon_map, seats, *, tagged=True, verified=False, site="GGPoker",
          hid=None, played_at=None, stacks=None, extra_lines=""):
    """Constrói uma linha de mão sintética. `seats` = lista de hashes (Hero implícito).
    `stacks` opcional = dict hash→stack (default 1000). `extra_lines` = acções do raw
    (all-in / collected) p/ o detector de bust."""
    stacks = stacks or {}
    lines = ["Poker Hand #x", "Table '1' 8-max Seat #1 is the button",
             "Seat 1: Hero (1000 in chips)"]
    for i, h in enumerate(seats, start=2):
        lines.append(f"Seat {i}: {h} ({stacks.get(h, 1000)} in chips)")
    raw = "\n".join(lines) + "\n" + (extra_lines or "")
    pn = {"match_method": mm, "anon_map": dict(anon_map)}
    if verified:
        pn["verified_by_user"] = True
    return {
        "id": hid if hid is not None else abs(hash(hand_id)) % 100000,
        "hand_id": hand_id, "site": site, "raw": raw,
        "player_names": pn, "played_at": played_at,
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


# ── strong_weak_mismatch — hash com FORTE X + FRACA divergente Y (novo kind) ──

def test_strong_weak_mismatch_detected():
    # 93d63976: FORTE "Vadzim Khazanau" + FRACA "Diego Emperador" → cartão; forte mantém-se
    strong = _hand("GG-s", "position_v3", {"93d63976": "Vadzim Khazanau"}, ["93d63976"], hid=1)
    weak = _hand("GG-w", "table_ss", {"93d63976": "Diego Emperador"}, ["93d63976"], hid=2)
    clean, quar = np.build_name_map([strong, weak])
    assert clean["93d63976"]["name"] == "Vadzim Khazanau"     # o FORTE fica no mapa (propaga)
    m = [q for q in quar if q["kind"] == "strong_weak_mismatch"]
    assert len(m) == 1 and m[0]["hash"] == "93d63976"
    assert set(m[0]["candidates"]) == {"Vadzim Khazanau", "Diego Emperador"}
    assert m[0]["hands"] == ["GG-w"]                          # a mão da leitura fraca


def test_strong_weak_mismatch_ignores_ocr_variant():
    # FRACA que é só truncagem/OCR do forte → NÃO é mismatch (é o mesmo jogador)
    strong = _hand("GG-s", "position_v3", {"3b4cd0c7": "Footloose r.."}, ["3b4cd0c7"], hid=1)
    weak = _hand("GG-w", "table_ss", {"3b4cd0c7": "Footlose r.."}, ["3b4cd0c7"], hid=2)
    _, quar = np.build_name_map([strong, weak])
    assert [q for q in quar if q["kind"] == "strong_weak_mismatch"] == []


def test_strong_weak_mismatch_needs_strong_seed():
    # só leituras FRACAS (sem forte) → não semeia nem gera cartão (guarda (a) manda)
    weak = _hand("GG-w", "table_ss", {"3b4cd0c7": "Diego"}, ["3b4cd0c7"], hid=2)
    clean, quar = np.build_name_map([weak])
    assert clean == {} and [q for q in quar if q["kind"] == "strong_weak_mismatch"] == []


def test_apply_decisions_strong_weak_mismatch_confirms_strong():
    # confirmar o forte (decision 'chosen') → hash fica VERIFICADO (dispara o scrub das fracas)
    quar = [{"kind": "strong_weak_mismatch", "hash": "93d63976", "name": "Vadzim Khazanau",
             "candidates": ["Diego Emperador", "Vadzim Khazanau"], "hands": ["GG-w"]}]
    clean = {"93d63976": {"name": "Vadzim Khazanau", "verified": False}}
    decisions = {("strong_weak_mismatch", "93d63976"):
                 {"decision": "chosen", "chosen_name": "Vadzim Khazanau", "chosen_hash": None}}
    clean2, still = np._apply_decisions_to_map(clean, quar, decisions)
    assert clean2["93d63976"] == {"name": "Vadzim Khazanau", "verified": True}
    assert still == []


def test_conflict_sides_strong_weak_mismatch_marks_source():
    strong = _hand("GG-s", "position_v3", {"93d63976": "Vadzim Khazanau"}, ["93d63976"], hid=1)
    weak = _hand("GG-w", "table_ss", {"93d63976": "Diego Emperador"}, ["93d63976"], hid=2)
    item = {"kind": "strong_weak_mismatch", "conflict_key": "93d63976",
            "candidates": ["Diego Emperador", "Vadzim Khazanau"]}
    sides = np.conflict_sides([strong, weak], item)
    assert next(s for s in sides if s["name"] == "Vadzim Khazanau")["appearances"][0]["source"] == "strong"
    assert next(s for s in sides if s["name"] == "Diego Emperador")["appearances"][0]["source"] == "weak"


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


def test_propagation_corrects_weak_misread_when_map_verified():
    # mão FRACA (table_ss) com misread "Vadzim Khazanau" no hash; mapa VERIFICADO diz
    # "OHmyBUDDHA" (decisão de re-entrada) → corrige (não deixa a leitura errada agarrada).
    tagged_weak = _hand("GG-072", "table_ss", {"5ee4d246": "Vadzim Khazanau"},
                        ["5ee4d246"], tagged=True, hid=9306)
    clean = {"5ee4d246": {"name": "OHmyBUDDHA", "verified": True}}
    plan = np.propagation_plan([tagged_weak], clean)
    ch = next(c for c in plan["changes"] if c["db_id"] == 9306)
    assert ch["fills"]["5ee4d246"] == "OHmyBUDDHA"     # sobrescreve o misread
    assert ch["corrected"]["5ee4d246"] == "Vadzim Khazanau"
    assert plan["stats"]["corrections_total"] == 1


def test_propagation_does_not_correct_strong_hand():
    # mão FORTE (position_v3) com um nome diferente NÃO é sobrescrita mesmo por mapa verificado
    strong = _hand("GG-s", "position_v3", {"5ee4d246": "Real Name"}, ["5ee4d246"],
                   tagged=True, hid=1)
    clean = {"5ee4d246": {"name": "OHmyBUDDHA", "verified": True}}
    plan = np.propagation_plan([strong], clean)
    assert plan["stats"]["corrections_total"] == 0
    assert plan["changes"] == []


def test_propagation_does_not_overwrite_when_map_unverified():
    # mapa NÃO-verificado (position_v3, por verificar) NÃO sobrescreve nome fraco existente
    # (o upgrade fraco→forte continua deferido — só decisão MANUAL corrige).
    weak = _hand("GG-w", "table_ss", {"5ee4d246": "Old Weak"}, ["5ee4d246"],
                 tagged=True, hid=2)
    clean = {"5ee4d246": {"name": "New Strong", "verified": False}}
    plan = np.propagation_plan([weak], clean)
    assert plan["stats"]["corrections_total"] == 0
    assert plan["changes"] == []


def test_propagation_idempotent_skips_own_names():
    # a mão tagada JÁ tem o hash no seu anon_map → não é branco → não preenche
    seed = _hand("GG-seed", "position_v3", {"3b4cd0c7": "Alice"}, ["3b4cd0c7"])
    tagged = _hand("GG-tag", "table_ss", {"3b4cd0c7": "Alice"}, ["3b4cd0c7"], tagged=True, hid=42)
    clean, _ = np.build_name_map([seed, tagged])
    plan = np.propagation_plan([seed, tagged], clean)
    assert plan["stats"]["fills_total"] == 0
    assert plan["changes"] == []


def test_fill_entry_hash_keyed():
    apa = {"_meta": {}, "5ee4d246": {"real_name": "Vadzim Khazanau", "seat": 6}}
    anon = {"5ee4d246": "Vadzim Khazanau"}
    assert np._fill_entry(apa, anon, "5ee4d246", "OHmyBUDDHA", True) is True
    assert apa["5ee4d246"]["real_name"] == "OHmyBUDDHA"
    assert anon["5ee4d246"] == "OHmyBUDDHA"


def test_fill_entry_name_keyed_legacy():
    # apa LEGADO name-keyed: 5ee4d246 NÃO é chave; a entrada vive sob o nome actual.
    apa = {"_meta": {}, "Vadzim Khazanau": {"real_name": "Vadzim Khazanau", "seat": 6}}
    anon = {"5ee4d246": "Vadzim Khazanau"}
    assert np._fill_entry(apa, anon, "5ee4d246", "OHmyBUDDHA", True) is True
    assert apa["Vadzim Khazanau"]["real_name"] == "OHmyBUDDHA"   # corrige a entrada legado
    assert anon["5ee4d246"] == "OHmyBUDDHA"                      # anon_map (hash) fica certo


def test_fill_entry_idempotent():
    apa = {"5ee4d246": {"real_name": "OHmyBUDDHA"}}
    anon = {"5ee4d246": "OHmyBUDDHA"}
    assert np._fill_entry(apa, anon, "5ee4d246", "OHmyBUDDHA", True) is False   # já certo


def test_fill_entry_missing_entry_returns_false():
    # hash sem entrada nem no apa nem via nome → não inventa
    apa = {"_meta": {}, "other": {"real_name": "X"}}
    anon = {}
    assert np._fill_entry(apa, anon, "5ee4d246", "OHmyBUDDHA", True) is False


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


# ── OBRA 2a — bloco de Seats do raw (seat/hash/stack + disputado) ─────────────

def test_seat_block_parses_seat_hash_stack():
    raw = ("Table x\nSeat 1: Hero (30000 in chips)\n"
           "Seat 2: 3b4cd0c7 (20,000 in chips)\nSeat 3: 89ef4cba (40000, 50€ bounty)\n")
    sb = np.seat_block(raw)
    assert [s["seat"] for s in sb] == [1, 2, 3]
    assert sb[1] == {"seat": 2, "hash": "3b4cd0c7", "stack": 20000}   # vírgula limpa
    assert sb[2]["stack"] == 40000                                     # WN "(40000, 50€ bounty)"


def test_conflict_sides_appearances_carry_seats_with_disputed():
    h1 = _hand("GG-1", "position_v3", {"3b4cd0c7": "Bob"}, ["3b4cd0c7", "89ef4cba"], hid=1)
    item = {"kind": "name_2_hash", "conflict_key": "Bob",
            "candidates": ["3b4cd0c7", "89ef4cba"]}
    sides = np.conflict_sides([h1], item)
    s = next(x for x in sides if x["hash"] == "3b4cd0c7")
    ap = s["appearances"][0]
    disputed = [x["hash"] for x in ap["seats"] if x["disputed"]]
    assert disputed == ["3b4cd0c7"]                    # só o hash do lado é destacado


# ── OBRA 1 — classificador de RE-ENTRADA + decisão 'reentry' ─────────────────

_HA, _HB = "b0b40d2c", "d07fa3d8"   # os 2 hashes do Olisadebee (re-entry)


def _reentry_item():
    return {"kind": "name_2_hash", "name": "Olisadebee", "conflict_key": "Olisadebee",
            "candidates": [_HA, _HB]}


def test_reentry_hint_likely_when_disjoint_strong_same_nick():
    early = _hand("GG-6159", "position_v3", {_HA: "Olisadebee"}, [_HA],
                  played_at=datetime(2026, 5, 28, 20, 50))
    late = _hand("GG-6515", "position_v3", {_HB: "Olisadebee"}, [_HB],
                 played_at=datetime(2026, 5, 28, 21, 25))
    hint = np.reentry_hint([early, late], _reentry_item())
    assert hint["applies"] and hint["likely_reentry"] is True
    assert hint["co_present"] is False and hint["disjoint_windows"] is True
    assert hint["same_nick"] and hint["both_strong"]


def test_reentry_hint_co_present_is_hard_poison():
    # os 2 hashes na MESMA mão → impossível ser 1 pessoa → nunca re-entrada
    both = _hand("GG-1", "position_v3", {_HA: "Olisadebee"}, [_HA, _HB],
                 played_at=datetime(2026, 5, 28, 21, 0))
    other = _hand("GG-2", "position_v3", {_HB: "Olisadebee"}, [_HB],
                  played_at=datetime(2026, 5, 28, 21, 30))
    hint = np.reentry_hint([both, other], _reentry_item())
    assert hint["co_present"] is True and hint["likely_reentry"] is False


def test_reentry_hint_overlapping_windows_not_likely():
    a1 = _hand("GG-1", "position_v3", {_HA: "Olisadebee"}, [_HA], played_at=datetime(2026, 5, 28, 20, 50))
    a2 = _hand("GG-2", "position_v3", {_HA: "Olisadebee"}, [_HA], played_at=datetime(2026, 5, 28, 21, 30))
    b1 = _hand("GG-3", "position_v3", {_HB: "Olisadebee"}, [_HB], played_at=datetime(2026, 5, 28, 21, 0))
    hint = np.reentry_hint([a1, a2, b1], _reentry_item())
    assert hint["disjoint_windows"] is False and hint["likely_reentry"] is False


def test_reentry_hint_weak_side_not_likely():
    early = _hand("GG-1", "position_v3", {_HA: "Olisadebee"}, [_HA], played_at=datetime(2026, 5, 28, 20, 50))
    late = _hand("GG-2", "table_ss", {_HB: "Olisadebee"}, [_HB], played_at=datetime(2026, 5, 28, 21, 25))
    hint = np.reentry_hint([early, late], _reentry_item())
    assert hint["both_strong"] is False and hint["likely_reentry"] is False


def test_apply_decisions_reentry_puts_name_on_both_hashes():
    quar = [{"kind": "name_2_hash", "name": "Olisadebee", "candidates": [_HA, _HB],
             "hands": ["GG-6159", "GG-6515"]}]
    decisions = {("name_2_hash", "Olisadebee"):
                 {"decision": "reentry", "chosen_name": "Olisadebee", "chosen_hash": None}}
    clean, still = np._apply_decisions_to_map({}, quar, decisions)
    assert clean[_HA] == {"name": "Olisadebee", "verified": True}
    assert clean[_HB] == {"name": "Olisadebee", "verified": True}   # nome nos DOIS
    assert still == []                                              # sai da quarentena


# ── OBRA (upgrade) — evidência DURA: bust + bala fresca + gap → 'confirmed' ────

_EARLY, _LATE, _WINNER = "e4224f2", "e8b6dae9", "0e0cafc0"
_START = 25000
_D = lambda hh, mm: datetime(2026, 6, 23, hh, mm)   # noqa: E731


def _amigo_item():
    return {"kind": "name_2_hash", "name": "AmigoCrypto", "conflict_key": "AmigoCrypto",
            "candidates": [_EARLY, _LATE]}


def _bust_extra():
    return ("e4224f2: calls 12836 and is all-in\n"
            "e4224f2: shows [Ad Jd] (two pair, Jacks and Fives)\n"
            "0e0cafc0 collected 45832 from pot\n"
            "Seat 3: 0e0cafc0 (small blind) showed [Td Tc] and won (45832)\n")


def _amigo_hands(*, bust=True, late_stack=_START):
    # 1ª mão do torneio (arranque, define start_stack = 25000)
    start = _hand("GG-A0", "position_v3", {_EARLY: "AmigoCrypto"}, [_EARLY, _WINNER],
                  stacks={_EARLY: _START, _WINNER: _START}, played_at=_D(17, 32), hid=10)
    # ÚLTIMA mão do early: bust (all-in perdido) OU normal (não legível)
    extra = _bust_extra() if bust else "e4224f2: folds\n"
    last = _hand("GG-6107814611", "position_v3", {_EARLY: "AmigoCrypto"}, [_EARLY, _WINNER],
                 stacks={_EARLY: 13000, _WINNER: 20000}, played_at=_D(18, 18),
                 extra_lines=extra, hid=11)
    # 1ª mão do late (re-buy): stack fresco, 2m24s depois
    rebuy = _hand("GG-6107814854", "position_v3", {_LATE: "AmigoCrypto"}, [_LATE, _WINNER],
                  stacks={_LATE: late_stack, _WINNER: 30000}, played_at=_D(18, 20), hid=12)
    return [start, last, rebuy]


def test_reentry_confirmed_bust_lost_fresh_bala_short_gap():
    hint = np.reentry_hint(_amigo_hands(), _amigo_item())
    assert hint["level"] == "confirmed"
    assert hint["bust"]["hash"] == _EARLY and hint["bust"]["lost"] is True
    assert hint["bust"]["hand_id"] == "GG-6107814611" and hint["bust"]["db_id"] == 11
    assert hint["rebuy"]["hash"] == _LATE and hint["rebuy"]["fresh"] is True
    assert hint["rebuy"]["start_stack"] == _START
    assert hint["gap_seconds"] == 120                       # 18:18 → 18:20 = 2 min


def test_reentry_bust_not_legible_stays_likely_not_demoted():
    # última mão do early NÃO mostra all-in (coverage/HH) → não promove, mas NÃO despromove
    hint = np.reentry_hint(_amigo_hands(bust=False), _amigo_item())
    assert hint["level"] == "likely"
    assert hint["likely_reentry"] is True
    assert hint["bust"]["lost"] is False


def test_reentry_big_inherited_stack_not_fresh_stays_likely():
    # 2ª entrada com stack GRANDE (2× arranque) = herdado, não re-buy → fora da banda
    hint = np.reentry_hint(_amigo_hands(late_stack=_START * 2), _amigo_item())
    assert hint["rebuy"]["fresh"] is False
    assert hint["level"] == "likely"                        # bust legível mas bala não-fresca


def test_reentry_same_nick_ignores_weak_misread():
    # OHmyBUDDHA: um lado tem leitura FORTE "OHmyBUDDHA" + misread FRACO "Vadzim Khazanau".
    # O same_nick usa só a FORTE → não se deixa enganar pelo misread → re-entry detectável.
    early_strong = _hand("GG-1", "position_v3", {_EARLY: "OHmyBUDDHA"}, [_EARLY, _WINNER],
                         stacks={_EARLY: _START, _WINNER: _START}, played_at=_D(19, 15), hid=1)
    early_weak = _hand("GG-2", "table_ss", {_EARLY: "Vadzim Khazanau"}, [_EARLY, _WINNER],
                       stacks={_EARLY: 5000, _WINNER: 20000}, played_at=_D(19, 25),
                       extra_lines=_bust_extra().replace("e4224f2", _EARLY), hid=2)
    late = _hand("GG-3", "position_v3", {_LATE: "OHmyBUDDHA"}, [_LATE, _WINNER],
                 stacks={_LATE: _START, _WINNER: 30000}, played_at=_D(19, 27), hid=3)
    item = {"kind": "name_2_hash", "conflict_key": "OHmyBUDDHA", "candidates": [_EARLY, _LATE]}
    hint = np.reentry_hint([early_strong, early_weak, late], item)
    assert hint["same_nick"] is True          # FORTE dos 2 lados = OHmyBUDDHA (ignora o fraco)
    assert hint["level"] == "confirmed"        # bust (early_weak) + bala fresca + gap curto
