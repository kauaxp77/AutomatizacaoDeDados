"""Caso -> campos, com evidencia e nivel de confianca.

Um principio governa o modulo inteiro: **sem evidencia, campo vazio**.

Um campo errado custa mais caro que um campo vazio. O vazio aparece na
conferencia e alguem resolve; o errado entra na base, alimenta o que vem
depois e ninguem descobre. Por isso nao ha nenhum caminho aqui que produza um
valor por aproximacao ou por padrao.
"""

from __future__ import annotations

import re
from datetime import date

from .modelo import Caso, Evento, Notificacao, Resultado
from .normaliza import canonizar, chave, parse_data


class Extrator:
    def __init__(self, regras: dict):
        self.regras = regras
        self.vocabulario = regras.get("vocabulario", [])

        dec = regras.get("decisao") or {}
        self._re_decisao = [re.compile(p, re.I) for p in dec.get("padroes", [])]
        self._categorias_diretas = [
            (re.compile(i["padrao"], re.I), i["valor"]) for i in dec.get("categorias_diretas", [])
        ]
        self._re_sem_categoria = [re.compile(p, re.I) for p in dec.get("sem_categoria", [])]

        enc = regras.get("encerramento") or {}
        self._re_enc_data = (
            re.compile(enc["padrao_com_data"], re.I) if enc.get("padrao_com_data") else None
        )
        self._re_enc = [re.compile(p, re.I) for p in enc.get("padroes", [])]

        resp = regras.get("respostas") or {}
        self._fonte_resposta = resp.get("fonte", "cronologia")
        self._partes = {
            "resposta_parte_a": resp.get("parte_a") or {},
            "resposta_parte_b": resp.get("parte_b") or {},
        }
        self._re_visualizacao = _talvez(resp.get("padrao_visualizacao"))
        self._re_envio = _talvez(resp.get("padrao_envio"))
        self._re_destinatario = _talvez(resp.get("padrao_destinatario"))

        self._ignorar = [re.compile(p, re.I) for p in (regras.get("ignorar") or [])]

    # ------------------------------------------------------------ auxiliares

    def _interessa(self, evento: Evento) -> bool:
        alvo = chave(evento.ato)
        return not any(r.search(alvo) for r in self._ignorar)

    def _achar_decisao(self, eventos: list[Evento]) -> tuple[Evento | None, str]:
        """A decisao mais recente, e a categoria que ela declara (se declara)."""
        for evento in eventos:
            if not self._interessa(evento):
                continue
            alvo = chave(evento.ato)

            for regex in self._re_decisao:
                m = regex.search(alvo)
                if m:
                    return evento, m.group("categoria").strip()

            for regex, valor in self._categorias_diretas:
                if regex.search(alvo):
                    return evento, valor

            if any(r.search(alvo) for r in self._re_sem_categoria):
                return evento, ""
        return None, ""

    def _achar_encerramento(self, eventos: list[Evento]) -> tuple[date | None, str]:
        for evento in eventos:
            alvo = chave(evento.ato)
            if self._re_enc_data:
                m = self._re_enc_data.search(alvo)
                if m:
                    return parse_data(m.group("data")), evento.ato
            if any(r.search(alvo) for r in self._re_enc) and evento.data:
                return evento.data, evento.ato
        return None, ""

    def _da_cronologia(
        self, eventos: list[Evento], padroes: list[str], regra: str, referencia: date | None
    ) -> tuple[date | None, str]:
        """A data em que a parte juntou sua manifestacao — a fonte correta."""
        regexes = [re.compile(p, re.I) for p in padroes]
        if not regexes:
            return None, ""
        candidatos = [
            e for e in eventos if e.data and any(r.search(chave(e.texto)) for r in regexes)
        ]
        if not candidatos:
            return None, ""
        if referencia:
            posteriores = [e for e in candidatos if e.data >= referencia]
            if posteriores:
                escolhido = (
                    max(posteriores, key=lambda e: e.data)
                    if regra == "ultima"
                    else min(posteriores, key=lambda e: e.data)
                )
                return escolhido.data, escolhido.texto
        escolhido = max(candidatos, key=lambda e: e.data)
        return escolhido.data, escolhido.texto

    def _da_notificacao(
        self, notificacoes: list[Notificacao], padroes: list[str]
    ) -> tuple[date | None, str]:
        """A data em que a parte VISUALIZOU o aviso.

        Mantido de proposito: e a leitura intuitiva, e e a errada. Serve para
        reproduzir o erro original e medir o tamanho dele.
        """
        regexes = [re.compile(p, re.I) for p in padroes]
        for n in notificacoes:
            alvo = chave(n.destinatario or n.texto)
            if any(r.search(alvo) for r in regexes):
                data = n.visualizada_em or n.enviada_em
                if data:
                    return data, n.texto
        return None, ""

    # --------------------------------------------------------------- publico

    def extrair(self, caso: Caso) -> Resultado:
        res = Resultado()
        if caso.vazio:
            res.observacoes.append("SEM_DADOS")
            return res

        for n in caso.notificacoes:
            _preencher_notificacao(n, self._re_destinatario, self._re_envio, self._re_visualizacao)

        evento, categoria_bruta = self._achar_decisao(caso.eventos)
        if evento is None:
            res.observacoes.append("SEM_ATO_DE_DECISAO")
        else:
            res.registrar("data_decisao", evento.data, "alta", evento.ato)
            if not evento.data:
                res.observacoes.append("SEM_DATA_DA_DECISAO")

            if categoria_bruta:
                canonica, aviso = canonizar(categoria_bruta, self.vocabulario)
                if canonica:
                    res.registrar("categoria", canonica, "alta", evento.ato)
                else:
                    res.observacoes.append(aviso or "FORA_DO_VOCABULARIO")
            else:
                # O sistema registrou o encerramento mas nao disse por que.
                # Preencher aqui seria inventar.
                res.observacoes.append("CATEGORIA_NAO_DECLARADA")

        data_enc, evidencia = self._achar_encerramento(caso.eventos)
        if data_enc:
            res.registrar("data_encerramento", data_enc, "alta", evidencia)
        else:
            res.observacoes.append("SEM_ENCERRAMENTO")

        referencia = res.valor("data_decisao")
        for campo, cfg in self._partes.items():
            if self._fonte_resposta == "notificacao":
                data, evidencia = self._da_notificacao(
                    caso.notificacoes, cfg.get("padroes_notificacao", [])
                )
                confianca = "baixa"
            else:
                data, evidencia = self._da_cronologia(
                    caso.eventos,
                    cfg.get("padroes_cronologia", []),
                    cfg.get("regra", "primeira"),
                    referencia,
                )
                confianca = "alta"
            if data:
                res.registrar(campo, data, confianca, evidencia)
            else:
                res.observacoes.append("SEM_" + campo.upper())

        return res


def _talvez(padrao: str | None):
    return re.compile(padrao, re.I) if padrao else None


def _preencher_notificacao(n: Notificacao, re_dest, re_env, re_vis) -> None:
    alvo = chave(n.texto)
    if re_dest and not n.destinatario:
        m = re_dest.search(alvo)
        if m:
            n.destinatario = m.group("quem").strip()
    if re_env and n.enviada_em is None:
        m = re_env.search(alvo)
        if m:
            n.enviada_em = parse_data(m.group("data"))
    if re_vis and n.visualizada_em is None:
        m = re_vis.search(alvo)
        if m:
            n.visualizada_em = parse_data(m.group("data"))
