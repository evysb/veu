"""Gera empacotamento/veu.ico a partir do ícone desenhado em veu/ui/tema.py."""

import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication

from veu.ui.tema import icone_app

destino = Path(__file__).with_name("veu.ico")
app = QApplication(sys.argv[:1])
pm = icone_app().pixmap(256, 256)
png = destino.with_suffix(".png")
pm.save(str(png))
from PIL import Image  # noqa: E402  (só no ambiente de construção)

Image.open(png).save(destino, sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
png.unlink()
print(destino)
