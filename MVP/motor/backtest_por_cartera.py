"""
BACKTEST POR CARTERA — entrena con 8 personas, prueba en la novena sin que el
modelo la haya visto nunca. Prueba "¿generaliza entre gente distinta?", NO
"¿predice el futuro?" (para eso esta backtest_temporal.py).

Usa TODAS las filas entrenables (pasado Y presente reciente) de las 8
carteras de entrenamiento — a diferencia del backtest temporal, aqui no hay
ventana de tiempo que respetar, la separacion es por PERSONA, no por fecha.

Se miden los TRES desenlaces siempre: expansion, contraccion y churn. Regla
dura del proyecto — nunca uno solo.

El esquema de columnas se construye SOLO con las 8 carteras de entrenamiento.
Construirlo con las nueve dejaria que las categorias propias de la cartera de
prueba (su industria dominante, su plantilla de venta) entren al modelo antes
de que la vea: seria hacer trampa por la puerta de atras.
"""
import json
import os

from evaluar import UMBRAL_CASOS_CONFIABLES, precision_recall_en_top, reporte
from features import construir_esquema, construir_x, nombres_de_columnas
from modelo_simple import entrenar, normalizar, predecir, vectorizar

from rutas import MAESTRO

OBJETIVOS = [
    ("etiqueta_expansion_90d", "EXPANSION"),
    ("etiqueta_contraccion_90d", "CONTRACCION"),
    ("etiqueta_churn_120d", "CHURN"),
]


def main():
    panel = json.load(open(os.path.join(MAESTRO, "panel_cuenta_mes.json")))
    entrenables = [f for f in panel if not f["para_puntuar"]]
    grams = sorted({f["gram"] for f in entrenables})

    resumen = []

    for gram_prueba in grams:
        train = [f for f in entrenables if f["gram"] != gram_prueba]
        test = [f for f in entrenables if f["gram"] == gram_prueba]
        if len(test) < 30:
            print("(%s: muy pocas filas de prueba, %d — se omite)\n"
                  % (gram_prueba, len(test)))
            continue

        esquema = construir_esquema(train)
        columnas = nombres_de_columnas(esquema)

        X_train_dict = [construir_x(f, esquema) for f in train]
        X_test_dict = [construir_x(f, esquema) for f in test]
        stats = normalizar(X_train_dict, columnas)
        X_train = [vectorizar(x, columnas, stats) for x in X_train_dict]
        X_test = [vectorizar(x, columnas, stats) for x in X_test_dict]

        print("=" * 68)
        print("CARTERA DE PRUEBA: %s  (entrenado con las otras %d, %d filas, %d columnas)"
              % (gram_prueba, len(grams) - 1, len(train), len(columnas)))

        fila = {"gram": gram_prueba, "n": len(test)}
        for objetivo, etiqueta in OBJETIVOS:
            y_train = [f[objetivo] for f in train]
            y_test = [f[objetivo] for f in test]
            modelo = entrenar(X_train, y_train, columnas, epocas=150)
            preds = [predecir(modelo, x) for x in X_test]
            reporte("%s en %s" % (etiqueta, gram_prueba), preds, y_test)

            r20 = precision_recall_en_top(preds, y_test, 0.20)
            total_pos = sum(y_test)
            base = total_pos / len(y_test) if y_test else 0
            fila[etiqueta] = (r20["precision"] / base) if base else 0
            fila[etiqueta + "_n"] = total_pos
        resumen.append(fila)

    print("=" * 68)
    print("=== RESUMEN — lift en el top 20%, por cartera (1.0x = igual que azar) ===")
    print("Un * junto al numero significa menos de %d casos reales en esa cartera:"
          " el lift es real pero fragil, se mueve mucho con 1-2 casos de diferencia."
          % UMBRAL_CASOS_CONFIABLES)
    print("%-9s %7s %12s %13s %10s" % ("cartera", "filas", "EXPANSION", "CONTRACCION", "CHURN"))

    def marca(r, etiqueta):
        return "*" if r[etiqueta + "_n"] < UMBRAL_CASOS_CONFIABLES else " "

    for r in resumen:
        print("%-9s %7d %10.1fx%s %11.1fx%s %8.1fx%s"
              % (r["gram"], r["n"],
                 r["EXPANSION"], marca(r, "EXPANSION"),
                 r["CONTRACCION"], marca(r, "CONTRACCION"),
                 r["CHURN"], marca(r, "CHURN")))
    if resumen:
        print("%-9s %7s %11.1fx %12.1fx %9.1fx"
              % ("PROMEDIO", "",
                 sum(r["EXPANSION"] for r in resumen) / len(resumen),
                 sum(r["CONTRACCION"] for r in resumen) / len(resumen),
                 sum(r["CHURN"] for r in resumen) / len(resumen)))


if __name__ == "__main__":
    main()
