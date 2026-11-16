"""Estruturas de dados do motor.

Coordenadas: todos os retângulos estão no espaço NÃO rotacionado da página,
em pontos PDF, origem no canto superior esquerdo. É o espaço devolvido por
``page.get_text`` e esperado por ``page.add_redact_annot``. Para exibir sobre
a imagem renderizada (que já vem rotacionada), multiplique por
``page.rotation_matrix``.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from enum import Enum

Rect = tuple[float, float, float, float]  # x0, y0, x1, y1


class Status(str, Enum):
    PENDENTE = "pendente"
    ACEITA = "aceita"
    REJEITADA = "rejeitada"


class EstiloTarja(str, Enum):
    PRETA = "preta"
    ROTULO = "rotulo"
    PESSOAS = "pessoas"  # como ROTULO, mas cada pessoa vira [P1], [P2]…


class Vetores(str, Enum):
    COBERTOS = "cobertos"  # remove desenhos totalmente cobertos pela tarja
    TOCADOS = "tocados"  # remove qualquer desenho que toque a tarja (mais agressivo)


class Origem(str, Enum):
    AUTOMATICA = "automatica"
    MANUAL = "manual"
    BUSCA = "busca"


@dataclass
class Achado:
    """Resultado de um detector sobre o texto puro (sem coordenadas)."""

    tipo: str
    inicio: int
    fim: int
    confianca: float
    detector: str = ""
    pre_aceito: bool = False  # ex.: termos da política "sempre tarjar"


@dataclass
class TextoPagina:
    """Texto de uma página com a posição de cada caractere.

    ``texto[i]`` foi desenhado em ``bboxes[i]`` e pertence à linha visual
    ``linhas[i]``. Separadores inseridos pelo extrator (quebras de linha) têm
    bbox ``None`` e linha ``-1``.
    """

    numero: int  # índice da página, começando em 0
    largura: float
    altura: float
    texto: str = ""
    bboxes: list[Rect | None] = field(default_factory=list)
    linhas: list[int] = field(default_factory=list)
    origem: str = "nativo"  # "nativo" | "ocr"

    @property
    def sem_texto(self) -> bool:
        return not self.texto.strip()

    def rects_do_trecho(self, inicio: int, fim: int) -> list[Rect]:
        """Converte um intervalo do texto em retângulos, um por linha visual."""
        por_linha: dict[int, list[float]] = {}
        ordem: list[int] = []
        for i in range(max(inicio, 0), min(fim, len(self.texto))):
            bbox = self.bboxes[i]
            if bbox is None or self.texto[i].isspace():
                continue
            linha = self.linhas[i]
            r = por_linha.get(linha)
            if r is None:
                por_linha[linha] = list(bbox)
                ordem.append(linha)
            else:
                r[0] = min(r[0], bbox[0])
                r[1] = min(r[1], bbox[1])
                r[2] = max(r[2], bbox[2])
                r[3] = max(r[3], bbox[3])
        rects = [tuple(por_linha[linha]) for linha in ordem]
        if self.origem == "ocr":
            # As caixas de caractere do OCR são justas (só a altura das letras) e
            # costumam terminar antes do fim real do glifo: folga proporcional.
            rects = [_folga_ocr(r) for r in rects]
        return rects  # type: ignore[return-value]

    def texto_na_area(self, rect: Rect) -> str:
        """Texto cujos caracteres têm o centro dentro de ``rect``."""
        x0, y0, x1, y1 = rect
        saida: list[str] = []
        linha_anterior = None
        for c, bbox, linha in zip(self.texto, self.bboxes, self.linhas):
            if bbox is None:
                continue
            cx = (bbox[0] + bbox[2]) / 2
            cy = (bbox[1] + bbox[3]) / 2
            if x0 <= cx <= x1 and y0 <= cy <= y1:
                if linha_anterior is not None and linha != linha_anterior:
                    saida.append(" ")
                saida.append(c)
                linha_anterior = linha
        return "".join(saida).strip()


def _folga_ocr(r) -> Rect:
    x0, y0, x1, y1 = r
    h = max(y1 - y0, 1.0)
    dx, dy = max(2.0, 0.6 * h), 0.35 * h
    return (x0 - dx, y0 - dy, x1 + dx, y1 + dy)


def _novo_id() -> str:
    return uuid.uuid4().hex[:12]


@dataclass
class Deteccao:
    """Uma região a tarjar (ou candidata), já com coordenadas."""

    tipo: str
    pagina: int
    trecho: str
    rects: list[Rect]
    confianca: float = 1.0
    origem: Origem = Origem.AUTOMATICA
    status: Status = Status.PENDENTE
    detector: str = ""
    id: str = field(default_factory=_novo_id)

    @property
    def ativa(self) -> bool:
        """Será tarjada se o usuário não a rejeitou."""
        return self.status != Status.REJEITADA


@dataclass
class Analise:
    """Resultado da etapa de detecção de um documento."""

    caminho: str
    paginas: list[TextoPagina]
    deteccoes: list[Deteccao]
    avisos: list[str] = field(default_factory=list)
    senha: str | None = None
    politica: object | None = None  # veu.core.policy.Politica usada na análise
    sha256_original: str = ""  # calculado na abertura (auditoria)

    @property
    def num_paginas(self) -> int:
        return len(self.paginas)
