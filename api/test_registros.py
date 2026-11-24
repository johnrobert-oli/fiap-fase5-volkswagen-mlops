
import os
import json
import sqlite3
import tempfile
import hashlib
from pathlib import Path
from fastapi.testclient import TestClient
from main import app

# Os testes não escrevem no histórico real da aplicação
with tempfile.TemporaryDirectory() as pasta:
    banco = Path(pasta) / "teste.sqlite3"
    os.environ["MONITOR_DB_PATH"] = str(banco)

    with TestClient(app) as cliente:
        pedido = {"ticker": "VOW3.DE"}

        resposta = cliente.post("/prever", json=pedido)
        assert resposta.status_code == 200, resposta.text
        primeira = resposta.json()
        assert primeira["previsao_id"]

        resposta = cliente.post("/prever", json=pedido)
        assert resposta.status_code == 200, resposta.text
        segunda = resposta.json()

        assert primeira["previsao_id"] != segunda["previsao_id"]
        print("PASSOU: cada previsão recebe um ID próprio.")

        invalida = cliente.post("/prever", json={"ticker": "INVALIDO"})
        assert invalida.status_code == 422

    # Abre uma nova conexão para confirmar a persistência
    with sqlite3.connect(str(banco)) as conexao:
        conexao.row_factory = sqlite3.Row

        total = conexao.execute(
            "SELECT COUNT(*) FROM previsoes"
        ).fetchone()[0]
        assert total == 2

        registro = conexao.execute(
            "SELECT * FROM previsoes WHERE id = ?",
            (primeira["previsao_id"],)
        ).fetchone()

        assert registro is not None
        assert registro["previsao"] == primeira["fechamento_previsto"]
        assert registro["baseline"] == primeira["baseline_ultimo_fechamento"]
        assert registro["data_prevista"] == primeira["data_prevista"]
        assert registro["versao_modelo"] == primeira["versao_modelo"]
        assert registro["origem"] == "base_salva"
        assert registro["alvo_ja_encerrado"] == int(
            primeira["pregao_alvo_ja_encerrado"]
        )

        entrada = json.loads(registro["entrada_json"])
        assert entrada == {"ticker": "VOW3.DE", "observacoes": []}

        hash_esperado = hashlib.sha256(
            registro["entrada_json"].encode("utf-8")
        ).hexdigest()
        assert registro["hash_entrada"] == hash_esperado

    print("PASSOU: previsão, baseline, datas e versão foram preservadas.")
    print("PASSOU: entrada e identificação do seu conteúdo conferem.")
    print("PASSOU: solicitação inválida não gerou registro de previsão.")
    print("Teste de armazenamento concluído em banco temporário.")
