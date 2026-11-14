"""Interface comum dos detectores.

Um detector recebe o texto de uma página e devolve ``Achado``s com posições
(início/fim) nesse texto. A conversão para coordenadas fica a cargo do
pipeline, o que mantém os detectores simples e testáveis sem PDF.
"""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from typing import ClassVar

from veu.core.busca import normalizar_preservando_posicoes
from veu.core.models import Achado


class Detector(ABC):
    tipo: ClassVar[str]
    #: Em sobreposições, vence o detector de maior prioridade.
    prioridade: ClassVar[int] = 50

    @property
    def nome(self) -> str:
        return type(self).__name__

    def preparar(self, textos: list[str]) -> None:
        """Chamado uma vez com o texto de todas as páginas, antes de ``detectar``.

        Detectores caros (ex.: NER) podem processar tudo em lote aqui.
        """

    @abstractmethod
    def detectar(self, texto: str) -> list[Achado]:
        ...

    def _achado(self, inicio: int, fim: int, confianca: float, pre_aceito: bool = False) -> Achado:
        return Achado(self.tipo, inicio, fim, min(confianca, 0.99 if not pre_aceito else 1.0), self.nome, pre_aceito)


def somente_digitos(s: str) -> str:
    return re.sub(r"\D", "", s)


def contexto_antes(texto: str, inicio: int, tamanho: int = 30) -> str:
    """Trecho anterior a ``inicio``, minúsculo e sem acentos."""
    return normalizar_preservando_posicoes(texto[max(0, inicio - tamanho):inicio])


def contexto_depois(texto: str, fim: int, tamanho: int = 20) -> str:
    return normalizar_preservando_posicoes(texto[fim:fim + tamanho])


def tem_palavra_chave(contexto: str, chaves: tuple[str, ...]) -> bool:
    """``chaves`` devem estar em minúsculas e sem acentos."""
    return any(re.search(rf"(?<![a-z0-9]){re.escape(c)}(?![a-z])", contexto) for c in chaves)


def aparar(texto: str, inicio: int, fim: int, extras: str = ".,;:") -> tuple[int, int]:
    """Remove espaços e pontuação das pontas do intervalo."""
    while inicio < fim and (texto[inicio].isspace() or texto[inicio] in extras):
        inicio += 1
    while fim > inicio and (texto[fim - 1].isspace() or texto[fim - 1] in extras):
        fim -= 1
    return inicio, fim
