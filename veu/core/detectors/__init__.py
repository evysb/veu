"""Detectores de dados pessoais (um por tipo, interface comum)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable

from veu.core.detectors.base import Detector
from veu.core.detectors.campos import DetectorConvenio, DetectorProfissao
from veu.core.detectors.cpf import DetectorCPF
from veu.core.detectors.documentos import (
    DetectorCNH,
    DetectorCNPJ,
    DetectorCNS,
    DetectorPassaporte,
    DetectorPIS,
    DetectorProntuario,
    DetectorRG,
    DetectorTituloEleitor,
)
from veu.core.detectors.email import DetectorEmail
from veu.core.detectors.endereco import DetectorEndereco
from veu.core.detectors.locais import DetectorCidade, DetectorInstituicao
from veu.core.detectors.nomes import DetectorNome
from veu.core.detectors.outros import (
    DetectorContaBancaria,
    DetectorDataNascimento,
    DetectorPix,
    DetectorPlaca,
    DetectorRegistroProfissional,
)
from veu.core.detectors.personalizados import DetectorRegex, DetectorTermosObrigatorios
from veu.core.detectors.saude import DetectorSaude
from veu.core.detectors.telefone import DetectorTelefone
from veu.core.tipos import TipoDado, registrar_tipo, remover_tipos_personalizados

if TYPE_CHECKING:
    from veu.core.policy import Politica

#: Fábrica por tipo: recebe a política e devolve o detector.
FABRICAS: dict[str, Callable[["Politica"], Detector]] = {
    "CPF": lambda p: DetectorCPF(),
    "CNPJ": lambda p: DetectorCNPJ(),
    "RG": lambda p: DetectorRG(),
    "CNH": lambda p: DetectorCNH(),
    "TITULO_ELEITOR": lambda p: DetectorTituloEleitor(),
    "PIS": lambda p: DetectorPIS(),
    "CNS": lambda p: DetectorCNS(),
    "PASSAPORTE": lambda p: DetectorPassaporte(),
    "PRONTUARIO": lambda p: DetectorProntuario(),
    "CONVENIO": lambda p: DetectorConvenio(),
    "NOME": lambda p: DetectorNome(usar_ner=p.usar_ner),
    "ENDERECO": lambda p: DetectorEndereco(),
    "CIDADE": lambda p: DetectorCidade(),
    "INSTITUICAO": lambda p: DetectorInstituicao(),
    "TELEFONE": lambda p: DetectorTelefone(),
    "EMAIL": lambda p: DetectorEmail(),
    "DATA_NASCIMENTO": lambda p: DetectorDataNascimento(),
    "PLACA": lambda p: DetectorPlaca(),
    "PROFISSAO": lambda p: DetectorProfissao(),
    "SAUDE": lambda p: DetectorSaude(),
    "CRM": lambda p: DetectorRegistroProfissional(),
    "CONTA_BANCARIA": lambda p: DetectorContaBancaria(),
    "PIX": lambda p: DetectorPix(),
}


def registrar_tipos_personalizados(politica: "Politica") -> None:
    remover_tipos_personalizados()
    for t in politica.tipos_personalizados:
        registrar_tipo(TipoDado(t.id, t.nome, t.rotulo, t.cor, "Personalizados", f"Regex: {t.regex}", personalizado=True))


def construir_detectores(politica: "Politica | None" = None) -> list[Detector]:
    """Detectores ativos segundo a política (ou todos, com a política padrão)."""
    if politica is None:
        from veu.core.policy import politica_padrao

        politica = politica_padrao()
    registrar_tipos_personalizados(politica)
    detectores: list[Detector] = [
        fabrica(politica) for tipo, fabrica in FABRICAS.items() if politica.tipo_ativo(tipo)
    ]
    for t in politica.tipos_personalizados:
        if t.ativo and politica.tipo_ativo(t.id):
            detectores.append(DetectorRegex(t.id, t.regex, t.ignorar_maiusculas))
    if politica.sempre_tarjar:
        detectores.append(DetectorTermosObrigatorios(politica.sempre_tarjar))
    return detectores


def detectores_padrao() -> list[Detector]:
    return construir_detectores(None)


__all__ = [
    "Detector",
    "DetectorCNH",
    "DetectorCNPJ",
    "DetectorCNS",
    "DetectorCPF",
    "DetectorContaBancaria",
    "DetectorDataNascimento",
    "DetectorEmail",
    "DetectorEndereco",
    "DetectorNome",
    "DetectorPIS",
    "DetectorCidade",
    "DetectorConvenio",
    "DetectorInstituicao",
    "DetectorPassaporte",
    "DetectorProfissao",
    "DetectorProntuario",
    "DetectorPix",
    "DetectorPlaca",
    "DetectorRG",
    "DetectorRegex",
    "DetectorRegistroProfissional",
    "DetectorSaude",
    "DetectorTelefone",
    "DetectorTermosObrigatorios",
    "DetectorTituloEleitor",
    "FABRICAS",
    "construir_detectores",
    "detectores_padrao",
]
