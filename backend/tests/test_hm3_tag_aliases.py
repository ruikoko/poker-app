from app.services.hm3_tag_aliases import apply_hm3_tag_aliases


def test_apply_hm3_tag_aliases_renames_gtw_to_pos_nko():
    assert apply_hm3_tag_aliases("GTw") == "pos-nko"


def test_apply_hm3_tag_aliases_passthrough_unknown():
    assert apply_hm3_tag_aliases("PKO SS") == "PKO SS"


def test_apply_hm3_tag_aliases_renames_nota_plus_to_nota():
    assert apply_hm3_tag_aliases("nota++") == "nota"


def test_apply_hm3_tag_aliases_preserves_nota_ex():
    # 'nota ex' tem significado distinto (nota exemplar p/ ML) — NÃO é aliased.
    assert apply_hm3_tag_aliases("nota ex") == "nota ex"
