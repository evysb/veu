"""Tarjas com remoção real, limpeza do documento e verificação pós-anonimização."""

from veu.core.models import EstiloTarja, Vetores
from veu.core.redaction.aplicar import (
    ArquivoOriginalProtegido,
    OpcoesAnonimizacao,
    ResultadoAnonimizacao,
    anonimizar,
    aplicar_tarjas,
    caminho_saida_padrao,
)
from veu.core.redaction.verificacao import ResultadoVerificacao, verificar

__all__ = [
    "ArquivoOriginalProtegido",
    "EstiloTarja",
    "OpcoesAnonimizacao",
    "ResultadoAnonimizacao",
    "ResultadoVerificacao",
    "Vetores",
    "anonimizar",
    "aplicar_tarjas",
    "caminho_saida_padrao",
    "verificar",
]
