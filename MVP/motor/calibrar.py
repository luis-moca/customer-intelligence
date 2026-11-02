"""Ajusta la bascula del modelo: que "40%" signifique 40% de verdad.

El modelo ORDENA bien (los backtests lo prueban) pero EXAGERA sus porcentajes
en expansion y contraccion — dice 62% donde pasa 48%. Eso no se arregla con
mas columnas (se probo con order_line: identico), se arregla recalibrando:

  1. Entrenar con el pasado (hasta sep-2025).
  2. En un mes que el modelo NO vio (oct-2025), comparar lo que dijo contra lo
     que paso, y ajustar una correccion de 2 parametros (escalado de Platt).
  3. Evaluar en OTRO mes que ni el modelo ni la correccion vieron (nov-2025).

La correccion jamas se ajusta con el mismo mes donde se evalua — seria
calificarse con las respuestas en la mano.
"""
import json
import math
import os

from features import construir_esquema, construir_x, nombres_de_columnas
from modelo_simple import entrenar, normalizar, predecir, sigmoide, vectorizar

from rutas import MAESTRO

MES_CALIBRACION = "2025-10-31"
MES_PRUEBA = "2025-11-30"
OBJETIVOS = [("etiqueta_expansion_90d", "EXPANSION"),
             ("etiqueta_contraccion_90d", "CONTRACCION"),
             ("etiqueta_churn_120d", "CHURN")]
TRAMOS = [(0.0, 0.05), (0.05, 0.10), (0.10, 0.20), (0.20, 0.35),
          (0.35, 0.50), (0.50, 1.01)]


def logit(p):
    p = min(max(p, 1e-6), 1 - 1e-6)
    return math.log(p / (1 - p))


def ajustar_platt(scores, y, epocas=500, tasa=0.1):
    """Encuentra A y B tal que sigmoide(A*logit(score)+B) diga la verdad."""
    zs = [logit(s) for s in scores]
    A, B = 1.0, 0.0
    n = len(zs)
    for _ in range(epocas):
        gA = gB = 0.0
        for z, yi in zip(zs, y):
            e = sigmoide(A * z + B) - yi
            gA += e * z
            gB += e
        A -= tasa * gA / n
        B -= tasa * gB / n
    return A, B


def aplicar(A, B, s):
    return sigmoide(A * logit(s) + B)


def tabla(nombre, preds, y):
    print("   %-18s %8s %14s %14s" % ("modelo dice", "cuentas", "dicho prom", "paso de verdad"))
    for lo, hi in TRAMOS:
        idx = [i for i, p in enumerate(preds) if lo <= p < hi]
        if not idx:
            continue
        d = sum(preds[i] for i in idx) / len(idx)
        r = sum(y[i] for i in idx) / len(idx)
        print("   %-18s %8d %13.1f%% %13.1f%%"
              % ("%.0f%%-%.0f%%" % (100 * lo, 100 * min(hi, 1)), len(idx), 100 * d, 100 * r))


def main():
    panel = json.load(open(os.path.join(MAESTRO, "panel_cuenta_mes.json")))
    ent = [f for f in panel if not f["para_puntuar"]]
    train = [f for f in ent if f["cierre_mes"] < MES_CALIBRACION]
    cal = [f for f in ent if f["cierre_mes"] == MES_CALIBRACION]
    test = [f for f in ent if f["cierre_mes"] == MES_PRUEBA]
    print("Entrena: %d | calibra: %d (%s) | prueba: %d (%s)\n"
          % (len(train), len(cal), MES_CALIBRACION, len(test), MES_PRUEBA))

    esquema = construir_esquema(train)
    cols = nombres_de_columnas(esquema)
    st = normalizar([construir_x(f, esquema) for f in train], cols)
    vec = lambda fs: [vectorizar(construir_x(f, esquema), cols, st) for f in fs]
    Xtr, Xcal, Xte = vec(train), vec(cal), vec(test)

    resultados = {}
    for objetivo, nombre in OBJETIVOS:
        m = entrenar(Xtr, [f[objetivo] for f in train], cols)
        A, B = ajustar_platt([predecir(m, x) for x in Xcal],
                             [f[objetivo] for f in cal])
        crudas = [predecir(m, x) for x in Xte]
        calibradas = [aplicar(A, B, p) for p in crudas]
        y = [f[objetivo] for f in test]
        print("=" * 70)
        print("%s  (correccion aprendida: A=%.2f B=%.2f)" % (nombre, A, B))
        print("  ANTES:")
        tabla(nombre, crudas, y)
        print("  DESPUES:")
        tabla(nombre, calibradas, y)
        for u in (0.20, 0.35):
            marc = [i for i, p in enumerate(calibradas) if p >= u]
            ok = sum(y[i] for i in marc)
            print("   umbral %2.0f%% calibrado: %3d cuentas, aciertan %d (%.0f%%)"
                  % (100 * u, len(marc), ok, 100 * ok / len(marc) if marc else 0))
        print()
        resultados[nombre] = {"A": A, "B": B}

    ruta = os.path.join(MAESTRO, "calibracion.json")
    with open(ruta, "w") as fh:
        json.dump(resultados, fh, indent=1)
    print("Parametros guardados en: %s" % ruta)


if __name__ == "__main__":
    main()
