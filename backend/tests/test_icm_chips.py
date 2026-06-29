"""Unit tests para #ICM-CHIPS-USE-TS-FINAL-FIELD-GG — derivação do total de
fichas do ICM a partir do campo FINAL do TS (em vez da foto parcial do lobby).

Cobre:
  - `_fresh_starting_stack` — salvaguarda da "mão fresca" (pura).
  - `lookup_icm_chips` — lookup em lote (query mockada).
"""
import app.services.hrc_queue as hq
from app.services.hrc_queue import _fresh_starting_stack, lookup_icm_chips


def _apa(level, stacks, hero_idx=0):
    """Constrói um all_players_actions com `stacks` (lista) e o nível dado."""
    out = {"_meta": {"level": level, "sb": 50, "bb": 100, "ante": 10,
                     "num_players": len(stacks)}}
    for i, s in enumerate(stacks):
        out[f"p{i}"] = {"seat": i + 1, "position": "?", "stack": s,
                        "stack_bb": s / 100, "actions": {},
                        "is_hero": i == hero_idx}
    return out


# ── _fresh_starting_stack ─────────────────────────────────────────────────────

def test_fresh_stack_level1_equal_round_returns_stack():
    assert _fresh_starting_stack(_apa(1, [10000, 10000, 10000])) == 10000.0


def test_fresh_stack_rejects_non_level_1():
    assert _fresh_starting_stack(_apa(2, [10000, 10000])) is None


def test_fresh_stack_rejects_unequal_stacks():
    # mão a meio do torneio (já houve acção) — stacks diferentes
    assert _fresh_starting_stack(_apa(1, [10000, 8000, 12000])) is None


def test_fresh_stack_rejects_non_round_stack():
    assert _fresh_starting_stack(_apa(1, [9999.5, 9999.5])) is None


def test_fresh_stack_rejects_hero_mismatch():
    apa = _apa(1, [10000, 10000])
    apa["p0"]["stack"] = 12000  # Hero diverge do comum → incoerente
    assert _fresh_starting_stack(apa) is None


def test_fresh_stack_rejects_missing_or_bad_stack():
    apa = _apa(1, [10000, 10000])
    apa["p1"]["stack"] = None
    assert _fresh_starting_stack(apa) is None


def test_fresh_stack_rejects_empty_or_meta_only():
    assert _fresh_starting_stack({"_meta": {"level": 1}}) is None
    assert _fresh_starting_stack({}) is None
    assert _fresh_starting_stack(None) is None


def test_fresh_stack_parses_json_string():
    import json
    s = json.dumps(_apa(1, [25000, 25000]))
    assert _fresh_starting_stack(s) == 25000.0


def test_fresh_stack_bad_json_string_returns_none():
    assert _fresh_starting_stack("{not json") is None


# ── lookup_icm_chips ──────────────────────────────────────────────────────────

class _QueryStub:
    """Devolve respostas em sequência por chamada a `query`."""
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def __call__(self, sql, params=None):
        self.calls.append((sql, params))
        return self.responses.pop(0)


def test_lookup_icm_chips_happy_path(monkeypatch):
    rows = [{"site": "GGPoker", "tournament_number": "292447656"}]
    stub = _QueryStub([
        [{"tournament_number": "292447656", "total_players": 151}],          # TS
        [{"tournament_number": "292447656",
          "all_players_actions": _apa(1, [10000, 10000, 10000, 10000])}],    # 1ª mão
    ])
    monkeypatch.setattr(hq, "query", stub)
    out = lookup_icm_chips(rows)
    assert out == {("GGPoker", "292447656"): {
        "total_chips": 1510000.0, "total_players": 151, "starting_stack": 10000.0,
    }}


def test_lookup_icm_chips_skips_when_first_hand_not_fresh(monkeypatch):
    rows = [{"site": "GGPoker", "tournament_number": "T1"}]
    stub = _QueryStub([
        [{"tournament_number": "T1", "total_players": 100}],
        [{"tournament_number": "T1",
          "all_players_actions": _apa(5, [8000, 12000])}],  # nível 5, desigual
    ])
    monkeypatch.setattr(hq, "query", stub)
    assert lookup_icm_chips(rows) == {}


def test_lookup_icm_chips_ignores_non_gg(monkeypatch):
    rows = [
        {"site": "Winamax", "tournament_number": "W1"},
        {"site": "PokerStars", "tournament_number": "P1"},
    ]
    # nem deve chegar a fazer query (sem tn GG)
    called = {"n": 0}

    def _q(sql, params=None):
        called["n"] += 1
        return []
    monkeypatch.setattr(hq, "query", _q)
    assert lookup_icm_chips(rows) == {}
    assert called["n"] == 0


def test_lookup_icm_chips_empty_when_no_ts(monkeypatch):
    rows = [{"site": "GGPoker", "tournament_number": "T1"}]
    stub = _QueryStub([[]])  # TS query vazia → para aí
    monkeypatch.setattr(hq, "query", stub)
    assert lookup_icm_chips(rows) == {}
    assert len(stub.calls) == 1  # não chega a procurar a 1ª mão
