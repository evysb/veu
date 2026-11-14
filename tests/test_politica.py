import json

import pymupdf
import pytest

from veu.core.models import EstiloTarja, Status
from veu.core.pipeline import analisar
from veu.core.policy import (
    Politica,
    PoliticaInvalida,
    TipoPersonalizado,
    carregar_politica,
    politica_ativa,
    salvar_politica,
)
from veu.core.policy import locais
from veu.core.redaction import anonimizar
from veu.core.revisao import Revisao
from veu.core.tipos import obter_tipo


@pytest.fixture
def pdf_politica(tmp_path):
    doc = pymupdf.open()
    page = doc.new_page()
    linhas = [
        "Funcionário: MAT-123456 / matrícula antiga mat-654321",
        "Projeto Águia: entrega em março. Cliente ACME Ltda.",
        "Atendido na Clínica Maria Helena Exemplo.",
        "Paciente: Rafael Duarte Nogueira, CPF 529.982.247-25",
        "Contato (11) 98765-4321",
    ]
    for i, linha in enumerate(linhas):
        page.insert_text((50, 72 + i * 18), linha, fontsize=11)
    caminho = tmp_path / "politica.pdf"
    doc.save(caminho)
    return caminho


def test_padrao_tem_todos_os_tipos():
    p = Politica()
    assert {"CPF", "NOME", "SAUDE", "ENDERECO", "PIX"} <= set(p.tipos)
    assert p.tipo_ativo("CPF") and p.confianca_minima("NOME") == 0.5


def test_ida_e_volta_yaml_e_json(tmp_path):
    p = Politica(
        nome="Hospital Exemplo",
        sempre_tarjar=["Projeto Águia"],
        excecoes=["Clínica Maria Helena Exemplo"],
        tipos_personalizados=[TipoPersonalizado(nome="Matrícula funcionário", regex=r"MAT-\d{6}")],
    )
    p.tipos["TELEFONE"].ativo = False
    p.tarja.estilo = EstiloTarja.ROTULO
    for ext in ("yaml", "json"):
        caminho = tmp_path / f"politica.{ext}"
        salvar_politica(p, caminho)
        lida = carregar_politica(caminho)
        assert lida == p
    assert "Matrícula funcionário" in (tmp_path / "politica.yaml").read_text(encoding="utf-8")


def test_tipo_personalizado_gera_id_e_rotulo():
    t = TipoPersonalizado(nome="Matrícula funcionário", regex=r"MAT-\d{6}")
    assert t.id == "MATRICULA_FUNCIONARIO"
    assert t.rotulo == "[MATRÍCULA FUNCIONÁRIO]"


@pytest.mark.parametrize(
    "conteudo, trecho_erro",
    [
        ({"tipos_personalizados": [{"nome": "X", "regex": "MAT-(\\d"}]}, "expressão regular inválida"),
        ({"tipos_personalizados": [{"nome": "X", "regex": "\\d*"}]}, "texto vazio"),
        ({"tipos": {"INEXISTENTE": {"ativo": True}}}, "desconhecido"),
        ({"tipos": {"CPF": {"confianca_minima": 2}}}, "confianca_minima"),
        ({"campo_errado": 1}, "campo desconhecido"),
        ({"tipos_personalizados": [{"nome": "CPF", "regex": "x"}]}, "tipo padrão"),
        ({"versao": 99}, "versão"),
    ],
)
def test_politica_invalida_mensagens_em_portugues(tmp_path, conteudo, trecho_erro):
    caminho = tmp_path / "ruim.json"
    caminho.write_text(json.dumps(conteudo), encoding="utf-8")
    with pytest.raises(PoliticaInvalida) as e:
        carregar_politica(caminho)
    assert trecho_erro in str(e.value)


def test_yaml_mal_formatado(tmp_path):
    caminho = tmp_path / "ruim.yaml"
    caminho.write_text("tipos: [sem fechar", encoding="utf-8")
    with pytest.raises(PoliticaInvalida, match="mal formatado"):
        carregar_politica(caminho)


