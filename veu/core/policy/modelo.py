"""Modelo da política (validado com pydantic) e leitura/gravação em YAML ou JSON."""

from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from veu.core.models import EstiloTarja, Vetores
from veu.core.tipos import tipos_detectaveis

VERSAO_ATUAL = 1
CONFIANCA_PADRAO = 0.5


class PoliticaInvalida(Exception):
    """Arquivo de política com erro. A mensagem já vem em português, pronta para o usuário."""


class ConfigTipo(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ativo: bool = True
    confianca_minima: float = Field(CONFIANCA_PADRAO, ge=0.0, le=1.0)


def _gerar_id(nome: str) -> str:
    sem_acento = unicodedata.normalize("NFKD", nome).encode("ascii", "ignore").decode()
    return re.sub(r"[^A-Z0-9]+", "_", sem_acento.upper()).strip("_")[:30] or "PERSONALIZADO"


class TipoPersonalizado(BaseModel):
    model_config = ConfigDict(extra="forbid")
    nome: str = Field(min_length=1, max_length=60)
    regex: str = Field(min_length=1)
    id: str = ""
    rotulo: str = ""
    cor: str = "#6C757D"
    ativo: bool = True
    ignorar_maiusculas: bool = False

    @field_validator("regex")
    @classmethod
    def _regex_valido(cls, v: str) -> str:
        try:
            r = re.compile(v)
        except re.error as e:
            raise ValueError(f"expressão regular inválida: {e}") from e
        if r.fullmatch(""):
            raise ValueError("a expressão aceita texto vazio; ela marcaria o documento inteiro")
        return v

    @field_validator("cor")
    @classmethod
    def _cor_valida(cls, v: str) -> str:
        if not re.fullmatch(r"#[0-9A-Fa-f]{6}", v):
            raise ValueError("cor deve estar no formato #RRGGBB")
        return v.upper()

    @model_validator(mode="after")
    def _preencher(self) -> "TipoPersonalizado":
        if not self.id:
            self.id = _gerar_id(self.nome)
        elif not re.fullmatch(r"[A-Z0-9_]{2,30}", self.id):
            raise ValueError("id deve ter de 2 a 30 caracteres: letras maiúsculas, números ou _")
        if not self.rotulo:
            self.rotulo = f"[{self.nome.upper()}]"
        return self


class ConfigTarja(BaseModel):
    model_config = ConfigDict(extra="forbid")
    estilo: EstiloTarja = EstiloTarja.PRETA
    vetores: Vetores = Vetores.COBERTOS


class ConfigOCR(BaseModel):
    model_config = ConfigDict(extra="forbid")
    #: Reconhecer texto em páginas escaneadas (sem camada de texto).
    ativo: bool = True
    dpi: int = Field(300, ge=150, le=600)


class ConfigAuditoria(BaseModel):
    model_config = ConfigDict(extra="forbid")
    #: Gravar um recibo (sem os dados tarjados) a cada anonimização.
    ativo: bool = True
    #: Nomes de arquivo podem conter dados pessoais ("laudo_maria.pdf");
    #: por padrão o recibo identifica os arquivos só pelo hash SHA-256.
    registrar_nome_arquivo: bool = False


def _tipos_padrao() -> dict[str, ConfigTipo]:
    return {t.id: ConfigTipo() for t in tipos_detectaveis()}


class Politica(BaseModel):
    model_config = ConfigDict(extra="forbid")

    versao: int = VERSAO_ATUAL
    nome: str = "Política padrão"
    #: Política da organização bloqueada: os usuários não podem alterá-la no programa.
    bloqueada: bool = False
    #: Reconhecimento de nomes com modelo de linguagem local (mais lento, mais preciso).
    usar_ner: bool = True
    tipos: dict[str, ConfigTipo] = Field(default_factory=_tipos_padrao)
    tipos_personalizados: list[TipoPersonalizado] = Field(default_factory=list)
    sempre_tarjar: list[str] = Field(default_factory=list)
    excecoes: list[str] = Field(default_factory=list)
    tarja: ConfigTarja = Field(default_factory=ConfigTarja)
    ocr: ConfigOCR = Field(default_factory=ConfigOCR)
    auditoria: ConfigAuditoria = Field(default_factory=ConfigAuditoria)

    @field_validator("sempre_tarjar", "excecoes")
    @classmethod
    def _limpar_listas(cls, v: list[str]) -> list[str]:
        vistos, saida = set(), []
        for termo in v:
            termo = " ".join(str(termo).split())
            if termo and termo.lower() not in vistos:
                vistos.add(termo.lower())
                saida.append(termo)
        return saida

    @model_validator(mode="after")
    def _validar(self) -> "Politica":
        if self.versao > VERSAO_ATUAL:
            raise ValueError(f"política da versão {self.versao}; esta versão do Véu entende até a {VERSAO_ATUAL}")
        conhecidos = {t.id for t in tipos_detectaveis()}
        ids_pers = [t.id for t in self.tipos_personalizados]
        if len(set(ids_pers)) != len(ids_pers):
            raise ValueError("há tipos personalizados com o mesmo id/nome")
        conflito = conhecidos & set(ids_pers)
        if conflito:
            raise ValueError(f"tipo personalizado com id de um tipo padrão: {', '.join(sorted(conflito))}")
        desconhecidos = set(self.tipos) - conhecidos - set(ids_pers)
        if desconhecidos:
            raise ValueError(f"tipo(s) desconhecido(s) em 'tipos': {', '.join(sorted(desconhecidos))}")
        for id_ in conhecidos - set(self.tipos):  # tipos novos em versões futuras
            self.tipos[id_] = ConfigTipo()
        return self

    # ---- consultas ------------------------------------------------------
    def tipo_ativo(self, id_tipo: str) -> bool:
        cfg = self.tipos.get(id_tipo)
        return cfg.ativo if cfg else True

    def confianca_minima(self, id_tipo: str) -> float:
        cfg = self.tipos.get(id_tipo)
        return cfg.confianca_minima if cfg else 0.0

    def para_dict(self) -> dict:
        return self.model_dump(mode="json")


def politica_padrao() -> Politica:
    return Politica()


def _mensagem_erro(e: ValidationError) -> str:
    linhas = []
    for err in e.errors():
        local = " → ".join(str(x) for x in err["loc"]) or "política"
        msg = err["msg"].removeprefix("Value error, ")
        traducoes = {
            "Extra inputs are not permitted": "campo desconhecido",
            "Field required": "campo obrigatório ausente",
            "Input should be a valid boolean": "deve ser true ou false",
            "Input should be a valid number": "deve ser um número",
            "Input should be a valid list": "deve ser uma lista",
            "Input should be a valid string": "deve ser um texto",
        }
        for en, pt in traducoes.items():
            msg = msg.replace(en, pt)
        linhas.append(f"• {local}: {msg}")
    return "\n".join(linhas)


def politica_de_dict(dados: dict) -> Politica:
    if not isinstance(dados, dict):
        raise PoliticaInvalida("O arquivo de política deve conter um objeto (chave: valor) na raiz.")
    try:
        return Politica.model_validate(dados)
    except ValidationError as e:
        raise PoliticaInvalida("A política tem erros:\n" + _mensagem_erro(e)) from e


def carregar_politica(caminho: str | Path) -> Politica:
    caminho = Path(caminho)
    try:
        texto = caminho.read_text(encoding="utf-8-sig")
    except OSError as e:
        raise PoliticaInvalida(f"Não foi possível ler {caminho}: {e}") from e
    try:
        if caminho.suffix.lower() == ".json":
            dados = json.loads(texto)
        else:
            dados = yaml.safe_load(texto) or {}
    except (json.JSONDecodeError, yaml.YAMLError) as e:
        raise PoliticaInvalida(f"Arquivo de política mal formatado ({caminho.name}):\n{e}") from e
    return politica_de_dict(dados)


def salvar_politica(politica: Politica, caminho: str | Path) -> None:
    caminho = Path(caminho)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    dados = politica.para_dict()
    if caminho.suffix.lower() == ".json":
        texto = json.dumps(dados, ensure_ascii=False, indent=2)
    else:
        cabecalho = (
            "# Política do Véu (anonimizador de PDF).\n"
            "# Edite pela tela Configurações ou manualmente; o arquivo é validado ao carregar.\n"
        )
        texto = cabecalho + yaml.safe_dump(dados, allow_unicode=True, sort_keys=False, width=100)
    temporario = caminho.with_suffix(caminho.suffix + ".tmp")
    temporario.write_text(texto, encoding="utf-8")
    temporario.replace(caminho)
