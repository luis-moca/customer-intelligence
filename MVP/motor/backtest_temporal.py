"""
BACKTEST TEMPORAL — le tapamos los ojos al modelo sobre un futuro que ya paso.

Corte: cierre de noviembre 2025. Se entrena SOLO con filas anteriores. Se
evalua contra las filas de ese mes, cuya etiqueta mira 90 dias hacia adelante
— dias que YA ocurrieron de verdad en el calendario.

Los TRES desenlaces por separado (propensiones independientes que pueden
coexistir): expansion, contraccion y churn. Nunca uno solo.
"""
import json
import os

from evaluar import reporte
from features import construir_esquema, construir_x, nombres_de_columnas
from modelo_simple import entrenar, normalizar, predecir, pesos_ordenados, vectorizar

from rutas import MAESTRO

CORTE = "2025-11-30"

OBJETIVOS = [
    ("etiqueta_expansion_90d", "EXPANSION"),
    ("etiqueta_contraccion_90d", "CONTRACCION"),
    ("etiqueta_churn_120d", "CHURN"),
]


def main():
    panel = json.load(open(os.path.join(MAESTRO, "panel_cuenta_mes.json")))
    entrenables = [f for f in panel if not f["para_puntuar"]]

    train = [f for f in entrenables if f["cierre_mes"] < CORTE]
    test = [f for f in entrenables if f["cierre_mes"] == CORTE]

    esquema = construir_esquema(entrenables)
    columnas = nombres_de_columnas(esquema)

    print("=== Backtest temporal — corte %s ===" % CORTE)
    print("Entrenamiento: %d filas | Prueba: %d filas" % (len(train), len(test)))
    print("Columnas generadas automaticamente desde el panel: %d\n" % len(columnas))

    X_train_dict = [construir_x(f, esquema) for f in train]
    X_test_dict = [construir_x(f, esquema) for f in test]
    stats = normalizar(X_train_dict, columnas)
    X_train = [vectorizar(x, columnas, stats) for x in X_train_dict]
    X_test = [vectorizar(x, columnas, stats) for x in X_test_dict]

    for objetivo, etiqueta in OBJETIVOS:
        y_train = [f[objetivo] for f in train]
        y_test = [f[objetivo] for f in test]
        modelo = entrenar(X_train, y_train, columnas)
        preds = [predecir(modelo, x) for x in X_test]

        reporte("%s — 90 dias despues de %s" % (etiqueta, CORTE), preds, y_test)

        pesos = pesos_ordenados(modelo)
        vivas = [(c, w) for c, w in pesos if abs(w) > 1e-9]
        print("   L1 dejo %d de %d variables vivas (apago %d):"
              % (len(vivas), len(columnas), len(columnas) - len(vivas)))
        for col, w in vivas[:8]:
            print("      %-42s peso=%+.3f" % (col, w))
        print()


if __name__ == "__main__":
    main()
