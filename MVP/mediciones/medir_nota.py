"""Mide la nota interna (la calificacion que el CS escribe en la cuenta) contra
los TRES desenlaces. Estaba clasificada como 'texto/ruido' — error mio: no es
ruido, es la calificacion de la cuenta.

Se mide por LARGO de la nota, no por su contenido: el largo dice si la cuenta
fue trabajada y calificada o si nadie la toco. El contenido en si no se usa
(seria texto libre imposible de meter a un modelo lineal, ademas de tener datos
de clientes)."""
import collections, json, os, re

from rutas import MAESTRO


def idv(v):
    return v[0] if isinstance(v, list) else v


def largo(s):
    """Largo del texto plano; internal_note_display viene en HTML."""
    if not s or not isinstance(s, str):
        return 0
    return len(re.sub(r"<[^>]+>", "", s).strip())


def tramo(n):
    if n == 0: return "0 sin nota"
    if n < 100: return "1 1-99"
    if n < 500: return "2 100-499"
    if n < 2000: return "3 500-1999"
    return "4 2000+"


def main():
    foto = json.load(open(os.path.join(MAESTRO, "foto_maestra.json")))
    ev = json.load(open(os.path.join(MAESTRO, "eventos_maestros.json")))
    tuvo = {t: set() for t in ("churn", "expansion", "contraccion")}
    mapa = {"2_churn": "churn", "1_expansion": "expansion", "15_contraction": "contraccion"}
    for e in ev:
        t = mapa.get(e.get("event_type"))
        if t: tuvo[t].add(idv(e.get("order_id")))

    subs = [s for s in foto if s.get("subscription_state") in ("3_progress", "6_churn")]
    g = collections.defaultdict(list)
    for s in subs:
        g[tramo(largo(s.get("internal_note_display")))].append(s["id"])

    print("Universo: %d suscripciones | con nota: %d (%.0f%%)\n"
          % (len(subs), sum(len(v) for k, v in g.items() if not k.startswith("0")),
             100 * sum(len(v) for k, v in g.items() if not k.startswith("0")) / len(subs)))
    print("%-12s %6s | %9s %9s %9s" % ("largo nota", "n", "churn", "expansion", "contrac"))
    for k in sorted(g):
        ids = g[k]
        r = [100.0 * sum(1 for i in ids if i in tuvo[d]) / len(ids)
             for d in ("churn", "expansion", "contraccion")]
        print("%-12s %6d | %8.1f%% %8.1f%% %8.1f%%" % (k[2:], len(ids), r[0], r[1], r[2]))

    print("\nMuestra real de notas (recortada a 90 caracteres, sin datos de contacto):")
    vistos = 0
    for s in subs:
        t = re.sub(r"<[^>]+>", " ", s.get("internal_note_display") or "")
        t = re.sub(r"\s+", " ", t).strip()
        if len(t) > 120 and vistos < 4:
            print("   [%s] %s..." % (s.get("_gram"), t[:90]))
            vistos += 1


if __name__ == "__main__":
    main()
