"""
Exporta la cartera de UNA persona, identificada por su gram.

Uso:   python3 exportar_cartera.py edara

Deja 4 archivos en salida/<gram>/:
   <gram>_foto.json          una fila por suscripción
   <gram>_eventos_log.json   histórico de MRR (últimos 3 años)
   <gram>_conexiones.json    última conexión por base de datos
   <gram>_resumen.txt        para saber de un vistazo qué se trajo

Diseño para dejar huella mínima en Odoo:
 - Todo es lectura, nada se escribe.
 - Acotado siempre al user_id de esa persona; cero barridos abiertos.
 - Sin upsell_content: es el campo con el bug que obliga a leer cuenta por
   cuenta (273 consultas para una sola cartera). Ya está clasificado como
   etiqueta, no predictor, así que no se pierde nada del modelo.
 - Histórico cortado a 3 años: menos volumen y los eventos viejos aportan
   poco. OJO: la antigüedad real del cliente NO se lee del log, se lee de
   first_contract_date en la foto (que sí viene completo, desde 2019).
 - Resultado: ~5 consultas por cartera.
"""
import datetime
import json
import os
import sys

from fuente_odoo import conectar, LIMITE_SEGURIDAD_CUENTAS
from exportar_todo import CAMPOS_SALE_ORDER, encontrar_bloqueados

CARPETA_SALIDA = os.path.join(os.path.dirname(__file__), "salida")
ANIOS_DE_HISTORICO = 3


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
    if limite and len(filas) >= limite:
        print("   [alerta] tope de seguridad alcanzado en %s — puede estar cortado."
              % etiqueta)
    return filas


def clientes_ya_exportados(gram_actual):
    """Revisa las carteras ya guardadas para avisar de clientes repetidos.
    Es lectura de archivos locales: cero consultas a Odoo."""
    vistos = {}
    if not os.path.isdir(CARPETA_SALIDA):
        return vistos
    for carpeta in sorted(os.listdir(CARPETA_SALIDA)):
        if carpeta == gram_actual:
            continue
        ruta = os.path.join(CARPETA_SALIDA, carpeta, "%s_foto.json" % carpeta)
        if not os.path.isfile(ruta):
            continue
        try:
            with open(ruta) as f:
                for fila in json.load(f):
                    p = fila.get("partner_id")
                    if p:
                        vistos.setdefault(p[0] if isinstance(p, list) else p, carpeta)
        except Exception:
            continue
    return vistos


def main():
    if len(sys.argv) < 2:
        print("Falta el gram. Ejemplo:  python3 exportar_cartera.py edara")
        raise SystemExit(1)
    gram = sys.argv[1].strip().lower()

    uid_mio, consultar = conectar()
    hoy = datetime.date.today()
    corte = (hoy - datetime.timedelta(days=365 * ANIOS_DE_HISTORICO)).isoformat()

    # --- Identificar a la persona ---
    # El gram viene entre paréntesis dentro del nombre que muestra Odoo
    # ("Eder Iván Aranda Vázquez (edara)"), NO en el campo login — por eso
    # se busca por nombre, que es como aparece en los filtros del frontend.
    dominio = [("user_id", "ilike", "(%s)" % gram), ("is_subscription", "=", True),
               ("state", "=", "sale")]
    prueba = consultar("sale.order", "search_read", [dominio],
                       {"fields": ["user_id"], "limit": 1})
    if not prueba:
        print("No encontré órdenes para el gram '%s'." % gram)
        print("Revisa que esté bien escrito (va como aparece entre paréntesis en Odoo).")
        raise SystemExit(1)
    persona = prueba[0]["user_id"]
    print("Persona encontrada: %s\n" % persona[1])

    print("=== Descargando (todo lectura, acotado a esta cartera) ===")
    foto = leer(consultar, "sale.order", dominio, CAMPOS_SALE_ORDER,
                "foto de suscripciones", limite=LIMITE_SEGURIDAD_CUENTAS)
    if not foto:
        print("Sin resultados. Nada que guardar.")
        raise SystemExit(1)

    ids = [f["id"] for f in foto]

    esquema_log = consultar("sale.order.log", "fields_get", [], {"attributes": ["type"]})
    eventos = leer(consultar, "sale.order.log",
                   [("order_id", "in", ids), ("event_date", ">=", corte)],
                   sorted(esquema_log.keys()),
                   "eventos MRR (%d años)" % ANIOS_DE_HISTORICO)

    esquema_db = consultar("openerp.enterprise.database", "fields_get", [],
                           {"attributes": ["type"]})
    conexiones = leer(consultar, "openerp.enterprise.database",
                      [("subscription_id", "in", ids)],
                      sorted(esquema_db.keys()), "conexiones")

    # --- Guardar ---
    destino = os.path.join(CARPETA_SALIDA, gram)
    os.makedirs(destino, exist_ok=True)
    for nombre, datos in (("foto", foto), ("eventos_log", eventos),
                          ("conexiones", conexiones)):
        ruta = os.path.join(destino, "%s_%s.json" % (gram, nombre))
        with open(ruta, "w") as f:
            json.dump(datos, f, ensure_ascii=False, indent=2)

    # --- Resumen legible ---
    import collections
    estados = collections.Counter(str(f.get("subscription_state")) for f in foto)
    activas = estados.get("3_progress", 0)
    churn = estados.get("6_churn", 0)
    renovadas = estados.get("5_renewed", 0)

    partners = {(f["partner_id"][0] if isinstance(f.get("partner_id"), list)
                 else f.get("partner_id")) for f in foto if f.get("partner_id")}
    previos = clientes_ya_exportados(gram)
    repetidos = {p: previos[p] for p in partners if p in previos}

    fechas = sorted(str(e.get("event_date"))[:10] for e in eventos if e.get("event_date"))
    antiguedad = sorted(str(f.get("first_contract_date"))[:10]
                        for f in foto if f.get("first_contract_date"))

    lineas = [
        "CARTERA: %s (%s)" % (persona[1], gram),
        "Exportado: %s" % hoy.isoformat(),
        "",
        "Suscripciones en el archivo: %d" % len(foto),
        "   activas (3_progress): %d" % activas,
        "   churneadas (6_churn): %d" % churn,
        "   renovadas/cerradas (5_renewed): %d" % renovadas,
        "   -> cuentas reales (activas + churn): %d" % (activas + churn),
        "",
        "Clientes únicos: %d" % len(partners),
        "Eventos de MRR: %d  (recorte a %d años, desde %s)"
        % (len(eventos), ANIOS_DE_HISTORICO, corte),
        "   rango real de eventos: %s a %s" % (fechas[0], fechas[-1]) if fechas
        else "   sin eventos en el rango",
        "Registros de conexión: %d" % len(conexiones),
        "",
        "Antigüedad del cliente más viejo: %s" % (antiguedad[0] if antiguedad else "?"),
        "(la antigüedad se lee de first_contract_date, NO del log recortado)",
        "",
        "Clientes que ya aparecían en otra cartera exportada: %d" % len(repetidos),
    ]
    for p, otra in sorted(repetidos.items(), key=lambda kv: kv[1]):
        lineas.append("   cliente id=%s ya estaba en '%s'" % (p, otra))

    texto = "\n".join(lineas)
    with open(os.path.join(destino, "%s_resumen.txt" % gram), "w") as f:
        f.write(texto + "\n")

    print()
    print(texto)
    print("\nGuardado en: %s" % destino)


if __name__ == "__main__":
    main()
