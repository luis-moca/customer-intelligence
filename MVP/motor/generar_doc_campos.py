"""Genera Contexto/05_CAMPOS.md: que campo entra al motor, cual no, y por que.

POR QUE EXISTE
--------------
La informacion ya vivia en el codigo (las 6 listas de exclusion de
panel_fase2.py) y en MEDICION_132.md (la tabla cruda de resultados), pero
ninguna de las dos se puede leer de corrido para entender el criterio. Luis
pidio verlo "de manera entendible para un ojo humano".

Se GENERA, no se escribe a mano, por una razon: si alguien mueve un campo de
una lista a otra en panel_fase2.py, el documento escrito a mano quedaria
mintiendo en silencio — y este proyecto ya tuvo ese problema con el README.
Aqui la unica fuente es el codigo. Se regenera con:

    python3 generar_doc_campos.py
"""
import json
import os

import panel_fase2 as pf
from exportar_todo import CAMPOS_SALE_ORDER
from rutas import MAESTRO

AQUI = os.path.dirname(os.path.abspath(__file__))

# El "por que" de cada lista, en lenguaje llano. Es lo unico escrito a mano —
# el contenido de las listas sale del codigo.
GRUPOS = [
    ("ELIMINADOS_APROBADOS", pf.ELIMINADOS_APROBADOS,
     "Medidos por Python y aprobados por Luis, en ese orden",
     "Metadata sin poder predictivo: comisiones, campos de interfaz, ratings que "
     "nunca se llenan, la moneda de la orden (siempre la misma), direcciones de "
     "facturacion y envio que duplican al cliente. Casi todos salieron "
     "**CONSTANTES o CASI CONSTANTES** en la medicion — el mismo valor en el "
     "99%+ de las cuentas, asi que no distinguen nada."),

    ("FUGA_CONFIRMADA", pf.FUGA_CONFIRMADA,
     "El modelo veria el futuro",
     "Se apagan o se encienden **exactamente cuando la cuenta muere**. Entrenar "
     "con ellos da un modelo que reconoce cadaveres, no que predice muertes. Se "
     "reviso uno por uno el 22-ago-2026 (`medir_fuga_por_desenlace.py` + "
     "`medir_artefacto_temporal.py`) para no tirar de mas: de 10 candidatos, "
     "**`payment_term_id` fue el unico estable de verdad** y ese SI entrena. "
     "Los otros 9 se usan para puntuar cuentas vivas hoy, jamas para entrenar."),

    ("LLAVES", pf.LLAVES,
     "Identifican, no describen",
     "IDs internos y relaciones a otros registros. Saber que una cuenta tiene el "
     "id 6311335 no dice nada de si va a crecer. Ojo: varios de estos SI se usan, "
     "pero como CONTEO, no como valor — `message_ids` se convierte en 'cuantos "
     "mensajes tiene' (medido: el churn sube de 7.9% a 36.6% del cuartil bajo al "
     "alto), y `order_line` se convierte en que productos tiene contratados."),

    ("TEXTO_O_RUIDO", pf.TEXTO_O_RUIDO,
     "Texto libre o HTML",
     "No son numero ni categoria: son parrafos. Un modelo lineal no puede leerlos. "
     "**`internal_note_display` salio de aqui** — llamarlo 'ruido' fue un error: es "
     "la calificacion que escribe el CS. Se movio a NO_ENTRENABLE_SOLO_PUNTUAR "
     "porque el problema no es que sea texto, es que solo existe en su version de hoy."),

    ("FECHAS_CRUDAS", pf.FECHAS_CRUDAS,
     "Se usan derivadas, nunca crudas",
     "Una fecha exacta casi nunca se repite entre cuentas, asi que como categoria "
     "no sirve. Lo que si sirve es lo que se calcula CON ellas: antiguedad en "
     "meses, dias hasta la renovacion, dias desde el ultimo evento. Esas derivadas "
     "si entran al modelo."),

    ("NO_ENTRENABLE_SOLO_PUNTUAR", pf.NO_ENTRENABLE_SOLO_PUNTUAR,
     "Solo tenemos el valor de HOY",
     "La categoria mas grande y el error mas repetido del proyecto. Estos campos "
     "cambian con el tiempo, pero Odoo solo guarda su valor actual. Pegarle el "
     "valor de agosto-2026 a una fila de marzo-2024 es fuga — y es una fuga que "
     "**el backtest NO detecta**, porque contamina tambien las filas de prueba. "
     "Caso de libro: `enterprise_users` esta en 0 para las 526 cuentas churneadas "
     "y en >0 para las 1,461 activas. Separacion perfecta, senal perfecta, modelo "
     "inutil. Cuando se puede, el valor historico se **reconstruye** desde eventos "
     "fechados (asi salen `mrr`, `licencias_contratadas`, `uso_activos`)."),
]

