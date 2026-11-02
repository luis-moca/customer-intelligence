"""
UN SOLO comando, UN SOLO archivo: todo lo que el dashboard necesita de tu
cartera, en una corrida.

Por que existe: antes hacian falta 4 scripts separados (foto+eventos+
conexiones, pings, order_lines, productos) apuntando a maestro/ — es decir,
solo servian para carteras que ya estaban en el archivo maestro consolidado.
Este script resuelve el caso real: "quiero cargar una cartera que no esta ahi".
Todo sale de tu propia cuenta, en un solo comando, sin tocar ningun archivo
local de otra persona.

Uso:
    export ODOO_URL=...  ODOO_DB=...  ODOO_USER=...  ODOO_API_KEY=...
    python3 exportar_para_dashboard.py <gram>

Ejemplo:
    python3 exportar_para_dashboard.py luram

Salida (UN archivo, listo para arrastrar al dashboard):
    salida/<gram>/<gram>_export.json

Diseño de huella minima, igual que siempre:
 - Solo lectura. Cero escritura, cero barridos abiertos.
 - Acotado por construccion al gram que se pide: primero se descubren las
   suscripciones de esa persona, y CADA consulta despues (eventos, conexiones,
   pings, lineas de producto) esta acotada a los ids que ya se encontraron —
   nunca una consulta abierta a todo Odoo.
 - Columnas siempre nombradas. Los pings en particular NUNCA piden mas de las
   7 que se usan (ver 03_LECCIONES.md del paquete MVP: pedir "todo lo que
   existe" en pings costo 238MB de datos de contacto en disco).
 - Reusa las MISMAS listas de campos y la MISMA biseccion de bloqueados que
   ya estan probadas en exportar_cartera.py / exportar_pings.py /
   exportar_order_lines.py — no se reinventa nada, solo se encadenan en una
   sola corrida y se cambia de donde salen los ids (de esta corrida, no de
   maestro/).
"""
import datetime
import json
import os
import sys
import time

from fuente_odoo import conectar, LIMITE_SEGURIDAD_CUENTAS
from exportar_todo import CAMPOS_SALE_ORDER, encontrar_bloqueados

CARPETA_SALIDA = os.path.join(os.path.dirname(__file__), "salida")
ANIOS_DE_HISTORICO = 3
PAUSA = 0.5

# Mismas listas nombradas que ya se midieron y aprobaron — una sola fuente
# de verdad de "que campos hacen falta", esten donde esten estos scripts.
CAMPOS_PINGS = ["ping_time", "nbr_active_regular_users", "nbr_regular_users",
                "nbr_active_users", "nbr_users", "nbr_share_users", "version"]
CAMPOS_LINEAS = ["product_id", "product_uom_qty", "price_subtotal", "discount",
                  "create_date"]


def idv(v):
    return v[0] if isinstance(v, list) else v


# Campos cuyo TEXTO son datos de medio de pago y no sirven para nada aqui.
# payment_token_id llega como [716290, '•••• 4553'] — los ultimos 4 digitos de
# la tarjeta del cliente. El motor NO lo usa (esta en la lista de excluidos de
# panel_fase2.py), pero viajaba de gratis dentro del archivo que se comparte
# por correo o Drive. Se deja solo el id: se conserva "tiene token de pago o
# no" y se van los digitos.
CAMPOS_SIN_TEXTO = ("payment_token_id",)


def sanear(fila):
    """Quita de una fila de sale.order los textos de medio de pago.

    No borra el campo — lo reduce a su id, que es lo unico que el motor podria
    llegar a mirar. Asi el archivo compartible deja de llevar los 4 digitos de
    la tarjeta sin que cambie ni un numero de la puntuacion.
    """
    limpia = dict(fila)
    for campo in CAMPOS_SIN_TEXTO:
        if isinstance(limpia.get(campo), list):
            limpia[campo] = idv(limpia[campo])
    return limpia


def leer(consultar, modelo, dominio, campos, etiqueta, limite=None):
    bloqueados = encontrar_bloqueados(consultar, modelo, dominio, campos)
    restantes = [c for c in campos if c not in bloqueados]
    opciones = {"fields": restantes}
    if limite:
        opciones["limit"] = limite
    filas = consultar(modelo, "search_read", [dominio], opciones)
    print("   %-28s %5d filas, %3d campos%s"
          % (etiqueta, len(filas), len(restantes),
             (", %d bloqueados (%s)" % (len(bloqueados), ", ".join(bloqueados)))
             if bloqueados else ""))
    return filas


def leer_por_lote(consultar, modelo, ids, campos, etiqueta, tamano_lote=3000):
    if not ids:
        return []
    bloqueados = encontrar_bloqueados(consultar, modelo, [("id", "in", ids[:50])], campos)
    restantes = [c for c in campos if c not in bloqueados]
    if bloqueados:
        print("      bloqueados en %s: %s" % (etiqueta, ", ".join(bloqueados)))
    todos = []
    for i in range(0, len(ids), tamano_lote):
        lote = ids[i:i + tamano_lote]
        todos.extend(consultar(modelo, "read", [lote], {"fields": restantes}))
        time.sleep(PAUSA)
    print("   %-28s %5d filas, %3d campos" % (etiqueta, len(todos), len(restantes)))
    return todos


