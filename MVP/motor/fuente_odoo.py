"""
FUENTE ODOO — el conector real. NO SE USA hasta que tú lo actives.

Habla con Odoo por su API externa (XML-RPC), usando solo la librería estándar
de Python. Sin instalar nada.

QUÉ NECESITAS ANTES DE USARLO
-----------------------------
1. Tu API key de Odoo (Preferencias -> Seguridad de la cuenta -> Nueva clave API).
2. Guardarla como variable de entorno, NUNCA escrita en este archivo:

       export ODOO_URL="https://www.odoo.com"
       export ODOO_DB="nombre_de_la_base"
       export ODOO_USER="tu_correo@odoo.com"
       export ODOO_API_KEY="la_clave_que_generaste"

   (Si cierras la Terminal se borran. Para dejarlas fijas se ponen en ~/.zshrc.)

3. Correr primero la exploración, porque no sabemos aún qué modelos y campos
   tiene la base interna de Odoo México ni a cuáles te da acceso tu perfil:

       python3 fuente_odoo.py

   Eso NO extrae datos de clientes: solo pregunta "¿qué existe y qué puedo leer?".

SOBRE PERMISOS
--------------
Una API key hereda EXACTAMENTE los permisos de tu usuario, ni uno más.
Lo que no ves en la pantalla de Odoo, tampoco lo ves por aquí.
Y este archivo solo usa 'search_read' y 'fields_get': operaciones de LECTURA.
No hay una sola llamada que escriba, modifique o borre nada.
"""

import os
import re
import xmlrpc.client


def _config():
    faltantes = [v for v in ("ODOO_URL", "ODOO_DB", "ODOO_USER", "ODOO_API_KEY")
                 if not os.environ.get(v)]
    if faltantes:
        raise RuntimeError(
            "Faltan variables de entorno: %s\n"
            "Configúralas antes de correr (ver instrucciones arriba)." % ", ".join(faltantes)
        )
    return (os.environ["ODOO_URL"].rstrip("/"), os.environ["ODOO_DB"],
            os.environ["ODOO_USER"], os.environ["ODOO_API_KEY"])


def conectar():
    """
    Se autentica contra Odoo y devuelve lo necesario para hacer consultas.
    Devuelve: (uid, funcion_para_consultar)
    """
    url, db, usuario, clave = _config()

    common = xmlrpc.client.ServerProxy("%s/xmlrpc/2/common" % url)
    uid = common.authenticate(db, usuario, clave, {})

    if not uid:
        raise RuntimeError(
            "Odoo rechazó las credenciales. Revisa ODOO_DB, ODOO_USER y ODOO_API_KEY."
        )

    modelos = xmlrpc.client.ServerProxy("%s/xmlrpc/2/object" % url)

    def consultar(modelo, metodo, argumentos, opciones=None):
        return modelos.execute_kw(db, uid, clave, modelo, metodo,
                                  argumentos, opciones or {})

    return uid, consultar


# Modelos que típicamente importan para Customer Success.
# Cuáles existan y cuáles puedas leer depende de la versión y de tu perfil:
# por eso explorar() los prueba uno por uno en vez de asumirlos.
# Segunda barda de contención, además del filtro user_id=uid: un tope duro
# a la consulta. Si algo cambiara (permisos, un uid mal puesto, lo que sea)
# y la consulta empezara a traer de más, esto la corta en seco en vez de
# dejarla crecer sin control.
# Subido de 500 a 900 el 22-ago-2026: la foto de sale.order incluye también
# los documentos 5_renewed (contratos viejos ya reemplazados), y la cartera
# de Lucero Chimal (lgcr) los sumó a sus cuentas reales y pegó justo en 500,
# cortando 8 cuentas reales del archivo. 900 deja margen para carteras
# grandes con mucho historial de renovación sin perder la función de freno.
LIMITE_SEGURIDAD_CUENTAS = 900

MODELOS_CANDIDATOS = [
    ("res.partner", "Clientes / contactos"),
    ("sale.order", "Órdenes y suscripciones"),
    ("sale.subscription", "Suscripciones (versiones anteriores)"),
    ("sale.order.line", "Líneas de orden (planes, cantidades)"),
    ("account.move", "Facturas"),
    ("helpdesk.ticket", "Tickets de soporte"),
    ("crm.lead", "Oportunidades"),
    ("mail.message", "Chatter / mensajes"),
    ("res.users", "Usuarios"),
    ("openerp.enterprise.database", "Bases de datos / uso real (confirmado 18-ago)"),
]

# Filtro para no repetir el paseo de 357 campos: solo enseña lo que podría
# servir para el motor (dueño de la cuenta, dinero, fechas, estatus, plan).
PALABRAS_CLAVE_CAMPOS = [
    "user", "salesperson", "partner", "amount", "price", "total", "mrr",
    "subscription", "recurring", "renew", "state", "stage", "date", "plan",
    "product", "quantity", "qty", "company", "currency", "invoice_status",
    "team", "tag", "active",
]


def verificar_churn_real():
    """
    Corrige contar_universo_real(): esa función contó sale.order EN BRUTO
    por estado, sin deduplicar por cliente — el mismo error que ya se había
    corregido en obtener_cartera() (1 orden != 1 cuenta), aplicado sin
    querer otra vez sobre las canceladas. Luis lo señaló el 18-ago-2026:
    "no tengo mas de 240 cuentas... no tengo mas de 40 cuentas en churn".

    Aquí se cuentan CLIENTES únicos (partner_id), no órdenes. Una orden
    cancelada de un cliente que sigue con otra orden activa NO es un
    cliente perdido — ya está contado en la cartera viva.
    """
    uid, consultar = conectar()

    activas = consultar(
        "sale.order", "search_read",
        [[("user_id", "=", uid), ("is_subscription", "=", True), ("state", "=", "sale")]],
        {"fields": ["partner_id"]},
    )
    partners_activos = {o["partner_id"][0] for o in activas if o["partner_id"]}
    print("Clientes con al menos 1 orden activa (state=sale): %d" % len(partners_activos))
    print("  (de %d órdenes activas en bruto — confirma la fusión que ya hace obtener_cartera)"
          % len(activas))

    canceladas = consultar(
        "sale.order", "search_read",
        [[("user_id", "=", uid), ("is_subscription", "=", True), ("state", "=", "cancel")]],
        {"fields": ["partner_id"]},
    )
    partners_cancelados = {o["partner_id"][0] for o in canceladas if o["partner_id"]}
    print("\nÓrdenes canceladas en bruto: %d" % len(canceladas))
    print("Clientes ÚNICOS con al menos 1 orden cancelada: %d" % len(partners_cancelados))

    solapados = partners_cancelados & partners_activos
    perdidos = partners_cancelados - partners_activos
    print("\n  De esos, %d YA tienen una orden activa — no están perdidos, ya contados." % len(solapados))
    print("  %d NO tienen ninguna orden activa — estos son clientes perdidos de verdad,"
          " fuera de las cuentas vivas." % len(perdidos))

    print("\n--- Comparación con lo que ya sabíamos ---")
    print("  subscription_state='6_churn' dentro de las activas (encontrado antes): 37")
    print("  clientes perdidos nuevos que aparecen aquí (orden cancelada, sin ninguna activa): %d"
          % len(perdidos))
    print("  (si hay traslape entre estos dos grupos, el total real de churn es")
    print("   MENOR a la suma directa — puede ser el mismo cliente contado dos veces)")


