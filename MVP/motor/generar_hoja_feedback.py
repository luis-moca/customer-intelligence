"""Genera la hoja de revision (Word) que se manda con el dashboard.

PARA QUE SIRVE
--------------
El dashboard muestra el resultado, pero no hay forma de que la persona que
conoce sus cuentas diga si el motor acerto o se equivoco. Esta hoja es ese
canal: lista sus cuentas de RIESGO DOWNGRADE y PROBABLE CRECIMIENTO — las dos
que Luis quiere validar primero — con espacio para escribir el veredicto.

Es Word (.docx) a proposito: se abre en Word, Pages o Google Docs, se escribe
encima sin instalar nada, y se regresa por correo. Un .md no lo abre nadie
fuera de gente tecnica.

QUE NO LLEVA
------------
Nombres de clientes. Solo el codigo de suscripcion (M...) y el numero de orden
(SO...), que es con lo que se busca en Odoo. Asi la hoja se puede reenviar,
imprimir o dejar en un escritorio sin exponer la cartera de nadie.

Uso:
    python3 generar_hoja_feedback.py            # todas las carteras
    python3 generar_hoja_feedback.py luesp      # una sola

Deja: salida/<gram>/Revision_<gram>.docx
"""
import datetime
import json
import os
import sys

import docx_simple

AQUI = os.path.dirname(os.path.abspath(__file__))
SALIDA = os.path.join(AQUI, "salida")

PRIORIDAD = ["RESCATAR", "RIESGO DOWNGRADE", "PROBABLE CRECIMIENTO",
             "LARGO PLAZO (pendiente)", "SIN ACCION"]

# Las dos que se piden validar. Se usa la accion UNICA (colapsada por
# prioridad), la misma que muestra el dashboard: si una cuenta sale aqui como
# "crecimiento" pero en la pantalla dice "rescatar", nadie entiende nada.
A_REVISAR = ["RIESGO DOWNGRADE", "PROBABLE CRECIMIENTO"]

TITULO = {
    "RIESGO DOWNGRADE": "Riesgo de downgrade",
    "PROBABLE CRECIMIENTO": "Probable crecimiento",
}
SUBTITULO = {
    "RIESGO DOWNGRADE": "El motor cree que estas cuentas podrian reducir su contrato.",
    "PROBABLE CRECIMIENTO": "El motor cree que estas cuentas tienen terreno para crecer.",
}

# El "por que" sale en jerga de columna (uso_activos=17). Aqui se traduce a
# algo que se lea. Lo que no este en el diccionario se muestra tal cual — mejor
# jerga honesta que una traduccion inventada.
LEGIBLE = {
    "uso_activos": "usuarios activos",
    "uso_creados": "usuarios creados",
    "uso_creados_sin_entrar": "usuarios creados que no entran",
    "uso_cambio_180d": "cambio de uso en 180 dias",
    "licencias_contratadas": "licencias contratadas",
    "licencias_sin_crear": "licencias pagadas sin usuario creado",
    "pings_al_tope": "semanas seguidas al 100% de sus licencias",
    "mensual_y_al_tope": "plan mensual y al tope de licencias",
    "mrr": "MRR",
    "mrr_hace_3m": "MRR hace 3 meses",
    "cambio_mrr_3m": "cambio de MRR en 3 meses",
    "cambio_mrr_12m_rel": "cambio de MRR en 12 meses",
    "balance_creci_contrac": "balance entre lo que ha crecido y lo que ha encogido",
    "monto_contraido_total": "monto total que ha reducido",
    "num_expansiones": "veces que ha crecido",
    "num_contracciones": "veces que ha reducido",
    "num_eventos": "movimientos en su contrato",
    "dias_desde_ult_expansion": "dias desde que crecio por ultima vez",
    "dias_desde_ult_contraccion": "dias desde que redujo por ultima vez",
    "dias_desde_ult_evento": "dias desde su ultimo movimiento",
    "antiguedad_meses": "meses de antiguedad",
    "dias_hasta_renovacion": "dias para su renovacion",
    "num_productos": "productos contratados",
    "num_modulos": "modulos de Odoo contratados",
    "modulos_faltantes": "modulos que NO tiene",
    "tiene_success_pack": "tiene Success Pack",
    "tiene_odoo_sh": "tiene Odoo.sh",
    "has_odoo_sh": "tiene Odoo.sh",
    "tiene_multi_year": "contrato multianual",
    "plan_contratado": "tipo de plan",
    "plan_billing_period_unit": "periodicidad de cobro",
    "hosting": "tipo de alojamiento",
    "version": "version de Odoo",
    "historia_truncada": "cliente mas viejo que nuestro historial",
}

