"""Detectores definidos pela política: regex personalizados e termos "sempre tarjar"."""

from __future__ import annotations

import re

from veu.core.busca import normalizar_preservando_posicoes
from veu.core.detectors.base import Detector
from veu.core.detectors.dicionarios import regex_de_termos
from veu.core.models import Achado


class DetectorRegex(Detector):
    prioridade = 95  # regra explícita da organização

    def __init__(self, tipo: str, padrao: str, ignorar_maiusculas: bool = False):
        self.tipo = tipo  # type: ignore[misc]
        self._re = re.compile(padrao, re.IGNORECASE if ignorar_maiusculas else 0)

    @property
    def nome(self) -> str:
        return f"Regex:{self.tipo}"

    def detectar(self, texto: str) -> list[Achado]:
        achados = []
        for m in self._re.finditer(texto):
            if m.end() > m.start() and m.group(0).strip():
                achados.append(self._achado(m.start(), m.end(), 0.95))
        return achados


class DetectorTermosObrigatorios(Detector):
    """Termos que sempre devem ser tarjados (já entram como aceitos)."""

    tipo = "TERMO"
    prioridade = 99

    def __init__(self, termos: list[str]):
        self._re = regex_de_termos(termos)

    def detectar(self, texto: str) -> list[Achado]:
        if self._re is None:
            return []
        norm = normalizar_preservando_posicoes(texto)
        return [self._achado(m.start(), m.end(), 1.0, pre_aceito=True) for m in self._re.finditer(norm)]
