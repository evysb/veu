"""Ponto de entrada da interface gráfica: ``python -m veu [arquivo.pdf]``."""

from __future__ import annotations

import os
import sys

from PySide6.QtCore import QEvent, QObject, QLocale, QTimer
from PySide6.QtWidgets import QApplication

from veu.ui.janela_principal import JanelaPrincipal
from veu.ui.tema import aplicar_tema


class _AberturaMac(QObject):
    """macOS: "Abrir com > Véu" e PDFs soltos no ícone do Dock chegam como QFileOpenEvent, não em sys.argv."""

    def __init__(self, janela: JanelaPrincipal) -> None:
        super().__init__(janela)
        self._janela = janela

    def eventFilter(self, obj, event) -> bool:  # noqa: N802 (nome da API do Qt)
        if event.type() == QEvent.FileOpen:
            arquivo = event.file()
            if arquivo.lower().endswith(".pdf"):
                QTimer.singleShot(0, lambda: self._janela.abrir(arquivo))
            return True
        return False


def main() -> int:
    QLocale.setDefault(QLocale(QLocale.Portuguese, QLocale.Brazil))
    app = QApplication(sys.argv)
    app.setApplicationName("Véu")
    app.setOrganizationName("Véu")
    aplicar_tema(app)
    janela = JanelaPrincipal()
    app.installEventFilter(_AberturaMac(janela))
    janela.show()
    arquivo = next((a for a in sys.argv[1:] if a.lower().endswith(".pdf")), None)
    if arquivo:
        QTimer.singleShot(0, lambda: janela.abrir(arquivo))

    # Usado pelo script de empacotamento para conferir que o executável abre:
    # analisa o PDF informado (se houver) e fecha sozinho.
    if os.environ.get("VEU_TESTE_INICIALIZACAO"):
        def verificar() -> None:
            if janela._tarefa is not None:
                QTimer.singleShot(200, verificar)
                return
            ok = arquivo is None or janela.analise is not None
            print(f"teste de inicialização: {'ok' if ok else 'FALHOU'}"
                  + (f", {len(janela.analise.deteccoes)} detecções" if janela.analise else ""), flush=True)
            janela.alterado = False
            # Fecha a janela antes de sair: no macOS, app.exit() sozinho, chamado de um
            # timer, às vezes não interrompe o laço de eventos do Cocoa e o processo fica aberto.
            janela.close()
            app.exit(0 if ok else 1)

        QTimer.singleShot(1500, verificar)
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
