from registros import registrar_previsao

from copy import deepcopy
from datetime import date, timedelta
from typing import Literal
import numpy as np
import pandas as pd
import exchange_calendars as xcals

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

def agora_utc():
    return pd.Timestamp.now(tz="UTC")

router = APIRouter()

class Observacao(BaseModel):
    model_config = ConfigDict(extra="forbid")
    data: date
    fechamento: float = Field(
        gt=0, allow_inf_nan=False, strict=True
    )

class PedidoPrevisao(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ticker: Literal["VOW3.DE"]
    observacoes: list[Observacao] = Field(
        default_factory=list, max_length=366
    )

@router.post("/prever")
def prever(pedido: PedidoPrevisao, request: Request):
    meta = request.app.state.metadados
    data_base = date.fromisoformat(
        meta["observacoes_incorporadas_ate"]
    )
    agora = agora_utc()
    hoje = agora.tz_convert("Europe/Berlin").date()

    datas = [item.data for item in pedido.observacoes]

    if any(d <= data_base or d > hoje for d in datas):
        raise HTTPException(
            status_code=422,
            detail="Envie somente datas posteriores à base e até hoje."
        )

    calendario = xcals.get_calendar(
        "XETR",
        start=str(data_base),
        end=str(max(hoje, data_base) + timedelta(days=370))
    )

    if datas:
        esperadas = [
            d.date()
            for d in calendario.sessions_in_range(
                str(data_base + timedelta(days=1)),
                str(datas[-1])
            )
        ]

        if datas != esperadas:
            raise HTTPException(
                status_code=422,
                detail=(
                    "Envie todos os pregões posteriores à base, "
                    "em ordem, sem lacunas ou datas repetidas."
                )
            )

        if calendario.session_close(str(datas[-1])) > agora:
            raise HTTPException(
                status_code=422,
                detail="O último pregão informado ainda não encerrou."
            )

    # Cada chamada utiliza um estado independente
    modelo = deepcopy(request.app.state.modelo)

    if pedido.observacoes:
        valores = [item.fechamento for item in pedido.observacoes]
        modelo = modelo.append(valores, refit=False)

    data_referencia = datas[-1] if datas else data_base
    data_alvo = calendario.next_session(
        str(data_referencia)
    ).date()

    previsao = float(modelo.forecast(steps=1)[0])
    baseline = float(np.asarray(modelo.model.endog).reshape(-1)[-1])

    if not np.isfinite(previsao) or previsao <= 0:
        raise HTTPException(
            status_code=503,
            detail="O modelo não produziu uma previsão de preço válida."
        )

    resultado = {
        "ticker": pedido.ticker,
        "moeda": meta["moeda"],
        "dados_ate": str(data_referencia),
        "data_prevista": str(data_alvo),
        "fechamento_previsto": previsao,
        "baseline_ultimo_fechamento": baseline,
        "novas_observacoes": len(pedido.observacoes),
        "versao_modelo": meta["modelo_sha256"],
        "pregao_alvo_ja_encerrado": bool(
            calendario.session_close(str(data_alvo)) <= agora
        ),
        "status_modelo": meta["status"]
    }

    resultado["previsao_id"] = registrar_previsao(pedido, resultado)
    return resultado
