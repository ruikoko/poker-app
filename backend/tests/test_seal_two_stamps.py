# -*- coding: utf-8 -*-
"""Fecho do conceito SELO (21 Jul 2026) — regra dos DOIS CARIMBOS + canais sem carimbo.

Prova exigida pelo Rui:
- coroa carimbada sobrevive a: editar nome do PRÓPRIO lugar · editar nome de OUTRO
  lugar · backfill Gold · reenrich Gold baralhada · canal do lote (os CINCO);
- editar nome com grafia que não bate NÃO zera a coroa (nem selada nem não-selada);
- carimbo novo grava a origem (placa vs aceitacao); carimbo antigo fica intocável;
- nada de coroa sem carimbo gravado por estes canais.
"""
import json
from types import SimpleNamespace

import pytest

from app.services.eliminated_bounty import (
    is_bounty_sealed, merge_sealed_crowns_apa)
from app.routers.screenshot import _enrich_all_players_actions


# ── infra fake de BD (sem Postgres) ───────────────────────────────────────────

class FakeCursor:
    def __init__(self, store):
        self.store = store

    def execute(self, sql, params=None):
        self.store.append((sql, params))

    def executemany(self, sql, rows):
        self.store.append((sql, rows))

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class FakeConn:
    def __init__(self, store):
        self.store = store

    def cursor(self):
        return FakeCursor(self.store)

    def commit(self):
        pass

    def close(self):
        pass


def _unwrap(v):
    """str JSON ou psycopg2.extras.Json → dict."""
    v = getattr(v, "adapted", v)
    return json.loads(v) if isinstance(v, str) else v


def _last_update_apa(store):
    """Devolve o apa (dict) do último UPDATE hands SET all_players_actions."""
    for sql, params in reversed(store):
        if isinstance(sql, str) and sql.startswith("UPDATE hands SET all_players_actions"):
            return _unwrap(params[0])
    raise AssertionError("nenhum UPDATE de apa capturado")


# ── transportador de coroas do apa (T1) ───────────────────────────────────────

def test_merge_transporta_selada_e_nao_selada_por_chave():
    prev = {"_meta": {"bb": 1000},
            "h1": {"seat": 3, "bounty_value_usd": 125.0, "bounty_source": "manual",
                   "bounty_stamp": "placa", "crown_review": "x"},
            "h2": {"seat": 4, "bounty_value_usd": 80.0},
            "h3": {"seat": 5, "bounty_value_usd": 50.0}}
    fresh = {"_meta": {"bb": 1000}, "h1": {"seat": 3}, "h2": {"seat": 4}}
    n_sealed = merge_sealed_crowns_apa(prev, fresh)
    assert n_sealed == 1                                  # só h1 é selado
    assert fresh["h1"]["bounty_value_usd"] == 125.0
    assert fresh["h1"]["bounty_source"] == "manual"
    assert fresh["h1"]["bounty_stamp"] == "placa"
    assert "crown_review" not in fresh["h1"]              # selo fecha o por-rever
    assert fresh["h2"]["bounty_value_usd"] == 80.0        # não-selada também viaja
    assert "h3" not in fresh                              # sem alvo → não inventa
    assert is_bounty_sealed(fresh["h1"]) and not is_bounty_sealed(fresh["h2"])


def test_merge_inputs_invalidos_sao_noop():
    assert merge_sealed_crowns_apa(None, {}) == 0
    assert merge_sealed_crowns_apa({}, None) == 0
    assert merge_sealed_crowns_apa({"h": "lixo"}, {"h": {}}) == 0


# ── enrich: nunca inventar $0 numa reconstrução (T2) ─────────────────────────

def _fresh_apa():
    return {"_meta": {"bb": 1000},
            "Hero": {"is_hero": True, "seat": 1},
            "h1": {"seat": 3}, "h2": {"seat": 4}}


def test_cenario1_editar_nome_do_proprio_lugar_preserva_selada():
    # grafia NOVA não bate no players_list → a selada sobrevive intacta
    prev = {"h1": {"seat": 3, "bounty_value_usd": 125.0, "bounty_source": "manual"}}
    fresh = _fresh_apa()
    merge_sealed_crowns_apa(prev, fresh)
    out = _enrich_all_players_actions(
        fresh, {"h1": "Nome Corrigido"},
        {"players_list": [{"name": "Grafia Antiga", "bounty_value_usd": 55.0}]})
    assert out["h1"]["bounty_value_usd"] == 125.0
    assert out["h1"]["bounty_source"] == "manual"


