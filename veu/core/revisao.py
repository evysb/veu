"""Estado da revisão humana: aceitar, rejeitar, adicionar e remover caixas.

Fica no núcleo (sem Qt) para poder ser reaproveitado pela CLI ou por uma API.
Os contadores alimentam o recibo de auditoria (etapa 3).
"""

from __future__ import annotations

from collections import Counter
from typing import Iterable

from veu.core import busca
from veu.core.models import Analise, Deteccao, Origem, Rect, Status


class Revisao:
    def __init__(self, analise: Analise):
        self.analise = analise
        self.adicionadas_manualmente = 0
        self.removidas_manualmente = 0

    # ---- consulta -------------------------------------------------------
    @property
    def deteccoes(self) -> list[Deteccao]:
        return self.analise.deteccoes

    def por_id(self, id_: str) -> Deteccao | None:
        return next((d for d in self.deteccoes if d.id == id_), None)

    def da_pagina(self, pagina: int) -> list[Deteccao]:
        return [d for d in self.deteccoes if d.pagina == pagina]

    def contagem_status(self) -> Counter:
        return Counter(d.status for d in self.deteccoes)

    def pendentes(self) -> list[Deteccao]:
        return [d for d in self.deteccoes if d.status == Status.PENDENTE]

    def a_tarjar(self) -> list[Deteccao]:
        return [d for d in self.deteccoes if d.status == Status.ACEITA]

    # ---- alteração ------------------------------------------------------
    def definir_status(self, ids: Iterable[str], status: Status) -> None:
        alvo = set(ids)
        for d in self.deteccoes:
            if d.id in alvo:
                if status == Status.REJEITADA and d.status != Status.REJEITADA:
                    self.removidas_manualmente += 1
                elif d.status == Status.REJEITADA and status != Status.REJEITADA:
                    self.removidas_manualmente = max(0, self.removidas_manualmente - 1)
                d.status = status

    def aceitar_pendentes(self) -> None:
        for d in self.pendentes():
            d.status = Status.ACEITA

    def adicionar_manual(self, pagina: int, rect: Rect, tipo: str = "MANUAL") -> Deteccao:
        x0, y0, x1, y1 = rect
        rect = (min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1))
        trecho = self.analise.paginas[pagina].texto_na_area(rect) or "(área desenhada)"
        det = Deteccao(
            tipo=tipo,
            pagina=pagina,
            trecho=trecho,
            rects=[rect],
            confianca=1.0,
            origem=Origem.MANUAL,
            status=Status.ACEITA,
            detector="manual",
        )
        self.deteccoes.append(det)
        self.adicionadas_manualmente += 1
        return det

    def excluir(self, ids: Iterable[str]) -> None:
        """Apaga de vez caixas manuais/de busca; automáticas são só rejeitadas."""
        alvo = set(ids)
        automaticas = [d.id for d in self.deteccoes if d.id in alvo and d.origem == Origem.AUTOMATICA]
        self.definir_status(automaticas, Status.REJEITADA)
        antes = len(self.deteccoes)
        self.analise.deteccoes = [
            d for d in self.deteccoes if not (d.id in alvo and d.origem != Origem.AUTOMATICA)
        ]
        self.adicionadas_manualmente = max(0, self.adicionadas_manualmente - (antes - len(self.deteccoes)))

    def marcar_termo(self, termo: str, palavra_inteira: bool = True) -> list[Deteccao]:
        """Marca (como aceitas) todas as ocorrências de ``termo`` no documento."""
        termo = termo.strip()
        novas: list[Deteccao] = []
        if not termo:
            return novas
        for pagina in self.analise.paginas:
            for inicio, fim in busca.buscar(pagina, termo, palavra_inteira):
                rects = pagina.rects_do_trecho(inicio, fim)
                if not rects or self._ja_coberto(pagina.numero, rects):
                    continue
                det = Deteccao(
                    tipo="TERMO",
                    pagina=pagina.numero,
                    trecho=" ".join(pagina.texto[inicio:fim].split()),
                    rects=rects,
                    confianca=1.0,
                    origem=Origem.BUSCA,
                    status=Status.ACEITA,
                    detector="busca",
                )
                novas.append(det)
        self.deteccoes.extend(novas)
        self.adicionadas_manualmente += len(novas)
        return novas

    def _ja_coberto(self, pagina: int, rects: list[Rect]) -> bool:
        """Evita duplicar uma marcação idêntica já existente e ativa."""
        for d in self.da_pagina(pagina):
            if d.ativa and d.rects == rects:
                return True
        return False
