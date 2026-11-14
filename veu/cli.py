"""Linha de comando do Véu.

Exemplos:
    anonimizar laudo.pdf                       # só analisa e lista o que encontrou
    anonimizar laudo.pdf --sem-revisao         # tarja tudo o que foi detectado (sem revisão humana!)
    anonimizar *.pdf --pasta-saida saida --sem-revisao --politica politica.yaml
    anonimizar --historico-csv historico.csv   # exporta os recibos de auditoria

Códigos de saída: 0 sucesso · 1 verificação encontrou problemas · 2 nada foi
gerado (falta --sem-revisao) · 3 erro de uso/arquivo.
"""

from __future__ import annotations

import argparse
import glob
import os
import sys
from collections import Counter
from pathlib import Path

from veu import __version__

AVISO_SEM_REVISAO = (
    "ATENÇÃO: modo --sem-revisao. Todas as detecções automáticas serão tarjadas sem revisão humana.\n"
    "Nenhum detector acerta 100%: dados podem ficar sem tarja e trechos inofensivos podem ser tarjados.\n"
    "Use este modo só para lotes de baixo risco e confira uma amostra dos resultados."
)

OK, FALHA_VERIFICACAO, NADA_GERADO, ERRO = 0, 1, 2, 3


def _configurar_console() -> None:
    for fluxo in (sys.stdout, sys.stderr):
        try:
            fluxo.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass


def _expandir_entradas(entradas: list[str]) -> list[Path]:
    arquivos: list[Path] = []
    for e in entradas:
        p = Path(e)
        if p.is_dir():
            arquivos.extend(sorted(p.glob("*.pdf")))
        elif any(c in e for c in "*?["):
            arquivos.extend(Path(x) for x in sorted(glob.glob(e)))
        else:
            arquivos.append(p)
    vistos, saida = set(), []
    for a in arquivos:
        chave = os.path.normcase(os.path.abspath(a))
        if chave not in vistos and "_anonimizado" not in a.stem:
            vistos.add(chave)
            saida.append(a)
    return saida


def _mascarar(trecho: str) -> str:
    """No terminal, mostra só o início do trecho (o histórico do console fica salvo)."""
    t = " ".join(trecho.split())
    return t if len(t) <= 4 else t[:3] + "…" + f" ({len(t)} car.)"


def construir_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="anonimizar",
        description="Véu — anonimiza dados pessoais em PDFs, 100%% offline.",
        epilog="Sem --sem-revisao, os arquivos são apenas analisados. Para revisar, use a interface: veu arquivo.pdf",
    )
    p.add_argument("entradas", nargs="*", help="PDFs, pastas ou padrões (ex.: laudos\\*.pdf)")
    p.add_argument("--politica", help="arquivo de política (.yaml ou .json); padrão: a política ativa")
    p.add_argument("--saida", help="arquivo de saída (só com um PDF de entrada)")
    p.add_argument("--pasta-saida", help="pasta para os PDFs anonimizados (padrão: ao lado de cada original)")
    p.add_argument("--sem-revisao", action="store_true", help="tarja todas as detecções sem revisão humana (com aviso)")
    p.add_argument("--estilo", choices=["preta", "rotulo"], help="estilo da tarja (padrão: o da política)")
    p.add_argument("--senha", help="senha do(s) PDF(s), se protegidos")
    p.add_argument("--sem-ocr", action="store_true", help="não aplicar OCR em páginas escaneadas")
    p.add_argument("--mostrar-trechos", action="store_true", help="na análise, mostra os trechos completos")
    p.add_argument("--historico-csv", metavar="ARQUIVO", help="exporta o histórico de auditoria para CSV e sai")
    p.add_argument("--versao", action="version", version=f"Véu {__version__}")
    return p


