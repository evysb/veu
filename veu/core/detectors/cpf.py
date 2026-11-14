"""CPF com ou sem máscara, validado pelos dígitos verificadores."""

from __future__ import annotations

import re

from veu.core.detectors.base import Detector, contexto_antes, somente_digitos, tem_palavra_chave
from veu.core.detectors.validacao import cpf_valido
from veu.core.models import Achado

# Separadores tolerados: ponto/hífen e no máximo um espaço ou quebra de linha
# (CPF quebrado entre linhas).
_RE_CPF = re.compile(
    r"(?<![\d.\-/])"
    r"(\d{3})( ?\.?\s?)(\d{3})( ?\.?\s?)(\d{3})( ?-?\s?)(\d{2})"
    r"(?![\d\-/]|\.\d)"
)
# Outros documentos de 11 dígitos: sem a palavra "CPF", o número é deles.
_OUTROS_DOCS = ("pis", "pasep", "nis", "nit", "cnh", "habilitacao", "titulo", "eleitor", "renavam")


class DetectorCPF(Detector):
    tipo = "CPF"
    prioridade = 90

    def detectar(self, texto: str) -> list[Achado]:
        achados: list[Achado] = []
        for m in _RE_CPF.finditer(texto):
            if not cpf_valido(somente_digitos(m.group(0))):
                continue
            antes = contexto_antes(texto, m.start())
            tem_cpf = tem_palavra_chave(antes, ("cpf", "c.p.f", "cpf/mf"))
            if not tem_cpf and tem_palavra_chave(antes, _OUTROS_DOCS):
                continue
            seps = (m.group(2), m.group(4), m.group(6))
            nus = [x.strip() for x in seps]
            mascarado = nus == [".", ".", "-"]
            sem_separador = not any(seps)
            if not mascarado and not sem_separador and not tem_cpf:
                continue  # separadores misturados ("123 456.789 09"): só com contexto
            confianca = 0.99 if (mascarado or tem_cpf) else 0.9
            achados.append(self._achado(m.start(), m.end(), confianca))
        return achados
