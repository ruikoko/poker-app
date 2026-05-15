"""Matching guard tests — protegem o pipeline cross-fluxo (SS↔HH, rematch GG,
fallback Discord↔HM3, placeholder upgrade) durante a serie de pecas
#ORFA-HM3-SYNTHETIC-ENTRIES (5 pecas sequenciais).

Devem passar **antes E depois** de cada peca. Validam comportamento
funcional (nao SQL exacto), portanto sao robustos a mudancas de filtro
que preservem semantica.

Guard 1 — Classificacao A/C/D para hand_villains.
Guard 2 — Rematch GG processa candidatos (independente do filtro SQL).
Guard 3 — Fallback match Discord image -> HM3 hand via origin.
Guard 4 — Placeholder upgrade preserva entry_id da entry Discord original.
"""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from app.services.hand_service import _classify_villain_categories, _insert_hand
from app.routers.attachments import _find_fallback_match


# ── Guard 1 — Classificacao A/C/D ──────────────────────────────────────


def test_guard1_regra_A_hm3_tag_nota_dispara_categoria_nota():
    cats = _classify_villain_categories(
        hand_meta={"hm3_tags": ["nota-pko"], "discord_tags": [], "match_method": ""},
        villain_nick="OponenteX",
        has_cards=False,
        has_vpip=True,
    )
    assert "nota" in cats


def test_guard1_regra_C_discord_nota_e_match_real_dispara_categoria_nota():
    cats = _classify_villain_categories(
        hand_meta={
            "hm3_tags": [],
            "discord_tags": ["nota"],
            "match_method": "anchors_stack_elimination_v2",
        },
        villain_nick="OponenteX",
        has_cards=True,
        has_vpip=False,
    )
    assert "nota" in cats


def test_guard1_regra_C_discord_nota_mas_placeholder_match_nao_dispara():
    cats = _classify_villain_categories(
        hand_meta={
            "hm3_tags": [],
            "discord_tags": ["nota"],
            "match_method": "discord_placeholder_no_hh",
        },
        villain_nick="OponenteX",
        has_cards=True,
        has_vpip=False,
    )
    assert "nota" not in cats


def test_guard1_regra_D_friend_hero_dispara_categoria_friend():
    cats = _classify_villain_categories(
        hand_meta={"hm3_tags": [], "discord_tags": [], "match_method": ""},
        villain_nick="Karluz",
        has_cards=False,
        has_vpip=True,
    )
    assert "friend" in cats


def test_guard1_sem_VPIP_nem_cards_nem_nota_intent_retorna_vazio():
    cats = _classify_villain_categories(
        hand_meta={"hm3_tags": [], "discord_tags": [], "match_method": ""},
        villain_nick="OponenteX",
        has_cards=False,
        has_vpip=False,
    )
    assert cats == []


def test_guard1_B19_excepcao_nota_HM3_ignora_pre_condicao_VPIP_cards():
    """#B19 (REGRAS_NEGOCIO.md §3.3) — tag nota HM3 dispensa VPIP/cards."""
    cats = _classify_villain_categories(
        hand_meta={"hm3_tags": ["nota-icm"], "discord_tags": [], "match_method": ""},
        villain_nick="OponenteX",
        has_cards=False,
        has_vpip=False,
    )
    assert "nota" in cats


# ── Guard 2 — Rematch GG processa candidatos ──────────────────────────


