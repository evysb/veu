"""Estilo de tarja PESSOAS: cada pessoa vira [P1], [P2]… em todas as ocorrências."""

import pymupdf
import pytest

from veu.core import pessoas
from veu.core.models import Analise, Deteccao, EstiloTarja, Status, TextoPagina
from veu.core.pipeline import analisar
from veu.core.redaction import OpcoesAnonimizacao, anonimizar
from veu.core.revisao import Revisao


def _nome(trecho: str, pagina: int = 0, y: float = 0.0, tipo: str = "NOME") -> Deteccao:
    return Deteccao(tipo=tipo, pagina=pagina, trecho=trecho, rects=[(10.0, y, 100.0, y + 10)])


def _revisao(*dets: Deteccao) -> Revisao:
    analise = Analise(caminho="x.pdf", paginas=[TextoPagina(0, 600, 800)], deteccoes=list(dets))
    return Revisao(analise)


# ---------------------------------------------------------------- agrupamento
def test_variacoes_do_mesmo_nome_ficam_juntas():
    a = _nome("Maria Aparecida Souza", y=10)
    b = _nome("Sra. Souza", y=20)
    c = _nome("MARIA APARECIDA SOUZA", y=30)
    d = _nome("Maria Aparecida de Souza", y=40)
    g = pessoas.agrupar([a, b, c, d])
    assert g[a.id] == g[b.id] == g[c.id] == g[d.id]


def test_acentos_e_tratamento_sao_ignorados():
    a = _nome("João Lima", y=10)
    b = _nome("Dr. Joao Lima", y=20)
    assert pessoas.agrupar([a, b])[a.id] == pessoas.agrupar([a, b])[b.id]


def test_pessoas_diferentes_ficam_separadas():
    a = _nome("Maria Souza", y=10)
    b = _nome("João Lima", y=20)
    g = pessoas.agrupar([a, b])
    assert g[a.id] != g[b.id]


def test_nome_parcial_ambiguo_vira_pessoa_propria():
    a = _nome("Maria Souza", y=10)
    b = _nome("Maria Lima", y=20)
    c = _nome("Maria", y=30)
    g = pessoas.agrupar([a, b, c])
    assert len({g[a.id], g[b.id], g[c.id]}) == 3


def test_outros_tipos_nao_entram():
    assert pessoas.agrupar([_nome("Maria Souza", tipo="CPF")]) == {}


# ---------------------------------------------------------------- numeração
def test_numeracao_segue_ordem_no_documento():
    b = _nome("João Lima", y=50)
    a = _nome("Maria Souza", y=10)
    c = _nome("Sr. Lima", pagina=0, y=90)
    r = _revisao(b, a, c)
    rot = r.rotulo_por_id()
    assert rot[a.id] == "[P1]" and rot[b.id] == "[P2]" and rot[c.id] == "[P2]"


def test_rejeitados_nao_contam_nem_recebem_rotulo():
    a = _nome("Maria Souza", y=10)
    b = _nome("João Lima", y=20)
    r = _revisao(a, b)
    r.definir_status([a.id], Status.REJEITADA)
    assert r.rotulo_por_id() == {b.id: "[P1]"}


# ---------------------------------------------------------------- revisão
def test_renomear_vale_para_todas_as_ocorrencias():
    a = _nome("Maria Souza", y=10)
    b = _nome("Sra. Souza", y=20)
    r = _revisao(a, b)
    assert r.renomear_pessoa(r.grupo_de(a.id), "paciente") == "[PACIENTE]"
    assert set(r.rotulo_por_id().values()) == {"[PACIENTE]"}
    r.renomear_pessoa(r.grupo_de(a.id), "")  # vazio volta ao automático
    assert set(r.rotulo_por_id().values()) == {"[P1]"}


@pytest.mark.parametrize("rotulo", ["Maria", "Dona Souza", "souza"])
def test_rotulo_com_parte_do_nome_e_recusado(rotulo):
    a = _nome("Maria Souza")
    r = _revisao(a)
    with pytest.raises(pessoas.RotuloInvalido):
        r.renomear_pessoa(r.grupo_de(a.id), rotulo)