def contar_universo_real():
    """
    Diagnóstico puntual, solo lectura: cuántas sale.order tuyas existen de
    verdad, SIN el filtro state="sale" que usa obtener_cartera().

    Hipótesis a probar (18-ago-2026): tanto mi extracción como la de
    Antigravity coinciden en ~230-235 cuentas, las dos por debajo del total
    real de Luis. Las dos extracciones piden solo state="sale" (o "sale"+
    "sent"). Si una cuenta churnea y Odoo le cierra la orden completa
    (state="cancel"), en vez de solo cambiar subscription_state, ninguna
    de las dos la ve. Esto cuenta cuántas hay en cada estado, sin extraer
    ninguna cuenta todavía.
    """
    uid, consultar = conectar()

    print("Conteo por 'state', SIN filtrar por state (solo user_id + is_subscription):")
    print("-" * 66)
    total = 0
    for estado in ("sale", "sent", "cancel", "draft", "done"):
        n = consultar("sale.order", "search_count",
                     [[("user_id", "=", uid), ("is_subscription", "=", True),
                       ("state", "=", estado)]])
        if n:
            print("   state=%-8s %d cuentas" % (estado, n))
        total += n
    print("-" * 66)
    print("   TOTAL (todos los estados): %d" % total)

    n_sin_filtro_estado = consultar(
        "sale.order", "search_count",
        [[("user_id", "=", uid), ("is_subscription", "=", True)]])
    print("\n   Confirmación (sin filtrar 'state' en absoluto): %d" % n_sin_filtro_estado)

    if total < n_sin_filtro_estado:
        print("\n   *** Hay estados de 'state' que no están en la lista de arriba.")
        print("       Corre explorar() para ver el esquema completo del campo.")

    print("\n   Lo que obtener_cartera() ve hoy (state='sale' únicamente):")
    n_actual = consultar(
        "sale.order", "search_count",
        [[("user_id", "=", uid), ("is_subscription", "=", True), ("state", "=", "sale")]])
    print("   %d cuentas — %d menos que el universo completo" % (
        n_actual, n_sin_filtro_estado - n_actual))


def explorar_historial_uso():
    """
    Diagnóstico puntual, solo lectura: por qué obtener_cartera() ve 1 fila de
    historial por cuenta en openerp.enterprise.database, cuando la captura de
    pantalla de Luis (18-ago-2026, modal "Databases" de SOLAR HUB) muestra 15+
    filas semanales para una sola suscripción.

    Prueba dos hipótesis, en orden de probabilidad. No extrae ninguna cuenta,
    no cruza con nombres — es solo para entender la forma del dato antes de
    tocar la lógica de adopción otra vez.
    """
    uid, consultar = conectar()

    ordenes = consultar(
        "sale.order", "search_read",
        [[("user_id", "=", uid), ("is_subscription", "=", True), ("state", "=", "sale")]],
        {"fields": ["id"], "limit": 10},
    )
    if not ordenes:
        print("No encontré ninguna orden tuya para probar.")
        return
    ids_prueba = [o["id"] for o in ordenes]

    # Primero el esquema real — no se vuelve a adivinar un nombre de campo.
    # La corrida anterior tronó pidiendo "active", que no existe en este
    # modelo (Odoo lo dijo explícito: "Invalid field 'active'"). Eso ya
    # descarta la hipótesis de filas archivadas: no hay active que archive.
    print("=== Esquema real de openerp.enterprise.database ===")
    esquema = consultar("openerp.enterprise.database", "fields_get", [],
                        {"attributes": ["string", "type", "relation"]})
    print("  %d campos en total. 'active' existe: %s" % (len(esquema), "active" in esquema))

    campos_fecha = sorted(n for n, i in esquema.items() if i.get("type") in ("date", "datetime"))
    print("  Campos de fecha/hora disponibles: %s" % campos_fecha)

    candidatos = [(n, i.get("relation")) for n, i in esquema.items()
                  if i.get("type") in ("one2many", "many2many") and i.get("relation")]
    print("  Campos relacionales (posible historial colgado de aquí): %s" % (candidatos or "ninguno"))

    print("\n=== Filas reales para tus órdenes de prueba ===")
    filas = consultar(
        "openerp.enterprise.database", "search_read",
        [[("subscription_id", "in", ids_prueba)]],
        {"fields": ["subscription_id"] + campos_fecha},
    )
    print("  %d filas encontradas para %d órdenes" % (len(filas), len(ids_prueba)))
    for f in filas[:8]:
        print("    ", f)

    if not candidatos:
        print("\n  Sin campos relacionales en este modelo — el historial que ves en pantalla")
        print("  no cuelga de aquí. Vive en otro modelo por completo, y ese modelo")
        print("  todavía no lo conocemos.")
        return

    if not filas:
        print("\n  No hay ninguna fila base de dónde partir para probar los candidatos.")
        return

    print("\n=== Probando los campos relacionales contra un registro real ===")
    for nombre, rel in candidatos:
        valor = consultar("openerp.enterprise.database", "read",
                          [[filas[0]["id"]]], {"fields": [nombre]})
        relacionados = valor[0].get(nombre) or []
        print("     %-28s -> %d registros en %s" % (nombre, len(relacionados), rel))


