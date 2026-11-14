"""Janela principal: abrir → detectar → revisar → anonimizar → salvar."""

from __future__ import annotations

import os
from collections import Counter

import pymupdf
from PySide6.QtCore import QPoint, QRectF, Qt, QTimer, Slot
from PySide6.QtGui import QAction, QActionGroup, QImage, QKeySequence, QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QDockWidget,
    QFileDialog,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMessageBox,
    QProgressDialog,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QStackedWidget,
    QStyle,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from veu import __version__
from veu.core.extraction import SenhaIncorreta, SenhaNecessaria, abrir_documento
from veu.core.models import Analise, Origem, Status
from veu.core.audit import criar_recibo, registrar
from veu.core.pipeline import analisar
from veu.core.policy import politica_ativa
from veu.core.redaction import ArquivoOriginalProtegido, anonimizar, caminho_saida_padrao
from veu.core.revisao import Revisao
from veu.core.tipos import obter_tipo
from veu.ui.configuracoes import DialogoConfiguracoes
from veu.ui.dialogos import DialogoConfirmacao, DialogoResultado
from veu.ui.historico import DialogoHistorico
from veu.ui.painel_deteccoes import PainelDeteccoes
from veu.ui.tarefas import Tarefa
from veu.ui.visualizador import CaixaExibida, Visualizador

ZOOM_MIN, ZOOM_MAX = 0.3, 5.0


