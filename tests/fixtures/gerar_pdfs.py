"""Gera PDFs sintéticos com dados FICTÍCIOS para testes automáticos e manuais.

Uso manual:  python -m tests.fixtures.gerar_pdfs [pasta_destino]
(padrão: ./exemplos)
"""

from __future__ import annotations

import sys
from pathlib import Path

import pymupdf

from tests.fixtures import dados as D
from veu.core.detectors.validacao import gerar_dv_cpf

# CPFs válidos, muito usados em exemplos públicos (não pertencem a pessoas reais conhecidas).
CPF_1 = gerar_dv_cpf("529982247")  # 52998224725
CPF_2 = gerar_dv_cpf("111444777")  # 11144477735
CPF_3 = gerar_dv_cpf("123456789")  # 12345678909
CPF_INVALIDO = "123.456.789-00"


def mascarar_cpf(c: str) -> str:
    return f"{c[:3]}.{c[3:6]}.{c[6:9]}-{c[9:]}"


EMAIL_1 = "maria.fictícia@exemplo.com.br".replace("í", "i")
EMAIL_2 = "joao_teste+lgpd@clinica-exemplo.org"
TEL_1 = "(11) 98765-4321"
TEL_2 = "+55 21 3274-1598"
TEL_3 = "61 99876 5432"

FONTE = "helv"
A4 = pymupdf.paper_rect("a4")


def _escrever(page: pymupdf.Page, linhas: list[str], x: float = 56, y: float = 72, tamanho: float = 11) -> float:
    for linha in linhas:
        page.insert_text((x, y), linha, fontname=FONTE, fontsize=tamanho)
        y += tamanho * 1.6
    return y


def pdf_texto_nativo(destino: Path) -> Path:
    """Documento clínico fictício com dados variados + extras para a limpeza."""
    doc = pymupdf.open()
    page = doc.new_page(width=A4.width, height=A4.height)
    _escrever(page, ["CLÍNICA EXEMPLO — FICHA DE ATENDIMENTO (DADOS FICTÍCIOS)"], tamanho=13)
    _escrever(
        page,
        [
            "Paciente: Maria Fictícia da Silva",
            f"CPF: {mascarar_cpf(CPF_1)}",
            f"CPF do responsável (sem máscara): {CPF_2}",
            f"Número de protocolo inválido como CPF: {CPF_INVALIDO}",
            f"E-mail: {EMAIL_1}",
            f"Contato: {TEL_1} ou {TEL_2}",
            f"Celular alternativo: {TEL_3}",
            "Código interno 2024 / lote 12345678 / valor R$ 1.234,56",
            "Observações: retorno em 30 dias.",
        ],
        y=110,
    )
    # Imagem e traço vetorial sob o CPF principal (devem sumir na área tarjada)
    pix = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 40, 10), 0)
    pix.set_rect(pix.irect, (255, 230, 150))
    page.insert_image(pymupdf.Rect(86, 128, 150, 140), pixmap=pix, overlay=False)
    page.draw_line((86, 140), (160, 140), color=(0.2, 0.2, 0.8), width=0.5)

    # Extras que a limpeza deve eliminar
    doc.set_metadata({"author": "Maria Fictícia da Silva", "title": f"Ficha {mascarar_cpf(CPF_1)}", "subject": EMAIL_1})
    page.add_text_annot((400, 100), f"Comentário: conferir CPF {mascarar_cpf(CPF_1)}")
    doc.embfile_add("anexo.txt", f"CPF {mascarar_cpf(CPF_1)}".encode(), filename="anexo.txt")
    doc.set_toc([[1, "Maria Fictícia da Silva", 1]])
    w = pymupdf.Widget()
    w.field_type = pymupdf.PDF_WIDGET_TYPE_TEXT
    w.field_name = "cpf_paciente"
    w.field_value = mascarar_cpf(CPF_1)
    w.rect = pymupdf.Rect(56, 400, 250, 420)
    page.add_widget(w)

    caminho = destino / "texto_nativo.pdf"
    doc.save(caminho)
    doc.close()
    return caminho


def pdf_multicolunas(destino: Path) -> Path:
    doc = pymupdf.open()
    page = doc.new_page(width=A4.width, height=A4.height)
    col1 = pymupdf.Rect(40, 60, 290, 500)
    col2 = pymupdf.Rect(305, 60, 555, 500)
    page.insert_textbox(
        col1,
        "Coluna da esquerda. Relato fictício do atendimento realizado na unidade. "
        f"O paciente informou o CPF {mascarar_cpf(CPF_3)} e pediu retorno por e-mail. "
        "Texto de preenchimento para ocupar espaço na coluna.",
        fontname=FONTE,
        fontsize=10,
    )
    page.insert_textbox(
        col2,
        "Coluna da direita. Dados para contato fornecidos na recepção: "
        f"{EMAIL_2} e telefone {TEL_1}. Fim do relato fictício.",
        fontname=FONTE,
        fontsize=10,
    )
    caminho = destino / "multicolunas.pdf"
    doc.save(caminho)
    doc.close()
    return caminho


