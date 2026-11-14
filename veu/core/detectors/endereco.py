"""Endereços: logradouro, número, complemento, bairro, cidade/UF e CEP."""

from __future__ import annotations

import re

from veu.core.detectors.base import Detector, aparar, contexto_antes, tem_palavra_chave
from veu.core.models import Achado

_UFS = "AC|AL|AP|AM|BA|CE|DF|ES|GO|MA|MT|MS|MG|PA|PB|PR|PE|PI|RJ|RN|RS|RO|RR|SC|SP|SE|TO"

_LOGRADOUROS_PRINCIPAIS = [
    "Rua", "Avenida", "Av.", "Av", "Travessa", "Trav.", "Tv.", "Alameda", "Al.", "Estrada", "Estr.",
    "Rodovia", "Rod.", "Praça", "Pça.", "Pça", "Largo", "Viela", "Beco", "Ladeira", "Servidão", "R.",
]
_LOGRADOUROS_OUTROS = [
    "Quadra", "Qd.", "Conjunto", "Conj.", "Setor", "Chácara", "Sítio", "Fazenda", "Loteamento", "Condomínio",
]


def _alternativas(palavras: list[str]) -> str:
    formas = set()
    for p in palavras:
        formas.add(re.escape(p))
        formas.add(re.escape(p.upper()))
    return "|".join(sorted(formas, key=len, reverse=True))


_LOGR = _alternativas(_LOGRADOUROS_PRINCIPAIS + _LOGRADOUROS_OUTROS)
_PRINCIPAIS = {p.lower().rstrip(".") for p in _LOGRADOUROS_PRINCIPAIS}
_PAL = r"(?:d[aeo]s?|D[AEO]S?|e|E|[A-ZÀ-Ý0-9][\wÀ-ÿ'º°ª.\-]*)"
_NUMERO = r"(?:\s*,\s*|[ ]+|\s*-\s*)(?:n[º°o.]*\s*|N[º°O.]*\s*|número\s*)?(?P<num>\d{1,6}[A-Za-z]?|[sS]/?[nN][º°o]?)(?![\w/])"

_RE_LOGR = re.compile(rf"(?<![\wÀ-ÿ])(?:{_LOGR})(?=[ ])")
_RE_COM_NUMERO = re.compile(rf"(?:{_LOGR})(?:[ ]+{_PAL}){{1,8}}?{_NUMERO}")
_RE_SEM_NUMERO = re.compile(rf"(?:{_LOGR})(?:[ ]+{_PAL}){{1,6}}")

_COMPLEMENTO = (
    r"(?:apto?|apartamento|ap|bloco|bl|casa|cs|sala|sl|conj(?:unto)?|andar|lote|lt|quadra|qd|km|torre|"
    r"fundos|frente|loja|box)\.?\s*[\w\-º°ª]*"
)
_PALAVRAS_CAP = r"[A-ZÀ-Ý][\wÀ-ÿ'.]*(?:[ ]+(?:d[aeo]s?|[A-ZÀ-Ý][\wÀ-ÿ'.]*)){0,4}"
_PARADAS = r"(?:Tel|Telefone|Fone|Cel|Celular|CEP|CPF|RG|E-?mail|CNPJ|Contato|Whats\w*|Nome|Data|Paciente)\b"
_RE_SEGMENTO = re.compile(
    rf"(?P<sep>\s*[,;\-–]\s*|\s*\n\s*|[ ]+)"
    r"(?:"
    rf"(?P<cep>CEP:?\s*\d{{5}}-?\d{{3}}|\d{{5}}-\d{{3}})"
    rf"|(?P<cidade>{_PALAVRAS_CAP}\s*[/\-–]\s*(?:{_UFS})\b)"
    rf"|(?P<comp>{_COMPLEMENTO})"
    rf"|(?P<bairro>(?:Bairro:?\s*)?(?!{_PARADAS}){_PALAVRAS_CAP})"
    r")",
    re.UNICODE,
)
_RE_CEP = re.compile(r"(?<![\d\-])(?P<rot>CEP:?\s*)?(?P<n>\d{5}-\d{3}|\d{2}\.\d{3}-\d{3})(?![\d\-])|CEP:?\s*(?P<n2>\d{8})(?!\d)")
_RE_ROTULO = re.compile(
    r"(?:endere[cç]o(?:\s+(?:residencial|comercial|completo))?|residente\s+(?:e\s+domiciliad[oa]\s+)?(?:na|no|em|à)"
    r"|reside\s+(?:na|no|em|à)|domiciliad[oa]\s+(?:na|no|em|à))[ \t]*:?[ \t]*(?P<v>[^\n;]{6,160})",
    re.IGNORECASE,
)


