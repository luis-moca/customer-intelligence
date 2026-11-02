"""
PRUEBAS — la forma de salir del loop de "revisalo otra vez".

"Revisar" no converge: releer codigo siempre encuentra algo. Esto si converge,
porque es una lista fija de afirmaciones que o pasan o fallan. Se corre en
segundos, y se vuelve a correr cada vez que se toque cualquier script.

Regla: si todas pasan, se avanza sin volver a discutir. Si una falla, se
arregla ESA y se vuelve a correr. Nada de auditorias abiertas.

Uso:   python3 pruebas.py
"""
import collections
import datetime
import json
import os

from rutas import MAESTRO

BASE = os.path.dirname(__file__)
SALIDA = os.path.join(BASE, "salida")
VENTANA_LOG = "2023-08-23"

# --- VERDAD EXTERNA: conteos que Luis confirmo en el frontend de Odoo. ---
# Yo no puedo verificar esto solo; es la unica parte que viene de fuera.
# Las carteras que Luis NO confirmo en pantalla quedan fuera a proposito:
# inventar su valor esperado seria fabricar la vara con la que me mido.
CONFIRMADO_EN_FRONTEND = {
    "luram": {"activas": 193, "churn": 39},
    "edara": {"activas": 167, "churn": 37},
    "falg":  {"activas": 175, "churn": 41},
    "mnav":  {"activas": 186, "churn": 68},
    "lgcr":  {"activas": 143, "churn": 180},
}
SIN_CONFIRMAR = ["queb", "mseb", "lusan", "mjmc"]

resultados = []


def prueba(nombre, condicion, detalle=""):
    resultados.append((nombre, bool(condicion), detalle))


def idv(v):
    return v[0] if isinstance(v, list) else v


def a_fecha(t):
    try:
        return datetime.date.fromisoformat(str(t)[:10])
    except (ValueError, TypeError):
        return None


