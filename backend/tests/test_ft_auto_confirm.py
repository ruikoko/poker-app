"""Auto-confirmação das fronteiras FT (decisão do Rui, 22 Jul — REGISTO_CONCEITO (d)).

Régua (fonte única `auto_confirm_witness`): a app só confirma sozinha com fronteira
computada + cross-check MATCH + testemunha INDEPENDENTE (TS com o Hero dentro da FT,
ou N do lobby a bater com os sentados). Match trivial (HH juiz de si própria) NÃO
confirma; decisões do Rui NUNCA são pisadas; dispensa reativada renasce PENDENTE;
a promoção (tags -ft) continua 100% manual — isto só fixa a fronteira."""
import datetime as dt
from unittest.mock import patch

import app.services.ft_boundary as fb

_B = dt.datetime(2026, 7, 14, 20, 52, 54)


def _d(source="hh_table_transition", status="transition", n=7, hh_seats=7,
       match=True, extra_cc=None, boundary=_B):
    cc = {"n": n, "hh_seats": hh_seats, "match": match}
    if extra_cc:
        cc.update(extra_cc)
    return {"boundary": boundary, "source": source, "status": status, "n": n,
            "cross_check": cc}


# ── a régua da testemunha (auto_confirm_witness) ─────────────────────────────
def test_witness_lobby_n(monkeypatch):
    monkeypatch.setattr(fb, "_lobby_ft_boundary", lambda tn: (_B, 7))
    monkeypatch.setattr(fb, "_ts_hero_position", lambda tn: None)
    assert fb.auto_confirm_witness("T", _d(), "match") == "lobby_n"


def test_witness_ts_via_ts_agrees(monkeypatch):
    monkeypatch.setattr(fb, "_lobby_ft_boundary", lambda tn: (None, None))
    monkeypatch.setattr(fb, "_ts_hero_position", lambda tn: None)
    d = _d(extra_cc={"ts_agrees": True})
    assert fb.auto_confirm_witness("T", d, "match") == "ts"


def test_witness_ts_positional(monkeypatch):
    monkeypatch.setattr(fb, "_lobby_ft_boundary", lambda tn: (None, None))
    monkeypatch.setattr(fb, "_ts_hero_position", lambda tn: 5)
    assert fb.auto_confirm_witness("T", _d(source="propagated_coherent",
                                           status="coherent"), "match") == "ts"
    # Hero acabou FORA da FT (9 > N=7) → não é testemunha a favor
    monkeypatch.setattr(fb, "_ts_hero_position", lambda tn: 9)
    assert fb.auto_confirm_witness("T", _d(source="propagated_coherent",
                                           status="coherent"), "match") is None


def test_trivial_match_does_not_confirm(monkeypatch):
    """★ Obrigatório: fonte T sem lobby e sem TS — o N veio da própria HH, o
    cross-check bate TRIVIALMENTE (HH juiz de si própria) → SEM testemunha →
    não auto-confirma (fica «Prontas a aprovar»)."""
    monkeypatch.setattr(fb, "_lobby_ft_boundary", lambda tn: (None, None))
    monkeypatch.setattr(fb, "_ts_hero_position", lambda tn: None)
    assert fb.auto_confirm_witness("T", _d(), "match") is None


def test_no_witness_without_boundary_or_match():
    # guardas de entrada — nem chega a consultar lobby/TS (sem DB no teste)
    assert fb.auto_confirm_witness("T", _d(boundary=None), "match") is None
    assert fb.auto_confirm_witness("T", _d(match=False), "mismatch") is None
    assert fb.auto_confirm_witness("T", _d(match=None), "n_unavailable") is None


# ── refresh: auto confirma, nunca pisa o Rui ─────────────────────────────────
_RUI_ROWS = {
    "conf": {"decision": "confirmed", "decided_by": "ruidias@ilhavo.org"},
    "conf_api": {"decision": "confirmed", "decided_by": "api"},   # Bearer = humano
    "corr": {"decision": "corrected", "decided_by": "ruidias@ilhavo.org"},
    "prom": {"decision": "promoted", "decided_by": "ruidias@ilhavo.org"},
    "dis": {"decision": "dismissed", "decided_by": "ruidias@ilhavo.org",
            "decided_at": _B},
}


def test_refresh_never_overrides_rui_decisions():
    """★ Obrigatório: mesmo com a régua a passar (testemunha presente), NENHUMA
    decisão humana é tocada — confirmed/corrected/promoted intocados, dismissed
    sem sinal novo fica dispensado."""
    writes = []
    with patch.object(fb, "_candidate_tns", return_value=list(_RUI_ROWS)), \
         patch.object(fb, "_review_row", side_effect=lambda tn: dict(_RUI_ROWS[tn])), \
         patch.object(fb, "compute_ft_boundary", return_value=_d()), \
         patch.object(fb, "auto_confirm_witness", return_value="ts"), \
         patch.object(fb, "has_new_ft_signal", return_value=False), \
         patch.object(fb, "_upsert_review_decision",
                      side_effect=lambda *a: writes.append(("decision", a))), \
         patch.object(fb, "_upsert_review_snapshot",
                      side_effect=lambda *a, **k: writes.append(("snapshot", a, k))):
        res = fb.refresh_ft_boundaries()
    assert writes == []
    assert res == {"refreshed": 0, "reactivated": 0,
                   "auto_confirmed": 0, "auto_reverted": 0}


