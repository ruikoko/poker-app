"""Painel 'Prints fora de tempo': RÉGUA DOS 6s (lei do Rui, 22 Jul — ≤6s pertence à
mão anterior, com tag ou SEM tag; FT fora) + régua original na TAG pos/nota em
(6,9)s com veredito por par (PROVADO = HH confirma dos dois lados). Factos pelos
helpers únicos de hh_facts; nota=showdown SÓ neste exercício."""
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
            "discord_tags": hand_tags if hand_tags is not None else ([folder] if folder else []),
            "hm3_tags": None, "raw": _raw(hero_postflop, shows)}


def _prev(hid="GG-PREV", hero_postflop=True, shows=False, tags=None, has_img=True):
    return [{"id": 99, "hand_id": hid, "pa": "2026-07-12 09:58:00",
             "raw": _raw(hero_postflop, shows), "discord_tags": tags or [],
             "hm3_tags": None, "entry_id": 7, "has_img": has_img}]


def _run(main, prevs, dismissed=None, awaiting=None, ft_states=None):
    # ordem: dispensadas → main → prevs… → query da secção "à espera de tag".
    # hand_ft_state (fonte única 22 Jul) simulado só-tags por defeito (comporta-
    # mento antigo); ft_states: tn→estado forçado p/ testar a fronteira sem tag.
    side = [dismissed or [], main] + prevs + [awaiting or []]
    fake_ft = (lambda tn, pa, tags=None, cache=None:
               "ft" if any(str(t).endswith("-ft") for t in (tags or []))
               else (ft_states or {}).get(tn, "not_ft"))
    with patch.object(gg_health, "query", side_effect=side), \
         patch.object(gg_health, "hand_ft_state", fake_ft):
        return gg_health.late_prints(current_user={})


# ── régua original (6,9)s na TAG — vereditos ─────────────────────────────────

def test_pos_provado_janela_7s():
    res = _run([_row(1, 7, "GG-A", 11, hero_postflop=False)], [_prev(hero_postflop=True)])
    h = res["pos"][0]
    assert h["verdict"] == "provado"
    assert res["counts"]["provados"] == 1 and res["counts"]["regra6s"] == 0


def test_pos_suspeita_posflop_nas_duas_e_sem_anterior():
    res = _run([_row(1, 7, "GG-A", 11, hero_postflop=True)], [_prev(hero_postflop=True)])
    assert res["pos"][0]["verdict"] == "suspeita"
    res2 = _run([_row(1, 8, "GG-B", 12)], [[]])
    assert "sem mão anterior" in res2["pos"][0]["verdict_reason"]


def test_nota_showdown_real_confirma_marcador_espurio_nao():
    res = _run([_row(1, 7, "GG-N", 13, folder="nota")],
               [_prev(hero_postflop=False, shows=True)])
    assert res["nota"][0]["verdict"] == "provado"
    prev_marker = _prev(hero_postflop=False, shows=False)
    prev_marker[0]["raw"] += "\n*** SHOWDOWN ***"
    res2 = _run([_row(1, 7, "GG-N2", 14, folder="nota")], [prev_marker])
    assert res2["nota"][0]["verdict"] == "suspeita"


# ── RÉGUA DOS 6s (≤6s, qualquer tag e sem tag) ───────────────────────────────

def test_regra6s_apanha_sem_tag_e_qualquer_tag():
    main = [
        _row(1, 3, "GG-SEMTAG", 11, folder=None, hand_tags=[]),      # sem tag → regra6s
        _row(2, 6, "GG-ICM", 12, folder="icm-pko"),                  # 6s INCLUSIVE, icm → regra6s
        _row(3, 2, "GG-POS", 13, folder="pos-pko"),                  # pos ≤6s → regra6s (não pos)
        _row(4, 7, "GG-SEMTAG7", 14, folder=None, hand_tags=[]),     # sem tag >6s → fora de tudo
    ]
    res = _run(main, [_prev(), _prev(), _prev()])
    assert res["counts"]["regra6s"] == 3 and res["counts"]["pos"] == 0
    ids = [r["hand_id"] for r in res["regra6s"]]
    assert set(ids) == {"GG-SEMTAG", "GG-ICM", "GG-POS"}
    sem = [r for r in res["regra6s"] if r["hand_id"] == "GG-SEMTAG"][0]
    assert sem["folder_tag"] is None and sem["verdict"] is None
    pos = [r for r in res["regra6s"] if r["hand_id"] == "GG-POS"][0]
    assert pos["verdict"] in ("provado", "suspeita")     # veredito continua a informar


