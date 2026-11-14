import shutil

import pymupdf

from tests.fixtures import gerar_pdfs as g
from veu.cli import ERRO, FALHA_VERIFICACAO, NADA_GERADO, OK, main
from veu.core.audit import ler_historico
from veu.core.policy import Politica, TipoPersonalizado, salvar_politica


def test_sem_flag_so_analisa(pdfs, tmp_path, capsys):
    pdf = shutil.copy(pdfs["texto_nativo"], tmp_path / "a.pdf")
    assert main([str(pdf)]) == NADA_GERADO
    out, err = capsys.readouterr()
    assert "CPF" in out and "Nenhum arquivo foi gerado" in err
    assert g.mascarar_cpf(g.CPF_1) not in out  # trechos mascarados por padrão
    assert not (tmp_path / "a_anonimizado.pdf").exists()


def test_sem_revisao_gera_verifica_e_audita(pdfs, tmp_path, capsys):
    pdf = shutil.copy(pdfs["prontuario"], tmp_path / "p.pdf")
    saida = tmp_path / "saida.pdf"
    assert main([str(pdf), "--saida", str(saida), "--sem-revisao", "--estilo", "rotulo"]) == OK
    out, err = capsys.readouterr()
    assert "ATENÇÃO" in err and "verificação: aprovada" in out
    texto = pymupdf.open(saida)[0].get_text()
    assert "529.982.247-25" not in texto and "[CPF]" in texto
    recibos = ler_historico()
    assert len(recibos) == 1 and recibos[0].modo == "cli-sem-revisao"


def test_lote_com_pasta_e_politica(pdfs, tmp_path, capsys):
    entrada = tmp_path / "entrada"
    entrada.mkdir()
    for nome in ("texto_nativo", "tabela", "multicolunas"):
        shutil.copy(pdfs[nome], entrada / f"{nome}.pdf")
    pol = Politica(tipos_personalizados=[TipoPersonalizado(nome="Matrícula", regex=r"MAT-\d{6}")])
    pol.tipos["TELEFONE"].ativo = False
    caminho_pol = tmp_path / "pol.yaml"
    salvar_politica(pol, caminho_pol)
    saida = tmp_path / "saida"
    assert main([str(entrada), "--pasta-saida", str(saida), "--sem-revisao", "--politica", str(caminho_pol)]) == OK
    gerados = sorted(p.name for p in saida.glob("*.pdf"))
    assert gerados == ["multicolunas_anonimizado.pdf", "tabela_anonimizado.pdf", "texto_nativo_anonimizado.pdf"]
    # Telefone desativado na política: continua no resultado.
    assert g.TEL_1 in pymupdf.open(saida / "tabela_anonimizado.pdf")[0].get_text()
    assert len(ler_historico()) == 3


def test_erros_de_uso(pdfs, tmp_path, capsys):
    assert main([]) == ERRO
    assert main([str(tmp_path / "nao_existe.pdf"), "--sem-revisao"]) == ERRO
    a = shutil.copy(pdfs["texto_nativo"], tmp_path / "a.pdf")
    b = shutil.copy(pdfs["tabela"], tmp_path / "b.pdf")
    assert main([str(a), str(b), "--saida", str(tmp_path / "x.pdf"), "--sem-revisao"]) == ERRO
    ruim = tmp_path / "ruim.yaml"
    ruim.write_text("tipos: {XYZ: {ativo: true}}", encoding="utf-8")
    assert main([str(a), "--politica", str(ruim)]) == ERRO
    assert "desconhecido" in capsys.readouterr().err


def test_nao_sobrescreve_original(pdfs, tmp_path):
    a = shutil.copy(pdfs["texto_nativo"], tmp_path / "a.pdf")
    antes = a.read_bytes() if hasattr(a, "read_bytes") else open(a, "rb").read()
    assert main([str(a), "--saida", str(a), "--sem-revisao"]) == ERRO
    assert open(a, "rb").read() == antes


def test_exporta_historico(pdfs, tmp_path, capsys):
    a = shutil.copy(pdfs["texto_nativo"], tmp_path / "a.pdf")
    main([str(a), "--sem-revisao"])
    csv = tmp_path / "h.csv"
    assert main(["--historico-csv", str(csv)]) == OK
    assert csv.read_text(encoding="utf-8-sig").count("\n") == 2


def test_codigo_de_falha_de_verificacao(pdfs, tmp_path, monkeypatch):
    import veu.core.redaction.aplicar as aplicar
    from veu.core.redaction.verificacao import Problema, ResultadoVerificacao

    monkeypatch.setattr(
        aplicar, "verificar", lambda *a, **k: ResultadoVerificacao(vazamentos=[Problema(0, "CPF", "teste")])
    )
    a = shutil.copy(pdfs["texto_nativo"], tmp_path / "a.pdf")
    assert main([str(a), "--sem-revisao"]) == FALHA_VERIFICACAO
