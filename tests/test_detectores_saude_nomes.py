import pytest

from veu.core.detectors import DetectorNome, DetectorSaude


def achados(detector, texto):
    return {texto[a.inicio:a.fim]: a.confianca for a in detector.detectar(texto)}


@pytest.fixture(scope="module")
def saude():
    return DetectorSaude()


# ---------------------------------------------------------------- saúde
def test_saude_doencas_medicamentos_e_cid(saude):
    texto = "Paciente gestante com diagnóstico de diabetes. CID F32.1, F41.0. Em uso de sertralina."
    a = achados(saude, texto)
    assert {"gestante", "diabetes", "F32.1", "F41.0", "sertralina"} <= set(a)
    assert a["diabetes"] >= 0.85  # contexto clínico aumenta a confiança


def test_saude_ignora_acentos_e_caixa(saude):
    a = achados(saude, "HIPERTENSÃO ARTERIAL e Depressao")
    assert "HIPERTENSÃO ARTERIAL" in a and "Depressao" in a


def test_termos_clinicos_sozinhos_nao_sao_tarjados(saude):
    assert achados(saude, "O laudo do exame e o prontuário foram revisados.") == {}


def test_siglas(saude):
    assert "HIV" in achados(saude, "Teste rápido de HIV")  # sigla forte: sempre
    assert achados(saude, "Reunião do AVC Club") == {}  # sigla fraca sem contexto
    assert "AVC" in achados(saude, "diagnóstico: AVC isquêmico")


def test_cid_exige_rotulo_ou_contexto(saude):
    assert "J45" in achados(saude, "CID-10: J45")
    assert achados(saude, "Sala B12, andar 3") == {}
    assert achados(saude, "modelo X50.1 da impressora") == {}


# ---------------------------------------------------------------- nomes
@pytest.fixture(scope="module", params=[True, False], ids=["com_ner", "sem_ner"])
def nomes(request):
    return DetectorNome(usar_ner=request.param)


@pytest.mark.parametrize(
    "texto, nome",
    [
        ("Paciente: Maria Fictícia da Silva", "Maria Fictícia da Silva"),
        ("Assinado por Carlos Eduardo Souza em 02/10", "Carlos Eduardo Souza"),
        ("Responsável: João Pereira Santos (esposo)", "João Pereira Santos"),
        ("NOME: ANA PAULA DOS SANTOS", "ANA PAULA DOS SANTOS"),
        ("A Sra. Helena compareceu.", "Helena"),
    ],
)
def test_nomes_positivos(nomes, texto, nome):
    a = achados(nomes, texto)
    assert nome in a, a
    assert a[nome] >= 0.5


@pytest.mark.parametrize(
    "texto",
    [
        "Hospital São Lucas atende na Rua João Pessoa.",
        "O paciente relatou melhora. Rosa dos ventos.",
        "Exame de imagem sem alterações.",
    ],
)
def test_nomes_negativos(nomes, texto):
    a = achados(nomes, texto)
    assert all(conf < 0.5 for conf in a.values()), a


def test_nome_nao_atravessa_linha_para_outro_campo():
    texto = "Paciente: Maria Fictícia\nRelatório de alta"
    a = achados(DetectorNome(usar_ner=False), texto)
    assert "Maria Fictícia" in a
