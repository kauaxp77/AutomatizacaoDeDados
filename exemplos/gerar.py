"""Gera casos sinteticos com gabarito conhecido.

Nenhum dado real, nenhum sistema real. O gerador reproduz de proposito as duas
armadilhas que apareceram no projeto original:

1. A parte VISUALIZA o aviso um dia, e RESPONDE outro. A leitura intuitiva
   pega a visualizacao; o gabarito e a resposta. O desvio e de poucos dias e
   sempre no mesmo sentido — exatamente o que torna o erro invisivel numa
   conferencia por amostragem.

2. A mesma parte se manifesta mais de uma vez. Escolher "a primeira depois da
   decisao" ou "a mais recente" muda o resultado, e a resposta certa e
   diferente para cada parte. Nao ha como saber sem medir.

Alem disso, parte dos casos usa o ato generico "ENCERRADO O CASO", que nao
declara categoria — para que a cobertura fique realista e o extrator tenha
onde exercitar a recusa de responder.
"""

from __future__ import annotations

import json
import random
from datetime import date, timedelta
from pathlib import Path

MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]

CATEGORIAS = [
    ("CUMPRIMENTO", "ENCERRADO O CASO POR CUMPRIMENTO INTEGRAL"),
    ("DESISTENCIA", "ENCERRADO O CASO POR DESISTENCIA DA PARTE"),
    ("PRESCRICAO", "ENCERRADA A ANALISE POR PRESCRICAO"),
    ("REDIRECIONAMENTO", "DECLARADA INCOMPETENCIA"),
    ("PERDA DE OBJETO", "DECLARADA PERDA DE OBJETO"),
]

# O ato generico: registra o encerramento sem dizer o motivo. Existe no mundo
# real e e a razao de a cobertura da categoria nunca chegar a 100%.
GENERICO = "CONCLUIDA A ANALISE"


def _por_extenso(d: date) -> str:
    return "%d %s %d" % (d.day, MESES[d.month - 1], d.year)


def _doc(seq: int) -> int:
    return 100000 + seq * 137


def gerar_caso(indice: int, aleatorio: random.Random) -> tuple[dict, dict]:
    inicio = date(2024, 1, 1) + timedelta(days=aleatorio.randint(0, 600))
    decisao = inicio + timedelta(days=aleatorio.randint(30, 200))

    # A categoria SEMPRE existe no gabarito: quem preencheu leu o documento
    # inteiro. Mas em parte dos casos o sistema registra so o ato generico, sem
    # dizer o motivo. Nesses, o extrator tem de deixar o campo vazio — e a
    # cobertura cai. Cobertura baixa com acuracia alta e um sistema honesto.
    categoria, texto_decisao = aleatorio.choice(CATEGORIAS)
    if aleatorio.random() < 0.35:
        texto_decisao = GENERICO

    # A parte A costuma responder mais de uma vez; vale a ultima.
    respostas_a = sorted(
        {decisao + timedelta(days=aleatorio.randint(1, 12)) for _ in range(aleatorio.randint(1, 3))}
    )
    # A parte B responde uma vez; vale a primeira depois da decisao.
    respostas_b = [decisao + timedelta(days=aleatorio.randint(1, 8))]

    encerramento = max(respostas_a + respostas_b) + timedelta(days=aleatorio.randint(3, 25))

    eventos = []

    def evento(quando: date, texto: str, seq: int) -> None:
        hora = "%02d:%02d" % (aleatorio.randint(8, 19), aleatorio.randint(0, 59))
        eventos.append({
            "data": _por_extenso(quando),
            "texto": "%s %d - Documento %s" % (texto, _doc(seq), hora),
        })

    evento(inicio, "RECEBIDO O EXPEDIENTE", indice * 10)
    evento(decisao - timedelta(days=2), "CONCLUSOS PARA ANALISE", indice * 10 + 1)
    evento(decisao, texto_decisao, indice * 10 + 2)
    for n, quando in enumerate(respostas_a):
        evento(quando, "JUNTADA DE MANIFESTACAO DA PARTE A", indice * 10 + 3 + n)
    for n, quando in enumerate(respostas_b):
        evento(quando, "JUNTADA DE MANIFESTACAO DA PARTE B", indice * 10 + 6 + n)
    evento(encerramento, "ARQUIVADO DEFINITIVAMENTE EM %s" % encerramento.strftime("%d/%m/%Y"),
           indice * 10 + 8)

    # Cronologia do mais recente para o mais antigo, como nas telas reais.
    eventos.reverse()

    # As notificacoes trazem "visualizada em", quase sempre no mesmo dia do
    # envio. Parece a resposta da parte. Nao e.
    notificacoes = []
    for parte, respostas in (("PARTE A", respostas_a), ("PARTE B", respostas_b)):
        visualizacao = decisao + timedelta(days=aleatorio.randint(0, 1))
        notificacoes.append({
            "texto": "Aviso (%d) - Destinatario: %s Enviada em %s Visualizada em %s"
            % (_doc(indice * 10 + 9), parte, decisao.strftime("%d/%m/%Y"),
               visualizacao.strftime("%d/%m/%Y")),
        })

    gabarito = {
        "categoria": categoria,
        "data_decisao": decisao.isoformat(),
        "resposta_parte_a": respostas_a[-1].isoformat(),   # a ULTIMA
        "resposta_parte_b": respostas_b[0].isoformat(),    # a PRIMEIRA
        "data_encerramento": encerramento.isoformat(),
    }

    # Erro humano de transcricao, em 4% dos casos. Existe em qualquer base
    # preenchida a mao, e e o motivo de nem toda divergencia ser culpa do
    # extrator. Diferente do erro de regra, este erra para os dois lados —
    # e a medicao consegue distinguir os dois.
    if aleatorio.random() < 0.04:
        campo = aleatorio.choice(["data_decisao", "resposta_parte_a", "data_encerramento"])
        desvio = aleatorio.choice([-1, 1])
        original = date.fromisoformat(gabarito[campo])
        gabarito[campo] = (original + timedelta(days=desvio)).isoformat()

    return {"eventos": eventos, "notificacoes": notificacoes, "gabarito": gabarito}, gabarito


def gerar(quantidade: int, destino: Path, semente: int = 42) -> int:
    aleatorio = random.Random(semente)
    destino.mkdir(parents=True, exist_ok=True)
    for arq in destino.glob("caso_*.json"):
        arq.unlink()
    for i in range(1, quantidade + 1):
        caso, _ = gerar_caso(i, aleatorio)
        (destino / ("caso_%03d.json" % i)).write_text(
            json.dumps(caso, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    return quantidade


if __name__ == "__main__":
    import sys

    n = int(sys.argv[1]) if len(sys.argv) > 1 else 120
    pasta = Path(__file__).resolve().parent / "casos"
    print("gerados %d casos em %s" % (gerar(n, pasta), pasta))
