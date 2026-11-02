"""Compara 3 formas de tratar valores extremos, con numeros, no con opinion.

Motivo: una cuenta de mnav con 12 contracciones (mediana del universo: 0,
p99: 4) domina sola la prediccion de expansion (aporte +1.7 de logit) y infla
el techo de su cartera; carteras sin outliers (luram) quedan castigadas.

Las 3 variantes se aplican PAREJO a todas las columnas numericas — nunca a
columnas elegidas a mano — y se juzgan en el backtest temporal (entrena con
las 9 carteras, corte 2025-11-30) sobre los TRES desenlaces.
"""
import json
import math
import os

# 'rutas' va PRIMERO: es quien encuentra la carpeta de datos y pone
# motor/ en el camino de busqueda — sin eso, los imports de abajo fallan.
from rutas import MAESTRO
from evaluar import precision_recall_en_top
from features import construir_esquema, construir_x, nombres_de_columnas
from modelo_simple import entrenar, normalizar, predecir, vectorizar


CORTE = "2025-11-30"
OBJETIVOS = [("etiqueta_expansion_90d", "EXPANSION"),
             ("etiqueta_contraccion_90d", "CONTRACCION"),
             ("etiqueta_churn_120d", "CHURN")]


def sin_cambio(v):
    return v


def log_con_signo(v):
    return math.copysign(math.log1p(abs(v)), v)


def percentiles(train_x, columnas):
    """p1 y p99 por columna, calculados SOLO con entrenamiento."""
    limites = {}
    for c in columnas:
        vals = sorted(x[c] for x in train_x if x.get(c) is not None)
        if vals:
            limites[c] = (vals[max(0, int(len(vals) * 0.01))],
                          vals[min(len(vals) - 1, int(len(vals) * 0.99))])
    return limites


def aplicar_transform(xs, columnas, modo, limites):
    out = []
    for x in xs:
        y = dict(x)
        for c in columnas:
            v = y.get(c)
            if v is None or isinstance(v, str):
                continue
            if modo == "clip":
                lo, hi = limites.get(c, (v, v))
                y[c] = min(max(v, lo), hi)
            elif modo == "slog":
                y[c] = log_con_signo(v)
        out.append(y)
    return out


def main():
    panel = json.load(open(os.path.join(MAESTRO, "panel_cuenta_mes.json")))
    ent = [f for f in panel if not f["para_puntuar"]]
    train = [f for f in ent if f["cierre_mes"] < CORTE]
    test = [f for f in ent if f["cierre_mes"] == CORTE]
    esquema = construir_esquema(train)
    cols = nombres_de_columnas(esquema)
    numericas = [e["col"] for e in esquema if e["tipo"] == "numerica"]

    Xtr_d = [construir_x(f, esquema) for f in train]
    Xte_d = [construir_x(f, esquema) for f in test]
    limites = percentiles(Xtr_d, numericas)

    print("Entrena %d | prueba %d | columnas numericas transformadas: %d\n"
          % (len(train), len(test), len(numericas)))
    print("%-12s %-11s %14s %10s" % ("desenlace", "variante", "lift top10%", "captura"))

    for objetivo, nombre in OBJETIVOS:
        y_tr = [f[objetivo] for f in train]
        y_te = [f[objetivo] for f in test]
        base = sum(y_te) / len(y_te)
        for modo, etiqueta in (("actual", "z-score"), ("clip", "clip p99"),
                               ("slog", "log signo")):
            A = aplicar_transform(Xtr_d, numericas, modo, limites)
            B = aplicar_transform(Xte_d, numericas, modo, limites)
            st = normalizar(A, cols)
            Xtr = [vectorizar(x, cols, st) for x in A]
            Xte = [vectorizar(x, cols, st) for x in B]
            m = entrenar(Xtr, y_tr, cols)
            preds = [predecir(m, x) for x in Xte]
            r = precision_recall_en_top(preds, y_te, 0.10)
            print("%-12s %-11s %13.1fx %9.0f%%"
                  % (nombre, etiqueta, r["precision"] / base, 100 * r["recall"]))
        print()


if __name__ == "__main__":
    main()
