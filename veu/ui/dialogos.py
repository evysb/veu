"""Diálogos de confirmação da anonimização e de resultado."""

from __future__ import annotations

import os
from html import escape
from collections import Counter

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QLabel,
    QPushButton,
    QTextBrowser,
    QVBoxLayout,
)

from veu.core.redaction import EstiloTarja, OpcoesAnonimizacao, ResultadoAnonimizacao, Vetores
from veu.core.tipos import obter_tipo
from veu.ui.tema import ERRO, SUCESSO


def _tabela_contagem(contagem: Counter) -> str:
    linhas = "".join(
        f"<tr><td>{escape(obter_tipo(t).nome)}</td><td align='right'><b>{n}</b></td></tr>"
        for t, n in sorted(contagem.items(), key=lambda x: -x[1])
    )
    return f"<table cellspacing='0' cellpadding='3'>{linhas}</table>"


class DialogoConfirmacao(QDialog):
    """Resumo do que será tarjado + opções + confirmação explícita da revisão."""

    def __init__(
        self, contagem: Counter, rejeitadas: int, manuais: int, paginas_sem_texto: int, parent=None, padrao=None
    ):
        super().__init__(parent)
        self.setWindowTitle("Confirmar anonimização")
        self.setMinimumWidth(460)
        total = sum(contagem.values())

        resumo = QLabel(
            f"<p>Serão aplicadas <b>{total}</b> tarja(s):</p>{_tabela_contagem(contagem)}"
            f"<p>{rejeitadas} detecção(ões) rejeitada(s) ficarão visíveis. "
            f"{manuais} marcação(ões) foram adicionadas manualmente.</p>"
        )
        resumo.setTextFormat(Qt.RichText)
        resumo.setWordWrap(True)

        self.estilo = QComboBox()
        self.estilo.addItem("Retângulo preto liso", EstiloTarja.PRETA)
        self.estilo.addItem("Retângulo com o tipo do dado ([CPF], [E-MAIL]…)", EstiloTarja.ROTULO)
        self.estilo.addItem("Tipo do dado, com cada pessoa numerada ([P1], [P2]…)", EstiloTarja.PESSOAS)
        self.vetores = QComboBox()
        self.vetores.addItem("Remover desenhos totalmente cobertos pela tarja", Vetores.COBERTOS)
        self.vetores.addItem("Remover qualquer desenho que toque a tarja (pode apagar linhas de tabelas)", Vetores.TOCADOS)
        if padrao is not None:  # valores iniciais vindos da política
            self.estilo.setCurrentIndex(self.estilo.findData(padrao.estilo))
            self.vetores.setCurrentIndex(self.vetores.findData(padrao.vetores))
        self.limpar = QCheckBox("Remover metadados, comentários, anexos, formulários e marcadores")
        self.limpar.setChecked(True)
        opcoes = QGroupBox("Opções")
        form = QFormLayout(opcoes)
        form.addRow("Estilo da tarja:", self.estilo)
        form.addRow("Desenhos vetoriais:", self.vetores)
        form.addRow(self.limpar)

        layout = QVBoxLayout(self)
        layout.addWidget(resumo)
        if paginas_sem_texto:
            aviso = QLabel(
                f"⚠ {paginas_sem_texto} página(s) não têm camada de texto (provável digitalização). "
                "O conteúdo delas só será tarjado onde você desenhou caixas."
            )
            aviso.setObjectName("aviso")
            aviso.setWordWrap(True)
            layout.addWidget(aviso)
        layout.addWidget(opcoes)

        self.confirmo = QCheckBox("Revisei todas as páginas e as marcações estão corretas.")
        layout.addWidget(self.confirmo)

        botoes = QDialogButtonBox()
        self.ok = QPushButton("Anonimizar e salvar…")
        self.ok.setObjectName("primario")
        self.ok.setEnabled(False)
        botoes.addButton(self.ok, QDialogButtonBox.AcceptRole)
        botoes.addButton("Voltar à revisão", QDialogButtonBox.RejectRole)
        botoes.accepted.connect(self.accept)
        botoes.rejected.connect(self.reject)
        self.confirmo.toggled.connect(self.ok.setEnabled)
        layout.addWidget(botoes)

    def opcoes(self) -> OpcoesAnonimizacao:
        return OpcoesAnonimizacao(
            estilo=EstiloTarja(self.estilo.currentData()),
            vetores=Vetores(self.vetores.currentData()),
            limpar_documento=self.limpar.isChecked(),
        )