def test_cenario2_editar_nome_de_outro_lugar_nao_toca_selada():
    # o lugar h2 é renomeado; a selada do h1 (cujo nome ATÉ bate no players_list
    # com um valor divergente da Vision) não é reescrita — o guard morde
    prev = {"h1": {"seat": 3, "bounty_value_usd": 125.0, "bounty_source": "manual"}}
    fresh = _fresh_apa()
    merge_sealed_crowns_apa(prev, fresh)
    out = _enrich_all_players_actions(
        fresh, {"h1": "Alice", "h2": "Nome Novo Do Outro"},
        {"players_list": [{"name": "Alice", "bounty_value_usd": 55.0}]})
    assert out["h1"]["bounty_value_usd"] == 125.0          # 55 da Vision NÃO entra
    assert out["h2"].get("bounty_value_usd") in (None, 0)  # h2 sem leitura/valor prévio


def test_grafia_que_nao_bate_nao_zera_coroa_nao_selada():
    # achado 21 Jul: renomear um seat com coroa NÃO-selada não pode pô-la a $0
    prev = {"h2": {"seat": 4, "bounty_value_usd": 80.0}}
    fresh = _fresh_apa()
    merge_sealed_crowns_apa(prev, fresh)
    out = _enrich_all_players_actions(
        fresh, {"h2": "Grafia Nova"},
        {"players_list": [{"name": "grafia velha", "bounty_value_usd": 60.0}]})
    assert out["h2"]["bounty_value_usd"] == 80.0


def test_regressao_ingest_fresco_continua_a_dar_zero():
    # mão nova, sem leitura da Vision p/ o seat → $0 = "por ler" (como sempre)
    out = _enrich_all_players_actions(_fresh_apa(), {}, {})
    assert out["h1"]["bounty_value_usd"] == 0


def test_vision_com_leitura_continua_a_escrever():
    out = _enrich_all_players_actions(
        _fresh_apa(), {"h1": "Bob"},
        {"players_list": [{"name": "Bob", "bounty_value_usd": 60.0}]})
    assert out["h1"]["bounty_value_usd"] == 60.0


# ── /set-anon-map: lápis do nome + canal do lote (T3+T4) ─────────────────────

def _wire_set_anon_map(monkeypatch, store, prev_apa, fresh_apa, pn, raw=""):
    from app.routers import table_ss as m

    def q(sql, params=None):
        if "prev_apa" in sql:
            return [{"id": 7, "prev_apa": json.loads(json.dumps(prev_apa))}]
        if "all_players_actions apa, player_names pn, raw" in sql:
            return [{"apa": json.loads(json.dumps(fresh_apa)),
                     "pn": json.loads(json.dumps(pn)), "raw": raw}]
        if sql.startswith("SELECT id, all_players_actions, player_names"):
            # lookup do set_bounties: estado PÓS-write do mapa (lê o último UPDATE)
            for s, p in reversed(store):
                if isinstance(s, str) and s.startswith("UPDATE hands SET all_players_actions"):
                    return [{"id": 7, "all_players_actions": p[0], "player_names": p[1]}]
            raise AssertionError("set_bounties correu antes do write do mapa")
        raise AssertionError("query inesperada: " + sql)

    monkeypatch.setattr(m, "query", q)
    monkeypatch.setattr(m, "get_conn", lambda: FakeConn(store))
    monkeypatch.setattr(m, "_reparse_apa_hash_keyed", lambda hid: True)
    import app.services.table_ss_deanon as deanon
    monkeypatch.setattr(deanon, "assert_deanon_consistency",
                        lambda raw, enriched, amap: ("ok", {}))
    import app.services.villain_rules as vr
    monkeypatch.setattr(vr, "apply_villain_rules", lambda hid: None)
    return m


def test_set_anon_map_preserva_selada_e_nao_selada(monkeypatch):
    store = []
    prev_apa = {"_meta": {"bb": 1000},
                "h1": {"seat": 3, "bounty_value_usd": 125.0, "bounty_source": "manual"},
                "h2": {"seat": 4, "bounty_value_usd": 80.0},
                "Hero": {"seat": 1, "is_hero": True}}
    fresh_apa = _fresh_apa()
    pn = {"players_list": [{"name": "Grafia Antiga", "bounty_value_usd": 55.0}],
          "hero": "H"}
    m = _wire_set_anon_map(monkeypatch, store, prev_apa, fresh_apa, pn)
    resp = m.set_anon_map_override(
        {"hand_id": "GG-1",
         "anon_map": {"h1": "Nome Corrigido", "h2": "Outro Nome", "Hero": "H"}},
        current_user={"email": "rui@x"})
    assert resp["sealed_crowns_kept"] == 1
    apa_written = _last_update_apa(store)
    assert apa_written["h1"]["bounty_value_usd"] == 125.0     # selada intacta
    assert apa_written["h1"]["bounty_source"] == "manual"
    assert apa_written["h2"]["bounty_value_usd"] == 80.0      # não-selada não zerada
    assert apa_written["h1"]["real_name"] == "Nome Corrigido"


