
import json
import os
import sqlite3
import hashlib
from pathlib import Path
from datetime import timedelta

import numpy as np
import pandas as pd
import yfinance as yf
import exchange_calendars as xcals

from registros import caminho_banco

def agora_utc():
    return pd.Timestamp.now(tz="UTC")

def avaliar():
    banco = caminho_banco()
    pasta = Path(os.environ.get(
        "MONITOR_REPORT_DIR",
        str(banco.parent / "relatorios")
    ))
    pasta.mkdir(parents=True, exist_ok=True)

    agora = agora_utc()
    relatorio = {
        "gerado_em": agora.isoformat(),
        "status": "sem dados suficientes",
        "fonte_reais": "Yahoo Finance via yfinance",
        "grupos": []
    }

    def salvar():
        destino = pasta / "qualidade_previsoes.json"
        destino.write_text(
            json.dumps(relatorio, indent=2, ensure_ascii=False),
            encoding="utf-8"
        )
        return relatorio

    if not banco.exists():
        relatorio["motivo"] = "Nenhuma previsão registrada neste ambiente."
        return salvar()

    with sqlite3.connect(str(banco)) as conexao:
        existe = conexao.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type='table' AND name='previsoes'"
        ).fetchone()

        if not existe:
            relatorio["motivo"] = "Tabela de previsões ainda não criada."
            return salvar()

        previsoes = pd.read_sql_query(
            "SELECT * FROM previsoes", conexao
        )

    relatorio["registros_encontrados"] = len(previsoes)

    if previsoes.empty:
        relatorio["motivo"] = "Nenhuma previsão registrada."
        return salvar()

    previsoes["data_prevista"] = pd.to_datetime(
        previsoes["data_prevista"]
    )
    previsoes["criado_em"] = pd.to_datetime(
        previsoes["criado_em"], utc=True
    )

    calendario = xcals.get_calendar(
        "XETR",
        start=str(previsoes["data_prevista"].min().date()),
        end=str(previsoes["data_prevista"].max().date() + timedelta(days=7))
    )

    elegiveis = []
    for _, linha in previsoes.iterrows():
        data = linha["data_prevista"]
        if not calendario.is_session(data):
            continue

        encerramento = calendario.session_close(data)

        if (
            not linha["alvo_ja_encerrado"]
            and linha["criado_em"] < encerramento <= agora
        ):
            elegiveis.append(linha.to_dict())

    if not elegiveis:
        relatorio["motivo"] = (
            "Nenhuma previsão anterior ao fechamento com resultado já disponível."
        )
        return salvar()

    elegiveis = pd.DataFrame(elegiveis)

    # Usa a primeira previsão registrada por data, versão e origem.
    elegiveis = elegiveis.sort_values("criado_em").drop_duplicates(
        ["ticker", "data_prevista", "versao_modelo", "origem"],
        keep="first"
    )

    relatorio["previsoes_elegiveis"] = len(elegiveis)

    inicio = elegiveis["data_prevista"].min().date()
    fim = elegiveis["data_prevista"].max().date() + timedelta(days=1)

    reais = yf.download(
        "VOW3.DE",
        start=str(inicio),
        end=str(fim),
        auto_adjust=False,
        multi_level_index=False,
        progress=False
    )

    if reais is None or reais.empty:
        relatorio["status"] = "coleta indisponivel"
        relatorio["motivo"] = "A fonte não retornou preços."
        return salvar()

    reais.index = pd.to_datetime(reais.index).tz_localize(None).normalize()

    # Preserva a resposta da fonte para auditoria
    conteudo_csv = reais.to_csv(index_label="Date")
    hash_coleta = hashlib.sha256(
        conteudo_csv.encode("utf-8")
    ).hexdigest()

    arquivo_coleta = pasta / f"fechamentos_{hash_coleta}.csv"
    arquivo_coleta.write_text(conteudo_csv, encoding="utf-8")
    relatorio["coleta_sha256"] = hash_coleta

    # Não utiliza observações suspeitas como fechamento real
    colunas = ["Open", "High", "Low", "Close", "Volume"]
    valores = reais[colunas]
    validos = (
        np.isfinite(valores).all(axis=1)
        & (reais["Volume"] > 0)
        & (reais[["Open", "High", "Low", "Close"]] > 0).all(axis=1)
        & (reais["High"] >= reais[["Open", "Low", "Close"]].max(axis=1))
        & (reais["Low"] <= reais[["Open", "High", "Close"]].min(axis=1))
    )

    fechamentos = reais.loc[validos, ["Close"]].rename(
        columns={"Close": "real"}
    )

    pares = elegiveis.merge(
        fechamentos,
        left_on="data_prevista",
        right_index=True,
        how="inner",
        validate="many_to_one"
    )

    relatorio["previsoes_com_real_validado"] = len(pares)
    relatorio["aguardando_real_validado"] = len(elegiveis) - len(pares)

    if pares.empty:
        relatorio["motivo"] = "Nenhum fechamento real passou nas verificações."
        return salvar()

    for (versao, origem), grupo in pares.groupby(
        ["versao_modelo", "origem"]
    ):
        metricas = {}
        for nome, coluna in [("ARIMA", "previsao"), ("Baseline", "baseline")]:
            erros = grupo["real"] - grupo[coluna]
            metricas[nome] = {
                "mae_eur": float(erros.abs().mean()),
                "rmse_eur": float(np.sqrt((erros ** 2).mean())),
                "mape_percentual": float(
                    (erros.abs() / grupo["real"]).mean() * 100
                )
            }

        relatorio["grupos"].append({
            "versao_modelo": versao,
            "origem_entradas": origem,
            "quantidade": len(grupo),
            "metricas": metricas
        })

    pares.to_csv(pasta / "previsoes_avaliadas.csv", index=False)
    relatorio["status"] = "avaliado"
    relatorio["observacao"] = (
        "Métricas descritivas da amostra disponível. "
        "Preços informados pelo usuário não foram verificados na origem."
    )
    return salvar()

if __name__ == "__main__":
    print(json.dumps(avaliar(), indent=2, ensure_ascii=False))
