"""Ponta a ponta: o que foi tarjado não pode ser recuperado do PDF final."""

import hashlib
import re
import socket

import pymupdf
import pytest

from tests.fixtures import gerar_pdfs as g
from veu.core.models import Status
from veu.core.pipeline import analisar
from veu.core.redaction import (
    ArquivoOriginalProtegido,
    EstiloTarja,
    OpcoesAnonimizacao,
    anonimizar,
    caminho_saida_padrao,
)
from veu.core.revisao import Revisao

VALORES = [g.CPF_1, g.CPF_2, g.CPF_3, g.EMAIL_1, g.EMAIL_2, "987654321", "32741598", "998765432"]


def _hash(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()


def _tudo_que_da_para_extrair(caminho) -> str:
    """Texto, metadados, XMP, anotações, anexos, bookmarks e bytes brutos."""
    doc = pymupdf.open(caminho)
    partes = [p.get_text() for p in doc]
    partes += [p.get_text("rawdict").__repr__() for p in doc]
    partes += [str(doc.metadata), doc.get_xml_metadata() or "", str(doc.get_toc())]
    for p in doc:
        partes += [a.info.get("content", "") for a in p.annots()]
        partes += [str(w.field_value) for w in p.widgets()]
    partes += [doc.embfile_get(n).decode("latin-1") for n in doc.embfile_names()]
    doc.close()
    bruto = open(caminho, "rb").read()
    # Bytes descomprimidos de todos os streams
    doc = pymupdf.open(caminho)
    for xref in range(1, doc.xref_length()):
        try:
            if doc.xref_is_stream(xref):
                partes.append(doc.xref_stream(xref).decode("latin-1"))
            partes.append(doc.xref_object(xref))
        except Exception:
            pass
    doc.close()
    partes.append(bruto.decode("latin-1"))
    return "\n".join(partes)


def _valor_presente(valor: str, texto: str) -> bool:
    if "@" in valor:
        return valor.lower() in texto.lower()
    digitos = re.sub(r"\D", "", valor)
    return re.search(r"[\s.\-()]{0,2}".join(digitos), texto) is not None


@pytest.mark.parametrize("nome", ["texto_nativo", "multicolunas", "tabela", "quebra_de_linha", "rotacionado"])
@pytest.mark.parametrize("estilo", [EstiloTarja.PRETA, EstiloTarja.ROTULO])
def test_nada_tarjado_e_recuperavel(pdfs, tmp_path, nome, estilo):
    original = str(pdfs[nome])
    hash_antes = _hash(original)
    a = analisar(original)
    assert a.deteccoes
    presentes_antes = [v for v in VALORES if _valor_presente(v, "\n".join(p.texto for p in a.paginas))]
    assert presentes_antes
    Revisao(a).aceitar_pendentes()

    saida = str(tmp_path / f"{nome}_anonimizado.pdf")
    r = anonimizar(a, saida, OpcoesAnonimizacao(estilo=estilo))

    assert r.verificacao.ok, r.verificacao.vazamentos
    assert r.verificacao.residuais_novos == []
    conteudo = _tudo_que_da_para_extrair(saida)
    for v in presentes_antes:
        assert not _valor_presente(v, conteudo), f"{v} recuperável em {nome}"
    assert _hash(original) == hash_antes, "o original não pode ser alterado"


def test_limpeza_de_metadados_anotacoes_anexos_formularios(pdfs, tmp_path):
    a = analisar(str(pdfs["texto_nativo"]))
    Revisao(a).aceitar_pendentes()
    saida = str(tmp_path / "limpo.pdf")
    anonimizar(a, saida)
    doc = pymupdf.open(saida)
    assert not any(v for k, v in doc.metadata.items() if k not in ("format", "encryption"))
    assert not doc.get_xml_metadata()
    assert doc.embfile_count() == 0
    assert doc.get_toc() == []
    assert list(doc[0].annots()) == []
    assert list(doc[0].widgets()) == []
    assert "Maria" not in str(doc.metadata)


def test_rejeitadas_permanecem_e_nao_contam_como_vazamento(pdfs, tmp_path):
    a = analisar(str(pdfs["texto_nativo"]))
    rev = Revisao(a)
    email = next(d for d in a.deteccoes if d.tipo == "EMAIL")
    rev.aceitar_pendentes()
    rev.definir_status([email.id], Status.REJEITADA)
    saida = str(tmp_path / "rej.pdf")
    r = anonimizar(a, saida)
    assert r.verificacao.ok
    assert r.verificacao.residuais_rejeitados == 1
    assert g.EMAIL_1 in pymupdf.open(saida)[0].get_text()
    assert rev.removidas_manualmente == 1


def test_caixa_manual_e_busca_de_termo(pdfs, tmp_path):
    a = analisar(str(pdfs["texto_nativo"]))
    rev = Revisao(a)
    rev.aceitar_pendentes()
    novas = rev.marcar_termo("clínica exemplo")  # sem acento/caixa: casa "CLÍNICA EXEMPLO"
    assert len(novas) == 1
    pag = a.paginas[0]
    i = pag.texto.index("retorno em 30 dias")
    r0 = pag.rects_do_trecho(i, i + len("retorno em 30 dias"))[0]
    manual = rev.adicionar_manual(0, (r0[2] + 1, r0[3] + 1, r0[0] - 1, r0[1] - 1))  # desenhado "ao contrário"
    assert manual.trecho == "retorno em 30 dias"
    assert rev.adicionadas_manualmente == 2

    saida = str(tmp_path / "manual.pdf")
    r = anonimizar(a, saida)
    assert r.verificacao.ok
    texto = pymupdf.open(saida)[0].get_text()
    assert "CLÍNICA EXEMPLO" not in texto
    assert "retorno em 30 dias" not in texto
    assert "Paciente:" in texto and "Observações:" in texto  # vizinhos preservados


def test_nao_sobrescreve_original(pdfs):
    a = analisar(str(pdfs["texto_nativo"]))
    Revisao(a).aceitar_pendentes()
    with pytest.raises(ArquivoOriginalProtegido):
        anonimizar(a, str(pdfs["texto_nativo"]))


def test_nome_de_saida_padrao(tmp_path):
    entrada = tmp_path / "laudo.pdf"
    entrada.write_bytes(b"")
    assert caminho_saida_padrao(str(entrada)).endswith("laudo_anonimizado.pdf")
    (tmp_path / "laudo_anonimizado.pdf").write_bytes(b"")
    assert caminho_saida_padrao(str(entrada)).endswith("laudo_anonimizado_2.pdf")


def test_processamento_nao_usa_rede(pdfs, tmp_path, monkeypatch):
    """Qualquer tentativa de abrir conexão durante o processamento falha o teste."""

    def proibido(*args, **kwargs):
        raise AssertionError("Tentativa de acesso à rede durante o processamento!")

    import veu.core.detectors.nomes as nomes
    from veu.core.audit import criar_recibo, registrar

    # Recarrega o modelo de nomes do zero, já com a rede bloqueada.
    monkeypatch.setattr(nomes, "_nlp", None)
    monkeypatch.setattr(nomes, "_nlp_erro", None)
    monkeypatch.setattr(socket, "socket", proibido)
    monkeypatch.setattr(socket, "create_connection", proibido)
    monkeypatch.setattr(socket, "getaddrinfo", proibido)
    for nome in ("prontuario", "prontuario_escaneado"):  # NER + OCR
        a = analisar(str(pdfs[nome]))
        assert not any("não está disponível" in av for av in a.avisos), a.avisos
        rev = Revisao(a)
        rev.aceitar_pendentes()
        r = anonimizar(a, str(tmp_path / f"{nome}_offline.pdf"))
        assert r.verificacao.ok
        registrar(criar_recibo(a, r, rev))


def test_prontuario_completo_nada_recuperavel(pdfs, tmp_path):
    """Todos os tipos da etapa 2: nada do que foi tarjado pode ser extraído."""
    from tests.fixtures import dados as D

    a = analisar(str(pdfs["prontuario"]))
    tipos = {d.tipo for d in a.deteccoes}
    esperados = {
        "NOME", "CPF", "RG", "DATA_NASCIMENTO", "CNS", "PIS", "TITULO_ELEITOR", "CNH", "PASSAPORTE",
        "ENDERECO", "TELEFONE", "EMAIL", "PLACA", "SAUDE", "CRM", "CNPJ", "CONTA_BANCARIA", "PIX",
    }
    assert esperados <= tipos, esperados - tipos
    Revisao(a).aceitar_pendentes()
    saida = str(tmp_path / "prontuario_anonimizado.pdf")
    r = anonimizar(a, saida, OpcoesAnonimizacao(estilo=EstiloTarja.ROTULO))
    assert r.verificacao.ok, r.verificacao.vazamentos
    assert r.verificacao.residuais_novos == [], [(d.tipo, d.trecho) for d in r.verificacao.residuais_novos]

    texto = pymupdf.open(saida)[0].get_text()
    for valor in [
        "Maria Fictícia", "529.982.247-25", "12.345.678-9", "14/03/1985", D.CNH, "FZ123456",
        "Rua das Acácias", "04567-010", "BRA2E19", "metformina", "O24.4", "HIV", "CRM-SP 123456",
        "11.222.333/0001-81", "12.ABC.345/01DE-35", "98765-4", "123e4567-e89b", "Carlos Eduardo Souza",
    ]:
        assert valor not in texto, valor
    # Contexto neutro preservado
    assert "HISTÓRIA CLÍNICA" in texto and "laudo do exame" in texto