def main():
    if len(sys.argv) < 2:
        print("Falta el gram. Ejemplo:  python3 exportar_para_dashboard.py luram")
        raise SystemExit(1)
    gram = sys.argv[1].strip().lower()

    print("Conectando a Odoo...")
    uid, consultar = conectar()
    hoy = datetime.date.today()
    corte = (hoy - datetime.timedelta(days=365 * ANIOS_DE_HISTORICO)).isoformat()

    # --- 1. Identificar a la persona por su gram (igual que exportar_cartera.py) ---
    dominio = [("user_id", "ilike", "(%s)" % gram), ("is_subscription", "=", True),
               ("state", "=", "sale")]
    prueba = consultar("sale.order", "search_read", [dominio],
                       {"fields": ["user_id"], "limit": 1})
    if not prueba:
        print("No encontre ordenes para el gram '%s'." % gram)
        print("Revisa que este bien escrito (va como aparece entre parentesis en Odoo).")
        raise SystemExit(1)
    persona = prueba[0]["user_id"]
    print("Persona: %s (%s)\n" % (persona[1], gram))

    print("=== Descargando (solo lectura, acotado a esta cartera) ===")

    # --- 2. Foto: los 132 campos de sale.order ---
    foto = leer(consultar, "sale.order", dominio, CAMPOS_SALE_ORDER,
               "foto de suscripciones", limite=LIMITE_SEGURIDAD_CUENTAS)
    if not foto:
        print("Sin resultados. Nada que guardar.")
        raise SystemExit(1)
    ids_orden = [f["id"] for f in foto]

    # --- 3. Eventos de MRR ---
    esquema_log = consultar("sale.order.log", "fields_get", [], {"attributes": ["type"]})
    eventos = leer(consultar, "sale.order.log",
                   [("order_id", "in", ids_orden), ("event_date", ">=", corte)],
                   sorted(esquema_log.keys()), "eventos MRR (%d anios)" % ANIOS_DE_HISTORICO)

    # --- 4. Conexiones (trae los ping_ids que se necesitan en el paso 6) ---
    esquema_db = consultar("openerp.enterprise.database", "fields_get", [],
                           {"attributes": ["type"]})
    conexiones = leer(consultar, "openerp.enterprise.database",
                      [("subscription_id", "in", ids_orden)],
                      sorted(esquema_db.keys()), "conexiones")

    # --- 5. Lineas de producto (ids salen de ESTA foto, no de disco) ---
    ids_lineas = []
    dueno_linea = {}
    for f in foto:
        for lid in (f.get("order_line") or []):
            ids_lineas.append(lid)
            dueno_linea[lid] = f["id"]
    ids_lineas = sorted(set(ids_lineas))
    lineas = leer_por_lote(consultar, "sale.order.line", ids_lineas, CAMPOS_LINEAS,
                           "lineas de producto")
    for l in lineas:
        l["_subscription_id"] = dueno_linea.get(l["id"])
        if isinstance(l.get("product_id"), list):
            l["product_id"] = l["product_id"][0]

    # --- 6. Pings (ids salen de ESTAS conexiones, no de disco) ---
    ids_pings, dueno_ping = [], {}
    for c in conexiones:
        sid = idv(c.get("subscription_id"))
        for pid in (c.get("ping_ids") or []):
            ids_pings.append(pid)
            dueno_ping[pid] = sid
    ids_pings = sorted(set(ids_pings))
    modelo_ping = consultar("openerp.enterprise.database", "fields_get",
                            [["ping_ids"]], {"attributes": ["relation"]})["ping_ids"]["relation"]
    pings = leer_por_lote(consultar, modelo_ping, ids_pings, CAMPOS_PINGS,
                          "pings de uso", tamano_lote=5000)
    for p in pings:
        p["_subscription_id"] = dueno_ping.get(p["id"])

    # --- 7. Catalogo de productos (solo los que aparecen en esta cartera) ---
    ids_productos = sorted({l["product_id"] for l in lineas if l.get("product_id")})
    productos = []
    if ids_productos:
        productos = consultar("product.product", "read",
                              [ids_productos], {"fields": ["id", "name"]})
    print("   %-28s %5d filas" % ("catalogo de productos", len(productos)))

    # --- Guardar: UN solo archivo, listo para arrastrar al dashboard ---
    destino = os.path.join(CARPETA_SALIDA, gram)
    os.makedirs(destino, exist_ok=True)
    paquete = {
        "gram": gram,
        "persona": persona[1],
        "generado": hoy.isoformat(),
        # Con que fecha se filtraron los eventos — el dashboard la necesita
        # para "historia_truncada" (si el cliente es mas viejo que la ventana
        # del log). Sin esto tendria que adivinarla.
        "ventana_eventos_desde": corte,
        "foto": [sanear(f) for f in foto],
        "eventos": eventos,
        "conexiones": conexiones,
        "order_lines": lineas,
        "pings": pings,
        "productos": productos,
    }
    ruta = os.path.join(destino, "%s_export.json" % gram)
    with open(ruta, "w") as fh:
        json.dump(paquete, fh, ensure_ascii=False)

    kb = os.path.getsize(ruta) / 1024
    print("\n=== Listo ===")
    print("Suscripciones: %d | eventos: %d | pings: %d | lineas de producto: %d"
          % (len(foto), len(eventos), len(pings), len(lineas)))
    print("Archivo (%.0f KB): %s" % (kb, ruta))
    print("\nSiguiente paso: arrastra ese archivo a la ventana del dashboard.")


if __name__ == "__main__":
    main()
