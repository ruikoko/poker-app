"""#WN-TOTAL-CHIPS-FROM-LOBBY (24 Jul 2026) — total de fichas Winamax pelo print
de lobby. Regra aprovada pelo Rui: RUNNING preferido, senão o mais tardio;
total = entradas totais × starting stack; guarda «não-desce» nas entradas;
incoerência do average = SINALIZADOR (nunca veto); «fichas provisórias» quando
o print escolhido não é RUNNING; re_entries INFO-ONLY. GG byte-a-byte intocada.
"""
import asyncio
from datetime import datetime, timezone
from unittest.mock import patch

from app.services.lobby_chips_rule import (
    STATE_LATE_REG, STATE_RUNNING, STATE_UNKNOWN,
    compute_wn_total_chips, print_state,
)

PNG = b"\x89PNG\r\n\x1a\nx"
T = [datetime(2026, 7, 2, 19 + h, 0) for h in range(4)]   # 19h, 20h, 21h, 22h


def _p(posted_at, **vj):
    return {"posted_at": posted_at, "vision_json": vj}


# ── print_state ───────────────────────────────────────────────────────────────
def test_print_state():
    assert print_state({"reg_open": False}) == STATE_RUNNING
    assert print_state({"reg_open": True}) == STATE_LATE_REG
    assert print_state({"reg_open": None}) == STATE_UNKNOWN
    assert print_state({}) == STATE_UNKNOWN
    assert print_state(None) == STATE_UNKNOWN


# ── compute_wn_total_chips: escolha do print ─────────────────────────────────
def test_running_preferred_over_later_prints():
    # RUNNING às 20h > prints mais tardios em late-reg/unknown (fisicamente um
    # late-reg depois de RUNNING é misread — a regra nem olha para ele).
    res = compute_wn_total_chips([
        _p(T[0], entrants=50, starting_stack=20000, reg_open=True),
        _p(T[1], entrants=56, starting_stack=20000, reg_open=False),
        _p(T[2], entrants=56, starting_stack=20000),               # unknown
    ])
    assert res["chips"] == 56 * 20000
    assert res["state"] == STATE_RUNNING
    assert res["provisional"] is False
    assert res["chosen_posted_at"] == T[1]


def test_latest_running_wins_among_running():
    res = compute_wn_total_chips([
        _p(T[1], entrants=56, starting_stack=20000, reg_open=False),
        _p(T[2], entrants=56, starting_stack=20000, reg_open=False),
    ])
    assert res["chosen_posted_at"] == T[2]


def test_no_running_uses_latest_and_marks_provisional():
    # só late-reg → o mais tardio manda + provisórias (falta print pós-fecho)
    res = compute_wn_total_chips([
        _p(T[0], entrants=63, starting_stack=20000, reg_open=True),
        _p(T[1], entrants=105, starting_stack=20000, reg_open=True),
    ])
    assert res["chips"] == 105 * 20000
    assert res["state"] == STATE_LATE_REG
    assert res["provisional"] is True


def test_unknown_state_historic_is_provisional_no_inference():
    # Opção A do Rui: histórico sem estado → mais tardio + «estado desconhecido»;
    # SEM inferência de fecho por entradas estáticas (2 prints iguais NÃO viram
    # RUNNING).
    res = compute_wn_total_chips([
        _p(T[0], entrants=131, starting_stack=20000),
        _p(T[2], entrants=131, starting_stack=20000),
    ])
    assert res["state"] == STATE_UNKNOWN
    assert res["provisional"] is True
    assert res["chips"] == 131 * 20000


# ── guarda «não-desce» + sinalizadores ───────────────────────────────────────
def test_entrants_never_decrease_guard():
    # entradas do escolhido < máximo anterior = misread → usa o MÁXIMO + por-rever
    res = compute_wn_total_chips([
        _p(T[0], entrants=433, starting_stack=20000),
        _p(T[1], entrants=248, starting_stack=20000),
    ])
    assert res["chips"] == 433 * 20000
    assert any(f.startswith("entrants_drop") for f in res["review"])


