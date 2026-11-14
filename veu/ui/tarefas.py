"""Execução de tarefas demoradas fora da thread da interface."""

from __future__ import annotations

from typing import Any, Callable

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal

FuncaoTarefa = Callable[[Callable[[int, int, str], None], Callable[[], bool]], Any]


class _Sinais(QObject):
    progresso = Signal(int, int, str)
    concluido = Signal(object)
    falhou = Signal(object)


class Tarefa(QRunnable):
    """Roda ``funcao(progresso, cancelado)`` no pool de threads do Qt.

    Os sinais são entregues na thread da interface (conexão enfileirada).
    """

    def __init__(self, funcao: FuncaoTarefa):
        super().__init__()
        self.setAutoDelete(False)
        self.sinais = _Sinais()
        self._funcao = funcao
        self._cancelar = False

    def cancelar(self) -> None:
        self._cancelar = True

    def iniciar(self) -> None:
        QThreadPool.globalInstance().start(self)

    def run(self) -> None:  # noqa: D401 (executa em outra thread)
        try:
            resultado = self._funcao(self.sinais.progresso.emit, lambda: self._cancelar)
        except BaseException as erro:  # repassa à interface
            self.sinais.falhou.emit(erro)
        else:
            self.sinais.concluido.emit(resultado)
