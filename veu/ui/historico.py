"""Janela de histórico de auditoria (recibos) com exportação para CSV."""

from __future__ import annotations

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QColor, QDesktopServices
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QHeaderView,
    QLabel,
    QMessageBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from veu.core.audit import exportar_csv, ler_historico, pasta_auditoria
from veu.core.tipos import obter_tipo
from veu.ui.tema import ERRO, SUCESSO

COLUNAS = ["Data/hora", "Usuário", "Modo", "Arquivo", "Tarjas", "Manuais (+/−)", "Verificação"]


class DialogoHistorico(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Histórico de anonimizações")
        self.resize(980, 520)
        self.recibos = list(reversed(ler_historico()))  # mais recentes primeiro

        info = QLabel(
            f"{len(self.recibos)} recibo(s) em {pasta_auditoria()}. "
            "Os recibos nunca contêm os dados tarjados; os arquivos são identificados pelo hash SHA-256."
        )
        info.setWordWrap(True)

        self.tabela = QTableWidget(len(self.recibos), len(COLUNAS))
        self.tabela.setHorizontalHeaderLabels(COLUNAS)
        self.tabela.verticalHeader().setVisible(False)
        self.tabela.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.tabela.setSelectionBehavior(QAbstractItemView.SelectRows)
        cab = self.tabela.horizontalHeader()
        cab.setSectionResizeMode(QHeaderView.ResizeToContents)
        cab.setSectionResizeMode(3, QHeaderView.Stretch)
        for i, r in enumerate(self.recibos):
            arquivo = r.arquivo_original or f"SHA-256 {r.sha256_original[:16]}…"
            tarjas = ", ".join(f"{obter_tipo(t).nome} {n}" for t, n in r.tarjas_por_tipo.items())
            if r.verificacao_ok is None:
                verif, cor = "não executada", None
            elif r.verificacao_ok:
                verif, cor = "aprovada", SUCESSO
            else:
                verif, cor = f"{r.vazamentos} problema(s)", ERRO
            valores = [
                r.data_hora.replace("T", " ")[:19],
                r.usuario,
                r.modo,
                arquivo,
                f"{r.total_tarjas}",
                f"+{r.adicionadas_manualmente} / −{r.removidas_manualmente}",
                verif,
            ]
            for j, v in enumerate(valores):
                item = QTableWidgetItem(v)
                if j == 4:
                    item.setToolTip(tarjas)
                if j == 3:
                    item.setToolTip(f"Original: {r.sha256_original}\nResultado: {r.sha256_resultado}")
                if j == 6 and cor:
                    item.setForeground(QColor(cor))
                self.tabela.setItem(i, j, item)

        botoes = QDialogButtonBox()
        b_csv = botoes.addButton("Exportar CSV…", QDialogButtonBox.ActionRole)
        b_pasta = botoes.addButton("Abrir pasta", QDialogButtonBox.ActionRole)
        botoes.addButton("Fechar", QDialogButtonBox.RejectRole)
        b_csv.clicked.connect(self._exportar)
        b_csv.setEnabled(bool(self.recibos))
        b_pasta.clicked.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(pasta_auditoria()))))
        botoes.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(info)
        layout.addWidget(self.tabela, 1)
        layout.addWidget(botoes)

    def _exportar(self) -> None:
        caminho, _ = QFileDialog.getSaveFileName(self, "Exportar histórico", "historico_veu.csv", "CSV (*.csv)")
        if caminho:
            exportar_csv(list(reversed(self.recibos)), caminho)
            QMessageBox.information(self, "Histórico exportado", f"{len(self.recibos)} recibo(s) exportado(s) para:\n{caminho}")
