"""#CROSSING-SIBLING-BY-ROWID-NOT-CONTENT — a 'fonte irmã' do painel Cruzamento tem de ser
uma IMAGEM DIFERENTE (file_hash), não outra linha/leitura da mesma imagem. Provado: 10 de 24
propostas eram a mesma captura contada 2x (via id de linha + fallback do context_table_ss_id).
Estes testes cravam o critério novo em `_distinct_failed_sibling` (puro, sem BD)."""
from app.routers.gg_health import _distinct_failed_sibling


def _cap(fh, crown, cid=1, kind="ss"):
    return {"kind": kind, "id": cid, "file_hash": fh, "crowns": {"joe": crown}}


def test_mesmo_file_hash_NAO_e_irma():
    """read e failed com o MESMO file_hash → NÃO há irmã (mesma imagem, não é prova)."""
    read = _cap("A", 20.0, cid=1)
    caps = [read, _cap("A", None, cid=2)]        # outra LINHA, mesma imagem (hash A)
    assert _distinct_failed_sibling(caps, read, "joe") is None


def test_propria_captura_reusada_NAO_e_irma():
    """Só existe a captura do read (o caso GG-6183037269) → sem irmã (mata o fallback)."""
    read = _cap("A", 20.0, cid=1)
    assert _distinct_failed_sibling([read], read, "joe") is None


def test_file_hash_distinto_que_leu_vazio_E_irma():
    """read e failed com file_hash DISTINTO (o failed leu vazio) → é irmã válida → é proposta."""
    read = _cap("A", 20.0, cid=1)
    other = _cap("B", None, cid=2)               # imagem diferente, leu vazio
    assert _distinct_failed_sibling([read, other], read, "joe") is other


def test_imagem_distinta_mas_leu_valor_NAO_e_failed():
    """Imagem diferente mas que TAMBÉM leu a coroa não é 'a que falhou' → não conta."""
    read = _cap("A", 20.0, cid=1)
    caps = [read, _cap("B", 18.0, cid=2)]
    assert _distinct_failed_sibling(caps, read, "joe") is None


def test_read_sem_hash_nao_ha_irma():
    """Sem file_hash no read não se prova distinção → conservador: sem irmã."""
    read = _cap(None, 20.0, cid=1)
    caps = [read, _cap("B", None, cid=2)]
    assert _distinct_failed_sibling(caps, read, "joe") is None
