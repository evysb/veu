import os
import time

from tests.fixtures import gerar_pdfs as g
from veu.core.pipeline import analisar


def tipos_trechos(analise):
    return {(d.tipo, "".join(c for c in d.trecho if c.isalnum() or c in "@._+-")) for d in analise.deteccoes}


def test_texto_nativo(pdfs):
    a = analisar(str(pdfs["texto_nativo"]))
    tt = tipos_trechos(a)
    assert ("CPF", g.mascarar_cpf(g.CPF_1)) in tt
    assert ("CPF", g.CPF_2) in tt
    assert ("EMAIL", g.EMAIL_1) in tt
    assert sum(1 for d in a.deteccoes if d.tipo == "TELEFONE") == 3
    assert not any("789-00" in d.trecho for d in a.deteccoes), "CPF inválido não pode ser detectado"
    for d in a.deteccoes:
        assert d.rects and all(r[2] > r[0] and r[3] > r[1] for r in d.rects)


def test_multicolunas_nao_mistura_colunas(pdfs):
    a = analisar(str(pdfs["multicolunas"]))
    assert {d.tipo for d in a.deteccoes} == {"CPF", "EMAIL", "TELEFONE"}
    email = next(d for d in a.deteccoes if d.tipo == "EMAIL")
    assert email.rects[0][0] > 300  # coluna da direita


def test_tabela(pdfs):
    a = analisar(str(pdfs["tabela"]))
    assert sum(1 for d in a.deteccoes if d.tipo == "CPF") == 3
    assert sum(1 for d in a.deteccoes if d.tipo == "EMAIL") == 3
    assert sum(1 for d in a.deteccoes if d.tipo == "TELEFONE") == 3


def test_dados_quebrados_entre_linhas_geram_duas_caixas(pdfs):
    a = analisar(str(pdfs["quebra_de_linha"]))
    cpf = next(d for d in a.deteccoes if d.tipo == "CPF")
    tel = next(d for d in a.deteccoes if d.tipo == "TELEFONE")
    assert len(cpf.rects) == 2 and len(tel.rects) == 2


def test_pagina_escaneada_sem_ocr_gera_aviso(pdfs):
    from veu.core.policy import Politica

    p = Politica()
    p.ocr.ativo = False
    a = analisar(str(pdfs["escaneado"]), politica=p)
    assert a.deteccoes == []
    assert a.avisos and "sem nenhum texto" in a.avisos[0]


def test_desempenho_50_paginas(pdfs):
    # Máquinas compartilhadas de CI são mais lentas: VEU_FATOR_TEMPO multiplica o limite.
    limite = 5 * float(os.environ.get("VEU_FATOR_TEMPO", "1"))
    inicio = time.perf_counter()
    a = analisar(str(pdfs["longo"]))
    assert time.perf_counter() - inicio < limite
    assert a.num_paginas == 50
    assert sum(1 for d in a.deteccoes if d.tipo in ("CPF", "EMAIL", "TELEFONE")) == 150
