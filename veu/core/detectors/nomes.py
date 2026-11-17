"""Nomes de pessoas: NER local (spaCy) + listas de prenomes/sobrenomes + contexto.

A pontuação combina três sinais:
- listas: o nome começa por um prenome conhecido, seguido de sobrenomes;
- contexto: gatilhos como "Sr.", "paciente", "nome:", "assinado por";
- NER: o modelo de português reconheceu a entidade como pessoa (PER).
Sem o modelo de NER, o detector continua funcionando só com listas e contexto.
"""

from __future__ import annotations

import os
import re
import sys
import threading
from pathlib import Path

from veu.core.busca import normalizar_preservando_posicoes
from veu.core.detectors.base import Detector, contexto_antes, tem_palavra_chave
from veu.core.detectors.dicionarios import conjunto_normalizado
from veu.core.models import Achado

MODELO_PADRAO = "pt_core_news_md"

_RE_PALAVRA = re.compile(r"[A-Za-zÀ-ÖØ-öø-ÿ][A-Za-zÀ-ÖØ-öø-ÿ'’]*(?:-[A-Za-zÀ-ÖØ-öø-ÿ]+)*")
_CONECTORES = {"da", "de", "do", "das", "dos", "e", "d'", "di", "del", "van", "von", "la"}
_TITULOS = {"sr", "sra", "srta", "dr", "dra", "prof", "profa", "dom", "padre", "pastor", "me", "mestre", "eng", "adv"}
_GATILHOS = (
    "sr.", "sra.", "srta.", "sr", "sra", "dr.", "dra.", "dr", "dra", "paciente", "nome", "nome completo",
    "assinado por", "assinado digitalmente por", "assinatura", "responsavel", "mae", "pai", "genitor",
    "genitora", "filho", "filha", "irmao", "irma", "neto", "neta", "sobrinho", "sobrinha", "cliente", "requerente", "requerido", "interessado", "interessada", "testemunha",
    "declarante", "acompanhante", "filho de", "filha de", "esposo", "esposa", "conjuge", "medico",
    "medica", "enfermeiro", "enfermeira", "solicitante", "beneficiario", "titular", "portador", "portadora",
    "aluno", "aluna", "servidor", "servidora", "funcionario", "funcionaria", "autor", "autora", "reu", "re",
)
# Palavras que, logo antes de um "nome", indicam lugar/instituição ("Rua João…", "Hospital São Lucas").
_PRECEDE_LUGAR = {
    "sao", "santa", "santo", "rua", "r", "av", "avenida", "travessa", "alameda", "praca", "largo", "rodovia",
    "estrada", "hospital", "clinica", "escola", "colegio", "instituto", "fundacao", "universidade", "faculdade",
    "edificio", "condominio", "bairro", "vila", "jardim", "parque", "igreja", "paroquia", "capela", "centro",
    "unidade", "policlinica", "ubs", "upa", "posto", "shopping", "ponte", "viaduto", "residencial", "conjunto",
    "projeto", "programa", "lei", "premio", "estadio", "aeroporto", "teatro", "museu", "biblioteca", "empresa",
}
# Palavras capitalizadas que encerram um nome (rótulos de campos em formulários).
_PARADAS = {
    "cpf", "rg", "cnpj", "cns", "crm", "cro", "tel", "telefone", "fone", "celular", "email", "e-mail",
    "rua", "av", "avenida", "data", "nascimento", "endereco", "paciente", "nome", "idade", "sexo", "cep",
    "cidade", "estado", "bairro", "profissao", "naturalidade", "nacionalidade", "estado civil", "convenio",
    "prontuario", "matricula", "registro", "assinatura", "documento", "observacoes", "obs", "diagnostico",
    "mae", "pai", "responsavel", "sr", "sra", "dr", "dra", "hospital", "clinica", "laudo", "exame",
}


def _eh_parada(palavra_normalizada: str) -> bool:
    """Rótulo de campo, inclusive com hífen ("CRM-SP", "RG-SSP")."""
    return palavra_normalizada in _PARADAS or palavra_normalizada.split("-", 1)[0] in _PARADAS