def test_cenario5_canal_do_lote_sela_manual_e_deixa_rasto(monkeypatch):
    store = []
    logged = []
    prev_apa = {"_meta": {"bb": 1000}, "h1": {"seat": 3}, "Hero": {"seat": 1}}
    fresh_apa = {"_meta": {"bb": 1000}, "h1": {"seat": 3}, "Hero": {"seat": 1}}
    pn = {"players_list": [{"name": "Alvo", "bounty_value_usd": 10.0}], "hero": "H"}
    m = _wire_set_anon_map(monkeypatch, store, prev_apa, fresh_apa, pn)
    import app.services.crown_seal_log as csl
    monkeypatch.setattr(csl, "log_seals",
                        lambda rows, origin, actor="?": logged.append((rows, origin)) or len(rows))
    resp = m.set_anon_map_override(
        {"hand_id": "GG-1", "anon_map": {"h1": "Alvo", "Hero": "H"},
         "bounties": {"Alvo": 150.0}},
        current_user={"email": "rui@x"})
    br = resp["bounties_result"]
    assert br and br.get("updated") == ["Alvo"]
    # rasto: origem do canal do lote
    assert logged and logged[-1][1] == "table_ss.set_anon_map.bounties"
    # a escrita final (do set_bounties, DEPOIS do write do mapa) sela nas 2 gavetas
    pl_written = apa_written = None
    for sql, params in reversed(store):
        if isinstance(sql, str) and sql.startswith("UPDATE hands SET player_names=%s, all_players_actions"):
            pl_written = _unwrap(params[0]); apa_written = _unwrap(params[1]); break
    assert pl_written is not None, "set_bounties não escreveu"
    e = pl_written["players_list"][0]
    assert e["bounty_value_usd"] == 150.0 and e["bounty_source"] == "manual"
    assert "bounty_stamp" not in e                 # sem stamp = intocável (decisão 2)
    assert apa_written["h1"]["bounty_value_usd"] == 150.0
    assert apa_written["h1"]["bounty_source"] == "manual"


# ── /set-bounties: regra dos DOIS CARIMBOS (T7) ───────────────────────────────

def _wire_set_bounties(monkeypatch, store, apa, pn, logged):
    from app.routers import table_ss as m

    def q(sql, params=None):
        if sql.startswith("SELECT id, all_players_actions, player_names"):
            return [{"id": 7, "all_players_actions": json.loads(json.dumps(apa)),
                     "player_names": json.loads(json.dumps(pn))}]
        raise AssertionError("query inesperada: " + sql)

    monkeypatch.setattr(m, "query", q)
    monkeypatch.setattr(m, "get_conn", lambda: FakeConn(store))
    import app.services.crown_seal_log as csl
    monkeypatch.setattr(csl, "log_seals",
                        lambda rows, origin, actor="?": logged.append((rows, origin)) or len(rows))
    return m


def test_set_bounties_grava_stamp_valido_e_ignora_invalido(monkeypatch):
    store, logged = [], []
    apa = {"A": {"seat": 3, "real_name": "A"}}
    pn = {"players_list": [{"name": "A"}, {"name": "B", "bounty_value_usd": 70.0}]}
    m = _wire_set_bounties(monkeypatch, store, apa, pn, logged)
    m.set_bounties_override(
        {"hand_id": "GG-2", "bounties": {"A": 100.0}, "confirm": ["B"],
         "stamps": {"A": "placa", "B": "carimbo-inventado"},
         "origin": "teste.origem"},
        current_user={"email": "rui@x"})
    pl_written = json.loads([p for s, p in store
                             if isinstance(s, str) and s.startswith("UPDATE hands SET player_names")][-1][0])
    a = pl_written["players_list"][0]; b = pl_written["players_list"][1]
    assert a["bounty_value_usd"] == 100.0 and a["bounty_source"] == "manual"
    assert a["bounty_stamp"] == "placa"
    assert b.get("bounty_confirmed") is True
    assert "bounty_stamp" not in b                        # inválido → NÃO se inventa
    # rasto: stamp na linha do A, origem do payload
    rows, origin = logged[-1]
    assert origin == "teste.origem"
    row_a = [r for r in rows if r["player"] == "A"][0]
    assert row_a["stamp"] == "placa"
    row_b = [r for r in rows if r["player"] == "B"][0]
    assert row_b.get("stamp") is None


