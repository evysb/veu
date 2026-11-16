# Véu — anonimizador de PDF 100% offline

O Véu encontra dados pessoais em PDFs, deixa você revisar cada marcação e gera
uma cópia anonimizada com **remoção real** do conteúdo tarjado. Todo o
processamento acontece no seu computador: o PDF e o texto dele nunca são
enviados para a internet. Não há chamadas de rede, telemetria nem IA na nuvem.

Recursos:

- 18 tipos de dado detectados, com nomes reconhecidos por um modelo de
  linguagem que roda localmente;
- **OCR local** para PDFs escaneados;
- política configurável pelo TI;
- verificação automática do resultado;
- recibos de auditoria;
- linha de comando para lotes.

---

## Instalação

### Para usar (Windows)

1. Descompacte `Veu-<versão>-windows.zip` em uma pasta, por exemplo
   `C:\Programas\Veu`.
2. Abra `Veu.exe`.

Não precisa de Python, de internet nem de permissão de administrador. O OCR e o
modelo de reconhecimento de nomes já vêm dentro da pasta. Para o atalho no menu
Iniciar, crie um atalho para `Veu.exe`.

### Para desenvolver

Requisitos: Python 3.11 ou mais recente (64 bits).

```powershell
cd anonimizacao_lgpd
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pip install -e .
.\.venv\Scripts\python.exe empacotamento\baixar_modelos.py
```

A preparação é a **única etapa que usa a internet**. Ela baixa:

- o modelo de português do spaCy (`pt_core_news_md`, cerca de 40 MB), usado para
  reconhecer nomes;
- o arquivo de idioma do OCR (`por.traineddata`, 8 MB), cujo SHA-256 é
  conferido.

Depois disso, tudo funciona offline.

## Como usar

```powershell
Veu.exe                                       # versão empacotada
.\.venv\Scripts\python.exe -m veu laudo.pdf  # versão de desenvolvimento, já abrindo um arquivo
```

1. **Abrir:** clique em *Abrir PDF…* ou arraste o arquivo para a janela.
2. **Detectar:** o Véu analisa o documento e desenha caixas coloridas sobre os
   dados encontrados (uma cor por tipo). Caixas **tracejadas** estão
   pendentes, **cheias** estão aceitas e **cinza pontilhadas** foram rejeitadas.
3. **Revisar (obrigatório):**
   - clique numa caixa (ou numa linha da lista à direita) e tecle **A** para
     aceitar ou **R** para rejeitar; o botão direito abre mais opções, como
     *Marcar todas as ocorrências* do mesmo trecho;
   - **Desenhar caixa (D):** arraste sobre a página para tarjar algo que o
     programa não detectou; **Del** apaga uma marcação manual;
   - **Buscar termo → Marcar todas:** marca todas as ocorrências de um nome,
     projeto etc. (ignora maiúsculas e acentos);
   - a lista lateral filtra por tipo e status e permite aceitar ou rejeitar em
     lote ("todas da lista" age sobre o que o filtro mostra);
   - navegue com **PgUp/PgDown**; zoom com **Ctrl + roda do mouse**,
     **Ctrl+/Ctrl−** e **Ctrl+0** (ajustar à largura).
4. **Anonimizar:** *Anonimizar e salvar…* (Ctrl+S). Escolha o estilo da tarja
   (preta lisa; com rótulo, como `[CPF]`, `[NOME]`, `[SAÚDE]`; ou com rótulo e
   pessoas numeradas, veja abaixo) e confirme que revisou o documento.
5. **Salvar:** o padrão é `arquivo_anonimizado.pdf` na mesma pasta. **O original
   nunca é sobrescrito.**

Ao final, o Véu **reabre o PDF gerado**, confirma que nada do que foi tarjado
pode ser extraído e roda os detectores outra vez para apontar dados que tenham
ficado sem tarja.

### Pessoas numeradas (`[P1]`, `[P2]`…)

No estilo *Tipo do dado, com cada pessoa numerada*, todas as ocorrências da
mesma pessoa recebem o mesmo rótulo. Assim o texto continua legível
(“[P1] relata que [P2]…”) sem revelar quem é quem. Os demais dados mantêm o
rótulo do tipo (`[CPF]`, `[SAÚDE]`…).

- Variações do nome são agrupadas automaticamente, ignorando acentos,
  maiúsculas, pronomes de tratamento (“Sr.”, “Dra.”) e conectores (“da”,
  “dos”): “Maria Aparecida Souza”, “Sra. Souza” e “MARIA APARECIDA DE SOUZA”
  viram `[P1]`. Um nome parcial que pode ser de mais de uma pessoa (“Maria”,
  havendo “Maria Souza” e “Maria Lima”) ganha um rótulo próprio.
