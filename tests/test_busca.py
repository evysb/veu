from veu.core.busca import buscar, normalizar_preservando_posicoes
from veu.core.models import TextoPagina


def pagina(texto):
    n = len(texto)
    return TextoPagina(0, 100, 100, texto, [(i, 0, i + 1, 1) for i in range(n)], [0] * n)


def test_normalizacao_preserva_tamanho():
    s = "Ação ÉRICA çÇ"
    assert len(normalizar_preservando_posicoes(s)) == len(s)
    assert normalizar_preservando_posicoes(s) == "acao erica cc"


def test_busca_ignora_acento_e_caixa():
    p = pagina("Projeto ÁGUIA e projeto aguia; aguiar não.")
    assert len(buscar(p, "Águia")) == 2


def test_busca_palavra_inteira():
    p = pagina("Ana e Banana")
    assert buscar(p, "ana") == [(0, 3)]
    assert buscar(p, "ana", palavra_inteira=False) == [(0, 3), (7, 10)]


def test_busca_atravessa_quebra_de_linha():
    p = pagina("cliente Maria\nSilva ok")
    assert buscar(p, "Maria Silva") == [(8, 19)]
