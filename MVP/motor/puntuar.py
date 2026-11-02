"""EL OUTPUT: una fila por cuenta activa, con sus 3 probabilidades calibradas.

Que hace, en orden:
 1. Entrena los 3 modelos con toda la historia etiquetada MENOS el ultimo mes.
 2. Con ese ultimo mes etiquetado (que el modelo no vio) ajusta la bascula
    (Platt) — asi las probabilidades de hoy salen ya corregidas, no crudas.
 3. Puntua la fila MAS RECIENTE de cada cuenta viva (las para_puntuar del
    ultimo cierre del panel).
 4. Etiqueta con los umbrales medidos en el backtest: churn>=20%,
    contraccion>=20%, expansion>=50%. Lo que no cruza ninguno = "sin accion"
    (resultado esperado para la mayoria de una cartera sana). Una cuenta
    puede cruzar dos umbrales a la vez — no se fuerza una sola cubeta.
 5. El "por que": las 2 variables que mas empujan la probabilidad hacia
    arriba en ESA cuenta (peso del modelo x valor de la cuenta).

Sin nombres ni contactos: solo id de suscripcion y gram. Cero Odoo.
Salida: maestro/puntuacion_hoy.json + resumen en consola.
"""
import json
import math
import os

from calibrar import ajustar_platt, aplicar
from features import construir_esquema, construir_x, nombres_de_columnas
from modelo_simple import entrenar, normalizar, predecir, vectorizar

from rutas import MAESTRO
# Umbral de churn subido de 0.20 a 0.23 por validacion de Luis en su frontend
# (22-ago-2026): de las 5 cuentas que caian entre 20% y 23%, solo 1 valia la
# pena rescatar. La vara la pone quien conoce las cuentas, no la estadistica.
UMBRALES = {"churn": 0.23, "contraccion": 0.20, "expansion": 0.50}

# Reglas duras de elegibilidad (Luis, 22-ago-2026). No son predicciones: son
# hechos del contrato que hacen que una alerta no tenga sentido.
MIN_LICENCIAS_PARA_SATURACION = 2   # con 1 sola licencia no hay señal
DIAS_RENOVACION_RECIENTE = 120      # renovo hace <4 meses -> nada que decir
OBJETIVOS = [("etiqueta_expansion_90d", "expansion"),
             ("etiqueta_contraccion_90d", "contraccion"),
             ("etiqueta_churn_120d", "churn")]
ACCION = {"churn": "RESCATAR", "contraccion": "RIESGO DOWNGRADE",
          "expansion": "PROBABLE CRECIMIENTO"}


