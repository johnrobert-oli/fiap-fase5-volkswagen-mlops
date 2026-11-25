# Previsão do fechamento da Volkswagen com ARIMA e FastAPI

John Robert Marreiro de Oliveira · FIAP · Pós Tech em Machine Learning Engineering · Fase 5

O projeto estima, em euros, o preço de fechamento da ação preferencial da Volkswagen (`VOW3.DE`) no pregão seguinte da Xetra. Para a mesma data, a API devolve a previsão do ARIMA(2,1,0) e uma referência simples que repete o último fechamento observado.

**O ARIMA obteve o menor erro absoluto médio na validação de 2024. No teste de 2025–2026, o último fechamento teve o menor erro nas três métricas.** Por isso, a API disponibiliza o ARIMA como experimental e registra as duas previsões para avaliação.

## Executar a API com Docker

No Windows, com o Git e o Docker Desktop instalados, abra o Docker Desktop e aguarde **Engine running**. Abra o PowerShell na pasta onde deseja baixar o projeto e execute os comandos abaixo.

```powershell
git clone https://github.com/johnrobert-oli/fiap-fase5-volkswagen-mlops.git
cd fiap-fase5-volkswagen-mlops/api
docker compose up --build -d
```

Se o projeto já estiver no computador, abra o terminal na pasta `api`, onde está o arquivo `compose.yaml`, e execute apenas o último comando. Depois, abra a [documentação interativa da API](http://127.0.0.1:8000/docs).

| Rota | Função |
|---|---|
| `GET /health` | Informa se o modelo foi carregado e até que data ele contém observações. |
| `GET /modelo` | Exibe o ativo, a moeda, a ordem do ARIMA, o horizonte, a versão e as datas de ajuste e atualização. |
| `POST /prever` | Gera e registra a previsão do ARIMA e a referência para o mesmo pregão. |
| `GET /metrics` | Expõe contagens de requisições por método, rota e status HTTP, além da duração das chamadas. [Abrir métricas locais](http://127.0.0.1:8000/metrics) |

### Fazer a primeira previsão

Em `/docs`, abra **POST /prever**, clique em **Try it out**, cole o JSON abaixo no campo da requisição e clique em **Execute**.

```json
{"ticker": "VOW3.DE"}
```

O modelo incluído no repositório contém observações até **16/11/2026**. Para **17/11/2026**, ele devolve **€ 67,0109** como previsão do ARIMA e **€ 67,0400** como referência. Esse pedido permite reproduzir a previsão da versão salva.

Para avançar a data-alvo, envie também a lista `observacoes`. Comece pelo primeiro pregão após a base e inclua um fechamento positivo por pregão, em ordem e sem lacunas. A API aceita até 366 pregões já encerrados por chamada. O exemplo abaixo incorpora o fechamento de 17/11 e calcula a previsão para 18/11.

```json
{
  "ticker": "VOW3.DE",
  "observacoes": [
    {"data": "2026-11-17", "fechamento": 66.300003}
  ]
}
```

As observações atualizam o estado do modelo apenas naquela requisição. Os parâmetros do ARIMA permanecem fixos. Cada previsão recebe um `previsao_id` que permite identificá-la no histórico.

## Dados e avaliação

A coleta usou o Yahoo Finance via `yfinance`, com `auto_adjust=False`. O alvo é o fechamento diário da coluna `Close`. Dos **3.019 registros originais**, cinco estavam fora do calendário de pregões da Xetra (`XETR`). A base de trabalho ficou com **3.014 datas e 3.013 fechamentos disponíveis**.

| Etapa | Período | Datas | Fechamentos disponíveis |
|---|---|---:|---:|
| Treino | 02/01/2015 a 29/12/2023 | 2.283 | 2.283 |
| Validação | 02/01/2024 a 30/12/2024 | 254 | 254 |
| Teste | 02/01/2025 a 16/11/2026 | 477 | 476 |

Em **25/06/2026**, a fonte informou volume zero e repetiu o fechamento anterior na abertura, na máxima, na mínima e no fechamento. A data foi preservada com o preço ausente. Em 25/06 faltou o fechamento real para medir o erro. Em 26/06 faltou o preço anterior para calcular a referência. Assim, a comparação usou os mesmos **475 pregões de teste** para os dois métodos.

Quatro ordens de ARIMA foram avaliadas em 2024. Após a escolha pelo menor MAE, o ARIMA(2,1,0) foi ajustado novamente com os dados de treino e validação até **30/12/2024**. Durante o teste, o modelo gerou a previsão de cada pregão antes de incorporar a observação daquele dia. Dessa forma, o estado do modelo avançou até **16/11/2026**, mantendo os parâmetros fixos.

| Etapa | Método | MAE (€) | RMSE (€) | MAPE (%) |
|---|---|---:|---:|---:|
| Validação | Último fechamento | 1,1357 | 1,5722 | 1,0864 |
| Validação | ARIMA(2,1,0) | **1,1323** | **1,5702** | **1,0845** |
| Teste | Último fechamento | **1,2695** | **1,6941** | **1,4127** |
| Teste | ARIMA(2,1,0) | 1,2723 | 1,7006 | 1,4147 |

O MAE mede a diferença absoluta média, em euros, entre previsão e fechamento. O RMSE também é expresso em euros e dá mais peso aos erros grandes. O MAPE expressa o erro absoluto percentual médio. Na validação, o ARIMA reduziu o MAE em cerca de **€ 0,0034 por previsão**. No teste, a referência errou em média **€ 0,0028 a menos** que o ARIMA.

[Comparação das quatro ordens na validação](dados/comparacao_arima_validacao.csv) · [Previsões por pregão no teste](dados/previsoes_teste.csv) · [Métricas do teste](dados/metricas_teste.csv)

## Rastreabilidade e monitoramento

O experimento `FIAP_Fase5_Volkswagen` registra no MLflow as cinco execuções de validação e as duas de teste. O pacote do modelo tem uma execução própria. Na construção da imagem Docker e na inicialização da API, o sistema verifica o SHA-256 do arquivo do modelo e confere se a previsão carregada reproduz o valor de referência. [Execuções de avaliação](mlflow/registros_experimentos.csv) · [Referências do modelo](mlflow/referencias_modelo.json)

### Operação da API

A rota `/metrics` expõe contadores e tempos de resposta em formato Prometheus. Para cada previsão emitida, a API guarda o horário de criação, os dados de entrada, a versão do modelo, a previsão e a referência. Com a variável de ambiente `DATABASE_URL` configurada, a API e o avaliador usam o mesmo PostgreSQL. Configure essa variável com a URL de conexão do Neon no Render. Sem essa variável, o Docker Compose usa SQLite e o volume local `historico_previsoes`. Os arquivos de relatório são gravados em `MONITOR_REPORT_DIR`. No Render Free, exporte os arquivos que deseja conservar. O histórico de previsões fica no PostgreSQL.

### Avaliar as previsões após o fechamento

Com o contêiner em execução, rode o avaliador a partir da pasta `api`.

```powershell
docker compose exec api python avaliar_previsoes.py
```

O avaliador considera as previsões emitidas antes do fechamento do pregão-alvo, depois que esse pregão termina. Quando há várias previsões para a mesma ação, data, versão e origem dos dados, ele usa a primeira. Em seguida, consulta os preços observados, valida os preços e o volume e calcula MAE, RMSE e MAPE para os dois métodos. As métricas são agrupadas por versão do modelo e origem das entradas.

O comando exibe o resultado no terminal e grava `/app/runtime/relatorios/qualidade_previsoes.json`. Quando ainda não existem pares válidos de previsão e fechamento, o relatório informa `sem dados suficientes`. Se a fonte retornar uma coleta vazia, o status será `coleta indisponivel`.

Com seis fechamentos informados até **24/11/2026**, a API estimou **€ 62,1483** para **25/11/2026**, com referência de **€ 62,3600**. O campo `pregao_alvo_ja_encerrado` era `false` na emissão. O JSON preserva a previsão feita antes do fechamento. A medição do erro depende da coleta posterior do fechamento real validado. [Resposta original da API](evidencias/previsao_VOW3_2026-11-25.json)

## Organização do repositório

| Pasta | Conteúdo |
|---|---|
| [`notebooks/`](notebooks/) | [Notebook do projeto](notebooks/FIAP_Fase5_Volkswagen_MLOps.ipynb), da coleta à avaliação e preparação da API. |
| [`dados/`](dados/) | Séries bruta e tratada, divisão temporal, previsões e métricas. |
| [`figuras/`](figuras/) | [Gráfico do histórico de fechamento](figuras/historico_fechamento.png). |
| [`mlflow/`](mlflow/) | Banco do experimento, registros das execuções e artefatos dos modelos. |
| [`api/`](api/) | Serviço FastAPI, modelo serializado, dependências, testes, avaliador e arquivos Docker. |
| [`evidencias/`](evidencias/) | Resposta da API salva para documentar a previsão emitida. |
