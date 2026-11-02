"""
MEDICION DE LOS 132 CAMPOS contra los TRES desenlaces, sobre las 9 carteras.

Dos reglas del proyecto que este script obedece:
 1. Ningun campo se elimina por criterio de Claude. Mide Python, decide Luis.
 2. Todo se evalua contra EXPANSION, CONTRACCION (downgrade) y CHURN — nunca
    contra un solo grupo. La version anterior de este script solo miro
    "activas vs churneadas" y con eso propuso eliminar campos: dejaba fuera
    5,170 expansiones y 1,263 contracciones. Error corregido.

Desenlaces por suscripcion, leidos del log completo (no del estado actual):
    expandio  = tiene al menos un evento 1_expansion
    contrajo  = tiene al menos un evento 15_contraction
    churneo   = tiene al menos un evento 2_churn

Un campo puede ser inutil (o fuga) para churn y ser el mejor predictor de
expansion. Por eso el veredicto se reporta por desenlace, nunca uno solo.
"""
import collections
import json
import os

# 'rutas' va PRIMERO: es quien encuentra la carpeta de datos y pone
# motor/ en el camino de busqueda — sin eso, los imports de abajo fallan.
from rutas import MAESTRO
from exportar_todo import CAMPOS_SALE_ORDER


SALIDA_MD = os.path.join(os.path.dirname(__file__), "MEDICION_132.md")
SOPORTE_MINIMO = 50

DESENLACES = ["expansion", "contraccion", "churn"]


def clasificar_valor(v):
    if isinstance(v, list):
        if len(v) == 2 and isinstance(v[0], int) and isinstance(v[1], str):
            return v[0], "many2one"
        return len(v), "lista"
    return v, "simple"


def es_vacio(v, forma, es_booleano):
    if forma == "lista":
        return v == 0
    if es_booleano:
        return v is None
    return v in (None, False, "", [], {})


def idv(v):
    return v[0] if isinstance(v, list) else v


