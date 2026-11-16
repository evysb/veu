"""Verificação automática: reabre o PDF gerado e confirma que nada vazou."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Iterable

import pymupdf

from veu.core.busca import normalizar_preservando_posicoes
from veu.core.detectors import Detector, construir_detectores
from veu.core.extraction import OpcoesExtracao, extrair_documento
from veu.core.models import Deteccao, Origem, Rect, Status, TextoPagina
from veu.core.pipeline import detectar_na_pagina, preparar_detectores
from veu.core.tipos import todos_os_tipos

_TIPOS_NUMERICOS = {"CPF", "TELEFONE", "CNPJ", "RG", "CNS", "PIS", "CNH", "TITULO_ELEITOR", "CONTA_BANCARIA"}


@dataclass
class Problema:
    pagina: int  # 0-based
    tipo: str
    descricao: str


@dataclass
class ResultadoVerificacao:
    vazamentos: list[Problema] = field(default_factory=list)
    residuais_novos: list[Deteccao] = field(default_factory=list)
    residuais_rejeitados: int = 0
    avisos: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.vazamentos


def _sobrepoe(a: Rect, b: Rect, margem: float = 0.5) -> bool:
    return not (a[2] <= b[0] + margem or b[2] <= a[0] + margem or a[3] <= b[1] + margem or b[3] <= a[1] + margem)


def _encolher(r: Rect, d: float = 0.8) -> Rect:
    x0, y0, x1, y1 = r
    if x1 - x0 > 2 * d:
        x0, x1 = x0 + d, x1 - d
    if y1 - y0 > 2 * d:
        y0, y1 = y0 + d, y1 - d
    return (x0, y0, x1, y1)


def _padrao_valor(det: Deteccao) -> re.Pattern | None:
    """Expressão que reencontra o valor tarjado, tolerando separadores."""
    if det.tipo in _TIPOS_NUMERICOS and not any(c.isalpha() for c in det.trecho):
        digitos = re.sub(r"\D", "", det.trecho)
        if len(digitos) < 6:
            return None
        return re.compile(r"(?<!\d)" + r"[\s.\-/()]{0,2}".join(digitos) + r"(?!\d)")
    valor = normalizar_preservando_posicoes(det.trecho).strip()
    if len(valor) < 3:
        return None
    partes = [re.escape(p) for p in valor.split()]
    return re.compile(r"(?<!\w)" + r"\s+".join(partes) + r"(?!\w)")


def verificar(
    caminho_saida: str,
    tarjadas: list[Deteccao],
    rejeitadas: list[Deteccao],
    detectores: Iterable[Detector] | None = None,
    politica=None,
    paginas_ocr: list[int] | None = None,
    rotulos_extras: Iterable[str] = (),
) -> ResultadoVerificacao:
    detectores = list(detectores) if detectores is not None else construir_detectores(politica)
    resultado = ResultadoVerificacao()
    rotulos = sorted(
        {t.rotulo for t in todos_os_tipos()} | {f"[{d.tipo}]" for d in tarjadas} | set(rotulos_extras),
        key=len,
        reverse=True,
    )

    # Páginas escaneadas: o texto só existe na imagem, então o PDF gerado
    # passa por OCR de novo para provar que a tarja apagou os pixels.
    dpi = politica.ocr.dpi if politica is not None else 300
    doc = pymupdf.open(caminho_saida)
    try:
        opcoes = OpcoesExtracao(ocr=False, dpi=dpi, forcar_ocr=set(paginas_ocr or []), ocr_so_imagens=True)
        extracao = extrair_documento(doc, opcoes=opcoes)
        paginas: list[TextoPagina] = extracao.paginas
    finally:
        doc.close()
    if extracao.paginas_sem_ocr:
        resultado.avisos.append(
            "Não foi possível conferir por OCR as páginas escaneadas "
            f"{', '.join(str(n + 1) for n in extracao.paginas_sem_ocr)} (arquivo de idioma ausente)."
        )

    rej_por_pag: dict[int, list[Rect]] = {}
    for d in rejeitadas:
        rej_por_pag.setdefault(d.pagina, []).extend(d.rects)

    def intencional(pagina: int, rects: list[Rect]) -> bool:
        return any(_sobrepoe(r, rr) for r in rects for rr in rej_por_pag.get(pagina, []))

    # 1) Nenhum caractere pode ter restado dentro de uma área tarjada.
    for det in tarjadas:
        pagina = paginas[det.pagina]
        for r in det.rects:
            sobra = pagina.texto_na_area(_encolher(r))
            for rot in rotulos:
                sobra = sobra.replace(rot, "")
            sobra = sobra.strip()
            # Rótulo cortado nas bordas da área encolhida (ex.: "SAÚDE" sem colchetes).
            if sobra and any(sobra in rot for rot in rotulos):
                sobra = ""
            if sobra:
                resultado.vazamentos.append(
                    Problema(det.pagina, det.tipo, "Ainda há texto extraível dentro de uma área tarjada.")
                )
                break

    # 2) O valor tarjado não pode reaparecer em outro lugar do documento
    #    (exceto onde o próprio usuário rejeitou a marcação).
    padroes = []
    vistos = set()
    for det in tarjadas:
        if det.origem == Origem.MANUAL:
            continue
        p = _padrao_valor(det)
        if p is not None and p.pattern not in vistos:
            vistos.add(p.pattern)
            padroes.append((det, p))
    for pagina in paginas:
        texto_norm = normalizar_preservando_posicoes(pagina.texto)
        for det, p in padroes:
            for m in p.finditer(texto_norm):
                rects = pagina.rects_do_trecho(m.start(), m.end())
                if rects and not intencional(pagina.numero, rects):
                    resultado.vazamentos.append(
                        Problema(pagina.numero, det.tipo, "Um valor tarjado ainda aparece no texto do documento.")
                    )

    # 3) Rodar os detectores de novo sobre o resultado.
    preparar_detectores(detectores, paginas)
    for pagina in paginas:
        for d in detectar_na_pagina(pagina, detectores, politica):
            if intencional(pagina.numero, d.rects):
                resultado.residuais_rejeitados += 1
            else:
                d.status = Status.PENDENTE
                resultado.residuais_novos.append(d)
    return resultado