def test_rotulo_repetido_e_recusado():
    a = _nome("Maria Souza", y=10)
    b = _nome("João Lima", y=20)
    r = _revisao(a, b)
    with pytest.raises(pessoas.RotuloInvalido):
        r.renomear_pessoa(r.grupo_de(b.id), "P1")


def test_juntar_e_separar():
    a = _nome("Maria Souza", y=10)
    b = _nome("Maria", y=20)
    c = _nome("Maria Lima", y=30)
    r = _revisao(a, b, c)
    assert r.grupo_de(b.id) not in (r.grupo_de(a.id), r.grupo_de(c.id))  # ambíguo
    r.renomear_pessoa(r.grupo_de(b.id), "MÃE")
    r.juntar_pessoas([a.id, b.id])
    rot = r.rotulo_por_id()
    assert rot[a.id] == rot[b.id] == "[MÃE]" and rot[c.id] == "[P2]"
    r.separar_pessoa([b.id])
    rot = r.rotulo_por_id()
    assert rot[a.id] == "[MÃE]" and rot[b.id] == "[P2]" and rot[c.id] == "[P3]"


# ---------------------------------------------------------------- ponta a ponta
LINHAS = [
    "Paciente: Maria Aparecida Souza, 54 anos, deu entrada no pronto-socorro.",
    "A Sra. Souza relata dor toracica ha dois dias.",
    "Acompanhante: Joao Pedro Lima, filho da paciente.",
    "Maria Aparecida Souza nega alergias. O Sr. Lima assina o termo.",
]


@pytest.fixture(scope="module")
def pdf_pessoas(tmp_path_factory):
    caminho = tmp_path_factory.mktemp("pessoas") / "pessoas.pdf"
    doc = pymupdf.open()
    page = doc.new_page()
    for i, linha in enumerate(LINHAS):
        page.insert_text((56, 72 + 18 * i), linha, fontname="helv", fontsize=11)
    doc.save(caminho)
    return caminho


def test_pdf_sai_com_rotulos_por_pessoa(pdf_pessoas, tmp_path):
    a = analisar(str(pdf_pessoas))
    Revisao(a).aceitar_pendentes()
    saida = tmp_path / "saida.pdf"
    r = anonimizar(a, str(saida), OpcoesAnonimizacao(estilo=EstiloTarja.PESSOAS))

    assert r.verificacao.ok, r.verificacao.vazamentos
    texto = pymupdf.open(saida)[0].get_text()
    for nome in ("Maria", "Aparecida", "Souza", "Joao", "Lima"):
        assert nome not in texto
    assert texto.count("[P1]") >= 3 and texto.count("[P2]") >= 2
    assert r.pessoas == 2


def test_renomeado_na_revisao_vai_para_o_pdf(pdf_pessoas, tmp_path):
    a = analisar(str(pdf_pessoas))
    rev = Revisao(a)
    rev.aceitar_pendentes()
    maria = next(d for d in a.deteccoes if d.tipo == "NOME" and "Maria" in d.trecho)
    rev.renomear_pessoa(rev.grupo_de(maria.id), "paciente")
    saida = tmp_path / "saida.pdf"
    opcoes = OpcoesAnonimizacao(estilo=EstiloTarja.PESSOAS, rotulos_por_id=rev.rotulo_por_id())
    r = anonimizar(a, str(saida), opcoes)

    assert r.verificacao.ok, r.verificacao.vazamentos
    texto = pymupdf.open(saida)[0].get_text()
    assert "[PACIENTE]" in texto and "[P2]" in texto and "Maria" not in texto


def test_cli_estilo_pessoas_audita_so_a_contagem(pdf_pessoas, tmp_path):
    from veu.cli import OK, main
    from veu.core.audit import ler_historico

    saida = tmp_path / "saida.pdf"
    assert main([str(pdf_pessoas), "--saida", str(saida), "--sem-revisao", "--estilo", "pessoas"]) == OK
    assert "[P1]" in pymupdf.open(saida)[0].get_text()
    recibo = ler_historico()[-1]
    assert recibo.estilo_tarja == "pessoas" and recibo.pessoas_rotuladas == 2
    assert "Maria" not in str(recibo) and "Lima" not in str(recibo)
