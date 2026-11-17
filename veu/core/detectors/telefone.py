"""Telefones brasileiros fixos e celulares, com ou sem DDD e +55."""

from __future__ import annotations

import re

from veu.core.detectors.base import Detector, contexto_antes, tem_palavra_chave
from veu.core.models import Achado

DDDS_VALIDOS = frozenset(
    {11, 12, 13, 14, 15, 16, 17, 18, 19, 21, 22, 24, 27, 28}
    | {31, 32, 33, 34, 35, 37, 38, 41, 42, 43, 44, 45, 46, 47, 48, 49}
    | {51, 53, 54, 55, 61, 62, 63, 64, 65, 66, 67, 68, 69}
    | {71, 73, 74, 75, 77, 79, 81, 82, 83, 84, 85, 86, 87, 88, 89}
    | {91, 92, 93, 94, 95, 96, 97, 98, 99}
)

_PALAVRAS_CHAVE = ("tel", "fone", "cel", "contato", "whats", "zap", "fax", "ramal")

_RE_TEL = re.compile(
    r"(?<![\w+/.\-])"
    r"(?P<pais>\+\s?55[\s.\-]?|\b55\s)?"
    r"(?P<ddd>\(\s?0?\d{2}\s?\)[\s.\-]?|0?\d{2}[\s.\-])?"
    r"(?P<num>(?:9[\s.]?\d{4}|[2-5]\d{3})(?P<sep>[\s.\-]?)\d{4})"
    r"(?![\w\-/]|[.,]\d)"
)
# Celular sem nenhum separador: 11987654321 ou 5511987654321.
_RE_TEL_COLADO = re.compile(r"(?<![\w+/.\-])(?P<pais>\+?55)?(?P<ddd>\d{2})(?P<num>9\d{8})(?![\w\-/]|[.,]\d)")


class DetectorTelefone(Detector):
    tipo = "TELEFONE"
    prioridade = 60

    def detectar(self, texto: str) -> list[Achado]:
        achados: list[Achado] = []
        for m in _RE_TEL.finditer(texto):
            ddd_txt = m.group("ddd")
            if ddd_txt:
                ddd = int(re.sub(r"\D", "", ddd_txt)[-2:])
                if ddd not in DDDS_VALIDOS:
                    # DDD inexistente (erro, número fictício): só no formato
                    # inequívoco "(00) 90000-1234", com parênteses e hífen.
                    if "(" in ddd_txt and m.group("sep") == "-":
                        achados.append(self._achado(m.start(), m.end(), 0.75))
                    continue
            contexto = tem_palavra_chave(contexto_antes(texto, m.start(), 25), _PALAVRAS_CHAVE)
            tem_sep = bool(m.group("sep"))
            if ddd_txt or m.group("pais"):
                confianca = 0.9 if (tem_sep or contexto) else 0.75
            elif tem_sep and contexto:
                confianca = 0.85
            elif tem_sep:
                confianca = 0.6
            else:
                continue  # 8–9 dígitos soltos, sem DDD nem separador: ambíguo demais
            achados.append(self._achado(m.start(), m.end(), confianca))
        for m in _RE_TEL_COLADO.finditer(texto):
            if int(m.group("ddd")) in DDDS_VALIDOS:
                achados.append(self._achado(m.start(), m.end(), 0.8))
        return achados