def test_politica_aplicada_na_analise(pdf_politica):
    p = Politica(
        sempre_tarjar=["Projeto Águia", "ACME"],
        excecoes=["Clínica Maria Helena Exemplo"],
        tipos_personalizados=[
            TipoPersonalizado(nome="Matrícula funcionário", regex=r"MAT-\d{6}", ignorar_maiusculas=True, cor="#123456")
        ],
    )
    p.tipos["TELEFONE"].ativo = False
    a = analisar(str(pdf_politica), politica=p)
    por_tipo = {}
    for d in a.deteccoes:
        por_tipo.setdefault(d.tipo, []).append(d)

    assert [d.trecho for d in por_tipo["MATRICULA_FUNCIONARIO"]] == ["MAT-123456", "mat-654321"]
    assert obter_tipo("MATRICULA_FUNCIONARIO").cor == "#123456"
    termos = por_tipo["TERMO"]
    assert {d.trecho for d in termos} == {"Projeto Águia", "ACME"}
    assert all(d.status == Status.ACEITA for d in termos)  # "sempre tarjar" já entra aceito
    assert "TELEFONE" not in por_tipo  # tipo desativado
    nomes = [d.trecho for d in por_tipo.get("NOME", [])]
    assert "Rafael Duarte Nogueira" in nomes
    assert not any("Maria Helena" in n for n in nomes)  # exceção


def test_confianca_minima_filtra(pdf_politica):
    p = Politica()
    p.tipos["NOME"].confianca_minima = 1.0
    a = analisar(str(pdf_politica), politica=p)
    assert not any(d.tipo == "NOME" for d in a.deteccoes)


def test_ponta_a_ponta_com_politica(pdf_politica, tmp_path):
    p = Politica(
        sempre_tarjar=["Projeto Águia"],
        tipos_personalizados=[TipoPersonalizado(nome="Matrícula", regex=r"MAT-\d{6}")],
    )
    a = analisar(str(pdf_politica), politica=p)
    Revisao(a).aceitar_pendentes()
    r = anonimizar(a, str(tmp_path / "saida.pdf"))
    assert r.verificacao.ok, r.verificacao.vazamentos
    texto = pymupdf.open(tmp_path / "saida.pdf")[0].get_text()
    assert "MAT-123456" not in texto and "Projeto Águia" not in texto
    assert "Rafael" not in texto


def test_precedencia_de_locais(tmp_path, monkeypatch):
    usuario = tmp_path / "usuario" / "politica.yaml"
    org = tmp_path / "org" / "politica.yaml"
    monkeypatch.delenv("VEU_POLITICA", raising=False)
    monkeypatch.setattr(locais, "caminho_usuario", lambda: usuario)
    monkeypatch.setattr(locais, "caminho_organizacao", lambda: org)

    pol, origem = politica_ativa()
    assert origem.descricao == "padrão" and origem.editavel

    salvar_politica(Politica(nome="Org"), org)
    assert politica_ativa()[0].nome == "Org"

    salvar_politica(Politica(nome="Usuário"), usuario)
    assert politica_ativa()[0].nome == "Usuário"  # usuário vence org não bloqueada

    salvar_politica(Politica(nome="Org travada", bloqueada=True), org)
    pol, origem = politica_ativa()
    assert pol.nome == "Org travada" and not origem.editavel

    org.write_text("tipos: [quebrado", encoding="utf-8")
    pol, origem = politica_ativa()
    assert pol.nome == "Usuário" and "ignorada" in (origem.aviso or "")

    monkeypatch.setenv("VEU_POLITICA", str(org.with_name("outra.yaml")))
    salvar_politica(Politica(nome="Env"), org.with_name("outra.yaml"))
    assert politica_ativa()[0].nome == "Env"