def explorar_historial_mrr():
    """
    Diagnóstico puntual, solo lectura: en el archivo que sacó Antigravity
    (Anti 2.0/CSI_Np/cartera_93_campos_estrategicos.json) apareció un campo
    'order_log_ids' presente en el 100% de las cuentas, con la forma de un
    puntero a otro modelo (lista de IDs enteros). Hipótesis a probar: ese
    modelo YA lleva el historial de cambios de MRR (altas, bajas, renovación)
    de cada cuenta desde que existe, nativo de Odoo Subscriptions.

    Si se confirma, no hace falta construir un cron + SQLite desde cero para
    fabricar histórico (el plan que traía Antigravity): ya existe, y
    probablemente con más profundidad que lo que daría empezar a apuntar
    hoy y esperar semanas a acumular pings.

    No extrae ninguna cuenta nueva. La consulta de las filas de historial
    EXCLUYE a propósito cualquier campo relacional (many2one/one2many/
    many2many) salvo el que liga la fila a la orden — así ningún nombre de
    cliente puede aparecer en la salida, no por promesa, por diseño de la
    consulta misma.
    """
    uid, consultar = conectar()

    ordenes = consultar(
        "sale.order", "search_read",
        [[("user_id", "=", uid), ("is_subscription", "=", True), ("state", "=", "sale")]],
        {"fields": ["id"], "limit": 10},
    )
    if not ordenes:
        print("No encontré ninguna orden tuya para probar.")
        return
    ids_prueba = [o["id"] for o in ordenes]

    print("=== ¿A qué modelo apunta 'order_log_ids'? ===")
    esquema_orden = consultar("sale.order", "fields_get", [],
                              {"attributes": ["string", "type", "relation"]})
    info = esquema_orden.get("order_log_ids")
    if not info:
        print("  'order_log_ids' no existe en sale.order en esta base/versión.")
        print("  (puede que Antigravity lo haya sacado de otro modelo relacionado")
        print("   — revisar cómo arma su extracción antes de descartar la idea.)")
        return

    modelo_log = info.get("relation")
    print("  order_log_ids -> modelo '%s' (%s)" % (modelo_log, info.get("string")))
    if not modelo_log:
        print("  Sin modelo relacionado — no hay nada más que explorar aquí.")
        return

    print("\n=== Esquema real de %s ===" % modelo_log)
    try:
        esquema_log = consultar(modelo_log, "fields_get", [],
                                {"attributes": ["string", "type", "relation"]})
    except Exception as e:
        print("  No se pudo leer el esquema: %s" % e)
        print("  (puede ser acceso denegado para tu perfil — eso también es una respuesta)")
        return

    print("  %d campos en total:" % len(esquema_log))
    for nombre, campo in sorted(esquema_log.items()):
        print("   %-28s %-12s %s" % (nombre, campo.get("type", ""), campo.get("string", "")))

    campo_orden = next((c for c in ("order_id", "subscription_id") if c in esquema_log), None)
    if not campo_orden:
        print("\n  No encontré un campo obvio que ligue estas filas a la orden")
        print("  ('order_id' / 'subscription_id'). Revisa el esquema de arriba a mano.")
        return

    # Solo campos no relacionales + el que liga a la orden. Nunca partner_id
    # ni nada que resuelva a un nombre de cliente, aunque el modelo lo tenga.
    campos_seguros = sorted(
        n for n, i in esquema_log.items()
        if n == campo_orden or i.get("type") not in ("many2one", "one2many", "many2many")
    )

    print("\n=== Filas reales para tus %d órdenes de prueba (campos: %s) ==="
          % (len(ids_prueba), ", ".join(campos_seguros)))
    filas = consultar(
        modelo_log, "search_read",
        [[(campo_orden, "in", ids_prueba)]],
        {"fields": campos_seguros, "order": "id asc"},
    )
    print("  %d filas encontradas" % len(filas))

    # order_id (many2one) llega como [id, nombre] aunque se haya pedido como
    # "el campo que liga a la orden" — se reduce al id puro: ni para agrupar
    # ni para imprimir hace falta la mitad del nombre.
    def _id_de(valor):
        return valor[0] if isinstance(valor, (list, tuple)) else valor

    for f in filas:
        f[campo_orden] = _id_de(f[campo_orden])

    por_orden = {}
    for f in filas:
        por_orden.setdefault(f[campo_orden], []).append(f)
    for oid in ids_prueba:
        print("   orden %s: %d eventos" % (oid, len(por_orden.get(oid, []))))

    if filas:
        print("\n  Primeras 3 filas completas (sin identidad de cliente, por diseño de la consulta):")
        for f in filas[:3]:
            print("   ", f)

    print("\n" + "=" * 72)
    print("Si esto trajo fechas/montos que van más atrás de hoy: ya existe historial")
    print("nativo, no hay que construir el cron de Antigravity. Pásame esta salida completa.")
    print("=" * 72)


def medir_profundidad_historial_mrr():
    """
    Sigue a explorar_historial_mrr(): ya confirmado que 'order_log_ids'
    apunta a sale.order.log (evento por cambio de MRR: alta, baja,
    transferencia, renovación...). Pero esa primera prueba tomó solo 10
    órdenes con un search_read SIN 'order' explícito — Odoo las trajo en su
    orden por defecto (probablemente las más recientes), no una muestra
    representativa. Por eso todo salió de julio 2026 para acá: pudo ser
    sesgo de muestra, no el límite real del historial.

    Esta función no muestrea: pregunta por TODA tu cartera de una vez,
    filtrando por relación (order_id.user_id, order_id.is_subscription) en
    vez de bajar IDs primero. Solo trae agregados — cuántas filas hay, desde
    cuándo, y qué tipos de evento existen — nunca filas individuales completas
    (para eso ya sirvió explorar_historial_mrr()).
    """
    uid, consultar = conectar()

    filas = consultar(
        "sale.order.log", "search_read",
        [[("order_id.user_id", "=", uid), ("order_id.is_subscription", "=", True)]],
        {"fields": ["order_id", "event_date", "effective_date", "event_type",
                    "amount_signed", "recurring_monthly"]},
    )

    print("Filas totales en sale.order.log para tu cartera: %d" % len(filas))
    if not filas:
        print("Cero filas — el modelo existe pero no tiene nada para tus órdenes.")
        return

    def _id_de(valor):
        return valor[0] if isinstance(valor, (list, tuple)) else valor

    ordenes_con_log = {_id_de(f["order_id"]) for f in filas if f.get("order_id")}
    print("Órdenes distintas con al menos 1 evento: %d" % len(ordenes_con_log))

    fechas_evento = sorted(f["event_date"] for f in filas if f.get("event_date"))
    fechas_efectiva = sorted(f["effective_date"] for f in filas if f.get("effective_date"))
    if fechas_evento:
        print("\nevent_date      : de %s a %s" % (fechas_evento[0], fechas_evento[-1]))
    if fechas_efectiva:
        print("effective_date  : de %s a %s" % (fechas_efectiva[0], fechas_efectiva[-1]))

    import collections
    tipos = collections.Counter(f.get("event_type") for f in filas)
    print("\nDistribución por event_type (todos los tipos que existen, no solo los vistos antes):")
    for tipo, n in tipos.most_common():
        print("   %-20s %d" % (tipo, n))

    montos = [f["amount_signed"] for f in filas if f.get("amount_signed") is not None]
    if montos:
        print("\namount_signed: %d filas con monto, suma neta = %.2f" % (len(montos), sum(montos)))

    print("\n" + "=" * 72)
    print("Si event_date se va meses/años atrás de hoy para varias cuentas: hay")
    print("historial real y profundo, no hace falta el cron de Antigravity.")
    print("Si casi todo se agrupa en los últimos 1-2 meses pase lo que pase con la")
    print("cuenta: el modelo probablemente empezó a llenarse hace poco (feature")
    print("activada recientemente), y ahí sí conviene un ping propio hacia adelante.")
    print("=" * 72)


CAMPOS_RELACIONALES_SIN_RESOLVER = [
    "activity_ids", "database_ids", "invoice_ids", "message_ids",
    "message_partner_ids", "order_line", "order_log_ids", "project_ids",
    "starred_user_ids", "subscription_child_ids", "subscription_tag_ids",
    "subscription_task_ids", "tag_ids", "tasks_ids", "website_message_ids",
    "website_order_line",
]


