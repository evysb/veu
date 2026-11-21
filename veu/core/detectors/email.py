"""Endereços de e-mail.

Além do formato normal, reconhece e-mails em que o OCR leu o ``@`` errado
(``maria.silvaQexemplo.com.br``). Como esse padrão sem ``@`` é mais ambíguo,
ele só vale com o rótulo "e-mail" na mesma linha ou com cara inequívoca de
e-mail: tudo em minúsculas e domínio terminado num sufixo comum.
"""

from __future__ import annotations

import re

from veu.core.detectors.base import Detector, contexto_antes, tem_palavra_chave
from veu.core.models import Achado

_LOCAL = r"[A-Za-z0-9](?:[A-Za-z0-9._%+\-]{0,62}[A-Za-z0-9_%+\-])?"
_DOMINIO = r"(?:[A-Za-z0-9](?:[A-Za-z0-9\-]{0,61}[A-Za-z0-9])?\.)+[A-Za-z]{2,24}"

_RE_EMAIL = re.compile(rf"(?<![\w.%+\-]){_LOCAL}@{_DOMINIO}(?![\w\-])")

# Leituras do "@" comuns no Tesseract, com espaços opcionais em volta.
_ARROBA_OCR = r"[ \t]?(?:Q|©|®|&|\(a\)|\(@\))[ \t]?"
_RE_EMAIL_OCR = re.compile(
    rf"(?<![\w.%+\-])(?P<local>[A-Za-z0-9][A-Za-z0-9._%+\-]{{0,62}}?)"
    rf"(?P<arroba>{_ARROBA_OCR})"
    rf"(?P<dominio>{_DOMINIO})(?![\w\-])"
)
_SUFIXO_COMUM = re.compile(r"\.(?:com|net|org|edu|gov|br|io|me|info)(?:\.br)?$")
_ROTULOS = ("e-mail", "email", "e mail", "correio eletronico")


class DetectorEmail(Detector):
    tipo = "EMAIL"
    prioridade = 80

    def detectar(self, texto: str) -> list[Achado]:
        achados = []
        for m in _RE_EMAIL.finditer(texto):
            if ".." in m.group(0):
                continue
            achados.append(self._achado(m.start(), m.end(), 0.98))
        for m in _RE_EMAIL_OCR.finditer(texto):
            if ".." in m.group(0) or not m.group("local")[-1].isalnum():
                continue
            local, dominio = m.group("local"), m.group("dominio")
            inicio_linha = texto.rfind("\n", 0, m.start()) + 1
            rotulado = tem_palavra_chave(contexto_antes(texto, m.start(), m.start() - inicio_linha), _ROTULOS)
            # Com espaço em volta ("cardiologia & clinica.com.br"), só vale com rótulo.
            tipico = (
                not any(c.isspace() for c in m.group("arroba"))
                and local == local.lower() and dominio == dominio.lower()
                and _SUFIXO_COMUM.search(dominio)
            )
            if rotulado or tipico:
                achados.append(self._achado(m.start(), m.end(), 0.85 if rotulado else 0.75))
        return achados