def test_refresh_auto_confirms_pending_with_witness():
    writes = []
    with patch.object(fb, "_candidate_tns", return_value=["novo", "pend"]), \
         patch.object(fb, "_review_row",
                      side_effect=lambda tn: None if tn == "novo" else {"decision": "pending"}), \
         patch.object(fb, "compute_ft_boundary", return_value=_d()), \
         patch.object(fb, "auto_confirm_witness", return_value="lobby_n"), \
         patch.object(fb, "_upsert_review_decision",
                      side_effect=lambda tn, d, s, decision, by: writes.append((tn, decision, by))):
        res = fb.refresh_ft_boundaries()
    assert writes == [("novo", "confirmed", fb.AUTO_DECIDED_BY),
                      ("pend", "confirmed", fb.AUTO_DECIDED_BY)]
    assert res["auto_confirmed"] == 2 and res["refreshed"] == 0


def test_refresh_trivial_stays_pending():
    """★ Obrigatório (lado do refresh): régua devolve None (match trivial) → snapshot
    pending, nunca decision='confirmed'."""
    snaps, decs = [], []
    with patch.object(fb, "_candidate_tns", return_value=["T"]), \
         patch.object(fb, "_review_row", return_value=None), \
         patch.object(fb, "compute_ft_boundary", return_value=_d()), \
         patch.object(fb, "auto_confirm_witness", return_value=None), \
         patch.object(fb, "_upsert_review_decision",
                      side_effect=lambda *a: decs.append(a)), \
         patch.object(fb, "_upsert_review_snapshot",
                      side_effect=lambda tn, d, s, decision: snaps.append((tn, decision))):
        res = fb.refresh_ft_boundaries()
    assert decs == [] and snaps == [("T", "pending")]
    assert res["auto_confirmed"] == 0 and res["refreshed"] == 1


def test_refresh_auto_revises_own_confirmation():
    """A app pode rever a PRÓPRIA decisão: dados novos invalidam a régua → volta a
    pending (assinatura limpa) e regressa ao painel."""
    row = {"decision": "confirmed", "decided_by": fb.AUTO_DECIDED_BY,
           "status": "match", "boundary": _B, "n_lobby": 7, "seats_first_hand": 7}
    writes = []
    with patch.object(fb, "_candidate_tns", return_value=["T"]), \
         patch.object(fb, "_review_row", return_value=dict(row)), \
         patch.object(fb, "compute_ft_boundary",
                      return_value=_d(status="quarantine_disagreement", match=False)), \
         patch.object(fb, "auto_confirm_witness", return_value=None), \
         patch.object(fb, "_upsert_review_decision",
                      side_effect=lambda tn, d, s, decision, by: writes.append((decision, by))):
        res = fb.refresh_ft_boundaries()
    assert writes == [("pending", None)]
    assert res["auto_reverted"] == 1


def test_refresh_auto_keep_is_idempotent_no_churn():
    """Auto-confirmada, régua ainda passa, base IGUAL → zero escrita (não re-assina o
    decided_at a cada import)."""
    row = {"decision": "confirmed", "decided_by": fb.AUTO_DECIDED_BY,
           "status": "match", "boundary": _B, "n_lobby": 7, "seats_first_hand": 7}
    writes = []
    with patch.object(fb, "_candidate_tns", return_value=["T"]), \
         patch.object(fb, "_review_row", return_value=dict(row)), \
         patch.object(fb, "compute_ft_boundary", return_value=_d()), \
         patch.object(fb, "auto_confirm_witness", return_value="ts"), \
         patch.object(fb, "_upsert_review_decision",
                      side_effect=lambda *a: writes.append(a)), \
         patch.object(fb, "_upsert_review_snapshot",
                      side_effect=lambda *a, **k: writes.append(a)):
        res = fb.refresh_ft_boundaries()
    assert writes == []
    assert res == {"refreshed": 0, "reactivated": 0,
                   "auto_confirmed": 0, "auto_reverted": 0}


def test_reactivated_dismiss_goes_pending_not_confirmed():
    """Dispensa do Rui + sinal novo forte → renasce PENDENTE (o Rui re-decide);
    nunca auto-confirma por cima da dispensa, mesmo com testemunha."""
    row = {"decision": "dismissed", "decided_by": "ruidias@ilhavo.org", "decided_at": _B}
    snaps, decs = [], []
    with patch.object(fb, "_candidate_tns", return_value=["T"]), \
         patch.object(fb, "_review_row", return_value=dict(row)), \
         patch.object(fb, "compute_ft_boundary", return_value=_d()), \
         patch.object(fb, "auto_confirm_witness", return_value="ts"), \
         patch.object(fb, "has_new_ft_signal", return_value=True), \
         patch.object(fb, "_upsert_review_decision",
                      side_effect=lambda *a: decs.append(a)), \
         patch.object(fb, "_upsert_review_snapshot",
                      side_effect=lambda tn, d, s, decision: snaps.append((tn, decision))):
        res = fb.refresh_ft_boundaries()
    assert decs == [] and snaps == [("T", "pending")]
    assert res["reactivated"] == 1 and res["auto_confirmed"] == 0