def reconocer_campos_relacionales():
    """
    Recon de los 16 campos que en el archivo de Antigravity (cartera_93_
    campos_estrategicos.json / 116 campos reales) llegaron como listas de
    IDs sin resolver. Ninguno se purga a ciegas por estar vacío hoy: un
    campo puede verse inútil en la foto y tener historia real colgada del
    modelo al que apunta — pasó con order_log_ids (fill 100%, apuntaba a
    945 eventos reales de 6 años que nadie había leído).

    Corre sobre TODA la cartera (activas + churn + lo que sea, sin filtrar
    por state — igual que medir_profundidad_historial_mrr()), no una
    muestra. Por cada campo: a qué modelo apunta, cuántas filas existen en
    total para tu cartera completa, y si ese modelo tiene fechas, desde
    cuándo hasta cuándo. Nunca baja el contenido de las filas — eso es
    decisión aparte, campo por campo, después de ver si vale la pena.
    """
    uid, consultar = conectar()

    ordenes = consultar(
        "sale.order", "search_read",
        [[("user_id", "=", uid), ("is_subscription", "=", True)]],
        {"fields": ["id"], "limit": LIMITE_SEGURIDAD_CUENTAS},
    )
    ids_cartera = [o["id"] for o in ordenes]
    print("Cartera completa (todos los estados): %d órdenes.\n" % len(ids_cartera))
    if len(ids_cartera) >= LIMITE_SEGURIDAD_CUENTAS:
        print("[alerta] se llegó al tope de seguridad (%d) — revisa el filtro "
              "antes de confiar en el recon.\n" % LIMITE_SEGURIDAD_CUENTAS)

    esquema_orden = consultar("sale.order", "fields_get", [],
                              {"attributes": ["string", "type", "relation"]})

    resumen = []

    for campo in CAMPOS_RELACIONALES_SIN_RESOLVER:
        info = esquema_orden.get(campo)
        print("-" * 72)
        if not info:
            print("%-26s no existe en sale.order en esta base." % campo)
            continue

        modelo = info.get("relation")
        print("%-26s -> modelo '%s' (%s)" % (campo, modelo, info.get("string")))
        if not modelo:
            continue

        try:
            esquema_rel = consultar(modelo, "fields_get", [],
                                    {"attributes": ["type", "relation"]})
        except Exception as e:
            print("   no se pudo leer el esquema: %s" % e)
            continue

        # Se busca por TIPO+RELACIÓN, no por nombre de campo — así funciona
        # aunque el campo de vuelta se llame order_id, subscription_id, o
        # cualquier otro nombre, siempre que apunte de verdad a sale.order.
        campo_liga = next(
            (n for n, i in esquema_rel.items()
             if i.get("type") == "many2one" and i.get("relation") == "sale.order"),
            None,
        )
        if not campo_liga:
            print("   sin campo directo de vuelta a sale.order en este modelo.")
            print("   (probablemente catálogo a resolver por nombre —tags— o")
            print("   modelo genérico tipo chatter con res_model/res_id: no es")
            print("   historial, es otra clase de dato, se resuelve distinto.)")
            continue

        total = consultar(modelo, "search_count", [[(campo_liga, "in", ids_cartera)]])
        print("   %d filas totales para tu cartera (liga: %s)" % (total, campo_liga))
        resumen.append((campo, modelo, total))
        if not total:
            continue

        campos_fecha = sorted(n for n, i in esquema_rel.items()
                              if i.get("type") in ("date", "datetime"))
        if not campos_fecha:
            print("   sin campos de fecha en este modelo — no es serie temporal.")
            continue

        filas = consultar(
            modelo, "search_read",
            [[(campo_liga, "in", ids_cartera)]],
            {"fields": campos_fecha},
        )
        for cf in campos_fecha:
            valores = sorted(f[cf] for f in filas if f.get(cf))
            if valores:
                print("   %-18s de %s a %s" % (cf, valores[0], valores[-1]))

    print("\n" + "=" * 72)
    print("RESUMEN (campo -> modelo -> filas totales):")
    for campo, modelo, total in resumen:
        print("   %-26s %-28s %d" % (campo, modelo, total))
    print("\nCon esto: qué campos SÍ tienen historial real detrás (vale la pena")
    print("pelearlos), cuáles no ligan directo (catálogo/chatter, se resuelven")
    print("distinto) y cuáles de plano no traen nada (esos sí se purgan sin culpa).")
    print("=" * 72)


def resolver_tags():
    """
    tag_ids / subscription_tag_ids llegan como números (IDs), no como texto.
    Esto los traduce a nombre real para toda la cartera, sin tocar historial.
    """
    import collections

    uid, consultar = conectar()

    ordenes = consultar(
        "sale.order", "search_read",
        [[("user_id", "=", uid), ("is_subscription", "=", True)]],
        {"fields": ["id", "partner_id", "tag_ids", "subscription_tag_ids"],
         "limit": LIMITE_SEGURIDAD_CUENTAS},
    )
    print("Documentos (sale.order, todas las versiones): %d" % len(ordenes))

    # Agrupar por CLIENTE real (partner_id), no por documento — un mismo
    # cliente puede tener varias órdenes (renovaciones, cotizaciones viejas,
    # canceladas) y no se cuenta más de una vez por tag.
    clientes = {}
    for o in ordenes:
        pid = o["partner_id"][0] if o.get("partner_id") else o["id"]
        c = clientes.setdefault(pid, {"tag_ids": set(), "subscription_tag_ids": set()})
        c["tag_ids"].update(o.get("tag_ids") or [])
        c["subscription_tag_ids"].update(o.get("subscription_tag_ids") or [])
    print("Clientes únicos (partner_id): %d\n" % len(clientes))

    for campo, modelo in (("tag_ids", "crm.tag"), ("subscription_tag_ids",
                          "openerp.enterprise.subscription.tag")):
        todos_ids = sorted({i for c in clientes.values() for i in c[campo]})
        if not todos_ids:
            print("%s: ningún cliente trae nada." % campo)
            continue
        nombres = {t["id"]: t["name"] for t in consultar(modelo, "read", [todos_ids], {"fields": ["name"]})}

        conteo = collections.Counter(
            nombres.get(i, "?(%d)" % i) for c in clientes.values() for i in c[campo]
        )
        print("=== %s (%s) — distribución por CLIENTE ===" % (campo, modelo))
        for nombre, n in conteo.most_common():
            print("   %-30s %d clientes" % (nombre, n))
        sin_tag = sum(1 for c in clientes.values() if not c[campo])
        print("   %-30s %d clientes\n" % ("(sin ninguno)", sin_tag))


