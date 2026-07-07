"""Tests para services/ft_boundary (#FT-PROPAGATION)."""
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

from app.services import ft_boundary as fb
from app.routers.gg_health import _tag_conflicts

T0 = datetime(2026, 6, 20, 21, 0, 0)


# ── _ft_applies (detetor FT) ─────────────────────────────────────────────────
def test_ft_applies_occupied_equals_players_left():
    vj = {"players_left": 3, "seats": [{"nick": "a"}, {"nick": "b"}, {"nick": "c"}]}
    assert fb._ft_applies(vj) is True


def test_ft_applies_false_when_mismatch_or_missing():
    assert fb._ft_applies({"players_left": 9, "seats": [{"nick": "a"}]}) is False
    assert fb._ft_applies({"seats": [{"nick": "a"}]}) is False          # sem pl
    assert fb._ft_applies({"players_left": 0, "seats": []}) is False


# ── Coerência (salvaguarda fonte b) ──────────────────────────────────────────
def test_coherent_monotone_decreasing():
    r = [{"players_left": 100}, {"players_left": 40}, {"players_left": 8}]
    kept, ok = fb._coherent_readings(r)
    assert ok is True and len(kept) == 3


def test_coherent_tolerates_small_jitter():
    r = [{"players_left": 50}, {"players_left": 49}, {"players_left": 50}]  # +1 <= TOL
    _, ok = fb._coherent_readings(r)
    assert ok is True


def test_isolated_spike_is_dropped_not_rejected():
    # 8 isolado (o resto sobe) = Vision mal lida → DESCARTA o outlier, resto coerente
    r = [{"players_left": 100}, {"players_left": 8}, {"players_left": 90}]
    kept, ok = fb._coherent_readings(r)
    assert ok is True
    assert [k["players_left"] for k in kept] == [100, 90]   # o 8 foi descartado


def test_multiple_jumps_genuinely_incoherent():
    # vários saltos, sem tendência clara → precisa remover 2+ → incoerente
    r = [{"players_left": 100}, {"players_left": 20}, {"players_left": 80},
         {"players_left": 30}, {"players_left": 70}]
    _, ok = fb._coherent_readings(r)
    assert ok is False


# ── Correção da tag (base → -ft) ─────────────────────────────────────────────
def test_to_ft_only_base_spots():
    assert fb._to_ft("icm") == "icm-ft"
    assert fb._to_ft("pos-pko") == "pos-pko-ft"
    assert fb._to_ft("icm-ft") is None        # já -ft
    assert fb._to_ft("nota") is None          # neutra


def test_ft_correct_array_converts_and_collapses():
    assert fb.ft_correct_array(["icm"]) == (["icm-ft"], True)
    assert fb.ft_correct_array(["icm-pko", "nota"]) == (["icm-pko-ft", "nota"], True)
    # base + a sua ft na mesma mão → colapsa em -ft (resolve conflito de fase)
    assert fb.ft_correct_array(["icm", "icm-ft"]) == (["icm-ft"], True)
    # já -ft / neutra → sem mudança
    assert fb.ft_correct_array(["icm-ft"]) == (["icm-ft"], False)
    assert fb.ft_correct_array(["nota"]) == (["nota"], False)


def test_no_double_suffix():
    assert fb._to_ft("icm-ft") is None
    assert fb.ft_correct_array(["icm-ft"])[0] == ["icm-ft"]   # nunca 'icm-ft-ft'


def test_correction_never_creates_format_conflict():
    # partindo de qualquer combinação, converter base→-ft não gera conflito 'formato'
    for start in (["icm"], ["icm-pko"], ["pos-nko"], ["pos-pko"], ["icm", "icm-ft"]):
        new, _ = fb.ft_correct_array(start)
        assert "formato" not in _tag_conflicts(new, [])


def test_correction_resolves_phase_conflict():
    # antes: fase (icm base + icm-ft); depois da correção: sem conflito
    assert "fase" in _tag_conflicts(["icm", "icm-ft"], [])
    new, _ = fb.ft_correct_array(["icm", "icm-ft"])
    assert _tag_conflicts(new, []) == []