class JanelaPrincipal(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Véu — anonimizador de PDF")
        self.resize(1360, 880)
        self.setAcceptDrops(True)

        self.analise: Analise | None = None
        self.revisao: Revisao | None = None
        self.doc: pymupdf.Document | None = None  # só para renderizar as páginas
        self.pagina_atual = 0
        self.zoom = 1.0
        self.ajustar_largura = True
        self.alterado = False
        self._selecao: list[str] = []
        self._tarefa: Tarefa | None = None
        self._progresso: QProgressDialog | None = None
        self.politica, self.origem_politica = politica_ativa()
        self._callbacks = (None, None)

        self._montar_interface()
        self._atualizar_estado()

    # =================================================================== UI
    def _montar_interface(self) -> None:
        st = self.style()
        tb = QToolBar("Principal")
        tb.setMovable(False)
        tb.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.addToolBar(tb)

        self.a_abrir = QAction(st.standardIcon(QStyle.SP_DialogOpenButton), "Abrir PDF…", self)
        self.a_abrir.setShortcut(QKeySequence.Open)
        self.a_abrir.triggered.connect(self.escolher_arquivo)
        tb.addAction(self.a_abrir)

        self.b_anonimizar = QPushButton("Anonimizar e salvar…")
        self.b_anonimizar.setObjectName("primario")
        self.b_anonimizar.setShortcut(QKeySequence.Save)
        self.b_anonimizar.clicked.connect(self.anonimizar)
        tb.addWidget(self.b_anonimizar)
        tb.addSeparator()

        self.a_ant = QAction(st.standardIcon(QStyle.SP_ArrowBack), "", self)
        self.a_ant.setToolTip("Página anterior (PgUp)")
        self.a_ant.setShortcut(QKeySequence(Qt.Key_PageUp))
        self.a_ant.triggered.connect(lambda: self.ir_para_pagina(self.pagina_atual - 1))
        self.a_prox = QAction(st.standardIcon(QStyle.SP_ArrowForward), "", self)
        self.a_prox.setToolTip("Próxima página (PgDown)")
        self.a_prox.setShortcut(QKeySequence(Qt.Key_PageDown))
        self.a_prox.triggered.connect(lambda: self.ir_para_pagina(self.pagina_atual + 1))
        self.spin_pagina = QSpinBox()
        self.spin_pagina.setMinimum(1)
        self.spin_pagina.setKeyboardTracking(False)
        self.spin_pagina.valueChanged.connect(lambda v: self.ir_para_pagina(v - 1))
        self.lbl_total = QLabel(" de 0 ")
        tb.addAction(self.a_ant)
        tb.addWidget(self.spin_pagina)
        tb.addWidget(self.lbl_total)
        tb.addAction(self.a_prox)
        tb.addSeparator()

        self.a_zoom_menos = QAction("−", self, toolTip="Diminuir zoom (Ctrl+−)", shortcut=QKeySequence.ZoomOut)
        self.a_zoom_mais = QAction("+", self, toolTip="Aumentar zoom (Ctrl++)", shortcut=QKeySequence.ZoomIn)
        self.a_zoom_ajustar = QAction("Ajustar à largura", self, shortcut=QKeySequence("Ctrl+0"))
        self.a_zoom_menos.triggered.connect(lambda: self.mudar_zoom(-1))
        self.a_zoom_mais.triggered.connect(lambda: self.mudar_zoom(1))
        self.a_zoom_ajustar.triggered.connect(self.zoom_ajustar)
        self.lbl_zoom = QLabel("100%")
        self.lbl_zoom.setMinimumWidth(44)
        self.lbl_zoom.setAlignment(Qt.AlignCenter)
        tb.addAction(self.a_zoom_menos)
        tb.addWidget(self.lbl_zoom)
        tb.addAction(self.a_zoom_mais)
        tb.addAction(self.a_zoom_ajustar)
        tb.addSeparator()

        grupo = QActionGroup(self)
        self.a_selecionar = QAction("Selecionar (V)", self, checkable=True, shortcut=QKeySequence("V"))
        self.a_desenhar = QAction("Desenhar caixa (D)", self, checkable=True, shortcut=QKeySequence("D"))
        self.a_selecionar.setToolTip("Clique em uma caixa para selecioná-la; botão direito para mais opções")
        self.a_desenhar.setToolTip("Arraste sobre a página para tarjar uma área que o programa não detectou")
        for a in (self.a_selecionar, self.a_desenhar):
            grupo.addAction(a)
            tb.addAction(a)
        self.a_selecionar.setChecked(True)
        self.a_desenhar.toggled.connect(lambda on: self.visualizador.set_modo_desenho(on))
        tb.addSeparator()

        self.campo_busca = QLineEdit()
        self.campo_busca.setPlaceholderText("Buscar termo para tarjar…")
        self.campo_busca.setClearButtonEnabled(True)
        self.campo_busca.setMinimumWidth(220)
        self.campo_busca.setMaximumWidth(320)
        self.campo_busca.returnPressed.connect(self.marcar_termo)
        self.chk_palavra = QCheckBox("Palavra inteira")
        self.chk_palavra.setChecked(True)
        self.b_marcar = QPushButton("Marcar todas")
        self.b_marcar.clicked.connect(self.marcar_termo)
        tb.addWidget(self.campo_busca)
        tb.addWidget(self.chk_palavra)
        tb.addWidget(self.b_marcar)
        espaco = QWidget()
        espaco.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        tb.addWidget(espaco)
        self.a_config = QAction(st.standardIcon(QStyle.SP_FileDialogDetailedView), "Configurações…", self)
        self.a_config.setToolTip("Política: tipos de dado, regras próprias, listas e estilo da tarja")
        self.a_config.triggered.connect(self.abrir_configuracoes)
        tb.addAction(self.a_config)
        self.a_historico = QAction(st.standardIcon(QStyle.SP_FileDialogContentsView), "Histórico…", self)
        self.a_historico.setToolTip("Recibos de auditoria das anonimizações (exportáveis para CSV)")
        self.a_historico.triggered.connect(lambda: DialogoHistorico(self).exec())
        tb.addAction(self.a_historico)

        # Ações sobre a seleção (atalhos valem para a página e para a lista)
        self.a_aceitar = QAction("Aceitar", self, shortcut=QKeySequence("A"))
        self.a_rejeitar = QAction("Rejeitar", self, shortcut=QKeySequence("R"))
        self.a_excluir = QAction("Excluir/rejeitar", self, shortcut=QKeySequence.Delete)
        self.a_aceitar.triggered.connect(lambda: self.definir_status(self._selecao, Status.ACEITA))
        self.a_rejeitar.triggered.connect(lambda: self.definir_status(self._selecao, Status.REJEITADA))
        self.a_excluir.triggered.connect(lambda: self.excluir(self._selecao))
        self.addActions([self.a_aceitar, self.a_rejeitar, self.a_excluir])

        # Área central: boas-vindas ou visualizador
        self.visualizador = Visualizador()
        self.visualizador.caixaDesenhada.connect(self._caixa_desenhada)
        self.visualizador.selecaoAlterada.connect(self._selecao_na_pagina)
        self.visualizador.menuSolicitado.connect(self._menu_caixa)
        self.visualizador.zoomSolicitado.connect(self.mudar_zoom)

        self.banner = QLabel()
        self.banner.setObjectName("aviso")
        self.banner.setWordWrap(True)
        self.banner.hide()
        pagina_doc = QWidget()
        lay = QVBoxLayout(pagina_doc)
        lay.setContentsMargins(6, 6, 6, 0)
        lay.addWidget(self.banner)
        lay.addWidget(self.visualizador, 1)

        boas_vindas = QLabel(
            "<p style='font-size:22px; color:#0F4C5C'><b>Véu</b></p>"
            "<p>Arraste um PDF para esta janela ou clique em <b>Abrir PDF…</b></p>"
            "<p style='font-size:12px'>Todo o processamento acontece neste computador.<br>"
            "Nenhum dado é enviado para a internet.</p>"
        )
        boas_vindas.setObjectName("boasVindas")
        boas_vindas.setAlignment(Qt.AlignCenter)
        container = QWidget()
        lv = QVBoxLayout(container)
        lv.setContentsMargins(80, 80, 80, 80)
        lv.addWidget(boas_vindas)

        self.pilha = QStackedWidget()
        self.pilha.addWidget(container)
        self.pilha.addWidget(pagina_doc)
        self.setCentralWidget(self.pilha)

        self.painel = PainelDeteccoes()
        self.painel.statusSolicitado.connect(self.definir_status)
        self.painel.selecaoAlterada.connect(self._selecao_na_lista)
        self.painel.irPara.connect(self.ir_para_deteccao)
        dock = QDockWidget("Detecções", self)
        dock.setWidget(self.painel)
        dock.setFeatures(QDockWidget.DockWidgetMovable | QDockWidget.DockWidgetFloatable)
        dock.setMinimumWidth(470)
        self.addDockWidget(Qt.RightDockWidgetArea, dock)

        self.lbl_politica = QLabel()
        self.statusBar().addPermanentWidget(self.lbl_politica)
        self._mostrar_politica()
        self.statusBar().showMessage(f"Véu {__version__} — processamento 100% local")

    def _mostrar_politica(self) -> None:
        cadeado = "🔒 " if not self.origem_politica.editavel else ""
        self.lbl_politica.setText(f"{cadeado}Política: {self.politica.nome} ({self.origem_politica.descricao})")
        if self.origem_politica.aviso:
            aviso = self.origem_politica.aviso
            self.origem_politica.aviso = None
            QTimer.singleShot(0, lambda: QMessageBox.warning(self, "Problema na política", aviso))

    def abrir_configuracoes(self) -> None:
        if self._tarefa is not None:
            return
        dlg = DialogoConfiguracoes(self.politica, self.origem_politica, self)
        if dlg.exec() != DialogoConfiguracoes.Accepted:
            return
        self.politica, self.origem_politica = politica_ativa()
        self._mostrar_politica()
        self.statusBar().showMessage("Política salva.", 5000)
        if self.analise is not None:
            r = QMessageBox.question(
                self,
                "Analisar de novo?",
                "A política mudou. Deseja analisar o documento aberto de novo com a nova política?\n\n"
                "As marcações e decisões da revisão atual serão perdidas.",
            )
            if r == QMessageBox.Yes:
                self.abrir(self.analise.caminho, senha=self.analise.senha, confirmar_descarte=False)

    def _atualizar_estado(self) -> None:
        tem_doc = self.analise is not None
        n = self.analise.num_paginas if tem_doc else 0
        for w in (self.b_anonimizar, self.spin_pagina, self.campo_busca, self.b_marcar, self.chk_palavra):
            w.setEnabled(tem_doc)
        for a in (self.a_zoom_mais, self.a_zoom_menos, self.a_zoom_ajustar, self.a_selecionar, self.a_desenhar):
            a.setEnabled(tem_doc)
        self.a_ant.setEnabled(tem_doc and self.pagina_atual > 0)
        self.a_prox.setEnabled(tem_doc and self.pagina_atual < n - 1)
        self.spin_pagina.blockSignals(True)
        self.spin_pagina.setMaximum(max(n, 1))
        self.spin_pagina.setValue(self.pagina_atual + 1)
        self.spin_pagina.blockSignals(False)
        self.lbl_total.setText(f" de {n} ")
        self.lbl_zoom.setText(f"{self.zoom:.0%}")
        self.pilha.setCurrentIndex(1 if tem_doc else 0)
        titulo = "Véu — anonimizador de PDF"
        if tem_doc:
            titulo = f"{os.path.basename(self.analise.caminho)}{' *' if self.alterado else ''} — Véu"
        self.setWindowTitle(titulo)

    # ============================================================ abrir
    def escolher_arquivo(self) -> None:
        caminho, _ = QFileDialog.getOpenFileName(self, "Abrir PDF", "", "Documentos PDF (*.pdf)")
        if caminho:
            self.abrir(caminho)

    def dragEnterEvent(self, event) -> None:
        urls = event.mimeData().urls()
        if urls and urls[0].toLocalFile().lower().endswith(".pdf"):
            event.acceptProposedAction()

    def dropEvent(self, event) -> None:
        self.abrir(event.mimeData().urls()[0].toLocalFile())

    def _pode_descartar(self) -> bool:
        if not self.alterado:
            return True
        r = QMessageBox.question(
            self,
            "Descartar revisão?",
            "A revisão do documento atual ainda não foi salva como PDF anonimizado. Descartá-la?",
            QMessageBox.Discard | QMessageBox.Cancel,
        )
        return r == QMessageBox.Discard

    def abrir(self, caminho: str, senha: str | None = None, confirmar_descarte: bool = True) -> None:
        if self._tarefa is not None or (confirmar_descarte and not self._pode_descartar()):
            return
        while True:
            try:
                doc = abrir_documento(caminho, senha)
                break
            except (SenhaNecessaria, SenhaIncorreta) as e:
                msg = "Este PDF é protegido. Digite a senha:" if isinstance(e, SenhaNecessaria) else "Senha incorreta. Tente novamente:"
                senha, ok = QInputDialog.getText(self, "PDF protegido", msg, QLineEdit.Password)
                if not ok:
                    return
            except Exception as e:
                QMessageBox.critical(self, "Não foi possível abrir", f"Não foi possível abrir o arquivo:\n{e}")
                return

        self._fechar_documento()
        politica = self.politica

        def trabalho(progresso, cancelado):
            return analisar(caminho, senha=senha, politica=politica, progresso=progresso, cancelado=cancelado)

        def concluido(analise: Analise) -> None:
            self.doc = doc
            self.analise = analise
            self.revisao = Revisao(analise)
            self.pagina_atual = 0
            self.ajustar_largura = True
            self.alterado = bool(analise.deteccoes)
            self._mostrar_avisos()
            self._atualizar_estado()
            self._calcular_zoom_ajuste()
            self._atualizar_tudo()
            self.statusBar().showMessage(
                f"{len(analise.deteccoes)} possível(is) dado(s) pessoal(is) encontrado(s) em "
                f"{analise.num_paginas} página(s). Revise antes de anonimizar."
            )

        def falhou(erro) -> None:
            doc.close()
            if not isinstance(erro, InterruptedError):
                QMessageBox.critical(self, "Erro na análise", f"Não foi possível analisar o PDF:\n{erro}")

        self._executar(trabalho, "Analisando o documento…", concluido, falhou)

    def _fechar_documento(self) -> None:
        if self.doc is not None:
            self.doc.close()
        self.doc = None
        self.analise = None
        self.revisao = None
        self._selecao = []
        self.alterado = False
        self.visualizador.limpar()
        self.painel.atualizar([])
        self.banner.hide()
        self._atualizar_estado()

    def _mostrar_avisos(self) -> None:
        if self.analise and self.analise.avisos:
            self.banner.setText("⚠ " + "<br>⚠ ".join(self.analise.avisos))
            self.banner.show()
        else:
            self.banner.hide()

    # ============================================================ tarefas
    def _executar(self, trabalho, titulo: str, concluido, falhou) -> None:
        tarefa = Tarefa(trabalho)
        self._tarefa = tarefa
        self._callbacks = (concluido, falhou)
        dlg = QProgressDialog(titulo, "Cancelar", 0, 100, self)
        dlg.setWindowTitle("Véu")
        dlg.setWindowModality(Qt.WindowModal)
        dlg.setMinimumDuration(300)
        dlg.setAutoClose(False)
        dlg.setAutoReset(False)
        dlg.canceled.connect(tarefa.cancelar)
        self._progresso = dlg
        # Slots da própria janela: o Qt os executa na thread da interface.
        tarefa.sinais.progresso.connect(self._tarefa_progresso)
        tarefa.sinais.concluido.connect(self._tarefa_concluida)
        tarefa.sinais.falhou.connect(self._tarefa_falhou)
        tarefa.iniciar()

    @Slot(int, int, str)
    def _tarefa_progresso(self, i: int, total: int, msg: str) -> None:
        dlg = self._progresso  # referência local: setValue processa eventos e
        if dlg is None:        # a tarefa pode terminar no meio desta chamada
            return
        dlg.setLabelText(msg)
        dlg.setMaximum(max(total, 1))
        dlg.setValue(min(i, total))

    def _tarefa_fim(self):
        self._tarefa = None
        if self._progresso is not None:
            self._progresso.close()
            self._progresso = None
        return self._callbacks

    @Slot(object)
    def _tarefa_concluida(self, resultado) -> None:
        concluido, _ = self._tarefa_fim()
        concluido(resultado)

    @Slot(object)
    def _tarefa_falhou(self, erro) -> None:
        _, falhou = self._tarefa_fim()
        falhou(erro)

    # ============================================================ página
    def _matriz_exibicao(self, page: pymupdf.Page) -> pymupdf.Matrix:
        return page.rotation_matrix * pymupdf.Matrix(self.zoom, self.zoom)

    def _renderizar(self, manter_rolagem: bool = False) -> None:
        if not self.doc or not self.revisao:
            return
        page = self.doc[self.pagina_atual]
        dpr = self.devicePixelRatioF()
        pix = page.get_pixmap(matrix=pymupdf.Matrix(self.zoom * dpr, self.zoom * dpr), alpha=False)
        img = QImage(pix.samples, pix.width, pix.height, pix.stride, QImage.Format_RGB888).copy()
        pm = QPixmap.fromImage(img)
        pm.setDevicePixelRatio(dpr)

        m = self._matriz_exibicao(page)
        caixas = []
        for d in self.revisao.da_pagina(self.pagina_atual):
            rects = []
            for r in d.rects:
                rr = pymupdf.Rect(r) * m
                rr.normalize()
                rects.append(QRectF(rr.x0, rr.y0, rr.width, rr.height))
            tipo = obter_tipo(d.tipo)
            dica = f"{tipo.nome} ({d.status.value}) — {d.trecho}"
            caixas.append(CaixaExibida(d.id, rects, tipo.cor, d.status, dica))
        self.visualizador.exibir(pm, caixas, manter_rolagem)
        self.visualizador.selecionar(self._selecao, centralizar=False)

    def _atualizar_tudo(self, manter_rolagem: bool = False) -> None:
        self._renderizar(manter_rolagem)
        if self.revisao:
            self.painel.atualizar(self.revisao.deteccoes)
            self.painel.selecionar(self._selecao, rolar=False)
        self._atualizar_estado()

    def ir_para_pagina(self, n: int) -> None:
        if not self.analise or not (0 <= n < self.analise.num_paginas) or n == self.pagina_atual:
            self._atualizar_estado()
            return
        self.pagina_atual = n
        self._renderizar()
        self._atualizar_estado()

    def ir_para_deteccao(self, id_: str) -> None:
        if not self.revisao:
            return
        d = self.revisao.por_id(id_)
        if d is None:
            return
        self._selecao = [id_]
        if d.pagina != self.pagina_atual:
            self.pagina_atual = d.pagina
            self._renderizar()
            self._atualizar_estado()
        self.visualizador.selecionar([id_], centralizar=True)

    # ============================================================ zoom
    def _calcular_zoom_ajuste(self) -> None:
        if not self.doc:
            return
        largura = self.doc[self.pagina_atual].rect.width
        disponivel = self.visualizador.viewport().width() - 40
        self.zoom = max(ZOOM_MIN, min(ZOOM_MAX, disponivel / largura))

    def zoom_ajustar(self) -> None:
        self.ajustar_largura = True
        self._calcular_zoom_ajuste()
        self._renderizar()
        self._atualizar_estado()

    def mudar_zoom(self, passo: int) -> None:
        if not self.doc:
            return
        self.ajustar_largura = False
        fator = 1.2 if passo > 0 else 1 / 1.2
        self.zoom = max(ZOOM_MIN, min(ZOOM_MAX, self.zoom * fator))
        self._renderizar(manter_rolagem=True)
        self._atualizar_estado()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if self.ajustar_largura and self.doc:
            self._calcular_zoom_ajuste()
            self._renderizar(manter_rolagem=True)
            self._atualizar_estado()

    # ============================================================ revisão
    def _selecao_na_pagina(self, ids: list[str]) -> None:
        self._selecao = ids
        self.painel.selecionar(ids)

    def _selecao_na_lista(self, ids: list[str]) -> None:
        self._selecao = ids
        if len(ids) == 1:
            self.ir_para_deteccao(ids[0])
        else:
            self.visualizador.selecionar(ids, centralizar=False)

    def definir_status(self, ids: list[str], status: Status) -> None:
        if not self.revisao or not ids:
            return
        self.revisao.definir_status(ids, status)
        self.alterado = True
        self._atualizar_tudo(manter_rolagem=True)

    def excluir(self, ids: list[str]) -> None:
        if not self.revisao or not ids:
            return
        self.revisao.excluir(ids)
        self._selecao = [i for i in self._selecao if self.revisao.por_id(i)]
        self.alterado = True
        self._atualizar_tudo(manter_rolagem=True)

    def _caixa_desenhada(self, rect_cena: QRectF) -> None:
        if not self.doc or not self.revisao:
            return
        page = self.doc[self.pagina_atual]
        inversa = ~self._matriz_exibicao(page)
        r = pymupdf.Rect(rect_cena.left(), rect_cena.top(), rect_cena.right(), rect_cena.bottom()) * inversa
        r.normalize()
        det = self.revisao.adicionar_manual(self.pagina_atual, (r.x0, r.y0, r.x1, r.y1))
        self._selecao = [det.id]
        self.alterado = True
        self._atualizar_tudo(manter_rolagem=True)
        self.statusBar().showMessage("Área marcada manualmente. Ela será tarjada.", 4000)

    def _menu_caixa(self, ids: list[str], pos: QPoint) -> None:
        if not self.revisao:
            return
        menu = QMenu(self)
        menu.addAction("Aceitar (A)", lambda: self.definir_status(ids, Status.ACEITA))
        menu.addAction("Rejeitar — não é dado pessoal (R)", lambda: self.definir_status(ids, Status.REJEITADA))
        manuais = [i for i in ids if (d := self.revisao.por_id(i)) and d.origem != Origem.AUTOMATICA]
        if manuais:
            menu.addAction("Excluir marcação (Del)", lambda: self.excluir(manuais))
        dets = [self.revisao.por_id(i) for i in ids]
        if len(dets) == 1 and dets[0] and dets[0].trecho and dets[0].origem != Origem.MANUAL:
            trecho = dets[0].trecho
            menu.addSeparator()
            menu.addAction(f"Marcar todas as ocorrências de “{trecho[:30]}”", lambda: self.marcar_termo(trecho))
        menu.exec(pos)

    def marcar_termo(self, termo: str | None = None) -> None:
        if not self.revisao:
            return
        termo = termo if isinstance(termo, str) else self.campo_busca.text()
        termo = termo.strip()
        if not termo:
            return
        novas = self.revisao.marcar_termo(termo, self.chk_palavra.isChecked())
        if novas:
            self.alterado = True
            paginas = sorted({d.pagina + 1 for d in novas})
            self.statusBar().showMessage(
                f"{len(novas)} ocorrência(s) de “{termo}” marcada(s) nas páginas {', '.join(map(str, paginas[:20]))}.", 6000
            )
        else:
            self.statusBar().showMessage(f"Nenhuma ocorrência nova de “{termo}”.", 5000)
        self._atualizar_tudo(manter_rolagem=True)

    # ============================================================ anonimizar
    def anonimizar(self) -> None:
        if not self.revisao or not self.analise or self._tarefa is not None:
            return
        pendentes = self.revisao.pendentes()
        if pendentes:
            caixa = QMessageBox(self)
            caixa.setIcon(QMessageBox.Warning)
            caixa.setWindowTitle("Revisão incompleta")
            caixa.setText(f"Ainda há {len(pendentes)} detecção(ões) pendente(s) de revisão.")
            caixa.setInformativeText("Detecções pendentes precisam ser aceitas ou rejeitadas antes de anonimizar.")
            aceitar = caixa.addButton("Aceitar as pendentes e continuar", QMessageBox.AcceptRole)
            caixa.addButton("Voltar à revisão", QMessageBox.RejectRole)
            caixa.exec()
            if caixa.clickedButton() is not aceitar:
                filtro = self.painel.combo_status.findData(Status.PENDENTE)
                self.painel.combo_status.setCurrentIndex(filtro)
                return
            self.revisao.aceitar_pendentes()
            self._atualizar_tudo(manter_rolagem=True)

        tarjar = self.revisao.a_tarjar()
        if not tarjar:
            r = QMessageBox.question(
                self,
                "Nada a tarjar",
                "Nenhuma área está marcada para tarja. Deseja gerar mesmo assim uma cópia apenas com a "
                "limpeza de metadados, comentários e anexos?",
            )
            if r != QMessageBox.Yes:
                return
        contagem = Counter(d.tipo for d in tarjar)
        rejeitadas = sum(1 for d in self.revisao.deteccoes if d.status == Status.REJEITADA)
        sem_texto = sum(1 for p in self.analise.paginas if p.sem_texto)
        dlg = DialogoConfirmacao(
            contagem, rejeitadas, self.revisao.adicionadas_manualmente, sem_texto, self, padrao=self.politica.tarja
        )
        if dlg.exec() != DialogoConfirmacao.Accepted:
            return
        opcoes = dlg.opcoes()

        sugestao = caminho_saida_padrao(self.analise.caminho)
        saida, _ = QFileDialog.getSaveFileName(self, "Salvar PDF anonimizado", sugestao, "Documentos PDF (*.pdf)")
        if not saida:
            return
        if not saida.lower().endswith(".pdf"):
            saida += ".pdf"
        if os.path.normcase(os.path.abspath(saida)) == os.path.normcase(os.path.abspath(self.analise.caminho)):
            QMessageBox.warning(self, "Escolha outro nome", "O PDF original nunca é sobrescrito. Escolha outro nome de arquivo.")
            return

        analise = self.analise

        def trabalho(progresso, cancelado):
            return anonimizar(analise, saida, opcoes, progresso)

        revisao = self.revisao
        auditar = self.politica.auditoria.ativo

        def concluido(resultado) -> None:
            self.alterado = False
            self._atualizar_estado()
            if auditar:
                try:
                    registrar(criar_recibo(analise, resultado, revisao, modo="interface"))
                    resultado.recibo_registrado = True
                except OSError as e:
                    QMessageBox.warning(self, "Auditoria", f"Não foi possível gravar o recibo de auditoria:\n{e}")
            ok = resultado.verificacao is None or resultado.verificacao.ok
            self.statusBar().showMessage(
                f"PDF anonimizado salvo em {saida}" + ("" if ok else " — ATENÇÃO: verificação encontrou problemas")
            )
            DialogoResultado(resultado, self).exec()

        def falhou(erro) -> None:
            if isinstance(erro, ArquivoOriginalProtegido):
                QMessageBox.warning(self, "Escolha outro nome", str(erro))
            else:
                QMessageBox.critical(self, "Erro ao anonimizar", f"Não foi possível gerar o PDF anonimizado:\n{erro}")

        self._executar(trabalho, "Aplicando tarjas…", concluido, falhou)

    # ============================================================ fechar
    def closeEvent(self, event) -> None:
        if self._tarefa is not None:
            event.ignore()
            return
        if not self._pode_descartar():
            event.ignore()
            return
        if self.doc is not None:
            self.doc.close()
        event.accept()
