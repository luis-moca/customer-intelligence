"""
FASE 2 — Panel cuenta-mes.

Convierte foto_maestra + eventos_maestros en una tabla donde cada fila es
UNA suscripcion en UN mes, con dos partes separadas por una linea dura:

  - Columnas de features: calculadas SOLO con eventos ocurridos hasta el
    cierre de ese mes. Nunca miran hacia adelante.
  - Columnas de etiqueta: miran los 90 dias SIGUIENTES. Solo se usan para
    entrenar, jamas como entrada del modelo.

Esa separacion es el punto entero de esta fase. La foto de una cuenta muerta
esta contaminada por su propia muerte (enterprise_users: 526/526 churneadas en
cero contra 1461/1461 activas con usuarios). Entrenar con eso produce un modelo
que reconoce cadaveres, no que predice muertes.

REGLAS FIJAS (decisiones ya tomadas, no se re-discuten aqui):
 - La antiguedad sale de first_contract_date de la foto, NUNCA del primer
   evento del log (el log esta cortado a 2023-08-23; una cuenta de 2016
   pareceria de 3 años).
 - De la foto solo entran atributos que NO cambian con el tiempo (pais,
   industria, plan, hosting, canal). Todo contador o estado actual queda
   fuera por definicion: son fotos del presente, no del mes que se modela.
 - Una suscripcion deja de generar filas el mes en que churnea.
 - Los ultimos 3 meses del panel no tienen etiqueta (su futuro aun no ocurre).
   Se marcan como 'para_puntuar' — sirven para predecir hoy, no para entrenar.
"""
import collections
import datetime
import json
import os

from rutas import MAESTRO as CARPETA_MAESTRO
# Horizontes por desenlace (decision de Luis, 22-ago-2026, tras validar sus 18
# cuentas en el frontend): churn mira 120 dias — las renovaciones de diciembre
# quedaban fuera con 90. Expansion y contraccion se quedan en 90 PARA ENTRENAR
# (con 3 años de historia no se puede entrenar una etiqueta mas larga); el
# "hasta 4 años" de expansion vive en puntuar.py como regla de elegibilidad,
# no aqui.
# Cual es "HOY" para el panel. None = el ultimo evento que exista en los datos
# (lo correcto para el maestro). Quien construya el panel de UNA cartera suelta
# debe ponerle la fecha del export — ver el comentario largo en main().
FIN_FORZADO = None

# Desde cuando corre la ventana del log de eventos. Se usa SOLO para
# historia_truncada ("¿el cliente es mas viejo que la ventana?"). None = el
# primer evento que exista en los datos — correcto para el maestro (9 carteras
# juntas: siempre hay un evento pegado al inicio de la ventana real), pero
# MENTIRA para una cartera sola: si el evento mas viejo de esa persona es de
# sep-2023, un cliente de ago-2023 saldria "truncado" en Python y "no truncado"
# en el dashboard (que si recibe la ventana real en el export). Mismo tipo de
# bug que FIN_FORZADO, encontrado el mismo dia comparando las 9 carteras.
INICIO_FORZADO = None

HORIZONTE_CHURN = 120
HORIZONTE_MRR = 90

# --- Que entra como atributo estatico y que no ---
# Regla del proyecto: Claude no elige a ojo. Se define por EXCLUSION explicita
# y documentada; todo lo demas entra y que la matematica (L1 + backtest) decida.

# Aprobados por Luis para eliminar (22-ago-2026): sin señal en ninguno de los
# 3 desenlaces, o muertos por sus propios datos (vacios/constantes).
ELIMINADOS_APROBADOS = {
    "commission_plan_id", "my_activity_date_deadline", "locked",
    "rating_avg_text", "rating_percentage_satisfaction",
    "percentage_satisfaction", "team_currency_id", "team_id", "team_user_id",
    "pending_transaction", "client_order_ref", "display_name", "note_order",
    "partner_invoice_id", "partner_shipping_id", "country_code",
    "currency_rate", "currency_id", "company_id", "pricelist_id",
    "prepayment_percent", "is_closing", "validity_date", "transition_date",
}

# Fuga medida: se apagan/encienden CUANDO la cuenta muere. Separacion perfecta
# contra churn (ver medir_132.py). Podrian servir al puntuar cuentas vivas,
# jamas para entrenar.
#
# Revision 22-ago-2026 (medir_fuga_por_desenlace.py + medir_artefacto_temporal.py):
# se reviso uno por uno si la fuga era contra los TRES desenlaces o solo contra
# churn, porque excluirlos en bloque tiraba informacion de mas.
#  - Contra expansion y contraccion los 10 salieron limpios (sin separacion).
#  - PERO la segunda prueba mostro que 9 de 10 son valores de HOY: se apagan al
#    morir la cuenta (100% vacios en TODAS las cohortes de churn 2023-2026 vs
#    ~82% en activas). Que un campo solo este lleno en cuentas vivas es fuga
#    aunque la prueba de separacion no la marque: el umbral de cobertura del
#    20% la dejaba pasar por un pelo.
#  - payment_term_id fue el unico estable de verdad (63.9%-80.2% entre cohortes
#    de muerte, 67.0% en activas). Ese si entrena, y en los tres desenlaces.
FUGA_CONFIRMADA = {
    "subscription_state", "close_reason_id", "enterprise_users",
    "enterprise_is_enterprise", "enterprise_has_download",
    "maintenance_is_activated", "maintenance_is_paying", "activity_user_id",
    "end_date",
}

