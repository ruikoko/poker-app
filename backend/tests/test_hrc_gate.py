"""pt41 #HERO-BOUNTY-FROM-TS-DERIVATION — gate Andar 1 (bounty exige TS, Mystery
excluído) + lookup_bounties + pending_ts_hands. Mocka `query` (sem DB)."""
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import patch

from app.services import hrc_queue


def test_andar1_sql_has_bounty_gate_and_params():
    """O SQL do Andar 1 aplica: Mystery fora + GG bounty-gated exige TS com
    buy_in_bounty. Params terminam em MYSTERY_FORMATS, TS_GATED_FORMATS."""
    captured = {}

    def fake_query(sql, params):
        captured["sql"] = sql
        captured["params"] = params
        return []

    dt = datetime(2026, 5, 1, tzinfo=timezone.utc)
    with patch("app.services.hrc_queue.query", side_effect=fake_query):
        hrc_queue.select_andar1_rows(["icm pko"], ["new"], dt, dt)

    sql = captured["sql"]
    assert "tournament_summaries" in sql
    assert "buy_in_bounty IS NOT NULL" in sql
    assert "<> ALL(%s::text[])" in sql            # mystery + ts_gated exclusions
    assert "site <> 'GGPoker'" in sql             # gate é GG-only (Winamax/PS passam)
    # params terminam em MYSTERY, TS_GATED (GG), wpn_tags, wpn_tags (#WPN-ICM-TAG-GATE)
    wpn_norm = hrc_queue.normalize_tags_basket(hrc_queue.WPN_ALLOWED_TAGS)
    assert captured["params"][-4] == list(hrc_queue.MYSTERY_FORMATS)
    assert captured["params"][-3] == list(hrc_queue.TS_GATED_FORMATS)
    assert captured["params"][-2] == wpn_norm
    assert captured["params"][-1] == wpn_norm


def test_andar1_wpn_in_sites_and_icm_tag_gated():
    """#WPN-ICM-TAG-GATE — WPN entra no Andar 1 (ALLOWED_SITES) mas SÓ com tag ICM:
    a cláusula `site <> 'WPN' OR tag ∈ WPN_ALLOWED_TAGS` exige a tag do Rui (a sua
    classificação), NÃO o formato. GG/PS/WN inalteradas (cláusula só morde WPN)."""
    captured = {}

    def fake_query(sql, params):
        captured["sql"] = sql
        captured["params"] = params
        return []

    dt = datetime(2026, 5, 1, tzinfo=timezone.utc)
    with patch("app.services.hrc_queue.query", side_effect=fake_query):
        hrc_queue.select_andar1_rows(["icm"], ["new"], dt, dt)

    assert "WPN" in hrc_queue.ALLOWED_SITES                  # WPN elegível
    assert "site <> 'WPN'" in captured["sql"]                # gate WPN por tag
    assert "site <> 'GGPoker'" in captured["sql"]            # gate GG intacto (sem regressão)
    assert "WPN-ICM-TAG-GATE" in captured["sql"]             # gate por TAG presente
    assert captured["params"][0] == hrc_queue.ALLOWED_SITES  # WPN no filtro de sites
    # o gate WPN passou a ser por tag (params = WPN_ALLOWED_TAGS norm, hm3+discord),
    # já NÃO por formato (era list(TS_GATED_FORMATS)).
    wpn_norm = hrc_queue.normalize_tags_basket(hrc_queue.WPN_ALLOWED_TAGS)
    assert captured["params"][-1] == wpn_norm                # gate WPN: tags ICM (discord)
    assert captured["params"][-2] == wpn_norm                # gate WPN: tags ICM (hm3)
    assert wpn_norm != list(hrc_queue.TS_GATED_FORMATS)      # confirma: não é o gate por formato


