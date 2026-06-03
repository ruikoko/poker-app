"""pt50 — testes de CONVERGÊNCIA independente da ordem das fontes.

Provam que o estado final não depende da ordem em que as fontes chegam:
- FIX A  : re-parse HM3 (PATH A, mão já existente) NÃO apaga o enrich GG
           (guard CASE espelhado do PATH B).
- FIX B.1: SS de mesa que ficou `tm_ambiguous` no upload passa a ser resgatável
           pelo relink (orfã → liga à mesma mão que casaria na ordem inversa).
- Discord: SS antes da HH (placeholder) preserva os dados Vision → mesmo estado
           que HH-antes-da-SS (enrich path).

Harness mock-based (sem Postgres), alinhado com test_table_ss / test_matching_guards.
"""
import inspect
import json
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock

from app.routers import table_ss
from app.routers.hm3 import import_hm3
from app.services.hand_service import _insert_hand


CAP = datetime(2026, 5, 23, 16, 4, 0, tzinfo=timezone.utc)
HAND = {"id": 10, "hand_id": "WN-10", "tournament_number": "T1",
        "tournament_name": "ODYSSEY #013", "site": "Winamax", "played_at": CAP}


# ── FIX A — guard de preservação de enrich nos DOIS write-paths do HM3 ────────

def test_fix_a_hm3_both_write_paths_guard_gg_enrich():
    """O import HM3 tem 2 caminhos de escrita em `hands`; AMBOS têm de preservar
    o all_players_actions de uma mão GG já decifrada por Vision (match_method).
    PATH B (INSERT...ON CONFLICT) já tinha o guard; FIX A acrescentou-o ao
    PATH A (UPDATE de mão existente). Sem isto, HM3 a chegar depois do enrich
    apagava os nicks (dependência de ordem latente)."""
    # NB: inspect.getsource devolve o CÓDIGO-FONTE (PATH A é construído por
    # concatenação de literais "..." "..."), por isso afirmamos fragmentos que
    # vivem dentro de um único literal, não a frase SQL inteira.
    norm = " ".join(inspect.getsource(import_hm3).split())
    # PATH B (ON CONFLICT, triple-quoted) — guard pré-existente, refs qualificadas.
    assert "WHEN hands.site = 'GGPoker'" in norm
    assert "THEN hands.all_players_actions" in norm
    # PATH A (UPDATE de mão existente) — guard FIX A: refs SEM prefixo + ELSE %s
    # (distingue-o do PATH B, que usa hands./EXCLUDED.).
    assert "WHEN site = 'GGPoker'" in norm
    assert "(player_names ->> 'match_method') IS NOT NULL" in norm
    assert "ELSE %s END" in norm


# ── FIX B.1 — convergência table-SS: ordem (SS antes vs depois) → mesma mão ───

def test_fix_b1_table_ss_before_vs_after_converge_to_same_hand():
    """(A) SS DEPOIS da mão: casa directo no upload (_resolve_match).
    (B) SS ANTES da mão: upload não acha (orfã) e o relink liga quando a mão
    chega. As duas ordens convergem para a MESMA mão."""
    ss_vj = {"tournament_name": "ODYSSEY #013"}

    # (A) ordem "depois" — match directo.
    m_after = table_ss._resolve_match(CAP, ss_vj, "Winamax", [HAND])
    assert m_after["matched"]["hand_id"] == "WN-10"
    assert m_after["reason"] == "single_tn"

    # (B) ordem "antes" — orfã + relink.
    orphan = {"id": 1, "captured_at": CAP, "site": "Winamax", "vision_json": ss_vj}
    with patch("app.routers.table_ss.tv._correct_site", side_effect=lambda n, s: s), \
         patch("app.routers.table_ss._bump_attempt_table_ss"), \
         patch("app.routers.table_ss._link_orphan_table_ss", return_value=True) as mlink, \
         patch("app.routers.table_ss._find_candidate_hands", return_value=[HAND]), \
         patch("app.routers.table_ss.query", return_value=[orphan]):
        res = table_ss.relink_orphan_table_ss()

    assert res["linked"] == 1
    linked_hand = mlink.call_args[0][1]
    # Convergência: a ordem (B) liga à MESMA mão que a ordem (A) casou.
    assert linked_hand["hand_id"] == m_after["matched"]["hand_id"] == "WN-10"