def test_avg_incoherence_flags_but_never_vetoes():
    # avg×restantes ACIMA de entradas×stack é impossível → sinalizador; as
    # entradas mantêm-se (a regra não usa avg/left para o total).
    res = compute_wn_total_chips([
        _p(T[0], entrants=116, starting_stack=20000,
           average_stack=61052, players_left=39),    # 2 381 028 > 2 320 000
    ])
    assert res["chips"] == 116 * 20000
    assert "avg_incoherent" in res["review"]


def test_avg_coherent_no_flag():
    # os dois prints do Rui (24 Jul): HIGHROLLER 56×20k vs 48 695×23 (−0,001%)
    res = compute_wn_total_chips([
        _p(T[0], entrants=56, starting_stack=20000,
           average_stack=48695, players_left=23, reg_open=False),
    ])
    assert res["chips"] == 1_120_000
    assert res["review"] == []
    assert res["provisional"] is False


def test_stack_mismatch_flagged():
    res = compute_wn_total_chips([
        _p(T[0], entrants=50, starting_stack=20000),
        _p(T[1], entrants=60, starting_stack=100000),   # MONSTER STACK misread?
    ])
    assert any(f.startswith("stack_mismatch") for f in res["review"])


# ── re_entries (INFO-ONLY) + casos-limite ────────────────────────────────────
def test_re_entries_latest_value_info_only():
    res = compute_wn_total_chips([
        _p(T[0], entrants=63, starting_stack=20000, re_entries=11),
        _p(T[1], entrants=105, starting_stack=20000, re_entries=16),
        _p(T[2], entrants=105, starting_stack=20000),    # sem leitura → mantém 16
    ])
    assert res["re_entries"] == 16
    assert res["chips"] == 105 * 20000                   # não entra na conta


def test_no_usable_prints_returns_none():
    assert compute_wn_total_chips([]) is None
    assert compute_wn_total_chips([_p(T[0], players_left=10)]) is None
    assert compute_wn_total_chips([_p(T[0], entrants=0, starting_stack=20000)]) is None


def test_mixed_tz_posted_at_sorts_without_crash():
    # o log mistura naive (Lisboa) e tz-aware — a ordenação normaliza
    res = compute_wn_total_chips([
        _p(datetime(2026, 7, 2, 19, 0, tzinfo=timezone.utc),
           entrants=50, starting_stack=20000),
        _p(T[2], entrants=56, starting_stack=20000),
        _p(None, entrants=40, starting_stack=20000),     # sem hora → primeiro
    ])
    assert res["chips"] == 56 * 20000


# ── ligação no live path (process_lobby_message) — por sala ──────────────────
def _run_live(vj, blob, prior_prints=None):
    from app.services import lobby_sync

    def _q(sql, params=None):
        if "FROM lobby_processing_log" in sql:
            return prior_prints or []
        return []                                        # precedência D11 passa

    with patch.object(lobby_sync, "_upsert_lobby_log"), \
         patch.object(lobby_sync, "_resolve_via_hero_anchor", return_value=None), \
         patch.object(lobby_sync, "query", side_effect=_q), \
         patch.object(lobby_sync, "check_vj_payout_coherent",
                      return_value=(True, None)), \
         patch.object(lobby_sync.lobby_vision, "extract_lobby_payout_json",
                      return_value="{}"), \
         patch.object(lobby_sync.lobby_vision, "parse_and_validate_lobby_json",
                      return_value=vj), \
         patch.object(lobby_sync.lobby_vision, "build_hrc_payouts_blob",
                      return_value=blob), \
         patch.object(lobby_sync.tournament_resolver, "resolve_tournament_number",
                      return_value=("1120632836", [], "tier2")), \
         patch.object(lobby_sync.payouts_service, "upsert_payout",
                      return_value={"action": "inserted"}) as mpay:
        res = asyncio.run(lobby_sync.process_lobby_message(
            PNG, "image/png", message_id="h", channel_id=None,
            posted_at=datetime(2026, 7, 2, 22, 28)))
    return res, mpay