def pdf_tabela(destino: Path) -> Path:
    doc = pymupdf.open()
    page = doc.new_page(width=A4.width, height=A4.height)
    cab = ["Nome", "CPF", "Telefone", "E-mail"]
    linhas = [
        ["Ana Exemplo", mascarar_cpf(CPF_1), TEL_1, "ana@exemplo.com"],
        ["Bruno Teste", CPF_2, TEL_3, "bruno@exemplo.com"],
        ["Carla Modelo", mascarar_cpf(CPF_3), TEL_2, "carla@exemplo.com"],
    ]
    xs = [40, 150, 270, 390, 555]
    y = 80
    for linha in [cab, *linhas]:
        for i, valor in enumerate(linha):
            page.insert_text((xs[i] + 4, y + 14), valor, fontname=FONTE, fontsize=9)
        y += 22
    for i in range(len(linhas) + 2):
        page.draw_line((xs[0], 80 + i * 22), (xs[-1], 80 + i * 22), width=0.5)
    for x in xs:
        page.draw_line((x, 80), (x, 80 + (len(linhas) + 1) * 22), width=0.5)
    caminho = destino / "tabela.pdf"
    doc.save(caminho)
    doc.close()
    return caminho


def pdf_quebra_de_linha(destino: Path) -> Path:
    """Dados quebrados entre duas linhas."""
    doc = pymupdf.open()
    page = doc.new_page(width=A4.width, height=A4.height)
    c = mascarar_cpf(CPF_2)
    _escrever(
        page,
        [
            f"Declaro para os devidos fins que o portador do CPF {c[:8]}",
            f"{c[8:]} compareceu à consulta nesta data.",
            "Telefone para contato informado: (11)",
            "98765-4321, falar com a recepção.",
        ],
    )
    caminho = destino / "quebra_de_linha.pdf"
    doc.save(caminho)
    doc.close()
    return caminho


def pdf_rotacionado(destino: Path) -> Path:
    doc = pymupdf.open()
    page = doc.new_page(width=A4.width, height=A4.height)
    _escrever(page, [f"Página rotacionada. CPF {mascarar_cpf(CPF_3)}", f"E-mail {EMAIL_2}"])
    page.set_rotation(90)
    caminho = destino / "rotacionado.pdf"
    doc.save(caminho)
    doc.close()
    return caminho


def pdf_escaneado(destino: Path) -> Path:
    """Página só com imagem (simula digitalização; sem camada de texto)."""
    fonte = pymupdf.open()
    p = fonte.new_page(width=A4.width, height=A4.height)
    _escrever(p, ["Documento digitalizado (fictício)", f"CPF {mascarar_cpf(CPF_1)}"], tamanho=14)
    pix = p.get_pixmap(dpi=150)
    fonte.close()
    doc = pymupdf.open()
    page = doc.new_page(width=A4.width, height=A4.height)
    page.insert_image(page.rect, pixmap=pix)
    caminho = destino / "escaneado.pdf"
    doc.save(caminho)
    doc.close()
    return caminho


def pdf_longo(destino: Path, paginas: int = 50) -> Path:
    doc = pymupdf.open()
    paragrafo = (
        "Este é um parágrafo fictício de preenchimento usado para medir desempenho. "
        "Ele contém números diversos como 2024, 1.234,56 e 45 dias, sem dados pessoais. "
    ) * 3
    for i in range(paginas):
        page = doc.new_page(width=A4.width, height=A4.height)
        texto = (
            f"Página {i + 1}. Paciente fictício com CPF {mascarar_cpf(CPF_1)}, e-mail {EMAIL_1}, "
            f"telefone {TEL_1}.\n\n" + "\n\n".join([paragrafo] * 6)
        )
        page.insert_textbox(pymupdf.Rect(50, 50, 545, 800), texto, fontname=FONTE, fontsize=9)
    caminho = destino / "longo_50_paginas.pdf"
    doc.save(caminho)
    doc.close()
    return caminho


