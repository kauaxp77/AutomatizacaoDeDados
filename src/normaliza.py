"""Normalizacao de texto, datas e vocabulario.

Sistemas antigos exibem a mesma data de quatro jeitos diferentes na mesma tela.
Este modulo existe porque cada um desses jeitos ja quebrou a extracao uma vez.
"""

from __future__ import annotations

import re
import unicodedata
from datetime import date, datetime, timedelta

_RE_ESPACOS = re.compile(r"\s+")
_RE_DATA_BR = re.compile(r"\b(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})\b")
_RE_DATA_ISO = re.compile(r"^(\d{4})-(\d{2})-(\d{2})(?:[T ].*)?$")

# Listas e cronologias costumam separar os dias por extenso: "17 jun 2026".
# Um extrator que so procura dd/mm/aaaa nunca encontra esses — e a falha e
# silenciosa: os itens simplesmente saem sem data.
MESES = {
    "jan": 1, "fev": 2, "mar": 3, "abr": 4, "mai": 5, "jun": 6,
    "jul": 7, "ago": 8, "set": 9, "out": 10, "nov": 11, "dez": 12,
}
_RE_DATA_EXTENSO = re.compile(r"\b(\d{1,2})\s+([a-z]{3})[a-z]*\.?\s+(\d{4})\b", re.I)

# Planilhas guardam datas como numero de dias desde 30/12/1899.
_EPOCA_PLANILHA = date(1899, 12, 30)


def sem_acento(texto: str) -> str:
    nfkd = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def chave(texto: str) -> str:
    """Forma comparavel: sem acento, minuscula, espacos colapsados.

    As regras de extracao sao escritas contra esta forma. Assim o mesmo padrao
    casa com "Manifestação", "MANIFESTACAO" e "manifestaçao".
    """
    return _RE_ESPACOS.sub(" ", sem_acento(str(texto)).lower()).strip()


def parse_data(valor: object) -> date | None:
    """Aceita date, serial de planilha, ISO, dd/mm/aaaa e "17 jun 2026"."""
    if valor is None or valor == "":
        return None
    if isinstance(valor, datetime):
        return valor.date()
    if isinstance(valor, date):
        return valor
    if isinstance(valor, (int, float)):
        return _de_serial(valor)

    s = str(valor).strip()

    m = _RE_DATA_ISO.match(s)
    if m:
        return _monta(int(m.group(1)), int(m.group(2)), int(m.group(3)))

    m = _RE_DATA_EXTENSO.search(sem_acento(s).lower())
    if m:
        mes = MESES.get(m.group(2))
        if mes:
            return _monta(int(m.group(3)), mes, int(m.group(1)))

    m = _RE_DATA_BR.search(s)
    if m:
        ano = int(m.group(3))
        return _monta(ano + 2000 if ano < 100 else ano, int(m.group(2)), int(m.group(1)))

    return _de_serial(s)


def _monta(ano: int, mes: int, dia: int) -> date | None:
    try:
        return date(ano, mes, dia)
    except ValueError:
        return None


def _de_serial(valor) -> date | None:
    try:
        n = float(valor)
    except (TypeError, ValueError):
        return None
    if n < 1 or n > 100000:
        return None
    return _EPOCA_PLANILHA + timedelta(days=int(n))


def para_serial(d: date) -> int:
    return (d - _EPOCA_PLANILHA).days


def formatar(d: date | None) -> str:
    return d.strftime("%d/%m/%Y") if d else ""


def canonizar(valor: str | None, vocabulario: list[str]) -> tuple[str, str]:
    """Encaixa um texto livre no vocabulario aceito. Devolve (valor, aviso).

    Sem correspondencia, devolve vazio e um aviso — **nunca** um palpite. Um
    valor fora do vocabulario contamina tudo que depende dele a jusante, e
    ninguem percebe: e mais caro que um campo vazio.
    """
    if not valor:
        return "", ""
    k = chave(valor)
    indice = {chave(v): v for v in vocabulario}
    if k in indice:
        return indice[k], ""
    contidos = [v for kv, v in indice.items() if kv and kv in k]
    if len(contidos) == 1:
        return contidos[0], ""
    return "", "FORA_DO_VOCABULARIO:%s" % valor
