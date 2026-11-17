"""Nomes de instituições e de cidades.

Instituições: uma palavra que indica o tipo de lugar ("Hospital", "Clínica",
"Colégio", "Padaria"…) seguida de um nome próprio ("Hospital Santa Aurora").
Nomes genéricos ("Clínica Médica", "Escola Estadual") ficam visíveis.

Cidades: não há lista de municípios embutida, então a cidade é reconhecida
pelo contexto ("Cidade:", "natural de", "centro de", "X/SP", o fim da linha
de endereço). Uma vez reconhecida, todas as outras ocorrências do mesmo nome
no documento também são marcadas.
"""

from __future__ import annotations

import re

from veu.core.busca import normalizar_preservando_posicoes
from veu.core.detectors.base import Detector
from veu.core.detectors.nomes import _PARADAS as _PARADAS_NOME
from veu.core.models import Achado

_UFS = "AC|AL|AP|AM|BA|CE|DF|ES|GO|MA|MT|MS|MG|PA|PB|PR|PE|PI|RJ|RN|RS|RO|RR|SC|SP|SE|TO"

# Palavra capitalizada (inclui siglas e abreviações como "Prof.") e conectores.
_CAP = r"(?:[A-ZÀ-Ý][\wÀ-ÿ'’]*\.?|\d{1,4})"
_CON = r"(?:d[aeo]s?|e|d['’])"
_NOME_PROPRIO = rf"{_CAP}(?:[ \t]+(?:{_CON}[ \t]+)?{_CAP}){{0,7}}"
# Cidade: só palavras ("Campinas", "SÃO PAULO"), nunca números ou siglas curtas ("9 SSP").
_PAL_CIDADE = r"(?:[A-ZÀ-Ý][a-zà-ÿ'’]+|[A-ZÀ-Ý]{4,})"
_NOME_CIDADE = rf"{_PAL_CIDADE}(?:[ \t]+(?:{_CON}[ \t]+)?{_PAL_CIDADE}){{0,5}}"

_TIPOS_INSTITUICAO = [
    # saúde
    "hospital", "clínica", "clinica", "maternidade", "policlínica", "policlinica", "ambulatório", "ambulatorio",
    "laboratório", "laboratorio", "consultório", "consultorio", "centro médico", "centro medico",
    "centro de saúde", "centro de saude", "posto de saúde", "posto de saude", "santa casa", "pronto-socorro",
    "pronto socorro", "ubs", "upa", "caps", "unidade básica de saúde", "unidade basica de saude",
    "farmácia", "farmacia", "drogaria",
    # ensino e outras
    "colégio", "colegio", "escola", "creche", "universidade", "faculdade", "instituto", "fundação", "fundacao",
    "igreja", "paróquia", "paroquia", "associação", "associacao", "cooperativa", "prefeitura", "secretaria",
    # comércio e trabalho
    "empresa", "padaria", "mercado", "supermercado", "loja", "restaurante", "academia", "oficina", "fábrica",
    "fabrica", "escritório", "escritorio", "construtora", "transportadora",
]
_RE_INSTITUICAO = re.compile(
    r"(?<![\wÀ-ÿ])(?P<tipo>" + "|".join(sorted((re.escape(t) for t in _TIPOS_INSTITUICAO), key=len, reverse=True)) + r")"
    # O nome pode começar na linha seguinte ("Padaria\nSilveira") e precisa
    # ser capitalizado (o tipo, não: "na maternidade Santa Aurora").
    rf"(?P<nome>(?:[ \t]+|[ \t]*\n[ \t]*)(?-i:(?:{_CON}[ \t]+)?{_CAP}(?:[ \t]+(?:{_CON}[ \t]+)?{_CAP})*))",
    re.IGNORECASE,
)
# Palavras que, sozinhas, não identificam o lugar.
_GENERICAS = {
    "medica", "medico", "geral", "cirurgica", "pediatrica", "infantil", "adulto", "municipal", "estadual",
    "federal", "publica", "publico", "particular", "privada", "privado", "regional", "central", "universitario",
    "universitaria", "especializada", "especializado", "odontologica", "veterinaria", "integrada", "integrado",
    "basica", "basico", "de", "da", "do", "das", "dos", "e", "saude", "medicina", "enfermagem", "sus", "uti",
    "pronto", "atendimento", "socorro", "emergencia", "familia", "escola", "ensino", "fundamental", "medio",
    "tecnico", "tecnica", "superior", "estado", "municipio", "cidade",
}

