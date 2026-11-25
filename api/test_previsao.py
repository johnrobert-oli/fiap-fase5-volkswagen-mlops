import os

import json
import numpy as np
import pandas as pd
from copy import deepcopy
from unittest.mock import patch
from fastapi.testclient import TestClient
from main import app

# Relógio fixo para tornar os testes reproduzíveis
instante = pd.Timestamp("2026-11-19T22:00:00Z")

with patch("previsao.agora_utc", return_value=instante):
    with patch.dict(os.environ, DATABASE_URL="", MONITOR_DB_PATH=":memory:"), TestClient(app) as cliente:
        # 1. Previsão usando o modelo salvo
        resposta = cliente.post("/prever", json={"ticker": "VOW3.DE"})
        assert resposta.status_code == 200, resposta.text
        original = resposta.json()

        np.testing.assert_allclose(
            original["fechamento_previsto"],
            app.state.metadados["previsao_referencia"],
            rtol=0, atol=1e-8
        )
        assert original["data_prevista"] == "2026-11-17"
        assert original["pregao_alvo_ja_encerrado"] is True
        print("PASSOU: previsão original e data do pregão.")

        # 2. Atualização com dois fechamentos FICTÍCIOS
        observacoes = [
            {"data": "2026-11-17", "fechamento": 68.0},
            {"data": "2026-11-18", "fechamento": 69.0}
        ]
        resposta = cliente.post("/prever", json={
            "ticker": "VOW3.DE",
            "observacoes": observacoes
        })
        assert resposta.status_code == 200, resposta.text
        atualizado = resposta.json()

        referencia = deepcopy(app.state.modelo).append(
            [68.0, 69.0], refit=False
        )
        np.testing.assert_allclose(
            atualizado["fechamento_previsto"],
            float(referencia.forecast(steps=1)[0]),
            rtol=0, atol=1e-8
        )
        assert atualizado["data_prevista"] == "2026-11-19"
        assert atualizado["baseline_ultimo_fechamento"] == 69.0
        assert atualizado["novas_observacoes"] == 2
        print("PASSOU: novos dados chegam ao modelo corretamente.")

        # 3. Uma requisição não modifica a próxima
        repetida = cliente.post(
            "/prever", json={"ticker": "VOW3.DE"}
        )
        assert repetida.status_code == 200
        assert {k: v for k, v in repetida.json().items() if k != "previsao_id"} == {k: v for k, v in original.items() if k != "previsao_id"}
        print("PASSOU: modelo original preservado entre requisições.")

        # 4. Entradas que a API deve rejeitar
        casos_invalidos = {
            "Outra ação": {"ticker": "PETR4.SA"},
            "Campo desconhecido": {"ticker": "VOW3.DE", "extra": 1},
            "Preço zero": {
                "ticker": "VOW3.DE",
                "observacoes": [{"data": "2026-11-17", "fechamento": 0}]
            },
            "Data já incorporada": {
                "ticker": "VOW3.DE",
                "observacoes": [{"data": "2026-11-16", "fechamento": 68.0}]
            },
            "Pregão pulado": {
                "ticker": "VOW3.DE",
                "observacoes": [observacoes[1]]
            },
            "Data repetida": {
                "ticker": "VOW3.DE",
                "observacoes": [observacoes[0], observacoes[0]]
            },
            "Ordem invertida": {
                "ticker": "VOW3.DE",
                "observacoes": list(reversed(observacoes))
            },
            "Data futura": {
                "ticker": "VOW3.DE",
                "observacoes": [{"data": "2099-01-01", "fechamento": 68.0}]
            }
        }

        for nome, pedido in casos_invalidos.items():
            resposta = cliente.post("/prever", json=pedido)
            assert resposta.status_code == 422, (nome, resposta.text)
            print(f"PASSOU: rejeita {nome.lower()}.")

        # 5. Rejeita fechamento de um pregão ainda aberto
        with patch(
            "previsao.agora_utc",
            return_value=pd.Timestamp("2026-11-17T10:00:00Z")
        ):
            resposta = cliente.post("/prever", json={
                "ticker": "VOW3.DE",
                "observacoes": [observacoes[0]]
            })
            assert resposta.status_code == 422, resposta.text
            print("PASSOU: rejeita fechamento de pregão ainda aberto.")

        print("\nRESPOSTA ORIGINAL:")
        print(json.dumps(original, indent=2, ensure_ascii=False))
        print("\nTodos os testes de previsão passaram.")
