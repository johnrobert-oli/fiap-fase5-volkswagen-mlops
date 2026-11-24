
from fastapi.testclient import TestClient
from main import app

with TestClient(app) as cliente:
    saude = cliente.get("/health")
    assert saude.status_code == 200
    assert saude.json()["modelo_carregado"] is True

    modelo = cliente.get("/modelo")
    assert modelo.status_code == 200
    assert modelo.json()["ticker"] == "VOW3.DE"
    assert modelo.json()["ordem"] == [2, 1, 0]

    print("GET /health:", saude.json())
    print("GET /modelo:", modelo.json())
    print("Inicialização e rotas verificadas com sucesso.")
