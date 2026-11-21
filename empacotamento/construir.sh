#!/usr/bin/env bash
# Constrói o Véu para macOS: dist/Veu.app e dist/Veu-<versão>-macos-<arquitetura>.zip
#
# Uso, a partir da raiz do projeto:
#   bash empacotamento/construir.sh                 # completo
#   bash empacotamento/construir.sh --pular-testes
#
# O app gerado roda na mesma arquitetura da máquina que o construiu
# (arm64 = Apple Silicon, x86_64 = Intel) e exige macOS 13 ou mais novo.
set -euo pipefail

PULAR_TESTES=0
for arg in "$@"; do
    case "$arg" in
        --pular-testes) PULAR_TESTES=1 ;;
        *) echo "Opção desconhecida: $arg" >&2; exit 2 ;;
    esac
done

RAIZ="$(cd "$(dirname "$0")/.." && pwd)"
cd "$RAIZ"
PY="$RAIZ/.venv/bin/python"
[ -x "$PY" ] || { echo "Ambiente .venv não encontrado. Veja o README (Instalação)." >&2; exit 1; }

passo() { printf '\n\033[36m=== %s\033[0m\n' "$1"; }

passo "Modelos offline (OCR)"
"$PY" empacotamento/baixar_modelos.py

passo "Dependências de construção"
"$PY" -m pip install -q "pyinstaller>=6.10" pillow

if [ "$PULAR_TESTES" -eq 0 ]; then
    passo "Testes automatizados"
    "$PY" -m pytest -q -p no:cacheprovider
fi

passo "Ícone"
"$PY" empacotamento/gerar_icone.py

passo "PyInstaller"
"$PY" -m PyInstaller empacotamento/veu.spec --noconfirm --distpath dist --workpath build

APP="$RAIZ/dist/Veu.app"
[ -d "$APP" ] || { echo "PyInstaller não gerou $APP" >&2; exit 1; }

passo "Assinatura"
# Sem conta Apple Developer: assinatura "ad hoc" (obrigatória no Apple Silicon).
# Com um certificado "Developer ID Application", defina VEU_IDENTIDADE com o nome dele
# para assinar com hardened runtime (pré-requisito da notarização).
IDENTIDADE="${VEU_IDENTIDADE:-}"
if [ -z "$IDENTIDADE" ]; then
    codesign --force --deep --sign - "$APP"
    echo "assinatura ad hoc (sem Developer ID)"
else
    codesign --force --deep --options runtime --timestamp --sign "$IDENTIDADE" "$APP"
    echo "assinado com: $IDENTIDADE"
fi
codesign --verify --deep --strict "$APP"

passo "Teste do executável empacotado"
TESTE="$(mktemp -d -t veu_teste)"
trap 'rm -rf "$TESTE"' EXIT
"$PY" -m tests.fixtures.gerar_pdfs "$TESTE"
export VEU_AUDITORIA="$TESTE/auditoria"
export VEU_POLITICA="$TESTE/sem_politica.yaml"

"$APP/Contents/MacOS/anonimizar" "$TESTE/prontuario_completo.pdf" "$TESTE/prontuario_escaneado.pdf" \
    --pasta-saida "$TESTE/saida" --sem-revisao \
    || { echo "anonimizar falhou ($?)" >&2; exit 1; }

VEU_TESTE_INICIALIZACAO=1 "$APP/Contents/MacOS/Veu" "$TESTE/prontuario_completo.pdf" \
    || { echo "Veu.app não passou no teste de inicialização ($?)" >&2; exit 1; }
echo "Veu.app: ok"
unset VEU_AUDITORIA VEU_POLITICA

passo "Pacote .zip"
VERSAO="$("$PY" -c 'import veu; print(veu.__version__)')"
ARQ="$(uname -m)"
NOME="Veu-$VERSAO-macos-$ARQ"
PACOTE="$RAIZ/dist/$NOME"
rm -rf "$PACOTE" "$PACOTE.zip"
mkdir -p "$PACOTE"
ditto "$APP" "$PACOTE/Veu.app"
cp LEIA-ME.md docs/politica_exemplo.yaml "$PACOTE/"
# ditto preserva links simbólicos e a assinatura do app (o "zip" comum não).
ditto -c -k --sequesterRsrc --keepParent "$PACOTE" "$PACOTE.zip"
APP_MB="$(du -sm "$APP" | cut -f1)"
ZIP_MB="$(du -sm "$PACOTE.zip" | cut -f1)"
printf '\n\033[32mPronto: dist/Veu.app (%s MB) e dist/%s.zip (%s MB)\033[0m\n' "$APP_MB" "$NOME" "$ZIP_MB"