PRONTUARIO = [
    "HOSPITAL SÃO LUCAS DE EXEMPLO — PRONTUÁRIO (DADOS FICTÍCIOS)",
    "",
    "Paciente: Maria Fictícia da Silva",
    f"CPF: {mascarar_cpf(CPF_1)}    RG: 12.345.678-9 SSP/SP",
    "Data de nascimento: 14/03/1985    Sexo: Feminino",
    f"Cartão SUS (CNS): {D.CNS[:3]} {D.CNS[3:7]} {D.CNS[7:11]} {D.CNS[11:]}",
    f"PIS/NIS: {D.mascarar_pis(D.PIS)}    Título de eleitor: {D.TITULO[:4]} {D.TITULO[4:8]} {D.TITULO[8:]}",
    f"CNH nº {D.CNH}    Passaporte: FZ123456",
    "Endereço: Rua das Acácias, 245, apto 32 - Jardim Primavera, São Paulo/SP - CEP 04567-010",
    f"Telefone: {TEL_1}    E-mail: {EMAIL_1}",
    "Responsável: João Pereira Santos (esposo)",
    "Veículo do acompanhante: placa BRA2E19",
    "",
    "HISTÓRIA CLÍNICA",
    "Paciente gestante, 28 semanas, com diagnóstico de diabetes gestacional e hipertensão.",
    "Sorologia para HIV não reagente. CID O24.4 e CID-10 O13.",
    "Em uso de metformina 500 mg e insulina NPH. Nega tabagismo.",
    "Encaminhada pela Dra. Fernanda Lima Costa, CRM-SP 123456.",
    "",
    "DADOS PARA REEMBOLSO",
    f"Empresa: Exemplo Saúde Ltda, CNPJ {D.mascarar_cnpj(D.CNPJ_NUM)}",
    f"Fornecedor: CNPJ {D.mascarar_cnpj(D.CNPJ_ALFA)}",
    "Banco do Brasil, agência 1234-5, conta corrente 98765-4",
    "Chave Pix: 123e4567-e89b-42d3-a456-426614174000",
    "",
    "Assinado digitalmente por Carlos Eduardo Souza em 02/10/2026.",
    "Texto neutro de controle: o laudo do exame foi revisado pela equipe em 2026.",
]


def pdf_prontuario(destino: Path) -> Path:
    """Prontuário fictício com todos os tipos de dado da etapa 2."""
    doc = pymupdf.open()
    page = doc.new_page(width=A4.width, height=A4.height)
    _escrever(page, PRONTUARIO, x=40, y=50, tamanho=9.5)
    caminho = destino / "prontuario_completo.pdf"
    doc.save(caminho)
    doc.close()
    return caminho


def _rasterizar(pdf_texto: pymupdf.Document, dpi: int = 200) -> pymupdf.Pixmap:
    return pdf_texto[0].get_pixmap(dpi=dpi)


def pdf_prontuario_escaneado(destino: Path) -> Path:
    """O prontuário completo como imagem (simula um documento digitalizado)."""
    fonte = pymupdf.open()
    p = fonte.new_page(width=A4.width, height=A4.height)
    _escrever(p, PRONTUARIO, x=40, y=50, tamanho=9.5)
    pix = _rasterizar(fonte)
    fonte.close()
    doc = pymupdf.open()
    page = doc.new_page(width=A4.width, height=A4.height)
    page.insert_image(page.rect, pixmap=pix)
    caminho = destino / "prontuario_escaneado.pdf"
    doc.save(caminho)
    doc.close()
    return caminho


def pdf_misto(destino: Path) -> Path:
    """Texto nativo + documento digitalizado colado como imagem na mesma página."""
    fonte = pymupdf.open()
    p = fonte.new_page(width=400, height=200)
    _escrever(p, ["Declaração anexa (imagem)", f"CPF {mascarar_cpf(CPF_3)}", f"E-mail {EMAIL_2}"], x=20, y=40, tamanho=14)
    pix = p.get_pixmap(dpi=200)
    fonte.close()
    doc = pymupdf.open()
    page = doc.new_page(width=A4.width, height=A4.height)
    _escrever(page, ["Relatório com anexo digitalizado (fictício).", f"Contato: {TEL_1}"], x=40, y=60)
    page.insert_image(pymupdf.Rect(40, 120, 555, 380), pixmap=pix)
    caminho = destino / "misto.pdf"
    doc.save(caminho)
    doc.close()
    return caminho


GERADORES = [pdf_prontuario, pdf_texto_nativo, pdf_multicolunas, pdf_tabela, pdf_quebra_de_linha, pdf_rotacionado, pdf_escaneado, pdf_prontuario_escaneado, pdf_misto, pdf_longo]


def gerar_todos(destino: Path) -> dict[str, Path]:
    destino.mkdir(parents=True, exist_ok=True)
    return {g.__name__.removeprefix("pdf_"): g(destino) for g in GERADORES}


if __name__ == "__main__":
    pasta = Path(sys.argv[1] if len(sys.argv) > 1 else "exemplos")
    for nome, caminho in gerar_todos(pasta).items():
        print(f"{nome:20s} {caminho}")