def test_andar1_wpn_gate_icm_in_pko_out():
    """Semântica do #WPN-ICM-TAG-GATE avaliada em Python (espelho da cláusula SQL):
    WPN com tag ICM/ICM FT entra; WPN com PKO (ou sem tag ICM) fica de fora;
    GG/PS/WN imunes a esta cláusula. Prova 'tag ICM entra · PKO fica de fora'."""
    norm = hrc_queue.normalize_tag_key
    wpn_norm = set(hrc_queue.normalize_tags_basket(hrc_queue.WPN_ALLOWED_TAGS))

    def wpn_clause(site, tags):  # site <> 'WPN' OR tem tag normalizada ∈ WPN_ALLOWED_TAGS
        hand_norm = {norm(t) for t in tags if norm(t)}
        return site != "WPN" or bool(hand_norm & wpn_norm)

    # WPN: ICM / ICM FT entram; PKO e outras (ou sem tag) ficam de fora
    assert wpn_clause("WPN", ["ICM"]) is True
    assert wpn_clause("WPN", ["ICM FT"]) is True
    assert wpn_clause("WPN", ["icm-pko"]) is False
    assert wpn_clause("WPN", ["PKO SS"]) is False
    assert wpn_clause("WPN", []) is False
    # outras salas: nunca excluídas por esta cláusula (mesmo sem tag ICM)
    for s in ("GGPoker", "PokerStars", "Winamax"):
        assert wpn_clause(s, ["icm-pko"]) is True
        assert wpn_clause(s, []) is True


def test_andar1_sql_excludes_done_hrc_jobs():
    """#SERVER-FILTER-HRC-STATUS — o SQL do Andar 1 exclui mãos com
    hrc_jobs.status='done' (NOT EXISTS join por hand_db_id)."""
    captured = {}

    def fake_query(sql, params):
        captured["sql"] = sql
        return []

    dt = datetime(2026, 5, 1, tzinfo=timezone.utc)
    with patch("app.services.hrc_queue.query", side_effect=fake_query):
        hrc_queue.select_andar1_rows(["icm pko"], ["new"], dt, dt)

    sql = captured["sql"]
    assert "hrc_jobs" in sql
    assert "j.hand_db_id = hands.id" in sql
    assert "j.status = 'done'" in sql
    assert "NOT EXISTS" in sql


def test_andar1_sql_excludes_set_aside_hands():
    """pt92 (fila manual) — o SQL do Andar 1 exclui mãos postas DE LADO
    (hrc_jobs.meta_json.set_aside='true') da elegibilidade/lista."""
    captured = {}

    def fake_query(sql, params):
        captured["sql"] = sql
        return []

    dt = datetime(2026, 5, 1, tzinfo=timezone.utc)
    with patch("app.services.hrc_queue.query", side_effect=fake_query):
        hrc_queue.select_andar1_rows(["icm pko"], ["new"], dt, dt)

    sql = captured["sql"]
    assert "meta_json ->> 'set_aside'" in sql
    assert "= 'true'" in sql


def test_lookup_bounties_maps_and_coerces_decimal():
    rows = [
        {"site": "GGPoker", "tournament_number": "T1",
         "buy_in_bounty": Decimal("100.00"), "tournament_format": "PKO"},
        {"site": "GGPoker", "tournament_number": "T2",
         "buy_in_bounty": None, "tournament_format": "None"},
    ]
    with patch("app.services.hrc_queue.query", return_value=rows):
        out = hrc_queue.lookup_bounties([
            {"site": "GGPoker", "tournament_number": "T1"},
            {"site": "GGPoker", "tournament_number": "T2"},
        ])
    assert out[("GGPoker", "T1")]["starting_bounty"] == 100.0
    assert isinstance(out[("GGPoker", "T1")]["starting_bounty"], float)
    assert out[("GGPoker", "T2")]["starting_bounty"] is None


def test_lookup_bounties_empty_without_keys():
    assert hrc_queue.lookup_bounties([]) == {}
    assert hrc_queue.lookup_bounties(
        [{"site": None, "tournament_number": None}]) == {}


def test_pending_ts_hands_reason_mapping():
    rows = [
        {"tn": "T1", "tournament_name": "Bounty Hunters $88",
         "fmt": "pko", "n_hands": 99},
        {"tn": "T2", "tournament_name": "Sunday [Mystery Bounty]",
         "fmt": "mystery ko", "n_hands": 214},
    ]
    with patch("app.services.hrc_queue.query", return_value=rows):
        out = hrc_queue.pending_ts_hands()
    by_tn = {g["tournament_number"]: g for g in out}
    assert by_tn["T1"]["reason"] == "needs_ts_import"
    assert by_tn["T2"]["reason"] == "mystery_unsupported"
    assert by_tn["T1"]["n_hands"] == 99