def main(argv: list[str] | None = None) -> int:
    _configurar_console()
    args = construir_parser().parse_args(argv)

    from veu.core.audit import criar_recibo, exportar_csv, ler_historico, registrar
    from veu.core.extraction import SenhaIncorreta, SenhaNecessaria
    from veu.core.models import EstiloTarja, Status
    from veu.core.pipeline import analisar
    from veu.core.policy import PoliticaInvalida, carregar_politica, politica_ativa
    from veu.core.redaction import ArquivoOriginalProtegido, OpcoesAnonimizacao, anonimizar, caminho_saida_padrao
    from veu.core.tipos import obter_tipo

    if args.historico_csv:
        recibos = ler_historico()
        exportar_csv(recibos, args.historico_csv)
        print(f"{len(recibos)} recibo(s) exportado(s) para {args.historico_csv}")
        return OK

    if not args.entradas:
        print("Informe ao menos um PDF. Use --help para ver as opções.", file=sys.stderr)
        return ERRO

    try:
        politica = carregar_politica(args.politica) if args.politica else politica_ativa()[0]
    except PoliticaInvalida as e:
        print(f"Erro na política: {e}", file=sys.stderr)
        return ERRO
    if args.sem_ocr:
        politica = politica.model_copy(deep=True)
        politica.ocr.ativo = False

    arquivos = _expandir_entradas(args.entradas)
    if not arquivos:
        print("Nenhum PDF encontrado.", file=sys.stderr)
        return ERRO
    if args.saida and len(arquivos) > 1:
        print("--saida só pode ser usado com um único PDF; use --pasta-saida para lotes.", file=sys.stderr)
        return ERRO
    if args.sem_revisao:
        print(AVISO_SEM_REVISAO, file=sys.stderr)
        print(file=sys.stderr)

    codigo = OK
    resumo = Counter()
    for arquivo in arquivos:
        print(f"== {arquivo}")
        if not arquivo.is_file():
            print("   arquivo não encontrado", file=sys.stderr)
            codigo = max(codigo, ERRO)
            continue
        try:
            analise = analisar(str(arquivo), senha=args.senha, politica=politica)
        except SenhaNecessaria:
            print("   PDF protegido: informe --senha", file=sys.stderr)
            codigo = max(codigo, ERRO)
            continue
        except SenhaIncorreta:
            print("   senha incorreta", file=sys.stderr)
            codigo = max(codigo, ERRO)
            continue
        except Exception as e:
            print(f"   não foi possível analisar: {e}", file=sys.stderr)
            codigo = max(codigo, ERRO)
            continue

        for aviso in analise.avisos:
            print(f"   aviso: {aviso}")
        por_tipo = Counter(d.tipo for d in analise.deteccoes)
        print(f"   {len(analise.deteccoes)} detecção(ões) em {analise.num_paginas} página(s): "
              + ", ".join(f"{obter_tipo(t).nome} {n}" for t, n in por_tipo.most_common()))

        if not args.sem_revisao:
            for d in analise.deteccoes:
                trecho = d.trecho if args.mostrar_trechos else _mascarar(d.trecho)
                print(f"     p.{d.pagina + 1:<3} {obter_tipo(d.tipo).nome:<28} {d.confianca:>4.0%}  {trecho}")
            codigo = max(codigo, NADA_GERADO)
            continue

        for d in analise.deteccoes:
            if d.status == Status.PENDENTE:
                d.status = Status.ACEITA
        if args.saida:
            saida = args.saida
        elif args.pasta_saida:
            Path(args.pasta_saida).mkdir(parents=True, exist_ok=True)
            saida = caminho_saida_padrao(str(Path(args.pasta_saida) / arquivo.name))
        else:
            saida = caminho_saida_padrao(str(arquivo))
        estilo = EstiloTarja(args.estilo) if args.estilo else politica.tarja.estilo
        opcoes = OpcoesAnonimizacao(estilo=estilo, vetores=politica.tarja.vetores)
        try:
            resultado = anonimizar(analise, saida, opcoes)
        except ArquivoOriginalProtegido as e:
            print(f"   {e}", file=sys.stderr)
            codigo = max(codigo, ERRO)
            continue
        v = resultado.verificacao
        print(f"   salvo: {saida} ({resultado.total_tarjas} tarja(s))")
        if v is not None:
            if v.ok:
                print("   verificação: aprovada (nada do que foi tarjado pode ser extraído)")
            else:
                print(f"   verificação: FALHOU — {len(v.vazamentos)} possível(is) vazamento(s). Não compartilhe sem revisar.")
                codigo = max(codigo, FALHA_VERIFICACAO)
            if v.residuais_novos:
                print(f"   atenção: {len(v.residuais_novos)} possível(is) dado(s) sem tarja no resultado")
            for aviso in v.avisos:
                print(f"   aviso: {aviso}")
        if politica.auditoria.ativo:
            registrar(criar_recibo(analise, resultado, None, modo="cli-sem-revisao"))
        resumo.update(resultado.tarjas_por_tipo)

    if not args.sem_revisao and codigo == NADA_GERADO:
        print("\nNenhum arquivo foi gerado. Revise na interface (veu arquivo.pdf) ou use --sem-revisao.", file=sys.stderr)
    elif args.sem_revisao and len(arquivos) > 1:
        print(f"\nTotal: {sum(resumo.values())} tarja(s) em {len(arquivos)} arquivo(s).")
    return codigo


if __name__ == "__main__":
    sys.exit(main())