# ── count_hh_seats (fonte única F2, movida do gg_health) ──────────────────────
def _raw(n_header, n_summary=0):
    seats = "".join(f"Seat {i}: p{i} ({i}000 in chips)\n" for i in range(1, n_header + 1))
    out = seats + "*** HOLE CARDS ***\naction\n"
    if n_summary:
        out += "*** SUMMARY ***\n" + "".join(
            f"Seat {i}: p{i} folded\n" for i in range(1, n_summary + 1))
    return out


def test_count_hh_seats_ignores_summary_and_handles_empty():
    assert fb.count_hh_seats(_raw(7, n_summary=7)) == 7   # não conta a dobrar
    assert fb.count_hh_seats(_raw(9)) == 9
    assert fb.count_hh_seats("") is None
    assert fb.count_hh_seats(None) is None


# ── _lobby_ft_boundary: gate open_tab='Info' (convenção 7 Jul) ────────────────
def test_lobby_boundary_only_anchors_on_info_tab():
    # SQL gateia por open_tab='Info' + final_table_size numérico; o mock devolve o
    # print do Info (posted_at, N). Prize Pool nunca chega aqui (filtrado no WHERE).
    def _q(sql, params=None):
        assert "open_tab" in sql and "Info" in sql          # o gate está no SQL
        assert "final_table_size" in sql
        return [{"posted_at": T0, "n": 7}]
    with patch.object(fb, "query", side_effect=_q):
        b, n = fb._lobby_ft_boundary("T1")
    assert b == T0 and n == 7


def test_lobby_boundary_none_without_info_print():
    with patch.object(fb, "query", return_value=[]):
        assert fb._lobby_ft_boundary("T1") == (None, None)


# ── cross-check HH (Adição 1, D2) ─────────────────────────────────────────────
def test_cross_check_match_mismatch_and_illegible():
    with patch.object(fb, "_first_hand_seats_after", return_value=7):
        assert fb._cross_check("T1", T0, 7) == {"n": 7, "hh_seats": 7, "match": True}
        assert fb._cross_check("T1", T0, 8) == {"n": 8, "hh_seats": 7, "match": False}
    with patch.object(fb, "_first_hand_seats_after", return_value=None):
        assert fb._cross_check("T1", T0, 7)["match"] is None     # HH ilegível → sem veredicto
    with patch.object(fb, "_first_hand_seats_after", return_value=7):
        assert fb._cross_check("T1", T0, None)["match"] is None  # N ausente → sem veredicto


# ── compute_ft_boundary: prioridade lobby > IT-coerente; incoerente sinaliza ──
def test_boundary_lobby_wins_carries_n_and_cross_check():
    with patch.object(fb, "_manual_ft_boundary", return_value=None), \
         patch.object(fb, "_lobby_ft_boundary", return_value=(T0, 7)), \
         patch.object(fb, "_snap_to_n", side_effect=lambda tn, b, n: b), \
         patch.object(fb, "_first_hand_seats_after", return_value=7):
        d = fb.compute_ft_boundary("T1")
    assert d["source"] == "propagated_lobby" and d["boundary"] == T0
    assert d["n"] == 7 and d["cross_check"]["match"] is True


def test_boundary_incoherent_signals():
    with patch.object(fb, "_manual_ft_boundary", return_value=None), \
         patch.object(fb, "_lobby_ft_boundary", return_value=(None, None)), \
         patch.object(fb, "_it_ft_boundary", return_value=(None, False, None)):
        d = fb.compute_ft_boundary("T1")
    assert d["status"] == "incoherent_signal" and d["boundary"] is None
    assert d["n"] is None and d["cross_check"] is None


def test_boundary_coherent_it_uses_players_left_as_n():
    # via (b): N = players_left da fronteira (D2); cross-check com os sentados da HH
    with patch.object(fb, "_manual_ft_boundary", return_value=None), \
         patch.object(fb, "_lobby_ft_boundary", return_value=(None, None)), \
         patch.object(fb, "_it_ft_boundary", return_value=(T0, True, 8)), \
         patch.object(fb, "_snap_to_n", side_effect=lambda tn, b, n: b), \
         patch.object(fb, "_first_hand_seats_after", return_value=8):
        d = fb.compute_ft_boundary("T1")
    assert d["source"] == "propagated_coherent" and d["boundary"] == T0
    assert d["n"] == 8 and d["cross_check"]["match"] is True


