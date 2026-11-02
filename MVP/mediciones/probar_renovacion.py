"""
¿La cercania a la renovacion (aniversario del contrato) predice churn o
expansion de verdad, o es puro ruido de calendario? Se mide, no se asume.

Construccion SIN riesgo de fuga: 'dias_hasta_aniversario' sale unicamente de
first_contract_date (estatica, ya validada) + el calendario — nunca del log,
nunca de next_invoice_date (que es un campo vivo/actual, no una foto
historica de lo que se sabia en el mes M).

Se separa por plan_billing_period_unit porque la afirmacion de Luis fue
especifica: "anual pesa mas, mensual pesa menos por cercania".
"""
import collections
import datetime
import json
import os
import statistics

from rutas import MAESTRO


def idv(v):
    return v[0] if isinstance(v, list) else v


def a_fecha(t):
    try:
        return datetime.date.fromisoformat(str(t)[:10])
    except (ValueError, TypeError):
        return None


def dias_hasta_aniversario(inicio, cierre):
    """Dias desde 'cierre' hasta el proximo aniversario (mismo mes/dia) de
    'inicio', cayendo en o despues de 'cierre'."""
    if inicio is None:
        return None
    try:
        prox = inicio.replace(year=cierre.year)
    except ValueError:  # 29-feb en año no bisiesto
        prox = inicio.replace(year=cierre.year, day=28)
    if prox < cierre:
        try:
            prox = prox.replace(year=cierre.year + 1)
        except ValueError:
            prox = prox.replace(year=cierre.year + 1, day=28)
    return (prox - cierre).days


def bucket(dias):
    if dias <= 30:
        return "0-30 dias"
    if dias <= 90:
        return "31-90 dias"
    if dias <= 180:
        return "91-180 dias"
    return "181+ dias"


def main():
    foto = json.load(open(os.path.join(MAESTRO, "foto_maestra.json")))
    panel = json.load(open(os.path.join(MAESTRO, "panel_cuenta_mes.json")))
    inicio_de = {f["id"]: a_fecha(f.get("first_contract_date")) for f in foto}

    filas = [f for f in panel if not f["para_puntuar"]]
    tasa_base_ch = sum(f["etiqueta_churn_120d"] for f in filas) / len(filas)
    tasa_base_ex = sum(f["etiqueta_expansion_90d"] for f in filas) / len(filas)

    for fila in filas:
        inicio = inicio_de.get(fila["suscripcion_id"])
        cierre = a_fecha(fila["cierre_mes"])
        fila["_dias_aniv"] = dias_hasta_aniversario(inicio, cierre) if inicio else None

    print("=== ¿Cercania a la renovacion predice algo? ===")
    print("Tasa base: churn=%.2f%%  expansion=%.2f%%\n" % (100*tasa_base_ch, 100*tasa_base_ex))

    for periodo in ("year", "month", None):
        subset = [f for f in filas if f.get("plan_billing_period_unit") == periodo
                  and f["_dias_aniv"] is not None]
        if not subset:
            continue
        etiqueta = periodo or "(otro/vacio)"
        print("--- plan_billing_period_unit = %s  (%d filas) ---" % (etiqueta, len(subset)))
        por_bucket = collections.defaultdict(list)
        for f in subset:
            por_bucket[bucket(f["_dias_aniv"])].append(f)
        orden = ["0-30 dias", "31-90 dias", "91-180 dias", "181+ dias"]
        for b in orden:
            grupo = por_bucket.get(b, [])
            if not grupo:
                continue
            ch = sum(f["etiqueta_churn_120d"] for f in grupo) / len(grupo)
            ex = sum(f["etiqueta_expansion_90d"] for f in grupo) / len(grupo)
            print("   %-14s n=%6d   churn=%5.2f%% (base %.2f%%)   expansion=%5.2f%% (base %.2f%%)"
                  % (b, len(grupo), 100*ch, 100*tasa_base_ch, 100*ex, 100*tasa_base_ex))
        print()


if __name__ == "__main__":
    main()
