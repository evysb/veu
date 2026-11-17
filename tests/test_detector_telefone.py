import pytest

from veu.core.detectors import DetectorTelefone


def trechos(texto):
    return [texto[a.inicio:a.fim] for a in DetectorTelefone().detectar(texto)]


@pytest.mark.parametrize(
    "texto, esperado",
    [
        ("Tel: (11) 98765-4321", ["(11) 98765-4321"]),
        ("+55 21 3456-7890", ["+55 21 3456-7890"]),
        ("+5511987654321", ["+5511987654321"]),
        ("ligar 11987654321", ["11987654321"]),
        ("cel 61 99876 5432", ["61 99876 5432"]),
        ("(011) 3456-7890", ["(011) 3456-7890"]),
        ("fone: 3456-7890", ["3456-7890"]),
        ("whatsapp 98765-4321", ["98765-4321"]),
        ("(11)\n98765-4321 quebrado", ["(11)\n98765-4321"]),
    ],
)
def test_detecta(texto, esperado):
    assert trechos(texto) == esperado


@pytest.mark.parametrize(
    "texto",
    [
        "20 98765-4321",  # DDD inexistente, sem parênteses
        "(20) 987654321",  # DDD inexistente, sem hífen
        "valor 1.234,56",
        "lote 12345678",  # 8 dígitos soltos
        "ano 2024",
        "CEP 01310-100",
        "1234-5678",  # começa com 1: não é fixo nem celular
        "data 12/03/2024",
    ],
)
def test_nao_detecta(texto):
    assert trechos(texto) == []


def test_ddd_inexistente_no_formato_completo():
    achados = DetectorTelefone().detectar("Contato: (00) 90000-1234")
    assert [a.confianca for a in achados] == [0.75]
