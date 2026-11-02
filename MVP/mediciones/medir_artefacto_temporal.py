"""Segunda prueba, obligatoria para todo campo que solo tenemos en su valor de HOY.

La leccion que la genero: internal_note_display parecia predecir churn brutal
(55.9% -> 13.3%). Era falso. Las cuentas que murieron en 2023 no tienen nota
porque en 2023 nadie escribia notas — no porque la falta de nota las matara.
El valor de hoy carga informacion de CUANDO murio la cuenta.

La prueba: si el campo fuera una propiedad estable, su distribucion seria
parecida entre los churn viejos y los recientes. Si cambia mucho por anio de
muerte, el campo esta contando el calendario, no la cuenta -> no entrena.
"""
import collections
import json
import os

from rutas import MAESTRO

CANDIDATOS = ["maintenance_is_paying", "activity_user_id", "payment_term_id"]
UMBRAL = 25.0  # puntos porcentuales de diferencia entre el churn mas viejo y el mas nuevo


def idv(v):
    return v[0] if isinstance(v, list) else v


def clave(v):
    if v is None or v is False or v == "":
        return "vacio"
    if isinstance(v, list):
        return "id=%s" % idv(v)
    return str(v)[:18]


def main():
    foto = json.load(open(os.path.join(MAESTRO, "foto_maestra.json")))
    ev = json.load(open(os.path.join(MAESTRO, "eventos_maestros.json")))
    anio_churn = {}
    for e in ev:
        if e.get("event_type") == "2_churn":
            anio_churn[idv(e.get("order_id"))] = str(e["event_date"])[:4]

    grupos = collections.defaultdict(list)
    for s in foto:
        if s.get("subscription_state") == "6_churn" and s["id"] in anio_churn:
            grupos[anio_churn[s["id"]]].append(s)
        elif s.get("subscription_state") == "3_progress":
            grupos["ACTIVAS"].append(s)
    anios = sorted(a for a in grupos if a != "ACTIVAS")

    for campo in CANDIDATOS:
        print("=" * 74)
        print("CAMPO: %s" % campo)
        # valor mas comun global, y como cambia su presencia por anio de muerte
        todos = collections.Counter(clave(s.get(campo)) for g in grupos.values() for s in g)
        dominante = todos.most_common(1)[0][0]
        print("   valor mas comun: %s" % dominante)
        pct = {}
        for a in anios + ["ACTIVAS"]:
            g = grupos[a]
            pct[a] = 100.0 * sum(1 for s in g if clave(s.get(campo)) == dominante) / len(g)
            print("      %-8s n=%4d  %% con el valor comun = %5.1f%%" % (a, len(g), pct[a]))
        rango = max(pct[a] for a in anios) - min(pct[a] for a in anios)
        veredicto = "ARTEFACTO TEMPORAL (no entrena)" if rango > UMBRAL else "estable (puede entrenar)"
        print("   variacion entre anios de muerte: %.1f puntos -> %s\n" % (rango, veredicto))


if __name__ == "__main__":
    main()
