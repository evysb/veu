import csv
import json
import re

from tests.fixtures import gerar_pdfs as g
from veu.core.audit import criar_recibo, exportar_csv, ler_historico, pasta_auditoria, registrar, sha256_arquivo
from veu.core.models import Status
from veu.core.pipeline import analisar
from veu.core.policy import Politica
from veu.core.redaction import anonimizar
from veu.core.revisao import Revisao


def _anonimizar_com_recibo(pdf, tmp_path, politica=None):
    a = analisar(str(pdf), politica=politica)
    rev = Revisao(a)
    rev.aceitar_pendentes()
    email = next(d for d in a.deteccoes if d.tipo == "EMAIL")
    rev.definir_status([email.id], Status.REJEITADA)
    rev.adicionar_manual(0, (50, 50, 150, 70))
    rev.marcar_termo("Observações")
    saida = tmp_path / "laudo_anonimizado.pdf"
    r = anonimizar(a, str(saida))
    recibo = criar_recibo(a, r, rev, modo="interface")
    registrar(recibo)
    return a, r, recibo


def test_recibo_contem_o_que_foi_feito(pdfs, tmp_path):
    a, r, recibo = _anonimizar_com_recibo(pdfs["texto_nativo"], tmp_path)
    assert recibo.sha256_original == sha256_arquivo(pdfs["texto_nativo"])
    assert recibo.sha256_resultado == sha256_arquivo(r.caminho_saida)
    assert recibo.tarjas_por_tipo["CPF"] == 3
    assert recibo.total_tarjas == r.total_tarjas
    assert recibo.adicionadas_manualmente == 2  # caixa desenhada + termo marcado
    assert recibo.removidas_manualmente == 1  # e-mail rejeitado
    assert recibo.verificacao_ok is True
    assert recibo.usuario and recibo.data_hora
    assert recibo.estilo_tarja == "preta"


def test_recibo_nunca_contem_valores_tarjados(pdfs, tmp_path):
    _anonimizar_com_recibo(pdfs["prontuario"], tmp_path)
    conteudo = (pasta_auditoria() / "recibos.jsonl").read_text(encoding="utf-8")
    for valor in ["529.982.247-25", "52998224725", "Maria", "Fictícia", "Acácias", "98765", "metformina", "BRA2E19", "@"]:
        assert valor not in conteudo, valor
    # Por padrão, nem o nome dos arquivos (podem conter dados pessoais).
    assert "prontuario" not in conteudo and "laudo_anonimizado" not in conteudo


def test_nome_de_arquivo_so_com_permissao_da_politica(pdfs, tmp_path):
    p = Politica()
    p.auditoria.registrar_nome_arquivo = True
    _, _, recibo = _anonimizar_com_recibo(pdfs["texto_nativo"], tmp_path, politica=p)
    assert recibo.arquivo_original.endswith("texto_nativo.pdf")
    assert recibo.arquivo_resultado.endswith("laudo_anonimizado.pdf")


def test_historico_e_csv(pdfs, tmp_path):
    _anonimizar_com_recibo(pdfs["texto_nativo"], tmp_path)
    _anonimizar_com_recibo(pdfs["prontuario"], tmp_path)
    with open(pasta_auditoria() / "recibos.jsonl", "a", encoding="utf-8") as f:
        f.write("{linha corrompida\n")
    historico = ler_historico()
    assert len(historico) == 2

    csv_path = tmp_path / "historico.csv"
    exportar_csv(historico, csv_path)
    texto = csv_path.read_text(encoding="utf-8-sig")
    linhas = list(csv.reader(texto.splitlines(), delimiter=";"))
    cab = linhas[0]
    assert "SHA-256 original" in cab and "Tarjas CPF" in cab and "Tarjas NOME" in cab
    assert len(linhas) == 3
    assert linhas[1][cab.index("Verificação aprovada")] == "sim"
    assert not re.search(r"\d{3}\.\d{3}\.\d{3}-\d{2}", texto)


def test_jsonl_valido(pdfs, tmp_path):
    _anonimizar_com_recibo(pdfs["texto_nativo"], tmp_path)
    for linha in (pasta_auditoria() / "recibos.jsonl").read_text(encoding="utf-8").splitlines():
        dados = json.loads(linha)
        assert len(dados["sha256_original"]) == 64