VALOR = {"True": "si", "False": "no", "month": "mensual", "year": "anual",
         "saas": "en la nube (SaaS)", "paas": "Odoo.sh (PaaS)",
         "premise": "servidor propio", "custom": "Custom", "standard": "Standard"}


def accion_unica(c):
    for p in PRIORIDAD:
        if p in c["acciones"]:
            return p
    return "SIN ACCION"


def traducir(senal):
    """'uso_activos=17' -> 'usuarios activos: 17'."""
    if "=" not in senal:
        return LEGIBLE.get(senal, senal)
    col, val = senal.split("=", 1)
    return "%s: %s" % (LEGIBLE.get(col, col), VALOR.get(val, val))


def porque_de(c, accion):
    clave = ("porque_contraccion" if accion == "RIESGO DOWNGRADE"
             else "porque_expansion")
    return [traducir(s) for s in (c.get(clave) or [])]


def datos_de_cartera(gram):
    ruta = os.path.join(SALIDA, gram, "%s_puntuacion.json" % gram)
    if not os.path.exists(ruta):
        return None
    cuentas = json.load(open(ruta))
    grupos = {a: [] for a in A_REVISAR}
    for c in cuentas:
        a = accion_unica(c)
        if a in grupos:
            grupos[a].append(c)
    for a in grupos:
        clave = "p_contraccion" if a == "RIESGO DOWNGRADE" else "p_expansion"
        grupos[a].sort(key=lambda c: -(c.get(clave) or 0))
    return {"gram": gram, "total": len(cuentas), "grupos": grupos}


