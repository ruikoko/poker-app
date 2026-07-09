"""#TS-LATE-NO-FORMAT-RECALC — decisão PURA de reclassificação de formato (GG).

Cobre o caso (a) "o TS corrige a classificação name-only da HH" e as guardas de não-mudança
(idempotência + não rebaixar KO específico). A parte (b) — re-scrub das coroas — é o MESMO
`scrub_and_persist` já provado (test_eliminated_bounty, 26 verdes + prova read-only na mão real):
o trigger apenas o re-invoca depois de o TS existir, e ele lê o TS live → resultado idêntico ao
de um enrich com TS presente (TS-primeiro). A integração DB (0 mãos = no-op no ritual TS-primeiro)
é verificável ao vivo pós-deploy.
"""
from app.services.ts_reclassify import _reclassified_format, reclassify_and_rescrub_for_tns


def test_ts_corrects_name_silent_vanilla_to_pko_when_bounty():
    # (a) HH classificou 'Vanilla' pelo nome mudo; o TS diz que TEM bounty → corrige p/ PKO.
    assert _reclassified_format("Vanilla", "Daily Special", has_bounty=True) == "PKO"


def test_ts_keeps_vanilla_when_no_bounty():
    # GG-6138905902 (Daily Hyper $60): nome mudo + TS sem bounty → fica Vanilla (sem mudança).
    assert _reclassified_format("Vanilla", "Daily Hyper $60", has_bounty=False) is None


def test_name_already_carries_format_no_change():
    # Nome já diz bounty → PKO por nome; TS concorda → sem mudança (idempotente).
    assert _reclassified_format("PKO", "Bounty Hunters Special $150", has_bounty=True) is None


def test_no_downgrade_mystery_to_pko():
    # Mystery KO (específico) NÃO é rebaixado a PKO por um sinal de bounty genérico.
    assert _reclassified_format("Mystery KO", "Mystery Battle", has_bounty=True) is None


def test_no_downgrade_super_ko_to_pko():
    assert _reclassified_format("Super KO", "Some KO", has_bounty=True) is None


def test_aggregator_empty_is_noop():
    # TS-primeiro (ritual normal): sem tns / sem mãos → no-op puro (não toca BD).
    r = reclassify_and_rescrub_for_tns([])
    assert r == {"tns": 0, "reclassified": 0, "rescrubbed": 0, "hrc_stale": [], "per_tn": []}
    assert reclassify_and_rescrub_for_tns(None)["reclassified"] == 0