# --------------------------------------------------------------------- NER
_nlp = None
_nlp_erro: str | None = None
_nlp_lock = threading.Lock()


def _caminhos_modelo() -> list[str]:
    candidatos = []
    if os.environ.get("VEU_MODELO_NER"):
        candidatos.append(os.environ["VEU_MODELO_NER"])
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[2]))  # executável PyInstaller
    for raiz in (base, base / "veu"):
        local = raiz / "modelos" / MODELO_PADRAO
        if local.exists():
            candidatos.append(str(local))
    candidatos.append(MODELO_PADRAO)
    return candidatos


def carregar_ner():
    """Carrega o modelo uma vez por processo. Devolve ``None`` se indisponível."""
    global _nlp, _nlp_erro
    with _nlp_lock:
        if _nlp is not None or _nlp_erro is not None:
            return _nlp
        try:
            import spacy
        except Exception as e:  # spaCy não instalado
            _nlp_erro = f"spaCy indisponível ({e})"
            return None
        excluir = ["parser", "lemmatizer", "morphologizer", "attribute_ruler", "senter", "tagger"]
        for caminho in _caminhos_modelo():
            try:
                _nlp = spacy.load(caminho, exclude=excluir)
                _nlp.max_length = 2_000_000
                return _nlp
            except Exception as e:
                _nlp_erro = f"modelo de NER não encontrado ({e})"
        return None


def erro_ner() -> str | None:
    return _nlp_erro