DERIVADAS = [
    ("Dinero (del log de eventos, con fecha real)",
     ["mrr", "mrr_hace_3m", "cambio_mrr_3m", "cambio_mrr_12m_rel",
      "balance_creci_contrac", "monto_contraido_total"],
     "El MRR de cada mes se reconstruye caminando el historial de eventos, no se "
     "copia el de hoy. `balance_creci_contrac` (cuanto ha crecido vs cuanto ha "
     "encogido) es **el mejor predictor de churn de toda la tabla**."),
    ("Ritmo de la cuenta",
     ["num_expansiones", "num_contracciones", "num_eventos",
      "dias_desde_ult_expansion", "dias_desde_ult_contraccion",
      "dias_desde_ult_evento", "antiguedad_meses", "historia_truncada",
      "dias_hasta_renovacion"],
     "`dias_hasta_renovacion` se calcula caminando ciclos de 12 meses hacia atras "
     "desde la proxima factura — reemplazo de `dias_hasta_aniversario`, que causo "
     "6 de 7 falsos positivos. `historia_truncada` marca si el cliente es mas "
     "viejo que la ventana del log (2023-08-23)."),
    ("Uso real (de los pings, fechados)",
     ["uso_activos", "uso_creados", "uso_creados_sin_entrar", "uso_cambio_180d",
      "licencias_contratadas", "licencias_sin_crear", "pings_al_tope",
      "mensual_y_al_tope"],
     "Los TRES niveles que Luis corrigio: licencias contratadas (lo que paga), "
     "usuarios creados (asientos que existen), usuarios activos (entraron esta "
     "semana). **El uso cae mediana -50% en los 180 dias previos al churn** — la "
     "senal mas fuerte del modelo."),
    ("Productos contratados (de las lineas de orden, con fecha)",
     ["num_productos", "num_modulos", "modulos_faltantes", "tiene_success_pack",
      "tiene_odoo_sh", "tiene_multi_year", "plan_contratado"],
     "`modulos_faltantes` contesta la pregunta de upsell al reves: en vez de "
     "'¿quien va a expandir?' (debil), pregunta '¿que le falta comprar?'."),
]