_RE_CIDADE_ROTULO = re.compile(
    r"(?<![\wÀ-ÿ])(?:cidade|munic[íi]pio|naturalidade|local\s+de\s+nascimento|cidade\s+natal)[ \t]*(?:/\s*UF)?[ \t]*:[ \t]*"
    rf"(?P<cidade>(?-i:{_NOME_CIDADE}))",
    re.IGNORECASE,
)
# Contexto em minúsculas antes do nome ("centro de", não "Centro de Saúde").
_RE_CIDADE_FRASE = re.compile(
    r"(?<![\wÀ-ÿ])(?:(?-i:cidade|munic[íi]pio|centro|interior|zona\s+rural|periferia)\s+de"
    r"|natural\s+de|residente\s+em|mora\s+em|morador[a]?\s+de|nascid[oa]\s+em|nasceu\s+em|mudou-se\s+para|veio\s+de)"
    rf"[ \t]+(?P<cidade>(?-i:{_NOME_CIDADE}))",
    re.IGNORECASE,
)
_RE_CIDADE_UF = re.compile(rf"(?<![\wÀ-ÿ])(?P<cidade>{_NOME_CIDADE})[ \t]*(?:/|[–-]|\()[ \t]*(?:{_UFS})\b\)?")
_RE_ENDERECO = re.compile(r"(?i:endere[çc]o(?:\s+\w+)?)[ \t]*:[ \t]*(?P<v>[^\n]+)")
_RE_ULTIMO_SEGMENTO = re.compile(rf",[ \t]*(?P<cidade>{_NOME_CIDADE})[ \t]*\.?$")


def _normalizar(nome: str) -> str:
    return " ".join(normalizar_preservando_posicoes(nome).split())


def _aparar_conectores(texto: str, ini: int, fim: int) -> tuple[int, int]:
    """Remove conectores soltos no fim ("Santa Aurora do" → "Santa Aurora")."""
    trecho = texto[ini:fim]
    m = re.search(rf"(?:[ \t]+{_CON})+[ \t]*$", trecho)
    if m:
        fim = ini + m.start()
    while fim > ini and texto[fim - 1] in " \t.,;":
        fim -= 1
    return ini, fim


def _primeira_palavra(nome: str) -> str:
    partes = _normalizar(nome).split()
    return partes[0].strip(".:") if partes else ""


def _nome_util(nome: str) -> bool:
    palavras = [p.strip(".") for p in _normalizar(nome).split()]
    return any(p not in _GENERICAS and not p.isdigit() and len(p) >= 2 for p in palavras)


class DetectorInstituicao(Detector):
    tipo = "INSTITUICAO"
    prioridade = 58  # acima de nomes de pessoa ("Padaria Silveira" é um lugar)

    def detectar(self, texto: str) -> list[Achado]:
        achados = []
        for m in _RE_INSTITUICAO.finditer(texto):
            ini, fim = _aparar_conectores(texto, m.start(), m.end("nome"))
            nome = texto[m.end("tipo"):fim]
            if "\n" in nome and (m.group("tipo").isupper() or _primeira_palavra(nome) in _PARADAS_NOME):
                continue  # título ("HISTÓRIA CLÍNICA") seguido da linha de baixo
            if not _nome_util(nome):
                continue
            achados.append(self._achado(ini, fim, 0.85))
        return achados


class DetectorCidade(Detector):
    tipo = "CIDADE"
    prioridade = 57  # abaixo do endereço: dentro dele, a caixa do endereço já cobre

    def __init__(self) -> None:
        self._cidades: set[str] = set()

    def _encontrar(self, texto: str) -> list[tuple[int, int]]:
        trechos: list[tuple[int, int]] = []
        for regex in (_RE_CIDADE_ROTULO, _RE_CIDADE_FRASE, _RE_CIDADE_UF):
            for m in regex.finditer(texto):
                trechos.append(_aparar_conectores(texto, m.start("cidade"), m.end("cidade")))
        for m in _RE_ENDERECO.finditer(texto):
            linha = m.group("v")
            s = _RE_ULTIMO_SEGMENTO.search(linha.rstrip())
            if s and not any(c.isdigit() for c in s.group("cidade")):
                base = m.start("v")
                trechos.append(_aparar_conectores(texto, base + s.start("cidade"), base + s.end("cidade")))
        return [(a, b) for a, b in trechos if b - a >= 3 and "\n" not in texto[a:b] and _nome_util(texto[a:b])]

    def preparar(self, textos: list[str]) -> None:
        self._cidades = set()
        for texto in textos:
            for a, b in self._encontrar(texto):
                self._cidades.add(_normalizar(texto[a:b]))

    def detectar(self, texto: str) -> list[Achado]:
        achados = [self._achado(a, b, 0.85) for a, b in self._encontrar(texto)]
        # Outras ocorrências das cidades já reconhecidas no documento.
        norm = normalizar_preservando_posicoes(texto)
        for cidade in self._cidades | {_normalizar(texto[a.inicio:a.fim]) for a in achados}:
            padrao = r"(?<![\w])" + r"\s+".join(re.escape(p) for p in cidade.split()) + r"(?![\w])"
            for m in re.finditer(padrao, norm):
                if texto[m.start()].isupper():
                    achados.append(self._achado(m.start(), m.end(), 0.75))
        return achados