def test_boundary_none_when_no_signal():
    with patch.object(fb, "_manual_ft_boundary", return_value=None), \
         patch.object(fb, "_lobby_ft_boundary", return_value=(None, None)), \
         patch.object(fb, "_it_ft_boundary", return_value=(None, True, None)):
        d = fb.compute_ft_boundary("T1")
    assert d["status"] == "none" and d["boundary"] is None


# ── Fonte (0) — tag -ft MANUAL do Rui (arquitetura 7 Jul) ────────────────────
def test_manual_source_wins_over_lobby_and_captures():
    # tag manual presente → source=manual_ft_tag, mesmo com lobby/captures disponíveis
    with patch.object(fb, "_manual_ft_boundary", return_value=T0), \
         patch.object(fb, "_lobby_ft_boundary", return_value=(None, None)), \
         patch.object(fb, "_infer_ft_size", return_value=7), \
         patch.object(fb, "_snap_to_n", side_effect=lambda tn, b, n: b), \
         patch.object(fb, "_first_hand_seats_after", return_value=7):
        d = fb.compute_ft_boundary("T1")
    assert d["source"] == "manual_ft_tag" and d["status"] == "manual"
    assert d["boundary"] == T0 and d["n"] == 7   # N inferido (sem lobby)
    # sem lobby não há N independente → cross-check sem veredicto (tag = verdade do Rui)
    assert d["cross_check"]["match"] is None


def test_manual_uses_lobby_n_when_present():
    # N vem do lobby Info quando existe (não do inferido) + cross-check independente
    with patch.object(fb, "_manual_ft_boundary", return_value=T0), \
         patch.object(fb, "_lobby_ft_boundary", return_value=(T0, 7)), \
         patch.object(fb, "_snap_to_n", side_effect=lambda tn, b, n: b), \
         patch.object(fb, "_first_hand_seats_after", return_value=7):
        d = fb.compute_ft_boundary("T1")
    assert d["source"] == "manual_ft_tag" and d["n"] == 7
    assert d["cross_check"]["match"] is True      # lobby N=7 vs 7 sentados


def test_manual_vs_lobby_disagreement_quarantines():
    # tag manual e lobby apontam momentos incompatíveis (> janela) → quarentena
    late = T0 + timedelta(minutes=30)
    with patch.object(fb, "_manual_ft_boundary", return_value=T0), \
         patch.object(fb, "_lobby_ft_boundary", return_value=(late, 7)), \
         patch.object(fb, "_snap_to_n", side_effect=lambda tn, b, n: b):
        d = fb.compute_ft_boundary("T1")
    assert d["status"] == "quarantine_disagreement" and d["boundary"] is None
    assert d["cross_check"]["match"] is False


def test_manual_empty_falls_through_to_lobby():
    # fonte (0) vazia NÃO mata o torneio → cai na salvaguarda (a)
    with patch.object(fb, "_manual_ft_boundary", return_value=None), \
         patch.object(fb, "_lobby_ft_boundary", return_value=(T0, 7)), \
         patch.object(fb, "_snap_to_n", side_effect=lambda tn, b, n: b), \
         patch.object(fb, "_first_hand_seats_after", return_value=7):
        d = fb.compute_ft_boundary("T1")
    assert d["source"] == "propagated_lobby"


def test_manual_ft_boundary_query():
    with patch.object(fb, "query", return_value=[{"b": T0}]):
        assert fb._manual_ft_boundary("T1") == T0
    with patch.object(fb, "query", return_value=[{"b": None}]):
        assert fb._manual_ft_boundary("T1") is None


def test_infer_ft_size_is_max_seats_in_window():
    rows = [{"raw": _raw(4)}, {"raw": _raw(7)}, {"raw": _raw(6)}]
    with patch.object(fb, "query", return_value=rows):
        assert fb._infer_ft_size("T1", T0) == 7
    with patch.object(fb, "query", return_value=[]):
        assert fb._infer_ft_size("T1", T0) is None


