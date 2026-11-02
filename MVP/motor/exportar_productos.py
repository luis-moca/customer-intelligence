"""
Trae el NOMBRE de los 39 productos que aparecen en order_lines.

Por que hace falta: order_lines trae product_id (un numero). Con solo el numero
no se puede distinguir un PLAN (que la cuenta contrata y predice) de un producto
que solo existe PORQUE la cuenta expandio (que no predice nada — es el resultado
disfrazado de causa). Ej: el producto id=5697 tiene 100% de expansion; eso puede
significar "producto pegajoso" o puede significar "esta linea SE CREA al expandir".
El nombre lo resuelve en un segundo.

Huella: 1 consulta de lectura sobre 39 ids, 2 columnas. No son datos de clientes,
es el catalogo de productos de Odoo.
"""
import json
import os

from fuente_odoo import conectar

from rutas import MAESTRO

CAMPOS = ["name", "default_code"]


def main():
    ol = json.load(open(os.path.join(MAESTRO, "order_lines.json")))
    ids = sorted({f["product_id"] for f in ol if f.get("product_id")})
    print("Productos a leer: %d (ids ya locales)" % len(ids))

    uid, consultar = conectar()
    filas = consultar("product.product", "read", [ids], {"fields": CAMPOS})

    ruta = os.path.join(MAESTRO, "productos.json")
    with open(ruta, "w") as fh:
        json.dump(filas, fh, ensure_ascii=False)

    print("Guardado: %s (%.1f KB)\n" % (ruta, os.path.getsize(ruta) / 1024))
    for f in sorted(filas, key=lambda x: x["id"]):
        print("  id=%-8s %s" % (f["id"], f.get("name")))


if __name__ == "__main__":
    main()