# Identifican, no predicen. message_ids sale de aqui: se usa como CONTEO
# (medido: churn de 7.9% a 36.6% por cuartil de cantidad de mensajes).
LLAVES = {
    "id", "name", "partner_id", "commercial_partner_id", "subscription_id",
    "order_log_ids", "opportunity_id", "database_ids", "project_id",
    "invoice_ids", "tasks_ids", "order_line", "origin_order_id",
    "upsell_order_id", "user_id", "subscription_child_ids",
    "subscription_task_ids", "project_ids", "website_order_line",
    "website_message_ids", "message_partner_ids", "activity_ids",
    "starred_user_ids", "tag_ids", "subscription_tag_ids", "database_count",
}

# Texto libre / HTML / binario: no son variables numericas ni categorias.
# internal_note_display salio de aqui: llamarlo "ruido" fue error mio, es la
# calificacion que el CS escribe sobre la cuenta. Se movio a
# NO_ENTRENABLE_SOLO_PUNTUAR, no aqui — ver la nota alla.
TEXTO_O_RUIDO = {
    "internal_note", "note", "recurring_details",
    "activity_summary", "activity_type_icon", "partner_status", "origin",
}

# Fechas crudas: se usan DERIVADAS (antiguedad, dias_hasta_renovacion), nunca
# el valor absoluto — una fecha exacta casi nunca se repite entre cuentas.
FECHAS_CRUDAS = {
    "create_date", "date_order", "start_date", "first_contract_date",
    "next_invoice_date", "expected_next_invoice_date", "last_invoice_date",
    "activity_date_deadline",
}


# NO ENTRENABLES — el valor cambia con el tiempo y solo tenemos el de HOY.
# Pegarle el valor de agosto-2026 a una fila de marzo-2024 es fuga, y es una
# fuga que el backtest temporal NO cacha (contamina tambien las filas de
# prueba, porque tambien reciben el valor de hoy). No se eliminan del
# proyecto: son utiles al PUNTUAR cuentas vivas hoy, jamas para entrenar.
# Misma categoria que enterprise_users.
NO_ENTRENABLE_SOLO_PUNTUAR = {
    # montos que se mueven con cada factura o cambio de contrato
    "amount_invoiced", "amount_paid", "amount_to_invoice", "amount_unpaid",
    "amount_total", "recurring_monthly", "recurring_total", "contract_value",
    "non_recurring_total", "invoice_date_diff",
    # contadores que solo crecen
    "invoice_count", "history_count", "renewal_count", "upsell_count",
    "project_count", "tasks_count", "timesheet_count", "closed_task_count",
    "message_attachment_count", "message_ids", "timesheet_count",
    "completed_task_percentage", "timesheet_total_duration",
    # banderas y estados del momento actual
    "is_upselling", "is_renewing", "to_renew", "invoice_status",
    "activity_state", "activity_type_id", "payment_token_id",
    # cantidad de licencias: cambia con cada upsell/downgrade
    "cart_quantity",
    # infraestructura contratada: cambia al escalar
    "odoo_sh_extra_gb", "odoo_sh_extra_stagings", "odoo_sh_extra_workers",
    "odoo_sh_project_activated",
    # La calificacion de la cuenta que escribe el CS. NO es ruido — pero solo
    # existe en su version de HOY, y el largo de la nota crece con el tiempo.
    # Medido (medir_nota.py): las cuentas que murieron en 2023 tienen mediana
    # 0 caracteres y 88.9% sin nota; las que murieron en 2026, mediana 1,975 y
    # 8.1% sin nota. O sea el largo cuenta EN QUE ANIO murio la cuenta, no que
    # tan bien se trabajo. Comparando parejo (churn 2026 vs activas, mismo
    # tiempo disponible) la diferencia real es chica: 1,975 vs 2,502 de mediana.
    # Sirve para puntuar cuentas vivas hoy; entrenar con ella seria fuga.
    "internal_note_display",
}


def atributos_estaticos():
    from exportar_todo import CAMPOS_SALE_ORDER
    fuera = (ELIMINADOS_APROBADOS | FUGA_CONFIRMADA | LLAVES | TEXTO_O_RUIDO
             | FECHAS_CRUDAS | NO_ENTRENABLE_SOLO_PUNTUAR)
    return sorted(c for c in CAMPOS_SALE_ORDER if c not in fuera)


