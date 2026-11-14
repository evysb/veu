# Véu — 100% offline PDF anonymizer

Véu finds personal data in PDFs, lets you review every mark, and produces an
anonymized copy with **true removal** of the redacted content. All processing
happens on your computer: the PDF and its text are never sent to the internet.
There are no network calls, no telemetry and no cloud AI.

Véu is built for Brazilian documents (LGPD compliance): its detectors target
Brazilian identifiers and Portuguese text, and the user interface is in
Portuguese. A Portuguese version of this document is available in
[LEIA-ME.md](LEIA-ME.md).

Features:

- 18 data types detected, with person names recognized by a language model that
  runs locally;
- **local OCR** for scanned PDFs;
- IT-configurable policy;
- automatic verification of the output;
- audit receipts;
- command line for batch processing.

---

## Installation

### For end users (Windows)

1. Unzip `Veu-<version>-windows.zip` into a folder, for example
   `C:\Programs\Veu`.
2. Open `Veu.exe`.

No Python, internet connection or administrator rights required. OCR and the
name-recognition model are already bundled in the folder. For a Start menu
entry, create a shortcut to `Veu.exe`.

### For development

Requirements: Python 3.11 or newer (64-bit).

```powershell
cd veu
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pip install -e .
.\.venv\Scripts\python.exe empacotamento\baixar_modelos.py
```

This setup is the **only step that uses the internet**. It downloads:

- the spaCy Portuguese model (`pt_core_news_md`, about 40 MB), used to
  recognize names;
- the OCR language file (`por.traineddata`, 8 MB), whose SHA-256 is verified.

After that, everything works offline.

## Usage

```powershell
Veu.exe                                       # packaged version
.\.venv\Scripts\python.exe -m veu laudo.pdf  # development version, opening a file directly
```

1. **Open:** click *Abrir PDF…* (Open PDF) or drag the file onto the window.
2. **Detect:** Véu analyzes the document and draws colored boxes over the data
   it finds (one color per type). **Dashed** boxes are pending, **solid** boxes
   are accepted and **dotted gray** boxes were rejected.
3. **Review (required):**
   - click a box (or a row in the list on the right) and press **A** to accept
     or **R** to reject; right-click opens more options, such as
     *Marcar todas as ocorrências* (mark all occurrences) of the same text;
   - **Desenhar caixa (D)** (draw box): drag over the page to redact something
     the program did not detect; **Del** deletes a manual mark;
   - **Buscar termo → Marcar todas** (search term → mark all): marks every
     occurrence of a name, project, etc. (case- and accent-insensitive);
   - the side list filters by type and status and allows bulk accept/reject
     ("todas da lista" — "all in list" — acts on what the filter shows);
   - navigate with **PgUp/PgDown**; zoom with **Ctrl + mouse wheel**,
     **Ctrl+/Ctrl−** and **Ctrl+0** (fit to width).
4. **Anonymize:** *Anonimizar e salvar…* (Anonymize and save, Ctrl+S). Choose
   the redaction style (plain black or labeled, such as `[CPF]`, `[NOME]`,
   `[SAÚDE]`) and confirm that you reviewed the document.
5. **Save:** the default is `file_anonimizado.pdf` in the same folder. **The
   original is never overwritten.**

When done, Véu **reopens the generated PDF**, confirms that nothing redacted
can be extracted, and runs the detectors again to flag any data left
unredacted.

### What anonymization does

- Actually removes the text under the redaction; copy-paste, search or
  extraction cannot recover the value. Text outside the redaction does not move.
- Erases image pixels under the redaction and removes vector drawings covered
  by it. A more aggressive option removes any drawing that touches the
  redaction, but it may erase table lines.
- Removes metadata (author, title, XMP), comments and annotations, form fields,
  embedded attachments, bookmarks, links, JavaScript and invisible text. Hidden
  layers (OCG) are made visible during analysis, so their content also goes
  through detection.
- Saves the file without orphan objects and without a password.

## What is detected

