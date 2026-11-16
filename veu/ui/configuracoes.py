"""Tela de configurações: edição, importação e exportação da política."""

from __future__ import annotations

import re
from html import escape

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QColorDialog,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from veu.core.models import EstiloTarja, Vetores
from veu.core.policy import (
    OrigemPolitica,
    Politica,
    PoliticaInvalida,
    carregar_politica,
    politica_padrao,
    salvar_politica,
    salvar_politica_usuario,
)
from veu.core.policy.modelo import politica_de_dict
from veu.core.tipos import tipos_detectaveis


def _amostra(cor: str) -> QPixmap:
    pm = QPixmap(14, 14)
    pm.fill(QColor(cor))
    return pm


def _ajuda(texto: str) -> QLabel:
    lbl = QLabel(texto)
    lbl.setWordWrap(True)
    lbl.setStyleSheet("color:#5A6670;")
    return lbl


class DialogoConfiguracoes(QDialog):
    def __init__(self, politica: Politica, origem: OrigemPolitica, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Configurações — política de anonimização")
        self.resize(900, 640)
        self.origem = origem
        self.politica: Politica = politica
        self._tipos_padrao = [t for t in tipos_detectaveis() if not t.personalizado]

        self.abas = QTabWidget()
        self.abas.addTab(self._aba_tipos(), "Tipos de dado")
        self.abas.addTab(self._aba_personalizados(), "Tipos personalizados")
        self.abas.addTab(self._aba_lista("sempre"), "Sempre tarjar")
        self.abas.addTab(self._aba_lista("excecoes"), "Exceções")
        self.abas.addTab(self._aba_tarja(), "Tarja")
        self.abas.addTab(self._aba_ocr_auditoria(), "OCR e auditoria")

        layout = QVBoxLayout(self)
        if not origem.editavel:
            aviso = QLabel("🔒 Esta política foi definida pelo TI da organização e está bloqueada. Você pode consultá-la e exportá-la, mas não alterá-la.")
            aviso.setObjectName("aviso")
            aviso.setWordWrap(True)
            layout.addWidget(aviso)
        linha_nome = QHBoxLayout()
        linha_nome.addWidget(QLabel("Nome da política:"))
        self.campo_nome = QLineEdit()
        linha_nome.addWidget(self.campo_nome, 1)
        layout.addLayout(linha_nome)
        layout.addWidget(self.abas, 1)
        local = str(origem.caminho) if origem.caminho else "nenhum arquivo (padrão embutido)"
        layout.addWidget(_ajuda(f"Política em uso: {origem.descricao} — {local}"))

        botoes = QDialogButtonBox()
        b_importar = botoes.addButton("Importar…", QDialogButtonBox.ActionRole)
        b_exportar = botoes.addButton("Exportar…", QDialogButtonBox.ActionRole)
        b_padrao = botoes.addButton("Restaurar padrão", QDialogButtonBox.ResetRole)
        self.b_salvar = botoes.addButton("Salvar", QDialogButtonBox.AcceptRole)
        self.b_salvar.setObjectName("primario")
        botoes.addButton("Cancelar", QDialogButtonBox.RejectRole)
        b_importar.clicked.connect(self._importar)
        b_exportar.clicked.connect(self._exportar)
        b_padrao.clicked.connect(lambda: self._preencher(politica_padrao()))
        botoes.accepted.connect(self._salvar)
        botoes.rejected.connect(self.reject)
        layout.addWidget(botoes)

        self._preencher(politica)
        if not origem.editavel:
            for w in (self.campo_nome, self.tabela_tipos, self.tabela_pers, self.texto_sempre, self.texto_excecoes,
                      self.combo_estilo, self.combo_vetores, self.chk_ner, self.b_add, self.b_rem,
                      self.chk_ocr, self.spin_dpi, self.chk_auditoria, self.chk_nomes):
                w.setEnabled(False)
            b_importar.setEnabled(False)
            b_padrao.setEnabled(False)
            self.b_salvar.setEnabled(False)

    # ================================================================ abas
    def _aba_tipos(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.addWidget(_ajuda(
            "Marque os tipos de dado que devem ser procurados. A confiança mínima descarta detecções "
            "mais incertas (0 = mostrar tudo para revisão; 1 = só as certeiras)."
        ))
        self.tabela_tipos = QTableWidget(len(self._tipos_padrao), 4)
        self.tabela_tipos.setHorizontalHeaderLabels(["Ativo", "Tipo", "Como detecta", "Confiança mínima"])
        self.tabela_tipos.verticalHeader().setVisible(False)
        self.tabela_tipos.setSelectionMode(QAbstractItemView.NoSelection)
        cab = self.tabela_tipos.horizontalHeader()
        cab.setSectionResizeMode(QHeaderView.ResizeToContents)
        cab.setSectionResizeMode(2, QHeaderView.Stretch)
        for linha, t in enumerate(self._tipos_padrao):
            ativo = QTableWidgetItem()
            ativo.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
            self.tabela_tipos.setItem(linha, 0, ativo)
            nome = QTableWidgetItem(_amostra(t.cor), f"{t.nome}  ")
            nome.setFlags(Qt.ItemIsEnabled)
            nome.setToolTip(f"Grupo: {t.grupo} · rótulo da tarja: {t.rotulo}")
            self.tabela_tipos.setItem(linha, 1, nome)
            desc = QTableWidgetItem(t.descricao)
            desc.setFlags(Qt.ItemIsEnabled)
            self.tabela_tipos.setItem(linha, 2, desc)
            spin = QDoubleSpinBox()
            spin.setRange(0.0, 1.0)
            spin.setSingleStep(0.05)
            spin.setDecimals(2)
            self.tabela_tipos.setCellWidget(linha, 3, spin)
        lay.addWidget(self.tabela_tipos, 1)
        self.chk_ner = QCheckBox("Usar o modelo de linguagem local para reconhecer nomes (mais preciso, um pouco mais lento)")
        lay.addWidget(self.chk_ner)
        return w

    def _aba_personalizados(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.addWidget(_ajuda(
            "Crie tipos próprios a partir de uma expressão regular. Exemplo: nome “Matrícula funcionário”, "
            "regex <code>MAT-\\d{6}</code>. Clique na cor para trocá-la."
        ))
        self.tabela_pers = QTableWidget(0, 6)
        self.tabela_pers.setHorizontalHeaderLabels(["Ativo", "Nome", "Expressão regular", "Rótulo da tarja", "Cor", "Ignorar maiúsc."])
        self.tabela_pers.verticalHeader().setVisible(False)
        cab = self.tabela_pers.horizontalHeader()
        cab.setSectionResizeMode(QHeaderView.ResizeToContents)
        cab.setSectionResizeMode(1, QHeaderView.Stretch)
        cab.setSectionResizeMode(2, QHeaderView.Stretch)
        self.tabela_pers.cellClicked.connect(self._clique_pers)
        self.tabela_pers.itemChanged.connect(lambda *_: self._testar_regex())
        self.tabela_pers.currentCellChanged.connect(lambda *_: self._testar_regex())
        lay.addWidget(self.tabela_pers, 1)

        botoes = QHBoxLayout()
        self.b_add = QPushButton("Adicionar tipo")
        self.b_rem = QPushButton("Remover selecionado")
        self.b_add.clicked.connect(lambda: self._adicionar_pers("Novo tipo", r"", "", "#6C757D", True, False))
        self.b_rem.clicked.connect(self._remover_pers)
        botoes.addWidget(self.b_add)
        botoes.addWidget(self.b_rem)
        botoes.addStretch(1)
        lay.addLayout(botoes)

        form = QFormLayout()
        self.teste_texto = QLineEdit("Funcionário MAT-123456 entregou o relatório.")
        self.teste_texto.textChanged.connect(self._testar_regex)
        self.teste_resultado = QLabel()
        self.teste_resultado.setTextFormat(Qt.RichText)
        self.teste_resultado.setWordWrap(True)
        form.addRow("Testar a regra selecionada em:", self.teste_texto)
        form.addRow("Resultado:", self.teste_resultado)
        lay.addLayout(form)
        return w

    def _aba_lista(self, qual: str) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        editor = QPlainTextEdit()
        if qual == "sempre":
            lay.addWidget(_ajuda(
                "Um termo por linha. Todas as ocorrências serão marcadas para tarja (já aceitas), "
                "ignorando maiúsculas e acentos. Use para nomes de clientes, projetos, codinomes etc."
            ))
            editor.setPlaceholderText("Projeto Águia\nCliente ACME")
            self.texto_sempre = editor
        else:
            lay.addWidget(_ajuda(
                "Um termo por linha. Nada que esteja inteiramente dentro destes termos será marcado "
                "automaticamente (ex.: o nome da própria empresa ou de um hospital com nome de pessoa). "
                "Marcações manuais e a lista “Sempre tarjar” não são afetadas."
            ))
            editor.setPlaceholderText("Hospital Maria Helena\nClínica Exemplo Ltda")
            self.texto_excecoes = editor
        lay.addWidget(editor, 1)
        return w

    def _aba_tarja(self) -> QWidget:
        w = QWidget()
        form = QFormLayout(w)
        self.combo_estilo = QComboBox()
        self.combo_estilo.addItem("Retângulo preto liso", EstiloTarja.PRETA)
        self.combo_estilo.addItem("Retângulo com o tipo do dado ([CPF], [NOME]…)", EstiloTarja.ROTULO)
        self.combo_estilo.addItem("Tipo do dado, com cada pessoa numerada ([P1], [P2]…)", EstiloTarja.PESSOAS)
        self.combo_vetores = QComboBox()
        self.combo_vetores.addItem("Remover desenhos totalmente cobertos pela tarja", Vetores.COBERTOS)
        self.combo_vetores.addItem("Remover qualquer desenho que toque a tarja (pode apagar linhas de tabelas)", Vetores.TOCADOS)
        form.addRow("Estilo padrão da tarja:", self.combo_estilo)
        form.addRow("Desenhos vetoriais:", self.combo_vetores)
        form.addRow(_ajuda("Estes são os valores iniciais; eles podem ser trocados a cada anonimização."))
        return w

    def _aba_ocr_auditoria(self) -> QWidget:
        w = QWidget()
        form = QFormLayout(w)
        self.chk_ocr = QCheckBox("Reconhecer texto (OCR) em páginas escaneadas")
        self.spin_dpi = QSpinBox()
        self.spin_dpi.setRange(150, 600)
        self.spin_dpi.setSingleStep(50)
        self.spin_dpi.setSuffix(" dpi")
        self.chk_auditoria = QCheckBox("Registrar um recibo de auditoria a cada anonimização")
        self.chk_nomes = QCheckBox("Incluir o nome e a pasta dos arquivos no recibo")
        form.addRow(self.chk_ocr)
        form.addRow("Resolução do OCR:", self.spin_dpi)
        form.addRow(_ajuda("Resolução maior reconhece letras pequenas, mas é mais lenta. 300 dpi atende a maioria dos casos."))
        form.addRow(self.chk_auditoria)
        form.addRow(self.chk_nomes)
        form.addRow(_ajuda(
            "Os recibos nunca contêm os dados tarjados. Nomes de arquivo podem conter dados pessoais "
            "(ex.: “laudo_maria_silva.pdf”); por isso, por padrão, os arquivos são identificados só pelo hash SHA-256."
        ))
        return w

    # ======================================================== preencher / ler
    def _preencher(self, p: Politica) -> None:
        self.campo_nome.setText(p.nome)
        for linha, t in enumerate(self._tipos_padrao):
            cfg = p.tipos.get(t.id)
            self.tabela_tipos.item(linha, 0).setCheckState(Qt.Checked if (cfg is None or cfg.ativo) else Qt.Unchecked)
            self.tabela_tipos.cellWidget(linha, 3).setValue(cfg.confianca_minima if cfg else 0.5)
        self.chk_ner.setChecked(p.usar_ner)
        self.tabela_pers.setRowCount(0)
        for t in p.tipos_personalizados:
            self._adicionar_pers(t.nome, t.regex, t.rotulo, t.cor, t.ativo and p.tipo_ativo(t.id), t.ignorar_maiusculas)
        self.texto_sempre.setPlainText("\n".join(p.sempre_tarjar))
        self.texto_excecoes.setPlainText("\n".join(p.excecoes))
        self.combo_estilo.setCurrentIndex(self.combo_estilo.findData(p.tarja.estilo))
        self.combo_vetores.setCurrentIndex(self.combo_vetores.findData(p.tarja.vetores))
        self.chk_ocr.setChecked(p.ocr.ativo)
        self.spin_dpi.setValue(p.ocr.dpi)
        self.chk_auditoria.setChecked(p.auditoria.ativo)
        self.chk_nomes.setChecked(p.auditoria.registrar_nome_arquivo)
        self._bloqueada = p.bloqueada
        self._testar_regex()

    def _adicionar_pers(self, nome, regex, rotulo, cor, ativo, ignorar) -> None:
        self.tabela_pers.blockSignals(True)
        linha = self.tabela_pers.rowCount()
        self.tabela_pers.insertRow(linha)
        chk = QTableWidgetItem()
        chk.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled | Qt.ItemIsSelectable)
        chk.setCheckState(Qt.Checked if ativo else Qt.Unchecked)
        self.tabela_pers.setItem(linha, 0, chk)
        self.tabela_pers.setItem(linha, 1, QTableWidgetItem(nome))
        self.tabela_pers.setItem(linha, 2, QTableWidgetItem(regex))
        item_rot = QTableWidgetItem(rotulo)
        item_rot.setToolTip("Deixe vazio para usar [NOME DO TIPO]")
        self.tabela_pers.setItem(linha, 3, item_rot)
        item_cor = QTableWidgetItem(_amostra(cor), cor)
        item_cor.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
        self.tabela_pers.setItem(linha, 4, item_cor)
        ign = QTableWidgetItem()
        ign.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled | Qt.ItemIsSelectable)
        ign.setCheckState(Qt.Checked if ignorar else Qt.Unchecked)
        self.tabela_pers.setItem(linha, 5, ign)
        self.tabela_pers.blockSignals(False)
        self.tabela_pers.setCurrentCell(linha, 1)

    def _remover_pers(self) -> None:
        linha = self.tabela_pers.currentRow()
        if linha >= 0:
            self.tabela_pers.removeRow(linha)
            self._testar_regex()

    def _clique_pers(self, linha: int, coluna: int) -> None:
        if coluna != 4 or not self.origem.editavel:
            return
        item = self.tabela_pers.item(linha, 4)
        cor = QColorDialog.getColor(QColor(item.text()), self, "Cor do tipo")
        if cor.isValid():
            item.setText(cor.name().upper())
            item.setIcon(_amostra(cor.name()))

    def _testar_regex(self) -> None:
        linha = self.tabela_pers.currentRow()
        if linha < 0 or self.tabela_pers.item(linha, 2) is None:
            self.teste_resultado.setText("<i>Selecione uma regra.</i>")
            return
        padrao = self.tabela_pers.item(linha, 2).text()
        flags = re.IGNORECASE if self.tabela_pers.item(linha, 5).checkState() == Qt.Checked else 0
        texto = self.teste_texto.text()
        if not padrao:
            self.teste_resultado.setText("<i>Digite a expressão regular.</i>")
            return
        try:
            r = re.compile(padrao, flags)
        except re.error as e:
            self.teste_resultado.setText(f"<span style='color:#C62828'>Expressão inválida: {escape(str(e))}</span>")
            return
        if r.fullmatch(""):
            self.teste_resultado.setText("<span style='color:#C62828'>A expressão aceita texto vazio.</span>")
            return
        partes, ultimo, n = [], 0, 0
        for m in r.finditer(texto):
            if m.end() == m.start():
                continue
            partes.append(escape(texto[ultimo:m.start()]))
            partes.append(f"<span style='background:#FFD54F'><b>{escape(m.group(0))}</b></span>")
            ultimo = m.end()
            n += 1
        partes.append(escape(texto[ultimo:]))
        self.teste_resultado.setText(f"{n} ocorrência(s): " + "".join(partes))

    def _ler(self) -> Politica:
        """Monta e valida a política a partir da tela. Lança PoliticaInvalida."""
        tipos = {}
        for linha, t in enumerate(self._tipos_padrao):
            tipos[t.id] = {
                "ativo": self.tabela_tipos.item(linha, 0).checkState() == Qt.Checked,
                "confianca_minima": round(self.tabela_tipos.cellWidget(linha, 3).value(), 2),
            }
        pers = []
        for linha in range(self.tabela_pers.rowCount()):
            pers.append({
                "nome": self.tabela_pers.item(linha, 1).text().strip(),
                "regex": self.tabela_pers.item(linha, 2).text(),
                "rotulo": self.tabela_pers.item(linha, 3).text().strip(),
                "cor": self.tabela_pers.item(linha, 4).text(),
                "ativo": self.tabela_pers.item(linha, 0).checkState() == Qt.Checked,
                "ignorar_maiusculas": self.tabela_pers.item(linha, 5).checkState() == Qt.Checked,
            })
        dados = {
            "nome": self.campo_nome.text().strip() or "Política sem nome",
            "bloqueada": self._bloqueada,
            "usar_ner": self.chk_ner.isChecked(),
            "tipos": tipos,
            "tipos_personalizados": pers,
            "sempre_tarjar": self.texto_sempre.toPlainText().splitlines(),
            "excecoes": self.texto_excecoes.toPlainText().splitlines(),
            "ocr": {"ativo": self.chk_ocr.isChecked(), "dpi": self.spin_dpi.value()},
            "auditoria": {"ativo": self.chk_auditoria.isChecked(), "registrar_nome_arquivo": self.chk_nomes.isChecked()},
            "tarja": {
                "estilo": EstiloTarja(self.combo_estilo.currentData()).value,
                "vetores": Vetores(self.combo_vetores.currentData()).value,
            },
        }
        return politica_de_dict(dados)

    # ============================================================ ações
    def _salvar(self) -> None:
        try:
            politica = self._ler()
        except PoliticaInvalida as e:
            QMessageBox.warning(self, "Política com erros", str(e))
            return
        try:
            salvar_politica_usuario(politica, self.origem)
        except OSError as e:
            QMessageBox.critical(self, "Não foi possível salvar", str(e))
            return
        self.politica = politica
        self.accept()

    def _importar(self) -> None:
        caminho, _ = QFileDialog.getOpenFileName(self, "Importar política", "", "Política (*.yaml *.yml *.json)")
        if not caminho:
            return
        try:
            politica = carregar_politica(caminho)
        except PoliticaInvalida as e:
            QMessageBox.warning(self, "Política inválida", str(e))
            return
        self._preencher(politica)
        QMessageBox.information(self, "Política importada", f"“{politica.nome}” foi carregada. Clique em Salvar para passar a usá-la.")

    def _exportar(self) -> None:
        try:
            politica = self._ler() if self.origem.editavel else self.politica
        except PoliticaInvalida as e:
            QMessageBox.warning(self, "Política com erros", str(e))
            return
        caminho, _ = QFileDialog.getSaveFileName(self, "Exportar política", "politica.yaml", "YAML (*.yaml);;JSON (*.json)")
        if caminho:
            salvar_politica(politica, caminho)
            QMessageBox.information(
                self,
                "Política exportada",
                f"Salva em {caminho}.\n\nPara distribuir a todos, o TI pode copiá-la para o arquivo de política da "
                "organização (com “bloqueada: true” para impedir alterações).",
            )
