# Régua da ELIMINAÇÃO (irmã da best_completion — lei do Rui, 22 Jul).
# Numa mesa, se todos os nomes casam entre HH e captura menos UM de cada lado,
# o par sobrante é a mesma pessoa — fica o nome MAIS COMPLETO. 3 guardas não
# negociáveis: Hero-fora-primeiro / contagens reconciliadas / um-e-um.
from app.services.name_merge import (
    clean_capture_nicks,
    elimination_completion,
)


def _vj(nicks, hero_idx=None):
    return {"seats": [{"nick": n, "is_hero": (i == hero_idx)}
                      for i, n in enumerate(nicks)]}


NAMED = {
    "Hero": "Lauro Dermio",
    "aaaa1111": "K Nikolaichuk",
    "bbbb2222": "Queimouo12mola",
    "cccc3333": "Footlose r..",       # coto MAL soletrado pelo OCR da Gold
}
CAP = ["Lauro Dermio", "K Nikolaichuk", "Queimouo12mola", "Footloose reg"]


def test_caminho_feliz_coto_divergente_completa():
    # o prefixo nunca casaria (Footlose vs Footloose) — a eliminação prova o par
    p = elimination_completion(NAMED, 4, _vj(CAP, hero_idx=0))
    assert p == {"hash": "cccc3333", "from": "Footlose r..", "to": "Footloose reg"}


def test_g1_hero_por_ler_recusa_tudo():
    # cautela do Rui: a Vision falha muitas vezes UM jogador — e muitas vezes é o
    # Hero. Hero ausente da captura → NÃO elimina nada (senão casava o Hero com
    # o vilão sobrante por engano).
    cap = ["K Nikolaichuk", "Queimouo12mola", "Footloose reg", "Outro Qualquer"]
    assert elimination_completion(NAMED, 4, _vj(cap)) is None


def test_g1_hero_pela_flag_is_hero_mesmo_com_grafia_divergente():
    # a flag is_hero identifica o Hero mesmo que a Vision tenha lido o nick torto
    cap = ["Lauro Dermlo", "K Nikolaichuk", "Queimouo12mola", "Footloose reg"]
    p = elimination_completion(NAMED, 4, _vj(cap, hero_idx=0))
    assert p == {"hash": "cccc3333", "from": "Footlose r..", "to": "Footloose reg"}


def test_g2_captura_leu_menos_nao_toca():
    cap = ["Lauro Dermio", "K Nikolaichuk", "Footloose reg"]
    assert elimination_completion(NAMED, 4, _vj(cap, hero_idx=0)) is None


def test_g2_captura_leu_a_mais_nao_toca():
    # jogador sentado sem cartas na HH (o caso Domenico) → contagens não batem
    cap = CAP + ["Domenico DiVito"]
    assert elimination_completion(NAMED, 4, _vj(cap, hero_idx=0)) is None


def test_g2_lixo_de_ui_nao_conta_como_nome():
    assert clean_capture_nicks(_vj(["Post Blind(s)", "Lauro Dermio", "post", ""])) == \
        ["Lauro Dermio"]
    # lixo no lugar do 4º → só 3 nomes legíveis → contagem não bate → recusa
    cap = ["Lauro Dermio", "K Nikolaichuk", "Queimouo12mola", "Post Blind(s)"]
    assert elimination_completion(NAMED, 4, _vj(cap, hero_idx=0)) is None


def test_g3_dois_e_dois_nao_toca():
    named = dict(NAMED)
    named["dddd4444"] = "Stoner Runn.."
    cap = ["Lauro Dermio", "K Nikolaichuk", "Footloose reg", "Outro Nome", "Mais Um"]
    assert elimination_completion(named, 5, _vj(cap, hero_idx=0)) is None


def test_vilao_sem_nome_recusa_sozinho():
    # vilão não desanonimizado: o sobrante da captura passa a 2 → G3 recusa (1-e-2)
    named = {k: v for k, v in NAMED.items() if k != "bbbb2222"}
    p = elimination_completion(named, 4, _vj(CAP, hero_idx=0))
    assert p is None


def test_sobrante_da_captura_truncado_nao_ganha():
    # a captura também trunca (caso Joel Nystedt) → não há nome completo a adotar
    cap = ["Lauro Dermio", "K Nikolaichuk", "Queimouo12mola", "Footloose re.."]
    assert elimination_completion(NAMED, 4, _vj(cap, hero_idx=0)) is None


def test_sobrante_da_hh_nao_truncado_fora_do_ambito():
    # só completa TRUNCADOS — um nome completo divergente não é reescrito
    named = dict(NAMED)
    named["cccc3333"] = "Footlose reg"        # completo (sem ..), grafia divergente
    assert elimination_completion(named, 4, _vj(CAP, hero_idx=0)) is None


def test_nomes_iguais_casam_e_nao_sobram():
    # mesa toda a casar (com uma truncatura-prefixo limpa) → 0-e-0 → nada a fazer
    named = {"Hero": "Lauro Dermio", "a1": "K Nikolaich..", "b2": "Queimouo12mola"}
    cap = ["Lauro Dermio", "K Nikolaichuk", "Queimouo12mola"]
    assert elimination_completion(named, 3, _vj(cap, hero_idx=0)) is None


def test_sem_hero_na_hh_recusa():
    named = {k: v for k, v in NAMED.items() if k != "Hero"}
    assert elimination_completion(named, 3, _vj(CAP[1:], hero_idx=None)) is None
