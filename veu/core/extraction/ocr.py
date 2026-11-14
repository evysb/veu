"""OCR local com o Tesseract embutido no MuPDF.

O PyMuPDF traz o motor do Tesseract 5 compilado junto; só precisamos do arquivo
de idioma ``por.traineddata``. O resultado já vem nas coordenadas do PDF,
caractere a caractere, no mesmo formato da extração nativa.
"""

from __future__ import annotations

import os
import sys
from enum import Enum
from pathlib import Path

import pymupdf

from veu.core.models import TextoPagina

IDIOMA = "por"


class ModoOCR(str, Enum):
    NENHUM = "nenhum"
    PAGINA_INTEIRA = "pagina_inteira"  # sem texto, ou texto ilegível
    SO_IMAGENS = "so_imagens"  # texto nativo + imagens grandes (ex.: documento digitalizado anexado)


def pasta_tessdata() -> Path | None:
    """Pasta com ``por.traineddata`` (nunca a do TESSDATA_PREFIX do sistema,
    que pode apontar para uma instalação antiga e incompatível do Tesseract)."""
    candidatos = []
    if os.environ.get("VEU_TESSDATA"):
        candidatos.append(Path(os.environ["VEU_TESSDATA"]))
    base_exe = getattr(sys, "_MEIPASS", None)
    if base_exe:
        candidatos.append(Path(base_exe) / "veu" / "modelos" / "tessdata")
    candidatos.append(Path(__file__).resolve().parents[2] / "modelos" / "tessdata")
    for c in candidatos:
        if (c / f"{IDIOMA}.traineddata").is_file():
            return c
    return None


def _texto_ilegivel(texto: str) -> bool:
    """Fonte sem mapeamento Unicode: o texto extraído vira lixo (U+FFFD, área privada…)."""
    visiveis = [c for c in texto if not c.isspace()]
    if len(visiveis) < 20:
        return False
    ruins = sum(1 for c in visiveis if c == "�" or 0xE000 <= ord(c) <= 0xF8FF or ord(c) < 32)
    return ruins / len(visiveis) > 0.3


def _fracao_coberta_por_imagens(page: pymupdf.Page) -> float:
    area_pagina = abs(page.rect) or 1.0
    total = 0.0
    try:
        for info in page.get_image_info():
            r = pymupdf.Rect(info["bbox"]) & page.rect
            if not r.is_empty:
                total += abs(r)
    except Exception:
        return 0.0
    return min(total / area_pagina, 1.0)


def modo_ocr(page: pymupdf.Page, nativo: TextoPagina) -> ModoOCR:
    tem_imagem = _fracao_coberta_por_imagens(page)
    if nativo.sem_texto:
        return ModoOCR.PAGINA_INTEIRA if tem_imagem > 0.05 or page.get_drawings() else ModoOCR.NENHUM
    if _texto_ilegivel(nativo.texto):
        return ModoOCR.PAGINA_INTEIRA
    if tem_imagem >= 0.15:
        return ModoOCR.SO_IMAGENS
    return ModoOCR.NENHUM


def textpage_ocr(page: pymupdf.Page, tessdata: Path, modo: ModoOCR, dpi: int = 300):
    return page.get_textpage_ocr(
        language=IDIOMA,
        dpi=dpi,
        full=modo == ModoOCR.PAGINA_INTEIRA,
        tessdata=str(tessdata),
    )


def pagina_so_com_imagens(page: pymupdf.Page) -> tuple[pymupdf.Document, pymupdf.Page]:
    """Cópia da página contendo APENAS as imagens (sem texto nem desenhos).

    Usada na verificação: o OCR dela mostra o que restou nos pixels das imagens,
    sem a interferência das tarjas pretas desenhadas por cima.
    """
    doc = page.parent
    copia = pymupdf.open()
    caixa = page.cropbox
    nova = copia.new_page(width=caixa.width, height=caixa.height)
    for info in page.get_image_info(xrefs=True):
        xref = info.get("xref")
        if not xref:
            continue
        try:
            dados = doc.extract_image(xref)["image"]
            nova.insert_image(pymupdf.Rect(info["bbox"]), stream=dados, keep_proportion=False)
        except Exception:
            continue
    return copia, nova
