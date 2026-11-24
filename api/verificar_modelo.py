
from pathlib import Path
import hashlib
import json
import sys
import numpy as np
from statsmodels.tsa.arima.model import ARIMAResults

pasta = Path(__file__).resolve().parent / "modelos"
arquivo = pasta / "arima_210_atualizado.pkl"
metadados = json.loads(
    (pasta / "metadados_modelo.json").read_text(encoding="utf-8")
)

hash_atual = hashlib.sha256(arquivo.read_bytes()).hexdigest()
if hash_atual != metadados["modelo_sha256"]:
    raise RuntimeError("O arquivo do modelo difere da versão registrada.")

modelo = ARIMAResults.load(str(arquivo))
previsao = float(modelo.forecast(steps=1)[0])

np.testing.assert_allclose(
    previsao,
    metadados["previsao_referencia"],
    rtol=0,
    atol=1e-8
)

print(f"Python utilizado: {sys.executable}")
print("Integridade do arquivo: aprovada.")
print(f"Previsão no ambiente isolado: € {previsao:.4f}")
print("Modelo validado no ambiente da API.")