# --------------------------------------------------------------- detector
class DetectorNome(Detector):
    tipo = "NOME"
    prioridade = 50

    def __init__(self, usar_ner: bool = True) -> None:
        self.usar_ner = usar_ner
        self._prenomes = conjunto_normalizado("prenomes.txt")
        self._sobrenomes = conjunto_normalizado("sobrenomes.txt")
        self._cache_ner: dict[str, list[tuple[int, int]]] = {}
        self.ner_disponivel = False

    # ---- NER em lote ----------------------------------------------------
    def preparar(self, textos: list[str]) -> None:
        if not self.usar_ner:
            return
        nlp = carregar_ner()
        self.ner_disponivel = nlp is not None
        if nlp is None:
            return
        pendentes = [t for t in dict.fromkeys(textos) if t.strip() and t not in self._cache_ner]
        for texto, doc in zip(pendentes, nlp.pipe(pendentes, batch_size=16)):
            self._cache_ner[texto] = [(e.start_char, e.end_char) for e in doc.ents if e.label_ == "PER"]

    def _entidades(self, texto: str) -> list[tuple[int, int]]:
        if not self.usar_ner:
            return []
        if texto not in self._cache_ner:
            self.preparar([texto])
        return self._cache_ner.get(texto, [])

    # ---- detecção -------------------------------------------------------
    def detectar(self, texto: str) -> list[Achado]:
        tokens = [(m.start(), m.end(), m.group(0)) for m in _RE_PALAVRA.finditer(texto)]
        norm = [normalizar_preservando_posicoes(t[2]) for t in tokens]
        entidades = self._entidades(texto)
        candidatos: list[tuple[int, int, float, bool]] = []  # início, fim, confiança, palavra única

        cobertos_ate = -1
        i = 0
        while i < len(tokens):
            if tokens[i][0] < cobertos_ate or not self._inicia_nome(tokens, norm, i):
                i += 1
                continue
            fim_idx = self._estender(texto, tokens, norm, i)
            palavras = [k for k in range(i, fim_idx + 1) if norm[k] not in _CONECTORES]
            n_sobrenomes = sum(1 for k in palavras[1:] if norm[k] in self._sobrenomes)
            ini, fim = tokens[i][0], tokens[fim_idx][1]
            if len(palavras) == 1:
                conf = 0.35
            elif n_sobrenomes:
                conf = 0.8
            else:
                conf = 0.6
            candidatos.append((ini, fim, conf, len(palavras) == 1))
            cobertos_ate = fim
            i = fim_idx + 1

        # Entidades do NER que não começam por um prenome conhecido.
        for e_ini, e_fim in entidades:
            if any(not (e_fim <= c[0] or e_ini >= c[1]) for c in candidatos):
                continue
            e_ini = self._remover_titulo(texto, e_ini, e_fim)
            idx = [k for k, t in enumerate(tokens) if t[0] >= e_ini and t[1] <= e_fim]
            palavras = [k for k in idx if norm[k] not in _CONECTORES]
            if not palavras or any(not tokens[k][2][0].isupper() for k in palavras):
                continue
            if any(_eh_parada(norm[k]) for k in palavras) or self._precedido_por_lugar(tokens, norm, idx[0]):
                continue
            conf = 0.55 if len(palavras) >= 2 else 0.3
            if any(norm[k] in self._sobrenomes for k in palavras):
                conf += 0.1
            candidatos.append((tokens[idx[0]][0], tokens[idx[-1]][1], conf, len(palavras) == 1))

        achados = []
        for ini, fim, conf, palavra_unica in candidatos:
            gatilho = tem_palavra_chave(self._contexto_da_frase(texto, ini), _GATILHOS)
            if gatilho:
                conf += 0.3 if conf < 0.5 else 0.15
            if any(not (fim <= e0 or ini >= e1) for e0, e1 in entidades):
                conf += 0.15
            if palavra_unica and not gatilho:
                conf = min(conf, 0.45)  # "Rosa", "Glória"… sozinhos são ambíguos demais
            achados.append(self._achado(ini, fim, conf))
        return achados

    @staticmethod
    def _contexto_da_frase(texto: str, ini: int) -> str:
        """Até 30 caracteres antes do nome, sem atravessar fim de frase ou de linha.

        Pontos de abreviações de tratamento ("Sr.", "Dra.") não encerram a frase.
        """
        ctx = contexto_antes(texto, ini, 30)
        corte = 0
        for m in re.finditer(r"[.;!?](?=\s)|\n", ctx):
            if m.group(0) == ".":
                palavra = re.search(r"([a-z]+)$", ctx[:m.start()])
                if palavra and palavra.group(1) in _TITULOS:
                    continue
            corte = m.end()
        return ctx[corte:]

    def _inicia_nome(self, tokens, norm, i: int) -> bool:
        palavra = tokens[i][2]
        return (
            len(palavra) >= 2
            and palavra[0].isupper()
            and norm[i] in self._prenomes
            and not self._precedido_por_lugar(tokens, norm, i)
        )

    def _precedido_por_lugar(self, tokens, norm, i: int) -> bool:
        return i > 0 and norm[i - 1] in _PRECEDE_LUGAR and tokens[i][0] - tokens[i - 1][1] <= 3

    def _estender(self, texto: str, tokens, norm, i: int) -> int:
        """Avança enquanto houver palavras capitalizadas ou conectores do nome."""
        fim = i
        k = i + 1
        while k < len(tokens) and k - i < 8:
            entre = texto[tokens[k - 1][1]:tokens[k][0]]
            if entre.strip() not in ("",):
                break
            if "\n" in entre and norm[k] not in self._sobrenomes and norm[k] not in _CONECTORES:
                break  # nova linha só continua o nome se for sobrenome conhecido
            palavra = tokens[k][2]
            if norm[k] in _CONECTORES:
                if k + 1 < len(tokens) and tokens[k + 1][2][0].isupper() and texto[tokens[k][1]:tokens[k + 1][0]].strip() == "":
                    k += 1
                    continue
                break
            if palavra[0].isupper() and len(palavra) >= 2 and not _eh_parada(norm[k]):
                fim = k
                k += 1
                continue
            break
        return fim

    def _remover_titulo(self, texto: str, ini: int, fim: int) -> int:
        m = re.match(r"((?:[A-Za-z]{1,6}\.?\s+)+)", texto[ini:fim])
        if m:
            palavras = m.group(1).split()
            pular = 0
            for p in palavras:
                if normalizar_preservando_posicoes(p.rstrip(".")) in _TITULOS:
                    pular += len(p)
                    pular += len(texto[ini + pular:]) - len(texto[ini + pular:].lstrip())
                else:
                    break
            return ini + pular
        return ini
