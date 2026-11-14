"""Carregamento dos dicionários locais (``veu/recursos/*.txt``)."""

from __future__ import annotations

import re
from functools import lru_cache
from importlib import resources

from veu.core.busca import normalizar_preservando_posicoes


def normalizar(s: str) -> str:
    return " ".join(normalizar_preservando_posicoes(s).split())


@lru_cache(maxsize=None)
def carregar_lista(nome: str) -> tuple[str, ...]:
    """Linhas de um arquivo de recursos, sem comentários nem linhas vazias."""
    texto = resources.files("veu.recursos").joinpath(nome).read_text(encoding="utf-8")
    linhas = []
    for linha in texto.splitlines():
        linha = linha.strip()
        if linha and not linha.startswith("#"):
            linhas.append(linha)
    return tuple(linhas)


@lru_cache(maxsize=None)
def conjunto_normalizado(nome: str) -> frozenset[str]:
    return frozenset(normalizar(x) for x in carregar_lista(nome))


def regex_de_termos(termos: list[str] | tuple[str, ...]) -> re.Pattern | None:
    """Regex que casa os termos (já normalizados) como palavras inteiras.

    Espaços no termo casam com qualquer sequência de espaços/quebras de linha.
    """
    termos = sorted({normalizar(t) for t in termos if t.strip()}, key=len, reverse=True)
    if not termos:
        return None
    partes = [r"\s+".join(re.escape(p) for p in t.split()) for t in termos]
    return re.compile(r"(?<![\w])(?:" + "|".join(partes) + r")(?![\w])")
