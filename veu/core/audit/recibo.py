"""Recibos de auditoria das anonimizações.

O recibo registra o QUE foi feito (quantas tarjas de cada tipo, quem, quando,
hashes dos arquivos, resultado da verificação), mas NUNCA os valores tarjados.
Fica num arquivo JSON Lines local (uma anonimização por linha), exportável
para CSV.
"""

from __future__ import annotations

import csv
import getpass
import hashlib
import json
import os
import platform
import sys
import uuid
from collections import Counter
from dataclasses import asdict, dataclass, field, fields
from datetime import datetime
from pathlib import Path

from veu import __version__

ARQUIVO = "recibos.jsonl"


def pasta_auditoria() -> Path:
    if os.environ.get("VEU_AUDITORIA"):
        return Path(os.environ["VEU_AUDITORIA"])
    if sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
        return base / "Veu" / "auditoria"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "Veu" / "auditoria"
    return Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")) / "veu" / "auditoria"


def sha256_arquivo(caminho: str | Path) -> str:
    h = hashlib.sha256()
    with open(caminho, "rb") as f:
        for bloco in iter(lambda: f.read(1 << 20), b""):
            h.update(bloco)
    return h.hexdigest()


@dataclass
class Recibo:
    id: str
    data_hora: str  # ISO 8601 com fuso
    usuario: str
    maquina: str
    versao_veu: str
    modo: str  # "interface" | "cli" | "cli-sem-revisao"
    politica: str
    sha256_original: str
    sha256_resultado: str
    paginas: int
    paginas_ocr: int
    tarjas_por_tipo: dict[str, int]
    total_tarjas: int
    adicionadas_manualmente: int
    removidas_manualmente: int
    estilo_tarja: str
    verificacao_ok: bool | None
    vazamentos: int
    residuais_novos: int
    # Só preenchidos se a política permitir (nomes podem conter dados pessoais).
    arquivo_original: str = ""
    arquivo_resultado: str = ""
    # Estilo "pessoas": só QUANTAS pessoas receberam rótulo ([P1]…), nunca quem.
    pessoas_rotuladas: int = 0
    extras: dict = field(default_factory=dict)


def criar_recibo(analise, resultado, revisao=None, modo: str = "interface") -> Recibo:
    """Monta o recibo a partir da análise, do resultado e da revisão (sem valores)."""
    politica = analise.politica
    registrar_nomes = bool(politica and politica.auditoria.registrar_nome_arquivo)
    v = resultado.verificacao
    contagem = Counter(resultado.tarjas_por_tipo)
    return Recibo(
        id=uuid.uuid4().hex,
        data_hora=datetime.now().astimezone().isoformat(timespec="seconds"),
        usuario=getpass.getuser(),
        maquina=platform.node(),
        versao_veu=__version__,
        modo=modo,
        politica=politica.nome if politica else "padrão",
        sha256_original=getattr(analise, "sha256_original", "") or sha256_arquivo(analise.caminho),
        sha256_resultado=sha256_arquivo(resultado.caminho_saida),
        paginas=analise.num_paginas,
        paginas_ocr=sum(1 for p in analise.paginas if p.origem == "ocr"),
        tarjas_por_tipo=dict(sorted(contagem.items())),
        total_tarjas=sum(contagem.values()),
        adicionadas_manualmente=revisao.adicionadas_manualmente if revisao else 0,
        removidas_manualmente=revisao.removidas_manualmente if revisao else 0,
        estilo_tarja=getattr(resultado, "estilo", ""),
        verificacao_ok=v.ok if v else None,
        vazamentos=len(v.vazamentos) if v else 0,
        residuais_novos=len(v.residuais_novos) if v else 0,
        arquivo_original=os.path.abspath(analise.caminho) if registrar_nomes else "",
        arquivo_resultado=os.path.abspath(resultado.caminho_saida) if registrar_nomes else "",
        pessoas_rotuladas=getattr(resultado, "pessoas", 0),
    )


def registrar(recibo: Recibo, pasta: Path | None = None) -> Path:
    pasta = pasta or pasta_auditoria()
    pasta.mkdir(parents=True, exist_ok=True)
    caminho = pasta / ARQUIVO
    with open(caminho, "a", encoding="utf-8") as f:
        f.write(json.dumps(asdict(recibo), ensure_ascii=False) + "\n")
    return caminho


def ler_historico(pasta: Path | None = None) -> list[Recibo]:
    caminho = (pasta or pasta_auditoria()) / ARQUIVO
    if not caminho.exists():
        return []
    nomes = {f.name for f in fields(Recibo)}
    recibos = []
    with open(caminho, encoding="utf-8") as f:
        for linha in f:
            try:
                dados = json.loads(linha)
                recibos.append(Recibo(**{k: v for k, v in dados.items() if k in nomes}))
            except (json.JSONDecodeError, TypeError):
                continue  # linha corrompida: ignora sem perder o resto
    return recibos


_COLUNAS = [
    ("data_hora", "Data/hora"),
    ("usuario", "Usuário"),
    ("maquina", "Máquina"),
    ("modo", "Modo"),
    ("politica", "Política"),
    ("arquivo_original", "Arquivo original"),
    ("arquivo_resultado", "Arquivo anonimizado"),
    ("sha256_original", "SHA-256 original"),
    ("sha256_resultado", "SHA-256 resultado"),
    ("paginas", "Páginas"),
    ("paginas_ocr", "Páginas com OCR"),
    ("total_tarjas", "Total de tarjas"),
    ("adicionadas_manualmente", "Adicionadas manualmente"),
    ("removidas_manualmente", "Removidas manualmente"),
    ("estilo_tarja", "Estilo da tarja"),
    ("pessoas_rotuladas", "Pessoas rotuladas"),
    ("verificacao_ok", "Verificação aprovada"),
    ("vazamentos", "Vazamentos"),
    ("residuais_novos", "Possíveis dados sem tarja"),
    ("versao_veu", "Versão do Véu"),
    ("id", "ID do recibo"),
]


def exportar_csv(recibos: list[Recibo], caminho: str | Path) -> None:
    """CSV com ';' e UTF-8 com BOM (abre direto no Excel em português)."""
    tipos = sorted({t for r in recibos for t in r.tarjas_por_tipo})
    with open(caminho, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow([titulo for _, titulo in _COLUNAS] + [f"Tarjas {t}" for t in tipos])
        for r in recibos:
            linha = []
            for campo, _ in _COLUNAS:
                valor = getattr(r, campo)
                if isinstance(valor, bool):
                    valor = "sim" if valor else "não"
                elif valor is None:
                    valor = ""
                linha.append(valor)
            w.writerow(linha + [r.tarjas_por_tipo.get(t, 0) for t in tipos])
