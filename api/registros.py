
import hashlib
import json
import os
import sqlite3
from contextlib import closing, contextmanager
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

def caminho_banco():
    return Path(os.environ.get(
        "MONITOR_DB_PATH",
        "/tmp/fiap_volkswagen_monitoramento.sqlite3"
    ))

@contextmanager
def conectar(url):
    if url:
        import psycopg

        with psycopg.connect(url, connect_timeout=15) as conexao:
            yield conexao
    else:
        caminho = caminho_banco()
        caminho.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(caminho, timeout=30)) as conexao:
            with conexao:
                yield conexao


def tabela_existe(conexao, url):
    if url:
        return conexao.execute(
            "SELECT to_regclass('previsoes') IS NOT NULL"
        ).fetchone()[0]
    return conexao.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='previsoes'"
    ).fetchone() is not None


def ler_previsoes():
    url = os.environ.get("DATABASE_URL")
    if not url and not caminho_banco().exists():
        return []

    with conectar(url) as conexao:
        if not tabela_existe(conexao, url):
            return []
        cursor = conexao.execute("SELECT * FROM previsoes")
        colunas = [campo[0] for campo in cursor.description]
        return [dict(zip(colunas, linha)) for linha in cursor]


def registrar_previsao(pedido, resultado):
    url = os.environ.get("DATABASE_URL")

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

    with conectar(url) as conexao:
        if not tabela_existe(conexao, url):
            if url:
                # Serializa a primeira criação entre requisições concorrentes.
                conexao.execute("SELECT pg_advisory_xact_lock(51730210)")
            conexao.execute(
                '''
                CREATE TABLE IF NOT EXISTS previsoes (
                    id TEXT PRIMARY KEY,
                    criado_em TEXT NOT NULL,
                    ticker TEXT NOT NULL,
                    dados_ate TEXT NOT NULL,
                    data_prevista TEXT NOT NULL,
                    previsao DOUBLE PRECISION NOT NULL,
                    baseline DOUBLE PRECISION NOT NULL,
                    versao_modelo TEXT NOT NULL,
                    hash_entrada TEXT NOT NULL,
                    entrada_json TEXT NOT NULL,
                    origem TEXT NOT NULL,
                    alvo_ja_encerrado INTEGER NOT NULL
                )
                '''
            )

        marcador = "%s" if url else "?"
        marcadores = ", ".join([marcador] * 12)
        conexao.execute(
            f'''
            INSERT INTO previsoes (
                id, criado_em, ticker, dados_ate, data_prevista,
                previsao, baseline, versao_modelo, hash_entrada,
                entrada_json, origem, alvo_ja_encerrado
            ) VALUES ({marcadores})
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
