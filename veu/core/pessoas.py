"""Rótulos por pessoa ([P1], [P2]…) para o estilo de tarja ``PESSOAS``.

Todas as marcações de nome que se referem à mesma pessoa recebem o mesmo
rótulo, de modo que o texto anonimizado continua legível ("[P1] relata que
[P2]…") sem revelar quem é quem.

Agrupamento (conservador: na dúvida, pessoas ficam separadas, porque um erro
aqui só atrapalha a leitura, não vaza dado):
- os nomes são comparados sem acentos, caixa, pronomes de tratamento
  ("Sr.", "Dra.") e conectores ("da", "dos");
- os nomes mais longos formam os grupos primeiro;
- um nome entra num grupo existente só se todas as suas palavras estiverem
  nesse grupo e em nenhum outro ("Sra. Silva" → "Maria da Silva").

A numeração segue a ordem da primeira aparição no documento e conta só as
pessoas que serão tarjadas. A ligação rótulo ↔ nome existe apenas na memória
durante a revisão; ela nunca é gravada.
"""

from __future__ import annotations

import re
from typing import Iterable

from veu.core.busca import normalizar_preservando_posicoes
from veu.core.detectors.nomes import _CONECTORES, _TITULOS
from veu.core.models import Deteccao

TIPO_NOME = "NOME"
TAMANHO_MAXIMO_ROTULO = 30

_RE_TOKEN = re.compile(r"[a-z]+")


class RotuloInvalido(ValueError):
    """Rótulo escolhido pelo usuário não pode ser usado."""


def tokens_do_nome(trecho: str) -> tuple[str, ...]:
    """Palavras significativas do nome, normalizadas."""
    texto = normalizar_preservando_posicoes(trecho)
    return tuple(t for t in _RE_TOKEN.findall(texto) if t not in _TITULOS and t not in _CONECTORES)


def ordem_no_documento(d: Deteccao) -> tuple:
    r = d.rects[0] if d.rects else (0.0, 0.0, 0.0, 0.0)
    return (d.pagina, round(r[1], 1), r[0])


def agrupar(deteccoes: Iterable[Deteccao]) -> dict[str, str]:
    """Atribui um grupo (``"g1"``, ``"g2"``…) a cada detecção de nome."""
    nomes = [d for d in deteccoes if d.tipo == TIPO_NOME]
    # Mais palavras primeiro; empate pela ordem no documento.
    nomes.sort(key=lambda d: (-len(set(tokens_do_nome(d.trecho))), ordem_no_documento(d)))
    grupos: dict[str, set[str]] = {}  # grupo → palavras de todos os nomes do grupo
    exatos: dict[tuple[str, ...], str] = {}
    resultado: dict[str, str] = {}
    for d in nomes:
        toks = tokens_do_nome(d.trecho)
        chave = tuple(sorted(set(toks)))
        if not chave:
            g = f"g{len(grupos) + 1}"
            grupos[g] = set()
        elif chave in exatos:
            g = exatos[chave]
        else:
            candidatos = [g for g, palavras in grupos.items() if set(chave) <= palavras]
            if len(candidatos) == 1:
                g = candidatos[0]
            else:
                g = f"g{len(grupos) + 1}"
                grupos[g] = set(chave)
            exatos[chave] = g
        resultado[d.id] = g
    return resultado


def validar_rotulo(rotulo: str, nomes_da_pessoa: Iterable[str]) -> str:
    """Normaliza o rótulo digitado e recusa os que revelam o nome."""
    r = " ".join(rotulo.split()).strip("[] ").upper()
    if not r:
        raise RotuloInvalido("O rótulo não pode ficar vazio.")
    if len(r) + 2 > TAMANHO_MAXIMO_ROTULO:
        raise RotuloInvalido(f"Use no máximo {TAMANHO_MAXIMO_ROTULO - 2} caracteres.")
    palavras_rotulo = set(tokens_do_nome(r))
    for nome in nomes_da_pessoa:
        for t in tokens_do_nome(nome):
            if len(t) >= 3 and t in palavras_rotulo:
                raise RotuloInvalido("O rótulo não pode conter partes do nome da pessoa.")
    return f"[{r}]"
