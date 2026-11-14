"""Documentos de identificação: CNPJ, RG, CNH, título de eleitor, PIS/NIS, CNS e passaporte."""

from __future__ import annotations

import re

from veu.core.detectors.base import Detector, contexto_antes, contexto_depois, somente_digitos, tem_palavra_chave
from veu.core.detectors.validacao import cnh_valida, cnpj_valido, cns_valido, pis_valido, titulo_eleitor_valido
from veu.core.models import Achado

_FIM = r"(?![\w\-/]|[.,]\w)"


class DetectorCNPJ(Detector):
    tipo = "CNPJ"
    prioridade = 90
    _RE = re.compile(
        r"(?<![\w./\-])([0-9A-Z]{2})(\.?)([0-9A-Z]{3})(\.?)([0-9A-Z]{3})(/?)([0-9A-Z]{4})(-?)(\d{2})" + _FIM
    )

    def detectar(self, texto: str) -> list[Achado]:
        achados = []
        for m in self._RE.finditer(texto):
            bruto = re.sub(r"[./\-]", "", m.group(0))
            if not cnpj_valido(bruto):
                continue
            mascarado = m.group(2) == "." and m.group(4) == "." and m.group(6) == "/" and m.group(8) == "-"
            tem_letra = any(c.isalpha() for c in bruto)
            contexto = tem_palavra_chave(contexto_antes(texto, m.start()), ("cnpj", "c.n.p.j", "inscricao"))
            if mascarado:
                conf = 0.99
            elif not any(m.group(i) for i in (2, 4, 6, 8)):
                if tem_letra and not contexto:
                    continue  # sequência alfanumérica solta: arriscado demais
                conf = 0.95 if contexto else 0.85
            else:
                if not contexto:
                    continue
                conf = 0.9
            achados.append(self._achado(m.start(), m.end(), conf))
        return achados


class DetectorPIS(Detector):
    tipo = "PIS"
    prioridade = 87
    _RE = re.compile(r"(?<![\d.\-])(\d{3})(\.?)(\d{5})(\.?)(\d{2})(-?)(\d)(?![\d\-]|\.\d)")
    _CHAVES = ("pis", "pasep", "nis", "nit", "pis/pasep", "cadunico")

    def detectar(self, texto: str) -> list[Achado]:
        achados = []
        for m in self._RE.finditer(texto):
            if not pis_valido(somente_digitos(m.group(0))):
                continue
            mascarado = m.group(2) == "." and m.group(4) == "." and m.group(6) == "-"
            contexto = tem_palavra_chave(contexto_antes(texto, m.start(), 35), self._CHAVES)
            if contexto:
                achados.append(self._achado(m.start(), m.end(), 0.97))
            elif mascarado:
                achados.append(self._achado(m.start(), m.end(), 0.9))
        return achados


class DetectorCNS(Detector):
    tipo = "CNS"
    prioridade = 88
    _RE = re.compile(r"(?<![\d.\-])([12789]\d{2})[ .]?(\d{4})[ .]?(\d{4})[ .]?(\d{4})(?![\d\-]|\.\d)")
    _CHAVES = ("cns", "cartao sus", "cartao do sus", "cartao nacional de saude", "sus")

    def detectar(self, texto: str) -> list[Achado]:
        achados = []
        for m in self._RE.finditer(texto):
            if not cns_valido(somente_digitos(m.group(0))):
                continue
            contexto = tem_palavra_chave(contexto_antes(texto, m.start(), 35), self._CHAVES)
            achados.append(self._achado(m.start(), m.end(), 0.97 if contexto else 0.85))
        return achados


class DetectorTituloEleitor(Detector):
    tipo = "TITULO_ELEITOR"
    prioridade = 86
    _RE = re.compile(r"(?<![\d.\-])(\d{4})[ .]?(\d{4})[ .]?(\d{4})(?![\d\-]|\.\d)")
    _CHAVES = ("titulo", "eleitor", "eleitoral", "inscricao eleitoral", "zona", "secao")

    def detectar(self, texto: str) -> list[Achado]:
        achados = []
        for m in self._RE.finditer(texto):
            if not titulo_eleitor_valido(somente_digitos(m.group(0))):
                continue
            contexto = tem_palavra_chave(contexto_antes(texto, m.start(), 40), self._CHAVES)
            achados.append(self._achado(m.start(), m.end(), 0.95 if contexto else 0.55))
        return achados


class DetectorCNH(Detector):
    tipo = "CNH"
    prioridade = 86
    _RE = re.compile(r"(?<![\d.\-])\d{11}(?![\d\-]|\.\d)")
    _CHAVES = ("cnh", "habilitacao", "carteira de motorista", "registro nacional", "permissao para dirigir")

    def detectar(self, texto: str) -> list[Achado]:
        achados = []
        for m in self._RE.finditer(texto):
            if cnh_valida(m.group(0)) and tem_palavra_chave(contexto_antes(texto, m.start(), 40), self._CHAVES):
                achados.append(self._achado(m.start(), m.end(), 0.95))
        return achados


class DetectorRG(Detector):
    """RG em formatos variados; exige palavra-chave antes ou órgão emissor depois."""

    tipo = "RG"
    prioridade = 75
    _RE = re.compile(
        r"(?<![\w.\-/])"
        r"(?:[A-Z]{2}[-\s]?)?"
        r"(?:\d{1,2}\.\d{3}\.\d{3}|\d\.\d{3}\.\d{3}|\d{5,10})"
        r"(?:[-\s]?[\dXx])?"
        r"(?![\w\-]|[.,]\d)"
    )
    _CHAVES = (
        "rg", "r.g", "r. g", "identidade", "carteira de identidade", "cedula de identidade",
        "registro geral", "doc. de identidade", "documento de identidade", "ci",
    )
    _ORGAOS = re.compile(r"^\s*[-–/,]?\s*(ssp|sds|sesp|pc|iip|iit|igp|detran|sejusp|ssp-|ssp/)", re.I)

    def detectar(self, texto: str) -> list[Achado]:
        achados = []
        for m in self._RE.finditer(texto):
            digitos = somente_digitos(m.group(0))
            if len(digitos) < 5 or len(set(digitos)) == 1:
                continue
            antes = contexto_antes(texto, m.start(), 30)
            # "RG nº", "RG:", "Identidade" etc. — e não "CPF" logo antes.
            chave = tem_palavra_chave(antes, self._CHAVES)
            orgao = bool(self._ORGAOS.match(contexto_depois(texto, m.end(), 12)))
            if not (chave or orgao):
                continue
            if tem_palavra_chave(antes[-12:], ("cpf", "cnpj", "cep", "tel", "fone", "crm")):
                continue
            achados.append(self._achado(m.start(), m.end(), 0.92 if chave and orgao else 0.85))
        return achados


class DetectorPassaporte(Detector):
    tipo = "PASSAPORTE"
    prioridade = 72
    _RE = re.compile(r"(?<![\w\-])([A-Z]{2}\d{6}|[A-Z]{1,2}\d{6,7}|[A-Z0-9]{6,9})(?![\w\-])")
    _CHAVES = ("passaporte", "passport")

    def detectar(self, texto: str) -> list[Achado]:
        achados = []
        for m in self._RE.finditer(texto):
            valor = m.group(0)
            if not any(c.isdigit() for c in valor):
                continue
            if tem_palavra_chave(contexto_antes(texto, m.start(), 30), self._CHAVES):
                conf = 0.95 if re.fullmatch(r"[A-Z]{2}\d{6}", valor) else 0.8
                achados.append(self._achado(m.start(), m.end(), conf))
        return achados
