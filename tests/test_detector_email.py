import pytest

from veu.core.detectors import DetectorEmail


def trechos(texto):
    return [texto[a.inicio:a.fim] for a in DetectorEmail().detectar(texto)]


@pytest.mark.parametrize(
    "texto, esperado",
    [
        ("contato: maria.silva@exemplo.com.br.", ["maria.silva@exemplo.com.br"]),
        ("<joao_teste+lgpd@clinica-exemplo.org>", ["joao_teste+lgpd@clinica-exemplo.org"]),
        ("a@b.co e x.y@z.gov.br", ["a@b.co", "x.y@z.gov.br"]),
    ],
)
def test_detecta(texto, esperado):
    assert trechos(texto) == esperado


@pytest.mark.parametrize(
    "texto",
    ["usuario@", "@exemplo.com", "nome@dominio", "a..b@exemplo.com", "siga @perfil.oficial no app", "texto sem email"],
)
def test_nao_detecta(texto):
    assert trechos(texto) == []
