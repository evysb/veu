"""Nomes de instituições e de cidades."""

import pytest

from veu.core.detectors import DetectorCidade, DetectorInstituicao


def instituicoes(texto):
    return [texto[a.inicio:a.fim] for a in DetectorInstituicao().detectar(texto)]


def cidades(*textos, pagina=0):
    d = DetectorCidade()
    d.preparar(list(textos))
    texto = textos[pagina]
    return sorted({texto[a.inicio:a.fim] for a in d.detectar(texto)})


# ---------------------------------------------------------------- instituições
@pytest.mark.parametrize(
    "texto, esperado",
    [
        ("Hospital Santa Aurora · Período: 13/11", ["Hospital Santa Aurora"]),
        ("Clínica Vida Plena · Preenchido pelo paciente", ["Clínica Vida Plena"]),
        ("Cesárea em 2004, na Maternidade Santa Aurora.", ["Maternidade Santa Aurora"]),
        ("agora dou aula no Colégio Monte Azul, e estou", ["Colégio Monte Azul"]),
        ("o pai é dono da Padaria\nSilveira, no centro", ["Padaria\nSilveira"]),  # nome na linha de baixo
        ("Hospital Municipal de Campinas", ["Hospital Municipal de Campinas"]),
        ("internada na maternidade Santa Aurora", ["maternidade Santa Aurora"]),
        ("HOSPITAL SÃO LUCAS DE EXEMPLO – PRONTUÁRIO", ["HOSPITAL SÃO LUCAS DE EXEMPLO"]),
    ],
)
def test_instituicao(texto, esperado):
    assert instituicoes(texto) == esperado


@pytest.mark.parametrize(
    "texto",
    [
        "Formulário de pré-consulta – Clínica Médica",  # especialidade, não lugar
        "Escola Estadual",
        "Secretaria de Saúde",
        "Troquei de escola em outubro",  # nome em minúsculas
        "O laboratório do hospital estava fechado",
        "HISTÓRIA CLÍNICA\nPaciente gestante",  # título seguido da próxima linha
    ],
)
def test_instituicao_negativos(texto):
    assert instituicoes(texto) == []


# ---------------------------------------------------------------- cidades
@pytest.mark.parametrize(
    "texto, esperado",
    [
        ("Naturalidade: Feira de Santana/BA", ["Feira de Santana"]),
        ("Natural de Ribeirão Preto, mora em Campinas.", ["Campinas", "Ribeirão Preto"]),
        ("Cidade: São Paulo - SP", ["São Paulo"]),
        ("informou que é dono de uma loja no centro de Santa Aurora do Sul.", ["Santa Aurora do Sul"]),
        ("Endereço: Rua A, 10, Jardim Primavera, Santa Aurora do Sul", ["Santa Aurora do Sul"]),
    ],
)
def test_cidade(texto, esperado):
    assert cidades(texto) == esperado


@pytest.mark.parametrize(
    "texto",
    [
        "RG: 12.345.678-9 SSP/SP",  # sigla do órgão, não cidade
        "Encaminhada ao Centro de Saúde",
        "Cidade: (em branco)",
    ],
)
def test_cidade_negativos(texto):
    assert cidades(texto) == []


def test_cidade_reconhecida_e_marcada_em_todo_o_documento():
    pag1 = "Endereço: Av. dos Ipês, 845, Santa Aurora do Sul"
    pag2 = "Visitou a feira de Santa Aurora do Sul no sábado."  # sem contexto próprio
    assert cidades(pag1, pag2, pagina=1) == ["Santa Aurora do Sul"]


def test_propagacao_exige_maiuscula():
    pag1 = "Naturalidade: Natal/RN"
    pag2 = "Ficou internada no natal."
    assert cidades(pag1, pag2, pagina=1) == []
