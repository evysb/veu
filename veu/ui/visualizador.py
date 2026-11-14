"""Visualizador de página com as caixas de detecção (seleção e desenho)."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QPoint, QRectF, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QMouseEvent, QPainter, QPen, QPixmap, QWheelEvent
from PySide6.QtWidgets import QGraphicsItem, QGraphicsPixmapItem, QGraphicsRectItem, QGraphicsScene, QGraphicsView

from veu.core.models import Status


@dataclass
class CaixaExibida:
    id: str
    rects: list[QRectF]  # em coordenadas da cena
    cor: str
    status: Status
    dica: str


class CaixaItem(QGraphicsRectItem):
    def __init__(self, caixa: CaixaExibida, rect: QRectF):
        super().__init__(rect.adjusted(-1, -1, 1, 1))
        self.id_deteccao = caixa.id
        self.status = caixa.status
        self.cor = QColor(caixa.cor)
        self.setFlag(QGraphicsItem.ItemIsSelectable, True)
        self.setAcceptHoverEvents(True)
        self.setToolTip(caixa.dica)
        self.setZValue(1)
        self._aplicar_estilo(False)

    def _aplicar_estilo(self, hover: bool) -> None:
        cor = QColor(self.cor)
        if self.status == Status.REJEITADA:
            cor = QColor("#8A949A")
            pen = QPen(cor, 1.2, Qt.DotLine)
            fundo = QColor(cor)
            fundo.setAlpha(25)
        elif self.status == Status.PENDENTE:
            pen = QPen(cor, 2.0, Qt.DashLine)
            fundo = QColor(cor)
            fundo.setAlpha(45)
        else:
            pen = QPen(cor, 2.0)
            fundo = QColor(cor)
            fundo.setAlpha(90)
        if hover:
            fundo.setAlpha(min(255, fundo.alpha() + 50))
        if self.isSelected():
            pen.setWidthF(3.2)
            pen.setColor(QColor("#111111"))
        pen.setCosmetic(True)
        self.setPen(pen)
        self.setBrush(QBrush(fundo))

    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemSelectedHasChanged:
            self._aplicar_estilo(False)
        return super().itemChange(change, value)

    def hoverEnterEvent(self, event):
        self._aplicar_estilo(True)
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event):
        self._aplicar_estilo(False)
        super().hoverLeaveEvent(event)


class Visualizador(QGraphicsView):
    caixaDesenhada = Signal(QRectF)  # coordenadas da cena
    selecaoAlterada = Signal(list)  # ids selecionados
    menuSolicitado = Signal(list, QPoint)  # ids, posição global
    zoomSolicitado = Signal(int)  # +1 / -1

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setScene(QGraphicsScene(self))
        self.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
        self.setBackgroundBrush(QColor("#DDE3E6"))
        self.setAlignment(Qt.AlignHCenter | Qt.AlignTop)
        self.setDragMode(QGraphicsView.NoDrag)
        self._modo_desenho = False
        self._inicio: QRectF | None = None
        self._rascunho: QGraphicsRectItem | None = None
        self._sincronizando = False
        self.scene().selectionChanged.connect(self._ao_mudar_selecao)

    # ---- conteúdo -------------------------------------------------------
    def exibir(self, pixmap: QPixmap, caixas: list[CaixaExibida], manter_rolagem: bool = False) -> None:
        h = self.horizontalScrollBar().value()
        v = self.verticalScrollBar().value()
        self._sincronizando = True
        self.scene().clear()
        self._rascunho = None
        fundo = QGraphicsPixmapItem(pixmap)
        fundo.setZValue(0)
        self.scene().addItem(fundo)
        for c in caixas:
            for r in c.rects:
                self.scene().addItem(CaixaItem(c, r))
        tamanho = pixmap.deviceIndependentSize()
        self.scene().setSceneRect(QRectF(-20, -20, tamanho.width() + 40, tamanho.height() + 40))
        self._sincronizando = False
        if manter_rolagem:
            self.horizontalScrollBar().setValue(h)
            self.verticalScrollBar().setValue(v)
        else:
            self.verticalScrollBar().setValue(self.verticalScrollBar().minimum())

    def limpar(self) -> None:
        self.scene().clear()

    def selecionar(self, ids: list[str], centralizar: bool = True) -> None:
        self._sincronizando = True
        alvo = set(ids)
        primeiro = None
        for item in self.scene().items():
            if isinstance(item, CaixaItem):
                sel = item.id_deteccao in alvo
                item.setSelected(sel)
                if sel and primeiro is None:
                    primeiro = item
        self._sincronizando = False
        if centralizar and primeiro is not None:
            self.ensureVisible(primeiro, 80, 80)

    def ids_selecionados(self) -> list[str]:
        vistos: list[str] = []
        for item in self.scene().selectedItems():
            if isinstance(item, CaixaItem) and item.id_deteccao not in vistos:
                vistos.append(item.id_deteccao)
        return vistos

    def _ao_mudar_selecao(self) -> None:
        if not self._sincronizando:
            ids = self.ids_selecionados()
            # Seleciona todas as partes de uma detecção quebrada entre linhas.
            self.selecionar(ids, centralizar=False)
            self.selecaoAlterada.emit(ids)

    # ---- modo de desenho ------------------------------------------------
    def set_modo_desenho(self, ativo: bool) -> None:
        self._modo_desenho = ativo
        self.viewport().setCursor(Qt.CrossCursor if ativo else Qt.ArrowCursor)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if self._modo_desenho and event.button() == Qt.LeftButton:
            p = self.mapToScene(event.position().toPoint())
            self._inicio = QRectF(p, p)
            self._rascunho = QGraphicsRectItem(self._inicio)
            pen = QPen(QColor("#7B2CBF"), 1.5, Qt.DashLine)
            pen.setCosmetic(True)
            self._rascunho.setPen(pen)
            self._rascunho.setBrush(QColor(123, 44, 191, 50))
            self._rascunho.setZValue(5)
            self.scene().addItem(self._rascunho)
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._modo_desenho and self._inicio is not None and self._rascunho is not None:
            p = self.mapToScene(event.position().toPoint())
            self._rascunho.setRect(QRectF(self._inicio.topLeft(), p).normalized())
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if self._modo_desenho and self._inicio is not None and self._rascunho is not None:
            rect = self._rascunho.rect()
            self.scene().removeItem(self._rascunho)
            self._rascunho = None
            self._inicio = None
            if rect.width() >= 4 and rect.height() >= 4:
                self.caixaDesenhada.emit(rect)
            return
        super().mouseReleaseEvent(event)

    # ---- outros eventos -------------------------------------------------
    def contextMenuEvent(self, event) -> None:
        item = self.itemAt(event.pos())
        if isinstance(item, CaixaItem):
            if not item.isSelected():
                self.selecionar([item.id_deteccao], centralizar=False)
                self.selecaoAlterada.emit([item.id_deteccao])
            self.menuSolicitado.emit(self.ids_selecionados(), event.globalPos())

    def wheelEvent(self, event: QWheelEvent) -> None:
        if event.modifiers() & Qt.ControlModifier:
            self.zoomSolicitado.emit(1 if event.angleDelta().y() > 0 else -1)
            return
        super().wheelEvent(event)
