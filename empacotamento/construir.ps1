# Constrói o Véu para Windows: dist\Veu\ (Veu.exe + anonimizar.exe) e dist\Veu-<versão>-windows.zip
#
# Uso, a partir da raiz do projeto:
#   powershell -ExecutionPolicy Bypass -File empacotamento\construir.ps1            # completo
#   powershell -ExecutionPolicy Bypass -File empacotamento\construir.ps1 -PularTestes
param([switch]$PularTestes)

$ErrorActionPreference = "Stop"
$Raiz = Split-Path -Parent $PSScriptRoot
Set-Location $Raiz
$Py = Join-Path $Raiz ".venv\Scripts\python.exe"
if (-not (Test-Path $Py)) { throw "Ambiente .venv não encontrado. Veja o README (Instalação)." }

function Passo($texto) { Write-Host "`n=== $texto" -ForegroundColor Cyan }
function Executar($exe, [string[]]$argumentos) {
    & $exe @argumentos
    if ($LASTEXITCODE -ne 0) { throw "Falhou ($LASTEXITCODE): $exe $argumentos" }
}

Passo "Modelos offline (OCR)"
Executar $Py @("empacotamento\baixar_modelos.py")

Passo "Dependências de construção"
Executar $Py @("-m", "pip", "install", "-q", "pyinstaller>=6.10", "pillow")

if (-not $PularTestes) {
    Passo "Testes automatizados"
    Executar $Py @("-m", "pytest", "-q", "-p", "no:cacheprovider")
}

Passo "Ícone"
Executar $Py @("empacotamento\gerar_icone.py")

Passo "PyInstaller"
Executar $Py @("-m", "PyInstaller", "empacotamento\veu.spec", "--noconfirm", "--distpath", "dist", "--workpath", "build")

Passo "Teste do executável empacotado"
$Teste = Join-Path $env:TEMP ("veu_teste_" + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Force $Teste | Out-Null
Executar $Py @("-m", "tests.fixtures.gerar_pdfs", $Teste)
$env:VEU_AUDITORIA = Join-Path $Teste "auditoria"
$env:VEU_POLITICA = Join-Path $Teste "sem_politica.yaml"
try {
    $Cli = Join-Path $Raiz "dist\Veu\anonimizar.exe"
    & $Cli (Join-Path $Teste "prontuario_completo.pdf") (Join-Path $Teste "prontuario_escaneado.pdf") --pasta-saida (Join-Path $Teste "saida") --sem-revisao
    if ($LASTEXITCODE -ne 0) { throw "anonimizar.exe falhou ($LASTEXITCODE)" }

    $env:VEU_TESTE_INICIALIZACAO = "1"
    $Gui = Start-Process -FilePath (Join-Path $Raiz "dist\Veu\Veu.exe") -ArgumentList "`"$(Join-Path $Teste 'prontuario_completo.pdf')`"" -PassThru -Wait
    if ($Gui.ExitCode -ne 0) { throw "Veu.exe não passou no teste de inicialização ($($Gui.ExitCode))" }
    Write-Host "Veu.exe: ok"
} finally {
    Remove-Item Env:VEU_TESTE_INICIALIZACAO, Env:VEU_AUDITORIA, Env:VEU_POLITICA -ErrorAction SilentlyContinue
    Remove-Item -Recurse -Force $Teste -ErrorAction SilentlyContinue
}

Passo "Pacote .zip"
$Versao = & $Py -c "import veu; print(veu.__version__)"
Copy-Item LEIA-ME.md (Join-Path $Raiz "dist\Veu\LEIA-ME.md") -Force
Copy-Item docs\politica_exemplo.yaml (Join-Path $Raiz "dist\Veu\politica_exemplo.yaml") -Force
$Zip = Join-Path $Raiz "dist\Veu-$Versao-windows.zip"
if (Test-Path $Zip) { Remove-Item $Zip -Force }
Compress-Archive -Path (Join-Path $Raiz "dist\Veu") -DestinationPath $Zip -CompressionLevel Optimal
$Mb = [math]::Round((Get-Item $Zip).Length / 1MB)
$PastaMb = [math]::Round(((Get-ChildItem -Recurse (Join-Path $Raiz "dist\Veu") | Measure-Object Length -Sum).Sum) / 1MB)
Write-Host "`nPronto: dist\Veu ($PastaMb MB) e $Zip ($Mb MB)" -ForegroundColor Green
