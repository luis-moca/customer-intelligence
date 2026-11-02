"""MEDICION: que cambia si los pings del mismo dia se ordenan por su HORA real.

El hallazgo (23-ago-2026, comparando Python contra el dashboard sobre la
cartera nueva de luesp): 1 cuenta de 127 daba una probabilidad distinta en los
dos motores. La causa no fue el puerto a JavaScript — fue que NINGUNO de los
dos tenia un orden definido para dos pings del MISMO dia.

  cargar_uso() guardaba (fecha, activos, creados) y hacia sort(). Con dos pings
  el mismo dia, el desempate lo terminaba decidiendo el numero de usuarios
  activos — o sea, "gana el ping con mas gente", que no significa nada.
  El JS ordenaba solo por fecha, asi que se quedaba con el ultimo que viniera
  en el archivo. Dos criterios arbitrarios distintos, mismo dato.

  Y lo importante: ping_time SI trae la hora ('2016-11-16 17:42:50'). El dato
  para desempatar bien siempre estuvo ahi; se estaba tirando al truncar a fecha.

Esto NO decide nada. Solo mide cuantas cuentas cambian de accion si se ordena
por hora real. El numero es para que Luis decida, no para aplicarlo solo.

Uso:  python3 medir_desempate_pings.py
"""
import collections
import contextlib
import datetime
import io
import json
import os
import tempfile

import panel_fase2
from calibrar import ajustar_platt, aplicar
from features import construir_esquema, construir_x, nombres_de_columnas
from modelo_simple import entrenar, normalizar, predecir, vectorizar
from puntuar import (ACCION, DIAS_RENOVACION_RECIENTE,
                     MIN_LICENCIAS_PARA_SATURACION, OBJETIVOS, UMBRALES)

from rutas import MAESTRO

ETIQUETAS = ("RESCATAR", "RIESGO DOWNGRADE", "PROBABLE CRECIMIENTO",
             "LARGO PLAZO (pendiente)", "SIN ACCION")


def cargar_uso_por_hora():
    """cargar_uso() con el desempate correcto: hora real del ping, luego id.

    Misma forma de salida que el original — (fecha, activos, creados) — para
    que ni uso_al_cierre() ni pings_al_tope() se enteren del cambio.
    """
    ruta = os.path.join(panel_fase2.CARPETA_MAESTRO, "pings_utiles.json")
    if not os.path.exists(ruta):
        return {}
    with open(ruta) as f:
        pings = json.load(f)
    serie = collections.defaultdict(list)
    for p in pings:
        t = p.get("ping_time")
        if not t:
            continue
        serie[p["_subscription_id"]].append((
            str(t), p.get("id") or 0,
            panel_fase2.a_fecha(t),
            p.get("nbr_active_regular_users") or 0,
            p.get("nbr_regular_users") or 0,
        ))
    salida = {}
    for sid, v in serie.items():
        v.sort()                       # por timestamp completo, luego id
        salida[sid] = [(f, a, c) for _, _, f, a, c in v]
    return salida


def puntuar_panel(panel, foto):
    """Mismo procedimiento que puntuar.py, sobre un panel que se le pasa."""
    ent = [f for f in panel if not f["para_puntuar"]]
    ultimo = max(f["cierre_mes"] for f in ent)
    train = [f for f in ent if f["cierre_mes"] < ultimo]
    cal = [f for f in ent if f["cierre_mes"] == ultimo]
    puntuables = [f for f in panel if f["para_puntuar"]]
    cierre_hoy = max(f["cierre_mes"] for f in puntuables)
    hoy = [f for f in puntuables if f["cierre_mes"] == cierre_hoy]

    esquema = construir_esquema(train)
    cols = nombres_de_columnas(esquema)
    st = normalizar([construir_x(f, esquema) for f in train], cols)
    vec = lambda fs: [vectorizar(construir_x(f, esquema), cols, st) for f in fs]
    Xtr, Xcal, Xhoy = vec(train), vec(cal), vec(hoy)

    cuentas = [{"suscripcion_id": f["suscripcion_id"], "gram": f["gram"],
                "acciones": []} for f in hoy]
    hoy_fecha = datetime.date.fromisoformat(cierre_hoy)
    dias_reales = {}
    for s_ in foto:
        ni = str(s_.get("next_invoice_date") or "")[:10]
        try:
            dias_reales[s_["id"]] = (datetime.date.fromisoformat(ni) - hoy_fecha).days
        except ValueError:
            pass

    recien = set()
    for cta, fila in zip(cuentas, hoy):
        if fila.get("plan_billing_period_unit") != "year":
            continue
        prox = dias_reales.get(cta["suscripcion_id"])
        if prox is None:
            continue
        if 0 <= 365 - prox < DIAS_RENOVACION_RECIENTE:
            recien.add(cta["suscripcion_id"])
            cta["excluida"] = "renovo hace %d dias" % (365 - prox)

    for objetivo, nombre in OBJETIVOS:
        m = entrenar(Xtr, [f[objetivo] for f in train], cols)
        A, B = ajustar_platt([predecir(m, x) for x in Xcal],
                             [f[objetivo] for f in cal])
        for cta, x, fila in zip(cuentas, Xhoy, hoy):
            p = aplicar(A, B, predecir(m, x))
            cta["p_" + nombre] = round(p, 4)
            if p < UMBRALES[nombre] or cta["suscripcion_id"] in recien:
                continue
            if nombre == "churn":
                renov = dias_reales.get(cta["suscripcion_id"])
                if (fila.get("plan_billing_period_unit") == "year"
                        and renov is not None and renov > 120):
                    cta["acciones"].append("LARGO PLAZO (pendiente)")
                    continue
            cta["acciones"].append(ACCION[nombre])

    for cta, fila in zip(cuentas, hoy):
        racha = fila.get("pings_al_tope") or 0
        lic = fila.get("licencias_contratadas") or 0
        if (racha < 5 or lic < MIN_LICENCIAS_PARA_SATURACION
                or cta["suscripcion_id"] in recien):
            continue
        cta["cuenta_llena"] = {"pings_seguidos_al_tope": racha}
        if "PROBABLE CRECIMIENTO" not in cta["acciones"]:
            cta["acciones"].append("PROBABLE CRECIMIENTO")

    for cta in cuentas:
        if not cta["acciones"]:
            cta["acciones"] = ["SIN ACCION"]
    return cuentas