def test_ft_fora_de_tudo_e_9s_fora():
    main = [
        _row(1, 3, "GG-FT", 20, folder="pos-pko-ft", hand_tags=["pos-pko-ft"]),
        _row(2, 9, "GG-9S", 21),
        _row(3, 3, "GG-OK", 22),
    ]
    res = _run(main, [_prev()])
    assert res["counts"]["regra6s"] == 1
    assert res["regra6s"][0]["hand_id"] == "GG-OK"


def test_ft_por_fronteira_sem_tag_fora_e_unknown_fica():
    """22 Jul: a exclusão de FT deixou de ser só-tags — FT pela FRONTEIRA (mão sem
    tag nenhuma) sai da lista; 'unknown' (fonte cega) FICA (painel manual)."""
    main = [
        _row(1, 3, "GG-FTSEM", 30, folder=None, hand_tags=[]),
        _row(2, 3, "GG-CEGO", 31, folder=None, hand_tags=[]),
    ]
    main[0]["tn"] = "FT_SEM_TAG"
    main[1]["tn"] = "CEGO"
    res = _run(main, [_prev()], ft_states={"FT_SEM_TAG": "ft", "CEGO": "unknown"})
    assert [h["hand_id"] for h in res["regra6s"]] == ["GG-CEGO"]


def test_par_resolvido_sai_da_lista():
    # LEI 1: tag movida/tirada da mão → sai (aplica-se ao ramo com-tag das duas janelas)
    main = [
        _row(1, 3, "GG-MOVIDA", 11, folder="pos-pko", hand_tags=[]),
        _row(2, 3, "GG-AINDA", 12, folder="pos-pko", hand_tags=["pos-pko"]),
        _row(3, 7, "GG-MOVIDA7", 13, folder="pos-pko", hand_tags=[]),
    ]
    res = _run(main, [_prev()])
    assert [r["hand_id"] for r in res["regra6s"]] == ["GG-AINDA"]
    assert res["counts"]["pos"] == 0


def test_dispensadas_ficam_fora():
    res = _run([_row(1, 3, "GG-A", 11), _row(2, 3, "GG-B", 12)],
               [_prev()], dismissed=[{"ssid": 1}])
    assert [h["hand_id"] for h in res["regra6s"]] == ["GG-B"]


def test_awaiting_tag_lista_donas_sem_tag_e_sai_ao_tagar():
    aw = [
        {"ssid": 5, "hand_id": "GG-DONA", "folder_tag": None, "decision": "auto_moved",
         "hand_db_id": 40, "pa": "2026-07-12 09:58:00", "tournament_name": "T",
         "dt": [], "ht": None},
        {"ssid": 6, "hand_id": "GG-JATAGADA", "folder_tag": None, "decision": "auto_moved",
         "hand_db_id": 41, "pa": "2026-07-12 09:59:00", "tournament_name": "T",
         "dt": ["nota"], "ht": None},
    ]
    res = _run([], [], awaiting=aw)
    assert res["counts"]["awaiting_tag"] == 1                 # a já-tagada saiu (LEI 1)
    assert res["awaiting_tag"][0]["hand_id"] == "GG-DONA"
    assert res["awaiting_tag"][0]["moved_by"] == "auto_moved"


def test_row_fields_imagem_e_prev_enriquecida():
    res = _run([_row(1, 7, "GG-A", 11)], [_prev(tags=["icm"], has_img=True)])
    h = res["pos"][0]
    assert h["image_url"] == "/api/table-ss/image/1"
    p = h["prev"]
    assert p["hand_id"] == "GG-PREV" and p["tags"] == ["icm"]
    assert p["image_url"] == "/api/screenshots/image/7"
    assert "had_flop" not in h
