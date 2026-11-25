from unittest.mock import patch
import os

from fastapi.testclient import TestClient
from prometheus_client.parser import text_string_to_metric_families
from main import app

def obter_valor(texto, nome, etiquetas):
    for familia in text_string_to_metric_families(texto):
        for amostra in familia.samples:
            if amostra.name == nome and amostra.labels == etiquetas:
                return amostra.value
    raise AssertionError(f"Métrica não encontrada: {nome} {etiquetas}")

with patch.dict(os.environ, DATABASE_URL="", MONITOR_DB_PATH=":memory:"), TestClient(app) as cliente:
    valida = cliente.post("/prever", json={"ticker": "VOW3.DE"})
    assert valida.status_code == 200, valida.text

    invalida = cliente.post("/prever", json={"ticker": "INVALIDO"})
    assert invalida.status_code == 422, invalida.text

    inexistente = cliente.get("/rota-inexistente-teste")
    assert inexistente.status_code == 404

    resposta = cliente.get("/metrics")
    assert resposta.status_code == 200
    texto = resposta.text

    casos = [
        ("POST", "/prever", "200"),
        ("POST", "/prever", "422"),
        ("GET", "rota_nao_encontrada", "404")
    ]

    for metodo, rota, status in casos:
        quantidade = obter_valor(
            texto,
            "api_requisicoes_total",
            {"metodo": metodo, "rota": rota, "status": status}
        )
        assert quantidade == 1, (rota, status, quantidade)
        print(f"PASSOU: {metodo} {rota} — status {status}, quantidade 1.")

    etiquetas = {"metodo": "POST", "rota": "/prever"}

    quantidade_tempos = obter_valor(
        texto, "api_duracao_segundos_count", etiquetas
    )
    tempo_total = obter_valor(
        texto, "api_duracao_segundos_sum", etiquetas
    )

    assert quantidade_tempos == 2
    assert tempo_total > 0
    print("PASSOU: duração registrada para as duas chamadas de previsão.")

    # Consultar as métricas não deve aumentar os próprios contadores
    segunda_coleta = cliente.get("/metrics")
    assert segunda_coleta.status_code == 200
    assert segunda_coleta.text == texto
    print("PASSOU: coleta de métricas não altera os contadores.")

    print("\nMonitoramento operacional verificado com sucesso.")
