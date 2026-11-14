"""Catálogo dos tipos de dado: nome exibido, rótulo da tarja, cor e grupo."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TipoDado:
    id: str
    nome: str
    rotulo: str  # texto usado na tarja com rótulo, ex.: "[CPF]"
    cor: str  # cor da caixa na revisão (hex)
    grupo: str = "Outros"
    descricao: str = ""
    personalizado: bool = False


_TIPOS: dict[str, TipoDado] = {}


def registrar_tipo(tipo: TipoDado) -> TipoDado:
    _TIPOS[tipo.id] = tipo
    return tipo


def remover_tipos_personalizados() -> None:
    for id_ in [i for i, t in _TIPOS.items() if t.personalizado]:
        del _TIPOS[id_]


def obter_tipo(id_tipo: str) -> TipoDado:
    """Devolve o tipo cadastrado; tipos desconhecidos recebem um padrão neutro."""
    if id_tipo in _TIPOS:
        return _TIPOS[id_tipo]
    return TipoDado(id_tipo, id_tipo.title(), f"[{id_tipo.upper()}]", "#6C757D")


def todos_os_tipos() -> list[TipoDado]:
    return list(_TIPOS.values())


def tipos_detectaveis() -> list[TipoDado]:
    """Tipos que têm detector (exclui marcações manuais e de busca)."""
    return [t for t in _TIPOS.values() if t.id not in ("TERMO", "MANUAL")]


_r = registrar_tipo
# Documentos
CPF = _r(TipoDado("CPF", "CPF", "[CPF]", "#E4572E", "Documentos", "Com e sem máscara; dígitos verificadores validados."))
CNPJ = _r(TipoDado("CNPJ", "CNPJ", "[CNPJ]", "#B23A48", "Documentos", "Numérico e alfanumérico; dígitos verificadores validados."))
RG = _r(TipoDado("RG", "RG", "[RG]", "#D1495B", "Documentos", "Perto de “RG”, “Identidade”, “SSP”…"))
CNH = _r(TipoDado("CNH", "CNH", "[CNH]", "#0277BD", "Documentos", "Registro da CNH validado, perto de “CNH”/“habilitação”."))
TITULO = _r(TipoDado("TITULO_ELEITOR", "Título de eleitor", "[TÍTULO]", "#1565C0", "Documentos", "Dígitos verificadores e UF validados."))
PIS = _r(TipoDado("PIS", "PIS/PASEP/NIS", "[PIS/NIS]", "#5D6D7E", "Documentos", "Dígito verificador validado."))
CNS = _r(TipoDado("CNS", "Cartão SUS (CNS)", "[CNS]", "#00897B", "Documentos", "15 dígitos, validação oficial."))
PASSAPORTE = _r(TipoDado("PASSAPORTE", "Passaporte", "[PASSAPORTE]", "#283593", "Documentos", "Perto de “passaporte”."))
# Pessoa e contato
NOME = _r(TipoDado("NOME", "Nome de pessoa", "[NOME]", "#8E44AD", "Pessoa e contato", "NER local + listas de nomes + contexto."))
ENDERECO = _r(TipoDado("ENDERECO", "Endereço/CEP", "[ENDEREÇO]", "#2E7D32", "Pessoa e contato", "Logradouro, número, complemento, bairro, cidade/UF e CEP."))
TELEFONE = _r(TipoDado("TELEFONE", "Telefone", "[TELEFONE]", "#E09F3E", "Pessoa e contato", "Fixo e celular, com ou sem DDD/+55."))
EMAIL = _r(TipoDado("EMAIL", "E-mail", "[E-MAIL]", "#2E86AB", "Pessoa e contato", "Endereços de e-mail."))
NASCIMENTO = _r(TipoDado("DATA_NASCIMENTO", "Data de nascimento", "[NASCIMENTO]", "#6D4C41", "Pessoa e contato", "Datas perto de “nascimento”, “DN”…"))
PLACA = _r(TipoDado("PLACA", "Placa de veículo", "[PLACA]", "#F57C00", "Pessoa e contato", "Modelo antigo e Mercosul."))
# Saúde
SAUDE = _r(TipoDado("SAUDE", "Dado de saúde", "[SAÚDE]", "#C2185B", "Saúde", "CID-10, doenças, medicamentos e condições sensíveis."))
CRM = _r(TipoDado("CRM", "Registro profissional (CRM/CRO…)", "[REGISTRO]", "#AD1457", "Saúde", "CRM, CRO, COREN, CRP, CRF…"))
# Financeiro
BANCO = _r(TipoDado("CONTA_BANCARIA", "Dados bancários", "[BANCO]", "#558B2F", "Financeiro", "Agência e conta perto das palavras-chave."))
PIX = _r(TipoDado("PIX", "Chave Pix", "[PIX]", "#00796B", "Financeiro", "Chave aleatória ou valor após “chave Pix”."))
# Marcações da revisão
TERMO = _r(TipoDado("TERMO", "Termo marcado", "[TARJA]", "#43AA8B", "Revisão"))
MANUAL = _r(TipoDado("MANUAL", "Marcação manual", "[TARJA]", "#7B2CBF", "Revisão"))
