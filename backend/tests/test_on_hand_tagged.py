# -*- coding: utf-8 -*-
"""Gatilho único do re-tag (`study_pipeline.on_hand_tagged`, 21 Jul 2026) — Fase 1.

Prova:
- o pipeline corre villains → scrub → propagação(tn) → FT, com auditoria;
- mão destagada: villains+scrub correm, propagação/FT não (nada estreitado);
- caso real GG-6090481360 (forma): re-tag → coroa fantasma do bustado anulada +
  'por rever', vivo-$0 marcado — através do pipeline REAL (scrub verdadeiro);
- os 3 caminhos de re-tag chamam a MESMA fonte (PATCH · selo da tag · folder-tag);
- o editor (PATCH) escreve pelo selo: remover uma tag selada gera decisão 'remove'
  (latest-wins → não volta), e discord_tags sai do UPDATE cru.
"""
import json

import pytest

from app.services.study_pipeline import on_hand_tagged


class FakeCursor:
    def __init__(self, store):
        self.store = store

    def execute(self, sql, params=None):
        self.store.append((sql, params))

    def fetchall(self):
        return []

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

    def rollback(self):
        pass

    def close(self):
        pass


# ── unidade: ordem, auditoria, gates ─────────────────────────────────────────

def _wire_pipeline(monkeypatch, calls, *, hand_row, scrub_result=1,
                   villains_raises=False):
    import app.services.villain_rules as vr
    import app.services.eliminated_bounty as eb
    import app.services.name_propagation as np
    import app.services.ft_boundary as ftb
    import app.db as db

    def _villains(hid, conn=None):
        calls.append(("villains", hid))
        if villains_raises:
            raise RuntimeError("boom")
    monkeypatch.setattr(vr, "apply_villain_rules", _villains)
    monkeypatch.setattr(eb, "scrub_and_persist",
                        lambda hid, vision_data=None, incoming_folder_tag=None:
                        calls.append(("scrub", hid, incoming_folder_tag)) or scrub_result)
    monkeypatch.setattr(np, "trigger_name_propagation",
                        lambda tn=None: calls.append(("prop", tn)))
    monkeypatch.setattr(ftb, "trigger_ft_refresh",
                        lambda: calls.append(("ft",)))
    monkeypatch.setattr(db, "query", lambda sql, params=None: [hand_row])


def test_pipeline_ordem_e_auditoria_mao_tagada(monkeypatch):
    calls = []
    _wire_pipeline(monkeypatch, calls, hand_row={
        "site": "GGPoker", "tournament_number": "T9",
        "hm3_tags": None, "discord_tags": ["pos-pko"]})
    audit = on_hand_tagged(7)
    assert [c[0] for c in calls] == ["villains", "scrub", "prop", "ft"]
    assert calls[2] == ("prop", "T9")
    assert audit["villains"] and audit["scrubbed"] == 1
    assert audit["tagged"] and audit["propagation_fired"] and audit["ft_fired"]


def test_pipeline_mao_destagada_nao_dispara_prop_nem_ft(monkeypatch):
    calls = []
    _wire_pipeline(monkeypatch, calls, hand_row={
        "site": "GGPoker", "tournament_number": "T9",
        "hm3_tags": None, "discord_tags": None})
    audit = on_hand_tagged(7)
    assert [c[0] for c in calls] == ["villains", "scrub"]   # nada estreitado; nada a mais
    assert not audit["tagged"] and not audit["propagation_fired"]


def test_pipeline_incoming_folder_tag_forca_tagada(monkeypatch):
    # tag ainda não commitada (reconcile em transacção) → incoming força o resto
    calls = []
    _wire_pipeline(monkeypatch, calls, hand_row={
        "site": "GGPoker", "tournament_number": "T9",
        "hm3_tags": None, "discord_tags": None})
    audit = on_hand_tagged(7, incoming_folder_tag="pos-pko")
    assert ("prop", "T9") in calls and ("ft",) in calls
    assert calls[1] == ("scrub", 7, "pos-pko")
    assert audit["tagged"]


def test_pipeline_defensivo_villains_rebenta_scrub_corre(monkeypatch):
    calls = []
    _wire_pipeline(monkeypatch, calls, villains_raises=True, hand_row={
        "site": "GGPoker", "tournament_number": "T9",
        "hm3_tags": None, "discord_tags": ["icm"]})
    audit = on_hand_tagged(7)
    assert ("scrub", 7, None) in calls                      # a falha não travou o funil
    assert audit["villains"] is False and audit["scrubbed"] == 1


# ── caso real (forma GG-6090481360): re-tag cura a coroa fantasma ────────────

