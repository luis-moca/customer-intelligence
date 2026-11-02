"""Mide si las probabilidades del modelo son HONESTAS, no solo si ordenan bien.

Por que importa: mientras el output fuera "top 20%", bastaba con que el orden
fuera correcto. Si el output pasa a ser "todas las cuentas que crucen el
umbral" (decision de Luis: no recortar la lista a la capacidad de nadie —
si son 60 cuentas, son 60), entonces el numero que dice el modelo tiene que
significar algo. Decir "45% de riesgo" y que en la realidad churneen el 12%
convierte la lista en ruido.

Calibracion = agrupar las cuentas por lo que el modelo predijo y comparar
contra lo que de verdad paso. Si el modelo dice 40% y churnea el 40%, esta
calibrado. Se mide en los TRES desenlaces, sobre todas las carteras.
"""
import collections
import json
import os

# 'rutas' va PRIMERO: es quien encuentra la carpeta de datos y pone
# motor/ en el camino de busqueda — sin eso, los imports de abajo fallan.
from rutas import MAESTRO
from features import construir_esquema, construir_x, nombres_de_columnas
from modelo_simple import entrenar, normalizar, predecir, vectorizar


CORTE = "2025-11-30"
OBJETIVOS = [("etiqueta_expansion_90d", "EXPANSION"),
             ("etiqueta_contraccion_90d", "CONTRACCION"),
             ("etiqueta_churn_120d", "CHURN")]
TRAMOS = [(0.0, 0.05), (0.05, 0.10), (0.10, 0.20), (0.20, 0.35),
          (0.35, 0.50), (0.50, 1.01)]


def main():
    panel = json.load(open(os.path.join(MAESTRO, "panel_cuenta_mes.json")))
    ent = [f for f in panel if not f["para_puntuar"]]
    train = [f for f in ent if f["cierre_mes"] < CORTE]
    test = [f for f in ent if f["cierre_mes"] == CORTE]

    esquema = construir_esquema(train)
    columnas = nombres_de_columnas(esquema)
    Xtr = [construir_x(f, esquema) for f in train]
    Xte = [construir_x(f, esquema) for f in test]
    st = normalizar(Xtr, columnas)
    Xtr = [vectorizar(x, columnas, st) for x in Xtr]
    Xte = [vectorizar(x, columnas, st) for x in Xte]

    print("Entrenado con %d filas, evaluado en %d (cierre %s)\n"
          % (len(train), len(test), CORTE))

    for objetivo, nombre in OBJETIVOS:
        modelo = entrenar(Xtr, [f[objetivo] for f in train], columnas)
        preds = [predecir(modelo, x) for x in Xte]
        y = [f[objetivo] for f in test]

        print("=" * 72)
        print("%s — ¿el modelo dice la verdad cuando dice un porcentaje?" % nombre)
        print("%-18s %8s %14s %14s" % ("modelo predice", "cuentas", "predicho prom", "paso de verdad"))
        for lo, hi in TRAMOS:
            idx = [i for i, p in enumerate(preds) if lo <= p < hi]
            if not idx:
                continue
            pred_prom = sum(preds[i] for i in idx) / len(idx)
            real = sum(y[i] for i in idx) / len(idx)
            señal = ""
            if len(idx) >= 20:
                if real > pred_prom * 1.5:
                    señal = "  <- SUBESTIMA el riesgo"
                elif pred_prom > real * 1.5:
                    señal = "  <- SOBREESTIMA el riesgo"
            print("%-18s %8d %13.1f%% %13.1f%%%s"
                  % ("%.0f%%-%.0f%%" % (100 * lo, 100 * min(hi, 1.0)),
                     len(idx), 100 * pred_prom, 100 * real, señal))

        print("\n   Si el output fuera 'todas las que pasen el umbral', cuantas cuentas salen:")
        for umbral in (0.20, 0.35, 0.50):
            marcadas = [i for i, p in enumerate(preds) if p >= umbral]
            if not marcadas:
                print("      umbral %.0f%%: 0 cuentas" % (100 * umbral))
                continue
            aciertos = sum(y[i] for i in marcadas)
            porc = collections.Counter(test[i]["gram"] for i in marcadas)
            detalle = ", ".join("%s:%d" % (g, n) for g, n in sorted(porc.items()))
            print("      umbral %2.0f%%: %4d cuentas de %d | aciertan %d (%.0f%%) | %s"
                  % (100 * umbral, len(marcadas), len(test), aciertos,
                     100 * aciertos / len(marcadas), detalle))
        print()


if __name__ == "__main__":
    main()