def confirmar_last_cnx_date():
    """
    ¿'last_cnx_date' es la última vez que un HUMANO entró a sesión, o solo
    el último latido técnico del servidor (como first_ping/last_ping)?
    No se adivina por el nombre — se pide el texto de ayuda real del campo,
    y se cruza contra una cuenta con actividad reciente conocida (el evento
    más nuevo de sale.order.log) para ver si se mueven juntos.
    """
    uid, consultar = conectar()

    print("=== Texto de ayuda real de cada campo de fecha en openerp.enterprise.database ===")
    esquema = consultar("openerp.enterprise.database", "fields_get",
                        [["first_ping", "last_ping", "last_cnx_date", "create_date"]],
                        {"attributes": ["string", "help"]})
    for campo, info in esquema.items():
        print("   %-16s %s" % (campo, info.get("string")))
        print("      help: %s" % (info.get("help") or "(sin texto de ayuda)"))

    print("\n=== Cruce contra tu evento de MRR más reciente ===")
    evento_reciente = consultar(
        "sale.order.log", "search_read",
        [[("order_id.user_id", "=", uid), ("order_id.is_subscription", "=", True)]],
        {"fields": ["order_id", "event_date", "event_type"], "order": "event_date desc", "limit": 1},
    )
    if not evento_reciente:
        print("   No encontré ningún evento para cruzar.")
        return
    ev = evento_reciente[0]
    oid = ev["order_id"][0] if isinstance(ev["order_id"], (list, tuple)) else ev["order_id"]
    print("   Evento más reciente: orden %s, %s el %s" % (oid, ev["event_type"], ev["event_date"]))

    db = consultar(
        "openerp.enterprise.database", "search_read",
        [[("subscription_id", "=", oid)]],
        {"fields": ["first_ping", "last_ping", "last_cnx_date"]},
    )
    if not db:
        print("   Esa orden no tiene fila en openerp.enterprise.database — no se puede cruzar.")
        return
    print("   Esa misma orden en openerp.enterprise.database:", db[0])
    print("\n   Si last_cnx_date/last_ping están cerca de %s: se mueven con actividad real." % ev["event_date"])
    print("   Si están muy lejos o congelados: es solo el latido del servidor, no uso real.")


def elegir_ejemplos_fechas_tasks():
    """
    Elige 2-3 ejemplos reales con los tres campos de fecha de QuickStart
    llenos (x_qs_start_date, x_date_production, x_date_support), para que
    Luis los busque por id en su Odoo y confirme si cuadran con lo que
    recuerda de esa implementación. Solo se muestra el id interno de la
    orden — ni nombre, ni referencia de cliente, nada más que un número.
    """
    uid, consultar = conectar()

    ordenes = consultar(
        "sale.order", "search_read",
        [[("user_id", "=", uid), ("is_subscription", "=", True)]],
        {"fields": ["id"], "limit": LIMITE_SEGURIDAD_CUENTAS},
    )
    ids_cartera = [o["id"] for o in ordenes]

    tasks = consultar(
        "project.task", "search_read",
        [[("sale_order_id", "in", ids_cartera)]],
        {"fields": ["sale_order_id", "x_qs_start_date", "x_date_production", "x_date_support"]},
    )

    completos = [t for t in tasks
                 if t.get("x_qs_start_date") and t.get("x_date_production") and t.get("x_date_support")]
    print("Tasks con los 3 campos llenos: %d de %d totales.\n" % (len(completos), len(tasks)))

    if not completos:
        print("Ninguna tiene los 3 a la vez — bajo el criterio a 2 de 3 llenos.")
        completos = [t for t in tasks if sum(bool(t.get(c)) for c in
                     ("x_qs_start_date", "x_date_production", "x_date_support")) >= 2]
        print("Con ese criterio: %d.\n" % len(completos))

    for t in completos[:3]:
        oid = t["sale_order_id"][0] if isinstance(t["sale_order_id"], (list, tuple)) else t["sale_order_id"]
        print("Orden id=%s" % oid)
        print("   x_qs_start_date   (¿kickoff?)                %s" % t.get("x_qs_start_date"))
        print("   x_date_production (¿salió a producción?)     %s" % t.get("x_date_production"))
        print("   x_date_support    (¿pasó de implementación a soporte/CS?)  %s" % t.get("x_date_support"))
        print()

    print("Búscalos por id en Odoo y dime si esas fechas cuadran con lo que recuerdas.")