def main():
    foto = json.load(open(os.path.join(MAESTRO, "foto_maestra.json")))
    eventos = json.load(open(os.path.join(MAESTRO, "eventos_maestros.json")))
    panel = json.load(open(os.path.join(MAESTRO, "panel_cuenta_mes.json")))

    # ================= GRUPO 1: contra la realidad de Odoo =================
    por_gram = collections.defaultdict(lambda: collections.Counter())
    for f in foto:
        por_gram[f["_gram"]][str(f.get("subscription_state"))] += 1

    for gram, esperado in CONFIRMADO_EN_FRONTEND.items():
        act = por_gram[gram]["3_progress"]
        chu = por_gram[gram]["6_churn"]
        prueba("frontend %s: activas=%d" % (gram, esperado["activas"]),
               act == esperado["activas"], "obtuve %d" % act)
        prueba("frontend %s: churn=%d" % (gram, esperado["churn"]),
               chu == esperado["churn"], "obtuve %d" % chu)

    # ================= GRUPO 2: integridad de foto_maestra =================
    prueba("foto: cero contratos 5_renewed",
           not any(str(f.get("subscription_state")) == "5_renewed" for f in foto))
    ids = [f["id"] for f in foto]
    prueba("foto: cero ids duplicados", len(ids) == len(set(ids)))
    prueba("foto: solo estados 3_progress y 6_churn",
           {str(f.get("subscription_state")) for f in foto} == {"3_progress", "6_churn"})
    prueba("foto: todas las filas traen _gram", all("_gram" in f for f in foto))
    prueba("foto: cero partner_id nulos", all(f.get("partner_id") for f in foto))

    # suma por cartera == total consolidado
    prueba("foto: la suma por cartera cuadra con el total",
           sum(sum(c.values()) for c in por_gram.values()) == len(foto))

    # ================= GRUPO 3: integridad de eventos =================
    fechas = [str(e.get("event_date"))[:10] for e in eventos if e.get("event_date")]
    prueba("eventos: ninguno antes de la ventana comun %s" % VENTANA_LOG,
           all(f >= VENTANA_LOG for f in fechas),
           "el mas viejo es %s" % min(fechas))
    prueba("eventos: cero order_id nulos",
           all(e.get("order_id") for e in eventos))

    # ================= GRUPO 4: invariantes del panel =================
    # Mapa de cuando murio cada suscripcion, segun el log
    churn_de = {}
    por_sub = collections.defaultdict(list)
    for e in eventos:
        oid = idv(e.get("order_id"))
        fecha = a_fecha(e.get("event_date"))
        if oid is None or fecha is None:
            continue
        por_sub[oid].append((fecha, e.get("id"), str(e.get("event_type")),
                             e.get("recurring_monthly") or 0.0))
        if str(e.get("event_type")) == "2_churn":
            if oid not in churn_de or fecha < churn_de[oid]:
                churn_de[oid] = fecha
    # Mismo desempate (fecha, id) que usa panel_fase2.py — si la prueba
    # ordenara distinto, fallaria por su propio criterio, no por el panel.
    for lista in por_sub.values():
        lista.sort(key=lambda e: (e[0], e[1]))

    # 4a. Ninguna fila despues del mes en que la suscripcion murio
    violaciones = [f for f in panel
                   if f["suscripcion_id"] in churn_de
                   and a_fecha(f["cierre_mes"]) > churn_de[f["suscripcion_id"]]]
    prueba("panel: cero filas posteriores al churn de su suscripcion",
           not violaciones, "%d violaciones" % len(violaciones))

    # 4b. Coherencia de etiquetas
    prueba("panel: filas 'para_puntuar' no tienen etiqueta",
           all(f["etiqueta_churn_120d"] is None
               for f in panel if f["para_puntuar"]))
    prueba("panel: filas entrenables siempre tienen etiqueta",
           all(f["etiqueta_churn_120d"] is not None
               for f in panel if not f["para_puntuar"]))

    # 4c. LA PRUEBA CENTRAL — anti-fuga por reconstruccion independiente.
    # Se recalculan las features desde los eventos crudos, sin mirar el panel,
    # y se comparan. Si el panel hubiera usado un evento posterior al cierre
    # del mes, este recalculo daria distinto.
    fallos_recalculo = []
    revisadas = 0
    for fila in panel[::37]:  # muestra dispersa a lo largo de todo el panel
        cierre = a_fecha(fila["cierre_mes"])
        historia = por_sub.get(fila["suscripcion_id"], [])
        pasados = [e for e in historia if e[0] <= cierre]
        if not pasados:
            continue
        revisadas += 1
        esperado_exp = sum(1 for e in pasados if e[2] == "1_expansion")
        esperado_con = sum(1 for e in pasados if e[2] == "15_contraction")
        esperado_mrr = pasados[-1][3]
        if (fila["num_expansiones"] != esperado_exp
                or fila["num_contracciones"] != esperado_con
                or abs((fila["mrr"] or 0) - esperado_mrr) > 0.01):
            fallos_recalculo.append(fila["suscripcion_id"])
    prueba("panel: features recalculadas desde cero coinciden (%d filas)" % revisadas,
           not fallos_recalculo, "%d discrepancias" % len(fallos_recalculo))

    # 4d. Las etiquetas miran SOLO hacia adelante — churn exactamente 120 dias
    # (decision de Luis 22-ago-2026: con 90 las renovaciones de diciembre
    # quedaban fuera de la ventana)
    fallos_etiqueta = []
    for fila in panel[::53]:
        if fila["para_puntuar"]:
            continue
        cierre = a_fecha(fila["cierre_mes"])
        limite = cierre + datetime.timedelta(days=120)
        historia = por_sub.get(fila["suscripcion_id"], [])
        futuros = [e for e in historia if cierre < e[0] <= limite]
        esperado = int(any(e[2] == "2_churn" for e in futuros))
        if fila["etiqueta_churn_120d"] != esperado:
            fallos_etiqueta.append(fila["suscripcion_id"])
    prueba("panel: etiquetas de churn recalculadas coinciden",
           not fallos_etiqueta, "%d discrepancias" % len(fallos_etiqueta))

    # 4e. La antiguedad viene de first_contract_date, NO del log recortado.
    # Si viniera del log, ninguna cuenta pasaria de ~36 meses.
    antiguedades = [f["antiguedad_meses"] for f in panel
                    if f["antiguedad_meses"] is not None]
    prueba("panel: hay cuentas con mas de 36 meses (antiguedad NO sale del log)",
           max(antiguedades) > 36, "maxima=%d meses" % max(antiguedades))

    # 4f. Las columnas de la foto contaminadas NO deben existir en el panel
    prohibidas = {"enterprise_users", "end_date", "close_reason_id",
                  "subscription_state", "next_invoice_date", "invoice_count",
                  "upsell_count", "renewal_count", "history_count"}
    presentes = prohibidas & set(panel[0].keys())
    prueba("panel: cero columnas contaminadas de la foto",
           not presentes, "encontradas: %s" % sorted(presentes))

    # ================= REPORTE =================
    ok = sum(1 for _, p, _ in resultados if p)
    print("=" * 68)
    for nombre, paso, detalle in resultados:
        marca = "PASA" if paso else "FALLA"
        print("[%s] %s%s" % (marca, nombre,
                             ("  -> %s" % detalle) if (detalle and not paso) else ""))
    print("=" * 68)
    print("%d de %d pruebas pasaron." % (ok, len(resultados)))
    if SIN_CONFIRMAR:
        print("\nSIN VERDAD EXTERNA (no confirmadas por Luis en el frontend): %s"
              % ", ".join(SIN_CONFIRMAR))
        print("Sus conteos son internamente consistentes, pero nadie los ha")
        print("comparado contra Odoo. Si Luis los confirma, se agregan arriba.")
    # La paridad Python<->dashboard va aparte a proposito: tarda ~1 min (corre
    # el motor de JavaScript sobre cada cartera) y estas 25 son instantaneas.
    # Pero se recuerda SIEMPRE, porque es la unica que cacha que el dashboard
    # y Python se hayan separado — y esa divergencia no la ve nadie hasta que
    # un AM actua sobre un numero equivocado.
    print("\nFALTA CORRER APARTE (no incluida en las %d de arriba):" % len(resultados))
    print("   python3 verificar_paridad.py    <- el dashboard vs Python, "
          "cartera por cartera")
    print("   Obligatoria antes de compartir el dashboard o despues de tocar")
    print("   features. Ahi salieron 6 bugs el 23-ago-2026, 3 de ellos visibles")
    print("   SOLO al puntuar una cartera sola.")

    print("\nVEREDICTO: %s" % ("listo para avanzar de fase."
                               if ok == len(resultados)
                               else "NO avanzar hasta arreglar lo que falla."))


if __name__ == "__main__":
    main()
