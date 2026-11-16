"""Lista lateral de detecções com filtros e ações em lote."""

from __future__ import annotations

from PySide6.QtCore import QAbstractTableModel, QItemSelectionModel, QModelIndex, QPoint, QSortFilterProxyModel, Qt, Signal
from PySide6.QtGui import QColor, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from veu.core.models import Deteccao, Origem, Status
from veu.core.tipos import obter_tipo

COLUNAS = ["Tipo", "Pág.", "Trecho", "Conf.", "Status", "Pessoa"]
NOMES_STATUS = {Status.PENDENTE: "Pendente", Status.ACEITA: "Aceita", Status.REJEITADA: "Rejeitada"}
CORES_STATUS = {Status.PENDENTE: "#B26A00", Status.ACEITA: "#2E7D32", Status.REJEITADA: "#8A949A"}
NOMES_ORIGEM = {Origem.AUTOMATICA: "automática", Origem.MANUAL: "manual", Origem.BUSCA: "busca"}


def _amostra_cor(cor: str) -> QPixmap:
    pm = QPixmap(12, 12)
    pm.fill(QColor(cor))
    return pm


class ModeloDeteccoes(QAbstractTableModel):
    def __init__(self):
        super().__init__()
        self._dets: list[Deteccao] = []
        self._icones: dict[str, QPixmap] = {}
        self._pessoas: dict[str, str] = {}

    def definir(self, deteccoes: list[Deteccao], pessoas: dict[str, str] | None = None) -> None:
        self.beginResetModel()
        self._pessoas = pessoas or {}
        self._dets = sorted(deteccoes, key=lambda d: (d.pagina, d.rects[0][1] if d.rects else 0, d.rects[0][0] if d.rects else 0))
        self.endResetModel()

    def deteccao(self, linha: int) -> Deteccao:
        return self._dets[linha]

    def rowCount(self, parent=QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self._dets)

    def columnCount(self, parent=QModelIndex()) -> int:
        return len(COLUNAS)

    def headerData(self, secao, orientacao, papel=Qt.DisplayRole):
        if orientacao == Qt.Horizontal and papel == Qt.DisplayRole:
            return COLUNAS[secao]
        return None

    def data(self, index: QModelIndex, papel=Qt.DisplayRole):
        d = self._dets[index.row()]
        col = index.column()
        if papel == Qt.DisplayRole:
            if col == 0:
                return obter_tipo(d.tipo).nome
            if col == 1:
                return d.pagina + 1
            if col == 2:
                return d.trecho
            if col == 3:
                return f"{d.confianca:.0%}"
            if col == 4:
                return NOMES_STATUS[d.status]
            if col == 5:
                return self._pessoas.get(d.id, "")
        if papel == Qt.DecorationRole and col == 0:
            cor = obter_tipo(d.tipo).cor
            if cor not in self._icones:
                self._icones[cor] = _amostra_cor(cor)
            return self._icones[cor]
        if papel == Qt.ForegroundRole:
            if col == 4:
                return QColor(CORES_STATUS[d.status])
            if d.status == Status.REJEITADA:
                return QColor("#8A949A")
        if papel == Qt.ToolTipRole:
            return f"{obter_tipo(d.tipo).nome} — página {d.pagina + 1}\n{d.trecho}\nOrigem: {NOMES_ORIGEM[d.origem]}"
        if papel == Qt.UserRole:
            return d.id
        if papel == Qt.TextAlignmentRole and col in (1, 3, 5):
            return int(Qt.AlignCenter)
        return None


class FiltroDeteccoes(QSortFilterProxyModel):
    def __init__(self):
        super().__init__()
        self.tipo: str | None = None
        self.status: Status | None = None

    def filterAcceptsRow(self, linha, pai) -> bool:
        d = self.sourceModel().deteccao(linha)
        return (self.tipo is None or d.tipo == self.tipo) and (self.status is None or d.status == self.status)