def test_live_winamax_overrides_blob_chips_with_rule():
    vj = {"site": "Winamax", "tournament_name": "HIGHROLLER",
          "entrants": 56, "starting_stack": 20000, "reg_open": False,
          "average_stack": 48695, "players_left": 23,
          "re_entries": 11, "prizes": {"1": 1425.0}}
    blob = {"structures": [{"name": "HIGHROLLER", "chips": 48695.0 * 23}]}
    res, mpay = _run_live(vj, blob)
    assert res["result"] == "success"
    assert res["wn_chips"] == {"chips": 1_120_000.0, "state": "running",
                               "provisional": False}
    sent = mpay.call_args.kwargs
    assert sent["payouts_json"]["structures"][0]["chips"] == 1_120_000.0
    assert sent["wn_chips_meta"]["re_entries"] == 11
    assert sent["wn_chips_meta"]["provisional"] is False


def test_live_winamax_uses_prior_prints_from_log():
    # print corrente em late-reg, mas há um RUNNING anterior no log → RUNNING manda
    vj = {"site": "Winamax", "tournament_name": "HIGHROLLER",
          "entrants": 40, "starting_stack": 20000, "reg_open": True,
          "prizes": {"1": 100.0}}
    prior = [{"discord_message_id": "old1",
              "posted_at": datetime(2026, 7, 2, 21, 0),
              "vision_json": {"entrants": 56, "starting_stack": 20000,
                              "reg_open": False}}]
    blob = {"structures": [{"chips": 1.0}]}
    res, mpay = _run_live(vj, blob, prior_prints=prior)
    assert res["wn_chips"]["chips"] == 56 * 20000
    assert res["wn_chips"]["state"] == "running"


def test_live_gg_path_untouched_no_meta_no_override():
    # GG byte-a-byte: blob tal-e-qual do builder, wn_chips_meta=None, sem chave
    # wn_chips na resposta.
    vj = {"site": "GGPoker", "tournament_name": "Daily Hyper $60",
          "entrants": 500, "starting_stack": 30000, "reg_open": False,
          "open_tab": "Prize Pool", "prizes": {"1": 100.0}}
    blob = {"structures": [{"chips": 123.0}]}
    res, mpay = _run_live(vj, blob)
    assert res["result"] == "success"
    assert "wn_chips" not in res
    sent = mpay.call_args.kwargs
    assert sent["payouts_json"]["structures"][0]["chips"] == 123.0
    assert sent["wn_chips_meta"] is None


# ── ligação no reconcile — por sala ──────────────────────────────────────────
def test_reconcile_winamax_overrides_chips():
    from app.services import lobby_sync
    row = {"discord_message_id": "w1", "site": "Winamax",
           "tournament_name": "INTERSTELLAR",
           "posted_at": datetime(2026, 7, 9, 20, 19),
           "vision_json": {"site": "Winamax", "entrants": 105,
                           "starting_stack": 20000, "reg_open": True,
                           "re_entries": 16, "prizes": {"1": 684.0}},
           "result": "tm_not_found"}

    def _q(sql, params=None):
        if "FROM lobby_processing_log" in sql and "result = 'success'" in sql:
            return []                                    # sem prints anteriores
        if "FROM lobby_processing_log" in sql:
            return [row]
        return []

    with patch.object(lobby_sync, "query", side_effect=_q), \
         patch.object(lobby_sync.tournament_resolver, "resolve_tournament_number",
                      return_value=("1125219400", [], "tier2")), \
         patch.object(lobby_sync, "_resolve_via_hero_anchor", return_value=None), \
         patch.object(lobby_sync, "check_vj_payout_coherent",
                      return_value=(True, None)), \
         patch.object(lobby_sync.lobby_vision, "build_hrc_payouts_blob",
                      return_value={"structures": [{"chips": 1.0}]}), \
         patch.object(lobby_sync.payouts_service, "upsert_payout",
                      return_value={"action": "inserted"}) as mpay, \
         patch.object(lobby_sync, "_upsert_lobby_log"):
        res = lobby_sync.reconcile_lobby_logs(message_ids=["w1"])
    assert res["written"] == 1
    assert res["items"][0]["wn_chips"] == {
        "chips": 2_100_000.0, "state": "late_reg", "provisional": True}
    sent = mpay.call_args.kwargs
    assert sent["payouts_json"]["structures"][0]["chips"] == 2_100_000.0
    assert sent["wn_chips_meta"]["re_entries"] == 16


