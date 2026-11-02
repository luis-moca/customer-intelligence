"""Arma el <gram>_export.json de CADA cartera SIN volver a consultar Odoo.

Por que existe: exportar_para_dashboard.py hace ~18-20 consultas a Odoo por
cartera. Pero los datos de las 9 carteras YA estan descargados en maestro/
(foto, eventos, conexiones, pings, lineas de producto, productos). Volver a
pedirlos seria trafico innecesario contra Odoo para obtener exactamente lo
mismo que ya esta en disco.

Este script solo REORGANIZA lo que ya existe: filtra maestro/ por persona y
escribe el mismo paquete que dejaria exportar_para_dashboard.py. Cero red,
cero credenciales, cero huella en Odoo.

Uso:
    python3 armar_exports_desde_maestro.py            # las 9 carteras
    python3 armar_exports_desde_maestro.py luram      # solo una

Deja: salida/<gram>/<gram>_export.json

DIFERENCIA HONESTA contra un export bajado de Odoo hoy:
  1. Los pings de maestro/ no traen 'id' (adelgazar_pings.py lo dejo fuera
     antes de que se supiera que hacia falta para desempatar). Sin 'id' el
     desempate de dos pings con el MISMO segundo cae a (activos, creados).
     No es un problema de correccion: ese criterio esta escrito EXPLICITO e
     IDENTICO en Python y en el JS del dashboard, asi que los dos llegan al
     mismo numero. Solo significa que el desempate es arbitrario en 28 de
     180,692 pings, en vez de cronologico.
  2. maestro/ ya excluyo los documentos '5_renewed' (contratos viejos ya
     reemplazados por su renovacion). Un export fresco de Odoo si los trae y
     los filtra despues. El resultado final es el mismo: ninguno de los dos
     los puntua.
  3. La foto es del dia en que se consolido maestro/, no de hoy. Para una
     cartera que cambio desde entonces, hay que bajarla de Odoo de verdad.
"""
import collections
import json
import os
import sys

from exportar_para_dashboard import sanear
from rutas import MAESTRO

SALIDA = os.path.join(os.path.dirname(__file__), "salida")

# Con que fecha se filtraron los eventos al consolidar maestro/. El dashboard
# la usa para 'historia_truncada' (saber si el cliente es mas viejo que la
# ventana del log). Se mide del propio archivo en vez de escribirla a mano.
CAMPOS_PING = ["_subscription_id", "id", "ping_time", "nbr_active_regular_users",
               "nbr_regular_users", "nbr_active_users", "nbr_users",
               "nbr_share_users", "version"]


def idv(v):
    return v[0] if isinstance(v, list) else v


def main():
    pedidos = [a.strip().lower() for a in sys.argv[1:]]

    print("Leyendo maestro/ (esto tarda un poco, son ~140 MB)...")
    foto = json.load(open(os.path.join(MAESTRO, "foto_maestra.json")))
    eventos = json.load(open(os.path.join(MAESTRO, "eventos_maestros.json")))
    conexiones = json.load(open(os.path.join(MAESTRO, "conexiones_maestras.json")))
    lineas = json.load(open(os.path.join(MAESTRO, "order_lines.json")))
    pings = json.load(open(os.path.join(MAESTRO, "pings_utiles.json")))
    productos = json.load(open(os.path.join(MAESTRO, "productos.json")))

    grams = sorted({f["_gram"] for f in foto})
    if pedidos:
        faltan = [g for g in pedidos if g not in grams]
        if faltan:
            print("No estan en maestro/: %s" % ", ".join(faltan))
            print("Disponibles: %s" % ", ".join(grams))
            raise SystemExit(1)
        grams = pedidos

    ventana = min(str(e.get("event_date")) for e in eventos if e.get("event_date"))
    generado = max(str(e.get("event_date")) for e in eventos if e.get("event_date"))
    print("Ventana de eventos en maestro/: %s a %s\n" % (ventana, generado))

    # --- Indices, una sola pasada por archivo (no una por cartera) ---
    por_orden_ev = collections.defaultdict(list)
    for e in eventos:
        por_orden_ev[idv(e.get("order_id"))].append(e)

    por_sub_cx = collections.defaultdict(list)
    for c in conexiones:
        por_sub_cx[idv(c.get("subscription_id"))].append(c)

    por_sub_ol = collections.defaultdict(list)
    for l in lineas:
        por_sub_ol[l.get("_subscription_id")].append(l)

    por_sub_ping = collections.defaultdict(list)
    for p in pings:
        por_sub_ping[p.get("_subscription_id")].append(p)

    print("%-8s %8s %9s %11s %8s %9s %9s"
          % ("gram", "cuentas", "eventos", "conexiones", "lineas", "pings", "MB"))

    for gram in grams:
        suyas = [f for f in foto if f["_gram"] == gram]
        ids = {f["id"] for f in suyas}

        # 'persona' sale del user_id de sus propias ordenes — el mismo texto
        # que pondria exportar_para_dashboard.py ("Nombre Apellido (gram)").
        persona = next((f["user_id"][1] for f in suyas
                        if isinstance(f.get("user_id"), list) and len(f["user_id"]) == 2),
                       gram)

        ev = [e for i in ids for e in por_orden_ev.get(i, [])]
        cx = [c for i in ids for c in por_sub_cx.get(i, [])]
        ol = [l for i in ids for l in por_sub_ol.get(i, [])]
        pg = [{c: p.get(c) for c in CAMPOS_PING if c in p}
              for i in ids for p in por_sub_ping.get(i, [])]

        # Solo el catalogo de los productos que esta cartera de verdad tiene.
        usados = {l.get("product_id") for l in ol if l.get("product_id")}
        prods = [p for p in productos if p["id"] in usados]

        paquete = {
            "gram": gram,
            "persona": persona,
            "generado": generado,
            "ventana_eventos_desde": ventana,
            # sanear() quita los 4 digitos de la tarjeta (payment_token_id),
            # que el motor no usa y no tienen por que viajar en un archivo que
            # se comparte por correo.
            "foto": [sanear({k: v for k, v in f.items() if k != "_gram"})
                     for f in suyas],
            "eventos": ev,
            "conexiones": cx,
            "order_lines": ol,
            "pings": pg,
            "productos": prods,
        }

        destino = os.path.join(SALIDA, gram)
        os.makedirs(destino, exist_ok=True)
        ruta = os.path.join(destino, "%s_export.json" % gram)
        with open(ruta, "w") as fh:
            json.dump(paquete, fh, ensure_ascii=False)

        print("%-8s %8d %9d %11d %8d %9d %9.1f"
              % (gram, len(suyas), len(ev), len(cx), len(ol), len(pg),
                 os.path.getsize(ruta) / 1e6))

    print("\nListos en salida/<gram>/<gram>_export.json — cero consultas a Odoo.")


if __name__ == "__main__":
    main()