- A numeração segue a ordem da primeira aparição e conta só os nomes que serão
  tarjados. A coluna *Pessoa* da lista lateral mostra o rótulo de cada nome.
- Com o botão direito sobre um ou mais nomes (na página ou na lista):
  **Renomear pessoa…** (ex.: `[PACIENTE]`, vale para todas as ocorrências;
  rótulos com parte do nome da pessoa são recusados),
  **Juntar como a mesma pessoa** ou **Separar como outra pessoa**.
- A ligação entre rótulos e nomes existe só na memória durante a revisão.
  Ela nunca é gravada no PDF, no recibo de auditoria nem em outro lugar.

Nomes marcados por *Buscar termo → Marcar todas* ou pela lista *Sempre tarjar*
são do tipo “Termo marcado” e continuam com o rótulo `[TARJA]`.

### O que a anonimização faz

- Remove de fato o texto sob a tarja; copiar e colar, buscar ou extrair não
  recupera o valor. O texto que fica fora da tarja não se move.
- Apaga os pixels de imagens sob a tarja e remove os desenhos vetoriais
  cobertos por ela. Há uma opção mais agressiva, que remove qualquer desenho que
  toque a tarja, mas ela pode apagar linhas de tabelas.
- Remove metadados (autor, título, XMP), comentários e anotações, campos de
  formulário, anexos embutidos, marcadores (bookmarks), links, JavaScript e
  texto invisível. Camadas ocultas (OCG) são tornadas visíveis já na análise, de
  modo que o conteúdo delas também passa pela detecção.
- Salva o arquivo sem objetos órfãos e sem senha.

## O que é detectado

| Tipo | Como detecta |
|---|---|
| **CPF** | com e sem máscara (também quebrado entre linhas), dígitos verificadores validados |
| **CNPJ** | numérico e **alfanumérico** (novo formato da Receita), dígitos verificadores validados |
| **RG** | formatos variados, só perto de “RG”, “Identidade”, “SSP”… ou do órgão emissor |
| **CNH** | 11 dígitos validados, perto de “CNH”/“habilitação” |
| **Título de eleitor** | dígitos verificadores e UF validados |
| **PIS/PASEP/NIS** | dígito verificador validado |
| **Cartão SUS (CNS)** | 15 dígitos, validação oficial (definitivo e provisório) |
| **Passaporte** | perto de “passaporte” |
| **Nome de pessoa** | modelo de linguagem local (spaCy) + listas de prenomes e sobrenomes + contexto (“Sr.”, “paciente”, “nome:”, “assinado por”…) |
| **Endereço/CEP** | logradouro, número, complemento, bairro, cidade/UF e CEP; também o texto após “Endereço:” e “residente na” |
| **Telefone** | fixo e celular, com ou sem DDD (validado) e +55 |
| **E-mail** | formato de endereço de e-mail |
| **Data de nascimento** | datas perto de “nascimento”, “DN”, “nascido em”… |
| **Placa de veículo** | modelo antigo e Mercosul |
| **Dado de saúde** (desligado por padrão) | CID-10 (após “CID” ou com contexto clínico), doenças e condições sensíveis, medicamentos |
| **Registro profissional** | CRM, CRO, COREN, CRP, CRF… |
| **Dados bancários** | agência e conta perto das palavras-chave |
| **Chave Pix** | chave aleatória (UUID) ou valor após “chave Pix” |

**Dados de saúde vêm desligados por padrão**: eles continuam no PDF
anonimizado. Para tarjá-los, ative o tipo em *Configurações… → Tipos de dado* ou
no arquivo de política (`SAUDE: ativo: true`). Uma política que já o lista como
ativo continua valendo.

**Termos clínicos genéricos** (“laudo”, “exame”, “diagnóstico”, “prontuário”)
**não são tarjados sozinhos**: eles só aumentam a confiança das detecções de
saúde próximas.

Os dicionários ficam em [veu/recursos/](veu/recursos/) (`prenomes.txt`,
`sobrenomes.txt`, `doencas.txt`, `medicamentos.txt`, `termos_clinicos.txt`).
São arquivos de texto simples, um termo por linha, que podem ser ampliados.

## Política da organização

A política define **o que** procurar e **como** tarjar. Ela é editada em
**Configurações…** (canto direito da barra de ferramentas):

- **Tipos de dado:** ativar ou desativar cada tipo e ajustar a *confiança
  mínima* (detecções abaixo dela são descartadas). O padrão é 0,5.
- **Tipos personalizados:** nome + expressão regular (ex.: “Matrícula
  funcionário”, `MAT-\d{6}`), com cor e rótulo próprios. A tela mostra ao vivo o
  que a regra encontra num texto de teste.
