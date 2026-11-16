"""OCR de páginas escaneadas e tarja sobre a imagem."""

import re

import pymupdf
import pytest

from tests.fixtures import gerar_pdfs as g
from veu.core.extraction import ModoOCR, extrair_pagina, pasta_tessdata
from veu.core.extraction.ocr import _texto_ilegivel, modo_ocr, textpage_ocr
from veu.core.pipeline import analisar
from veu.core.redaction import anonimizar
from veu.core.revisao import Revisao

precisa_ocr = pytest.mark.skipif(
    pasta_tessdata() is None, reason="por.traineddata ausente: rode empacotamento/baixar_modelos.py"
)


def test_texto_ilegivel():
    assert _texto_ilegivel("�" * 30 + "abc")
    assert _texto_ilegivel("".join(chr(0xE000 + i) for i in range(40)))
    assert not _texto_ilegivel("Paciente: Maria Fictícia da Silva, CPF 529.982.247-25")
    assert not _texto_ilegivel("��")  # pouco texto: não decide


def test_modo_ocr_por_tipo_de_pagina(pdfs):
    casos = {"texto_nativo": ModoOCR.NENHUM, "escaneado": ModoOCR.PAGINA_INTEIRA, "misto": ModoOCR.SO_IMAGENS}
    for nome, esperado in casos.items():
        page = pymupdf.open(pdfs[nome])[0]
        assert modo_ocr(page, extrair_pagina(page)) == esperado, nome


@precisa_ocr
def test_ocr_encontra_dados_em_pagina_escaneada(pdfs):
    a = analisar(str(pdfs["escaneado"]))
    assert a.paginas[0].origem == "ocr"
    # O OCR às vezes insere espaços ("529.982 .247-25"); compara-se pelos dígitos.
    assert any(d.tipo == "CPF" and re.sub(r"\D", "", d.trecho) == g.CPF_1 for d in a.deteccoes)
    assert any("OCR aplicado" in av for av in a.avisos)


@precisa_ocr
def test_pagina_mista_ocr_so_nas_imagens(pdfs):
    a = analisar(str(pdfs["misto"]))
    tipos = {(d.tipo, d.trecho) for d in a.deteccoes}
    assert ("TELEFONE", g.TEL_1) in tipos  # do texto nativo
    assert ("CPF", g.mascarar_cpf(g.CPF_3)) in tipos  # de dentro da imagem


@precisa_ocr
def test_prontuario_escaneado_ponta_a_ponta(pdfs, tmp_path):
    a = analisar(str(pdfs["prontuario_escaneado"]))
    tipos = {d.tipo for d in a.deteccoes}
    assert {"NOME", "CPF", "RG", "CNS", "ENDERECO", "TELEFONE", "CNPJ", "CRM"} <= tipos
    assert "SAUDE" not in tipos  # desligado na política padrão
    Revisao(a).aceitar_pendentes()
    saida = tmp_path / "escaneado_anonimizado.pdf"
    r = anonimizar(a, str(saida))
    v = r.verificacao
    assert v.ok, v.vazamentos
    assert not v.avisos

    # Prova independente: OCR do resultado não encontra os valores tarjados.
    page = pymupdf.open(saida)[0]
    texto = page.get_text(textpage=textpage_ocr(page, pasta_tessdata(), ModoOCR.PAGINA_INTEIRA))
    for valor in ["529.982.247-25", "Maria Fictícia", "Acácias", "11.222.333", "98765-4321"]:
        assert valor not in texto, valor
    assert "metformina" in texto  # dado de saúde fica (desligado por padrão)
    assert "HISTÓRIA CLÍNICA" in texto  # o resto da página continua legível


def test_sem_arquivo_de_idioma_avisa(pdfs, monkeypatch):
    import veu.core.extraction.texto_nativo as tn

    monkeypatch.setattr(tn, "pasta_tessdata", lambda: None)
    a = analisar(str(pdfs["escaneado"]))
    assert a.deteccoes == []
    assert any("OCR não está disponível" in av for av in a.avisos)