_RAW = (
    "Poker Hand #TM123: Tournament #298000000, Hold'em No Limit - Level10(500/1,000)\n"
    "Seat 1: Hero (10,000 in chips)\n"
    "Seat 2: a1b2c3d4 (5,000 in chips)\n"
    "Seat 3: e5f6a7b8 (8,000 in chips)\n"
    "a1b2c3d4: bets 5,000 and is all-in\n"
    "Hero: calls 5,000\n"
    "Hero collected 11,000 from pot\n"
)


def test_caso_real_retag_anula_coroa_de_bustado_e_marca_vivo_zero(monkeypatch):
    # forma da GG-6090481360: bustado (Lauro) com coroa fantasma $421 sem source;
    # vivo (e5f6a7b8) com coroa $0; TS na base ($250). Re-tag → pipeline REAL
    # (scrub verdadeiro) anula+marca o bustado e marca o vivo-$0.
    store, calls = [], []
    apa = {"_meta": {"bb": 1000},
           "Hero": {"is_hero": True, "seat": 1, "real_name": "Hero"},
           "a1b2c3d4": {"seat": 2, "real_name": "Lauro Dermio", "bounty_value_usd": 421.0},
           "e5f6a7b8": {"seat": 3, "real_name": "Vivo Zero", "bounty_value_usd": 0}}
    pn = {"players_list": [
        {"name": "Lauro Dermio", "bounty_value_usd": 421.0},
        {"name": "Vivo Zero", "bounty_value_usd": 0},
        {"name": "Hero", "bounty_value_usd": 100.0}]}
    hand_row_scrub = {"id": 9217, "hand_id": "GG-6090481360", "raw": _RAW,
                      "apa": json.loads(json.dumps(apa)), "pn": json.loads(json.dumps(pn)),
                      "hm3_tags": None, "discord_tags": ["pos-pko"], "site": "GGPoker",
                      "bounty_base": 250.0, "has_ts": True}
    hand_row_state = {"site": "GGPoker", "tournament_number": "T298",
                      "hm3_tags": None, "discord_tags": ["pos-pko"]}

    import app.db as db
    import app.services.villain_rules as vr
    import app.services.name_propagation as np
    import app.services.ft_boundary as ftb
    import app.services.crown_seal_log as csl

    def q(sql, params=None):
        if "ts.buy_in_bounty AS bounty_base" in sql:
            return [hand_row_scrub]
        if sql.startswith("SELECT site, tournament_number"):
            return [hand_row_state]
        raise AssertionError("query inesperada: " + sql[:90])

    monkeypatch.setattr(db, "query", q)
    monkeypatch.setattr(db, "get_conn", lambda: FakeConn(store))
    monkeypatch.setattr(vr, "apply_villain_rules",
                        lambda hid, conn=None: calls.append(("villains", hid)))
    monkeypatch.setattr(np, "trigger_name_propagation",
                        lambda tn=None: calls.append(("prop", tn)))
    monkeypatch.setattr(ftb, "trigger_ft_refresh", lambda: calls.append(("ft",)))
    monkeypatch.setattr(csl, "log_seals", lambda rows, origin, actor="?": 0)

    audit = on_hand_tagged(9217)
    assert ("villains", 9217) in calls and ("prop", "T298") in calls
    assert audit["scrubbed"] >= 1
    upd = [p for s, p in store if isinstance(s, str)
           and s.startswith("UPDATE hands SET all_players_actions")]
    assert upd, "o funil não escreveu"
    apa_w = json.loads(upd[-1][0]); pn_w = json.loads(upd[-1][1])
    lauro = apa_w["a1b2c3d4"]
    assert lauro["bounty_value_usd"] is None                 # coroa fantasma ANULADA
    assert lauro["bounty_review"] == "eliminated_no_green"   # e POR REVER (não calado)
    vivo = apa_w["e5f6a7b8"]
    assert vivo["bounty_value_usd"] is None
    assert vivo["bounty_review"] == "live_crown_read_zero"   # vivo-$0 marcado
    lauro_pl = [e for e in pn_w["players_list"] if e["name"] == "Lauro Dermio"][0]
    assert lauro_pl["bounty_value_usd"] is None              # as 2 gavetas coerentes
    hero_pl = [e for e in pn_w["players_list"] if e["name"] == "Hero"][0]
    assert hero_pl["bounty_value_usd"] == 100.0              # vivo COM coroa: intacto


# ── os 3 caminhos chamam a MESMA fonte ───────────────────────────────────────

