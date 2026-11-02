"""Encuentra QUE forma de medir la trayectoria del MRR discrimina mejor.

Motivo (Luis, 22-ago-2026, validando 6309555 y 6196485): num_contracciones
cuenta eventos sin mirar monto ni antiguedad. Una cuenta que crecio de $27 a
$449 MRR en 15 meses acumulo 3 contracciones de -$13, -$3 y -$13 — migajas
dentro de un crecimiento de 16x — y el modelo la marco como riesgo de
downgrade. Contar sin contexto es el mismo error que el aniversario.

No se asume la ventana correcta: se prueban TODAS (1, 3, 6, 9, 12 meses,
contra el pico, ponderadas por monto, recientes vs viejas) contra los TRES
desenlaces sobre las 9 carteras, y gana la que mida mejor.

Metrica: se parte cada variable en quintiles y se mide cuanto separa la tasa
del desenlace entre el quintil mas alto y el mas bajo. Una variable que no
separa nada da ~1.0x; una que separa de verdad da 2x, 3x o mas.
"""
import collections
import json
import os

from rutas import MAESTRO

OBJETIVOS = [("etiqueta_expansion_90d", "EXPANSION"),
             ("etiqueta_contraccion_90d", "CONTRACCION"),
             ("etiqueta_churn_120d", "CHURN")]


def idv(v):
    return v[0] if isinstance(v, list) else v


def a_fecha(t):
    import datetime
    return datetime.date.fromisoformat(str(t)[:10])


def construir_series():
    """MRR y deltas por suscripcion, ordenados en el tiempo."""
    ev = json.load(open(os.path.join(MAESTRO, "eventos_maestros.json")))
    serie = collections.defaultdict(list)
    for e in ev:
        sid = idv(e.get("order_id"))
        if sid is None or not e.get("event_date"):
            continue
        serie[sid].append({
            "fecha": a_fecha(e["event_date"]),
            "id": e.get("id"),
            "tipo": str(e.get("event_type")),
            "mrr": e.get("recurring_monthly") or 0.0,
            "delta": e.get("amount_signed") or 0.0,
        })
    for v in serie.values():
        v.sort(key=lambda e: (e["fecha"], e["id"]))
    return serie


def mrr_en(pasados, fecha):
    prev = [e for e in pasados if e["fecha"] <= fecha]
    return prev[-1]["mrr"] if prev else None


def candidatas(pasados, cierre):
    """Todas las formas de mirar la trayectoria. Solo pasado, nunca futuro."""
    import datetime
    if not pasados:
        return {}
    hoy = pasados[-1]["mrr"]
    out = {}

    # 1) cambio relativo a distintas ventanas
    for meses in (1, 3, 6, 9, 12):
        antes = mrr_en(pasados, cierre - datetime.timedelta(days=30 * meses))
        out["cambio_%dm" % meses] = ((hoy - antes) / antes) if antes else None

    # 2) contra el pico historico: cuanto ha perdido de su mejor momento
    pico = max(e["mrr"] for e in pasados)
    out["vs_pico"] = (hoy / pico) if pico else None

    # 3) contracciones PONDERADAS POR MONTO, no contadas
    neg_total = sum(-e["delta"] for e in pasados if e["delta"] < 0)
    pos_total = sum(e["delta"] for e in pasados if e["delta"] > 0)
    out["monto_contraido_total"] = neg_total
    out["monto_contraido_sobre_mrr"] = (neg_total / hoy) if hoy else None
    out["razon_creci_vs_contrac"] = (pos_total / neg_total) if neg_total else None

    # 4) lo mismo pero SOLO reciente — una contraccion de hace 2 años no pesa
    for meses in (6, 12):
        corte = cierre - datetime.timedelta(days=30 * meses)
        recientes = [e for e in pasados if e["fecha"] > corte]
        neg = sum(-e["delta"] for e in recientes if e["delta"] < 0)
        out["monto_contraido_%dm" % meses] = neg
        out["monto_contraido_%dm_sobre_mrr" % meses] = (neg / hoy) if hoy else None
        out["num_contracciones_%dm" % meses] = sum(
            1 for e in recientes if e["tipo"] == "15_contraction")

    # 5) el control: lo que ya usa el modelo hoy
    out["num_contracciones_TOTAL"] = sum(
        1 for e in pasados if e["tipo"] == "15_contraction")
    return out