def test_set_bounties_sem_stamps_continua_como_antes(monkeypatch):
    store, logged = [], []
    apa = {}
    pn = {"players_list": [{"name": "A"}]}
    m = _wire_set_bounties(monkeypatch, store, apa, pn, logged)
    m.set_bounties_override(
        {"hand_id": "GG-2", "bounties": {"A": 100.0}}, current_user={"email": "r"})
    pl_written = json.loads([p for s, p in store
                             if isinstance(s, str) and s.startswith("UPDATE hands SET player_names")][-1][0])
    a = pl_written["players_list"][0]
    assert a["bounty_source"] == "manual" and "bounty_stamp" not in a


# ── cenário 3: backfill Gold respeita o selo (T6) ────────────────────────────

def test_cenario3_backfill_gold_nao_pisa_selada(monkeypatch):
    from app.routers import screenshot as sc
    store = []
    apa = {"_meta": {"bb": 1000},
           "h1": {"seat": 3, "real_name": "Alice",
                  "bounty_value_usd": 125.0, "bounty_source": "manual"},
           "h2": {"seat": 4, "real_name": "Bob"}}
    rows = [{"id": 7, "hand_id": "GG-3", "tournament_number": "T1",
             "all_players_actions": apa,
             "entry_players": [{"name": "Alice", "bounty_value_usd": 500.0},
                                {"name": "Bob", "bounty_value_usd": 60.0}]}]

    def q(sql, params=None):
        if "tournament_summaries" in sql:
            return [{"tournament_number": "T1", "buy_in_bounty": 50.0}]
        return rows

    monkeypatch.setattr(sc, "query", q)
    monkeypatch.setattr(sc, "get_conn", lambda: FakeConn(store))
    import app.services.eliminated_bounty as eb
    monkeypatch.setattr(eb, "scrub_and_persist", lambda hid, **kw: None)
    out = sc.backfill_gold_bounties(dry_run=False)
    assert out["players_sealed_skipped"] == 1
    assert apa["h1"]["bounty_value_usd"] == 125.0          # selada intacta ($500 da Gold NÃO entra)
    assert apa["h2"]["bounty_value_usd"] == 60.0           # não-selada preenchida


# ── cenário 4: reenrich Gold baralhada preserva o selo (T5) ──────────────────

def test_cenario4_reenrich_preserva_selada_mesmo_abaixo_do_floor(monkeypatch):
    from app.routers import screenshot as sc
    store = []
    prev_apa = {"_meta": {"bb": 1000},
                "h1": {"seat": 3, "bounty_value_usd": 20.0,   # < floor 25 → clamp mataria
                       "bounty_source": "manual"},
                "Hero": {"seat": 1, "is_hero": True}}
    fresh_apa = {"_meta": {"bb": 1000}, "h1": {"seat": 3}, "Hero": {"seat": 1}}
    row = {"id": 7, "hand_id": "GG-4", "raw": "raw", "tournament_number": "T1",
           "player_names": {"anon_map": {"h1": "Alice", "Hero": "H"}},
           "all_players_actions": prev_apa,
           "entry_players": [{"name": "Alice", "bounty_value_usd": 0.0}]}

    def q(sql, params=None):
        if "tournament_summaries" in sql:
            return [{"tournament_number": "T1", "buy_in_bounty": 50.0}]
        return [row]

    monkeypatch.setattr(sc, "query", q)
    monkeypatch.setattr(sc, "get_conn", lambda: FakeConn(store))
    monkeypatch.setattr(sc, "_seats_from_raw", lambda raw: [1, 2])
    monkeypatch.setattr(sc, "_SS_LVL_RE", SimpleNamespace(
        search=lambda s: SimpleNamespace(group=lambda i: "1,000")))
    monkeypatch.setattr(sc, "_scramble_state", lambda *a: (True, False))
    monkeypatch.setattr(sc, "_final_chips_by_token", lambda *a: {})
    monkeypatch.setattr(sc, "_stack_gate_ok", lambda *a: (True, 1, 1))
    import app.parsers.gg_hands as ggp
    monkeypatch.setattr(ggp, "parse_hands",
                        lambda b, n: ([{"all_players_actions":
                                        json.loads(json.dumps(fresh_apa))}], []))
    import app.services.eliminated_bounty as eb
    monkeypatch.setattr(eb, "scrub_and_persist", lambda hid, **kw: None)
    sc.reenrich_scrambled_gold(dry_run=False)
    apa_written = _last_update_apa(store)
    assert apa_written["h1"]["bounty_value_usd"] == 20.0    # selada sobrevive ao reenrich
    assert apa_written["h1"]["bounty_source"] == "manual"   # e ao clamp do floor


# ── crown_seal_log: seal_row carrega o stamp ─────────────────────────────────

def test_seal_row_com_e_sem_stamp():
    from app.services.crown_seal_log import seal_row
    r1 = seal_row("GG-1", "A", 10, 20, stamp="aceitacao")
    r2 = seal_row("GG-1", "B", None, 5)
    assert r1["stamp"] == "aceitacao" and r2["stamp"] is None
