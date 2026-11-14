"""Extração de texto com coordenadas: camada nativa e OCR local quando necessário."""

from veu.core.extraction.documento import SenhaIncorreta, SenhaNecessaria, abrir_documento
from veu.core.extraction.ocr import ModoOCR, pasta_tessdata
from veu.core.extraction.texto_nativo import OpcoesExtracao, ResultadoExtracao, extrair_documento, extrair_pagina

__all__ = [
    "ModoOCR",
    "OpcoesExtracao",
    "ResultadoExtracao",
    "SenhaIncorreta",
    "SenhaNecessaria",
    "abrir_documento",
    "extrair_documento",
    "extrair_pagina",
    "pasta_tessdata",
]
