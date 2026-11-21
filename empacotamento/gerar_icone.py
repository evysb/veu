"""Gera o ícone do executável a partir do ícone desenhado em veu/ui/tema.py.

- Windows: empacotamento/veu.ico
- macOS:   empacotamento/veu.icns
"""

import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication

from veu.ui.tema import icone_app

MACOS = sys.platform == "darwin"
destino = Path(__file__).with_name("veu.icns" if MACOS else "veu.ico")
app = QApplication(sys.argv[:1])
lado = 1024 if MACOS else 256
pm = icone_app().pixmap(lado, lado)
png = destino.with_suffix(".png")
pm.save(str(png))
from PIL import Image  # noqa: E402  (só no ambiente de construção)

imagem = Image.open(png)
if MACOS:
    imagem.save(destino)  # o Pillow gera todos os tamanhos do .icns (16 a 1024)
else:
    imagem.save(destino, sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
png.unlink()
print(destino)