ATRIBUTOS_ESTATICOS = atributos_estaticos()


def idv(v):
    return v[0] if isinstance(v, list) else v


def nombre_de(v):
    return v[1] if isinstance(v, list) and len(v) > 1 else None


def a_fecha(texto):
    if not texto:
        return None
    try:
        return datetime.date.fromisoformat(str(texto)[:10])
    except ValueError:
        return None


def dias_hasta_renovacion(prox_factura, periodo, cierre):
    """Dias desde 'cierre' hasta la renovacion REAL mas cercana.

    Reemplaza a dias_hasta_aniversario (22-ago-2026). El aniversario del
    PRIMER contrato mentia: Luis valido sus 18 cuentas de RESCATAR en el
    frontend y 6 de 7 falsos positivos venian de ahi — cuentas que acababan
    de renovar (su decision ya estaba tomada) seguian marcadas porque el
    aniversario original caia cerca. La fecha que decide es next_invoice_date.

    Como se evita la fuga de "valor de HOY": no se usa la fecha directa — se
    reconstruye caminando ciclos de 12 meses hacia atras desde next_invoice_date
    hasta encontrar la renovacion inmediatamente posterior al cierre. Misma
    tecnica que MRR historico y licencias_por_fecha.

    Solo aplica a planes anuales/multianuales. En mensuales devuelve None:
    su factura SIEMPRE esta cerca (es rutina, no decision) — su riesgo mayor
    lo aprende el modelo por plan_billing_period_unit=month, no por esta
    columna. Correccion de Luis: las mensuales son MAS riesgosas (renuevan
    decision cada mes), jamas se descuidan — solo no se marcan por "factura
    proxima", que en mensual no informa nada."""
    if periodo != "year" or prox_factura is None:
        return None
    f = prox_factura
    # caminar hacia atras hasta la renovacion inmediatamente despues del cierre
    while True:
        try:
            anterior = f.replace(year=f.year - 1)
        except ValueError:  # 29 de febrero
            anterior = f.replace(year=f.year - 1, day=28)
        if anterior <= cierre:
            break
        f = anterior
    return (f - cierre).days if f > cierre else None


def cargar_uso():
    """Serie historica de uso real por suscripcion, sacada de los pings.

    Cada ping es una foto FECHADA de cuanta gente usaba esa base ese dia. Es la
    unica fuente del proyecto que permite decir "en marzo de 2024 esta cuenta
    tenia 8 usuarios activos" sin inventarlo. Todo lo demas que teniamos de uso
    era el valor de HOY, que no se puede pegar a una fila de 2024.

    Medido antes de meterlo (senal_uso): en los 180 dias previos al churn el
    uso cae mediana -50% y solo sube en 8.6% de los casos; antes de una
    expansion sube +12.5%. Aguanta en las 9 carteras por separado.
    """
    ruta = os.path.join(CARPETA_MAESTRO, "pings_utiles.json")
    if not os.path.exists(ruta):
        return {}
    with open(ruta) as f:
        pings = json.load(f)
    # ORDEN: por la HORA real del ping, y el id como desempate final.
    #
    # Aqui habia un bug (encontrado el 23-ago-2026 al comparar Python contra el
    # dashboard sobre una cartera nueva): se guardaba (fecha, activos, creados)
    # y se hacia sort() a secas. Con DOS pings el mismo dia — 6,527 casos, en
    # 1,545 de 1,922 cuentas — el desempate lo terminaba decidiendo el numero
    # de usuarios activos, o sea "gana el ping con mas gente", que no significa
    # nada. Y como uso_al_cierre() se queda con el ULTIMO, ese orden arbitrario
    # decidia el dato de uso de la fila.
    #
    # ping_time SI trae la hora ('2016-11-16 17:42:50'): el dato para desempatar
    # bien siempre estuvo ahi, se estaba tirando al truncar a fecha. Es la misma
    # disciplina que ya tenian los eventos de MRR ("orden por (fecha, id)").
    #
    # Medido antes de aplicarlo (medir_desempate_pings.py, las 9 carteras
    # completas): cambia de accion 4 de 1,456 cuentas (0.3%).
    #
    # El orden completo es (ping_time, id, activos, creados), y los CUATRO
    # niveles importan: maestro/pings_utiles.json no trae 'id' (adelgazar_pings
    # lo dejo fuera antes de que se supiera que hacia falta), asi que ahi el id
    # sale 0 para todos y el desempate cae a activos/creados. Eso pasa en 28 de
    # 180,692 pings — mismo segundo exacto, uso distinto. Sigue siendo un
    # criterio arbitrario, pero ahora es EXPLICITO y esta escrito igual en los
    # dos motores (Python y el JS del dashboard), que era el problema de fondo:
    # antes cada uno desempataba distinto y nadie lo habia escrito.
    # Los exports nuevos SI traen id, asi que ahi el desempate es el real.
    serie = collections.defaultdict(list)
    for p in pings:
        t = p.get("ping_time")
        if not t:
            continue
        serie[p["_subscription_id"]].append((
            str(t), p.get("id") or 0,
            a_fecha(t),
            p.get("nbr_active_regular_users") or 0,
            p.get("nbr_regular_users") or 0,
        ))
    # Se ordena con la hora y el id, pero se devuelve la misma forma de siempre
    # — (fecha, activos, creados) — para que ni uso_al_cierre() ni
    # pings_al_tope() tengan que enterarse del cambio.
    return {sid: [(f, a, c) for _, _, f, a, c in sorted(v)]
            for sid, v in serie.items()}


