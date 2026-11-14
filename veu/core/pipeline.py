"""Orquestração: abrir → extrair → detectar (segundo a política)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable, Iterable

from veu.core import busca
from veu.core.detectors import Detector, construir_detectores
from veu.core.detectors.nomes import DetectorNome, erro_ner
from veu.core.extraction import OpcoesExtracao, abrir_documento, extrair_documento
from veu.core.models import Achado, Analise, Deteccao, Origem, Status, TextoPagina

if TYPE_CHECKING:
    from veu.core.policy import Politica

Progresso = Callable[[int, int, str], None]


def preparar_detectores(detectores: Iterable[Detector], paginas: list[TextoPagina]) -> None:
    textos = [p.texto for p in paginas]
    for d in detectores:
        d.preparar(textos)


def _ocorrencias_excecoes(pagina: TextoPagina, excecoes: list[str]) -> list[tuple[int, int]]:
    ocorr: list[tuple[int, int]] = []
    for termo in excecoes:
        ocorr.extend(busca.buscar(pagina, termo, palavra_inteira=True))
    return ocorr


def detectar_na_pagina(
    pagina: TextoPagina,
    detectores: Iterable[Detector],
    politica: "Politica | None" = None,
) -> list[Deteccao]:
    detectores = list(detectores)
    prioridade = {d.nome: d.prioridade for d in detectores}
    achados: list[Achado] = []
    for det in detectores:
        achados.extend(det.detectar(pagina.texto))

    if politica is not None:
        achados = [a for a in achados if a.pre_aceito or a.confianca >= politica.confianca_minima(a.tipo)]
        if politica.excecoes:
            excecoes = _ocorrencias_excecoes(pagina, politica.excecoes)
            achados = [
                a for a in achados
                if a.pre_aceito or not any(e0 <= a.inicio and a.fim <= e1 for e0, e1 in excecoes)
            ]
    achados = resolver_sobreposicoes(achados, prioridade)

    deteccoes = []
    for a in achados:
        rects = pagina.rects_do_trecho(a.inicio, a.fim)
        if not rects:
            continue
        deteccoes.append(
            Deteccao(
                tipo=a.tipo,
                pagina=pagina.numero,
                trecho=" ".join(pagina.texto[a.inicio:a.fim].split()),
                rects=rects,
                confianca=a.confianca,
                origem=Origem.AUTOMATICA,
                status=Status.ACEITA if a.pre_aceito else Status.PENDENTE,
                detector=a.detector,
            )
        )
    return deteccoes


def resolver_sobreposicoes(achados: list[Achado], prioridade: dict[str, int]) -> list[Achado]:
    """Descarta achados inteiramente contidos em outro já aceito.

    Ordem de preferência: prioridade do detector, confiança, tamanho. Sobreposições
    parciais mantêm os dois achados — melhor tarjar a mais do que deixar uma sobra.
    """
    ordenados = sorted(
        achados,
        key=lambda a: (-prioridade.get(a.detector, 0), -a.confianca, -(a.fim - a.inicio), a.inicio),
    )
    aceitos: list[Achado] = []
    for a in ordenados:
        if a.fim <= a.inicio:
            continue
        if any(b.inicio <= a.inicio and a.fim <= b.fim for b in aceitos):
            continue
        aceitos.append(a)

    def redundante(a: Achado) -> bool:
        # Contido num achado maior de prioridade igual/maior: a caixa maior já cobre.
        # Se o contido tem prioridade MAIOR (ex.: CPF dentro de um "endereço"),
        # ele fica: se o usuário rejeitar o maior, o CPF continua marcado.
        for b in aceitos:
            if b is a or not (b.inicio <= a.inicio and a.fim <= b.fim):
                continue
            if a.pre_aceito and not b.pre_aceito:
                continue
            if prioridade.get(a.detector, 0) <= prioridade.get(b.detector, 0):
                return True
        return False

    return sorted((a for a in aceitos if not redundante(a)), key=lambda a: a.inicio)


def _lista_paginas(numeros: list[int]) -> str:
    nums = [str(n + 1) for n in numeros[:15]]
    return ", ".join(nums) + ("…" if len(numeros) > 15 else "")


def analisar(
    caminho: str,
    senha: str | None = None,
    politica: "Politica | None" = None,
    detectores: Iterable[Detector] | None = None,
    progresso: Progresso | None = None,
    cancelado: Callable[[], bool] | None = None,
) -> Analise:
    if politica is None:
        from veu.core.policy import politica_padrao

        politica = politica_padrao()
    detectores = list(detectores) if detectores is not None else construir_detectores(politica)
    doc = abrir_documento(caminho, senha)
    try:
        def prog_extracao(i: int, total: int, msg: str) -> None:
            if progresso:
                progresso(i, total * 3, msg)

        opcoes = OpcoesExtracao(ocr=politica.ocr.ativo, dpi=politica.ocr.dpi)
        extracao = extrair_documento(doc, prog_extracao, cancelado, opcoes)
        paginas = extracao.paginas
    finally:
        doc.close()

    total = len(paginas)
    if progresso:
        nomes = any(isinstance(d, DetectorNome) and d.usar_ner for d in detectores)
        progresso(total, total * 3, "Reconhecendo nomes (modelo local)…" if nomes else "Preparando detectores…")
    preparar_detectores(detectores, paginas)
    if cancelado and cancelado():
        raise InterruptedError("Operação cancelada.")

    deteccoes: list[Deteccao] = []
    for i, pagina in enumerate(paginas, start=1):
        if cancelado and cancelado():
            raise InterruptedError("Operação cancelada.")
        deteccoes.extend(detectar_na_pagina(pagina, detectores, politica))
        if progresso:
            progresso(total * 2 + i, total * 3, f"Procurando dados na página {i} de {total}…")

    avisos = []
    if extracao.paginas_ocr:
        avisos.append(
            f"OCR aplicado em {len(extracao.paginas_ocr)} página(s) escaneada(s): {_lista_paginas(extracao.paginas_ocr)}. "
            "O reconhecimento de texto pode falhar (letras trocadas, trechos ilegíveis): revise essas páginas com "
            "atenção redobrada e marque manualmente o que faltar."
        )
    sem_texto = [p.numero for p in paginas if p.sem_texto and p.numero not in extracao.paginas_ocr]
    if extracao.paginas_sem_ocr:
        avisos.append(
            f"{len(extracao.paginas_sem_ocr)} página(s) parecem escaneadas, mas o OCR não está disponível "
            f"(arquivo de idioma ausente): {_lista_paginas(extracao.paginas_sem_ocr)}. Marque as áreas manualmente."
        )
    elif sem_texto:
        avisos.append(
            f"{len(sem_texto)} página(s) sem nenhum texto reconhecível: {_lista_paginas(sem_texto)}. "
            "Confira-as visualmente e marque o que for preciso."
        )
    if any(isinstance(d, DetectorNome) and d.usar_ner and not d.ner_disponivel for d in detectores):
        avisos.append(
            "O modelo de reconhecimento de nomes não está disponível "
            f"({erro_ner() or 'motivo desconhecido'}). Nomes foram buscados só pelas listas e pelo contexto."
        )
    from veu.core.audit import sha256_arquivo

    return Analise(
        caminho=caminho,
        paginas=paginas,
        deteccoes=deteccoes,
        avisos=avisos,
        senha=senha,
        politica=politica,
        sha256_original=sha256_arquivo(caminho),
    )
