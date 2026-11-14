"""Endereços de e-mail."""

from __future__ import annotations

import re

from veu.core.detectors.base import Detector
from veu.core.models import Achado

_RE_EMAIL = re.compile(
    r"(?<![\w.%+\-])"
    r"[A-Za-z0-9](?:[A-Za-z0-9._%+\-]{0,62}[A-Za-z0-9_%+\-])?"
    r"@"
    r"(?:[A-Za-z0-9](?:[A-Za-z0-9\-]{0,61}[A-Za-z0-9])?\.)+"
    r"[A-Za-z]{2,24}"
    r"(?![\w\-])"
)


class DetectorEmail(Detector):
    tipo = "EMAIL"
    prioridade = 80

    def detectar(self, texto: str) -> list[Achado]:
        achados = []
        for m in _RE_EMAIL.finditer(texto):
            if ".." in m.group(0):
                continue
            achados.append(self._achado(m.start(), m.end(), 0.98))
        return achados