def uso_al_cierre(serie_sub, cierre):
    """Ultimo ping en o antes del cierre del mes. Jamas mira hacia adelante."""
    ultimo = None
    for fecha, activos, configurados in serie_sub:
        if fecha > cierre:
            break
        ultimo = (activos, configurados)
    return ultimo


def pings_al_tope(serie_sub, cierre, licencias_por_mes):
    """Cuantos pings SEGUIDOS (los mas recientes) trae la cuenta con todas sus
    licencias contratadas en uso — o sea, ya no le cabe nadie mas.

    Regla de negocio de Luis (22-ago-2026): una cuenta al 100% de usuarios
    activos contra contratados durante 5 pings seguidos ya es candidata a
    expansion; con 6, 8 o mas, sube. No es una regla de accion por si sola —
    entra como variable y el modelo decide cuanto pesa (regla dura del
    proyecto: la matematica elige, no nadie a ojo).

    Se cuenta hacia atras desde el ping mas reciente <= cierre; en cuanto
    aparece un ping por debajo del tope, la racha se corta. Solo mira el
    pasado, como todo lo demas del panel.
    """
    racha = 0
    for fecha, activos, _creados in reversed(serie_sub):
        if fecha > cierre:
            continue
        contratadas = licencias_por_mes
        if not contratadas or activos < contratadas:
            break
        racha += 1
    return racha


def features_de_uso(serie_sub, cierre, licencias):
    """Las columnas de uso de una fila del panel.

    Son TRES niveles distintos, no dos (correccion de Luis, 22-ago-2026):
      1. licencias CONTRATADAS — lo que el cliente paga. Ej: 7
      2. usuarios CREADOS en la base — asientos que existen. Ej: 3
      3. usuarios ACTIVOS — entraron en la semana del ping. Ej: 2

    Las dos brechas significan cosas diferentes y hay que medirlas aparte:
      1-2 = licencias pagadas sin siquiera crear el usuario (desperdicio puro
            de facturacion; el cliente las guarda "para cuando las use")
      2-3 = asientos creados donde nadie entra (problema de adopcion)

    Antes esto estaba mal: se llamaba "uso_ociosos" a la brecha 2-3, que no son
    licencias ociosas. La brecha puede ir en ambos sentidos y en cualquier
    cantidad — hay cuentas con mas usuarios creados que licencias contratadas.

    Los niveles 2 y 3 salen del ping (fechado). El nivel 1 se reconstruye del
    log de eventos, ver licencias_por_fecha().
    """
    hoy = uso_al_cierre(serie_sub, cierre)
    contratadas = licencias
    if hoy is None:
        return {"uso_activos": None, "uso_creados": None,
                "uso_creados_sin_entrar": None, "uso_cambio_180d": None,
                "licencias_contratadas": contratadas,
                "licencias_sin_crear": None}
    activos, creados = hoy
    antes = uso_al_cierre(serie_sub, cierre - datetime.timedelta(days=180))
    cambio = None
    if antes and antes[0] > 0:
        cambio = (activos - antes[0]) / antes[0]
    return {
        "uso_activos": activos,
        "uso_creados": creados,
        "uso_creados_sin_entrar": creados - activos,
        "uso_cambio_180d": cambio,
        "licencias_contratadas": contratadas,
        "licencias_sin_crear": (contratadas - creados) if contratadas is not None else None,
    }


# Los 39 productos que aparecen en las carteras, agrupados por lo que son.
# Sale de maestro/productos.json (leido una vez, no se adivina ningun id).
MODULOS_APP = {323: "Purchase", 326: "Inventory", 329: "Accounting",
               332: "eCommerce", 816: "Invoicing", 817: "CRM", 818: "Sales",
               819: "Website", 837: "Expenses", 854: "TimeOff", 2372: "Studio"}
SUCCESS_PACK = {5694, 5695, 5696, 5697, 5698, 5699, 5700, 5701, 49782}
ODOO_SH = {8003, 8004, 8005, 9470}
PLAN_STANDARD = 45062
PLAN_CUSTOM = 45064
MULTI_YEAR = 68037