class PainelDeteccoes(QWidget):
    statusSolicitado = Signal(list, object)  # ids, Status
    selecaoAlterada = Signal(list)  # ids
    irPara = Signal(str)  # id
    menuSolicitado = Signal(list, QPoint)  # ids, posição global

    def __init__(self, parent=None):
        super().__init__(parent)
        self.modelo = ModeloDeteccoes()
        self.filtro = FiltroDeteccoes()
        self.filtro.setSourceModel(self.modelo)
        self._sincronizando = False

        self.resumo = QLabel("Nenhum documento aberto.")
        self.resumo.setWordWrap(True)

        self.combo_tipo = QComboBox()
        self.combo_status = QComboBox()
        self.combo_status.addItem("Todos os status", None)
        for st in (Status.PENDENTE, Status.ACEITA, Status.REJEITADA):
            self.combo_status.addItem(NOMES_STATUS[st] + "s", st)
        self.combo_tipo.currentIndexChanged.connect(self._filtro_mudou)
        self.combo_status.currentIndexChanged.connect(self._filtro_mudou)

        self.tabela = QTableView()
        self.tabela.setModel(self.filtro)
        self.tabela.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tabela.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.tabela.setSortingEnabled(True)
        self.tabela.sortByColumn(1, Qt.AscendingOrder)  # por página
        self.tabela.verticalHeader().setVisible(False)
        self.tabela.setWordWrap(False)
        cab = self.tabela.horizontalHeader()
        cab.setSectionResizeMode(QHeaderView.ResizeToContents)
        cab.setSectionResizeMode(0, QHeaderView.Interactive)
        cab.setSectionResizeMode(2, QHeaderView.Stretch)
        self.tabela.setColumnWidth(0, 125)
        self.tabela.setTextElideMode(Qt.ElideRight)
        self.tabela.selectionModel().selectionChanged.connect(self._selecao_mudou)
        self.tabela.doubleClicked.connect(lambda idx: self.irPara.emit(idx.data(Qt.UserRole)))
        self.tabela.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tabela.customContextMenuRequested.connect(self._menu)

        b_aceitar = QPushButton("Aceitar selecionadas")
        b_rejeitar = QPushButton("Rejeitar selecionadas")
        b_aceitar_todas = QPushButton("Aceitar todas da lista")
        b_rejeitar_todas = QPushButton("Rejeitar todas da lista")
        b_aceitar.clicked.connect(lambda: self._emitir(self.ids_selecionados(), Status.ACEITA))
        b_rejeitar.clicked.connect(lambda: self._emitir(self.ids_selecionados(), Status.REJEITADA))
        b_aceitar_todas.clicked.connect(lambda: self._emitir(self.ids_visiveis(), Status.ACEITA))
        b_rejeitar_todas.clicked.connect(lambda: self._emitir(self.ids_visiveis(), Status.REJEITADA))
        b_aceitar.setToolTip("Atalho: A")
        b_rejeitar.setToolTip("Atalho: R (Del exclui marcações manuais)")

        filtros = QHBoxLayout()
        filtros.addWidget(self.combo_tipo, 1)
        filtros.addWidget(self.combo_status, 1)
        botoes = QGridLayout()
        botoes.addWidget(b_aceitar, 0, 0)
        botoes.addWidget(b_rejeitar, 0, 1)
        botoes.addWidget(b_aceitar_todas, 1, 0)
        botoes.addWidget(b_rejeitar_todas, 1, 1)

        layout = QVBoxLayout(self)
        layout.addWidget(self.resumo)
        layout.addLayout(filtros)
        layout.addWidget(self.tabela, 1)
        layout.addLayout(botoes)
        self.atualizar([])

    # ---- dados ----------------------------------------------------------
    def atualizar(self, deteccoes: list[Deteccao], pessoas: dict[str, str] | None = None) -> None:
        """``pessoas``: rótulo ([P1]…) de cada nome que será tarjado, por id."""
        selecionados = self.ids_selecionados()
        tipo_atual = self.combo_tipo.currentData()
        self.combo_tipo.blockSignals(True)
        self.combo_tipo.clear()
        self.combo_tipo.addItem("Todos os tipos", None)
        for t in sorted({d.tipo for d in deteccoes}, key=lambda t: obter_tipo(t).nome):
            self.combo_tipo.addItem(_amostra_cor(obter_tipo(t).cor), obter_tipo(t).nome, t)
        i = self.combo_tipo.findData(tipo_atual)
        self.combo_tipo.setCurrentIndex(max(i, 0))
        self.filtro.tipo = self.combo_tipo.currentData()
        self.combo_tipo.blockSignals(False)

        self.modelo.definir(deteccoes, pessoas)
        self.selecionar(selecionados, rolar=False)

        n = len(deteccoes)
        pend = sum(1 for d in deteccoes if d.status == Status.PENDENTE)
        acc = sum(1 for d in deteccoes if d.status == Status.ACEITA)
        rej = n - pend - acc
        if n == 0:
            self.resumo.setText("Nenhuma detecção. Use a busca ou desenhe caixas para marcar áreas.")
        else:
            self.resumo.setText(
                f"<b>{n}</b> detecção(ões): <span style='color:#B26A00'>{pend} pendente(s)</span> · "
                f"<span style='color:#2E7D32'>{acc} aceita(s)</span> · "
                f"<span style='color:#8A949A'>{rej} rejeitada(s)</span>"
            )

    def _filtro_mudou(self) -> None:
        if hasattr(self.filtro, "beginFilterChange"):  # Qt ≥ 6.10
            self.filtro.beginFilterChange()
            self.filtro.tipo = self.combo_tipo.currentData()
            self.filtro.status = self.combo_status.currentData()
            self.filtro.endFilterChange()
        else:
            self.filtro.tipo = self.combo_tipo.currentData()
            self.filtro.status = self.combo_status.currentData()
            self.filtro.invalidateFilter()

    # ---- seleção --------------------------------------------------------
    def ids_selecionados(self) -> list[str]:
        return [idx.data(Qt.UserRole) for idx in self.tabela.selectionModel().selectedRows()]

    def ids_visiveis(self) -> list[str]:
        return [self.filtro.index(r, 0).data(Qt.UserRole) for r in range(self.filtro.rowCount())]

    def selecionar(self, ids: list[str], rolar: bool = True) -> None:
        self._sincronizando = True
        sel = self.tabela.selectionModel()
        sel.clearSelection()
        alvo = set(ids)
        primeiro = None
        for r in range(self.filtro.rowCount()):
            idx = self.filtro.index(r, 0)
            if idx.data(Qt.UserRole) in alvo:
                sel.select(idx, QItemSelectionModel.Select | QItemSelectionModel.Rows)
                primeiro = primeiro or idx
        if rolar and primeiro is not None:
            self.tabela.scrollTo(primeiro)
        self._sincronizando = False

    def _selecao_mudou(self) -> None:
        if not self._sincronizando:
            self.selecaoAlterada.emit(self.ids_selecionados())

    def _menu(self, pos) -> None:
        ids = self.ids_selecionados()
        if ids:
            self.menuSolicitado.emit(ids, self.tabela.viewport().mapToGlobal(pos))

    def _emitir(self, ids: list[str], status: Status) -> None:
        if ids:
            self.statusSolicitado.emit(ids, status)
