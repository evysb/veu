"""Data de nascimento, placa de veículo, dados bancários, Pix e registro profissional."""

from __future__ import annotations

import re
from datetime import date

from veu.core.detectors.base import Detector, aparar, contexto_antes, tem_palavra_chave
from veu.core.models import Achado

_MESES = {
    "janeiro": 1, "fevereiro": 2, "marco": 3, "março": 3, "abril": 4, "maio": 5, "junho": 6,
    "julho": 7, "agosto": 8, "setembro": 9, "outubro": 10, "novembro": 11, "dezembro": 12,
}


class DetectorDataNascimento(Detector):
    tipo = "DATA_NASCIMENTO"
    prioridade = 74
    _RE = re.compile(
        r"(?<![\d/.\-])(?:"
        r"(?P<d>\d{1,2})[/.\-](?P<m>\d{1,2})[/.\-](?P<a>\d{4}|\d{2})"
        r"|(?P<d2>\d{1,2})º?\s+de\s+(?P<m2>[A-Za-zçÇ]+)\s+de\s+(?P<a2>\d{4})"
        r")(?![\d/])"
    )
    _CHAVES = (
        "nascimento", "nasc", "nasc.", "d.n", "dn", "data de nasc", "nascido em", "nascida em",
        "nasceu", "nascido(a)", "dt. nasc", "dt nasc", "d. nasc",
    )

    def detectar(self, texto: str) -> list[Achado]:
        achados = []
        for m in self._RE.finditer(texto):
            if not tem_palavra_chave(contexto_antes(texto, m.start(), 35), self._CHAVES):
                continue
            try:
                if m.group("d"):
                    d, mes, a = int(m.group("d")), int(m.group("m")), int(m.group("a"))
                    a = a + (1900 if a > 30 else 2000) if a < 100 else a
                else:
                    mes = _MESES.get(m.group("m2").lower(), 0)
                    d, a = int(m.group("d2")), int(m.group("a2"))
                date(a, mes, d)
            except ValueError:
                continue
            achados.append(self._achado(m.start(), m.end(), 0.93))
        return achados


class DetectorPlaca(Detector):
    tipo = "PLACA"
    prioridade = 55
    _RE = re.compile(r"(?<![\w\-])([A-Z]{3})(?:(?P<sep>[-\s]?)(\d{4})|(\d[A-Z]\d{2}))(?![\w\-])")
    _CHAVES = ("placa", "veiculo", "carro", "moto", "automovel", "renavam", "caminhao")

    def detectar(self, texto: str) -> list[Achado]:
        achados = []
        for m in self._RE.finditer(texto):
            contexto = tem_palavra_chave(contexto_antes(texto, m.start(), 30), self._CHAVES)
            if m.group(4):  # Mercosul ABC1D23
                conf = 0.97 if contexto else 0.8
            elif m.group("sep") == "-":
                conf = 0.97 if contexto else 0.7
            elif m.group("sep") == "":
                conf = 0.95 if contexto else 0.55
            else:  # "ISO 9001", "NBR 6023"… só com contexto
                if not contexto:
                    continue
                conf = 0.9
            achados.append(self._achado(m.start(), m.end(), conf))
        return achados


class DetectorContaBancaria(Detector):
    tipo = "CONTA_BANCARIA"
    prioridade = 72
    _RE = re.compile(
        r"(?<![\w])(?:"
        r"ag[eê]ncia|ag\.|ag"
        r"|conta(?:[\s-]+corrente|[\s-]+poupan[cç]a|[\s-]+salário|[\s-]+pagamento)?|c/c|c\.c\.|cc|c/p"
        r")\s*(?:banc[aá]ria\s*)?(?:n[º°o.]*\s*)?[:\-]?\s*"
        r"(?P<num>\d[\d.]{2,13}(?:\s?-\s?[\dXx]{1,2})?)(?![\d])",
        re.IGNORECASE,
    )

    def detectar(self, texto: str) -> list[Achado]:
        achados = []
        for m in self._RE.finditer(texto):
            ini, fim = aparar(texto, m.start("num"), m.end("num"))
            if len(re.sub(r"\D", "", texto[ini:fim])) >= 3:
                achados.append(self._achado(ini, fim, 0.88))
        return achados


class DetectorPix(Detector):
    tipo = "PIX"
    prioridade = 85
    # Tolera espaços isolados que o OCR às vezes insere no meio da chave.
    _UUID = re.compile(r"(?<![\w\-])(?:[0-9a-fA-F] ?){7}[0-9a-fA-F] ?- ?(?:[0-9a-fA-F] ?){3}[0-9a-fA-F] ?- ?(?:[0-9a-fA-F] ?){3}[0-9a-fA-F] ?- ?(?:[0-9a-fA-F] ?){3}[0-9a-fA-F] ?- ?(?:[0-9a-fA-F] ?){11}[0-9a-fA-F](?![\w\-])")
    _CHAVE = re.compile(r"chave[ \t]+pix(?:[ \t]*\([^)\n]{0,30}\))?[ \t]*[:\-–]?[ \t]*(?P<v>[^\s,;]{5,77})", re.IGNORECASE)

    def detectar(self, texto: str) -> list[Achado]:
        achados = []
        for m in self._UUID.finditer(texto):
            contexto = tem_palavra_chave(contexto_antes(texto, m.start(), 40), ("pix",))
            achados.append(self._achado(m.start(), m.end(), 0.97 if contexto else 0.6))
        for m in self._CHAVE.finditer(texto):
            ini, fim = aparar(texto, m.start("v"), m.end("v"))
            if fim - ini >= 5:
                achados.append(self._achado(ini, fim, 0.95))
        return achados


class DetectorRegistroProfissional(Detector):
    tipo = "CRM"
    prioridade = 78
    _RE = re.compile(
        r"(?<![\w])(?:CRM|CRO|COREN|CRP|CRF|CREFITO|CRN|CRBM|CREFONO|CRFa|RMS)"
        r"(?:\s*[-/:]?\s*[A-Z]{2}(?![a-z]))?"
        r"\s*[-/:]?\s*(?:n[º°o.]*\s*)?"
        r"\d{2,7}(?:[-./]?\d{1,3})?"
        r"(?:\s*[-/]\s*[A-Z]{2}(?![\w]))?"
    )

    def detectar(self, texto: str) -> list[Achado]:
        return [self._achado(m.start(), m.end(), 0.95) for m in self._RE.finditer(texto)]