- **Sempre tarjar:** termos (nomes de clientes, projetos) marcados em todas as
  ocorrências e já aceitos.
- **Exceções:** termos que nunca são marcados automaticamente (ex.: o nome da
  própria empresa ou de um hospital com nome de pessoa).
- **Tarja:** estilo padrão e tratamento de desenhos vetoriais.
- **Importar/Exportar:** em YAML ou JSON.

Um exemplo completo está em [docs/politica_exemplo.yaml](docs/politica_exemplo.yaml).
O arquivo é validado ao carregar; erros (regex inválida, tipo inexistente,
campo desconhecido) aparecem em português, indicando o campo com problema.

### Onde a política fica (e qual vale)

| Ordem | Local | Uso |
|---|---|---|
| 1 | variável de ambiente `VEU_POLITICA` | apontar para um arquivo específico |
| 2 | `%PROGRAMDATA%\Veu\politica.yaml` com `bloqueada: true` | **política do TI**, que os usuários não podem alterar |
| 3 | `%APPDATA%\Veu\politica.yaml` | política do usuário (gravada pela tela de configurações) |
| 4 | `%PROGRAMDATA%\Veu\politica.yaml` sem bloqueio | ponto de partida sugerido pelo TI |
| 5 | padrão embutido | quando não há nenhum arquivo |

**Para o TI distribuir a mesma configuração:** exporte a política pela tela,
acrescente `bloqueada: true` e copie o arquivo para
`C:\ProgramData\Veu\politica.yaml` em cada máquina (ou via GPO/Intune).

## PDFs escaneados (OCR)

O Véu decide, página por página, quando aplicar OCR:

- **página sem texto** (digitalizada): faz o OCR da página inteira;
- **texto ilegível** (fonte sem mapeamento de caracteres): faz o OCR da página
  inteira;
- **texto nativo com imagens grandes** (ex.: um documento digitalizado colado
  num relatório): faz o OCR só das imagens.

O OCR usa o Tesseract 5, que já vem embutido na biblioteca de PDF, com o modelo
de português `tessdata_best`. Nas páginas escaneadas, a tarja **apaga os pixels
da imagem**. Na verificação, o Véu reconstrói a página só com as imagens (sem
as tarjas pretas por cima) e roda o OCR de novo, para provar que nada restou.

> ⚠ **O OCR pode errar**: trocar letras (`O`↔`0`, `@`→`Q`), juntar ou separar
> palavras, ignorar texto pequeno, manuscrito ou em ângulo. Um e-mail com o `@`
> mal reconhecido, por exemplo, não é detectado. Nas páginas com OCR, o Véu
> mostra um aviso, e a **revisão visual é ainda mais importante**. As caixas de
> OCR são alargadas automaticamente, porque o OCR tende a devolver caixas
> justas.

Resolução e ativação do OCR ficam em *Configurações… → OCR e auditoria*.

## Auditoria

A cada anonimização, o Véu grava um **recibo** em
`%LOCALAPPDATA%\Veu\auditoria\recibos.jsonl` com:

- data e hora;
- usuário do sistema e nome da máquina;
- SHA-256 do arquivo original e do resultado;
- número de páginas, incluindo quantas passaram por OCR;
- quantidade de tarjas por tipo;
- quantas marcações foram adicionadas e quantas foram rejeitadas manualmente;
- estilo da tarja e, no estilo de pessoas numeradas, quantas pessoas foram
  rotuladas (nunca quem);
- resultado da verificação;
- versão do programa e da política.

**Os valores tarjados nunca são gravados.** Como nomes de arquivo podem conter
dados pessoais (`laudo_maria_silva.pdf`), por padrão os arquivos são
identificados **só pelo hash**. Para incluir o nome e a pasta, ative a opção na
política.

O histórico aparece em **Histórico…**, e o botão *Exportar CSV* gera um arquivo
com `;` e acentos corretos, que abre direto no Excel. Pela linha de comando:
`anonimizar --historico-csv historico.csv`.

## Linha de comando (lotes)

```powershell
anonimizar laudo.pdf                                   # só analisa e lista o que encontrou (nada é gerado)
anonimizar laudo.pdf --sem-revisao                     # gera laudo_anonimizado.pdf
anonimizar laudos\ --pasta-saida anonimizados --sem-revisao --politica politica.yaml
anonimizar entrada.pdf --saida saida.pdf --sem-revisao --estilo rotulo
anonimizar entrada.pdf --sem-revisao --estilo pessoas  # nomes viram [P1], [P2]…
anonimizar --historico-csv historico.csv
anonimizar --help
```

