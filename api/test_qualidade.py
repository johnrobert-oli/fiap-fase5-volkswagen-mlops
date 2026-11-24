
import os
import json
import sqlite3
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np
import pandas as pd
import avaliar_previsoes as avaliador
from registros import registrar_previsao

with tempfile.TemporaryDirectory() as pasta:
    banco = Path(pasta) / "teste.sqlite3"
    relatorios = Path(pasta) / "relatorios"
    os.environ["MONITOR_DB_PATH"] = str(banco)
    os.environ["MONITOR_REPORT_DIR"] = str(relatorios)

    pedido = SimpleNamespace(
        model_dump=lambda **kwargs: {
            "ticker": "VOW3.DE", "observacoes": []
        }
    )

    def adicionar(data, previsao, baseline, criado_em, encerrado=False):
        identificador = registrar_previsao(pedido, {
            "ticker": "VOW3.DE",
            "dados_ate": "2026-11-16",
            "data_prevista": data,
            "fechamento_previsto": previsao,
            "baseline_ultimo_fechamento": baseline,
            "versao_modelo": "modelo_ficticio",
            "pregao_alvo_ja_encerrado": encerrado
        })

        with sqlite3.connect(str(banco)) as conexao:
            conexao.execute(
                "UPDATE previsoes SET criado_em = ? WHERE id = ?",
                (criado_em, identificador)
            )
        return identificador

    instante = pd.Timestamp("2026-11-20T20:00:00Z")

    with patch.object(avaliador, "agora_utc", return_value=instante):
        with patch.object(avaliador.yf, "download") as consulta:
            vazio = avaliador.avaliar()
            assert vazio["status"] == "sem dados suficientes"
            consulta.assert_not_called()
            print("PASSOU: ausência de previsões não gera métricas inventadas.")

            adicionar(
                "2026-11-17", 500.0, 500.0,
                "2026-11-17T20:00:00+00:00", encerrado=True
            )
            historico = avaliador.avaliar()
            assert historico["status"] == "sem dados suficientes"
            consulta.assert_not_called()
            print("PASSOU: consulta histórica não entra na avaliação.")

        # Previsões fictícias registradas antes dos respectivos fechamentos
        adicionar("2026-11-17", 100.0, 99.0, "2026-11-17T10:00:00+00:00")
        adicionar("2026-11-18", 104.0, 102.0, "2026-11-18T10:00:00+00:00")
        adicionar("2026-11-19", 103.0, 102.0, "2026-11-19T10:00:00+00:00")

        # Repetição: deve prevalecer a primeira previsão daquele dia
        adicionar("2026-11-17", 999.0, 999.0, "2026-11-17T11:00:00+00:00")

        # Mesmo com a marcação incorreta, o horário deve impedir sua inclusão
        adicionar("2026-11-18", 999.0, 999.0, "2026-11-18T20:00:00+00:00")

        reais_ficticios = pd.DataFrame({
            "Open": [101.0, 102.0, 103.0],
            "High": [103.0, 104.0, 103.0],
            "Low": [100.0, 101.0, 103.0],
            "Close": [102.0, 103.0, 103.0],
            "Volume": [1000, 1000, 0]
        }, index=pd.to_datetime([
            "2026-11-17", "2026-11-18", "2026-11-19"
        ]))

        with patch.object(
            avaliador.yf, "download", return_value=reais_ficticios
        ) as consulta:
            resultado = avaliador.avaliar()
            consulta.assert_called_once()

        assert resultado["status"] == "avaliado"
        assert resultado["previsoes_elegiveis"] == 3
        assert resultado["previsoes_com_real_validado"] == 2
        assert resultado["aguardando_real_validado"] == 1
        assert len(resultado["grupos"]) == 1

        grupo = resultado["grupos"][0]
        assert grupo["quantidade"] == 2
        arima = grupo["metricas"]["ARIMA"]
        baseline = grupo["metricas"]["Baseline"]

        # Erros absolutos esperados: ARIMA [2, 1], baseline [3, 1]
        np.testing.assert_allclose(arima["mae_eur"], 1.5)
        np.testing.assert_allclose(arima["rmse_eur"], np.sqrt(2.5))
        np.testing.assert_allclose(
            arima["mape_percentual"],
            ((2 / 102 + 1 / 103) / 2) * 100
        )
        np.testing.assert_allclose(baseline["mae_eur"], 2.0)
        np.testing.assert_allclose(baseline["rmse_eur"], np.sqrt(5.0))

        print("PASSOU: duplicidades e registros atrasados são excluídos.")
        print("PASSOU: fechamento com volume zero fica pendente.")
        print("PASSOU: métricas conferem com o cálculo manual.")

        salvo = json.loads(
            (relatorios / "qualidade_previsoes.json").read_text(
                encoding="utf-8"
            )
        )
        assert salvo == resultado
        assert (relatorios / "previsoes_avaliadas.csv").exists()
        assert list(relatorios.glob("fechamentos_*.csv"))

        print("PASSOU: relatório e evidências da coleta foram salvos.")
        print("Todos os testes de qualidade passaram com dados fictícios.")
