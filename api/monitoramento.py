
from time import perf_counter
from fastapi import Response
from prometheus_client import (
    CollectorRegistry, Counter, Histogram,
    generate_latest, CONTENT_TYPE_LATEST
)

def configurar_monitoramento(app):
    registro = CollectorRegistry()

    requisicoes = Counter(
        "api_requisicoes_total",
        "Quantidade de requisicoes por rota e resposta",
        ["metodo", "rota", "status"],
        registry=registro
    )

    duracao = Histogram(
        "api_duracao_segundos",
        "Tempo de processamento das requisicoes",
        ["metodo", "rota"],
        registry=registro
    )

    @app.middleware("http")
    async def medir_requisicao(request, call_next):
        # A coleta de métricas não entra na própria contagem
        if request.url.path == "/metrics":
            return await call_next(request)

        inicio = perf_counter()
        status = 500

        try:
            resposta = await call_next(request)
            status = resposta.status_code
            return resposta
        finally:
            rota_objeto = request.scope.get("route")
            rota = getattr(
                rota_objeto, "path", "rota_nao_encontrada"
            )

            metodo = request.method
            if metodo not in {
                "GET", "POST", "PUT", "PATCH", "DELETE",
                "HEAD", "OPTIONS"
            }:
                metodo = "OUTRO"

            requisicoes.labels(
                metodo, rota, str(status)
            ).inc()

            duracao.labels(
                metodo, rota
            ).observe(perf_counter() - inicio)

    @app.get("/metrics", include_in_schema=False)
    def metricas():
        return Response(
            content=generate_latest(registro),
            headers={"Content-Type": CONTENT_TYPE_LATEST}
        )