def test_guard2_rematch_processa_hand_hm3_gg_com_hashes_anonimos():
    """O endpoint /api/mtt/rematch chama _enrich_hand_from_orphan_entry
    para mao GG HM3 com hashes anonimos quando ha SS Discord correspondente.

    Independe do filtro SQL exacto (entry_id IS NULL hoje, origin='hm3'
    apos Peca 2) — mocka query() para retornar o candidato e valida o flow.
    """
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.routers.mtt import router as mtt_router
    from app.auth import require_auth

    app = FastAPI()
    app.include_router(mtt_router)
    app.dependency_overrides[require_auth] = lambda: {"id": 1, "email": "t@t"}
    client = TestClient(app)

    # Hand HM3 GG candidata (hashes anonimos, sem SS associada).
    candidate_hand = {"id": 42, "hand_id": "GG-1234567890"}
    # SS Discord disponivel com Vision concluido para esse TM (encontrado em
    # phase 2 do rematch via raw_json->>'tm').
    ss_entry = {
        "id": 99,
        "raw_json": {"vision_done": True, "tm": "TM1234567890", "players": []},
    }
    # Truque: dar 1 SS inicial sem 'tm' para o loop de phase 1 nao fazer
    # match acidental — assim phase 1 percorre o continue e chega a phase 2.
    phase1_skip_ss = {"id": 100, "raw_json": {}}

    enriched_calls = []

    def fake_enrich(entry_id, hand_id, raw):
        enriched_calls.append((entry_id, hand_id))
        return {"status": "ok", "players_mapped": 6}

    def fake_query(sql, params=None):
        # Phase 2 SS finder por TM — distingue pelo lookup do tm em raw_json.
        if "raw_json->>'tm'" in sql:
            return [ss_entry]
        # Phase 1 inicial: screenshot_entries (sem TM filter ainda).
        if "entry_type = 'screenshot'" in sql and "raw_json->>'tm'" not in sql:
            return [phase1_skip_ss]
        # Pending hands query (phase 2) — distingue por GGPoker filter.
        if "site = 'GGPoker'" in sql and "hand_id LIKE 'GG-%'" in sql:
            return [candidate_hand]
        # Outras queries (mtt_hands existing, hand lookups por hand_id em
        # phase 1 que nao se aplicam ao SS sem tm, etc) — vazias.
        return []

    fake_conn = MagicMock()
    fake_conn.cursor.return_value.__enter__.return_value = MagicMock()

    with patch("app.routers.mtt.query", side_effect=fake_query), \
         patch("app.routers.mtt.get_conn", return_value=fake_conn), \
         patch(
             "app.routers.screenshot._enrich_hand_from_orphan_entry",
             side_effect=fake_enrich,
         ), \
         patch(
             "app.services.villain_rules.apply_villain_rules",
             return_value={"n_villains_created": 0},
         ):
        r = client.post("/api/mtt/rematch")

    assert r.status_code == 200, r.text
    # Verifica que _enrich foi chamado para a hand candidata.
    assert (99, 42) in enriched_calls, (
        f"_enrich_hand_from_orphan_entry nao foi chamado para a hand candidata. "
        f"Chamadas: {enriched_calls}"
    )
    body = r.json()
    assert body["hh_to_ss"]["matched"] >= 1


# ── Guard 3 — Fallback match Discord image -> HM3 hand ──────────────────


def test_guard3_find_fallback_match_usa_origin_hm3_hh_import():
    """_find_fallback_match procura hands com origin IN ('hm3', 'hh_import')
    dentro de janela ±90s — caminho canonico para anexar imagens Discord
    a maos HM3 sem entry Discord previa."""
    import datetime as dt
    posted_at = dt.datetime(2026, 5, 14, 12, 0, 0, tzinfo=dt.timezone.utc)
    img_entry = {
        "id": 7,
        "raw_text": "https://i.gyazo.com/x.png",
        "discord_channel": "icm-pko",
        "discord_posted_at": posted_at,
        "entry_type": "image",
    }
    expected_hand = {
        "hand_db_id": 100,
        "hand_id_text": "GG-9999999999",
        "played_at": posted_at,
        "delta_s": 0,
    }

    captured = {}

    def fake_query(sql, params):
        captured["sql"] = sql
        captured["params"] = params
        return [expected_hand]

    with patch("app.routers.attachments.query", side_effect=fake_query):
        result = _find_fallback_match(img_entry)

    assert result == expected_hand
    # Garantia: a SQL do fallback usa `origin IN ('hm3', 'hh_import')` —
    # independente de entry_id. Esta e a propriedade que torna o caminho
    # robusto a mudancas em entry_id de maos HM3.
    assert "origin IN ('hm3', 'hh_import')" in captured["sql"], (
        "_find_fallback_match deve filtrar por origin (nao entry_id) — caso "
        "contrario quebra apos #ORFA-HM3-SYNTHETIC-ENTRIES Peca 5."
    )
    # Janela temporal ±90s deve permanecer.
    assert "90" in captured["sql"]


def test_guard3_find_fallback_match_nao_filtra_por_canal():
    """Discord-channel-agnostico: mao HM3 pode estar em qualquer canal."""
    import datetime as dt
    posted_at = dt.datetime(2026, 5, 14, 12, 0, 0, tzinfo=dt.timezone.utc)
    img_entry = {
        "id": 7,
        "raw_text": "url",
        "discord_channel": "any-channel",
        "discord_posted_at": posted_at,
        "entry_type": "image",
    }
    captured = {}

    def fake_query(sql, params):
        captured["sql"] = sql
        return []

    with patch("app.routers.attachments.query", side_effect=fake_query):
        _find_fallback_match(img_entry)

    assert "discord_channel" not in captured["sql"], (
        "Fallback deve ser agnostico a canal (a primary path e que filtra por canal)."
    )


# ── Guard 4 — Placeholder upgrade preserva entry_id Discord ─────────────


