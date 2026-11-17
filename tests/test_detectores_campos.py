"""Campos de formulário pelo rótulo: convênio/carteirinha e profissão."""

import pytest

from veu.core.detectors import DetectorConvenio, DetectorProfissao


def trechos(detector, texto):
    return [texto[a.inicio:a.fim] for a in detector.detectar(texto)]


@pytest.mark.parametrize(
    "texto, esperado",
    [
        ("Convênio: Saúde Aurora, carteirinha 0000 1234 5678", ["Saúde Aurora", "0000 1234 5678"]),
        ("Convênio médico: Bradesco Saúde\nIdade: 52", ["Bradesco Saúde"]),
        ("Plano de saúde: Unimed Rio – carteira do plano nº 0 123 456789012 3", ["Unimed Rio", "0 123 456789012 3"]),
        ("Carteirinha: AB 123456-7, titular", ["AB 123456-7"]),
        ("carteirinha 0000 1234 5678 Válida até 2027", ["0000 1234 5678"]),
        ("Nº da carteirinha: 987654321", ["987654321"]),
    ],
)
def test_convenio(texto, esperado):
    assert trechos(DetectorConvenio(), texto) == esperado


@pytest.mark.parametrize(
    "texto",
    [
        "Convênio: particular",
        "Convênio: SUS",
        "Convênio: (em branco)",
        "O convênio não cobre o exame.",  # sem o rótulo com dois-pontos
        "carteirinha 123",  # número curto demais
        "Carteira de identidade 12.345.678-9",  # é RG, não convênio
    ],
)
def test_convenio_negativos(texto):
    assert trechos(DetectorConvenio(), texto) == []


@pytest.mark.parametrize(
    "texto, esperado",
    [
        ("Profissão: professora\nIdade: 52", ["professora"]),
        ("Ocupação: motorista de aplicativo", ["motorista de aplicativo"]),
        ("Cargo: Auxiliar de enfermagem; turno noturno", ["Auxiliar de enfermagem"]),
    ],
)
def test_profissao(texto, esperado):
    assert trechos(DetectorProfissao(), texto) == esperado


@pytest.mark.parametrize("texto", ["Profissão: (em branco)", "Ocupação: -", "a profissão dela é exigente"])
def test_profissao_negativos(texto):
    assert trechos(DetectorProfissao(), texto) == []
