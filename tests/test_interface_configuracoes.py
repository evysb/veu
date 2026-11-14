"""Tela de configurações (sem diálogos modais)."""

import pytest
from PySide6.QtCore import Qt

from veu.core.models import EstiloTarja
from veu.core.policy import Politica, PoliticaInvalida, TipoPersonalizado, carregar_politica, locais, politica_ativa
from veu.ui.configuracoes import DialogoConfiguracoes


@pytest.fixture
def dialogo(qtbot):
    pol, origem = politica_ativa()
    d = DialogoConfiguracoes(pol, origem)
    qtbot.addWidget(d)
    return d


def _linha_tipo(d, id_tipo):
    return next(i for i, t in enumerate(d._tipos_padrao) if t.id == id_tipo)


def test_le_e_salva_politica(dialogo):
    d = dialogo
    d.campo_nome.setText("Hospital Exemplo")
    d.tabela_tipos.item(_linha_tipo(d, "TELEFONE"), 0).setCheckState(Qt.Unchecked)
    d.tabela_tipos.cellWidget(_linha_tipo(d, "NOME"), 3).setValue(0.7)
    d._adicionar_pers("Matrícula funcionário", r"MAT-\d{6}", "", "#123456", True, False)
    d.texto_sempre.setPlainText("Projeto Águia\n\nProjeto Águia\nACME")
    d.texto_excecoes.setPlainText("Clínica Exemplo")
    d.combo_estilo.setCurrentIndex(d.combo_estilo.findData(EstiloTarja.ROTULO))

    d._salvar()
    salvo = carregar_politica(locais.caminho_usuario())
    assert salvo.nome == "Hospital Exemplo"
    assert not salvo.tipo_ativo("TELEFONE")
    assert salvo.confianca_minima("NOME") == 0.7
    assert salvo.tipos_personalizados[0].id == "MATRICULA_FUNCIONARIO"
    assert salvo.sempre_tarjar == ["Projeto Águia", "ACME"]  # vazios e repetidos removidos
    assert salvo.excecoes == ["Clínica Exemplo"]
    assert salvo.tarja.estilo == EstiloTarja.ROTULO
    assert politica_ativa()[0].nome == "Hospital Exemplo"


def test_regex_invalida_nao_salva(dialogo):
    dialogo._adicionar_pers("Ruim", "MAT-(\\d", "", "#123456", True, False)
    with pytest.raises(PoliticaInvalida, match="expressão regular inválida"):
        dialogo._ler()
    assert "inválida" in dialogo.teste_resultado.text()


def test_teste_de_regex_ao_vivo(dialogo):
    dialogo._adicionar_pers("Matrícula", r"MAT-\d{6}", "", "#123456", True, False)
    dialogo.teste_texto.setText("MAT-123456 e MAT-654321, mas não MAT-12")
    assert dialogo.teste_resultado.text().startswith("2 ocorrência(s)")


def test_politica_carregada_preenche_a_tela(qtbot):
    pol = Politica(
        nome="Importada",
        usar_ner=False,
        sempre_tarjar=["X"],
        tipos_personalizados=[TipoPersonalizado(nome="Protocolo", regex=r"PRT\d+", ativo=False)],
    )
    pol.tipos["CPF"].ativo = False
    d = DialogoConfiguracoes(pol, politica_ativa()[1])
    qtbot.addWidget(d)
    assert d.campo_nome.text() == "Importada"
    assert not d.chk_ner.isChecked()
    assert d.tabela_tipos.item(_linha_tipo(d, "CPF"), 0).checkState() == Qt.Unchecked
    assert d.tabela_pers.rowCount() == 1 and d.tabela_pers.item(0, 0).checkState() == Qt.Unchecked
    assert d._ler() == pol


def test_politica_bloqueada_e_somente_leitura(qtbot):
    locais.salvar_politica(Politica(nome="Do TI", bloqueada=True), locais.caminho_organizacao())
    pol, origem = politica_ativa()
    assert not origem.editavel
    d = DialogoConfiguracoes(pol, origem)
    qtbot.addWidget(d)
    assert not d.b_salvar.isEnabled()
    assert not d.tabela_tipos.isEnabled()