def test_fix_b1_previously_ambiguous_ss_is_now_relinkable():
    """Uma SS que ficou `tm_ambiguous` no upload (resolver sem desambiguador na
    altura) tem de poder ser resgatada pelo relink quando o desambiguador chega
    — antes do FIX B.1 ficava presa para sempre (relink só via no_match_to_hand).

    Prova: o SELECT do relink e a UPDATE de link cobrem `tm_ambiguous`, e uma
    orfã ambígua que agora resolve para 1 mão é ligada."""
    # 1) O SELECT do relink inclui tm_ambiguous.
    with patch("app.routers.table_ss._find_candidate_hands"), \
         patch("app.routers.table_ss.query", return_value=[]) as mq:
        table_ss.relink_orphan_table_ss()
    select_sql = " ".join(mq.call_args[0][0].split())
    assert "result IN ('no_match_to_hand', 'tm_ambiguous')" in select_sql

    # 2) Uma orfã (que tinha ficado tm_ambiguous) cuja janela agora resolve para
    #    1 mão → relink liga (end-to-end sobre conn mockada).
    orphan = {"id": 5, "captured_at": CAP, "site": "Winamax",
              "vision_json": {"tournament_name": "ODYSSEY #013"}}
    conn = MagicMock()
    cur = MagicMock()
    cur.rowcount = 1
    conn.cursor.return_value.__enter__.return_value = cur
    with patch("app.routers.table_ss.tv._correct_site", side_effect=lambda n, s: s), \
         patch("app.routers.table_ss.get_conn", return_value=conn), \
         patch("app.routers.table_ss._find_candidate_hands", return_value=[HAND]), \
         patch("app.routers.table_ss.query", return_value=[orphan]):
        res = table_ss.relink_orphan_table_ss()
    assert res["linked"] == 1
    sqls = [" ".join(c[0][0].split()) for c in cur.execute.call_args_list]
    # A UPDATE de link aceita a transição a partir de tm_ambiguous.
    assert any("result IN ('no_match_to_hand', 'tm_ambiguous')" in s for s in sqls)
    assert any("UPDATE hands SET context_table_ss_id = %s" in s for s in sqls)


# ── Discord — SS antes da HH (placeholder) preserva os dados Vision ──────────

class _Cur:
    def __init__(self, existing):
        self.existing = existing
        self.updates = []
        self.deletes = []
        self.inserts = []
        self._fetch = None

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def execute(self, sql, params=None):
        low = sql.lower().strip()
        if "select id, raw, hm3_tags" in low:
            self._fetch = self.existing
        elif "delete from hands" in low:
            self.deletes.append(params)
        elif "insert into hands" in low:
            self.inserts.append(params)
        elif "update hands" in low:
            self.updates.append(params)
        else:
            self._fetch = None

    def fetchone(self):
        return self._fetch


class _Conn:
    def __init__(self, existing):
        self.cur = _Cur(existing)

    def cursor(self):
        return self.cur

    def commit(self):
        pass

    def rollback(self):
        pass

    def close(self):
        pass


def test_discord_ss_before_hh_preserves_vision_players():
    """SS Discord chega ANTES da HH → placeholder com players_list Vision. Quando
    a HH real é importada, _insert_hand apaga o placeholder e REAPLICA o
    player_names Vision (COALESCE) → mesmo estado final que a ordem inversa
    (HH primeiro, SS enriquece depois via _enrich_hand_from_orphan_entry)."""
    vision_players = [{"name": "Rui", "seat": 1}, {"name": "VillainX", "seat": 3}]
    placeholder = {
        "id": 1,
        "raw": "",  # placeholder: sem HH ainda
        "hm3_tags": ["GGDiscord"],
        "origin": "discord",
        "discord_tags": ["icm-pko"],
        "placeholder_entry_id": 555,
        "player_names": {
            "match_method": "discord_placeholder_no_hh",
            "players_list": vision_players,
            "hero": "Rui",
        },
        "screenshot_url": "https://gg.cdn/x.png",
        "tags": ["SSMatch"],
    }
    conn = _Conn(placeholder)
    new_hand = {
        "site": "GGPoker", "hand_id": "GG-1234", "played_at": None,
        "stakes": "1000/2000", "position": "BTN", "hero_cards": ["As", "Kh"],
        "board": [], "result": 0, "currency": "$",
        "raw": "Poker Hand #GG-1234 ...", "all_players_actions": {},
        "tournament_id": None, "buy_in": None, "tournament_format": None,
        "tournament_name": None,
    }

    # Binding hash->nick irrelevante aqui (raw fake) → forçar {} p/ determinismo:
    # players_list mantém-se em pn_clean de qualquer forma.
    with patch("app.routers.screenshot._build_anon_to_real_map", return_value={}):
        ok = _insert_hand(conn, new_hand, entry_id=777, study_state="new", origin="discord")

    assert ok is True
    assert len(conn.cur.deletes) == 1          # placeholder apagado
    assert len(conn.cur.inserts) == 1          # HH real inserida
    assert len(conn.cur.updates) == 1          # reaplicação da metadata Vision
    pn_param = conn.cur.updates[0]["player_names"]
    assert pn_param is not None
    # Os nicks Vision sobrevivem à promoção (convergência com o enrich path).
    assert "players_list" in pn_param
    assert "VillainX" in pn_param
    # entry_id Discord original preservado.
    assert conn.cur.updates[0]["placeholder_entry_id"] == 555
