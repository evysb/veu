"""Abertura segura de PDFs."""

from __future__ import annotations

import pymupdf


class SenhaNecessaria(Exception):
    """O PDF está protegido e nenhuma senha foi informada."""


class SenhaIncorreta(Exception):
    """A senha informada não abre o PDF."""


def abrir_documento(caminho: str, senha: str | None = None) -> pymupdf.Document:
    """Abre o PDF, desbloqueia com a senha e torna visíveis todas as camadas.

    Camadas opcionais (OCG) ocultas também podem conter dados pessoais; ao
    ligá-las, elas passam pela detecção e pela tarja como o resto da página.
    """
    doc = pymupdf.open(caminho)
    if not doc.is_pdf:
        doc.close()
        raise ValueError("O arquivo não é um PDF.")
    if doc.needs_pass:
        if not senha:
            doc.close()
            raise SenhaNecessaria()
        if not doc.authenticate(senha):
            doc.close()
            raise SenhaIncorreta()
    _ligar_todas_as_camadas(doc)
    return doc


def _ligar_todas_as_camadas(doc: pymupdf.Document) -> None:
    try:
        ocgs = doc.get_ocgs()
    except Exception:
        return
    if not ocgs:
        return
    try:
        doc.set_layer(-1, basestate="ON", on=list(ocgs.keys()), off=[])
    except Exception:
        pass