| Type | How it is detected |
|---|---|
| **CPF** (individual taxpayer ID) | with and without mask (including when split across lines), check digits validated |
| **CNPJ** (company taxpayer ID) | numeric and **alphanumeric** (new Receita Federal format), check digits validated |
| **RG** (state ID card) | various formats, only near “RG”, “Identidade”, “SSP”… or the issuing agency |
| **CNH** (driver's license) | 11 digits validated, near “CNH”/“habilitação” |
| **Título de eleitor** (voter ID) | check digits and state code validated |
| **PIS/PASEP/NIS** (social security number) | check digit validated |
| **Cartão SUS (CNS)** (public health card) | 15 digits, official validation (permanent and provisional) |
| **Passport** | near “passaporte” |
| **Person name** | local language model (spaCy) + first-name and surname lists + context (“Sr.”, “paciente”, “nome:”, “assinado por”…) |
| **Address/CEP** (postal code) | street, number, unit, neighborhood, city/state and CEP; also text after “Endereço:” and “residente na” |
| **Phone** | landline and mobile, with or without area code (validated) and +55 |
| **E-mail** | e-mail address format |
| **Date of birth** | dates near “nascimento”, “DN”, “nascido em”… |
| **License plate** | old format and Mercosul |
| **Health data** | ICD-10 codes (after “CID” or with clinical context), sensitive diseases and conditions, medications |
| **Professional registration** | CRM, CRO, COREN, CRP, CRF… |
| **Bank details** | branch and account near keywords |
| **Pix key** | random key (UUID) or value after “chave Pix” |

**Generic clinical terms** (“laudo”, “exame”, “diagnóstico”, “prontuário” —
report, exam, diagnosis, medical record) **are not redacted on their own**: they
only increase the confidence of nearby health detections.

The dictionaries live in [veu/recursos/](veu/recursos/) (`prenomes.txt`,
`sobrenomes.txt`, `doencas.txt`, `medicamentos.txt`, `termos_clinicos.txt`).
They are plain text files, one term per line, and can be extended.

## Organization policy

The policy defines **what** to look for and **how** to redact it. It is edited
under **Configurações…** (Settings, at the right of the toolbar):

- **Data types:** enable or disable each type and set the *minimum confidence*
  (detections below it are discarded). The default is 0.5.
- **Custom types:** name + regular expression (e.g. “Matrícula funcionário”,
  `MAT-\d{6}`), with their own color and label. The screen shows live what the
  rule matches in a sample text.
- **Always redact:** terms (client names, projects) marked in every occurrence
  and pre-accepted.
- **Exceptions:** terms that are never marked automatically (e.g. your own
  company's name, or a hospital named after a person).
- **Redaction:** default style and handling of vector drawings.
- **Import/Export:** in YAML or JSON.

A complete example is in [docs/politica_exemplo.yaml](docs/politica_exemplo.yaml).
The file is validated on load; errors (invalid regex, unknown type, unknown
field) are shown in Portuguese, pointing to the offending field.

### Where the policy lives (and which one applies)

| Priority | Location | Use |
|---|---|---|
| 1 | environment variable `VEU_POLITICA` | point to a specific file |
| 2 | `%PROGRAMDATA%\Veu\politica.yaml` with `bloqueada: true` | **IT policy**, which users cannot change |
| 3 | `%APPDATA%\Veu\politica.yaml` | user policy (written by the settings screen) |
| 4 | `%PROGRAMDATA%\Veu\politica.yaml` without lock | starting point suggested by IT |
| 5 | built-in default | when no file exists |

**For IT to roll out the same configuration:** export the policy from the
settings screen, add `bloqueada: true` and copy the file to
`C:\ProgramData\Veu\politica.yaml` on each machine (or via GPO/Intune).

## Scanned PDFs (OCR)

Véu decides, page by page, when to apply OCR:

- **page without text** (scanned): OCR of the whole page;
- **unreadable text** (font without a character map): OCR of the whole page;
- **native text with large images** (e.g. a scanned document pasted into a
  report): OCR of the images only.

OCR uses Tesseract 5, already built into the PDF library, with the Portuguese
`tessdata_best` model. On scanned pages, redaction **erases the image pixels**.
During verification, Véu rebuilds the page from the images alone (without the
black boxes on top) and runs OCR again, to prove nothing was left behind.

> ⚠ **OCR can make mistakes**: swapping characters (`O`↔`0`, `@`→`Q`), merging
> or splitting words, missing small, handwritten or rotated text. An e-mail
> whose `@` is misrecognized, for example, will not be detected. On OCR pages,
> Véu shows a warning, and **visual review matters even more**. OCR boxes are
> enlarged automatically, because OCR tends to return tight boxes.

OCR resolution and activation are under *Configurações… → OCR e auditoria*
(Settings → OCR and audit).

## Audit

On every anonymization, Véu writes a **receipt** to
`%LOCALAPPDATA%\Veu\auditoria\recibos.jsonl` containing:

- date and time;
- system user and machine name;
- SHA-256 of the original file and of the output;
- number of pages, including how many went through OCR;
- number of redactions per type;
- how many marks were added and how many were rejected manually;
- redaction style;
- verification result;
- program and policy version.

**Redacted values are never recorded.** Since file names may contain personal
data (`laudo_maria_silva.pdf`), by default files are identified **by hash
only**. To include the file name and folder, enable the option in the policy.

The history is shown under **Histórico…** (History), and the *Exportar CSV*
(Export CSV) button produces a `;`-separated file with correct accents that
opens directly in Excel. From the command line:
`anonimizar --historico-csv historico.csv`.

## Command line (batches)

```powershell
anonimizar laudo.pdf                                   # analyze only and list findings (nothing is written)
anonimizar laudo.pdf --sem-revisao                     # writes laudo_anonimizado.pdf
anonimizar laudos\ --pasta-saida anonimizados --sem-revisao --politica politica.yaml
anonimizar entrada.pdf --saida saida.pdf --sem-revisao --estilo rotulo
anonimizar --historico-csv historico.csv
anonimizar --help
```

- Without `--sem-revisao` (no review), the CLI **writes no files**. It lists
  the detections, showing only the start of each match, because terminal
  history is persisted. `--mostrar-trechos` shows full matches.
- With `--sem-revisao`, **everything detected is redacted without human
  review**, and the CLI prints a warning. Use this mode only for low-risk
  batches and spot-check a sample of the results.
- Other options: `--senha` for password-protected PDFs and `--sem-ocr` to
  disable OCR.
- Exit codes: `0` success · `1` verification found problems ·
  `2` nothing was written (missing `--sem-revisao`) · `3` usage or file error.

In the development version, the command is `.\.venv\Scripts\anonimizar.exe`.

## Packaging

```powershell
powershell -ExecutionPolicy Bypass -File empacotamento\construir.ps1
```

The script, in order:

1. downloads and verifies the models;
2. runs the tests;
3. generates the icon;
4. runs PyInstaller ([empacotamento/veu.spec](empacotamento/veu.spec));
5. **tests the generated executables**: `anonimizar.exe` on a native and a
   scanned medical record, and `Veu.exe` with a startup test;
6. produces `dist\Veu-<version>-windows.zip`.

The output takes about 350 MB unpacked and 155 MB zipped. It contains
`Veu.exe`, `anonimizar.exe`, the name model, OCR, the dictionaries, the sample
policy and the Portuguese `LEIA-ME.md`.

**macOS and Linux:** PyInstaller must run on each OS. The workflow
[.github/workflows/construir.yml](.github/workflows/construir.yml) builds on
all three, but **only runs when triggered manually** (GitHub *Actions* tab).
The macOS and Linux builds have not yet been tested on real machines.

## Tests

```powershell
.\.venv\Scripts\python.exe -m pytest
```

The test PDFs are **synthetic, with fictitious data**: native text, multiple
columns, a table, text split across lines, a rotated page, a scanned page, a
medical record with every data type, and a 50-page document. To generate them
into a folder for manual testing:

```powershell
.\.venv\Scripts\python.exe -m tests.fixtures.gerar_pdfs exemplos
```

## Known limitations

- **No detector is 100% accurate.** There will be false positives (e.g. a
  protocol number shaped like a phone number, a common word that is also a
  name) and false negatives (unusual formats, foreign or rare names). That is
  why **human review is required**.
- **Names:** a first name alone (“Rosa”, “Glória”) is only marked with a
  trigger nearby (“Sra. Rosa”, “Paciente: Rosa”). Place and institution names
  derived from person names (“Hospital São Lucas”, “Rua João Pessoa”) are
  ignored on purpose.
- **Health:** the dictionary covers the most common diseases and medications,
  but is not exhaustive. Ambiguous acronyms (AVC, AAS) are only marked with
  clinical context nearby.
- **Exceptions** only remove detections that fall **entirely** within the
  exception term.
- **OCR** (see above): recognition errors let data slip through undetected.
  Review scanned pages carefully.
- Text drawn as **vector outlines** (rather than text) is not detected and is
  only removed if you cover it with a manual box.
- Password-protected PDFs are opened with the password; the output is saved
  without a password.
- **PyMuPDF pinned to 1.28.2:** versions 2.0 and 2.1 shift the text that comes
  after a redaction. An automated test
  ([tests/test_regressao_pymupdf.py](tests/test_regressao_pymupdf.py)) catches
  the problem if the version is upgraded.

## Third-party licenses

| Component | License |
|---|---|
| PyMuPDF / MuPDF | AGPL-3.0 (internal use; distributing to third parties requires publishing the source code under AGPL or buying Artifex's commercial license) |
| PySide6 (Qt) | LGPL-3.0 |
| spaCy | MIT |
| `pt_core_news_md` model | CC BY-SA 4.0 |
| Tesseract (built into MuPDF) and `por.traineddata` (tessdata_best) | Apache-2.0 |
| pydantic, PyYAML, pytest | MIT |
| PyInstaller (build only) | GPL-2.0 with an exception for the generated executable |
