"""Validação de dígitos verificadores de documentos brasileiros."""

from __future__ import annotations


def _todos_iguais(s: str) -> bool:
    return len(set(s)) == 1


def cpf_valido(digitos: str) -> bool:
    if len(digitos) != 11 or not digitos.isdigit() or _todos_iguais(digitos):
        return False
    nums = [int(d) for d in digitos]
    for pos in (9, 10):
        soma = sum(nums[i] * (pos + 1 - i) for i in range(pos))
        if (soma * 10) % 11 % 10 != nums[pos]:
            return False
    return True


def gerar_dv_cpf(base9: str) -> str:
    """Completa 9 dígitos com os 2 verificadores (útil para dados de teste)."""
    nums = [int(d) for d in base9]
    for pos in (9, 10):
        soma = sum(nums[i] * (pos + 1 - i) for i in range(pos))
        nums.append((soma * 10) % 11 % 10)
    return "".join(map(str, nums))


_PESOS_CNPJ_1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
_PESOS_CNPJ_2 = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]


def _dv_cnpj(base: str, pesos: list[int]) -> int:
    # Alfanumérico (IN RFB 2.229/2024): valor do caractere = código ASCII − 48.
    soma = sum((ord(c) - 48) * p for c, p in zip(base, pesos))
    resto = soma % 11
    return 0 if resto < 2 else 11 - resto


def cnpj_valido(cnpj: str) -> bool:
    """Aceita CNPJ numérico ou alfanumérico (14 caracteres, sem máscara)."""
    cnpj = cnpj.upper()
    if len(cnpj) != 14 or not cnpj[:12].isalnum() or not cnpj[12:].isdigit() or _todos_iguais(cnpj):
        return False
    if not all(c.isdigit() or "A" <= c <= "Z" for c in cnpj[:12]):
        return False
    dv1 = _dv_cnpj(cnpj[:12], _PESOS_CNPJ_1)
    dv2 = _dv_cnpj(cnpj[:12] + str(dv1), _PESOS_CNPJ_2)
    return cnpj[12:] == f"{dv1}{dv2}"


def gerar_dv_cnpj(base12: str) -> str:
    base12 = base12.upper()
    dv1 = _dv_cnpj(base12, _PESOS_CNPJ_1)
    dv2 = _dv_cnpj(base12 + str(dv1), _PESOS_CNPJ_2)
    return f"{base12}{dv1}{dv2}"


def pis_valido(digitos: str) -> bool:
    if len(digitos) != 11 or not digitos.isdigit() or _todos_iguais(digitos):
        return False
    pesos = [3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    resto = sum(int(d) * p for d, p in zip(digitos, pesos)) % 11
    dv = 11 - resto
    if dv >= 10:
        dv = 0
    return dv == int(digitos[10])


def gerar_dv_pis(base10: str) -> str:
    pesos = [3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    dv = 11 - sum(int(d) * p for d, p in zip(base10, pesos)) % 11
    return base10 + str(0 if dv >= 10 else dv)


def cns_valido(digitos: str) -> bool:
    """Cartão Nacional de Saúde: definitivos (1, 2) e provisórios (7, 8, 9)."""
    if len(digitos) != 15 or not digitos.isdigit() or digitos[0] not in "12789":
        return False
    return sum(int(d) * (15 - i) for i, d in enumerate(digitos)) % 11 == 0


def titulo_eleitor_valido(digitos: str) -> bool:
    if len(digitos) != 12 or not digitos.isdigit() or _todos_iguais(digitos):
        return False
    uf = int(digitos[8:10])
    if not 1 <= uf <= 28:
        return False
    sp_mg = uf in (1, 2)
    resto = sum(int(digitos[i]) * (i + 2) for i in range(8)) % 11
    dv1 = 0 if resto == 10 else (1 if resto == 0 and sp_mg else resto)
    resto2 = (int(digitos[8]) * 7 + int(digitos[9]) * 8 + dv1 * 9) % 11
    dv2 = 0 if resto2 == 10 else (1 if resto2 == 0 and sp_mg else resto2)
    return digitos[10:] == f"{dv1}{dv2}"


def cnh_valida(digitos: str) -> bool:
    if len(digitos) != 11 or not digitos.isdigit() or _todos_iguais(digitos):
        return False
    d = [int(c) for c in digitos]
    dv1 = sum(d[i] * (9 - i) for i in range(9)) % 11
    desconto = 0
    if dv1 >= 10:
        dv1, desconto = 0, 2
    x = sum(d[i] * (1 + i) for i in range(9)) % 11
    dv2 = 0 if x >= 10 else x - desconto
    return dv2 >= 0 and d[9] == dv1 and d[10] == dv2
