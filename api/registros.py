
import hashlib
import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

def caminho_banco():
    # Na implantação, configuraremos um diretório persistente.
    return Path(os.environ.get(
        "MONITOR_DB_PATH",
        "/tmp/fiap_volkswagen_monitoramento.sqlite3"
    ))

def registrar_previsao(pedido, resultado):
    caminho = caminho_banco()
    caminho.parent.mkdir(parents=True, exist_ok=True)

    entrada = pedido.model_dump(mode="json")
    entrada_json = json.dumps(
        entrada, sort_keys=True, separators=(",", ":")
    )

    identificador = str(uuid4())
    criado_em = datetime.now(timezone.utc).isoformat()
    hash_entrada = hashlib.sha256(
        entrada_json.encode("utf-8")
    ).hexdigest()

    origem = (
        "base_salva"
        if not entrada["observacoes"]
        else "dados_informados_pelo_usuario"
    )

    with sqlite3.connect(str(caminho), timeout=30) as conexao:
        conexao.execute(
            '''
            CREATE TABLE IF NOT EXISTS previsoes (
                id TEXT PRIMARY KEY,
                criado_em TEXT NOT NULL,
                ticker TEXT NOT NULL,
                dados_ate TEXT NOT NULL,
                data_prevista TEXT NOT NULL,
                previsao REAL NOT NULL,
                baseline REAL NOT NULL,
                versao_modelo TEXT NOT NULL,
                hash_entrada TEXT NOT NULL,
                entrada_json TEXT NOT NULL,
                origem TEXT NOT NULL,
                alvo_ja_encerrado INTEGER NOT NULL
            )
            '''
        )

        conexao.execute(
            '''
            INSERT INTO previsoes (
                id, criado_em, ticker, dados_ate, data_prevista,
                previsao, baseline, versao_modelo, hash_entrada,
                entrada_json, origem, alvo_ja_encerrado
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''',
            (
                identificador,
                criado_em,
                resultado["ticker"],
                resultado["dados_ate"],
                resultado["data_prevista"],
                resultado["fechamento_previsto"],
                resultado["baseline_ultimo_fechamento"],
                resultado["versao_modelo"],
                hash_entrada,
                entrada_json,
                origem,
                int(resultado["pregao_alvo_ja_encerrado"])
            )
        )

    return identificador
