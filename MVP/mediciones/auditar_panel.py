"""
FASE 2.5 — Auditoria de fuga sobre el panel cuenta-mes.

La misma prueba que destapo enterprise_users, aplicada a las columnas que
genero panel_fase2.py. Pregunta unica: ¿alguna feature separa demasiado bien
las filas que churnean de las que no? Si una columna "predice" casi perfecto,
no es oro: es que esta leyendo el futuro, y hay que sacarla antes de entrenar.

Dos pruebas por columna, solo filas entrenables:
 1. Numericas: mediana en filas churn-en-90d vs filas sin churn, y el traslape
    real de sus distribuciones (si no se traslapan, es fuga casi segura).
 2. Categoricas: si algun valor concentra churn muy por encima de la tasa
    base (6.04%), se reporta para revision — puede ser señal real o fuga,
    pero se decide viendolo, no adivinando.

No toca Odoo. Solo lee maestro/panel_cuenta_mes.json.
"""
import collections
import json
import os
import statistics

from rutas import MAESTRO as CARPETA_MAESTRO

NO_SON_FEATURES = {
    "suscripcion_id", "cliente_id", "gram", "anio", "mes", "cierre_mes",
    "etiqueta_churn_120d", "etiqueta_expansion_90d", "para_puntuar",
}

# Todos estos son many2one: su valor es un entero (el id de Odoo), pero son
# CATEGORIAS, no cantidades. Un "id promedio" no significa nada — se prueban
# por churn-rate-por-valor, igual que cualquier categorico. Este bug se
# encontro a mano: el primer intento los clasifico por tipo de Python (int),
# no por significado, y eso escondio 2 candidatos reales (team_id=283 y
# l10n_mx_edi_payment_method_id=22, ambos con churn 3x-5x la base).
CATEGORICOS_AUNQUE_SEAN_ID = {
    "country_id", "industry_id", "plan_id", "source_id", "medium_id",
    "campaign_id", "team_id", "company_id", "currency_id", "pricelist_id",
    "l10n_mx_edi_payment_method_id", "l10n_mx_edi_usage",
}


def es_numerica(col, valores):
    if col in CATEGORICOS_AUNQUE_SEAN_ID:
        return False
    for v in valores:
        if v is not None and not isinstance(v, bool):
            return isinstance(v, (int, float))
    return False


def cuartiles(vals):
    vals = sorted(vals)
    n = len(vals)
    return vals[n // 4], vals[n // 2], vals[(3 * n) // 4]


def main():
    with open(os.path.join(CARPETA_MAESTRO, "panel_cuenta_mes.json")) as f:
        panel = json.load(f)

    filas = [f for f in panel if not f["para_puntuar"]]
    churn = [f for f in filas if f["etiqueta_churn_120d"] == 1]
    vivas = [f for f in filas if f["etiqueta_churn_120d"] == 0]
    tasa_base = len(churn) / len(filas)

    print("=== FASE 2.5 — Auditoria de fuga del panel ===")
    print("Filas entrenables: %d  (churn=%d, vivas=%d, tasa base=%.2f%%)\n"
          % (len(filas), len(churn), len(vivas), 100 * tasa_base))

    columnas = [c for c in filas[0] if c not in NO_SON_FEATURES]
    sospechosas = []

    print("--- Numericas: mediana churn vs vivas + traslape ---")
    print("%-28s %12s %12s %10s %10s  %s" % ("columna", "med.vivas", "med.churn",
                                             "%nulo ch.", "%nulo viv", "veredicto"))
    for col in columnas:
        vals_todos = [f.get(col) for f in filas]
        if not es_numerica(col, vals_todos):
            continue
        vc = [f.get(col) for f in churn if f.get(col) is not None]
        vv = [f.get(col) for f in vivas if f.get(col) is not None]
        nulos_ch = 100 * (1 - len(vc) / len(churn))
        nulos_vv = 100 * (1 - len(vv) / len(vivas))
        if not vc or not vv:
            sospechosas.append((col, "un grupo entero es nulo"))
            print("%-28s %12s %12s %9.0f%% %9.0f%%  FUGA: un grupo entero nulo"
                  % (col, "-", "-", nulos_ch, nulos_vv))
            continue

        q1c, mc, q3c = cuartiles(vc)
        q1v, mv, q3v = cuartiles(vv)
        # Traslape de rangos intercuartiles: si el IQR de churn no toca el de
        # vivas, la separacion es demasiado limpia para ser señal honesta.
        se_traslapan = not (q3c < q1v or q3v < q1c)
        # Diferencia brutal de nulos entre grupos tambien delata fuga
        # (el patron end_date: 97% lleno en churn, 2% en vivas).
        dif_nulos = abs(nulos_ch - nulos_vv)

        veredicto = "ok"
        if not se_traslapan:
            veredicto = "FUGA PROBABLE: distribuciones separadas"
            sospechosas.append((col, veredicto))
        elif dif_nulos > 30:
            veredicto = "FUGA PROBABLE: nulos %d%% vs %d%%" % (nulos_ch, nulos_vv)
            sospechosas.append((col, veredicto))
        print("%-28s %12.1f %12.1f %9.0f%% %9.0f%%  %s"
              % (col, mv, mc, nulos_ch, nulos_vv, veredicto))

    print("\n--- Categoricas: valores con churn muy sobre la tasa base ---")
    for col in columnas:
        vals_todos = [f.get(col) for f in filas]
        if es_numerica(col, vals_todos):
            continue
        grupos = collections.defaultdict(lambda: [0, 0])
        for f in filas:
            v = f.get(col)
            g = grupos[str(v)]
            g[0] += 1
            g[1] += f["etiqueta_churn_120d"]
        reportar = []
        for valor, (n, ch) in grupos.items():
            if n < 30:
                continue
            tasa = ch / n
            if tasa > 3 * tasa_base or (tasa == 0 and n > 500):
                reportar.append((valor, n, tasa))
        if reportar:
            print("   %s:" % col)
            for valor, n, tasa in sorted(reportar, key=lambda x: -x[2]):
                print("      %-24s n=%6d  churn=%5.1f%%  (base %.1f%%)"
                      % (valor[:24], n, 100 * tasa, 100 * tasa_base))

    print("\n=== VEREDICTO ===")
    if sospechosas:
        print("Columnas a revisar/sacar antes de entrenar:")
        for col, razon in sospechosas:
            print("   %-28s %s" % (col, razon))
    else:
        print("Ninguna columna numerica muestra el patron de fuga.")


if __name__ == "__main__":
    main()