class DialogoResultado(QDialog):
    def __init__(self, resultado: ResultadoAnonimizacao, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Anonimização concluída")
        self.setMinimumSize(560, 460)
        self._caminho = resultado.caminho_saida
        v = resultado.verificacao

        html = [f"<h3>PDF anonimizado salvo</h3><p><code>{escape(os.path.normpath(resultado.caminho_saida))}</code></p>"]
        html.append(f"<p><b>{resultado.total_tarjas}</b> tarja(s) aplicada(s):</p>{_tabela_contagem(resultado.tarjas_por_tipo)}")
        if resultado.pessoas:
            html.append(f"<p>Nomes substituídos por rótulos de <b>{resultado.pessoas}</b> pessoa(s) ([P1], [P2]…).</p>")
        if resultado.limpeza:
            html.append("<p><b>Limpeza do documento:</b></p><ul>" + "".join(f"<li>{x}</li>" for x in resultado.limpeza) + "</ul>")

        html.append("<h3>Verificação automática</h3>")
        if v is None:
            html.append("<p>Verificação não executada.</p>")
        elif v.ok:
            html.append(
                f"<p style='color:{SUCESSO}'><b>✔ Aprovado.</b> O PDF gerado foi reaberto e nenhum dos valores "
                "tarjados pôde ser extraído (texto, busca ou cópia).</p>"
            )
        else:
            html.append(
                f"<p style='color:{ERRO}'><b>✖ Atenção: foram encontrados possíveis vazamentos.</b> "
                "Não compartilhe este arquivo antes de revisar.</p><ul>"
                + "".join(f"<li>Página {p.pagina + 1} ({obter_tipo(p.tipo).nome}): {p.descricao}</li>" for p in v.vazamentos)
                + "</ul>"
            )
        if v is not None:
            if v.residuais_novos:
                html.append(
                    f"<p><b>{len(v.residuais_novos)}</b> possível(is) dado(s) pessoal(is) sem tarja no resultado "
                    "(não estavam marcados para tarjar):</p><ul>"
                    + "".join(
                        f"<li>Página {d.pagina + 1} — {obter_tipo(d.tipo).nome}: {escape(d.trecho)}</li>"
                        for d in v.residuais_novos[:50]
                    )
                    + "</ul>"
                )
            for aviso in v.avisos:
                html.append(f"<p style='color:{ERRO}'>⚠ {escape(aviso)}</p>")
            if v.residuais_rejeitados:
                html.append(f"<p>{v.residuais_rejeitados} item(ns) que você rejeitou continuam visíveis, como esperado.</p>")

        if getattr(resultado, "recibo_registrado", False):
            html.append("<p style='color:#5A6670'>Recibo de auditoria registrado (sem os dados tarjados). "
                        "Consulte em <b>Histórico…</b>.</p>")
        texto = QTextBrowser()
        texto.setHtml("".join(html))

        botoes = QDialogButtonBox()
        abrir = botoes.addButton("Abrir PDF", QDialogButtonBox.ActionRole)
        pasta = botoes.addButton("Abrir pasta", QDialogButtonBox.ActionRole)
        fechar = botoes.addButton("Fechar", QDialogButtonBox.AcceptRole)
        abrir.clicked.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(self._caminho)))
        pasta.clicked.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(os.path.dirname(self._caminho))))
        fechar.clicked.connect(self.accept)

        layout = QVBoxLayout(self)
        layout.addWidget(texto)
        layout.addWidget(botoes)
