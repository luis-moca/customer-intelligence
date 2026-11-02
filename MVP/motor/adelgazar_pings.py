"""Deja de los pings SOLO lo que el modelo usa; tira el resto.

Por que existe: exportar_pings.py pidio las 30 columnas del ping, y ahi venian
repetidos 180,000 veces el correo, telefono, IP y URL de cada cliente. El motor
no usa nada de eso — usa una fecha y cuatro contadores. Este script se corre
UNA vez, en local, sin ninguna consulta a Odoo: reescribe el archivo dejando
solo los campos utiles y sin un solo dato de contacto.
"""
import json, os

from rutas import MAESTRO as M
# lo unico que el panel necesita de un ping
# 'id' se agrego el 23-ago-2026: hace falta para desempatar dos pings con el
# MISMO ping_time (28 casos en el maestro actual). Sin el, cargar_uso() tiene
# que caer a un criterio arbitrario. No es dato de contacto — es el numero de
# fila interno del ping.
CAMPOS = ["id", "_subscription_id", "ping_time",
          "nbr_active_regular_users", "nbr_regular_users",
          "nbr_active_users", "nbr_users", "nbr_share_users", "version"]

gordo = os.path.join(M, "pings.json")
flaco = os.path.join(M, "pings_utiles.json")

p = json.load(open(gordo))
out = [{c: f.get(c) for c in CAMPOS} for f in p]
with open(flaco, "w") as fh:
    json.dump(out, fh, ensure_ascii=False)

mb = lambda r: os.path.getsize(r) / 1e6
print("filas: %d (sin perder ninguna)" % len(out))
print("antes: %.1f MB con 30 campos (correo, telefono, IP, URL, nombre...)" % mb(gordo))
print("ahora: %.1f MB con %d campos, cero datos de contacto" % (mb(flaco), len(CAMPOS)))
print("ejemplo de fila:", out[0])