def medir_dias_sin_ping_antes_de_churn():
    """
    ¿'last_cnx_date' avisa con tiempo o solo confirma el churn ya ocurrido?
    Un solo ejemplo (5 días) no prueba nada — se mide contra los 39 churns
    reales completos.

    Cuenta churneada = ya no recibe pings nuevos, así que last_cnx_date de
    HOY ya es la foto congelada del momento real en que se apagó. No hace
    falta ningún histórico propio para esta prueba.

    Gap chico (días) en la mayoría: el campo confirma el churn, no avisa.
    Gap grande (semanas/meses): ahí sí hay ventana real de alerta temprana
    — y ese mismo gap, aplicado HOY a cuentas activas, dice cuáles ya están
    en silencio sin que nadie se haya dado cuenta.
    """
    import datetime

    uid, consultar = conectar()

    def _id_de(v):
        return v[0] if isinstance(v, (list, tuple)) else v

    churns = consultar(
        "sale.order.log", "search_read",
        [[("order_id.user_id", "=", uid), ("order_id.is_subscription", "=", True),
          ("event_type", "=", "2_churn")]],
        {"fields": ["order_id", "event_date"]},
    )
    print("Eventos de churn encontrados: %d" % len(churns))

    ids_churn = [_id_de(c["order_id"]) for c in churns]
    dbs = consultar(
        "openerp.enterprise.database", "search_read",
        [[("subscription_id", "in", ids_churn)]],
        {"fields": ["subscription_id", "last_cnx_date"]},
    )
    ultima_conexion = {_id_de(d["subscription_id"]): d["last_cnx_date"]
                       for d in dbs if d.get("last_cnx_date")}

    gaps = []
    sin_dato = 0
    for c in churns:
        oid = _id_de(c["order_id"])
        lcd = ultima_conexion.get(oid)
        if not lcd:
            sin_dato += 1
            continue
        fecha_churn = datetime.date.fromisoformat(c["event_date"])
        fecha_conexion = datetime.date.fromisoformat(lcd[:10])
        gaps.append((fecha_churn - fecha_conexion).days)

    print("Con dato de last_cnx_date: %d de %d (%d sin fila en openerp.enterprise.database)\n"
          % (len(gaps), len(churns), sin_dato))

    if not gaps:
        print("Sin datos suficientes para medir nada.")
        return

    gaps.sort()
    n = len(gaps)
    print("Gap real (días entre última conexión y churn registrado), los %d casos:" % n)
    print("   mínimo:  %d días" % gaps[0])
    print("   mediana: %d días" % gaps[n // 2])
    print("   máximo:  %d días" % gaps[-1])
    print("   todos: %s" % gaps)
    print("\nSi la mediana es de pocos días: el campo confirma, no avisa.")
    print("Si la mediana es de semanas/meses: ahí hay ventana real de alerta temprana.")


def candidatos_upsell():
    """
    El objetivo real del proyecto: no el churn, el upsell (471 eventos de
    expansión reales en 6 años, contra 39 de churn — ahí está el material).

    Candidato = cuenta ACTIVA que ya demostró que crece (tiene expansiones
    en su historial), lleva tiempo sin volver a expandir, y sigue sana
    (last_cnx_date reciente, no en silencio). Eso es un cliente probado,
    maduro para la siguiente conversación — no un nombre al azar.

    Solo ids, nunca nombres. Ordenado por más tiempo sin expandir primero.
    """
    import datetime
    uid, consultar = conectar()

    def _id_de(v):
        return v[0] if isinstance(v, (list, tuple)) else v

    hoy = datetime.date.today()

    ordenes = consultar(
        "sale.order", "search_read",
        [[("user_id", "=", uid), ("is_subscription", "=", True), ("state", "=", "sale")]],
        {"fields": ["id", "subscription_state", "recurring_monthly"],
         "limit": LIMITE_SEGURIDAD_CUENTAS},
    )
    activas = {o["id"]: o for o in ordenes if o.get("subscription_state") != "6_churn"}
    print("Cuentas activas: %d\n" % len(activas))

    expansiones = consultar(
        "sale.order.log", "search_read",
        [[("order_id.user_id", "=", uid), ("event_type", "=", "1_expansion")]],
        {"fields": ["order_id", "event_date"], "order": "event_date asc"},
    )
    por_orden = {}
    for e in expansiones:
        oid = _id_de(e["order_id"])
        por_orden.setdefault(oid, []).append(e["event_date"])

    dbs = consultar(
        "openerp.enterprise.database", "search_read",
        [[("subscription_id", "in", list(activas.keys()))]],
        {"fields": ["subscription_id", "last_cnx_date"]},
    )
    ultima_conexion = {_id_de(d["subscription_id"]): d["last_cnx_date"]
                       for d in dbs if d.get("last_cnx_date")}

    candidatos = []
    for oid, orden in activas.items():
        fechas_exp = por_orden.get(oid)
        if not fechas_exp:
            continue  # nunca ha expandido, no es este tipo de candidato

        dias_sin_expandir = (hoy - datetime.date.fromisoformat(fechas_exp[-1])).days

        lcd = ultima_conexion.get(oid)
        dias_sin_ping = (hoy - datetime.date.fromisoformat(lcd[:10])).days if lcd else None

        candidatos.append({
            "id": oid,
            "mrr_actual": orden.get("recurring_monthly") or 0.0,
            "expansiones_previas": len(fechas_exp),
            "dias_sin_expandir": dias_sin_expandir,
            "dias_sin_ping": dias_sin_ping,
        })

    # Sano = o no tenemos dato (no penalizar por falta de info) o <30 días,
    # el umbral real que medimos contra los 39 churns.
    sanos = [c for c in candidatos if c["dias_sin_ping"] is None or c["dias_sin_ping"] < 30]
    sanos.sort(key=lambda c: -c["dias_sin_expandir"])

    print("Cuentas con historial de expansión: %d" % len(candidatos))
    print("De esas, sanas (sin silencio de +30 días): %d\n" % len(sanos))

    print("Top 15 — más tiempo sin volver a expandir, siendo cuenta sana:")
    print("%-10s %10s %8s %16s %12s" % ("id", "mrr", "#exp", "días sin expandir", "días sin ping"))
    for c in sanos[:15]:
        print("%-10s %10.2f %8d %16d %12s" % (
            c["id"], c["mrr_actual"], c["expansiones_previas"],
            c["dias_sin_expandir"], c["dias_sin_ping"] if c["dias_sin_ping"] is not None else "sin dato"))


def explorar():
    """
    Descubre a qué tienes acceso. Esto es el primer paso real del proyecto:
    hasta no correr esto, cualquier mapeo de campos es una suposición.
    """
    uid, consultar = conectar()
    print("Conectado a Odoo. Tu uid es %s.\n" % uid)

    disponibles = []
    for modelo, descripcion in MODELOS_CANDIDATOS:
        try:
            cuantos = consultar(modelo, "search_count", [[]])
            print("  [OK]    %-22s %-38s %s registros visibles" % (
                modelo, descripcion, "{:,}".format(cuantos)))
            disponibles.append(modelo)
        except Exception as e:
            crudo = str(e).strip().replace("\n", " ")
            if "does not exist" in crudo.lower():
                categoria = "no existe en esta versión"
            elif any(p in crudo.lower() for p in ("access", "permission", "denied")):
                categoria = "acceso denegado en esta consulta"
            else:
                categoria = "error"
            print("  [--]    %-22s %-38s %s" % (modelo, descripcion, categoria))
            print("           -> %s" % crudo[:200])  # el texto real de Odoo, sin resumir

    for modelo in disponibles:
        print("\n" + "-" * 72)
        print("Campos relevantes de %s (filtrados por palabra clave):" % modelo)
        print("-" * 72)
        campos = consultar(modelo, "fields_get", [],
                           {"attributes": ["string", "type"]})
        relevantes = sorted(
            n for n in campos
            if any(clave in n.lower() or clave in campos[n].get("string", "").lower()
                   for clave in PALABRAS_CLAVE_CAMPOS)
        )
        for nombre in relevantes:
            print("  %-34s %-12s %s" % (
                nombre, campos[nombre].get("type", ""), campos[nombre].get("string", "")))
        print("\n  (%d de %d campos totales — el resto son de UI/metadata, sin uso aquí)"
              % (len(relevantes), len(campos)))

    print("\n" + "=" * 72)
    print("SIGUIENTE PASO: pásame esta salida y mapeo obtener_cartera() a los")
    print("campos que de verdad existen en tu base, en vez de adivinarlos.")
    print("=" * 72)

    return disponibles


def obtener_cartera():
    """
    Extracción real, mapeada con campos confirmados el 18-ago-2026 (ver
    fuente_odoo.py::explorar) — nada adivinado.

    EL FILTRO DE ALCANCE (línea siguiente a "uid, consultar = conectar()")
    es la barda de contención: sin importar qué tan amplios sean los permisos
    reales de la API key (confirmado: ve res.partner/sale.order/etc. de las
    TRES compañías, ~20-50 millones de registros globales), esta función
    NUNCA pide nada sin filtrar primero por user_id = tu propio uid, obtenido
    en cada corrida — nunca un número quemado en el código.

    Devuelve la MISMA FORMA de diccionario que fuente_demo.obtener_cartera(),
    con dos excepciones honestas:
      - No hay "uso_diario" (curva de 90 días) porque no existe con ese grano
        en ningún modelo al que tengas acceso. En su lugar: "historial_activacion",
        la lista real de pings semanales de openerp.enterprise.database
        (fecha, usuarios activos, usuarios comprados). Menos denso que lo
        sintético, pero real — nunca se rellena ni se inventa un punto.
      - "mrr_hace_60d" no se calcula a mano: se usa kpi_1month_mrr_percentage
        y kpi_3months_mrr_percentage, que Odoo YA calcula internamente (los
        mismos números que usa Finanzas) — más confiable que reinventarlos.
    """
    uid, consultar = conectar()

    # --- LA BARDA DE CONTENCIÓN: nunca se quita este filtro ---
    # state="sale" evita traer la cotización de renovación Y el contrato padre
    # como si fueran dos cuentas (pasa en Genera Factoring del volcado real:
    # state="draft" + subscription_state="2_renewal" = cotización, no contrato).
    dominio_ordenes = [
        ("user_id", "=", uid),
        ("is_subscription", "=", True),
        ("state", "=", "sale"),
    ]

    ordenes = consultar(
        "sale.order", "search_read", [dominio_ordenes],
        {"limit": LIMITE_SEGURIDAD_CUENTAS,
         "fields": [
            "id", "partner_id", "recurring_monthly", "contract_value",
            "kpi_1month_mrr_percentage", "kpi_3months_mrr_percentage",
            "subscription_state", "to_renew", "is_renewing",
            "plan_id", "plan_billing_period_unit", "enterprise_users",
            "hosting", "version",
            # next_invoice_date, NO validity_date: comprobado en el volcado que
            # validity_date es la expiración de la COTIZACIÓN (JJ la tiene en el
            # pasado y está activa hasta 2027). next_invoice_date es la buena.
            "next_invoice_date", "first_contract_date", "last_invoice_date",
            "is_upselling", "upsell_count", "close_reason_id",
            "payment_exception", "pending_transaction", "payment_token_id",
            # Success pack / consultoría
            "project_count", "tasks_count", "timesheet_total_duration",
            "completed_task_percentage", "milestone_count",
            # Contexto de relación (conteos, nunca contenido)
            "message_ids", "history_count", "invoice_count",
            "tag_ids", "subscription_tag_ids",
            # internal_note SOLO para saber si la cuenta está calificada y qué
            # tan extensa es la nota. El TEXTO nunca sale de esta función.
            "internal_note_display",
        ]},
    )

    if not ordenes:
        return []

    if len(ordenes) >= LIMITE_SEGURIDAD_CUENTAS:
        print("  [alerta] Se llegó al tope de seguridad (%d cuentas). "
              "Esto es más de lo esperado para tu cartera — revisa el "
              "filtro antes de confiar en estos datos." % LIMITE_SEGURIDAD_CUENTAS)

    ids_ordenes = [o["id"] for o in ordenes]

    # Historial de pings SOLO de las cuentas ya filtradas arriba — nunca una
    # consulta abierta sobre openerp.enterprise.database (que por sí solo
    # tiene ~50 millones de filas globales).
    pings = consultar(
        "openerp.enterprise.database", "search_read",
        [[("subscription_id", "in", ids_ordenes)]],
        {"fields": ["subscription_id", "nbr_active_regular_users", "quantity",
                    "last_cnx_date", "create_date"],
         "order": "create_date asc"},
    )

    historial_por_orden = {}
    for p in pings:
        if not p["subscription_id"]:
            continue
        oid = p["subscription_id"][0]
        historial_por_orden.setdefault(oid, []).append({
            "fecha": p["create_date"],
            "activos": p["nbr_active_regular_users"] or 0,
            "comprados": p["quantity"] or 0,
        })

    # --- Resolver tags a nombres legibles ---
    # No adivino el modelo de los tags: se lo pregunto al esquema con
    # fields_get(attributes=["relation"]). Así funciona aunque Odoo lo renombre.
    nombres_tag = {}
    try:
        esquema = consultar("sale.order", "fields_get", [],
                            {"attributes": ["relation"]})
        for campo in ("tag_ids", "subscription_tag_ids"):
            modelo_tag = esquema.get(campo, {}).get("relation")
            ids = sorted({i for o in ordenes for i in (o.get(campo) or [])})
            if modelo_tag and ids:
                for t in consultar(modelo_tag, "read", [ids], {"fields": ["name"]}):
                    nombres_tag[(campo, t["id"])] = t["name"]
    except Exception as e:
        print("  [aviso] no se pudieron resolver los tags: %s" % e)

    def tags_de(orden, campo):
        return [nombres_tag.get((campo, i)) for i in (orden.get(campo) or [])
                if nombres_tag.get((campo, i))]

    # --- Construir un registro POR ORDEN primero (no es la cuenta final) ---
    # Un mismo cliente puede tener más de una sale.order activa a la vez: su
    # plan principal y, aparte, una propuesta de paquete de horas ya confirmada
    # (state="sale") — confirmado por Luis el 18-ago-2026 con su cartera real.
    # Contar cada orden como si fuera una cuenta distinta infla el número Y
    # puede generarle dos diagnósticos separados a la misma relación. Por eso
    # esto se agrupa por cliente (partner_id) más abajo, antes de convertirse
    # en "cartera".
    por_orden = []
    for o in ordenes:
        historial = historial_por_orden.get(o["id"], [])
        ultimo_ping = historial[-1] if historial else None

        # La calificación: solo su EXISTENCIA y tamaño, jamás el texto.
        # El contenido lleva nombres de personas y no tiene fecha por dato
        # (comprobado: la nota de Raymisa afirma un upsell "inminente" que
        # lleva 5 meses muerto). Se mide, no se lee.
        nota = o.get("internal_note_display") or ""
        texto_nota = re.sub(r"<[^>]+>", " ", nota).strip()
        es_mensual = o.get("plan_billing_period_unit") == "month"
        por_orden.append({
            "_partner_id": o["partner_id"][0] if o["partner_id"] else None,
            "nombre": o["partner_id"][1] if o["partner_id"] else "Sin nombre",
            "plan": o["plan_id"][1] if o["plan_id"] else "Sin plan",
            "mrr_actual": o["recurring_monthly"] or 0.0,
            "mrr_tendencia_1m_pct": o["kpi_1month_mrr_percentage"] or 0.0,
            "mrr_tendencia_3m_pct": o["kpi_3months_mrr_percentage"] or 0.0,
            "subscription_state": o["subscription_state"] or "",
            "to_renew": bool(o["to_renew"]),
            "is_renewing": bool(o["is_renewing"]),
            "next_invoice_date": o.get("next_invoice_date") or None,
            "first_contract_date": o.get("first_contract_date") or None,
            "usuarios_comprados": ultimo_ping["comprados"] if ultimo_ping else (o["enterprise_users"] or 0),
            "usuarios_activos": ultimo_ping["activos"] if ultimo_ping else 0,
            "ultimo_ping": ultimo_ping["fecha"] if ultimo_ping else None,
            "historial_activacion": historial,

            "hosting": o.get("hosting") or None,
            "es_mensual": es_mensual,
            "version_odoo": o.get("version") or None,
            "contract_value": o.get("contract_value") or 0.0,

            "is_upselling": bool(o.get("is_upselling")),
            "upsell_count": o.get("upsell_count") or 0,
            "motivo_cierre": o["close_reason_id"][1] if o.get("close_reason_id") else None,

            # Cobro: solo tiene sentido en mensuales. En anuales/multianuales la
            # renovación es manual por diseño (el CSTD manda la cotización), así
            # que la ausencia de token es lo NORMAL, no una señal de nada.
            "pago_en_excepcion": bool(o.get("payment_exception")) and es_mensual,
            "transaccion_pendiente": bool(o.get("pending_transaction")) and es_mensual,
            "tiene_token_pago": bool(o.get("payment_token_id")) if es_mensual else None,

            # Success pack / consultoría
            "proyectos": o.get("project_count") or 0,
            "tareas": o.get("tasks_count") or 0,
            "horas_registradas": o.get("timesheet_total_duration") or 0,
            "pct_tareas_completadas": o.get("completed_task_percentage") or 0.0,
            "milestones": o.get("milestone_count") or 0,

            # Relación: conteos, nunca contenido
            "mensajes_chatter": len(o.get("message_ids") or []),
            "renovaciones_historicas": o.get("history_count") or 0,
            "facturas_emitidas": o.get("invoice_count") or 0,

            # Calificación: existencia y tamaño, nunca el texto
            "esta_calificada": len(texto_nota) > 200,
            "largo_calificacion": len(texto_nota),

            "tags": tags_de(o, "tag_ids") + tags_de(o, "subscription_tag_ids"),
        })

    # --- Agrupar por cliente real y fusionar ---
    grupos = {}
    for c in por_orden:
        clave = c["_partner_id"] if c["_partner_id"] is not None else c["nombre"]
        grupos.setdefault(clave, []).append(c)

    con_varias = sum(1 for g in grupos.values() if len(g) > 1)
    print("  %d sale.order -> %d clientes distintos (partner_id)" % (len(ordenes), len(grupos)))
    if con_varias:
        print("  %d clientes tienen más de 1 orden activa — se fusionaron en una sola cuenta" % con_varias)

    return [_fusionar_ordenes_de_cliente(grupo) for grupo in grupos.values()]


def _fusionar_ordenes_de_cliente(ordenes_cliente):
    """
    Recibe todas las sale.order activas de UN cliente y devuelve UNA cuenta.
    Con una sola orden, es un passthrough. Con varias, cada campo se fusiona
    con la regla que tiene sentido para ese tipo de dato — nunca un promedio
    ciego donde promediar no significa nada:
      - dinero (MRR, valor de contrato, conteos): se suma.
      - riesgo (pago en excepción, upsell en proceso): basta con que UNA orden
        lo tenga — no se diluye promediando con las que sí están al corriente.
      - fechas de urgencia (próxima renovación): la más próxima manda.
      - antigüedad: la fecha de inicio más antigua.
      - historial de adopción: se combinan los pings de todas sus órdenes.
      - KPIs de Odoo que ya vienen en % (mrr_tendencia_*): no son sumables,
        se toman del contrato con más MRR (el principal), no se promedian.
    """
    partner_id = ordenes_cliente[0]["_partner_id"]
    nombre = ordenes_cliente[0]["nombre"]
    id_cuenta = "CTA-%s" % (partner_id if partner_id is not None else nombre)

    if len(ordenes_cliente) == 1:
        cuenta = dict(ordenes_cliente[0])
        cuenta.pop("_partner_id", None)
        cuenta["id"] = id_cuenta
        cuenta["ordenes_activas"] = 1
        return cuenta

    principal = max(ordenes_cliente, key=lambda o: o["mrr_actual"])
    fechas_renovacion = [o["next_invoice_date"] for o in ordenes_cliente if o["next_invoice_date"]]
    fechas_inicio = [o["first_contract_date"] for o in ordenes_cliente if o["first_contract_date"]]
    historial_fusionado = sorted(
        (p for o in ordenes_cliente for p in o["historial_activacion"]),
        key=lambda p: p["fecha"],
    )
    ultimo_ping = historial_fusionado[-1] if historial_fusionado else None
    algun_mensual = any(o["es_mensual"] for o in ordenes_cliente)
    con_proyecto = [o for o in ordenes_cliente if o["proyectos"]]

    return {
        "id": id_cuenta,
        "nombre": nombre,
        "plan": principal["plan"],
        "ordenes_activas": len(ordenes_cliente),

        "mrr_actual": sum(o["mrr_actual"] for o in ordenes_cliente),
        "mrr_tendencia_1m_pct": principal["mrr_tendencia_1m_pct"],
        "mrr_tendencia_3m_pct": principal["mrr_tendencia_3m_pct"],

        "subscription_state": principal["subscription_state"],
        "to_renew": any(o["to_renew"] for o in ordenes_cliente),
        "is_renewing": any(o["is_renewing"] for o in ordenes_cliente),
        "next_invoice_date": min(fechas_renovacion) if fechas_renovacion else None,
        "first_contract_date": min(fechas_inicio) if fechas_inicio else None,

        "usuarios_comprados": (ultimo_ping["comprados"] if ultimo_ping
                                else sum(o["usuarios_comprados"] for o in ordenes_cliente)),
        "usuarios_activos": (ultimo_ping["activos"] if ultimo_ping
                              else sum(o["usuarios_activos"] for o in ordenes_cliente)),
        "ultimo_ping": ultimo_ping["fecha"] if ultimo_ping else None,
        "historial_activacion": historial_fusionado,

        "hosting": principal["hosting"],
        "es_mensual": algun_mensual,
        "version_odoo": principal["version_odoo"],
        "contract_value": sum(o["contract_value"] for o in ordenes_cliente),

        "is_upselling": any(o["is_upselling"] for o in ordenes_cliente),
        "upsell_count": sum(o["upsell_count"] for o in ordenes_cliente),
        "motivo_cierre": principal["motivo_cierre"],

        "pago_en_excepcion": any(o["pago_en_excepcion"] for o in ordenes_cliente),
        "transaccion_pendiente": any(o["transaccion_pendiente"] for o in ordenes_cliente),
        "tiene_token_pago": (any(o["tiene_token_pago"] for o in ordenes_cliente)
                              if algun_mensual else None),

        "proyectos": sum(o["proyectos"] for o in ordenes_cliente),
        "tareas": sum(o["tareas"] for o in ordenes_cliente),
        "horas_registradas": sum(o["horas_registradas"] for o in ordenes_cliente),
        "pct_tareas_completadas": (
            sum(o["pct_tareas_completadas"] for o in con_proyecto) / len(con_proyecto)
            if con_proyecto else 0.0
        ),
        "milestones": sum(o["milestones"] for o in ordenes_cliente),

        "mensajes_chatter": sum(o["mensajes_chatter"] for o in ordenes_cliente),
        "renovaciones_historicas": sum(o["renovaciones_historicas"] for o in ordenes_cliente),
        "facturas_emitidas": sum(o["facturas_emitidas"] for o in ordenes_cliente),

        "esta_calificada": any(o["esta_calificada"] for o in ordenes_cliente),
        "largo_calificacion": max(o["largo_calificacion"] for o in ordenes_cliente),

        "tags": sorted({t for o in ordenes_cliente for t in o["tags"]}),
    }


if __name__ == "__main__":
    try:
        explorar()
    except RuntimeError as e:
        print("\n%s" % e)
    except Exception as e:
        print("\nNo se pudo conectar: %s: %s" % (type(e).__name__, e))
