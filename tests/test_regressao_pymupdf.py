"""Regressão: a tarja não pode mover o texto que sobra na linha.

O PyMuPDF 2.0/2.1 (MuPDF 1.28.5/1.28.6) desloca para a esquerda os caracteres
que vêm depois da área tarjada, pela largura do que foi removido. Assim, texto
que não deveria ser tarjado acaba embaixo da tarja e o layout muda. Este teste
falha se uma atualização trouxer o problema de volta.
"""

import pymupdf
import pytest


def _x_de(page, caractere):
    for b in page.get_text("rawdict")["blocks"]:
        for linha in b.get("lines", []):
            for span in linha["spans"]:
                for c in span["chars"]:
                    if c["c"] == caractere:
                        return c["bbox"][0]
    return None


@pytest.mark.parametrize("fonte", [{}, {"fontname": "arial", "fontfile": r"C:\Windows\Fonts\arial.ttf"}])
def test_texto_apos_a_tarja_nao_se_move(fonte):
    if fonte.get("fontfile") and not __import__("os").path.exists(fonte["fontfile"]):
        pytest.skip("fonte do Windows indisponível")
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((50, 72), "Funcionário: MAT-123456 / matrícula", fontsize=11, **fonte)
    antes = _x_de(page, "m")
    x_mat = _x_de(page, "M")
    x_barra = _x_de(page, "/")
    page.add_redact_annot(pymupdf.Rect(x_mat, 60, x_barra - 3.5, 76), fill=(0, 0, 0))
    page.apply_redactions()
    assert _x_de(page, "M") is None
    assert _x_de(page, "m") == pytest.approx(antes, abs=0.5), (
        f"PyMuPDF {pymupdf.VersionBind}: texto deslocado após a tarja"
    )
