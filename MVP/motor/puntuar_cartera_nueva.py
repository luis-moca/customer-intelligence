"""Puntua con PYTHON una cartera que NO esta en maestro/.

Por que existe: puntuar.py entrena y puntua sobre el mismo archivo maestro
(las 9 carteras consolidadas). Cuando alguien corre exportar_para_dashboard.py
para SU cartera, esa cartera no esta ahi — y hasta hoy la unica forma de verla
puntuada era el motor de JavaScript del dashboard.

Este script cierra ese hueco por el lado de Python, y de paso sirve como
prueba de paridad real: la MISMA cartera nueva, puntuada por los dos caminos,
tiene que dar el mismo numero.

Regla que NO se rompe: el modelo se entrena SIEMPRE con maestro/ (las carteras
historicas etiquetadas) y se APLICA a la cartera nueva. Entrenar con la propia
cartera nueva seria hacer trampa — no tiene futuro observable todavia.

Uso:
    python3 puntuar_cartera_nueva.py <gram>

Lee:   salida/<gram>/<gram>_export.json   (lo que dejo exportar_para_dashboard)
Deja:  salida/<gram>/<gram>_puntuacion.json
"""
import datetime
import json
import os
import sys
import tempfile

import panel_fase2
from calibrar import ajustar_platt, aplicar
from features import construir_esquema, construir_x, nombres_de_columnas
from modelo_simple import entrenar, normalizar, predecir, vectorizar
from puntuar import (ACCION, DIAS_RENOVACION_RECIENTE,
                     MIN_LICENCIAS_PARA_SATURACION, OBJETIVOS, UMBRALES)

from rutas import MAESTRO

SALIDA = os.path.join(os.path.dirname(__file__), "salida")
ETIQUETAS = ("RESCATAR", "RIESGO DOWNGRADE", "PROBABLE CRECIMIENTO",
             "LARGO PLAZO (pendiente)", "SIN ACCION")


def construir_panel_de_la_cartera(export, gram, carpeta):
    """Arma el panel cuenta-mes de UNA cartera reusando panel_fase2 tal cual.

    No se reescribe nada de la logica: se deja el export con la MISMA forma de
    archivos que panel_fase2 espera de maestro/, y se le apunta la carpeta.
    Asi es imposible que este camino y el de las 9 carteras se desincronicen —
    corren el mismo codigo, byte por byte.
    """
    # Mismo filtro que consolidar_fase1: 5_renewed son contratos viejos ya
    # reemplazados por su renovacion, no cuentas. Contarlos duplicaria.
    foto = [dict(f, _gram=gram) for f in export["foto"]
            if str(f.get("subscription_state")) != "5_renewed"]

    escribir = lambda nombre, datos: json.dump(
        datos, open(os.path.join(carpeta, nombre), "w"), ensure_ascii=False)
    escribir("foto_maestra.json", foto)
    escribir("eventos_maestros.json", export["eventos"])
    escribir("pings_utiles.json", export["pings"])
    escribir("order_lines.json", export["order_lines"])

    # "Hoy" es la fecha del export, NO el ultimo evento de esta cartera. Si la
    # persona lleva dias sin movimiento, el tiempo no se detuvo. Es la misma
    # fecha que usa el dashboard (paquete.generado) — sin esto los dos motores
    # puntuan en dias distintos y divergen (ver panel_fase2.FIN_FORZADO).
    anterior = panel_fase2.CARPETA_MAESTRO
    anterior_fin = panel_fase2.FIN_FORZADO
    anterior_ini = panel_fase2.INICIO_FORZADO
    try:
        panel_fase2.CARPETA_MAESTRO = carpeta
        panel_fase2.FIN_FORZADO = panel_fase2.a_fecha(export["generado"])
        # La ventana REAL del log, del export — no el evento mas viejo que
        # esta persona tenga por casualidad (ver panel_fase2.INICIO_FORZADO).
        panel_fase2.INICIO_FORZADO = panel_fase2.a_fecha(
            export.get("ventana_eventos_desde"))
        panel_fase2.main()
    finally:
        panel_fase2.CARPETA_MAESTRO = anterior
        panel_fase2.FIN_FORZADO = anterior_fin
        panel_fase2.INICIO_FORZADO = anterior_ini

    return json.load(open(os.path.join(carpeta, "panel_cuenta_mes.json"))), foto