def main():
    panel = json.load(open(os.path.join(MAESTRO, "panel_cuenta_mes.json")))
    ent = [f for f in panel if not f["para_puntuar"]]
    ultimo_etiquetado = max(f["cierre_mes"] for f in ent)
    train = [f for f in ent if f["cierre_mes"] < ultimo_etiquetado]
    cal = [f for f in ent if f["cierre_mes"] == ultimo_etiquetado]

    puntuables = [f for f in panel if f["para_puntuar"]]
    cierre_hoy = max(f["cierre_mes"] for f in puntuables)
    hoy = [f for f in puntuables if f["cierre_mes"] == cierre_hoy]

    print("Entrena: %d filas | calibra: %d (%s) | puntua: %d cuentas vivas (%s)\n"
          % (len(train), len(cal), ultimo_etiquetado, len(hoy), cierre_hoy))

    esquema = construir_esquema(train)
    cols = nombres_de_columnas(esquema)
    st = normalizar([construir_x(f, esquema) for f in train], cols)
    vec = lambda fs: [vectorizar(construir_x(f, esquema), cols, st) for f in fs]
    Xtr, Xcal, Xhoy = vec(train), vec(cal), vec(hoy)

    # Fecha REAL de proxima factura por suscripcion (para la regla de "ya
    # pago" — ver el comentario en el bloque de churn de abajo).
    import datetime
    foto = json.load(open(os.path.join(MAESTRO, "foto_maestra.json")))

    # QUIEN es cada cuenta. Antes la salida traia solo el id interno
    # (54517328), que no le sirve a nadie: no dice de quien se trata ni se
    # puede buscar en Odoo. Decision de Luis (23-ago-2026): sale el NOMBRE del
    # cliente y su CODIGO de suscripcion (client_order_ref, el que empieza con
    # M — presente en el 100% de las suscripciones y con el que el CS busca de
    # verdad). El id se conserva porque es la llave interna con la que se cruza
    # todo, pero ya no es lo unico.
    #
    # Nada de esto entra al modelo: el nombre no es una variable, es una
    # etiqueta para leer el resultado. La precision no cambia ni un decimal.
    identidad = {}
    for s_ in foto:
        p = s_.get("partner_id")
        identidad[s_["id"]] = {
            "cliente": p[1] if isinstance(p, list) and len(p) == 2 else None,
            "codigo": s_.get("client_order_ref") or None,
            "orden": s_.get("name") or None,
        }

    cuentas = []
    for f in hoy:
        ident = identidad.get(f["suscripcion_id"], {})
        cuentas.append({"suscripcion_id": f["suscripcion_id"],
                        "cliente": ident.get("cliente"),
                        "codigo": ident.get("codigo"),
                        "orden": ident.get("orden"),
                        "gram": f["gram"],
                        # MRR al cierre (reconstruido del log, no el de hoy).
                        # NO es variable del modelo aqui: es para que la matriz
                        # del dashboard dibuje el tamano de cada burbuja — una
                        # cuenta de $5,000 no puede verse igual que una de $27.
                        "mrr": f.get("mrr"),
                        "acciones": []})
    hoy_fecha = datetime.date.fromisoformat(cierre_hoy)
    dias_reales = {}
    for s_ in foto:
        ni = str(s_.get("next_invoice_date") or "")[:10]
        try:
            dias_reales[s_["id"]] = (datetime.date.fromisoformat(ni) - hoy_fecha).days
        except ValueError:
            pass

    # Regla 4: una cuenta anual/multianual que renovo hace menos de 4 meses
    # queda fuera de TODAS las categorias, no solo de rescate. Acaba de decidir
    # y pagar: no hay nada que decirle al AM sobre ella (Luis, 22-ago-2026,
    # sobre SO2026/8172046, que salia en CUENTA LLENA y en LARGO PLAZO).
    recien_renovadas = set()
    for cta, fila in zip(cuentas, hoy):
        if fila.get("plan_billing_period_unit") != "year":
            continue
        prox = dias_reales.get(cta["suscripcion_id"])
        if prox is None:
            continue
        # dias transcurridos desde la ultima renovacion en un ciclo anual
        desde_renovacion = 365 - prox
        if 0 <= desde_renovacion < DIAS_RENOVACION_RECIENTE:
            recien_renovadas.add(cta["suscripcion_id"])
            cta["excluida"] = ("renovo hace %d dias — decision reciente ya "
                               "tomada y pagada" % desde_renovacion)

    for objetivo, nombre in OBJETIVOS:
        m = entrenar(Xtr, [f[objetivo] for f in train], cols)
        A, B = ajustar_platt([predecir(m, x) for x in Xcal],
                             [f[objetivo] for f in cal])
        for cta, x, fila in zip(cuentas, Xhoy, hoy):
            p = aplicar(A, B, predecir(m, x))
            cta["p_" + nombre] = round(p, 4)
            if p < UMBRALES[nombre] or cta["suscripcion_id"] in recien_renovadas:
                continue

            # Regla dura de "ya pago" (Luis, 22-ago-2026), SOLO para churn,
            # SIN excepcion: una cuenta anual/multianual con proxima factura
            # a mas de 120 dias no puede entrar a RESCATAR, sin importar que
            # tan bajo este su uso. Contractualmente no puede churnear antes
            # de esa fecha — la decision de renovar ya esta tomada y pagada.
            # Uso bajo ahi es candidata para el modelo de largo plazo
            # (PENDIENTES.md), NO evidencia de riesgo inmediato — se aplica
            # parejo, no se pondera contra el uso. Las mensuales NUNCA se
            # suprimen (renuevan su decision cada mes — son las mas
            # riesgosas). Expansion jamas se suprime por fecha de renovacion:
            # una multianual que renueva en 2-4 años puede crecer en
            # cualquier momento.
            if nombre == "churn":
                # OJO: aqui se usa la fecha REAL de proxima factura (de la
                # foto), NO la feature reconstruida del panel. La reconstruida
                # camina ciclos hacia atras — necesario para filas historicas,
                # pero a una cuenta que YA renovo le inventa su fecha vieja
                # (asi se colaron 8118653 y 8172046 en la primera corrida,
                # cachadas por Luis). Para decidir HOY, la verdad es la fecha
                # de hoy tal cual.
                renov = dias_reales.get(cta["suscripcion_id"])
                anual = fila.get("plan_billing_period_unit") == "year"
                if anual and renov is not None and renov > 120:
                    cta["acciones"].append("LARGO PLAZO (pendiente)")
                    cta["nota_largo_plazo"] = (
                        "renovacion anual/multianual a %d dias — no puede "
                        "churnear antes; candidata para el futuro modelo de "
                        "largo plazo, no una prediccion" % renov)
                    continue

            # por que: las variables que mas empujan HACIA ARRIBA en esta
            # cuenta, CON su valor real — para que el motivo sea verificable
            # de un vistazo, no un nombre de columna pelon.
            # Desempate EXPLICITO por nombre de columna: hay variables que
            # aportan exactamente lo mismo (p.ej. plan_id=173 y
            # plan_billing_period_unit=month, que en el train van siempre
            # juntas, asi que L1 les da el mismo peso). Con `reverse=True` el
            # empate lo rompia el nombre al reves, y el JS del dashboard lo
            # rompia por orden de columna — dos criterios distintos, y el AM
            # veia motivos en distinto orden segun donde mirara. Ordenar por
            # (-aporte, nombre) es la misma regla escrita en los dos motores.
            aportes = sorted(((w * v, c) for w, v, c in zip(m["w"], x, cols)
                              if w * v > 0), key=lambda a: (-a[0], a[1]))[:3]
            motivos = []
            for _, c in aportes:
                base_col = c.split("=")[0]
                crudo = fila.get(base_col)
                if "=" in c or crudo is None:
                    motivos.append(c)
                else:
                    crudo = round(crudo, 2) if isinstance(crudo, float) else crudo
                    motivos.append("%s=%s" % (c, crudo))
            cta["acciones"].append(ACCION[nombre])
            cta["porque_" + nombre] = motivos

    # --- CUENTA LLENA: regla de negocio de Luis, fuera del modelo ---
    # Una cuenta con el 100% de sus licencias contratadas en uso durante 5
    # pings seguidos o mas ya no tiene donde crecer por dentro: es candidata a
    # expansion. Aplica a CUALQUIER plan — mensual, anual o multianual: estar
    # lleno es salud y oportunidad en los tres (correccion de Luis: proponer
    # esto solo para mensuales dejaba fuera media cartera).
    #
    # Va aparte del modelo a proposito. Se midio (medir_saturacion.py: 45% de
    # expansion contra 30% de tasa base) y se probo dentro del modelo
    # (ablacion): L1 la apago porque solo cubre 1.8% de las filas — cierta
    # pero de bajo volumen, no mueve un promedio. Diluirla entre 130 columnas
    # la desperdicia; como marca explicita llega entera al AM.
    #
    # En las MENSUALES ademas se sugiere el cambio de plan: pasar de mensual a
    # anual/multianual tambien es expansion — sube el ingreso para Odoo, no
    # solo la venta de usuarios o modulos.
    for cta, fila in zip(cuentas, hoy):
        racha = fila.get("pings_al_tope") or 0
        licencias = fila.get("licencias_contratadas") or 0
        # Con 1 sola licencia estar "al tope" no dice nada: no hay forma de
        # saber si la cuenta tiene potencial (Luis, 22-ago-2026).
        if (racha < 5 or licencias < MIN_LICENCIAS_PARA_SATURACION
                or cta["suscripcion_id"] in recien_renovadas):
            continue
        cta["cuenta_llena"] = {
            "pings_seguidos_al_tope": racha,
            "licencias": fila.get("licencias_contratadas"),
            "usuarios_activos": fila.get("uso_activos"),
        }
        if "PROBABLE CRECIMIENTO" not in cta["acciones"]:
            cta["acciones"].append("PROBABLE CRECIMIENTO")
        if fila.get("plan_billing_period_unit") == "month":
            cta["cuenta_llena"]["sugerencia_plan"] = (
                "mensual al tope — candidata tambien a cambio a plan anual "
                "o multianual (cambiar de plan tambien es expansion: sube el "
                "ingreso, no solo se venden usuarios o modulos)")

    for cta in cuentas:
        if not cta["acciones"]:
            cta["acciones"] = ["SIN ACCION"]

    ruta = os.path.join(MAESTRO, "puntuacion_hoy.json")
    with open(ruta, "w") as fh:
        json.dump(cuentas, fh, ensure_ascii=False, indent=1)

    # resumen por cartera
    ETIQUETAS = ("RESCATAR", "RIESGO DOWNGRADE", "PROBABLE CRECIMIENTO",
                 "LARGO PLAZO (pendiente)", "SIN ACCION")
    print("%-8s %7s %9s %10s %12s %11s %10s %9s"
          % ("gram", "cuentas", "RESCATAR", "DOWNGRADE", "CRECIMIENTO",
             "LARGO PLAZO", "sin accion", "excluidas"))
    grams = sorted({c["gram"] for c in cuentas})
    tot = {k: 0 for k in ETIQUETAS}
    for g in grams:
        cs = [c for c in cuentas if c["gram"] == g]
        n = {k: sum(1 for c in cs if k in c["acciones"]) for k in ETIQUETAS}
        for k in ETIQUETAS:
            tot[k] += n[k]
        print("%-8s %7d %9d %10d %12d %11d %10d %9d"
              % (g, len(cs), n["RESCATAR"], n["RIESGO DOWNGRADE"],
                 n["PROBABLE CRECIMIENTO"], n["LARGO PLAZO (pendiente)"],
                 n["SIN ACCION"], sum(1 for c in cs if c.get("excluida"))))
    print("%-8s %7d %9d %10d %12d %11d %10d %9d"
          % ("TOTAL", len(cuentas), tot["RESCATAR"], tot["RIESGO DOWNGRADE"],
             tot["PROBABLE CRECIMIENTO"], tot["LARGO PLAZO (pendiente)"],
             tot["SIN ACCION"], sum(1 for c in cuentas if c.get("excluida"))))
    print("\nGuardado: %s" % ruta)


if __name__ == "__main__":
    main()
