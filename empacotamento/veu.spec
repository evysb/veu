# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller: gera dist/Veu/ com Veu.exe (interface) e anonimizar.exe (linha de comando).

Uso (a partir da raiz do projeto):  pyinstaller empacotamento/veu.spec --noconfirm
Prefira o script empacotamento/construir.ps1, que prepara os modelos e testa o resultado.

Modo "onedir" (pasta) de propósito: as bibliotecas do Qt (LGPL) ficam como
arquivos separados e substituíveis, como a licença pede, e o programa abre
mais rápido do que no modo "onefile".
"""

import os
from pathlib import Path

import pt_core_news_md
from PyInstaller.utils.hooks import collect_all, collect_submodules

RAIZ = Path(SPECPATH).parent
ICONE = str(RAIZ / "empacotamento" / "veu.ico") if (RAIZ / "empacotamento" / "veu.ico").exists() else None

# --- dados embutidos ---------------------------------------------------------
tessdata = RAIZ / "veu" / "modelos" / "tessdata" / "por.traineddata"
if not tessdata.exists():
    raise SystemExit("Falta veu/modelos/tessdata/por.traineddata: rode empacotamento/baixar_modelos.py")

pacote_modelo = Path(pt_core_news_md.__file__).parent
pasta_modelo = next(p for p in pacote_modelo.iterdir() if p.is_dir() and (p / "config.cfg").exists())

datas = [
    (str(RAIZ / "veu" / "recursos" / "*.txt"), "veu/recursos"),
    (str(tessdata), "veu/modelos/tessdata"),
    (str(pasta_modelo), "veu/modelos/pt_core_news_md"),
]
binaries = []
hiddenimports = ["veu.recursos"]

# spaCy e dependências carregam componentes por "registry" (import dinâmico).
for pacote in ("spacy", "thinc", "srsly", "catalogue", "confection", "spacy_legacy", "spacy_loggers",
               "blis", "cymem", "preshed", "murmurhash", "wasabi", "langcodes"):
    try:
        d, b, h = collect_all(pacote)
    except Exception:
        continue
    datas += d
    binaries += b
    hiddenimports += h
hiddenimports += collect_submodules("spacy.lang.pt")
# Os pacotes trazem as próprias suítes de teste: não vão para o executável.
hiddenimports = [h for h in hiddenimports if ".tests" not in h and not h.endswith(".conftest")]
datas = [d for d in datas if "/tests/" not in d[0].replace("\\", "/") and "\\tests\\" not in d[0]]

EXCLUIR = [
    "tkinter", "matplotlib", "IPython", "pytest", "pytestqt", "notebook", "torch", "tensorflow", "PIL",
    "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets", "PySide6.QtQml", "PySide6.QtQuick",
    "PySide6.Qt3DCore", "PySide6.QtMultimedia", "PySide6.QtCharts", "PySide6.QtDataVisualization",
    "PySide6.QtPdf", "PySide6.QtBluetooth", "PySide6.QtNetworkAuth", "PySide6.QtSql",
]


def analise(script):
    return Analysis(
        [str(RAIZ / "empacotamento" / script)],
        pathex=[str(RAIZ)],
        binaries=binaries,
        datas=datas,
        hiddenimports=hiddenimports,
        excludes=EXCLUIR,
        noarchive=False,
    )


def _desnecessario(destino: str) -> bool:
    """Partes do Qt que o Véu não usa (interface só com widgets, sem QML/OpenGL)."""
    nome = destino.replace("\\", "/").lower()
    base = nome.rsplit("/", 1)[-1]
    if base in ("opengl32sw.dll", "qt6pdf.dll") or base.startswith(("qt6quick", "qt6qml", "qt6virtualkeyboard")):
        return True
    if "/translations/" in nome and base.endswith(".qm"):
        return not ("_pt" in base)  # mantém só as traduções em português
    return "qtvirtualkeyboard" in nome


def enxugar(a):
    a.binaries = [b for b in a.binaries if not _desnecessario(b[0])]
    a.datas = [d for d in a.datas if not _desnecessario(d[0])]
    return a


a_gui = enxugar(analise("entrada_gui.py"))
a_cli = enxugar(analise("entrada_cli.py"))

pyz_gui = PYZ(a_gui.pure)
pyz_cli = PYZ(a_cli.pure)

exe_gui = EXE(
    pyz_gui, a_gui.scripts, [], exclude_binaries=True, name="Veu",
    console=False, icon=ICONE, upx=False,
)
exe_cli = EXE(
    pyz_cli, a_cli.scripts, [], exclude_binaries=True, name="anonimizar",
    console=True, icon=ICONE, upx=False,
)

COLLECT(
    exe_gui, a_gui.binaries, a_gui.datas,
    exe_cli, a_cli.binaries, a_cli.datas,
    name="Veu", upx=False,
)
