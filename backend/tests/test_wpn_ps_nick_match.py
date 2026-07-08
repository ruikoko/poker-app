"""#WPN-PS-TABLE-SS-TIME-ONLY-MATCH — WPN/PS não têm nome de torneio fiável; o match
da captura de mesa passa a validar-se por SOBREPOSIÇÃO DE NICKS (HH WPN/PS têm nicks
reais; a Vision lê-os). Divergência → não casa (orphan honesto). Sem dados reais (0
capturas WPN/PS), teste sintético."""
from app.routers.table_ss import _resolve_match

_RAW_A = ("Seat 1: Alice (100.00)\nSeat 2: Bob (100.00)\n"
          "Seat 3: Carol (100.00)\nSeat 4: Dave (100.00)\n")
_RAW_B = ("Seat 1: Xavier (100.00)\nSeat 2: Yara (100.00)\n"
          "Seat 3: Zoe (100.00)\nSeat 4: Walt (100.00)\n")


def _cand(raw, hand_id="H", cid=1, tn="T1"):
    return {"id": cid, "hand_id": hand_id, "tournament_number": tn,
            "tournament_name": "$30,000 GTD", "site": "WPN", "raw": raw}


def _vj(nicks):
    return {"tournament_name": "$30,000 GTD", "seats": [{"nick": n} for n in nicks]}


def test_wpn_nick_fit_matches():
    r = _resolve_match(None, _vj(["Alice", "Bob", "Carol"]), "WPN", [_cand(_RAW_A)])
    assert r["matched"] is not None and r["reason"] == "single_tn"


def test_wpn_nick_mismatch_is_orphan():
    # a mão (mesma tn, mesa ERRADA) tem outros jogadores → NÃO casa
    r = _resolve_match(None, _vj(["Alice", "Bob", "Carol"]), "WPN", [_cand(_RAW_B)])
    assert r["matched"] is None and "wpn_ps_nick_mismatch" in r["reason"]


def test_wpn_picks_best_nick_fit_among_same_tn():
    # multi-tabling: o candidato mais próximo no tempo ([0]) é a mesa errada (B),
    # mas os nicks apontam a A → escolhe A (não a hora)
    cands = [_cand(_RAW_B, "Hb", 2), _cand(_RAW_A, "Ha", 1)]
    r = _resolve_match(None, _vj(["Alice", "Bob", "Carol"]), "WPN", cands)
    assert r["matched"]["hand_id"] == "Ha"


def test_wpn_few_nicks_falls_back_to_time():
    # SS leu só 2 nicks (< mínimo) → sinal insuficiente → leniente (proximidade temporal)
    r = _resolve_match(None, _vj(["Alice", "Bob"]), "WPN", [_cand(_RAW_B, "Hb")])
    assert r["matched"]["hand_id"] == "Hb" and r["reason"] == "single_tn"


def test_gg_unaffected_uses_name():
    # GG é sala de nome fiável → valida por NOME, não por nicks (regra intocada)
    vj = {"tournament_name": "ZENITH", "seats": [{"nick": "x"}]}
    cand = {"id": 1, "hand_id": "G", "tournament_number": "T1",
            "tournament_name": "ZENITH", "site": "GGPoker", "raw": _RAW_B}
    r = _resolve_match(None, vj, "GGPoker", [cand])
    assert r["matched"] is not None and r["reason"] == "single_tn"