def cargar_lineas():
    """Que productos tiene contratada cada cuenta, CON la fecha en que se
    contrato cada uno. La fecha es lo que la hace utilizable: permite decir
    'en marzo de 2024 esta cuenta tenia CRM y Ventas, no tenia Inventario'
    en vez de pegarle a esa fila el catalogo de hoy."""
    ruta = os.path.join(CARPETA_MAESTRO, "order_lines.json")
    if not os.path.exists(ruta):
        return {}
    with open(ruta) as f:
        lineas = json.load(f)
    por_sub = collections.defaultdict(list)
    for l in lineas:
        fecha = a_fecha(l.get("create_date"))
        if fecha is None or l.get("product_id") is None:
            continue
        por_sub[l["_subscription_id"]].append((fecha, l["product_id"]))
    for v in por_sub.values():
        v.sort()
    return por_sub


def features_de_productos(lineas_sub, cierre):
    """Que tenia contratado la cuenta al cierre de ese mes.

    'modulos_faltantes' es la que contesta la pregunta de upsell: de las apps
    que vende Odoo, cuantas NO tiene esta cuenta. Preguntar "¿quien va a
    expandir?" es debil (expande 1 de cada 3); "¿que le falta comprar?" no.
    """
    vigentes = [pid for fecha, pid in lineas_sub if fecha <= cierre]
    if not vigentes:
        return {"num_productos": None, "num_modulos": None,
                "modulos_faltantes": None, "tiene_success_pack": None,
                "tiene_odoo_sh": None, "tiene_multi_year": None,
                "plan_contratado": None}
    conjunto = set(vigentes)
    modulos = len(conjunto & set(MODULOS_APP))
    plan = None
    if PLAN_CUSTOM in conjunto:
        plan = "custom"
    elif PLAN_STANDARD in conjunto:
        plan = "standard"
    return {
        "num_productos": len(vigentes),
        "num_modulos": modulos,
        "modulos_faltantes": len(MODULOS_APP) - modulos,
        "tiene_success_pack": bool(conjunto & SUCCESS_PACK),
        "tiene_odoo_sh": bool(conjunto & ODOO_SH),
        "tiene_multi_year": MULTI_YEAR in conjunto,
        "plan_contratado": plan,
    }


def licencias_por_fecha(licencias_hoy, historia, cierre):
    """Cuantas licencias tenia CONTRATADAS esta cuenta al cierre de ese mes.

    No se puede usar enterprise_users directo: es el valor de HOY. Pero el log
    guarda en new_enterprise_user el CAMBIO de licencias en cada evento, con
    fecha. Entonces se camina hacia atras desde hoy restando lo que paso
    despues del cierre:

        contratadas(T) = contratadas(hoy) - suma de cambios posteriores a T

    Eso quita informacion del futuro, no la agrega — es la misma tecnica con la
    que el panel ya reconstruye el MRR historico.

    Validado (95.6% de las activas): la suma de todos los cambios reproduce
    exacto el valor de hoy. El 4.4% restante son cuentas anteriores a la
    ventana del log (2023-08-23), donde faltan cambios viejos; para esas el
    calculo hacia atras sigue siendo correcto porque parte del presente.
    """
    if licencias_hoy is None:
        return None
    posteriores = sum(e["delta_licencias"] for e in historia if e["fecha"] > cierre)
    v = licencias_hoy - posteriores
    # Una cuenta no puede tener licencias negativas: si sale negativo es que al
    # log le faltan eventos de esa cuenta. Mejor sin dato que con dato falso.
    return v if v >= 0 else None


def fin_de_mes(anio, mes):
    if mes == 12:
        return datetime.date(anio, 12, 31)
    return datetime.date(anio, mes + 1, 1) - datetime.timedelta(days=1)


def meses_entre(desde, hasta):
    """Lista de (anio, mes) desde el mes de 'desde' hasta el de 'hasta'."""
    salida = []
    a, m = desde.year, desde.month
    while (a, m) <= (hasta.year, hasta.month):
        salida.append((a, m))
        m += 1
        if m > 12:
            m = 1
            a += 1
    return salida


