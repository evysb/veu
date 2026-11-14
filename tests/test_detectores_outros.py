import pytest

from veu.core.detectors import (
    DetectorContaBancaria,
    DetectorDataNascimento,
    DetectorEndereco,
    DetectorPix,
    DetectorPlaca,
    DetectorRegistroProfissional,
)


def trechos(detector, texto):
    return [texto[a.inicio:a.fim] for a in detector.detectar(texto)]


# ---------------------------------------------------------------- nascimento
@pytest.mark.parametrize(
    "texto, esperado",
    [
        ("Data de nascimento: 14/03/1985", ["14/03/1985"]),
        ("DN 01-12-1990", ["01-12-1990"]),
        ("nascida em 3 de março de 1979", ["3 de março de 1979"]),
        ("Nasc.: 5/7/62", ["5/7/62"]),
    ],
)
def test_nascimento_positivos(texto, esperado):
    assert trechos(DetectorDataNascimento(), texto) == esperado


@pytest.mark.parametrize("texto", ["Consulta em 14/03/2024", "nascimento: 31/02/1985", "Data: 01/01/2000"])
def test_nascimento_negativos(texto):
    assert trechos(DetectorDataNascimento(), texto) == []


# ---------------------------------------------------------------- placa
def test_placa():
    d = DetectorPlaca()
    assert trechos(d, "placa BRA2E19") == ["BRA2E19"]
    assert trechos(d, "carro ABC-1234") == ["ABC-1234"]
    assert trechos(d, "veículo ABC 1234") == ["ABC 1234"]
    assert trechos(d, "certificação ISO 9001") == []
    assert trechos(d, "norma NBR 6023") == []


# ---------------------------------------------------------------- banco / pix
def test_dados_bancarios():
    d = DetectorContaBancaria()
    assert trechos(d, "Banco do Brasil, agência 1234-5, conta corrente 98765-4") == ["1234-5", "98765-4"]
    assert trechos(d, "Ag. 0001 C/C 123456-7") == ["0001", "123456-7"]
    assert trechos(d, "ver a conta de luz") == []


def test_pix():
    d = DetectorPix()
    uuid = "123e4567-e89b-42d3-a456-426614174000"
    assert trechos(d, f"Chave Pix: {uuid}") == [uuid, uuid]  # UUID + "chave pix:" (resolvido no pipeline)
    assert trechos(d, "chave pix (e-mail): maria@exemplo.com.") == ["maria@exemplo.com"]
    assert trechos(d, "sem chave aqui") == []


def test_registro_profissional():
    d = DetectorRegistroProfissional()
    assert trechos(d, "Dra. Ana, CRM-SP 123456.") == ["CRM-SP 123456"]
    assert trechos(d, "CRO/RJ 12.345") == ["CRO/RJ 12.345"]
    assert trechos(d, "COREN 456789-SP") == ["COREN 456789-SP"]
    assert trechos(d, "CRMV não é listado; crm minúsculo também não 1234") == []


# ---------------------------------------------------------------- endereço
@pytest.mark.parametrize(
    "texto, esperado",
    [
        (
            "Endereço: Rua das Acácias, 245, apto 32 - Jardim Primavera, São Paulo/SP - CEP 04567-010",
            "Rua das Acácias, 245, apto 32 - Jardim Primavera, São Paulo/SP - CEP 04567-010",
        ),
        ("mora na Av. Paulista, 1000 - Bela Vista", "Av. Paulista, 1000 - Bela Vista"),
        ("Rua 7 de Setembro, nº 15, casa 2", "Rua 7 de Setembro, nº 15, casa 2"),
        ("RUA DAS FLORES, 45 - CENTRO", "RUA DAS FLORES, 45 - CENTRO"),
        ("Travessa Boa Vista s/n", "Travessa Boa Vista s/n"),
    ],
)
def test_endereco_completo(texto, esperado):
    assert esperado in trechos(DetectorEndereco(), texto)


def test_endereco_nao_engole_campo_seguinte():
    texto = "Rua das Acácias, 245 - Tel: (11) 98765-4321"
    assert trechos(DetectorEndereco(), texto)[0] == "Rua das Acácias, 245"


def test_endereco_quebrado_em_linhas():
    texto = "Rua das Acácias, 245\nSão Paulo/SP\nCEP 04567-010\nTelefone: 1234"
    assert trechos(DetectorEndereco(), texto)[0] == "Rua das Acácias, 245\nSão Paulo/SP\nCEP 04567-010"


def test_cep_isolado_e_endereco_rotulado():
    d = DetectorEndereco()
    assert "01310-100" in trechos(d, "CEP: 01310-100")
    assert "Sítio Boa Esperança, zona rural, Itabuna/BA" in trechos(
        d, "Endereço: Sítio Boa Esperança, zona rural, Itabuna/BA"
    )


@pytest.mark.parametrize("texto", ["a rua estava vazia", "Rua", "R. Silva, 23 anos"])
def test_endereco_negativos(texto):
    achados = DetectorEndereco().detectar(texto)
    assert all(a.confianca < 0.7 for a in achados)


def test_pix_nao_pega_palavra_da_linha_seguinte():
    assert trechos(DetectorPix(), "Chave Pix: \n\nAssinado por Fulano") == []


def test_pix_tolera_espaco_do_ocr():
    texto = "Chave Pix: 123e4567-e89b-42d3-a456-4266 14174000"
    assert "123e4567-e89b-42d3-a456-4266 14174000" in trechos(DetectorPix(), texto)


def test_rotulo_endereco_nao_atravessa_linha():
    assert trechos(DetectorEndereco(), "Endereço\nTelefone: 1234") == []
