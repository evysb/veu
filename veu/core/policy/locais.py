"""Onde a política fica gravada e qual delas vale.

Ordem de precedência:
1. variável de ambiente ``VEU_POLITICA`` (caminho de um arquivo);
2. política da organização **bloqueada** (``%PROGRAMDATA%\\Veu\\politica.yaml``);
3. política do usuário (``%APPDATA%\\Veu\\politica.yaml``);
4. política da organização não bloqueada (serve de ponto de partida);
5. política padrão embutida.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path

from veu.core.policy.modelo import Politica, PoliticaInvalida, carregar_politica, politica_padrao, salvar_politica


def caminho_usuario() -> Path:
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
        return base / "Veu" / "politica.yaml"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "Veu" / "politica.yaml"
    return Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "veu" / "politica.yaml"


def caminho_organizacao() -> Path:
    if sys.platform == "win32":
        return Path(os.environ.get("PROGRAMDATA", r"C:\ProgramData")) / "Veu" / "politica.yaml"
    if sys.platform == "darwin":
        return Path("/Library/Application Support/Veu/politica.yaml")
    return Path("/etc/veu/politica.yaml")


@dataclass
class OrigemPolitica:
    descricao: str  # texto para o usuário
    caminho: Path | None
    editavel: bool
    aviso: str | None = None  # ex.: arquivo com erro ignorado


def politica_ativa() -> tuple[Politica, OrigemPolitica]:
    avisos: list[str] = []

    def tentar(caminho: Path) -> Politica | None:
        if not caminho.exists():
            return None
        try:
            return carregar_politica(caminho)
        except PoliticaInvalida as e:
            avisos.append(f"Política ignorada ({caminho}): {e}")
            return None

    def aviso() -> str | None:
        return "\n".join(avisos) or None

    if os.environ.get("VEU_POLITICA"):
        p = Path(os.environ["VEU_POLITICA"])
        pol = tentar(p)
        if pol is not None:
            return pol, OrigemPolitica(f"definida em VEU_POLITICA ({p})", p, editavel=not pol.bloqueada, aviso=aviso())

    org = tentar(caminho_organizacao())
    if org is not None and org.bloqueada:
        return org, OrigemPolitica("da organização (bloqueada pelo TI)", caminho_organizacao(), editavel=False, aviso=aviso())

    usuario = tentar(caminho_usuario())
    if usuario is not None:
        return usuario, OrigemPolitica("do usuário", caminho_usuario(), editavel=True, aviso=aviso())
    if org is not None:
        return org, OrigemPolitica("da organização", caminho_organizacao(), editavel=True, aviso=aviso())
    return politica_padrao(), OrigemPolitica("padrão", None, editavel=True, aviso=aviso())


def salvar_politica_usuario(politica: Politica, origem: OrigemPolitica | None = None) -> Path:
    """Grava as alterações feitas na tela de configurações."""
    destino = origem.caminho if (origem and origem.caminho and os.environ.get("VEU_POLITICA")) else caminho_usuario()
    salvar_politica(politica, destino)
    return destino
