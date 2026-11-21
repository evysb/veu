# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller: gera o Véu com a interface (Veu) e a linha de comando (anonimizar).

- Windows: dist/Veu/ com Veu.exe e anonimizar.exe.
- macOS:   dist/Veu.app, com o anonimizar em Veu.app/Contents/MacOS/.

Uso (a partir da raiz do projeto):  pyinstaller empacotamento/veu.spec --noconfirm
Prefira os scripts empacotamento/construir.ps1 (Windows) e empacotamento/construir.sh (macOS),
que preparam os modelos e testam o resultado.

Modo "onedir" (pasta) de propósito: as bibliotecas do Qt (LGPL) ficam como
arquivos separados e substituíveis, como a licença pede, e o programa abre
mais rápido do que no modo "onefile".
"""

import os
import sys
from pathlib import Path

import pt_core_news_md
from PyInstaller.utils.hooks import collect_all, collect_submodules

RAIZ = Path(SPECPATH).parent
MACOS = sys.platform == "darwin"
_icone = RAIZ / "empacotamento" / ("veu.icns" if MACOS else "veu.ico")
ICONE = str(_icone) if _icone.exists() else None
sys.path.insert(0, str(RAIZ))
from veu import __version__ as VERSAO  # noqa: E402

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


_QT_SEM_USO = ("qtquick", "qtqml", "qtvirtualkeyboard", "qtpdf")


def _desnecessario(destino: str) -> bool:
    """Partes do Qt que o Véu não usa (interface só com widgets, sem QML/OpenGL)."""
    nome = destino.replace("\\", "/").lower()
    base = nome.rsplit("/", 1)[-1]
    if base in ("opengl32sw.dll", "qt6pdf.dll") or base.startswith(("qt6quick", "qt6qml", "qt6virtualkeyboard")):
        return True
    # macOS: o Qt vem em frameworks (QtQuick.framework/Versions/A/QtQuick, libqtquick*.dylib...)
    if any(parte.removeprefix("lib").startswith(_QT_SEM_USO) for parte in nome.split("/")):
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

pasta = COLLECT(
    exe_gui, a_gui.binaries, a_gui.datas,
    exe_cli, a_cli.binaries, a_cli.datas,
    name="Veu", upx=False,
)

if MACOS:
    # O primeiro executável da pasta (Veu) é o que abre ao clicar no app.
    BUNDLE(
        pasta,
        name="Veu.app",
        icon=ICONE,
        bundle_identifier="io.github.evysb.veu",
        version=VERSAO,
        info_plist={
            "CFBundleName": "Véu",
            "CFBundleDisplayName": "Véu",
            "CFBundleShortVersionString": VERSAO,
            "CFBundleVersion": VERSAO,
            "CFBundleDevelopmentRegion": "pt_BR",
            "LSMinimumSystemVersion": "13.0",
            "NSHighResolutionCapable": True,
            "NSHumanReadableCopyright": "Licença AGPL-3.0",
            # Permite "Abrir com > Véu" e arrastar PDFs para o ícone no Dock.
            "CFBundleDocumentTypes": [{
                "CFBundleTypeName": "Documento PDF",
                "CFBundleTypeRole": "Editor",
                "LSHandlerRank": "Alternate",
                "LSItemContentTypes": ["com.adobe.pdf"],
            }],
        },
    )