# ── propagate_ft dry_run: não escreve; idempotente ───────────────────────────
def _fake_hands(rows):
    def _q(sql, params=None):
        if "FROM hands" in sql and "played_at >=" in sql:
            return rows
        return []
    return _q


def test_propagate_dry_run_plans_without_writing():
    hands = [{"id": 1, "hand_id": "GG-1", "discord_tags": ["icm"], "hm3_tags": [],
              "folder_ft_source": None}]
    with patch.object(fb, "compute_ft_boundary",
                      return_value={"boundary": T0, "source": "propagated_lobby", "status": "lobby"}), \
         patch.object(fb, "query", side_effect=_fake_hands(hands)), \
         patch.object(fb, "get_conn") as mconn:
        res = fb.propagate_ft("T1", dry_run=True)
    assert res["n_changed"] == 1
    assert res["changed"][0]["from"] == ["icm"]
    assert res["changed"][0]["to"] == ["icm-ft"]
    mconn.assert_not_called()                 # dry-run NÃO escreve


def test_propagate_skips_hand_without_base_spot():
    hands = [{"id": 2, "hand_id": "GG-2", "discord_tags": ["nota"], "hm3_tags": [],
              "folder_ft_source": None},
             {"id": 3, "hand_id": "GG-3", "discord_tags": ["icm-ft"], "hm3_tags": [],
              "folder_ft_source": None}]
    with patch.object(fb, "compute_ft_boundary",
                      return_value={"boundary": T0, "source": "propagated_lobby", "status": "lobby"}), \
         patch.object(fb, "query", side_effect=_fake_hands(hands)), \
         patch.object(fb, "get_conn") as mconn:
        res = fb.propagate_ft("T1", dry_run=True)
    assert res["n_changed"] == 0              # nada a corrigir (neutra / já -ft)
    mconn.assert_not_called()


def test_propagate_surfaces_cross_check():
    hands = [{"id": 1, "hand_id": "GG-1", "discord_tags": ["icm"], "hm3_tags": [],
              "folder_ft_source": None}]
    cc = {"n": 7, "hh_seats": 9, "match": False}      # mismatch → o revisor tem de ver
    with patch.object(fb, "compute_ft_boundary",
                      return_value={"boundary": T0, "source": "propagated_lobby",
                                    "status": "lobby", "n": 7, "cross_check": cc}), \
         patch.object(fb, "query", side_effect=_fake_hands(hands)), \
         patch.object(fb, "get_conn"):
        res = fb.propagate_ft("T1", dry_run=True)
    assert res["cross_checks"] == [{"tn": "T1", "source": "propagated_lobby",
                                    "n": 7, "hh_seats": 9, "match": False}]


def test_propagate_signals_incoherent_tournament():
    with patch.object(fb, "compute_ft_boundary",
                      return_value={"boundary": None, "source": None, "status": "incoherent_signal"}), \
         patch.object(fb, "get_conn") as mconn:
        res = fb.propagate_ft("T9", dry_run=False)
    assert res["signaled"] == ["T9"] and res["n_changed"] == 0
    mconn.assert_not_called()                 # incoerente → não escreve


# ── Fase 1: persistência — folder_ft_source='auto', preserva 'manual' (D3) ────
def test_persist_writes_auto_not_via_string_and_preserves_manual():
    mconn = MagicMock()
    mcur = MagicMock()
    mconn.cursor.return_value.__enter__.return_value = mcur
    with patch.object(fb, "get_conn", return_value=mconn), \
         patch("app.services.villain_rules.apply_villain_rules"):
        fb._persist_ft_correction(7, ["icm-ft"], [], "propagated_lobby")
    sql, params = mcur.execute.call_args[0]
    # a VIA ('propagated_lobby') nunca chega à coluna — nem no SQL nem nos params
    assert "propagated_lobby" not in sql
    assert "propagated_lobby" not in params
    # grava 'auto' mas o CASE preserva um 'manual' pré-existente (pasta -ft manda)
    assert "CASE WHEN folder_ft_source='manual'" in sql
    assert "'auto'" in sql
    # params = (discord_tags, hm3_tags, hand_db_id) — a via ficou de fora
    assert params == (["icm-ft"], [], 7)
    mconn.commit.assert_called_once()


