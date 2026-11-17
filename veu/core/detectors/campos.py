"""Campos de formulário identificados pelo rótulo: convênio/carteirinha e profissão.

O valor desses campos não tem formato fixo ("Saúde Aurora", "professora"),
então os detectores dependem do rótulo logo antes. Sem rótulo, nada é marcado.
"""

from __future__ import annotations

import re

from veu.core.busca import normalizar_preservando_posicoes
from veu.core.detectors.base import Detector, aparar, somente_digitos
from veu.core.models import Achado

# Respostas que não identificam ninguém e ficam visíveis.
_VAZIOS = {
    "", "-", "--", "nao", "nao tem", "nao possui", "nenhum", "nenhuma", "nao informado", "nao informada",
    "em branco", "(em branco)", "n/a", "na", "nao se aplica", "sem convenio", "particular", "sus", "sim",
}


def _vazio(valor: str) -> bool:
    return normalizar_preservando_posicoes(valor).strip(" .()") in {v.strip("()") for v in _VAZIOS}


def _valor_do_campo(texto: str, inicio: int, limite: re.Pattern) -> tuple[int, int]:
    """Do início do valor até o fim da linha (ou até ``limite``), sem pontuação nas pontas."""
    fim_linha = texto.find("\n", inicio)
    fim = len(texto) if fim_linha < 0 else fim_linha
    m = limite.search(texto, inicio, fim)
    if m:
        fim = m.start()
    return aparar(texto, inicio, fim, extras=".,;:–-")


class DetectorConvenio(Detector):
    """Nome do convênio/plano e número da carteirinha."""

    tipo = "CONVENIO"
    prioridade = 68
    _RE_PLANO = re.compile(
        r"(?<![\w])(?:conv[êe]nio(?:\s+m[ée]dico)?|plano\s+de\s+sa[úu]de|operadora(?:\s+de\s+sa[úu]de)?)"
        r"[ \t]*:[ \t]*",
        re.IGNORECASE,
    )
    # O nome do plano termina na vírgula, no ponto e vírgula, num travessão ou
    # onde começa o número da carteirinha.
    _FIM_PLANO = re.compile(r"[,;(]|\s[–-]\s|\s(?:carteir|cart[ãa]o|matr[íi]cula|n[º°]\s?\d)", re.IGNORECASE)
    _RE_CARTEIRA = re.compile(
        r"(?<![\w])(?:carteirinha|carteira\s+(?:do|de)\s+(?:conv[êe]nio|plano)|cart[ãa]o\s+do\s+(?:plano|conv[êe]nio)"
        r"|n[º°o.]?\s*da\s+carteir(?:a|inha)|matr[íi]cula\s+(?:do|no)\s+(?:plano|conv[êe]nio))"
        r"(?:\s*(?:n[º°o.]|n[úu]mero))?[ \t]*[:#]?[ \t]*"
        r"(?P<valor>(?-i:[A-Z0-9](?:[A-Z0-9]|[ .\-/](?=[A-Z0-9])){3,30}))(?!\w)",
        re.IGNORECASE,
    )

    def detectar(self, texto: str) -> list[Achado]:
        achados = []
        for m in self._RE_PLANO.finditer(texto):
            ini, fim = _valor_do_campo(texto, m.end(), self._FIM_PLANO)
            if fim - ini < 2 or fim - ini > 60 or _vazio(texto[ini:fim]):
                continue
            achados.append(self._achado(ini, fim, 0.85))
        for m in self._RE_CARTEIRA.finditer(texto):
            if len(somente_digitos(m.group("valor"))) >= 4:
                achados.append(self._achado(m.start("valor"), m.end("valor"), 0.9))
        return achados


class DetectorProfissao(Detector):
    """Valor do campo "Profissão:"/"Ocupação:" de formulários."""

    tipo = "PROFISSAO"
    prioridade = 50
    _RE = re.compile(r"(?<![\w])(?:profiss[ãa]o|ocupa[çc][ãa]o|cargo)[ \t]*:[ \t]*", re.IGNORECASE)
    _FIM = re.compile(r"[;(]|\s{2,}")

    def detectar(self, texto: str) -> list[Achado]:
        achados = []
        for m in self._RE.finditer(texto):
            ini, fim = _valor_do_campo(texto, m.end(), self._FIM)
            if fim - ini < 2 or _vazio(texto[ini:fim]):
                continue
            fim = self._continuacao(texto, fim)
            # O valor inteiro identifica ("técnica de enfermagem no Hospital X,
            # setor de pediatria, plantão noturno"); só um parágrafo longo demais
            # deixa de parecer um campo de formulário.
            if fim - ini > 200:
                continue
            achados.append(self._achado(ini, fim, 0.85))
        return achados

    @staticmethod
    def _continuacao(texto: str, fim: int) -> int:
        """Inclui até duas linhas de continuação do valor quebrado ("plantão noturno\\n12x36")."""
        for _ in range(2):
            if texto[fim:fim + 1] != "\n" or texto[fim - 1:fim] in ".;":
                break
            prox_fim = texto.find("\n", fim + 1)
            prox_fim = len(texto) if prox_fim < 0 else prox_fim
            linha = texto[fim + 1:prox_fim].strip()
            if not linha or len(linha) > 40 or ":" in linha or not (linha[0].islower() or linha[0].isdigit()):
                break
            fim = fim + 1 + texto[fim + 1:prox_fim].rstrip().__len__()
        return fim
