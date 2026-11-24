
from contextlib import asynccontextmanager
from pathlib import Path
import hashlib
import json
import numpy as np

from fastapi import FastAPI
from statsmodels.tsa.arima.model import ARIMAResults

PASTA_MODELOS = Path(__file__).resolve().parent / "modelos"

@asynccontextmanager
async def lifespan(app: FastAPI):
    arquivo = PASTA_MODELOS / "arima_210_atualizado.pkl"
    metadados = json.loads(
        (PASTA_MODELOS / "metadados_modelo.json").read_text(
            encoding="utf-8"
        )
    )

    hash_atual = hashlib.sha256(arquivo.read_bytes()).hexdigest()
    if hash_atual != metadados["modelo_sha256"]:
        raise RuntimeError("Integridade do modelo não confirmada.")

    modelo = ARIMAResults.load(str(arquivo))
    previsao = float(modelo.forecast(steps=1)[0])

    np.testing.assert_allclose(
        previsao,
        metadados["previsao_referencia"],
        rtol=0,
        atol=1e-8
    )

    app.state.modelo = modelo
    app.state.metadados = metadados
    yield
    app.state.modelo = None

app = FastAPI(
    title="Volkswagen — API de previsão",
    description="Projeto acadêmico FIAP: previsão experimental com ARIMA.",
    version="0.1.0",
    lifespan=lifespan
)

@app.get("/health")
def health():
    return {
        "status": "ok",
        "modelo_carregado": app.state.modelo is not None,
        "dados_ate": app.state.metadados["observacoes_incorporadas_ate"]
    }

@app.get("/modelo")
def informacoes_modelo():
    meta = app.state.metadados
    return {
        "modelo": meta["modelo"],
        "ordem": meta["ordem"],
        "ticker": meta["ticker"],
        "moeda": meta["moeda"],
        "horizonte": meta["horizonte"],
        "parametros_ajustados_ate": meta["parametros_ajustados_ate"],
        "dados_ate": meta["observacoes_incorporadas_ate"],
        "versao_modelo": meta["modelo_sha256"],
        "status": meta["status"]
    }

from previsao import router as router_previsao
app.include_router(router_previsao)

from monitoramento import configurar_monitoramento
configurar_monitoramento(app)