# ── SNAP-TO-N + cauda pós-pico (política da fronteira, 7 Jul) ─────────────────
def _hand_at(secs, seats):
    return {"played_at": T0 + timedelta(seconds=secs), "raw": _raw(seats)}


def test_starts_drainage_unit():
    assert fb._starts_drainage([7, 7, 6, 5], 7) is True
    assert fb._starts_drainage([7, 5, 4, 7], 7) is False   # sobe no fim (mesa pré-FT)
    assert fb._starts_drainage([4, 3, 7], 7) is False       # não começa em N
    assert fb._starts_drainage([7], 7) is True
    assert fb._starts_drainage([7, None, 6], 7) is True     # ignora ilegível
    assert fb._starts_drainage([], 7) is False


def test_snap_hits_ft_start():
    # (a) gap real 51 s: pré-FT 4,3 depois FT 7 @ −51s; boundary 7 @ 0. snap → −51s
    rows = [_hand_at(-120, 4), _hand_at(-80, 3), _hand_at(-51, 7), _hand_at(-5, 7)]
    with patch.object(fb, "query", return_value=rows):
        assert fb._snap_to_n("T", T0, 7) == T0 + timedelta(seconds=-51)


def test_snap_ignores_pre_ft_table_seven():
    # (b) 7 pré-FT (mesa cheia do Hero) que DEPOIS sobe → não ancora no 1º 7,
    # ancora no início da drenagem (2º 7 seguido de 6)
    rows = [_hand_at(-160, 7), _hand_at(-120, 5), _hand_at(-90, 4),
            _hand_at(-40, 7), _hand_at(-5, 6)]
    with patch.object(fb, "query", return_value=rows):
        assert fb._snap_to_n("T", T0, 7) == T0 + timedelta(seconds=-40)


def test_snap_no_match_falls_back():
    # (c) nenhuma mão ==N na janela → fallback à fronteira computada
    rows = [_hand_at(-120, 5), _hand_at(-80, 4), _hand_at(-30, 3)]
    with patch.object(fb, "query", return_value=rows):
        assert fb._snap_to_n("T", T0, 7) == T0


def test_snap_noop_without_n_or_boundary():
    assert fb._snap_to_n("T", T0, None) == T0
    assert fb._snap_to_n("T", None, 7) is None


def _read(pl, occ, secs=0):
    return {"played_at": T0 + timedelta(minutes=secs), "players_left": pl,
            "vision_json": {"players_left": pl,
                            "seats": [{"nick": f"p{i}"} for i in range(occ)]}}


def test_post_peak_tail_trims_late_reg_rise():
    r = [_read(35, 0), _read(37, 0), _read(40, 0), _read(52, 0),
         _read(23, 0), _read(15, 0), _read(5, 0), _read(5, 0)]
    assert [x["players_left"] for x in fb._post_peak_tail(r)] == [52, 23, 15, 5, 5]


def test_post_peak_tail_keeps_monotone_decreasing():
    r = [_read(100, 0), _read(40, 0), _read(8, 0)]
    assert [x["players_left"] for x in fb._post_peak_tail(r)] == [100, 40, 8]


def test_it_boundary_anchors_late_reg_by_tail():
    # (d) late-reg: sobe 35→52 (pré-pico, ignorado) depois cai; FT deteta-se na
    # cauda (reading de 5 players com 5 sentados == 5 → _ft_applies)
    reads = [_read(35, 0, 0), _read(52, 0, 5), _read(15, 0, 20), _read(5, 5, 30)]
    with patch.object(fb, "_it_readings", return_value=reads):
        b, coh, n = fb._it_ft_boundary("T")
    assert coh is True and n == 5 and b == T0 + timedelta(minutes=30)


def test_it_boundary_incoherent_dirty_tail():
    # (e) cauda pós-pico com 2+ saltos (não fixável com 1 outlier) → incoerente
    reads = [_read(100, 0, 0), _read(20, 0, 5), _read(80, 0, 10),
             _read(30, 0, 15), _read(70, 0, 20)]
    with patch.object(fb, "_it_readings", return_value=reads):
        b, coh, n = fb._it_ft_boundary("T")
    assert coh is False and b is None
