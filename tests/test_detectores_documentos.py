import pytest

from tests.fixtures import dados as D
from veu.core.detectors import (
    DetectorCNH,
    DetectorCNPJ,
    DetectorCNS,
    DetectorCPF,
    DetectorPassaporte,
    DetectorPIS,
    DetectorRG,
    DetectorTituloEleitor,
)
from veu.core.detectors.validacao import cnpj_valido, gerar_dv_cnpj


def trechos(detector, texto):
    return [texto[a.inicio:a.fim] for a in detector.detectar(texto)]


# ---------------------------------------------------------------- CNPJ
def test_cnpj_alfanumerico_exemplo_oficial():
    assert gerar_dv_cnpj("12ABC34501DE") == "12ABC34501DE35"
    assert cnpj_valido("12ABC34501DE35")
    assert not cnpj_valido("12ABC34501DE36")


@pytest.mark.parametrize(
    "texto, esperado",
    [
        ("CNPJ 11.222.333/0001-81", ["11.222.333/0001-81"]),
        ("cnpj: 11222333000181", ["11222333000181"]),
        ("Empresa 11222333000181 ltda", ["11222333000181"]),
        ("Fornecedor 12.ABC.345/01DE-35", ["12.ABC.345/01DE-35"]),
        ("CNPJ 12ABC34501DE35", ["12ABC34501DE35"]),
    ],
)
def test_cnpj_positivos(texto, esperado):
    assert trechos(DetectorCNPJ(), texto) == esperado


@pytest.mark.parametrize(
    "texto",
    ["CNPJ 11.222.333/0001-82", "11.111.111/1111-11", "código 12ABC34501DE35 do lote", "pedido 112223330001810"],
)
def test_cnpj_negativos(texto):
    assert trechos(DetectorCNPJ(), texto) == []


# ---------------------------------------------------------------- PIS
def test_pis():
    p = D.PIS
    assert trechos(DetectorPIS(), f"PIS {D.mascarar_pis(p)}") == [D.mascarar_pis(p)]
    assert trechos(DetectorPIS(), f"NIS: {p}") == [p]
    assert trechos(DetectorPIS(), f"número {p}") == []  # 11 dígitos soltos: só com contexto
    assert trechos(DetectorPIS(), f"PIS {p[:-1]}{(int(p[-1]) + 1) % 10}") == []


def test_cpf_nao_confunde_com_pis_ou_cnh():
    # Mesmo que o número também valide como CPF, a palavra-chave decide.
    assert trechos(DetectorCPF(), f"CNH nº {D.CNH}") == []
    assert trechos(DetectorCPF(), f"PIS {D.PIS}") == []


# ---------------------------------------------------------------- CNS
def test_cns():
    c = D.CNS
    formatado = f"{c[:3]} {c[3:7]} {c[7:11]} {c[11:]}"
    assert trechos(DetectorCNS(), f"Cartão SUS: {formatado}") == [formatado]
    assert trechos(DetectorCNS(), f"CNS {c}") == [c]
    assert trechos(DetectorCNS(), f"CNS {c[:-1]}{(int(c[-1]) + 1) % 10}") == []
    assert trechos(DetectorCNS(), "CNS 300000000000000") == []  # não começa com 1, 2, 7, 8, 9


# ---------------------------------------------------------------- Título
def test_titulo_eleitor():
    t = D.TITULO
    det = DetectorTituloEleitor()
    achados = det.detectar(f"Título de eleitor: {t[:4]} {t[4:8]} {t[8:]}")
    assert len(achados) == 1 and achados[0].confianca >= 0.9
    sem_contexto = det.detectar(f"ref {t}")
    assert len(sem_contexto) == 1 and sem_contexto[0].confianca < 0.6
    assert det.detectar(f"Título {t[:8]}29{t[10:]}") == []  # UF inexistente


# ---------------------------------------------------------------- CNH
def test_cnh():
    assert trechos(DetectorCNH(), f"CNH nº {D.CNH}") == [D.CNH]
    assert trechos(DetectorCNH(), f"Habilitação {D.CNH}") == [D.CNH]
    assert trechos(DetectorCNH(), f"protocolo {D.CNH}") == []
    assert trechos(DetectorCNH(), "CNH 12345678901") == []  # DV inválido


# ---------------------------------------------------------------- RG
@pytest.mark.parametrize(
    "texto, esperado",
    [
        ("RG: 12.345.678-9", ["12.345.678-9"]),
        ("RG nº 1.234.567", ["1.234.567"]),
        ("Identidade 12345678X", ["12345678X"]),
        ("Carteira de identidade MG-12.345.678", ["MG-12.345.678"]),
        ("documento 4.567.890 SSP/BA", ["4.567.890"]),
        ("R.G. 23456789-0 expedido", ["23456789-0"]),
    ],
)
def test_rg_positivos(texto, esperado):
    assert trechos(DetectorRG(), texto) == esperado


@pytest.mark.parametrize(
    "texto",
    [
        "processo 12.345.678-9",  # sem palavra-chave
        "RG 1234",  # curto demais
        "Identidade visual aprovada em 2024",
        "RG: 11.111.111-1",  # repetido
    ],
)
def test_rg_negativos(texto):
    assert trechos(DetectorRG(), texto) == []


# ---------------------------------------------------------------- Passaporte
def test_passaporte():
    assert trechos(DetectorPassaporte(), "Passaporte: FZ123456") == ["FZ123456"]
    assert trechos(DetectorPassaporte(), "passport no. YB987654") == ["YB987654"]
    assert trechos(DetectorPassaporte(), "lote FZ123456") == []
