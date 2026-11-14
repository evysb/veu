"""Extração de texto caractere a caractere, com coordenadas (nativo ou OCR)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

import pymupdf

from veu.core.extraction.ocr import ModoOCR, modo_ocr, pagina_so_com_imagens, pasta_tessdata, textpage_ocr
from veu.core.models import Rect, TextoPagina

# Sem TEXT_PRESERVE_LIGATURES: ligaduras como "ﬁ" viram "f" + "i", o que
# permite que buscas e detectores encontrem o texto normalmente.
_FLAGS = pymupdf.TEXT_PRESERVE_WHITESPACE | pymupdf.TEXT_MEDIABOX_CLIP


@dataclass
class OpcoesExtracao:
    ocr: bool = True
    dpi: int = 300
    #: Páginas que devem passar por OCR de página inteira, mesmo com texto
    #: (usado na verificação do PDF gerado).
    forcar_ocr: set[int] = field(default_factory=set)
    #: No OCR forçado, ler só as imagens da página (ignorando tarjas e texto).
    ocr_so_imagens: bool = False


@dataclass
class ResultadoExtracao:
    paginas: list[TextoPagina]
    paginas_ocr: list[int] = field(default_factory=list)
    paginas_sem_ocr: list[int] = field(default_factory=list)  # precisavam, mas o OCR não estava disponível


def extrair_pagina(page: pymupdf.Page, textpage=None, origem: str = "nativo") -> TextoPagina:
    raw = page.get_text("rawdict", flags=_FLAGS, textpage=textpage)
    texto: list[str] = []
    bboxes: list[Rect | None] = []
    linhas: list[int] = []
    id_linha = 0

    for bloco in raw.get("blocks", []):
        if bloco.get("type") != 0:
            continue
        for linha in bloco.get("lines", []):
            houve_char = False
            for span in linha.get("spans", []):
                for ch in span.get("chars", []):
                    c = ch["c"]
                    if not c:
                        continue
                    texto.append(c)
                    bboxes.append(tuple(ch["bbox"]))  # type: ignore[arg-type]
                    linhas.append(id_linha)
                    houve_char = True
            if houve_char:
                texto.append("\n")
                bboxes.append(None)
                linhas.append(-1)
                id_linha += 1

    rect = page.cropbox  # dimensões sem rotação (mesmo espaço do get_text)
    return TextoPagina(
        numero=page.number,
        largura=rect.width,
        altura=rect.height,
        texto="".join(texto),
        bboxes=bboxes,
        linhas=linhas,
        origem=origem,
    )


def extrair_documento(
    doc: pymupdf.Document,
    progresso: Callable[[int, int, str], None] | None = None,
    cancelado: Callable[[], bool] | None = None,
    opcoes: OpcoesExtracao | None = None,
) -> ResultadoExtracao:
    opcoes = opcoes or OpcoesExtracao()
    tessdata = pasta_tessdata() if (opcoes.ocr or opcoes.forcar_ocr) else None
    resultado = ResultadoExtracao(paginas=[])
    total = doc.page_count
    for i in range(total):
        if cancelado and cancelado():
            raise InterruptedError("Operação cancelada.")
        page = doc[i]
        pagina = extrair_pagina(page)
        modo = ModoOCR.PAGINA_INTEIRA if i in opcoes.forcar_ocr else (modo_ocr(page, pagina) if opcoes.ocr else ModoOCR.NENHUM)
        if modo != ModoOCR.NENHUM:
            if tessdata is None:
                resultado.paginas_sem_ocr.append(i)
            else:
                if progresso:
                    progresso(i, total, f"Reconhecendo texto (OCR) na página {i + 1} de {total}…")
                if i in opcoes.forcar_ocr and opcoes.ocr_so_imagens:
                    copia, so_imagens = pagina_so_com_imagens(page)
                    tp = textpage_ocr(so_imagens, tessdata, ModoOCR.PAGINA_INTEIRA, opcoes.dpi)
                    pagina = extrair_pagina(so_imagens, textpage=tp, origem="ocr")
                    pagina.numero = i
                    copia.close()
                else:
                    tp = textpage_ocr(page, tessdata, modo, opcoes.dpi)
                    pagina = extrair_pagina(page, textpage=tp, origem="ocr")
                resultado.paginas_ocr.append(i)
        resultado.paginas.append(pagina)
        if progresso:
            progresso(i + 1, total, f"Lendo página {i + 1} de {total}…")
    return resultado
