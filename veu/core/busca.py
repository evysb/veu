"""Busca de termos no texto das páginas, ignorando maiúsculas e acentos."""

from __future__ import annotations

import unicodedata

from veu.core.models import TextoPagina


def _normalizar_char(c: str) -> str:
    base = unicodedata.normalize("NFD", c)[:1] or c
    baixa = base.lower()
    return baixa if len(baixa) == 1 else base  # preserva o comprimento


def normalizar_preservando_posicoes(texto: str) -> str:
    """Remove acentos e caixa sem alterar o comprimento (posição i ↔ i)."""
    return "".join(_normalizar_char(c) for c in texto)


def _normalizar_termo(termo: str) -> str:
    # Espaços múltiplos no termo casam com qualquer espaço/quebra de linha.
    return " ".join(normalizar_preservando_posicoes(termo).split())


def buscar(pagina: TextoPagina, termo: str, palavra_inteira: bool = True) -> list[tuple[int, int]]:
    alvo = _normalizar_termo(termo)
    if not alvo:
        return []
    texto = normalizar_preservando_posicoes(pagina.texto)
    # Quebras de linha viram espaço para achar termos quebrados entre linhas.
    texto_busca = texto.replace("\n", " ")
    ocorrencias: list[tuple[int, int]] = []
    inicio = 0
    while True:
        i = texto_busca.find(alvo, inicio)
        if i < 0:
            break
        fim = i + len(alvo)
        if palavra_inteira:
            antes_ok = i == 0 or not texto_busca[i - 1].isalnum()
            depois_ok = fim >= len(texto_busca) or not texto_busca[fim].isalnum()
            if not (antes_ok and depois_ok):
                inicio = i + 1
                continue
        ocorrencias.append((i, fim))
        inicio = fim
    return ocorrencias
