"""#TAGS pt43 — tag_family_key: agrupamento visual de famílias no Estudo.
Não toca escrita/literais; só colapsa a chave de grouping."""
from app.routers.hands import tag_family_key


def test_nota_family_groups_nota_and_nota_ex():
    assert tag_family_key("nota") == "nota"
    assert tag_family_key("nota ex") == "nota"


def test_tag_family_passthrough_other_tags():
    assert tag_family_key("icm-pko") == "icm-pko"
    assert tag_family_key("pos-pko") == "pos-pko"
    # 'nota++' não é família (tratado pelo alias a montante) → passthrough.
    assert tag_family_key("nota++") == "nota++"