class _StatefulCursor:
    """Cursor stateful que responde a varios SELECTs/INSERTs sequenciais
    para simular o fluxo de _insert_hand."""

    def __init__(self, existing_row: dict | None):
        self.existing = existing_row
        self.last_sql = ""
        self.last_params = None
        self.updates: list[tuple] = []
        self.deletes: list[tuple] = []
        self.inserts: list[tuple] = []
        self._next_fetchone = None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def execute(self, sql, params=None):
        self.last_sql = sql
        self.last_params = params
        sql_lower = sql.lower().strip()
        if "select id, raw, hm3_tags" in sql_lower:
            self._next_fetchone = self.existing
        elif "delete from hands" in sql_lower:
            self.deletes.append(params)
        elif "insert into hands" in sql_lower:
            self.inserts.append(params)
        elif "update hands" in sql_lower:
            self.updates.append(params)
        elif "select" in sql_lower and "tournament" in sql_lower:
            self._next_fetchone = None
        else:
            self._next_fetchone = None

    def fetchone(self):
        return self._next_fetchone


class _StatefulConn:
    def __init__(self, existing_row):
        self.cur = _StatefulCursor(existing_row)
        self.committed = False
        self.rolled_back = False

    def cursor(self):
        return self.cur

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True

    def close(self):
        pass


def test_guard4_placeholder_upgrade_preserva_entry_id_discord_original():
    """Quando placeholder Discord (raw vazio, match_method='discord_placeholder_*')
    e substituido pela HH real, o entry_id da entry Discord original DEVE
    ser preservado — nao substituido pelo entry_id da fonte HH (e.g., sintetico HM3).
    """
    # Placeholder Discord existente com entry_id=555.
    existing_placeholder = {
        "id": 1,
        "raw": "",
        "hm3_tags": ["GGDiscord"],
        "origin": "discord",
        "discord_tags": ["icm-pko"],
        "placeholder_entry_id": 555,
        "player_names": {"match_method": "discord_placeholder_no_hh"},
        "screenshot_url": "https://gg.cdn/x.png",
        "tags": ["SSMatch"],
    }
    conn = _StatefulConn(existing_placeholder)

    # HH real chega via HM3 ou ZIP — entry_id 777 passado como argumento (sintetico HM3 hipotetico).
    new_hand = {
        "site": "GGPoker",
        "hand_id": "GG-1234",
        "played_at": None,
        "stakes": "1000/2000",
        "position": "BTN",
        "hero_cards": ["As", "Kh"],
        "board": [],
        "result": 0,
        "currency": "$",
        "raw": "Poker Hand #GG-1234 ...",
        "all_players_actions": {},
        "tournament_id": None,
        "buy_in": None,
        "tournament_format": None,
        "tournament_name": None,
    }
    result = _insert_hand(
        conn,
        new_hand,
        entry_id=777,  # sintetico HM3 hipotetico
        tournament_pk=None,
        study_state="new",
        origin="hm3",
    )

    assert result is True, "_insert_hand devia ter retornado True (inserido)"
    # Foi feito DELETE do placeholder.
    assert len(conn.cur.deletes) == 1
    # Foi feito INSERT da HH real.
    assert len(conn.cur.inserts) == 1
    # Foi feito UPDATE pos-INSERT para reaplicar metadata do placeholder.
    assert len(conn.cur.updates) == 1, "Devia ter UPDATE pos-INSERT"
    upd_params = conn.cur.updates[0]
    # entry_id da entry Discord original DEVE estar nos params do UPDATE
    # como placeholder_entry_id, para preserver via reverse COALESCE.
    assert upd_params["placeholder_entry_id"] == 555, (
        f"entry_id Discord original (555) DEVE viajar nos params do UPDATE como "
        f"'placeholder_entry_id'. Recebido: {upd_params.get('placeholder_entry_id')}"
    )


def test_guard4_nao_placeholder_ignora_segunda_insercao():
    """Se a row existente NAO e placeholder (raw populado), _insert_hand
    devolve False (skip silencioso, dedup) sem alterar."""
    existing_real = {
        "id": 1,
        "raw": "Poker Hand #GG-1234 ...",  # raw populado → nao placeholder
        "hm3_tags": [],
        "origin": "hm3",
        "discord_tags": [],
        "placeholder_entry_id": 222,
        "player_names": {"match_method": "anchors_stack_elimination_v2"},
        "screenshot_url": None,
        "tags": [],
    }
    conn = _StatefulConn(existing_real)
    new_hand = {
        "site": "GGPoker",
        "hand_id": "GG-1234",
        "played_at": None,
        "stakes": None,
        "position": None,
        "hero_cards": [],
        "board": [],
        "result": 0,
        "currency": "$",
        "raw": "novo raw",
        "all_players_actions": None,
        "tournament_id": None,
        "buy_in": None,
        "tournament_format": None,
        "tournament_name": None,
    }
    result = _insert_hand(conn, new_hand, entry_id=999)
    assert result is False
    assert len(conn.cur.deletes) == 0
    assert len(conn.cur.inserts) == 0
    assert len(conn.cur.updates) == 0