class DetectorEndereco(Detector):
    tipo = "ENDERECO"
    prioridade = 65

    def detectar(self, texto: str) -> list[Achado]:
        achados: list[Achado] = []
        for m in _RE_LOGR.finditer(texto):
            achado = self._a_partir_do_logradouro(texto, m.start())
            if achado:
                achados.append(achado)
        achados.extend(self._ceps(texto))
        achados.extend(self._rotulados(texto))
        return achados

    def _a_partir_do_logradouro(self, texto: str, inicio: int) -> Achado | None:
        logr = _RE_LOGR.match(texto, inicio).group(0)  # type: ignore[union-attr]
        principal = logr.lower().rstrip(".") in _PRINCIPAIS
        m = _RE_COM_NUMERO.match(texto, inicio)
        tem_numero = m is not None
        if m is None:
            m = _RE_SEM_NUMERO.match(texto, inicio)
            if m is None:
                return None
        fim = m.end()
        partes = {"cep": False, "cidade": False}
        for _ in range(5):
            s = _RE_SEGMENTO.match(texto, fim)
            if s is None:
                break
            quebra = "\n" in s.group("sep")
            so_espaco = not s.group("sep").strip() and not quebra
            if s.group("bairro") and (quebra or so_espaco):
                break  # nova linha / continuação sem vírgula: provavelmente outro assunto
            if s.group("comp") and quebra:
                break
            if so_espaco and not (s.group("cep") or s.group("comp")):
                break
            for k in partes:
                if s.group(k):
                    partes[k] = True
            fim = s.end()
        ini, fim = aparar(texto, inicio, fim)

        if tem_numero:
            conf = 0.9 if principal else 0.75
            if logr in ("R.", "R") and not (partes["cep"] or partes["cidade"]):
                conf = 0.65  # "R." também é inicial de nome
        elif partes["cep"] or partes["cidade"]:
            conf = 0.85
        elif principal and tem_palavra_chave(contexto_antes(texto, inicio, 40), ("endereco", "reside", "residente", "domiciliad")):
            conf = 0.8
        elif principal and logr not in ("R.", "R"):
            conf = 0.55
        else:
            return None
        return self._achado(ini, fim, conf)

    def _ceps(self, texto: str) -> list[Achado]:
        achados = []
        for m in _RE_CEP.finditer(texto):
            grupo = "n" if m.group("n") else "n2"
            com_rotulo = bool(m.group("rot")) or grupo == "n2"
            if not com_rotulo and tem_palavra_chave(contexto_antes(texto, m.start(), 25), ("cep",)):
                com_rotulo = True
            achados.append(self._achado(m.start(grupo), m.end(grupo), 0.95 if com_rotulo else 0.7))
        return achados

    def _rotulados(self, texto: str) -> list[Achado]:
        achados = []
        for m in _RE_ROTULO.finditer(texto):
            valor = m.group("v")
            # Corta antes de outro campo ("Telefone:", "CPF:") na mesma linha.
            corte = re.search(rf"\s+(?:{_PARADAS}|\w+:)", valor)
            fim_rel = corte.start() if corte else len(valor)
            ini, fim = aparar(texto, m.start("v"), m.start("v") + fim_rel)
            if fim - ini >= 6 and any(c.isalpha() for c in texto[ini:fim]):
                achados.append(self._achado(ini, fim, 0.8))
        return achados
