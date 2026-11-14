"""Geradores de números de documentos FICTÍCIOS, mas válidos, para os testes."""

from veu.core.detectors.validacao import (
    cnh_valida,
    cns_valido,
    gerar_dv_cnpj,
    gerar_dv_pis,
    titulo_eleitor_valido,
)


def gerar_cns(prefixo14: str) -> str:
    """Completa 14 dígitos (começando por 7, 8 ou 9) com o dígito que valida o CNS."""
    for base in (prefixo14, prefixo14[:-1] + str((int(prefixo14[-1]) + 1) % 10)):
        soma = sum(int(d) * (15 - i) for i, d in enumerate(base))
        ultimo = (11 - soma % 11) % 11
        if ultimo < 10 and cns_valido(base + str(ultimo)):
            return base + str(ultimo)
    raise ValueError("prefixo sem dígito válido")


def gerar_titulo(base8: str, uf: str = "01") -> str:
    for dv1 in range(10):
        for dv2 in range(10):
            t = f"{base8}{uf}{dv1}{dv2}"
            if titulo_eleitor_valido(t):
                return t
    raise ValueError


def gerar_cnh(base9: str) -> str:
    for dv in range(100):
        c = f"{base9}{dv:02d}"
        if cnh_valida(c):
            return c
    raise ValueError


CNPJ_NUM = gerar_dv_cnpj("112223330001")  # 11222333000181
CNPJ_ALFA = gerar_dv_cnpj("12ABC34501DE")  # exemplo oficial da Receita: 12.ABC.345/01DE-35
PIS = gerar_dv_pis("1201234567")
CNS = gerar_cns("70000000000000"[:13] + "1")
TITULO = gerar_titulo("12345678", "01")
CNH = gerar_cnh("123456789")


def mascarar_cnpj(c: str) -> str:
    return f"{c[:2]}.{c[2:5]}.{c[5:8]}/{c[8:12]}-{c[12:]}"


def mascarar_pis(p: str) -> str:
    return f"{p[:3]}.{p[3:8]}.{p[8:10]}-{p[10]}"
