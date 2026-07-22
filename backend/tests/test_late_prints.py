"""Painel 'Prints fora de tempo' + RECONCILIAÇÃO (régua do Rui, 22 Jul): gatilho <9s na
TAG (pos/nota), FT fora, dispensadas fora; veredito por par (PROVADO = HH confirma dos
DOIS lados; senão SUSPEITA com razão). Factos pelos helpers únicos de hh_facts
(hero_postflop substitui o antigo had_flop; nota=showdown SÓ neste exercício)."""
from unittest.mock import patch
from app.routers import gg_health


def _raw(hero_postflop=False, shows=False):
    parts = ["Table '5' 8-max"]
    if hero_postflop:
        parts += ["*** FLOP *** [Ah 2c 3d]", "Hero: checks"]
    else:
        parts += ["Hero: folds"]
    if shows:
        parts += ["*** SHOWDOWN ***", "a1: shows [Ah Kd] (a pair)"]
    parts += ["*** SUMMARY ***"]
    return "\n".join(parts)


def _row(ssid, iv_s, hid, db_id, folder="pos-pko", reason="filename_hand_id",
         hand_tags=None, hero_postflop=False, shows=False):
    return {"ssid": ssid, "folder_tag": folder, "cap": f"2026-07-12 10:00:{iv_s:02d}",
            "reason_detail": reason, "db_id": db_id, "hand_id": hid,
            "pa": "2026-07-12 10:00:00", "tn": "T1",
            "discord_tags": hand_tags if hand_tags is not None else [folder],
            "hm3_tags": None, "raw": _raw(hero_postflop, shows)}


def _prev(hid="GG-PREV", hero_postflop=True, shows=False, tags=None, has_img=True):
    return [{"id": 99, "hand_id": hid, "pa": "2026-07-12 09:58:00",
             "raw": _raw(hero_postflop, shows), "discord_tags": tags or [],
             "hm3_tags": None, "entry_id": 7, "has_img": has_img}]


def _run(main, prevs, dismissed=None):
    # ordem das queries: dispensadas → main → 1 prev-query por linha que passa o corte
    side = [dismissed or [], main] + prevs
    with patch.object(gg_health, "query", side_effect=side):
        return gg_health.late_prints(current_user={})


def test_pos_provado_atual_sem_posflop_anterior_com():
    res = _run([_row(1, 5, "GG-A", 11, hero_postflop=False)], [_prev(hero_postflop=True)])
    h = res["pos"][0]
    assert h["verdict"] == "provado"
    assert h["hero_postflop"] is False and h["prev"]["hero_postflop"] is True
    assert res["counts"] == {"pos": 1, "nota": 0, "provados": 1, "suspeitas": 0}


def test_pos_suspeita_quando_posflop_nas_duas():
    res = _run([_row(1, 5, "GG-A", 11, hero_postflop=True)], [_prev(hero_postflop=True)])
    h = res["pos"][0]
    assert h["verdict"] == "suspeita" and "DUAS" in h["verdict_reason"]


def test_pos_suspeita_quando_anterior_sem_posflop_ou_inexistente():
    res = _run([_row(1, 5, "GG-A", 11)], [_prev(hero_postflop=False)])
    assert res["pos"][0]["verdict"] == "suspeita"
    res2 = _run([_row(1, 5, "GG-B", 12)], [[]])          # sem anterior na mesma mesa
    assert res2["pos"][0]["verdict"] == "suspeita"
    assert "sem mão anterior" in res2["pos"][0]["verdict_reason"]


def test_nota_provado_por_showdown_real_e_marcador_espurio_nao_conta():
    # nota=showdown SÓ neste exercício: anterior COM shows reais + atual sem → provado
    res = _run([_row(1, 3, "GG-N", 13, folder="nota")],
               [_prev(hero_postflop=False, shows=True)])
    assert res["nota"][0]["verdict"] == "provado"
    # anterior só com o MARCADOR (sem 'shows') → não confirma
    prev_marker = _prev(hero_postflop=False, shows=False)
    prev_marker[0]["raw"] += "\n*** SHOWDOWN ***"
    res2 = _run([_row(1, 3, "GG-N2", 14, folder="nota")], [prev_marker])
    assert res2["nota"][0]["verdict"] == "suspeita"


def test_final_table_e_9s_e_icm_continuam_fora():
    main = [
        _row(1, 5, "GG-FT", 20, folder="pos-pko-ft", hand_tags=["pos-pko-ft"]),
        _row(2, 9, "GG-9S", 21),                          # >=9s → fora
        _row(3, 5, "GG-ICM", 22, folder="icm-pko"),       # icm → fora das listas
        _row(4, 5, "GG-OK", 23),
    ]
    # icm passa o corte <9s (só sai na divisão pos/nota) → também consome 1 prev-query
    res = _run(main, [_prev(), _prev()])
    assert res["counts"]["pos"] == 1 and res["counts"]["nota"] == 0
    assert res["pos"][0]["hand_id"] == "GG-OK"


def test_par_resolvido_sai_da_lista():
    # LEI 1 (apanhado pelo Rui, 22 Jul): tag movida/tirada da mão → a captura ainda
    # tem folder_tag, mas o par está RESOLVIDO → não volta à lista.
    main = [
        _row(1, 5, "GG-MOVIDA", 11, folder="pos-pko", hand_tags=[]),        # tag já saiu
        _row(2, 5, "GG-AINDA", 12, folder="pos-pko", hand_tags=["pos-pko"]),
    ]
    res = _run(main, [_prev()])
    assert [h["hand_id"] for h in res["pos"]] == ["GG-AINDA"]
    assert res["counts"]["pos"] == 1


def test_dispensadas_ficam_fora():
    res = _run([_row(1, 5, "GG-A", 11), _row(2, 5, "GG-B", 12)],
               [_prev()], dismissed=[{"ssid": 1}])
    assert [h["hand_id"] for h in res["pos"]] == ["GG-B"]


def test_row_fields_imagem_e_prev_enriquecida():
    res = _run([_row(1, 5, "GG-A", 11)], [_prev(tags=["icm"], has_img=True)])
    h = res["pos"][0]
    assert h["image_url"] == "/api/table-ss/image/1"
    assert h["match_method"] == "filename_hand_id"
    p = h["prev"]
    assert p["hand_id"] == "GG-PREV" and p["tags"] == ["icm"]
    assert p["image_url"] == "/api/screenshots/image/7"
    assert "had_flop" not in h                        # a meia-duplicação morreu