def main():
    print("=== Que tan extendido esta el empate ===")
    pings = json.load(open(os.path.join(MAESTRO, "pings_utiles.json")))
    por_dia = collections.defaultdict(list)
    for p in pings:
        por_dia[(p["_subscription_id"], str(p.get("ping_time"))[:10])].append(p)
    conflicto = [k for k, v in por_dia.items() if len(v) > 1 and len(
        {(y.get("nbr_active_regular_users"), y.get("nbr_regular_users")) for y in v}) > 1]
    print("Pings totales:                                  %d" % len(pings))
    print("Pares (cuenta, dia) con mas de un ping:         %d" % sum(
        1 for v in por_dia.values() if len(v) > 1))
    print("   ...de esos, con uso DISTINTO (el orden manda): %d" % len(conflicto))
    print("Cuentas tocadas por al menos un empate:         %d de %d\n"
          % (len({k[0] for k in conflicto}), len({p["_subscription_id"] for p in pings})))

    foto = json.load(open(os.path.join(MAESTRO, "foto_maestra.json")))

    print("=== Reconstruyendo el panel con el orden por HORA real ===")
    original = panel_fase2.cargar_uso
    with tempfile.TemporaryDirectory() as tmp:
        for n in ("foto_maestra.json", "eventos_maestros.json",
                  "pings_utiles.json", "order_lines.json"):
            os.symlink(os.path.join(MAESTRO, n), os.path.join(tmp, n))
        anterior = panel_fase2.CARPETA_MAESTRO
        try:
            panel_fase2.CARPETA_MAESTRO = tmp
            panel_fase2.cargar_uso = cargar_uso_por_hora
            with contextlib.redirect_stdout(io.StringIO()):
                panel_fase2.main()
        finally:
            panel_fase2.cargar_uso = original
            panel_fase2.CARPETA_MAESTRO = anterior
        nuevo_panel = json.load(open(os.path.join(tmp, "panel_cuenta_mes.json")))

    viejo_panel = json.load(open(os.path.join(MAESTRO, "panel_cuenta_mes.json")))
    print("Filas del panel: antes %d | ahora %d\n" % (len(viejo_panel), len(nuevo_panel)))

    print("=== Puntuando con los dos paneles (mismo procedimiento) ===")
    antes = {c["suscripcion_id"]: c for c in puntuar_panel(viejo_panel, foto)}
    ahora = {c["suscripcion_id"]: c for c in puntuar_panel(nuevo_panel, foto)}

    cambios = []
    for sid, a in antes.items():
        b = ahora.get(sid)
        if not b:
            continue
        sa = sorted(a["acciones"])
        sb = sorted(b["acciones"])
        if sa != sb:
            cambios.append((sid, a["gram"], " + ".join(sa), " + ".join(sb)))

    print("\nCuentas que CAMBIAN de accion: %d de %d (%.1f%%)\n"
          % (len(cambios), len(antes), 100 * len(cambios) / len(antes)))
    if cambios:
        print("%-11s %-7s %-32s %s" % ("cuenta", "gram", "antes", "ahora"))
        for sid, g, sa, sb in sorted(cambios, key=lambda c: c[1])[:40]:
            print("%-11s %-7s %-32s %s" % (sid, g, sa, sb))
        if len(cambios) > 40:
            print("... y %d mas" % (len(cambios) - 40))

    print("\n=== Totales por etiqueta ===")
    print("%-26s %8s %8s %8s" % ("etiqueta", "antes", "ahora", "delta"))
    for k in ETIQUETAS:
        na = sum(1 for c in antes.values() if k in c["acciones"])
        nb = sum(1 for c in ahora.values() if k in c["acciones"])
        print("%-26s %8d %8d %+8d" % (k, na, nb, nb - na))


if __name__ == "__main__":
    main()
