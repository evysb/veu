"""Testes de fumaça da interface (sem diálogos modais)."""

import pytest
from PySide6.QtCore import QRectF

from veu.core.models import Origem, Status
from veu.ui.janela_principal import JanelaPrincipal


@pytest.fixture
def janela(qtbot):
    j = JanelaPrincipal()
    j.resize(1200, 800)
    j.show()
    yield j
    qtbot.waitUntil(lambda: j._tarefa is None, timeout=15000)
    j.alterado = False  # evita o diálogo modal "Descartar revisão?" ao fechar
    j.close()
    j.deleteLater()


def abrir(qtbot, janela, caminho):
    janela.abrir(str(caminho))
    qtbot.waitUntil(lambda: janela.analise is not None and janela._tarefa is None, timeout=15000)


def test_abre_detecta_e_lista(qtbot, janela, pdfs):
    abrir(qtbot, janela, pdfs["texto_nativo"])
    assert janela.pilha.currentIndex() == 1
    assert janela.painel.modelo.rowCount() == len(janela.analise.deteccoes) >= 6
    assert janela.b_anonimizar.isEnabled()


def test_revisao_pela_interface(qtbot, janela, pdfs):
    abrir(qtbot, janela, pdfs["texto_nativo"])
    rev = janela.revisao
    primeira = rev.deteccoes[0]

    janela.definir_status([primeira.id], Status.REJEITADA)
    assert primeira.status == Status.REJEITADA

    janela._caixa_desenhada(QRectF(50, 50, 120, 30))
    manual = rev.deteccoes[-1]
    assert manual.origem == Origem.MANUAL and manual.status == Status.ACEITA

    janela.campo_busca.setText("Maria Fictícia")
    janela.marcar_termo()
    assert any(d.origem == Origem.BUSCA for d in rev.deteccoes)

    janela.excluir([manual.id])
    assert rev.por_id(manual.id) is None

    # filtro por status na lista
    janela.painel.combo_status.setCurrentIndex(janela.painel.combo_status.findData(Status.REJEITADA))
    assert janela.painel.filtro.rowCount() == 1


def test_navegacao_e_zoom(qtbot, janela, pdfs):
    abrir(qtbot, janela, pdfs["longo"])
    janela.ir_para_pagina(10)
    assert janela.spin_pagina.value() == 11
    z = janela.zoom
    janela.mudar_zoom(1)
    assert janela.zoom > z
    det = next(d for d in janela.revisao.deteccoes if d.pagina == 30)
    janela.ir_para_deteccao(det.id)
    assert janela.pagina_atual == 30


def test_pagina_escaneada_mostra_aviso(qtbot, janela, pdfs):
    abrir(qtbot, janela, pdfs["escaneado"])
    assert janela.banner.isVisibleTo(janela)


def test_historico_lista_recibos(qtbot, pdfs, tmp_path):
    import shutil

    from veu.cli import main
    from veu.ui.historico import DialogoHistorico

    a = shutil.copy(pdfs["texto_nativo"], tmp_path / "a.pdf")
    main([str(a), "--sem-revisao"])
    d = DialogoHistorico()
    qtbot.addWidget(d)
    assert d.tabela.rowCount() == 1
    assert d.tabela.item(0, 6).text() == "aprovada"
    assert "SHA-256" in d.tabela.item(0, 3).text()  # sem nome de arquivo por padrão


def test_painel_mostra_pessoa_e_menu_junta(qtbot, janela, pdfs):
    from PySide6.QtWidgets import QMenu

    abrir(qtbot, janela, pdfs["prontuario"])
    janela.revisao.aceitar_pendentes()
    janela._atualizar_tudo()
    modelo = janela.painel.modelo
    col = modelo.columnCount() - 1
    nomes = [r for r in range(modelo.rowCount()) if modelo.deteccao(r).tipo == "NOME"]
    assert nomes
    assert all(modelo.index(r, col).data().startswith("[P") for r in nomes)

    ids = [modelo.deteccao(r).id for r in nomes]
    menu = QMenu()
    janela._menu_pessoas(menu, ids[:1])
    assert any(a.text().startswith("Renomear pessoa [P") for a in menu.actions())


def test_aceitar_pendentes_mantem_rejeitadas(qtbot, janela, pdfs):
    from veu.core.models import Status

    abrir(qtbot, janela, pdfs["prontuario"])
    dets = janela.revisao.deteccoes
    assert len(dets) >= 2
    rejeitada, aceita = dets[0].id, dets[1].id
    janela.revisao.definir_status([rejeitada], Status.REJEITADA)
    janela.revisao.definir_status([aceita], Status.ACEITA)
    janela._atualizar_tudo()

    pendentes = janela.painel.ids_pendentes_visiveis()
    assert rejeitada not in pendentes and aceita not in pendentes
    janela.painel._emitir(pendentes, Status.ACEITA)

    por_id = {d.id: d.status for d in janela.revisao.deteccoes}
    assert por_id[rejeitada] == Status.REJEITADA
    assert all(st != Status.PENDENTE for st in por_id.values())