def main():
    if len(sys.argv) < 2:
        print("Falta el gram. Ejemplo:  python3 puntuar_cartera_nueva.py luesp")
        raise SystemExit(1)
    gram = sys.argv[1].strip().lower()

    ruta_export = os.path.join(SALIDA, gram, "%s_export.json" % gram)
    if not os.path.exists(ruta_export):
        print("No existe %s" % ruta_export)
        print("Corre primero:  python3 exportar_para_dashboard.py %s" % gram)
        raise SystemExit(1)

    export = json.load(open(ruta_export))
    print("=== Cartera nueva: %s (%s) ===" % (export.get("persona", gram), gram))
    print("Suscripciones en el export: %d | eventos: %d | pings: %d\n"
          % (len(export["foto"]), len(export["eventos"]), len(export["pings"])))

    print("--- Construyendo el panel cuenta-mes de esta cartera ---")
    with tempfile.TemporaryDirectory() as tmp:
        panel_nuevo, foto = construir_panel_de_la_cartera(export, gram, tmp)

    # --- Entrenamiento: SIEMPRE con maestro, nunca con la cartera nueva ---
    print("\n--- Entrenando con maestro/ (las carteras historicas) ---")
    maestro = json.load(open(os.path.join(MAESTRO, "panel_cuenta_mes.json")))
    ent = [f for f in maestro if not f["para_puntuar"]]
    ultimo = max(f["cierre_mes"] for f in ent)
    train = [f for f in ent if f["cierre_mes"] < ultimo]
    cal = [f for f in ent if f["cierre_mes"] == ultimo]

    puntuables = [f for f in panel_nuevo if f["para_puntuar"]]
    if not puntuables:
        print("Esta cartera no dejo ninguna fila puntuable. Nada que hacer.")
        raise SystemExit(1)
    cierre_hoy = max(f["cierre_mes"] for f in puntuables)
    hoy = [f for f in puntuables if f["cierre_mes"] == cierre_hoy]

    print("Entrena: %d filas | calibra: %d (%s) | puntua: %d cuentas vivas de %s (%s)"
          % (len(train), len(cal), ultimo, len(hoy), gram, cierre_hoy))

    esquema = construir_esquema(train)
    cols = nombres_de_columnas(esquema)
    st = normalizar([construir_x(f, esquema) for f in train], cols)
    vec = lambda fs: [vectorizar(construir_x(f, esquema), cols, st) for f in fs]
    Xtr, Xcal, Xhoy = vec(train), vec(cal), vec(hoy)

    # QUIEN es cada cuenta — nombre del cliente y codigo M. Mismo criterio que
    # puntuar.py, ver el comentario ahi.
    identidad = {}
    for s_ in foto:
        p = s_.get("partner_id")
        identidad[s_["id"]] = {
            "cliente": p[1] if isinstance(p, list) and len(p) == 2 else None,
            "codigo": s_.get("client_order_ref") or None,
            "orden": s_.get("name") or None,
        }

    cuentas = []
    for f in hoy:
        ident = identidad.get(f["suscripcion_id"], {})
        cuentas.append({"suscripcion_id": f["suscripcion_id"],
                        "cliente": ident.get("cliente"),
                        "codigo": ident.get("codigo"),
                        "orden": ident.get("orden"),
                        "gram": f["gram"],
                        # MRR al cierre (reconstruido del log, no el de hoy).
                        # NO es variable del modelo aqui: es para que la matriz
                        # del dashboard dibuje el tamano de cada burbuja — una
                        # cuenta de $5,000 no puede verse igual que una de $27.
                        "mrr": f.get("mrr"),
                        "acciones": []})

    # Fecha REAL de proxima factura (de la foto de HOY, no reconstruida).
    # "Hoy" = la fecha del export, la misma que usa el dashboard. Antes se
    # usaba cierre_hoy (el ultimo mes del panel), que en una cartera sin
    # movimiento reciente queda dias atras y corre todas las cuentas de dias.
    hoy_fecha = datetime.date.fromisoformat(str(export["generado"])[:10])
    dias_reales = {}
    for s_ in foto:
        ni = str(s_.get("next_invoice_date") or "")[:10]
        try:
            dias_reales[s_["id"]] = (datetime.date.fromisoformat(ni) - hoy_fecha).days
        except ValueError:
            pass

    recien_renovadas = set()
    for cta, fila in zip(cuentas, hoy):
        if fila.get("plan_billing_period_unit") != "year":
            continue
        prox = dias_reales.get(cta["suscripcion_id"])
        if prox is None:
            continue
        desde_renovacion = 365 - prox
        if 0 <= desde_renovacion < DIAS_RENOVACION_RECIENTE:
            recien_renovadas.add(cta["suscripcion_id"])
            cta["excluida"] = ("renovo hace %d dias — decision reciente ya "
                               "tomada y pagada" % desde_renovacion)

    for objetivo, nombre in OBJETIVOS:
        m = entrenar(Xtr, [f[objetivo] for f in train], cols)
        A, B = ajustar_platt([predecir(m, x) for x in Xcal],
                             [f[objetivo] for f in cal])
        for cta, x, fila in zip(cuentas, Xhoy, hoy):
            p = aplicar(A, B, predecir(m, x))
            cta["p_" + nombre] = round(p, 4)
            if p < UMBRALES[nombre] or cta["suscripcion_id"] in recien_renovadas:
                continue

            if nombre == "churn":
                renov = dias_reales.get(cta["suscripcion_id"])
                anual = fila.get("plan_billing_period_unit") == "year"
                if anual and renov is not None and renov > 120:
                    cta["acciones"].append("LARGO PLAZO (pendiente)")
                    cta["nota_largo_plazo"] = (
                        "renovacion anual/multianual a %d dias — no puede "
                        "churnear antes; candidata para el futuro modelo de "
                        "largo plazo, no una prediccion" % renov)
                    continue

            # Mismo desempate explicito que puntuar.py — ver el comentario ahi.
            aportes = sorted(((w * v, c) for w, v, c in zip(m["w"], x, cols)
                              if w * v > 0), key=lambda a: (-a[0], a[1]))[:3]
            motivos = []
            for _, c in aportes:
                base_col = c.split("=")[0]
                crudo = fila.get(base_col)
                if "=" in c or crudo is None:
                    motivos.append(c)
                else:
                    crudo = round(crudo, 2) if isinstance(crudo, float) else crudo
                    motivos.append("%s=%s" % (c, crudo))
            cta["acciones"].append(ACCION[nombre])
            cta["porque_" + nombre] = motivos

    # --- CUENTA LLENA (regla de negocio, fuera del modelo) ---
    for cta, fila in zip(cuentas, hoy):
        racha = fila.get("pings_al_tope") or 0
        licencias = fila.get("licencias_contratadas") or 0
        if (racha < 5 or licencias < MIN_LICENCIAS_PARA_SATURACION
                or cta["suscripcion_id"] in recien_renovadas):
            continue
        cta["cuenta_llena"] = {
            "pings_seguidos_al_tope": racha,
            "licencias": fila.get("licencias_contratadas"),
            "usuarios_activos": fila.get("uso_activos"),
        }
        if "PROBABLE CRECIMIENTO" not in cta["acciones"]:
            cta["acciones"].append("PROBABLE CRECIMIENTO")
        if fila.get("plan_billing_period_unit") == "month":
            cta["cuenta_llena"]["sugerencia_plan"] = (
                "mensual al tope — candidata tambien a cambio a plan anual "
                "o multianual (cambiar de plan tambien es expansion: sube el "
                "ingreso, no solo se venden usuarios o modulos)")

    for cta in cuentas:
        if not cta["acciones"]:
            cta["acciones"] = ["SIN ACCION"]

    ruta = os.path.join(SALIDA, gram, "%s_puntuacion.json" % gram)
    with open(ruta, "w") as fh:
        json.dump(cuentas, fh, ensure_ascii=False, indent=1)

    n = {k: sum(1 for c in cuentas if k in c["acciones"]) for k in ETIQUETAS}
    print("\n--- Cartera %s: %d cuentas vivas ---" % (gram, len(cuentas)))
    for k in ETIQUETAS:
        print("   %-26s %4d  (%4.1f%%)" % (k, n[k], 100 * n[k] / len(cuentas)))
    print("   %-26s %4d" % ("excluidas (renovo <4m)",
                            sum(1 for c in cuentas if c.get("excluida"))))
    print("\nGuardado: %s" % ruta)


if __name__ == "__main__":
    main()
