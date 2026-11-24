FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=8000 \
    MONITOR_DB_PATH=/app/runtime/previsoes.sqlite3 \
    MONITOR_REPORT_DIR=/app/runtime/relatorios

WORKDIR /app

COPY requirements.txt .
RUN python -m pip install -r requirements.txt && python -m pip check

COPY main.py previsao.py registros.py monitoramento.py ./
COPY avaliar_previsoes.py iniciar.py verificar_modelo.py ./
COPY modelos/ ./modelos/

RUN useradd --create-home --uid 10001 appuser \
    && mkdir -p /app/runtime \
    && chown -R appuser:appuser /app

USER appuser

# A construção falha se o modelo não funcionar neste ambiente.
RUN python verificar_modelo.py

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD python -c "import os, urllib.request; urllib.request.urlopen('http://127.0.0.1:' + os.getenv('PORT', '8000') + '/health', timeout=5)"

CMD ["python", "iniciar.py"]