def escribir_docx(info, destino, fecha):
    """Arma el .docx. Ver docx_simple.py — Python puro, sin dependencias."""
    D = docx_simple
    ANCHO = D.ANCHO_UTIL
    # codigo | % | por que | veredicto | observaciones  == ANCHO
    COLS = [2050, 620, 2900, 1500, ANCHO - 2050 - 620 - 2900 - 1500]

    c = []
    c.append(D.parrafo("Revision de cuentas — cartera %s" % info["gram"],
                       negrita=True, tam=32, espacio_despues=40))
    c.append(D.parrafo("Customer Intelligence  ·  %s  ·  %d cuentas vivas en total"
                       % (fecha, info["total"]),
                       tam=18, color="6B6B76", espacio_despues=200,
                       borde_abajo="D0D0D8"))

    c.append(D.parrafo(
        "Estas son las cuentas que el motor marco en las dos categorias que "
        "queremos validar contigo. No trae nombres de clientes a proposito: "
        "busca el codigo de suscripcion o el numero de orden en Odoo.",
        tam=19, espacio_despues=90))
    c.append(D.parrafo(
        "Lo unico que necesitamos de ti: en la columna \u00bfAcerto? escribe SI, NO "
        "o NO SE, y si algo no cuadra, dinos por que en Observaciones. Un \"NO\" "
        "bien explicado vale mas que diez \"SI\" — asi es como el motor aprende "
        "lo que no esta en Odoo.",
        tam=19, espacio_despues=260))

    primera = True
    for accion in A_REVISAR:
        cuentas = info["grupos"][accion]
        if not primera:
            c.append(D.salto_pagina())
        primera = False

        color = "C0700A" if accion == "RIESGO DOWNGRADE" else "0B7A55"
        c.append(D.parrafo("%s  (%d %s)"
                           % (TITULO[accion], len(cuentas),
                              "cuenta" if len(cuentas) == 1 else "cuentas"),
                           negrita=True, tam=26, color=color,
                           espacio_antes=60, espacio_despues=40))
        c.append(D.parrafo(SUBTITULO[accion], tam=19, color="6B6B76",
                           cursiva=True, espacio_despues=140))

        if not cuentas:
            c.append(D.parrafo(
                "El motor no marco ninguna cuenta en esta categoria. "
                "Si crees que si deberia haber alguna, dinoslo — que no salga "
                "nada tambien es un resultado que hay que revisar.",
                tam=19, espacio_despues=200))
            continue

        encabezados = ["Codigo de suscripcion", "Prob.", "Por que lo marco",
                       "\u00bfAcerto?", "Observaciones"]
        filas = [D.fila([D.celda(D.parrafo(h, negrita=True, tam=17,
                                           color="FFFFFF", espacio_despues=0),
                                 COLS[j], fondo=color)
                         for j, h in enumerate(encabezados)],
                        encabezado=True)]

        clave_p = ("p_contraccion" if accion == "RIESGO DOWNGRADE"
                   else "p_expansion")
        for c_ in cuentas:
            izq = [D.parrafo(c_.get("codigo") or "\u2014", negrita=True, tam=17,
                             mono=True, espacio_despues=20),
                   D.parrafo(c_.get("orden") or "\u2014", tam=15, color="6B6B76",
                             mono=True, espacio_despues=0)]
            porque = porque_de(c_, accion) or ["(sin senal dominante)"]
            senales = [D.parrafo("\u2022 " + p, tam=16, espacio_despues=20)
                       for p in porque]
            prob = round(100 * (c_.get(clave_p) or 0))
            filas.append(D.fila([
                D.celda(izq, COLS[0]),
                D.celda(D.parrafo("%d%%" % prob, negrita=True, tam=20,
                                  color=color, alineacion="center",
                                  espacio_despues=0), COLS[1]),
                D.celda(senales, COLS[2]),
                D.celda(D.parrafo("", espacio_despues=0), COLS[3], fondo="FAFAFB"),
                D.celda(D.parrafo("", espacio_despues=0), COLS[4], fondo="FAFAFB"),
            ], alto=760))

        c.append(D.tabla(filas, COLS))
        c.append(D.parrafo("", espacio_despues=0))

    c.append(D.salto_pagina())
    c.append(D.parrafo("\u00bfAlgo que el motor NO vio?", negrita=True, tam=24,
                       espacio_despues=40))
    c.append(D.parrafo(
        "Si tienes cuentas que deberian estar en alguna de las dos listas y no "
        "aparecen, anotalas aqui. Esto es igual de valioso que corregir las de "
        "arriba: lo que el motor no marca es su punto ciego, y no hay forma de "
        "encontrarlo sin ti.",
        tam=19, color="6B6B76", espacio_despues=160))

    COLS2 = [2050, 2000, D.ANCHO_UTIL - 2050 - 2000]
    filas2 = [D.fila([D.celda(D.parrafo(h, negrita=True, tam=17, color="FFFFFF",
                                        espacio_despues=0), COLS2[j],
                              fondo="4A4A55")
                      for j, h in enumerate(["Codigo o numero de orden",
                                             "\u00bfCual deberia ser?",
                                             "\u00bfPor que?"])],
                     encabezado=True)]
    for _ in range(8):
        filas2.append(D.fila([D.celda(D.parrafo("", espacio_despues=0), w,
                                      fondo="FAFAFB") for w in COLS2], alto=620))
    c.append(D.tabla(filas2, COLS2))

    c.append(D.parrafo(
        "Gracias. Cuando lo termines, regresame el archivo — con eso ajustamos "
        "el motor.", tam=19, cursiva=True, color="6B6B76",
        espacio_antes=200, espacio_despues=0))

    D.guardar(destino, c)
    return destino


def main():
    grams = sys.argv[1:] or sorted(
        g for g in os.listdir(SALIDA)
        if os.path.exists(os.path.join(SALIDA, g, "%s_puntuacion.json" % g)))
    hoy = datetime.date.today()
    meses = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
             "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
    fecha = "%d de %s de %d" % (hoy.day, meses[hoy.month - 1], hoy.year)

    print("%-8s %10s %12s   %s" % ("cartera", "downgrade", "crecimiento", "archivo"))
    for g in grams:
        info = datos_de_cartera(g)
        if not info:
            print("%-8s  falta %s_puntuacion.json" % (g, g))
            continue
        destino = os.path.join(SALIDA, g, "Revision_%s.docx" % g)
        escribir_docx(info, destino, fecha)
        print("%-8s %10d %12d   %s"
              % (g, len(info["grupos"]["RIESGO DOWNGRADE"]),
                 len(info["grupos"]["PROBABLE CRECIMIENTO"]),
                 os.path.basename(destino)))


if __name__ == "__main__":
    main()
