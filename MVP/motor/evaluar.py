"""
Metricas explicables a un CS, no jerga de data scientist.

En vez de AUC/ROC: "de las 20% cuentas que el modelo marco como mas riesgosas,
cuantas de verdad churnearon/expandieron" — comparado contra que tan seguido
pasa eso si se eligieran cuentas al azar (la tasa base). Eso es directamente
tu criterio de exito: si el modelo no le gana claro a elegir al azar, no sirve.

Un lift de "4.6x" con 13 casos reales y un lift de "3.7x" con 170 casos NO son
igual de confiables, aunque se vean igual de solidos en una tabla. Con pocos
casos, un par de aciertos de mas o de menos mueve el numero muchisimo (ver
lusan: 0.91% de tasa de churn en 3 años de historia — no es una racha de mala
suerte del corte de prueba, es la cartera entera). Por eso todo reporte trae
el intervalo de confianza junto al numero, y se marca cuando hay muy pocos
casos para confiar en el — nunca se esconde la incertidumbre.
"""

UMBRAL_CASOS_CONFIABLES = 30  # menos de esto: el numero se muestra, pero marcado


def intervalo_wilson(aciertos, n, z=1.96):
    """Intervalo de confianza (95%) para una proporcion aciertos/n.

    Por que Wilson y no +-1.96*sqrt(p(1-p)/n) (la formula de libro): esa
    formula se rompe justo donde mas se necesita, con pocos casos o tasas
    cercanas a 0% — puede dar limites negativos o mayores a 100%. Wilson no.
    """
    if n == 0:
        return (0.0, 0.0)
    p = aciertos / n
    denom = 1 + z * z / n
    centro = (p + z * z / (2 * n)) / denom
    margen = z * ((p * (1 - p) / n + z * z / (4 * n * n)) ** 0.5) / denom
    return (max(0.0, centro - margen), min(1.0, centro + margen))


def precision_recall_en_top(predicciones, etiquetas, porcentaje):
    """predicciones: lista de scores (mas alto = mas riesgo/probabilidad).
    etiquetas: 0/1 en el mismo orden. porcentaje: 0.1 = top 10%."""
    pares = sorted(zip(predicciones, etiquetas), key=lambda p: -p[0])
    n_top = max(1, int(len(pares) * porcentaje))
    top = pares[:n_top]

    aciertos_top = sum(e for _, e in top)
    total_positivos = sum(etiquetas)

    precision = aciertos_top / n_top
    recall = aciertos_top / total_positivos if total_positivos else 0.0
    return {
        "n_top": n_top,
        "aciertos_en_top": aciertos_top,
        "precision": precision,
        "recall": recall,
    }


def reporte(nombre, predicciones, etiquetas):
    total_positivos = sum(etiquetas)
    tasa_base = total_positivos / len(etiquetas) if etiquetas else 0.0
    aviso = ("   *** SOLO %d CASOS REALES EN TOTAL — bajo el umbral de %d. "
              "El lift de abajo puede moverse mucho con solo 1 o 2 casos de "
              "diferencia; no tratarlo con la misma confianza que una cartera "
              "con mas historia. ***" % (total_positivos, UMBRAL_CASOS_CONFIABLES)
              ) if total_positivos < UMBRAL_CASOS_CONFIABLES else ""
    print("--- %s (n=%d, tasa base=%.2f%%, %d casos reales) ---"
          % (nombre, len(etiquetas), 100 * tasa_base, total_positivos))
    if aviso:
        print(aviso)
    for pct in (0.10, 0.20, 0.30):
        r = precision_recall_en_top(predicciones, etiquetas, pct)
        lift = (r["precision"] / tasa_base) if tasa_base else 0.0
        lo, hi = intervalo_wilson(r["aciertos_en_top"], r["n_top"])
        lift_lo = (lo / tasa_base) if tasa_base else 0.0
        lift_hi = (hi / tasa_base) if tasa_base else 0.0
        print("   top %3.0f%% (%4d cuentas): acierta %3d  ->  precision=%5.1f%%  "
              "(%.1fx la tasa base, 95%% seguro entre %.1fx-%.1fx)   "
              "captura %4.0f%% de los casos reales"
              % (pct * 100, r["n_top"], r["aciertos_en_top"],
                 100 * r["precision"], lift, lift_lo, lift_hi, 100 * r["recall"]))
    print()
