"""Aplicação das tarjas com remoção real do conteúdo."""

from __future__ import annotations

import os
from collections import Counter
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Callable

import pymupdf

from veu.core.extraction import abrir_documento
from veu.core.models import Analise, Deteccao, EstiloTarja, Rect, Status, Vetores
from veu.core.redaction.limpeza import limpar_documento
from veu.core.redaction.verificacao import ResultadoVerificacao, verificar
from veu.core.tipos import obter_tipo


@dataclass
class OpcoesAnonimizacao:
    estilo: EstiloTarja = EstiloTarja.PRETA
    vetores: Vetores = Vetores.COBERTOS
    limpar_documento: bool = True
    verificar: bool = True
    #: Estilo PESSOAS: rótulo de cada detecção de nome (id → "[P1]"). Vazio =
    #: agrupamento automático (ex.: na linha de comando, sem revisão).
    rotulos_por_id: dict[str, str] = field(default_factory=dict)


@dataclass
class ResultadoAnonimizacao:
    caminho_saida: str
    tarjas_por_tipo: Counter
    limpeza: list[str] = field(default_factory=list)
    verificacao: ResultadoVerificacao | None = None
    estilo: str = ""
    recibo_registrado: bool = False
    pessoas: int = 0  # estilo PESSOAS: quantas pessoas distintas foram rotuladas

    @property
    def total_tarjas(self) -> int:
        return sum(self.tarjas_por_tipo.values())


class ArquivoOriginalProtegido(Exception):
    """Tentativa de salvar por cima do PDF original."""


def caminho_saida_padrao(entrada: str) -> str:
    p = Path(entrada)
    candidato = p.with_name(f"{p.stem}_anonimizado.pdf")
    n = 2
    while candidato.exists():
        candidato = p.with_name(f"{p.stem}_anonimizado_{n}.pdf")
        n += 1
    return str(candidato)


def _mesmo_arquivo(a: str, b: str) -> bool:
    try:
        if os.path.exists(b) and os.path.samefile(a, b):
            return True
    except OSError:
        pass
    return os.path.normcase(os.path.abspath(a)) == os.path.normcase(os.path.abspath(b))


def _tamanho_fonte_rotulo(rotulo: str, r: pymupdf.Rect) -> float | None:
    fs = min(9.0, r.height * 0.75)
    while fs >= 3.0:
        if pymupdf.get_text_length(rotulo, fontname="helv", fontsize=fs) <= r.width - 1:
            return fs
        fs -= 0.5
    return None


def _para_coordenadas_pdf(page: pymupdf.Page, rect: Rect) -> pymupdf.Rect:
    """Rect da detecção (espaço não rotacionado) → área da anotação de redação."""
    r = pymupdf.Rect(rect)
    r.normalize()
    # Pequena folga vertical para cobrir acentos e descendentes.
    return pymupdf.Rect(r.x0 - 0.3, r.y0 - 0.5, r.x1 + 0.3, r.y1 + 0.5)


def aplicar_tarjas(
    entrada: str,
    saida: str,
    deteccoes: list[Deteccao],
    opcoes: OpcoesAnonimizacao,
    senha: str | None = None,
    progresso: Callable[[int, int, str], None] | None = None,
) -> tuple[Counter, list[str]]:
    if _mesmo_arquivo(entrada, saida):
        raise ArquivoOriginalProtegido("O arquivo de saída não pode ser o próprio PDF original.")

    graficos = (
        pymupdf.PDF_REDACT_LINE_ART_REMOVE_IF_TOUCHED
        if opcoes.vetores == Vetores.TOCADOS
        else pymupdf.PDF_REDACT_LINE_ART_REMOVE_IF_COVERED
    )
    contagem: Counter = Counter()
    por_pagina: dict[int, list[Deteccao]] = {}
    for d in deteccoes:
        por_pagina.setdefault(d.pagina, []).append(d)

    doc = abrir_documento(entrada, senha)
    try:
        total = len(por_pagina)
        for n, (num, dets) in enumerate(sorted(por_pagina.items()), start=1):
            page = doc[num]
            for d in dets:
                rotulo = obter_tipo(d.tipo).rotulo
                if opcoes.estilo == EstiloTarja.PESSOAS:
                    rotulo = opcoes.rotulos_por_id.get(d.id, rotulo)
                for rect in d.rects:
                    r = _para_coordenadas_pdf(page, rect)
                    if r.is_empty:
                        continue
                    if opcoes.estilo in (EstiloTarja.ROTULO, EstiloTarja.PESSOAS):
                        fs = _tamanho_fonte_rotulo(rotulo, r)
                        page.add_redact_annot(
                            r,
                            text=rotulo if fs else None,
                            fontname="helv",
                            fontsize=fs or 6,
                            align=pymupdf.TEXT_ALIGN_CENTER,
                            fill=(0, 0, 0),
                            text_color=(1, 1, 1),
                            cross_out=False,
                        )
                    else:
                        page.add_redact_annot(r, fill=(0, 0, 0), cross_out=False)
                contagem[d.tipo] += 1
            page.apply_redactions(
                images=pymupdf.PDF_REDACT_IMAGE_PIXELS,
                graphics=graficos,
                text=pymupdf.PDF_REDACT_TEXT_REMOVE,
            )
            if progresso:
                progresso(n, total, f"Aplicando tarjas ({n}/{total})…")

        limpeza = limpar_documento(doc) if opcoes.limpar_documento else []

        Path(saida).parent.mkdir(parents=True, exist_ok=True)
        temporario = saida + ".tmp"
        # garbage=4 + clean: descarta objetos órfãos (o conteúdo antigo não
        # sobrevive "escondido" no arquivo); sem criptografia na saída.
        doc.save(temporario, garbage=4, deflate=True, clean=True, encryption=pymupdf.PDF_ENCRYPT_NONE)
    finally:
        doc.close()
    os.replace(temporario, saida)
    return contagem, limpeza


def anonimizar(
    analise: Analise,
    saida: str,
    opcoes: OpcoesAnonimizacao | None = None,
    progresso: Callable[[int, int, str], None] | None = None,
) -> ResultadoAnonimizacao:
    """Tarja as detecções aceitas, limpa o documento, salva e verifica."""
    opcoes = opcoes or OpcoesAnonimizacao()
    tarjar = [d for d in analise.deteccoes if d.status == Status.ACEITA]
    rejeitadas = [d for d in analise.deteccoes if d.status == Status.REJEITADA]
    rotulos_extras: set[str] = set()
    if opcoes.estilo == EstiloTarja.PESSOAS:
        if not opcoes.rotulos_por_id:
            from veu.core.revisao import Revisao  # agrupamento automático

            opcoes = replace(opcoes, rotulos_por_id=Revisao(analise).rotulo_por_id())
        rotulos_extras = set(opcoes.rotulos_por_id.values())
    contagem, limpeza = aplicar_tarjas(analise.caminho, saida, tarjar, opcoes, analise.senha, progresso)
    resultado = ResultadoAnonimizacao(saida, contagem, limpeza, estilo=EstiloTarja(opcoes.estilo).value)
    ids_tarjados = {d.id for d in tarjar}
    resultado.pessoas = len({r for i, r in opcoes.rotulos_por_id.items() if i in ids_tarjados})
    if opcoes.verificar:
        if progresso:
            progresso(1, 1, "Verificando o PDF gerado…")
        paginas_ocr = [p.numero for p in analise.paginas if p.origem == "ocr"]
        resultado.verificacao = verificar(
            saida, tarjar, rejeitadas, politica=analise.politica, paginas_ocr=paginas_ocr, rotulos_extras=rotulos_extras
        )
    return resultado
