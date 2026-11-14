"""Dados de saúde: CID-10, doenças/condições sensíveis e medicamentos.

Termos clínicos genéricos ("laudo", "exame", "diagnóstico"…) NÃO são tarjados
sozinhos: eles apenas aumentam a confiança das detecções próximas.
"""

from __future__ import annotations

import bisect
import re

from veu.core.busca import normalizar_preservando_posicoes
from veu.core.detectors.base import Detector
from veu.core.detectors.dicionarios import carregar_lista, conjunto_normalizado, regex_de_termos
from veu.core.models import Achado

_RE_CID = re.compile(r"(?<![\w.])([A-TV-Z0]\d{2}(?:\.\d{1,2})?)(?![\w]|\.\d)")
_RE_CID_ROTULO = re.compile(r"cid(?:[\s\-]?10)?\b", re.IGNORECASE)
_JANELA_CONTEXTO = 200


class DetectorSaude(Detector):
    tipo = "SAUDE"
    prioridade = 45

    def __init__(self) -> None:
        doencas = carregar_lista("doencas.txt")
        medicamentos = carregar_lista("medicamentos.txt")
        self._siglas_fortes = conjunto_normalizado("siglas_fortes.txt")
        # Siglas (tudo maiúsculo no dicionário) são casadas com distinção de caixa.
        self._siglas = {t for t in (*doencas, *medicamentos) if t.isupper() and len(t) <= 5}
        self._re_doencas = regex_de_termos([t for t in doencas if t not in self._siglas])
        self._re_medicamentos = regex_de_termos([t for t in medicamentos if t not in self._siglas])
        self._re_siglas = (
            re.compile(r"(?<![\w])(?:" + "|".join(map(re.escape, sorted(self._siglas, key=len, reverse=True))) + r")(?![\w])")
            if self._siglas
            else None
        )
        self._medicamentos_siglas = {t for t in medicamentos if t in self._siglas}
        self._re_contexto = regex_de_termos(carregar_lista("termos_clinicos.txt"))

    def detectar(self, texto: str) -> list[Achado]:
        norm = normalizar_preservando_posicoes(texto)
        pos_contexto = [m.start() for m in self._re_contexto.finditer(norm)] if self._re_contexto else []

        def tem_contexto(inicio: int, fim: int) -> bool:
            i = bisect.bisect_left(pos_contexto, inicio - _JANELA_CONTEXTO)
            return i < len(pos_contexto) and pos_contexto[i] <= fim + _JANELA_CONTEXTO

        achados: list[Achado] = []
        if self._re_doencas:
            for m in self._re_doencas.finditer(norm):
                ctx = tem_contexto(m.start(), m.end())
                achados.append(self._achado(m.start(), m.end(), 0.9 if ctx else 0.75))
        if self._re_medicamentos:
            for m in self._re_medicamentos.finditer(norm):
                ctx = tem_contexto(m.start(), m.end())
                achados.append(self._achado(m.start(), m.end(), 0.85 if ctx else 0.65))
        if self._re_siglas:
            for m in self._re_siglas.finditer(texto):
                sigla = m.group(0)
                ctx = tem_contexto(m.start(), m.end())
                if sigla.lower() in self._siglas_fortes:
                    achados.append(self._achado(m.start(), m.end(), 0.95 if ctx else 0.85))
                elif ctx:
                    conf = 0.7 if sigla in self._medicamentos_siglas else 0.75
                    achados.append(self._achado(m.start(), m.end(), conf))
        achados.extend(self._cids(texto, tem_contexto))
        return achados

    def _cids(self, texto: str, tem_contexto) -> list[Achado]:
        rotulos = [m.end() for m in _RE_CID_ROTULO.finditer(texto)]
        achados = []
        ultimo_fim = -1
        for m in _RE_CID.finditer(texto):
            # Rótulo "CID" logo antes, ou lista "CID F32.1, F41.0" encadeada.
            i = bisect.bisect_right(rotulos, m.start()) - 1
            perto_rotulo = i >= 0 and m.start() - rotulos[i] <= 15
            encadeado = ultimo_fim >= 0 and m.start() - ultimo_fim <= 5 and re.fullmatch(r"[\s,;e/]*", texto[ultimo_fim:m.start()])
            if m.group(1).startswith("0") and not (perto_rotulo or encadeado):
                continue  # "0" no lugar de "O" (erro de OCR) só vale logo após "CID"
            if perto_rotulo or encadeado:
                conf = 0.97
            elif "." in m.group(1) and tem_contexto(m.start(), m.end()):
                conf = 0.75
            else:
                continue
            achados.append(self._achado(m.start(), m.end(), conf))
            ultimo_fim = m.end()
        return achados