def main():
    with open(os.path.join(CARPETA_MAESTRO, "foto_maestra.json")) as f:
        foto = json.load(f)
    with open(os.path.join(CARPETA_MAESTRO, "eventos_maestros.json")) as f:
        eventos = json.load(f)

    print("=== FASE 2 — Panel cuenta-mes ===")
    print("Suscripciones en foto_maestra: %d" % len(foto))
    print("Eventos en eventos_maestros:   %d" % len(eventos))

    serie_uso = cargar_uso()
    lineas_prod = cargar_lineas()
    if lineas_prod:
        print("Lineas de producto (fechadas) para: %d suscripciones" % len(lineas_prod))
    if serie_uso:
        print("Series de uso (pings) para:    %d suscripciones\n" % len(serie_uso))
    else:
        print("SIN pings_utiles.json — el panel saldra sin columnas de uso.\n")

    # --- Agrupar eventos por suscripcion, ordenados en el tiempo ---
    por_suscripcion = collections.defaultdict(list)
    for ev in eventos:
        oid = idv(ev.get("order_id"))
        fecha = a_fecha(ev.get("event_date"))
        if oid is None or fecha is None:
            continue
        por_suscripcion[oid].append({
            "fecha": fecha,
            "id": ev.get("id"),
            "tipo": str(ev.get("event_type")),
            "mrr": ev.get("recurring_monthly") or 0.0,
            "delta_licencias": ev.get("new_enterprise_user") or 0,
            "delta": ev.get("amount_signed") or 0.0,
        })
    # Orden por (fecha, id). El id desempata: 833 suscripciones tienen 2+
    # eventos el MISMO dia (tipico: expansion + transferencia juntas), y
    # ordenar solo por fecha dejaba al azar cual era "el ultimo evento del
    # mes" — y con el, el MRR de esa fila. Con el id el resultado es siempre
    # el mismo, y las pruebas pueden reproducirlo.
    for lista in por_suscripcion.values():
        lista.sort(key=lambda e: (e["fecha"], e["id"]))

    # --- Limites del panel ---
    todas_fechas = [e["fecha"] for lista in por_suscripcion.values() for e in lista]
    panel_inicio, panel_fin = min(todas_fechas), max(todas_fechas)

    # FIN_FORZADO: cual es "HOY" para este panel.
    #
    # Por defecto, "hoy" = el ultimo evento que existe en los datos. Eso es
    # correcto para el maestro (9 carteras: siempre hay movimiento reciente en
    # alguna), pero se rompe al construir el panel de UNA sola cartera: si esa
    # persona lleva 2 dias sin un solo evento, el panel concluye que hoy es
    # antier. Y entonces dias_hasta_renovacion se corre 2 dias, y los eventos
    # de esos 2 dias no entran a las features.
    #
    # El dashboard nunca tuvo ese problema: siempre uso paquete.generado, la
    # fecha en que se creo el export. Ahi estaba la divergencia — no en la
    # formula, sino en QUE DIA cree cada motor que es hoy (encontrada el
    # 23-ago-2026 al comparar las 9 carteras: hasta 0.79 de diferencia en una
    # probabilidad, por 2 dias de desfase).
    #
    # Quien construye el panel de una cartera suelta debe forzar esta fecha al
    # 'generado' del export. El maestro no la toca y se comporta igual que
    # siempre.
    if FIN_FORZADO is not None:
        panel_fin = FIN_FORZADO
    if INICIO_FORZADO is not None:
        panel_inicio = INICIO_FORZADO
    print("Ventana del panel: %s a %s" % (panel_inicio, panel_fin))

    # El corte usa el horizonte MAS LARGO (churn, 120d): una fila solo entrena
    # si TODAS sus etiquetas tienen futuro completo observable. Cuesta ~1 mes
    # de filas de expansion, pero evita filas a medio etiquetar.
    corte_etiqueta = panel_fin - datetime.timedelta(days=HORIZONTE_CHURN)
    print("Con etiqueta hasta: %s (despues de eso, filas solo para puntuar)\n"
          % corte_etiqueta)

    panel = []
    sin_eventos = 0
    churneadas_vistas = 0
    churn_sin_fecha = 0

    for sub in foto:
        sid = sub["id"]
        historia = por_suscripcion.get(sid, [])
        if not historia:
            sin_eventos += 1
            continue

        # Antiguedad SIEMPRE desde la foto, nunca desde el log.
        inicio_cliente = a_fecha(sub.get("first_contract_date"))

        # Mes en que muere, si muere. Despues de eso no se generan filas.
        churn_ev = next((e for e in historia if e["tipo"] == "2_churn"), None)
        fecha_churn = churn_ev["fecha"] if churn_ev else None
        if fecha_churn:
            churneadas_vistas += 1

        # Churneada segun la foto pero sin evento de churn en el log: murio
        # antes de la ventana (2023-08-23). No se puede saber cuando, y
        # tratarla como viva inyectaria filas falsas de "no churneo". Fuera.
        if str(sub.get("subscription_state")) == "6_churn" and not fecha_churn:
            churn_sin_fecha += 1
            continue

        primer_evento = historia[0]["fecha"]
        # Si la cuenta murio, la ultima fila valida es el ultimo cierre de mes
        # ESTRICTAMENTE ANTERIOR al churn. Incluir el mes del churn metia el
        # propio evento de muerte dentro de las features de esa fila: la fila
        # "sabia" que la cuenta ya se habia caido. Eran 488 filas con fuga.
        ultimo_mes = (fecha_churn - datetime.timedelta(days=1)) if fecha_churn else panel_fin

        estaticos = {}
        for campo in ATRIBUTOS_ESTATICOS:
            valor = sub.get(campo)
            if isinstance(valor, list):
                # many2one [id, 'nombre'] -> id ; one2many [1,2,3] -> cantidad
                if len(valor) == 2 and isinstance(valor[0], int) and isinstance(valor[1], str):
                    estaticos[campo] = valor[0]
                else:
                    estaticos[campo] = len(valor)
            else:
                estaticos[campo] = valor

        for (anio, mes) in meses_entre(primer_evento, ultimo_mes):
            # El mes en curso aun no cierra: se corta en panel_fin para que
            # las cuentas nuevas de este mes tambien generen su fila.
            cierre = min(fin_de_mes(anio, mes), panel_fin)
            # Cuenta muerta: nunca pasar del dia previo al churn.
            if fecha_churn and cierre >= fecha_churn:
                break

            # --- FEATURES: solo eventos ocurridos HASTA el cierre del mes ---
            pasados = [e for e in historia if e["fecha"] <= cierre]
            if not pasados:
                continue

            expansiones = [e for e in pasados if e["tipo"] == "1_expansion"]
            contracciones = [e for e in pasados if e["tipo"] == "15_contraction"]
            mrr_hoy = pasados[-1]["mrr"]

            hace_3m = cierre - datetime.timedelta(days=90)
            previos_3m = [e for e in pasados if e["fecha"] <= hace_3m]
            mrr_hace_3m = previos_3m[-1]["mrr"] if previos_3m else None

            hace_12m = cierre - datetime.timedelta(days=365)
            previos_12m = [e for e in pasados if e["fecha"] <= hace_12m]
            mrr_hace_12m = previos_12m[-1]["mrr"] if previos_12m else None

            suma_expansiones = sum(e["delta"] for e in pasados if e["delta"] > 0)
            suma_contracciones = sum(-e["delta"] for e in pasados if e["delta"] < 0)

            ult_exp = expansiones[-1]["fecha"] if expansiones else None
            ult_con = contracciones[-1]["fecha"] if contracciones else None

            fila = {
                "suscripcion_id": sid,
                "cliente_id": idv(sub.get("partner_id")),
                "gram": sub.get("_gram"),
                "anio": anio,
                "mes": mes,
                "cierre_mes": cierre.isoformat(),

                # --- features de comportamiento (pasado puro) ---
                "mrr": mrr_hoy,
                "mrr_hace_3m": mrr_hace_3m,
                "cambio_mrr_3m": (mrr_hoy - mrr_hace_3m) if mrr_hace_3m is not None else None,

                # Trayectoria del MRR con CONTEXTO, no conteo de eventos.
                # Medido (medir_ventanas_mrr.py, AUC sobre las 9 carteras,
                # 17,549 filas): la ventana de 12 meses gana limpio y mejora
                # de forma monotona 1m<3m<6m<9m<12m — expansion 0.620 y
                # contraccion 0.624, contra 0.516/0.610 de num_contracciones,
                # que en expansion y churn es literalmente azar.
                "cambio_mrr_12m_rel": (
                    (mrr_hoy - mrr_hace_12m) / mrr_hace_12m
                    if mrr_hace_12m else None),

                # El mejor predictor de churn de toda la medicion (AUC 0.339,
                # invertido: razon baja = churn alto). Cuanto dinero ha ganado
                # la cuenta contra cuanto ha perdido, en pesos. Nace de la
                # validacion de Luis: 6309555 acumulo 3 contracciones de -$13,
                # -$3 y -$13 mientras crecia de $27 a $449 de MRR — contarlas
                # como iguales la marcaba enferma; pesarlas la muestra sana.
                # Forma "balance" en vez de razon pura: (ganado - perdido) /
                # (ganado + perdido). Vale +1 si solo ha crecido, -1 si solo
                # ha encogido, 0 si va parejo. Es monotona con la razon
                # (balance = (r-1)/(r+1)), asi que conserva EXACTAMENTE el
                # mismo AUC medido — pero no se indefine cuando la cuenta
                # nunca se ha contraido, que es justo el caso mas sano. Con la
                # razon pura ese caso quedaba vacio y la cobertura era 24%.
                "balance_creci_contrac": (
                    (suma_expansiones - suma_contracciones)
                    / (suma_expansiones + suma_contracciones)
                    if (suma_expansiones + suma_contracciones) > 0 else None),
                "monto_contraido_total": suma_contracciones,
                "num_expansiones": len(expansiones),
                "num_contracciones": len(contracciones),
                "num_eventos": len(pasados),
                "dias_desde_ult_expansion": (cierre - ult_exp).days if ult_exp else None,
                "dias_desde_ult_contraccion": (cierre - ult_con).days if ult_con else None,
                "dias_desde_ult_evento": (cierre - pasados[-1]["fecha"]).days,
                "antiguedad_meses": (
                    (cierre.year - inicio_cliente.year) * 12
                    + (cierre.month - inicio_cliente.month)
                ) if inicio_cliente else None,
                "historia_truncada": bool(
                    inicio_cliente and inicio_cliente < panel_inicio),
                "dias_hasta_renovacion": dias_hasta_renovacion(
                    a_fecha(sub.get("next_invoice_date")),
                    sub.get("plan_billing_period_unit"), cierre),

                # --- uso real de la base ese mes (pings fechados) ---
                **features_de_uso(
                    serie_uso.get(sid, ()), cierre,
                    licencias_por_fecha(sub.get("enterprise_users"), historia, cierre)),

                # --- cuenta "llena": sin cupo para mas usuarios ---
                # Racha de pings al 100% de licencias en uso. El modelo le
                # asigna el peso; aqui solo se mide. Se guarda tambien la
                # version cruzada con plan mensual porque, segun Luis, una
                # mensual llena no solo compra usuarios: es candidata a
                # brincar a anual/multianual.
                "pings_al_tope": pings_al_tope(
                    serie_uso.get(sid, ()), cierre,
                    licencias_por_fecha(sub.get("enterprise_users"), historia, cierre)),
                "mensual_y_al_tope": bool(
                    sub.get("plan_billing_period_unit") == "month"
                    and pings_al_tope(
                        serie_uso.get(sid, ()), cierre,
                        licencias_por_fecha(
                            sub.get("enterprise_users"), historia, cierre)) >= 5),

                # --- productos contratados a esa fecha ---
                **features_de_productos(lineas_prod.get(sid, ()), cierre),

                # --- atributos estaticos ---
                **estaticos,
            }

            # --- ETIQUETAS: miran hacia ADELANTE (churn 120d, MRR 90d) ---
            lim_churn = cierre + datetime.timedelta(days=HORIZONTE_CHURN)
            lim_mrr = cierre + datetime.timedelta(days=HORIZONTE_MRR)
            fut_churn = [e for e in historia if cierre < e["fecha"] <= lim_churn]
            fut_mrr = [e for e in historia if cierre < e["fecha"] <= lim_mrr]

            # Tres propensiones independientes que pueden coexistir (decision
            # de Luis: multi-etiqueta, no una sola cubeta por cuenta). Un
            # cliente puede expandir Y contraer en la misma ventana.
            if cierre <= corte_etiqueta:
                fila["etiqueta_churn_120d"] = int(
                    any(e["tipo"] == "2_churn" for e in fut_churn))
                fila["etiqueta_expansion_90d"] = int(
                    any(e["tipo"] == "1_expansion" for e in fut_mrr))
                fila["etiqueta_contraccion_90d"] = int(
                    any(e["tipo"] == "15_contraction" for e in fut_mrr))
                fila["para_puntuar"] = False
            else:
                fila["etiqueta_churn_120d"] = None
                fila["etiqueta_expansion_90d"] = None
                fila["etiqueta_contraccion_90d"] = None
                fila["para_puntuar"] = True

            panel.append(fila)

    # --- Guardar ---
    ruta = os.path.join(CARPETA_MAESTRO, "panel_cuenta_mes.json")
    with open(ruta, "w") as f:
        json.dump(panel, f, ensure_ascii=False, indent=2)

    entrenables = [f for f in panel if not f["para_puntuar"]]
    puntuables = [f for f in panel if f["para_puntuar"]]

    print("--- Resultado ---")
    print("Filas del panel:            %d" % len(panel))
    print("   entrenables (con etiqueta): %d" % len(entrenables))
    print("   para puntuar (sin futuro):  %d" % len(puntuables))
    print("Suscripciones representadas: %d de %d"
          % (len({f["suscripcion_id"] for f in panel}), len(foto)))
    print("Suscripciones sin ningun evento (excluidas): %d" % sin_eventos)
    print("Churneadas sin fecha de churn (excluidas):   %d" % churn_sin_fecha)
    print("Suscripciones con churn en el log:           %d" % churneadas_vistas)
    print()
    print("--- Tasas base (el numero contra el que se juzga todo) ---")
    if entrenables:
        ch = sum(f["etiqueta_churn_120d"] for f in entrenables)
        ex = sum(f["etiqueta_expansion_90d"] for f in entrenables)
        print("churn en 120 dias:    %d de %d filas  (%.2f%%)"
              % (ch, len(entrenables), 100 * ch / len(entrenables)))
        print("expansion en 90 dias: %d de %d filas  (%.2f%%)"
              % (ex, len(entrenables), 100 * ex / len(entrenables)))
    print("\nGuardado en: %s" % ruta)


if __name__ == "__main__":
    main()
