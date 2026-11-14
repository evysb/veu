from pathlib import Path

import pytest

from tests.fixtures import gerar_pdfs
from veu.core.policy import locais


@pytest.fixture(scope="session")
def pdfs(tmp_path_factory) -> dict[str, Path]:
    """Gera todos os PDFs sintéticos uma única vez por sessão de testes."""
    return gerar_pdfs.gerar_todos(tmp_path_factory.mktemp("pdfs"))


@pytest.fixture(autouse=True)
def politica_isolada(tmp_path, monkeypatch):
    """Nenhum teste lê ou grava a política nem a auditoria reais do usuário."""
    monkeypatch.delenv("VEU_POLITICA", raising=False)
    monkeypatch.setenv("VEU_AUDITORIA", str(tmp_path / "auditoria"))
    monkeypatch.setattr(locais, "caminho_usuario", lambda: tmp_path / "usuario" / "politica.yaml")
    monkeypatch.setattr(locais, "caminho_organizacao", lambda: tmp_path / "org" / "politica.yaml")