def main():
    esquema_cols = json.load(open(os.path.join(MAESTRO, "panel_cuenta_mes.json")))[0]
    no_feature = {"suscripcion_id", "gram", "cierre_mes", "para_puntuar",
                  "cliente_id", "anio", "mes", "etiqueta_churn_120d",
                  "etiqueta_expansion_90d", "etiqueta_contraccion_90d"}
    del esquema_cols

    total_fuera = sum(len(g[1]) for g in GRUPOS)
    L = []
    w = L.append

    w("# Los campos: cual entra al motor, cual no, y por que\n")
    w("> **Generado por `motor/generar_doc_campos.py`, no escrito a mano.** Las")
    w("> listas salen directo de `panel_fase2.py`. Si alguien mueve un campo de")
    w("> una lista a otra, se regenera y este documento se actualiza solo — no")
    w("> puede quedar mintiendo.\n")
    w("De los **%d campos** que trae `sale.order` en Odoo:\n" % len(CAMPOS_SALE_ORDER))
    w("| | Cuantos |")
    w("|---|---|")
    w("| **Excluidos** (6 razones distintas, abajo) | **%d** |" % total_fuera)
    w("| **Entran como atributo** de la cuenta | **%d** |" % len(pf.ATRIBUTOS_ESTATICOS))
    w("| Caso aparte sin resolver (`upsell_content`) | 1 |")
    w("")
    w("A esos %d atributos se suman **%d variables calculadas** que NO salen de"
      % (len(pf.ATRIBUTOS_ESTATICOS), sum(len(d[1]) for d in DERIVADAS)))
    w("`sale.order`, sino de los pings, el log de eventos y las lineas de producto.")
    w("Esas son las que de verdad predicen — ver la ultima seccion.\n")
    w("---\n")
    w("## Lo que NO entra, y por que\n")

    for i, (nombre, campos, titulo, explicacion) in enumerate(GRUPOS, 1):
        w("### %d. %s — %d campos" % (i, titulo, len(campos)))
        w("<sub>`%s` en `panel_fase2.py`</sub>\n" % nombre)
        w(explicacion + "\n")
        w("```")
        linea = ""
        for c in sorted(campos):
            if len(linea) + len(c) > 74:
                w(linea.rstrip())
                linea = ""
            linea += c + ", "
        w(linea.rstrip().rstrip(","))
        w("```\n")

    w("### + El caso aparte: `upsell_content`\n")
    w("**No esta en ninguna de las 6 listas de arriba** — nunca se decidio")
    w("excluirlo. Se pide aparte de los otros %d por un bug de Odoo (no se puede"
      % len(CAMPOS_SALE_ORDER))
    w("leer en lote, hay que pedirlo cuenta por cuenta), esta descargado en")
    w("`datos/foto_maestra.json`, y simplemente **nadie escribio la linea que lo**")
    w("**mete al panel**. Solo 21 de 1,987 cuentas lo traen lleno (1.06%).")
    w("Pendiente de medir antes de decidir — ver `PENDIENTES.md`.\n")
    w("---\n")
    w("## Lo que SI entra\n")
    w("### Atributos de la cuenta (%d, directo de `sale.order`)\n"
      % len(pf.ATRIBUTOS_ESTATICOS))
    w("Lo que la cuenta *es* y no cambia mes a mes: su plan, donde esta alojada,")
    w("su pais, su version de Odoo, su plantilla de contrato.\n")
    w("```")
    linea = ""
    for c in sorted(pf.ATRIBUTOS_ESTATICOS):
        if len(linea) + len(c) > 74:
            w(linea.rstrip())
            linea = ""
        linea += c + ", "
    w(linea.rstrip().rstrip(","))
    w("```\n")

    w("### Variables calculadas (%d) — las que de verdad predicen\n"
      % sum(len(d[1]) for d in DERIVADAS))
    w("Ninguna existe en `sale.order`. Todas se **reconstruyen hacia atras** desde")
    w("fuentes fechadas, que es lo que permite decir 'en marzo de 2024 esta cuenta")
    w("tenia 8 usuarios activos' sin inventarlo.\n")
    for titulo, campos, nota in DERIVADAS:
        w("**%s** — %d" % (titulo, len(campos)))
        w("")
        w("```")
        w(", ".join(campos))
        w("```")
        w("")
        w(nota + "\n")

    w("---\n")
    w("## Donde esta la evidencia\n")
    w("- `mediciones/MEDICION_132.md` — la tabla cruda: cada campo contra los 3")
    w("  desenlaces, con su veredicto (CONSTANTE / FUGA / DEBIL / FUERTE).")
    w("- `mediciones/medir_fuga_por_desenlace.py` — si la fuga es contra los 3")
    w("  desenlaces o solo contra churn.")
    w("- `mediciones/medir_artefacto_temporal.py` — si un campo cuenta el")
    w("  calendario en vez de la cuenta.")
    w("- `03_LECCIONES.md` — los errores que produjeron estas reglas.\n")
    w("**Regla 1 del proyecto:** ningun campo se elimina sin medicion de Python y")
    w("aprobacion de Luis, en ese orden.")

    for destino in (os.path.join(AQUI, "..", "MVP", "Contexto", "05_CAMPOS.md"),
                    os.path.join(AQUI, "..", "Contexto", "05_CAMPOS.md")):
        if os.path.isdir(os.path.dirname(destino)):
            with open(destino, "w") as fh:
                fh.write("\n".join(L) + "\n")
            print("Escrito: %s (%d lineas)" % (os.path.normpath(destino), len(L)))
            break


if __name__ == "__main__":
    main()
