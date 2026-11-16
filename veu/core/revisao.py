"""Estado da revisão humana: aceitar, rejeitar, adicionar e remover caixas.

Fica no núcleo (sem Qt) para poder ser reaproveitado pela CLI ou por uma API.
Os contadores alimentam o recibo de auditoria (etapa 3).
"""

from __future__ import annotations

from collections import Counter
from typing import Iterable

from veu.core import busca, pessoas
from veu.core.models import Analise, Deteccao, Origem, Rect, Status


class Revisao:
    def __init__(self, analise: Analise):
        self.analise = analise
        self.adicionadas_manualmente = 0
        self.removidas_manualmente = 0
        # Pessoas (estilo de tarja PESSOAS): grupo de cada nome e rótulos
        # escolhidos pelo usuário. Só em memória; nunca são gravados.
        self.grupo_por_id: dict[str, str] = pessoas.agrupar(analise.deteccoes)
        self.rotulo_por_grupo: dict[str, str] = {}
        self._proximo_grupo = len(set(self.grupo_por_id.values())) + 1

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

    # ---- pessoas ([P1], [P2]…) -------------------------------------------
    def rotulos_pessoas(self) -> dict[str, str]:
        """Rótulo de cada grupo com ao menos um nome a tarjar, em ordem de aparição."""
        primeiro: dict[str, tuple] = {}
        for d in self.deteccoes:
            g = self.grupo_por_id.get(d.id)
            if g is None or not d.ativa:
                continue
            pos = pessoas.ordem_no_documento(d)
            if g not in primeiro or pos < primeiro[g]:
                primeiro[g] = pos
        ordem = sorted(primeiro, key=primeiro.__getitem__)
        return {g: self.rotulo_por_grupo.get(g) or f"[P{n}]" for n, g in enumerate(ordem, start=1)}

    def rotulo_por_id(self) -> dict[str, str]:
        """Rótulo de cada nome que será tarjado (entrada de ``OpcoesAnonimizacao``)."""
        rotulos = self.rotulos_pessoas()
        return {
            d.id: rotulos[g]
            for d in self.deteccoes
            if d.ativa and (g := self.grupo_por_id.get(d.id)) in rotulos
        }

    def grupo_de(self, id_: str) -> str | None:
        return self.grupo_por_id.get(id_)

    def nomes_do_grupo(self, grupo: str) -> list[str]:
        return [d.trecho for d in self.deteccoes if self.grupo_por_id.get(d.id) == grupo]

    def renomear_pessoa(self, grupo: str, rotulo: str) -> str:
        """Define o rótulo da pessoa; texto vazio volta à numeração automática."""
        if not rotulo.strip("[] \t"):
            self.rotulo_por_grupo.pop(grupo, None)
            return self.rotulos_pessoas().get(grupo, "")
        novo = pessoas.validar_rotulo(rotulo, self.nomes_do_grupo(grupo))
        outros = {r for g, r in self.rotulos_pessoas().items() if g != grupo}
        if novo in outros:
            raise pessoas.RotuloInvalido(
                f"Outra pessoa já usa o rótulo {novo}. Para tratá-las como a mesma pessoa, use “Juntar”."
            )
        self.rotulo_por_grupo[grupo] = novo
        return novo

    def juntar_pessoas(self, ids: Iterable[str]) -> str | None:
        """Junta os grupos das detecções indicadas no grupo que aparece primeiro."""
        grupos = [g for g in dict.fromkeys(self.grupo_por_id.get(i) for i in ids) if g]
        if len(grupos) < 2:
            return grupos[0] if grupos else None
        ordem = list(self.rotulos_pessoas())
        grupos.sort(key=lambda g: ordem.index(g) if g in ordem else len(ordem))
        destino = grupos[0]
        rotulo = next((self.rotulo_por_grupo[g] for g in grupos if g in self.rotulo_por_grupo), None)
        for id_, g in self.grupo_por_id.items():
            if g in grupos:
                self.grupo_por_id[id_] = destino
        for g in grupos[1:]:
            self.rotulo_por_grupo.pop(g, None)
        if rotulo:
            self.rotulo_por_grupo[destino] = rotulo
        return destino

    def separar_pessoa(self, ids: Iterable[str]) -> str | None:
        """Move as detecções indicadas para uma pessoa nova."""
        alvo = [i for i in ids if i in self.grupo_por_id]
        if not alvo:
            return None
        novo = f"g{self._proximo_grupo}"
        self._proximo_grupo += 1
        for i in alvo:
            self.grupo_por_id[i] = novo
        return novo

    def _ja_coberto(self, pagina: int, rects: list[Rect]) -> bool:
        """Evita duplicar uma marcação idêntica já existente e ativa."""
        for d in self.da_pagina(pagina):
            if d.ativa and d.rects == rects:
                return True
        return False
