import pytest

from veu.core.detectors import DetectorCPF
from veu.core.detectors.validacao import cpf_valido, gerar_dv_cpf


def trechos(texto):
    return [texto[a.inicio:a.fim] for a in DetectorCPF().detectar(texto)]


@pytest.mark.parametrize(
    "texto, esperado",
    [
        ("CPF: 529.982.247-25", ["529.982.247-25"]),
        ("cpf 52998224725 ok", ["52998224725"]),
        ("CPF 111.444.\n777-35 quebrado", ["111.444.\n777-35"]),
        ("CPF 529 982 247 25", ["529 982 247 25"]),
        ("vários: 529.982.247-25, 111.444.777-35.", ["529.982.247-25", "111.444.777-35"]),
        ("CPF 529.982 .247-25 (OCR)", ["529.982 .247-25"]),
    ],
)
def test_detecta_cpf_valido(texto, esperado):
    assert trechos(texto) == esperado


@pytest.mark.parametrize(
    "texto",
    [
        "CPF: 123.456.789-00",  # dígito verificador errado
        "111.111.111-11",  # sequência repetida
        "000.000.000-00",
        "12345678901234",  # número maior (ex.: CNPJ/código)
        "Valor 529.982.247,25",  # vírgula decimal, não é CPF
        "529 982 247 25",  # separadores ambíguos sem a palavra CPF
        "processo 0529982247251",
    ],
)
def test_nao_detecta_invalidos(texto):
    assert trechos(texto) == []


def test_validacao_dv():
    assert cpf_valido("52998224725")
    assert not cpf_valido("52998224724")
    assert gerar_dv_cpf("529982247") == "52998224725"