def main():
    foto = json.load(open(os.path.join(MAESTRO, "foto_maestra.json")))
    eventos = json.load(open(os.path.join(MAESTRO, "eventos_maestros.json")))

    # --- Los tres desenlaces, desde el log ---
    tipos_por_sub = collections.defaultdict(set)
    for ev in eventos:
        oid = idv(ev.get("order_id"))
        if oid is not None:
            tipos_por_sub[oid].add(str(ev.get("event_type")))

    resultado = {}
    for f in foto:
        tipos = tipos_por_sub.get(f["id"], set())
        resultado[f["id"]] = {
            "expansion": "1_expansion" in tipos,
            "contraccion": "15_contraction" in tipos,
            "churn": "2_churn" in tipos,
        }

    total = len(foto)
    bases = {d: sum(resultado[f["id"]][d] for f in foto) / total for d in DESENLACES}

    print("=== MEDICION DE LOS 132 CAMPOS — 3 desenlaces, 9 carteras ===")
    print("Suscripciones: %d\n" % total)
    for d in DESENLACES:
        n = sum(resultado[f["id"]][d] for f in foto)
        print("   %-12s %4d suscripciones  (tasa base %.1f%%)" % (d, n, 100 * bases[d]))
    print()

    filas_reporte = []

    for campo in sorted(CAMPOS_SALE_ORDER):
        if campo not in foto[0]:
            filas_reporte.append({"campo": campo, "veredicto_global": "NO EXPORTADO",
                                  "por_desenlace": {}, "llenado": None})
            continue

        crudos = [clasificar_valor(f.get(campo)) for f in foto]
        valores = [c[0] for c in crudos]
        forma = crudos[0][1] if crudos else "simple"
        no_nulos = {v for v in valores if v is not None}
        es_booleano = bool(no_nulos) and no_nulos <= {True, False}

        llenado = sum(1 for v in valores if not es_vacio(v, forma, es_booleano)) / total
        distintos = collections.Counter(
            v for v in valores if not isinstance(v, (list, dict)))
        cardinalidad = len(distintos)
        dominante = (distintos.most_common(1)[0][1] / total) if distintos else 1.0

        # --- Medicion contra CADA desenlace ---
        por_desenlace = {}
        for d in DESENLACES:
            por_valor = collections.defaultdict(lambda: [0, 0])
            for f, (v, _) in zip(foto, crudos):
                if isinstance(v, (list, dict)):
                    continue
                g = por_valor[v]
                g[0] += 1
                g[1] += resultado[f["id"]][d]

            separacion = False
            max_desv = 0.0
            detalle = ""
            for v, (n, ok) in por_valor.items():
                if n < SOPORTE_MINIMO:
                    continue
                tasa = ok / n
                desv = abs(tasa - bases[d])
                if desv > max_desv:
                    max_desv = desv
                    detalle = "%s -> %.0f%% (n=%d)" % (str(v)[:14], 100 * tasa, n)
                if tasa in (0.0, 1.0):
                    separacion = True

            if separacion:
                v_d = "FUGA"
            elif max_desv >= 0.10:
                v_d = "FUERTE"
            elif max_desv >= 0.03:
                v_d = "DEBIL"
            else:
                v_d = "NADA"
            por_desenlace[d] = {"veredicto": v_d, "desv": max_desv, "detalle": detalle}

        # --- Veredicto global: solo lo que NO depende de la etiqueta ---
        if llenado < 0.05:
            global_v = "VACIO"
        elif cardinalidad <= 1:
            global_v = "CONSTANTE"
        elif dominante > 0.99:
            global_v = "CASI CONSTANTE"
        elif all(por_desenlace[d]["veredicto"] == "FUGA" for d in DESENLACES):
            global_v = "FUGA EN LOS 3"
        elif any(por_desenlace[d]["veredicto"] == "FUGA" for d in DESENLACES):
            global_v = "FUGA PARCIAL"
        elif any(por_desenlace[d]["veredicto"] == "FUERTE" for d in DESENLACES):
            global_v = "SEÑAL FUERTE"
        elif any(por_desenlace[d]["veredicto"] == "DEBIL" for d in DESENLACES):
            global_v = "SEÑAL DEBIL"
        else:
            global_v = "SIN SEÑAL EN NINGUNO"

        filas_reporte.append({
            "campo": campo, "llenado": llenado, "cardinalidad": cardinalidad,
            "dominante": dominante, "por_desenlace": por_desenlace,
            "veredicto_global": global_v,
        })

    conteo = collections.Counter(f["veredicto_global"] for f in filas_reporte)
    for v, n in conteo.most_common():
        print("   %-22s %3d campos" % (v, n))
    print("\n   TOTAL: %d" % len(filas_reporte))

    with open(SALIDA_MD, "w") as fh:
        fh.write("# Medicion de los 132 campos — 3 desenlaces, 9 carteras\n\n")
        fh.write("Suscripciones: %d\n\n" % total)
        for d in DESENLACES:
            fh.write("- Tasa base **%s**: %.1f%%\n" % (d, 100 * bases[d]))
        fh.write("\nVeredicto por reglas, no por opinion. Propuesta para que "
                 "Luis decida.\n\n")
        fh.write("| Campo | Lleno | Val. | EXPANSION | CONTRACCION | CHURN | Global |\n")
        fh.write("|---|---|---|---|---|---|---|\n")
        for f in sorted(filas_reporte, key=lambda x: (x["veredicto_global"], x["campo"])):
            if f["llenado"] is None:
                fh.write("| `%s` | — | — | — | — | — | %s |\n"
                         % (f["campo"], f["veredicto_global"]))
                continue
            celdas = []
            for d in DESENLACES:
                pd_ = f["por_desenlace"][d]
                celdas.append("%s %s" % (pd_["veredicto"], pd_["detalle"]))
            fh.write("| `%s` | %.0f%% | %d | %s | %s | %s | **%s** |\n"
                     % (f["campo"], 100 * f["llenado"], f["cardinalidad"],
                        celdas[0], celdas[1], celdas[2], f["veredicto_global"]))
    print("\nTabla completa: %s" % SALIDA_MD)


if __name__ == "__main__":
    main()
