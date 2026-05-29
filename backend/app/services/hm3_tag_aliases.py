"""Aliases para renomear tags HM3 retroactivamente.

Quando o Rui descontinua uma tag no HM3 mas ela continua a vir
na exportação .bat (porque a BD do HM3 mantém a categoria), o
importer da app converte automaticamente.
"""

_HM3_TAG_RENAMES = {
    "GTw": "pos-nko",
    "nota++": "nota",   # sinónimo — pode perder (pt43). 'nota ex' NÃO entra (significado distinto: nota exemplar p/ ML futuro).
}


def apply_hm3_tag_aliases(tag: str) -> str:
    """Devolve o nome canónico da tag (ou inalterado se sem alias)."""
    return _HM3_TAG_RENAMES.get(tag, tag)
