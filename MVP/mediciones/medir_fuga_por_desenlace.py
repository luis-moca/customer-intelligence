"""Mide los 10 campos de FUGA_CONFIRMADA contra los TRES desenlaces por separado.

Por que existe: se excluyeron en bloque porque se apagan cuando la cuenta muere
— eso es fuga contra CHURN. Pero "se apaga al morir" no dice nada sobre
expansion ni contraccion. Excluirlos de los tres modelos es tirar informacion
de mas. Aqui decide la medicion, no el criterio de nadie.

Criterio de fuga (el mismo que se uso contra churn): un valor del campo que
separe casi perfecto — cubre >=20% de las cuentas y la tasa del desenlace ahi
es <2% o >98%. Eso no es una senal, es la etiqueta disfrazada.
"""
import collections
import json
import os

from rutas import MAESTRO

CAMPOS = ["subscription_state", "close_reason_id", "enterprise_users",
          "enterprise_is_enterprise", "enterprise_has_download",
          "maintenance_is_activated", "maintenance_is_paying",
          "activity_user_id", "payment_term_id", "end_date"]


def idv(v):
    return v[0] if isinstance(v, list) else v


def balde(v):
    """Agrupa el valor en una categoria legible. Los numeros grandes en tramos."""
    if v is None or v is False or v == "":
        return "vacio/False"
    if isinstance(v, bool):
        return "True"
    if isinstance(v, list):
        return "id=%s" % idv(v)
    if isinstance(v, (int, float)):
        if v == 0:
            return "0"
        if v <= 5:
            return "1-5"
        if v <= 20:
            return "6-20"
        return ">20"
    return str(v)[:22]


def main():
    foto = json.load(open(os.path.join(MAESTRO, "foto_maestra.json")))
    ev = json.load(open(os.path.join(MAESTRO, "eventos_maestros.json")))

    # desenlace por suscripcion, del ledger de eventos (unica fuente con fechas)
    tuvo = {t: set() for t in ("churn", "expansion", "contraccion")}
    mapa = {"2_churn": "churn", "1_expansion": "expansion",
            "15_contraction": "contraccion"}
    for e in ev:
        t = mapa.get(e.get("event_type"))
        if t:
            tuvo[t].add(idv(e.get("order_id")))

    subs = [s for s in foto if s.get("subscription_state") in ("3_progress", "6_churn")]
    n = len(subs)
    print("Universo: %d suscripciones de las 9 carteras\n" % n)

    for campo in CAMPOS:
        print("=" * 78)
        print("CAMPO: %s" % campo)
        grupos = collections.defaultdict(list)
        for s in subs:
            grupos[balde(s.get(campo))].append(s["id"])
        veredicto = []
        for desen in ("churn", "expansion", "contraccion"):
            objetivo = tuvo[desen]
            base = 100.0 * sum(1 for s in subs if s["id"] in objetivo) / n
            filas = []
            fuga = False
            for val, ids in sorted(grupos.items(), key=lambda t: -len(t[1]))[:6]:
                tasa = 100.0 * sum(1 for i in ids if i in objetivo) / len(ids)
                cobertura = 100.0 * len(ids) / n
                marca = ""
                if cobertura >= 20 and (tasa < 2 or tasa > 98):
                    marca = "  <-- SEPARACION CASI PERFECTA"
                    fuga = True
                filas.append("      %-22s n=%4d (%4.1f%%)  tasa=%5.1f%%%s"
                             % (val, len(ids), cobertura, tasa, marca))
            print("   %s (tasa base %.1f%%):" % (desen.upper(), base))
            print("\n".join(filas))
            veredicto.append((desen, fuga))
        vs = ", ".join("%s=%s" % (d, "FUGA" if f else "limpio") for d, f in veredicto)
        print("   VEREDICTO: %s\n" % vs)


if __name__ == "__main__":
    main()
