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


# ── FIX B.3 — reconcile R: match converge em qualquer ordem + auto-corrige ───

def _ss_row(rid, result, matched, name="ODYSSEY #013"):
    return {"id": rid, "captured_at": CAP, "site": "Winamax",
            "vision_json": {"tournament_name": name},
            "result": result, "matched_hand_id": matched}


def test_b3_table_ss_converges_same_match_regardless_of_order():
    """A MESMA função R produz o mesmo match independentemente da ordem:
    (A) SS DEPOIS da mão → R casa directo no upload (compute).
    (B) SS ANTES da mão → gravada órfã; quando a mão chega, o reconcile recalcula
        de raiz e liga à MESMA mão (hand_db_id 10)."""
    ss_vj = {"tournament_name": "ODYSSEY #013"}

    # (A) ordem "depois" — R no upload.
    with patch("app.routers.table_ss.tv._correct_site", side_effect=lambda n, s: s), \
         patch("app.routers.table_ss._find_candidate_hands", return_value=[HAND]):
        d_after = table_ss.compute_table_ss_match(CAP, "Winamax", ss_vj)
    assert d_after["matched_hand_id"] == "WN-10"
    assert d_after["matched_hand_db_id"] == 10

    # (B) ordem "antes" — órfã na BD; reconcile recalcula e liga.
    orphan = _ss_row(1, "no_match_to_hand", None)
    conn = MagicMock(); cur = MagicMock()
    conn.cursor.return_value.__enter__.return_value = cur
    with patch("app.routers.table_ss.tv._correct_site", side_effect=lambda n, s: s), \
         patch("app.routers.table_ss.get_conn", return_value=conn), \
         patch("app.routers.table_ss._find_candidate_hands", return_value=[HAND]), \
         patch("app.routers.table_ss.query", return_value=[orphan]):
        res = table_ss.reconcile_table_ss()

    assert res["success"] == 1 and res["changed"] == 1
    link = [(" ".join(c[0][0].split()), c[0][1]) for c in cur.execute.call_args_list]
    # Convergência: a ordem (B) liga à MESMA mão (ss_id=1 → hand_db_id=10) que (A).
    assert any("SET context_table_ss_id = %s WHERE id = %s" in s and p == (1, 10)
               for s, p in link)


def test_b3_corrects_previous_wrong_match_after_reconcile():
    """SS gravada `success` ligada à mão ERRADA (WN-99); quando uma mão melhor
    existe, o reconcile recalcula → desliga a obsoleta e liga a correcta (vai
    além do B.1: re-avalia mesmo as já success)."""
    wrong = _ss_row(1, "success", "WN-99")
    conn = MagicMock(); cur = MagicMock()
    conn.cursor.return_value.__enter__.return_value = cur
    with patch("app.routers.table_ss.tv._correct_site", side_effect=lambda n, s: s), \
         patch("app.routers.table_ss.get_conn", return_value=conn), \
         patch("app.routers.table_ss._find_candidate_hands", return_value=[HAND]), \
         patch("app.routers.table_ss.query", return_value=[wrong]):
        res = table_ss.reconcile_table_ss()

    assert res["changed"] == 1   # corrigiu WN-99 → WN-10
    sqls = [(" ".join(c[0][0].split()), c[0][1]) for c in cur.execute.call_args_list]
    # desliga a mão obsoleta (id <> match) e liga a correcta (id 10).
    assert any("SET context_table_ss_id = NULL WHERE context_table_ss_id = %s AND id <> %s" in s
               for s, _ in sqls)
    assert any("SET context_table_ss_id = %s WHERE id = %s" in s and p == (1, 10)
               for s, p in sqls)


def test_b3_reconcile_idempotent_no_change_when_same():
    """Reconcile com o MESMO estado da BD → não muda nada (changed=0)."""
    same = _ss_row(1, "success", "WN-10")
    conn = MagicMock(); cur = MagicMock()
    conn.cursor.return_value.__enter__.return_value = cur
    with patch("app.routers.table_ss.tv._correct_site", side_effect=lambda n, s: s), \
         patch("app.routers.table_ss.get_conn", return_value=conn), \
         patch("app.routers.table_ss._find_candidate_hands", return_value=[HAND]), \
         patch("app.routers.table_ss.query", return_value=[same]):
        res = table_ss.reconcile_table_ss()
    assert res["checked"] == 1
    assert res["changed"] == 0   # match idêntico → sem churn


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
