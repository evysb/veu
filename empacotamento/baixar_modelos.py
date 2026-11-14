"""Baixa e confere os modelos usados offline pelo Véu.

Uso: python empacotamento/baixar_modelos.py

- veu/modelos/tessdata/por.traineddata  (Tesseract, tessdata_best, Apache-2.0)

O modelo de nomes (spaCy pt_core_news_md) é instalado pelo requirements.txt e
copiado para o executável pelo veu.spec.
Este script é a ÚNICA parte do projeto que acessa a internet, e só é usado na
preparação do ambiente — nunca durante o processamento de documentos.
"""

from __future__ import annotations

import hashlib
import sys
import urllib.request
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
MODELOS = [
    (
        "https://github.com/tesseract-ocr/tessdata_best/raw/main/por.traineddata",
        RAIZ / "veu" / "modelos" / "tessdata" / "por.traineddata",
        "711de9dbb8052067bd42f16b9119967f30bada80d57e2ef24f65d09f531adb04",
    ),
]


def sha256(caminho: Path) -> str:
    h = hashlib.sha256()
    with open(caminho, "rb") as f:
        for bloco in iter(lambda: f.read(1 << 20), b""):
            h.update(bloco)
    return h.hexdigest()


def main() -> int:
    for url, destino, esperado in MODELOS:
        if destino.exists() and sha256(destino) == esperado:
            print(f"ok      {destino.relative_to(RAIZ)}")
            continue
        destino.parent.mkdir(parents=True, exist_ok=True)
        print(f"baixando {url}")
        temporario = destino.with_suffix(".tmp")
        urllib.request.urlretrieve(url, temporario)
        obtido = sha256(temporario)
        if obtido != esperado:
            temporario.unlink()
            print(f"ERRO: SHA-256 não confere para {destino.name}\n  esperado {esperado}\n  obtido   {obtido}")
            return 1
        temporario.replace(destino)
        print(f"ok      {destino.relative_to(RAIZ)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
