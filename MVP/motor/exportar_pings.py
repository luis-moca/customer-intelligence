"""
Exporta el HISTORICO de uso real: los pings semanales de cada base de datos.

Que es: conexiones_maestras trae 1 fila por suscripcion (foto de HOY), pero
cada fila cuelga ping_ids — el registro semanal de cuantos usuarios activos
tenia esa base en cada fecha. Mediana 83 pings por cuenta, max ~3,000.
Es la unica fuente que dice "cuanta gente usaba esta cuenta en marzo de 2024",
o sea: uso HISTORICO entrenable, no foto congelada.

Diseño de huella minima, mismo patron de siempre:
 - Todo lectura. Los ids de los pings YA estan en el disco local (vienen
   dentro de conexiones_maestras.json) — no hay que descubrir nada, solo
   leer esos registros por id, en lotes, con pausa entre lotes.
 - El modelo de los pings se descubre con UN fields_get (pregunta el esquema,
   no datos), y los campos bloqueados se detectan con la biseccion de siempre.
 - Acotado por construccion: solo los ids que cuelgan de las 1,922
   suscripciones ya exportadas. Cero barridos abiertos.

Uso:   python3 exportar_pings.py
Salida: maestro/pings.json  (+ resumen en consola)
"""
import json
import os
import time

from exportar_todo import encontrar_bloqueados
from fuente_odoo import conectar

from rutas import MAESTRO

TAMANO_LOTE = 5000
PAUSA = 0.5


def idv(v):
    return v[0] if isinstance(v, list) else v


def main():
    conexiones = json.load(open(os.path.join(MAESTRO, "conexiones_maestras.json")))

    ids_pings = []
    dueno = {}  # ping_id -> subscription_id, para ligar sin otra consulta
    for c in conexiones:
        sid = idv(c.get("subscription_id"))
        for pid in (c.get("ping_ids") or []):
            ids_pings.append(pid)
            dueno[pid] = sid
    ids_pings = sorted(set(ids_pings))
    print("Pings a leer: %d (de %d suscripciones, ids ya locales)"
          % (len(ids_pings), len({v for v in dueno.values()})))

    uid, consultar = conectar()

    # El modelo real de los pings: se pregunta al esquema, no se adivina.
    esquema_db = consultar("openerp.enterprise.database", "fields_get",
                           [["ping_ids"]], {"attributes": ["relation"]})
    modelo = esquema_db["ping_ids"]["relation"]
    print("Modelo de pings: %s" % modelo)

    # SOLO los campos que el motor usa. La primera version pidio las 30 columnas
    # del ping "por si acaso", y eso arrastro correo, telefono, IP, URL y nombre
    # de cada cliente repetidos 180,000 veces: 238 MB de datos de contacto en el
    # disco que el modelo jamas iba a mirar. Regla que queda: se piden los campos
    # que se van a usar, no los que existen.
    campos = ["ping_time", "nbr_active_regular_users", "nbr_regular_users",
              "nbr_active_users", "nbr_users", "nbr_share_users", "version"]
    esquema = consultar(modelo, "fields_get", [], {"attributes": ["type"]})
    faltantes = [c for c in campos if c not in esquema]
    if faltantes:
        raise SystemExit("El modelo %s no tiene: %s" % (modelo, faltantes))
    print("Campos pedidos: %d -> %s\n" % (len(campos), ", ".join(campos)))

    bloqueados = encontrar_bloqueados(consultar, modelo,
                                      [("id", "in", ids_pings[:50])], campos)
    campos = [c for c in campos if c not in bloqueados]
    if bloqueados:
        print("Bloqueados por permiso: %s" % ", ".join(bloqueados))

    todos = []
    for i in range(0, len(ids_pings), TAMANO_LOTE):
        lote = ids_pings[i:i + TAMANO_LOTE]
        filas = consultar(modelo, "read", [lote], {"fields": campos})
        todos.extend(filas)
        print("   %d/%d..." % (min(i + TAMANO_LOTE, len(ids_pings)), len(ids_pings)))
        time.sleep(PAUSA)

    for f in todos:
        f["_subscription_id"] = dueno.get(f["id"])

    ruta = os.path.join(MAESTRO, "pings.json")
    with open(ruta, "w") as fh:
        json.dump(todos, fh, ensure_ascii=False)

    fechas = sorted(str(f.get("create_date"))[:10] for f in todos
                    if f.get("create_date"))
    print("\nGuardado: %s" % ruta)
    print("Pings: %d | rango de fechas: %s a %s"
          % (len(todos), fechas[0] if fechas else "?", fechas[-1] if fechas else "?"))


if __name__ == "__main__":
    main()
