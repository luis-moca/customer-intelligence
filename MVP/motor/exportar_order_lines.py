"""
Exporta QUE PRODUCTOS tiene contratados cada cuenta (order_line resuelto).

Por que existe: order_line hoy solo se cuenta (LLAVES, en panel_fase2.py) —
sabemos CUANTAS lineas tiene una cuenta, no QUE hay en ellas. Sin esto el
modelo no puede contestar "que le falta comprar", que es la pregunta real de
upsell (la de "quien va a expandir" es debil: expande 1 de cada 3 cuentas).

Leccion aplicada de exportar_pings.py (se pidieron 30 campos "por si acaso" y
salieron 238MB con datos de contacto repetidos 180,000 veces): aqui se piden
SOLO 4 columnas, nombradas desde el inicio, nunca "todos los campos simples".

Huella: los 6,026 ids de las lineas YA estan en disco (dentro de order_line en
foto_maestra.json) — no hay descubrimiento, solo lectura por id. Sin datos de
contacto (ni nombre de producto en texto libre: product_id ya trae el nombre
del producto/modulo, que es lo que se necesita, no texto para redactar).

Uso:    python3 exportar_order_lines.py
Salida: maestro/order_lines.json  (+ resumen en consola)
"""
import json
import os
import time

from exportar_todo import encontrar_bloqueados
from fuente_odoo import conectar

from rutas import MAESTRO

TAMANO_LOTE = 3000
PAUSA = 0.5

# Nombradas desde el inicio — nunca "todos los campos simples".
# create_date es la clave del asunto: sin ella, el mix de productos es una foto
# de HOY y meterla al panel repetiria la fuga de siempre (pegarle a una fila de
# 2024 un producto contratado en 2026). Con la fecha se reconstruye que tenia
# contratado la cuenta en cada mes, igual que se hizo con MRR y con licencias.
CAMPOS = ["product_id", "product_uom_qty", "price_subtotal", "discount",
          "create_date"]


def idv(v):
    return v[0] if isinstance(v, list) else v


def main():
    foto = json.load(open(os.path.join(MAESTRO, "foto_maestra.json")))

    ids_lineas = []
    dueno = {}  # line_id -> subscription_id, sin consulta extra
    for s in foto:
        sid = s["id"]
        for lid in (s.get("order_line") or []):
            ids_lineas.append(lid)
            dueno[lid] = sid
    ids_lineas = sorted(set(ids_lineas))
    print("Lineas a leer: %d (ids ya locales, de %d suscripciones)"
          % (len(ids_lineas), len({v for v in dueno.values()})))

    uid, consultar = conectar()

    esquema = consultar("sale.order.line", "fields_get", [CAMPOS], {"attributes": ["type"]})
    faltantes = [c for c in CAMPOS if c not in esquema]
    if faltantes:
        raise SystemExit("sale.order.line no tiene: %s" % faltantes)
    print("Campos pedidos: %s\n" % ", ".join(CAMPOS))

    bloqueados = encontrar_bloqueados(consultar, "sale.order.line",
                                      [("id", "in", ids_lineas[:50])], CAMPOS)
    campos = [c for c in CAMPOS if c not in bloqueados]
    if bloqueados:
        print("Bloqueados por permiso: %s" % ", ".join(bloqueados))

    todos = []
    for i in range(0, len(ids_lineas), TAMANO_LOTE):
        lote = ids_lineas[i:i + TAMANO_LOTE]
        filas = consultar("sale.order.line", "read", [lote], {"fields": campos})
        todos.extend(filas)
        print("   %d/%d..." % (min(i + TAMANO_LOTE, len(ids_lineas)), len(ids_lineas)))
        time.sleep(PAUSA)

    for f in todos:
        f["_subscription_id"] = dueno.get(f["id"])
        # product_id llega [id, "nombre"] — se queda solo el id, el nombre es
        # texto libre que no hace falta y no se guarda en disco de mas.
        if isinstance(f.get("product_id"), list):
            f["product_id"] = f["product_id"][0]

    ruta = os.path.join(MAESTRO, "order_lines.json")
    with open(ruta, "w") as fh:
        json.dump(todos, fh, ensure_ascii=False)

    productos = {f["product_id"] for f in todos if f.get("product_id")}
    print("\nGuardado: %s" % ruta)
    print("Lineas: %d | productos distintos: %d | tamano: %.1f KB"
          % (len(todos), len(productos), os.path.getsize(ruta) / 1024))


if __name__ == "__main__":
    main()
