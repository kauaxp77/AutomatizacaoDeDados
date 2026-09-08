"""Demonstração completa: gera casos, extrai, mede e compara regras.

    python demo.py                 mede a configuração atual
    python demo.py --comparar      mostra a fonte errada ao lado da certa
    python demo.py --detalhar      lista as divergências
    python demo.py --n 300         outro tamanho de amostra
    python demo.py --semente 7     outra amostra (validação cega)

Não há sistema externo: os casos são sintéticos e o gabarito é conhecido.
"""

from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
sys.path.insert(0, str(RAIZ))

import yaml  # noqa: E402

from exemplos.gerar import gerar  # noqa: E402
from src.extrator import Extrator  # noqa: E402
from src.medicao import medir  # noqa: E402
from src.modelo import Caso, Evento, Notificacao  # noqa: E402
from src.normaliza import parse_data  # noqa: E402


def carregar_casos(pasta: Path) -> list[tuple[Caso, dict]]:
    casos = []
    for arq in sorted(pasta.glob("caso_*.json")):
        o = json.loads(arq.read_text(encoding="utf-8"))
        caso = Caso(identificador=arq.stem)
        for e in o["eventos"]:
            caso.eventos.append(Evento(data=parse_data(e["data"]), texto=e["texto"]))
        for n in o["notificacoes"]:
            caso.notificacoes.append(Notificacao(texto=n["texto"]))
        casos.append((caso, o["gabarito"]))
    return casos


def main() -> int:
    p = argparse.ArgumentParser(description="Demonstração do extrator auditável.")
    p.add_argument("--n", type=int, default=120, help="quantos casos gerar")
    p.add_argument("--semente", type=int, default=42, help="semente da amostra")
    p.add_argument("--comparar", action="store_true", help="mede as duas fontes lado a lado")
    p.add_argument("--detalhar", action="store_true", help="lista as divergências")
    args = p.parse_args()

    pasta = RAIZ / "exemplos" / "casos"
    gerar(args.n, pasta, args.semente)
    casos = carregar_casos(pasta)

    regras = yaml.safe_load((RAIZ / "config" / "regras.yaml").read_text(encoding="utf-8"))

    print()
    print("%d casos sintéticos | semente %d" % (len(casos), args.semente))

    if args.comparar:
        errada = copy.deepcopy(regras)
        errada["respostas"]["fonte"] = "notificacao"
        print()
        print("=" * 78)
        print(" FONTE: notificação — a leitura intuitiva (quando a parte VISUALIZOU)")
        print("=" * 78)
        m_errada = medir(casos, Extrator(errada))
        print(m_errada.tabela())
        print()
        print(m_errada.direcao_das_divergencias())

    print()
    print("=" * 78)
    print(" FONTE: cronologia — quando a parte RESPONDEU")
    print("=" * 78)
    medicao = medir(casos, Extrator(regras))
    print(medicao.tabela())

    direcao = medicao.direcao_das_divergencias()
    if direcao:
        print()
        print(direcao)

    if args.detalhar and medicao.divergencias:
        print()
        print("Divergências:")
        for d in medicao.divergencias[:20]:
            desvio = " (%+d dias)" % d.dias if d.dias else ""
            print("  %-22s gabarito=%s  extrator=%s%s" % (d.campo, d.esperado, d.obtido, desvio))

    print()
    print("Campos preenchidos sem evidência: 0 — por construção.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
