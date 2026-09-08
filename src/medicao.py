"""Mede a extracao contra o que humanos preencheram.

E o modulo que da nome ao projeto. Automatizar uma leitura e facil; saber se a
leitura esta certa e o trabalho.

Duas metricas, e a distincao entre elas importa:

    acuracia  = acertos / (acertos + divergencias)
                dos campos que o extrator preencheu, quantos bateram

    cobertura = preenchidos / (preenchidos + vazios)
                em quantos casos ele conseguiu preencher alguma coisa

Cobertura baixa com acuracia alta e um sistema honesto: ele so responde quando
sabe. O contrario — cobertura alta com acuracia baixa — e um sistema que
chuta, e e o pior resultado possivel, porque parece produtivo.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from .modelo import CAMPOS, ROTULOS, Caso
from .normaliza import canonizar, parse_data


@dataclass
class Placar:
    acerto: int = 0
    divergencia: int = 0
    vazio: int = 0
    sem_gabarito: int = 0

    @property
    def preenchidos(self) -> int:
        return self.acerto + self.divergencia

    @property
    def acuracia(self) -> float:
        return (self.acerto / self.preenchidos * 100) if self.preenchidos else 0.0

    @property
    def cobertura(self) -> float:
        base = self.preenchidos + self.vazio
        return (self.preenchidos / base * 100) if base else 0.0


@dataclass
class Divergencia:
    campo: str
    esperado: object
    obtido: object

    @property
    def dias(self) -> int | None:
        """Direcao e tamanho do desvio, quando os dois lados sao datas.

        A direcao e o sinal mais util do projeto: um erro de leitura erra para
        os dois lados; um erro de REGRA erra sempre para o mesmo. Quando todas
        as divergencias apontam na mesma direcao, o defeito nao esta na
        leitura — esta na definicao do que se esta lendo.
        """
        if isinstance(self.esperado, date) and isinstance(self.obtido, date):
            return (self.esperado - self.obtido).days
        return None


@dataclass
class Medicao:
    placares: dict[str, Placar] = field(default_factory=dict)
    divergencias: list[Divergencia] = field(default_factory=list)
    total: int = 0

    def tabela(self) -> str:
        linhas = [
            "%-22s %8s %13s %8s %11s %12s"
            % ("Campo", "Acertos", "Divergencias", "Vazios", "Acuracia", "Cobertura"),
            "-" * 78,
        ]
        for campo in CAMPOS:
            p = self.placares[campo]
            linhas.append(
                "%-22s %8d %13d %8d %10.1f%% %11.0f%%"
                % (ROTULOS[campo], p.acerto, p.divergencia, p.vazio, p.acuracia, p.cobertura)
            )
        return "\n".join(linhas)

    def direcao_das_divergencias(self) -> str:
        """Diz se as divergencias tem assinatura de regra errada."""
        desvios = [d.dias for d in self.divergencias if d.dias]
        if len(desvios) < 3:
            return ""
        adiantados = sum(1 for d in desvios if d > 0)
        if adiantados in (0, len(desvios)):
            lado = "ANTES" if adiantados == len(desvios) else "DEPOIS"
            mediana = sorted(desvios)[len(desvios) // 2]
            return (
                "%d de %d divergencias com o extrator %s do gabarito, mediana de %d dias.\n"
                "Direcao constante e assinatura de REGRA errada, nao de leitura errada."
                % (len(desvios), len(desvios), lado, abs(mediana))
            )
        return "Divergencias para os dois lados: parece ruido de leitura, nao regra."


def _comparavel(campo: str, valor, vocabulario: list[str]):
    if valor in (None, ""):
        return None
    if campo == "categoria":
        canonica, _ = canonizar(str(valor), vocabulario)
        return canonica or str(valor).strip().upper()
    d = parse_data(valor)
    return d if isinstance(d, date) else None


def medir(casos: list[tuple[Caso, dict]], extrator) -> Medicao:
    m = Medicao(placares={c: Placar() for c in CAMPOS}, total=len(casos))
    vocabulario = extrator.vocabulario

    for caso, gabarito in casos:
        resultado = extrator.extrair(caso)
        for campo in CAMPOS:
            esperado = _comparavel(campo, gabarito.get(campo), vocabulario)
            obtido = _comparavel(campo, resultado.valor(campo), vocabulario)
            p = m.placares[campo]
            if esperado is None:
                p.sem_gabarito += 1
            elif obtido is None:
                p.vazio += 1
            elif esperado == obtido:
                p.acerto += 1
            else:
                p.divergencia += 1
                m.divergencias.append(Divergencia(ROTULOS[campo], esperado, obtido))
    return m