def test_caminho_b_selo_da_tag_chama_pipeline(monkeypatch):
    import app.services.study_pipeline as sp
    from app.routers.tag_decisions import _refresh_villains
    got = []
    monkeypatch.setattr(sp, "on_hand_tagged",
                        lambda hid, **kw: got.append(hid))
    _refresh_villains([5, 6, 6, 5])
    assert got == [5, 6]                                     # dedupe, ordem preservada


def test_caminho_c_folder_tag_chama_pipeline_com_vision_e_incoming(monkeypatch):
    import app.services.study_pipeline as sp
    from app.routers import table_ss as m
    got = []
    monkeypatch.setattr(sp, "on_hand_tagged",
                        lambda hid, **kw: got.append((hid, kw.get("incoming_folder_tag"),
                                                      kw.get("vision_data") is not None)))
    store = []
    m._apply_folder_tag_to_hand(7, "pos-pko", {"players_list": []}, conn=FakeConn(store))
    assert got == [(7, "pos-pko", True)]
    # e a escrita da tag continua a passar pelo selo (apply_tag_decisions no SQL)
    assert any("apply_tag_decisions" in s for s, _ in store)


def test_caminho_c_sem_folder_tag_pipeline_corre_na_mesma(monkeypatch):
    # captura web-first numa mão já-tagada: o scrub de sempre não se perde (não estreitar)
    import app.services.study_pipeline as sp
    from app.routers import table_ss as m
    got = []
    monkeypatch.setattr(sp, "on_hand_tagged",
                        lambda hid, **kw: got.append((hid, kw.get("incoming_folder_tag"))))
    m._apply_folder_tag_to_hand(7, None, {"players_list": []}, conn=FakeConn([]))
    assert got == [(7, None)]


def test_caminho_d_gg_health_tag_untag_chamam_pipeline(monkeypatch):
    # LEI 2 (22 Jul): as ferramentas /tag e /untag da Saúde GG eram o 4º caminho
    # de re-tag (selam, mas só re-avaliavam vilões) — agora chamam a mesma fonte.
    import app.services.study_pipeline as sp
    import app.services.tag_decisions as td
    from app.routers import gg_health as G
    got, store = [], []
    monkeypatch.setattr(sp, "on_hand_tagged", lambda hid, **kw: got.append(hid))
    monkeypatch.setattr(td, "seal_and_recompute",
                        lambda cur, hid, tag, action, actor=None, origin=None: [1])
    monkeypatch.setattr(G, "seal_and_recompute", td.seal_and_recompute, raising=False)
    monkeypatch.setattr(G, "query", lambda sql, params=None:
                        [{"id": 9, "hand_id": "GG-1", "discord_tags": ["pos-pko"],
                          "tournament_format": "PKO"}])
    monkeypatch.setattr(G, "get_conn", lambda: FakeConn(store))
    G.gg_health_untag({"hand_ids": ["GG-1"], "tag": "pos-pko"},
                      current_user={"email": "r"})
    assert got == [9]
    got.clear()
    G.gg_health_tag({"hand_ids": ["GG-1"], "tag": "icm-pko"},
                    current_user={"email": "r"})
    assert got == [9]


def test_caminho_a_patch_nao_toca_discord_tags_logo_nao_luta_com_o_selo():
    # verificação da premissa: o editor da página (PATCH) NÃO aceita discord_tags
    # (o TagEditor edita hm3_tags) → não há luta com o selo (que é discord-only).
    from app.routers import hands as H
    assert "discord_tags" not in H.HandUpdate.model_fields
    assert "hm3_tags" in H.HandUpdate.model_fields


def test_caminho_a_patch_sem_mudanca_de_tags_nao_dispara(monkeypatch):
    from app.routers import hands as H
    import app.services.study_pipeline as sp
    fired, executed = [], []
    monkeypatch.setattr(H, "execute", lambda sql, params=None: executed.append((sql, params)))
    monkeypatch.setattr(sp, "on_hand_tagged", lambda hid, **kw: fired.append(hid))
    H.update_hand(77, H.HandUpdate(study_state="review"), current_user={"email": "r"})
    assert fired == [] and executed            # update normal correu, pipeline não


def test_caminho_a_patch_hm3_tags_directo_mas_dispara(monkeypatch):
    from app.routers import hands as H
    import app.services.study_pipeline as sp
    fired, executed = [], []
    monkeypatch.setattr(H, "execute", lambda sql, params=None: executed.append((sql, params)))
    monkeypatch.setattr(sp, "on_hand_tagged", lambda hid, **kw: fired.append(hid))
    H.update_hand(77, H.HandUpdate(hm3_tags=["ICM"]), current_user={"email": "r"})
    assert fired == [77]
    assert any("hm3_tags" in (s or "") for s, _ in executed)   # hm3 continua escrita directa