def test_reconcile_gg_untouched():
    from app.services import lobby_sync
    row = {"discord_message_id": "g1", "site": "GGPoker",
           "tournament_name": "Daily Hyper $60",
           "posted_at": datetime(2026, 7, 9, 20, 19),
           "vision_json": {"site": "GGPoker", "entrants": 500,
                           "starting_stack": 30000, "open_tab": "Prize Pool",
                           "prizes": {"1": 100.0}},
           "result": "tm_not_found"}

    def _q(sql, params=None):
        if "FROM lobby_processing_log" in sql:
            return [row]
        return []

    with patch.object(lobby_sync, "query", side_effect=_q), \
         patch.object(lobby_sync.tournament_resolver, "resolve_tournament_number",
                      return_value=("295219051", [], "tier2")), \
         patch.object(lobby_sync, "_resolve_via_hero_anchor", return_value=None), \
         patch.object(lobby_sync, "check_vj_payout_coherent",
                      return_value=(True, None)), \
         patch.object(lobby_sync.lobby_vision, "build_hrc_payouts_blob",
                      return_value={"structures": [{"chips": 123.0}]}), \
         patch.object(lobby_sync.payouts_service, "upsert_payout",
                      return_value={"action": "inserted"}) as mpay, \
         patch.object(lobby_sync, "_upsert_lobby_log"):
        res = lobby_sync.reconcile_lobby_logs(message_ids=["g1"])
    assert res["written"] == 1
    assert "wn_chips" not in res["items"][0]
    sent = mpay.call_args.kwargs
    assert sent["payouts_json"]["structures"][0]["chips"] == 123.0
    assert sent["wn_chips_meta"] is None


# ── wn_chips_recalc (F4) — ensaio vs aplicar ─────────────────────────────────
def _recalc_fixtures():
    payout_rows = [
        {"tournament_number": "1120632836", "source": "file_lobby_vision:x",
         "payouts_json": {"structures": [{"name": "HIGHROLLER",
                                          "chips": 819984.0}]}},
        {"tournament_number": "999", "source": "manual:rui",
         "payouts_json": {"structures": [{"name": "MANUAL", "chips": 5.0}]}},
    ]
    log_rows = [
        {"posted_at": datetime(2026, 7, 2, 22, 28),
         "vision_json": {"entrants": 56, "starting_stack": 20000,
                         "reg_open": False, "re_entries": 11}},
    ]

    def _q(sql, params=None):
        if "FROM tournament_payouts" in sql:
            return payout_rows
        if "FROM lobby_processing_log" in sql:
            return log_rows
        if "FROM hands" in sql:
            return [{"tournament_number": "1120632836",
                     "hands": 21, "solves_done": 0}]
        return []

    return _q


def test_recalc_dry_run_never_writes():
    from app.services import lobby_sync
    with patch.object(lobby_sync, "query", side_effect=_recalc_fixtures()), \
         patch.object(lobby_sync, "execute") as mexec:
        res = lobby_sync.wn_chips_recalc(dry_run=True)
    mexec.assert_not_called()
    assert res["dry_run"] is True
    assert res["updated"] == 0
    assert res["skipped_precedence"] == 1               # manual: intacto (D11)
    it = next(i for i in res["items"] if i["tournament_number"] == "1120632836")
    assert it["action"] == "would_update"
    assert it["old_chips"] == 819984.0
    assert it["new_chips"] == 1_120_000.0
    assert it["delta_pct"] == 36.59
    assert it["state"] == "running" and it["provisional"] is False
    assert it["hands"] == 21 and it["solves_done"] == 0


def test_recalc_apply_writes_and_preserves_source():
    from app.services import lobby_sync
    with patch.object(lobby_sync, "query", side_effect=_recalc_fixtures()), \
         patch.object(lobby_sync, "execute") as mexec:
        res = lobby_sync.wn_chips_recalc(dry_run=False)
    assert res["updated"] == 1
    mexec.assert_called_once()
    sql, params = mexec.call_args.args
    assert "UPDATE tournament_payouts" in sql
    assert "source" not in sql                          # source PRESERVADO
    assert params[0]["structures"][0]["chips"] == 1_120_000.0
    assert params[1] == "running" and params[2] is False
    assert params[4] == 11                              # re_entries info-only
    assert params[5] == "1120632836"