def separacion(valores, etiquetas):
    """AUC: probabilidad de que la variable ordene bien un caso positivo
    contra uno negativo tomados al azar.

    Se uso AUC y no "tasa del quintil alto vs bajo" porque esa metrica se
    rompe con variables casi todas en cero (la mayoria de cuentas nunca se
    contrae): el quintil bajo queda en 0% y la division explota. AUC maneja
    los empates promediando rangos, asi que compara peras con peras entre
    una variable densa y una dispersa.

    0.50 = no ordena nada (azar). Se reporta la distancia al azar hacia
    cualquier lado: una variable que ordena AL REVES (AUC 0.30) tambien sirve,
    el modelo solo le pone signo negativo.
    """
    pares = [(v, y) for v, y in zip(valores, etiquetas) if v is not None]
    n_pos = sum(y for _, y in pares)
    n_neg = len(pares) - n_pos
    if len(pares) < 500 or n_pos < 30 or n_neg < 30:
        return None
    pares.sort(key=lambda p: p[0])
    # rangos promediados en los empates
    rangos = [0.0] * len(pares)
    i = 0
    while i < len(pares):
        j = i
        while j + 1 < len(pares) and pares[j + 1][0] == pares[i][0]:
            j += 1
        promedio = (i + j) / 2.0 + 1
        for k in range(i, j + 1):
            rangos[k] = promedio
        i = j + 1
    suma_pos = sum(r for r, (_, y) in zip(rangos, pares) if y)
    auc = (suma_pos - n_pos * (n_pos + 1) / 2.0) / (n_pos * n_neg)
    return auc


def main():
    panel = json.load(open(os.path.join(MAESTRO, "panel_cuenta_mes.json")))
    ent = [f for f in panel if not f["para_puntuar"]]
    serie = construir_series()

    print("Filas evaluadas: %d (9 carteras completas)\n" % len(ent))

    calculadas = []
    for f in ent:
        cierre = a_fecha(f["cierre_mes"])
        pasados = [e for e in serie.get(f["suscripcion_id"], [])
                   if e["fecha"] <= cierre]
        calculadas.append(candidatas(pasados, cierre))

    nombres = sorted({k for c in calculadas for k in c})
    resultados = {}
    for objetivo, etiqueta in OBJETIVOS:
        y = [f[objetivo] for f in ent]
        for nombre in nombres:
            vals = [c.get(nombre) for c in calculadas]
            s = separacion(vals, y)
            if s is not None:
                resultados.setdefault(nombre, {})[etiqueta] = s

    print("AUC por variable (0.500 = azar)\n")
    print("%-36s %10s %11s %8s" % ("variable", "EXPANSION", "CONTRACCION", "CHURN"))
    fuerza = lambda r: max(abs(v - 0.5) for v in r.values()) if r else 0
    orden = sorted(resultados, key=lambda n: -fuerza(resultados[n]))
    for n in orden:
        r = resultados[n]
        marca = " <<< la que usa el modelo hoy" if n == "num_contracciones_TOTAL" else ""
        print("%-36s %10.3f %11.3f %8.3f%s"
              % (n, r.get("EXPANSION", 0.5), r.get("CONTRACCION", 0.5),
                 r.get("CHURN", 0.5), marca))
    print("\n0.500 = azar puro. Mientras mas lejos de 0.500 (arriba o abajo),")
    print("mejor ordena. Debajo de 0.500 ordena al reves, que tambien sirve.")


if __name__ == "__main__":
    main()
