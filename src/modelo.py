"""Os tipos que atravessam o projeto.

O extrator nao conhece navegador nem HTML. Ele recebe `Caso` — duas listas de
texto ja lidas de algum lugar — e devolve `Resultado`. Essa fronteira e o que
permite medir a extracao offline, milhares de vezes, sem tocar no sistema de
origem.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Protocol

CAMPOS = ("categoria", "data_decisao", "resposta_parte_a", "resposta_parte_b", "data_encerramento")

ROTULOS = {
    "categoria": "CATEGORIA",
    "data_decisao": "DATA DA DECISAO",
    "resposta_parte_a": "RESPOSTA PARTE A",
    "resposta_parte_b": "RESPOSTA PARTE B",
    "data_encerramento": "ENCERRAMENTO",
}

CONFIANCAS = ("baixa", "media", "alta")


@dataclass
class Evento:
    """Uma linha da cronologia do caso.

    O texto costuma vir no formato "<ATO EM CAIXA ALTA> <id> - <tipo> <hh:mm>",
    que e como sistemas antigos costumam montar a lista.
    """

    data: date | None
    texto: str

    @property
    def ato(self) -> str:
        """O que aconteceu, sem o identificador do documento."""
        return re.split(r"\b\d{6,12}\s*-\s*", self.texto)[0].strip()

    @property
    def hora(self) -> str:
        """Ancora barata para ligar este evento a uma notificacao."""
        m = re.search(r"(\d{1,2}:\d{2})\s*$", self.texto)
        return m.group(1) if m else ""


@dataclass
class Notificacao:
    """Um aviso enviado a uma das partes."""

    texto: str
    destinatario: str = ""
    enviada_em: date | None = None
    visualizada_em: date | None = None


@dataclass
class Caso:
    identificador: str
    eventos: list[Evento] = field(default_factory=list)
    notificacoes: list[Notificacao] = field(default_factory=list)

    @property
    def vazio(self) -> bool:
        return not self.eventos and not self.notificacoes


@dataclass
class Campo:
    valor: Any = None
    confianca: str = ""
    evidencia: str = ""


@dataclass
class Resultado:
    """O que o extrator devolve.

    Cada campo carrega a evidencia que o originou. E o que torna a conferencia
    possivel sem reabrir o sistema — e o que permite discutir uma divergencia
    olhando o texto, em vez de opiniao.
    """

    campos: dict[str, Campo] = field(default_factory=dict)
    observacoes: list[str] = field(default_factory=list)

    def valor(self, campo: str) -> Any:
        c = self.campos.get(campo)
        return c.valor if c else None

    def registrar(self, campo: str, valor, confianca: str, evidencia: str) -> None:
        if valor:
            self.campos[campo] = Campo(valor, confianca, evidencia[:180])

    @property
    def confianca_geral(self) -> str:
        presentes = [c.confianca for c in self.campos.values() if c.valor and c.confianca]
        if not presentes:
            return "baixa"
        return min(presentes, key=lambda c: CONFIANCAS.index(c) if c in CONFIANCAS else 0)

    @property
    def observacao(self) -> str:
        return " | ".join(self.observacoes)

    @property
    def evidencia(self) -> str:
        partes = [k + "=" + c.evidencia for k, c in self.campos.items() if c.valor and c.evidencia]
        return " || ".join(partes)[:600]


class Fonte(Protocol):
    """De onde os casos vem.

    A implementacao de referencia le casos gravados em disco. Uma implementacao
    real conversaria com o sistema de origem — via navegador, API ou banco — e
    devolveria a mesma estrutura. O extrator nao sabe a diferenca, e e por isso
    que ele pode ser medido sem o sistema estar disponivel.
    """

    def casos(self) -> list[tuple[Caso, dict[str, str]]]:
        """Devolve (caso, gabarito). O gabarito e o que humanos preencheram."""
        ...
