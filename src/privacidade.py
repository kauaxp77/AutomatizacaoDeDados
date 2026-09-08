"""Mascaramento de dados pessoais em tudo que sai do processo.

O projeto nasceu sobre dados sensiveis, e a regra era simples: o registro
guarda o **ato**, nunca a **pessoa**. Todo log passa por este filtro; nao ha
caminho que escreva sem passar.

O caso dificil nao e o CPF — e o nome em caixa alta numa coluna solta, colado
a termos tecnicos que tambem estao em caixa alta. Mascarar tudo destruiria o
texto que se quer analisar. A solucao aqui e uma lista de termos do dominio:
uma sequencia que contenha qualquer um deles nao e nome de pessoa.
"""

from __future__ import annotations

import logging
import re
import unicodedata

_RE_CPF = re.compile(r"\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b")
_RE_IDENTIFICADOR = re.compile(r"\b(\d{7})-(\d{2})\.(\d{4})\.(\d)\.(\d{2})\.(\d{4})\b")

# "Juntado por FULANA DE TAL - ANALISTA em 13/08/2026" -> o nome sai, o ato fica.
_RE_AUTORIA = re.compile(
    r"(?i)\b(juntad[oa]|assinad[oa]|lid[oa]|cadastrad[oa]|expedid[oa]"
    r"|registrad[oa]|proferid[oa]|elaborad[oa])\s+por\s+.+?(?=\s+-\s|\s+em\s+\d|$)"
)

# Ajuste esta lista ao vocabulario do seu dominio.
TERMOS_DO_DOMINIO = {
    "decisao", "sentenca", "certidao", "peticao", "oficio", "relatorio", "documento",
    "documentos", "manifestacao", "notificacao", "intimacao", "ciencia", "resposta",
    "encerramento", "encerrado", "arquivamento", "arquivado", "prazo", "prazos",
    "categoria", "processo", "processos", "autos", "parte", "partes", "sistema",
    "usuario", "servidor", "analista", "setor", "unidade", "protocolo", "registro",
    "aberta", "terminada", "andamento", "pendente", "concluido", "tarefa", "fluxo",
}

_RE_CAIXA_ALTA = re.compile(
    r"\b[A-ZÁÂÃÀÉÊÍÓÔÕÚÜÇ][A-ZÁÂÃÀÉÊÍÓÔÕÚÜÇ']{1,}"
    r"(?:\s+(?:[A-ZÁÂÃÀÉÊÍÓÔÕÚÜÇ][A-ZÁÂÃÀÉÊÍÓÔÕÚÜÇ']{1,}|DA|DE|DO|DAS|DOS|E)){1,6}\b"
)

_LIGACOES = {"da", "de", "do", "das", "dos", "e"}


def _sem_acento(texto: str) -> str:
    nfkd = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def _parece_nome(trecho: str) -> bool:
    palavras = [_sem_acento(p).lower() for p in trecho.split()]
    uteis = [p for p in palavras if p not in _LIGACOES]
    if len(uteis) < 2:
        return False
    return not any(p in TERMOS_DO_DOMINIO for p in uteis)


def mascarar_identificador(texto: str) -> str:
    """1234567-89.2026.1.23.4567 -> 1234***-**.2026.1.23.4567"""
    return _RE_IDENTIFICADOR.sub(
        lambda m: "%s***-**.%s.%s.%s.%s" % (m.group(1)[:4], m.group(3), m.group(4), m.group(5), m.group(6)),
        texto,
    )


def mascarar(texto: object) -> str:
    s = str(texto)
    s = mascarar_identificador(s)
    s = _RE_CPF.sub("***.***.***-**", s)
    s = _RE_AUTORIA.sub(lambda m: m.group(1) + " por [NOME]", s)
    return _RE_CAIXA_ALTA.sub(lambda m: "[NOME]" if _parece_nome(m.group(0)) else m.group(0), s)


class FiltroMascara(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = mascarar(record.getMessage())
        record.args = ()
        return True


def obter_logger(nome: str = "extrator") -> logging.Logger:
    """Logger em que nao existe caminho de escrita sem mascaramento."""
    log = logging.getLogger(nome)
    if log.handlers:
        return log
    log.setLevel(logging.INFO)
    console = logging.StreamHandler()
    console.setFormatter(logging.Formatter("%(asctime)s %(levelname)-7s %(message)s", "%H:%M:%S"))
    console.addFilter(FiltroMascara())
    log.addHandler(console)
    log.propagate = False
    return log
