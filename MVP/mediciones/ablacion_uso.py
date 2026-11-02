"""Mide cuanto aportan REALMENTE las columnas de uso (los pings).

Corre el mismo backtest dos veces — con y sin las columnas uso_* — y compara.
Sin esto, "el modelo mejoro" no significa nada: pudo haber mejorado por
payment_term_id, por ruido, o por nada.
"""
import json
import os

# 'rutas' va PRIMERO: es quien encuentra la carpeta de datos y pone
# motor/ en el camino de busqueda — sin eso, los imports de abajo fallan.
from rutas import MAESTRO
from evaluar import reporte
from features import construir_esquema, construir_x, nombres_de_columnas
from modelo_simple import entrenar, normalizar, predecir, pesos_ordenados, vectorizar

CORTE = "2025-11-30"
OBJETIVOS = [("etiqueta_expansion_90d", "EXPANSION"),
             ("etiqueta_contraccion_90d", "CONTRACCION"),
             ("etiqueta_churn_120d", "CHURN")]


def corre(train, test, objetivo, esquema, columnas):
    Xtr = [construir_x(f, esquema) for f in train]
    Xte = [construir_x(f, esquema) for f in test]
    st = normalizar(Xtr, columnas)
    Xtr = [vectorizar(x, columnas, st) for x in Xtr]
    Xte = [vectorizar(x, columnas, st) for x in Xte]
    m = entrenar(Xtr, [f[objetivo] for f in train], columnas)
    preds = [predecir(m, x) for x in Xte]
    y = [f[objetivo] for f in test]
    orden = sorted(range(len(preds)), key=lambda i: -preds[i])
    k = max(1, len(orden) // 10)
    base = sum(y) / len(y) if y else 0
    acierta = sum(y[i] for i in orden[:k])
    prec = acierta / k
    return (prec / base if base else 0), (acierta / sum(y) if sum(y) else 0), m


def main():
    panel = json.load(open(os.path.join(MAESTRO, "panel_cuenta_mes.json")))
    ent = [f for f in panel if not f["para_puntuar"]]
    train = [f for f in ent if f["cierre_mes"] < CORTE]
    test = [f for f in ent if f["cierre_mes"] == CORTE]

    esquema_full = construir_esquema(ent)
    esquema_sin = [e for e in esquema_full if e["col"] not in ("pings_al_tope", "mensual_y_al_tope")]

    print("Entrenamiento %d filas | prueba %d filas | corte %s\n" % (len(train), len(test), CORTE))
    print("%-13s %26s %26s" % ("", "SIN cuenta-llena", "CON cuenta-llena"))
    print("%-13s %12s %13s %12s %13s" % ("desenlace", "top10% x base", "captura", "top10% x base", "captura"))
    for objetivo, nombre in OBJETIVOS:
        cs = corre(train, test, objetivo, esquema_sin, nombres_de_columnas(esquema_sin))
        cc = corre(train, test, objetivo, esquema_full, nombres_de_columnas(esquema_full))
        print("%-13s %11.1fx %12.0f%% %11.1fx %12.0f%%"
              % (nombre, cs[0], 100 * cs[1], cc[0], 100 * cc[1]))
        vivas = [(c, w) for c, w in pesos_ordenados(cc[2])
                 if c.split("=")[0] in ("pings_al_tope", "mensual_y_al_tope") and abs(w) > 1e-9]
        print("      columnas de cuenta-llena vivas: %s"
              % (", ".join("%s(%+.3f)" % (c, w) for c, w in vivas) or "NINGUNA — no aportaron"))


if __name__ == "__main__":
    main()