- Sem `--sem-revisao`, a CLI **não gera arquivos**. Ela lista as detecções,
  mostrando só o começo de cada trecho, porque o histórico do terminal fica
  salvo. `--mostrar-trechos` exibe os trechos completos.
- Com `--sem-revisao`, **tudo o que foi detectado é tarjado sem revisão
  humana**, e a CLI mostra um aviso. Use esse modo só em lotes de baixo risco e
  confira uma amostra dos resultados.
- Outras opções: `--senha` para PDFs protegidos e `--sem-ocr`.
- Códigos de saída: `0` sucesso · `1` a verificação encontrou problemas ·
  `2` nada foi gerado (falta `--sem-revisao`) · `3` erro de uso ou de arquivo.

Na versão de desenvolvimento, o comando é `.\.venv\Scripts\anonimizar.exe`.

## Empacotamento

```powershell
powershell -ExecutionPolicy Bypass -File empacotamento\construir.ps1
```

O script faz, nesta ordem:

1. baixa e confere os modelos;
2. roda os testes;
3. gera o ícone;
4. roda o PyInstaller ([empacotamento/veu.spec](empacotamento/veu.spec));
5. **testa os executáveis gerados**: `anonimizar.exe` num prontuário nativo e
   num escaneado, e `Veu.exe` com um teste de inicialização;
6. gera `dist\Veu-<versão>-windows.zip`.

O resultado ocupa cerca de 350 MB em pasta e 155 MB compactado. Dentro dela
estão `Veu.exe`, `anonimizar.exe`, o modelo de nomes, o OCR, os dicionários, a
política de exemplo e este LEIA-ME.

**macOS e Linux:** ainda não há builds para esses sistemas. O PyInstaller
precisa rodar em cada sistema operacional, então o `construir.ps1` gera apenas a
versão para Windows.

## Testes

```powershell
.\.venv\Scripts\python.exe -m pytest
```

Os PDFs de teste são **sintéticos, com dados fictícios**: texto nativo, várias
colunas, tabela, texto quebrado entre linhas, página rotacionada, página
escaneada, prontuário com todos os tipos de dado e um documento de 50 páginas.
Para gerá-los numa pasta e testar manualmente:

```powershell
.\.venv\Scripts\python.exe -m tests.fixtures.gerar_pdfs exemplos
```

## Limitações conhecidas

- **Nenhum detector acerta 100%.** Haverá falsos positivos (ex.: um número de
  protocolo com formato de telefone, uma palavra comum que também é nome) e
  falsos negativos (formatos incomuns, nomes estrangeiros ou raros). Por isso
  **a revisão humana é obrigatória**.
- **Nomes:** um prenome sozinho (“Rosa”, “Glória”) só é marcado com um gatilho
  por perto (“Sra. Rosa”, “Paciente: Rosa”). Nomes de lugares e instituições
  derivados de nomes de pessoas (“Hospital São Lucas”, “Rua João Pessoa”) são
  ignorados de propósito.
- **Saúde:** o dicionário cobre as doenças e os medicamentos mais comuns, mas
  não é exaustivo. Siglas ambíguas (AVC, AAS) só são marcadas com contexto
  clínico por perto.
- **Exceções** só removem detecções que estão **inteiramente** dentro do termo
  da exceção.
- **OCR** (veja acima): erros de reconhecimento fazem dados passarem sem
  detecção. Revise com atenção as páginas escaneadas.
- Texto desenhado como **contorno vetorial** (não como texto) não é detectado e
  só é removido se você o cobrir com uma caixa manual.
- PDFs protegidos por senha são abertos com a senha; o resultado é salvo sem
  senha.
- **Versão do PyMuPDF fixada em 1.28.2:** as versões 2.0 e 2.1 deslocam o texto
  que fica depois de uma tarja. Um teste automático
  ([tests/test_regressao_pymupdf.py](tests/test_regressao_pymupdf.py)) detecta o
  problema caso a versão seja atualizada.

## Licença

O Véu é distribuído sob a **AGPL-3.0** (veja [LICENSE](LICENSE)). O código-fonte
completo está disponível neste repositório. Quem modificar o Véu e distribuí-lo,
ou oferecê-lo a terceiros por rede, deve disponibilizar o código-fonte das
modificações sob a mesma licença.

### Licenças de terceiros

| Componente | Licença |
|---|---|
| PyMuPDF / MuPDF | AGPL-3.0 |
| PySide6 (Qt) | LGPL-3.0 |
| spaCy | MIT |
| Modelo `pt_core_news_md` | CC BY-SA 4.0 |
| Tesseract (embutido no MuPDF) e `por.traineddata` (tessdata_best) | Apache-2.0 |
| pydantic, PyYAML, pytest | MIT |
| PyInstaller (só na construção) | GPL-2.0 com exceção para o executável gerado |
