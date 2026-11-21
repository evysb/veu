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


# OCR: o "@" às vezes vira "Q", "©", "&"…
@pytest.mark.parametrize(
    "texto, esperado",
    [
        ("E-mail: maria.ficticiaQexemplo.com.br", ["maria.ficticiaQexemplo.com.br"]),
        ("maria.ficticiaQexemplo.com.br", ["maria.ficticiaQexemplo.com.br"]),
        ("contato joao©clinica.org.br.", ["joao©clinica.org.br"]),
        ("Email: Joao.Silva Q Exemplo.COM", ["Joao.Silva Q Exemplo.COM"]),
        ("E-mail: ana(a)exemplo.net", ["ana(a)exemplo.net"]),
    ],
)
def test_detecta_arroba_mal_lida_pelo_ocr(texto, esperado):
    assert trechos(texto) == esperado


@pytest.mark.parametrize(
    "texto",
    [
        "cardiologia & clinica.com.br",  # espaço em volta e sem rótulo
        "Visite AT&T.com para detalhes",  # maiúsculas e sem rótulo
        "SQL.Server e QA.team",
        "PQRS.Brasil",
        "E-mail: (em branco)",
    ],
)
def test_nao_confunde_texto_comum_com_email_do_ocr(texto):
    assert trechos(texto) == []
