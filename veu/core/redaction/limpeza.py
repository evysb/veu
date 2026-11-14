"""Remoção de tudo que pode carregar dados fora do conteúdo visível da página."""

from __future__ import annotations

import pymupdf


def limpar_documento(doc: pymupdf.Document) -> list[str]:
    """Remove metadados, XMP, anotações, formulários, anexos, bookmarks,
    links, JavaScript, miniaturas e texto oculto. Devolve o que foi feito."""
    feito: list[str] = []

    # Anotações e campos de formulário (comentários, notas, assinaturas visuais…)
    n_annots = n_widgets = 0
    for page in doc:
        for w in list(page.widgets() or []):
            page.delete_widget(w)
            n_widgets += 1
        annot = page.first_annot
        while annot is not None:
            proximo = annot.next
            page.delete_annot(annot)
            n_annots += 1
            annot = proximo
    if n_annots:
        feito.append(f"{n_annots} anotação(ões)/comentário(s) removido(s)")
    if n_widgets:
        feito.append(f"{n_widgets} campo(s) de formulário removido(s)")

    if doc.get_toc(simple=True):
        doc.set_toc([])
        feito.append("marcadores (bookmarks) removidos")

    n_anexos = doc.embfile_count()
    for nome in list(doc.embfile_names()):
        doc.embfile_del(nome)
    if n_anexos:
        feito.append(f"{n_anexos} anexo(s) embutido(s) removido(s)")

    # scrub cobre: metadados, XMP, JavaScript, links, miniaturas, anexos de
    # anotação, respostas de formulário e texto invisível (modo de render 3).
    doc.scrub(
        attached_files=True,
        clean_pages=True,
        embedded_files=True,
        hidden_text=True,
        javascript=True,
        metadata=True,
        redactions=True,
        redact_images=0,
        remove_links=True,
        reset_fields=True,
        reset_responses=True,
        thumbnails=True,
        xml_metadata=True,
    )
    doc.set_metadata({})
    try:
        doc.del_xml_metadata()
    except Exception:
        pass
    _remover_camadas(doc)
    feito.append("metadados, XMP, links, JavaScript e texto oculto removidos")
    return feito


def _remover_camadas(doc: pymupdf.Document) -> None:
    """Retira /OCProperties do catálogo: o conteúdo das camadas já foi tornado
    visível na abertura, e sem a definição de camadas nada volta a ficar oculto."""
    try:
        cat = doc.pdf_catalog()
        if doc.xref_get_key(cat, "OCProperties")[0] != "null":
            doc.xref_set_key(cat, "OCProperties", "null")
    except Exception:
        pass
