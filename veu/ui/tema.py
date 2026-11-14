"""Identidade visual do Véu."""

from __future__ import annotations

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPainterPath, QPalette, QPixmap
from PySide6.QtWidgets import QApplication

PETROLEO = "#0F4C5C"
PETROLEO_CLARO = "#1B6F82"
GRAFITE = "#2B2D31"
FUNDO = "#F4F6F7"
AVISO = "#FFF4D6"
AVISO_BORDA = "#E0A800"
SUCESSO = "#2E7D32"
ERRO = "#C62828"

ESTILO = f"""
QMainWindow, QDialog {{ background: {FUNDO}; }}
QToolBar {{ background: white; border-bottom: 1px solid #D9DEE1; spacing: 4px; padding: 4px; }}
QToolButton {{ padding: 4px 8px; border-radius: 4px; }}
QToolButton:hover {{ background: #E6EEF0; }}
QToolButton:checked {{ background: #D2E3E8; }}
QPushButton {{ padding: 5px 12px; border-radius: 4px; border: 1px solid #C5CDD1; background: white; }}
QPushButton:hover {{ background: #EEF3F5; }}
QPushButton#primario {{ background: {PETROLEO}; color: white; border: none; font-weight: 600; }}
QPushButton#primario:hover {{ background: {PETROLEO_CLARO}; }}
QPushButton#primario:disabled {{ background: #9BB3BA; }}
QLabel#aviso {{ background: {AVISO}; border: 1px solid {AVISO_BORDA}; border-radius: 4px; padding: 6px 10px; }}
QLabel#boasVindas {{ color: #5A6670; font-size: 15px; border: 2px dashed #B8C4CA; border-radius: 12px; padding: 40px; }}
QDockWidget::title {{ background: white; padding: 6px; font-weight: 600; }}
QTableView {{ background: white; selection-background-color: #CFE2E8; selection-color: {GRAFITE}; }}
"""


def aplicar_tema(app: QApplication) -> None:
    app.setStyle("Fusion")
    pal = app.palette()
    pal.setColor(QPalette.Window, QColor(FUNDO))
    pal.setColor(QPalette.Highlight, QColor(PETROLEO))
    pal.setColor(QPalette.HighlightedText, QColor("white"))
    pal.setColor(QPalette.WindowText, QColor(GRAFITE))
    pal.setColor(QPalette.Text, QColor(GRAFITE))
    app.setPalette(pal)
    app.setStyleSheet(ESTILO)
    app.setWindowIcon(icone_app())


def icone_app() -> QIcon:
    """Ícone desenhado em código: um véu (arco) sobre fundo petróleo."""
    pm = QPixmap(64, 64)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    p.setBrush(QColor(PETROLEO))
    p.setPen(Qt.NoPen)
    p.drawRoundedRect(QRectF(2, 2, 60, 60), 14, 14)
    caminho = QPainterPath()
    caminho.moveTo(14, 46)
    caminho.cubicTo(18, 12, 46, 12, 50, 46)
    caminho.lineTo(42, 46)
    caminho.cubicTo(40, 28, 24, 28, 22, 46)
    caminho.closeSubpath()
    p.setBrush(QColor("white"))
    p.drawPath(caminho)
    p.end()
    return QIcon(pm)


def fonte_negrito(base: QFont | None = None) -> QFont:
    f = QFont(base) if base else QFont()
    f.setBold(True)
    return f
