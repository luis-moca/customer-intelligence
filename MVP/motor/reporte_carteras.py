"""
REPORTE DESCRIPTIVO POR CARTERA — aritmetica y estadistica pura, cero modelo.

Lee SOLO maestro/ (la fuente unica verificada con 25 pruebas) y produce:
   reportes/<gram>.md          un reporte completo por cartera (9)
   reportes/_comparativo.md    la tabla que cruza las 9 contra el promedio

Reglas que obedece:
 - Los 3 desenlaces siempre (expansion, contraccion, churn), nunca uno solo.
 - Cada porcentaje dice sobre QUE base se calculo (total o submuestra).
 - Dinero normalizado a USD con 18.74 MXN/USD (fijado por Luis). Las 2
   cuentas en EUR se excluyen de agregados de dinero y se reportan aparte.
 - Churn atribuido de DOS formas: al dueño actual de la cartera y a quien
   tenia la cuenta cuando ocurrio (user_id del evento en el log).
"""
import collections
import datetime
import json
import os
import statistics

from rutas import MAESTRO

REPORTES = os.path.join(os.path.dirname(__file__), "reportes")
FX_MXN = 18.74
HOY = datetime.date(2026, 8, 22)  # fecha del export, no "hoy" movil


def idv(v):
    return v[0] if isinstance(v, list) else v


def nom(v):
    return v[1] if isinstance(v, list) and len(v) > 1 else None


def fecha(t):
    try:
        return datetime.date.fromisoformat(str(t)[:10])
    except (ValueError, TypeError):
        return None


def usd(monto, moneda):
    if moneda == "USD":
        return monto
    if moneda == "MXN":
        return monto / FX_MXN
    return None  # EUR u otra: fuera de agregados


def pct(parte, total):
    return 100.0 * parte / total if total else 0.0


def mediana(vals):
    return statistics.median(vals) if vals else 0


def main():
    os.makedirs(REPORTES, exist_ok=True)
    foto = json.load(open(os.path.join(MAESTRO, "foto_maestra.json")))
    eventos = json.load(open(os.path.join(MAESTRO, "eventos_maestros.json")))
    conexiones = json.load(open(os.path.join(MAESTRO, "conexiones_maestras.json")))

    grams = sorted({f["_gram"] for f in foto})

    # --- indices globales ---
    ev_por_orden = collections.defaultdict(list)
    for e in eventos:
        oid = idv(e.get("order_id"))
        if oid is not None:
            ev_por_orden[oid].append(e)
    for lst in ev_por_orden.values():
        lst.sort(key=lambda e: (str(e.get("event_date")), e.get("id") or 0))

    conex_por_orden = {}
    for c in conexiones:
        oid = idv(c.get("subscription_id"))
        if oid is not None:
            conex_por_orden[oid] = c

    # dueño (uid) por cartera = el user_id dominante en su foto
    uid_de_gram = {}
    for g in grams:
        cnt = collections.Counter(idv(f.get("user_id")) for f in foto
                                  if f["_gram"] == g and f.get("user_id"))
        uid_de_gram[g] = cnt.most_common(1)[0][0]

    stats = {}

    for g in grams:
        filas = [f for f in foto if f["_gram"] == g]
        activas = [f for f in filas if str(f.get("subscription_state")) == "3_progress"]
        churn = [f for f in filas if str(f.get("subscription_state")) == "6_churn"]
        s = {"filas": len(filas), "activas": len(activas), "churn": len(churn)}
        s["clientes"] = len({idv(f.get("partner_id")) for f in filas if f.get("partner_id")})

        # --- dinero (solo activas; churneadas tienen MRR congelado en 0/ultimo) ---
        monedas = collections.Counter(nom(f.get("currency_id")) for f in filas)
        s["monedas"] = dict(monedas)
        mrr_usd = []
        eur_n = 0
        for f in activas:
            m = usd(f.get("recurring_monthly") or 0.0, nom(f.get("currency_id")))
            if m is None:
                eur_n += 1
            else:
                mrr_usd.append(m)
        s["eur_excluidas"] = eur_n
        s["mrr_total"] = sum(mrr_usd)
        s["mrr_prom"] = statistics.mean(mrr_usd) if mrr_usd else 0
        s["mrr_mediana"] = mediana(mrr_usd)
        top = sorted(mrr_usd, reverse=True)[:max(1, len(mrr_usd) // 10)]
        s["concentracion_top10"] = pct(sum(top), sum(mrr_usd))

        # --- desenlaces por el log (alguna vez, ventana comun 3 anios) ---
        res = {"expansion": 0, "contraccion": 0, "churn_log": 0}
        churn_propio = 0
        churn_heredado = 0
        gan_exp, per_con, per_chu = 0.0, 0.0, 0.0
        for f in filas:
            evs = ev_por_orden.get(f["id"], [])
            tipos = {str(e.get("event_type")) for e in evs}
            if "1_expansion" in tipos:
                res["expansion"] += 1
            if "15_contraction" in tipos:
                res["contraccion"] += 1
            if "2_churn" in tipos:
                res["churn_log"] += 1
            moneda = nom(f.get("currency_id"))
            for e in evs:
                t = str(e.get("event_type"))
                monto = usd(e.get("amount_signed") or 0.0, moneda)
                if monto is None:
                    continue
                if t == "1_expansion":
                    gan_exp += monto
                elif t == "15_contraction":
                    per_con += monto  # viene negativo
                elif t == "2_churn":
                    per_chu += monto  # viene negativo
                    if idv(e.get("user_id")) == uid_de_gram[g]:
                        churn_propio += 1
                    else:
                        churn_heredado += 1
        s.update(res)
        s["churn_propio"] = churn_propio
        s["churn_heredado"] = churn_heredado
        s["mrr_ganado_exp"] = gan_exp
        s["mrr_perdido_con"] = per_con
        s["mrr_perdido_chu"] = per_chu
        s["mrr_neto"] = gan_exp + per_con + per_chu

        # --- antiguedad (de first_contract_date, nunca del log) ---
        ants = []
        for f in filas:
            ini = fecha(f.get("first_contract_date"))
            if ini:
                ants.append((HOY - ini).days / 365.25)
        s["antiguedad_mediana"] = mediana(ants)
        s["antiguedad_max"] = max(ants) if ants else 0

        # --- silencio: dias sin ningun evento (solo activas) ---
        sil = []
        for f in activas:
            evs = ev_por_orden.get(f["id"], [])
            if evs:
                ult = fecha(evs[-1].get("event_date"))
                if ult:
                    sil.append((HOY - ult).days)
        s["silencio_mediana"] = mediana(sil)
        s["silencio_180"] = pct(sum(1 for d in sil if d >= 180), len(sil))

        # --- plan: duracion y standard/custom ---
        dur = collections.Counter(nom(f.get("plan_id")) for f in filas)
        s["planes"] = dict(dur.most_common())
        tipo = collections.Counter()
        for f in filas:
            t = nom(f.get("sale_order_template_id")) or ""
            if "Custom" in t:
                tipo["Custom"] += 1
            elif "Standard" in t:
                tipo["Standard"] += 1
            else:
                tipo["(sin plantilla)"] += 1
        s["tipo_plan"] = dict(tipo)

        # --- industria: fill + distribucion sobre las que la tienen ---
        con_ind = [nom(f.get("industry_id")) for f in filas if f.get("industry_id")]
        s["industria_fill"] = pct(len(con_ind), len(filas))
        s["industrias"] = collections.Counter(con_ind).most_common(5)

        # --- hosting y version (foto + conexiones) ---
        s["hosting"] = dict(collections.Counter(f.get("hosting") for f in filas))
        vers = collections.Counter()
        gap_uso = []
        cnx_viejas = 0
        cnx_total = 0
        for f in activas:
            c = conex_por_orden.get(f["id"])
            if not c:
                continue
            cnx_total += 1
            if c.get("version"):
                vers[str(c["version"])] += 1
            comprados = c.get("quantity") or 0
            act_u = c.get("nbr_active_regular_users") or 0
            if comprados:
                gap_uso.append(act_u / comprados)
            lcd = fecha(c.get("last_cnx_date"))
            if lcd and (HOY - lcd).days >= 30:
                cnx_viejas += 1
        s["versiones"] = vers.most_common(4)
        s["uso_prom"] = 100 * statistics.mean(gap_uso) if gap_uso else None
        s["sin_conectar_30d"] = pct(cnx_viejas, cnx_total)
        s["con_dato_conexion"] = cnx_total

        # --- cruces: plan x desenlace / mrr x desenlace / antiguedad x churn ---
        s["cruces"] = {}
        def cruce(nombre, particion):
            tabla = []
            for etiqueta, grupo in particion:
                if len(grupo) < 15:
                    continue
                n = len(grupo)
                e_ = pct(sum(1 for f in grupo if "1_expansion" in
                             {str(e.get("event_type")) for e in ev_por_orden.get(f["id"], [])}), n)
                c_ = pct(sum(1 for f in grupo if "15_contraction" in
                             {str(e.get("event_type")) for e in ev_por_orden.get(f["id"], [])}), n)
                ch = pct(sum(1 for f in grupo if str(f.get("subscription_state")) == "6_churn"), n)
                tabla.append((etiqueta, n, e_, c_, ch))
            s["cruces"][nombre] = tabla

        cruce("Duracion de plan", [(p, [f for f in filas if nom(f.get("plan_id")) == p])
                                  for p, _ in dur.most_common(6)])
        cruce("Standard vs Custom", [(t, [f for f in filas
                                          if (("Custom" in (nom(f.get("sale_order_template_id")) or "")) == (t == "Custom"))])
                                     for t in ("Custom", "Standard")])
        mrrs = sorted(filas, key=lambda f: usd(f.get("recurring_monthly") or 0,
                                               nom(f.get("currency_id"))) or 0)
        terc = max(1, len(mrrs) // 3)
        cruce("Tamano de MRR", [("tercio bajo", mrrs[:terc]),
                                ("tercio medio", mrrs[terc:2 * terc]),
                                ("tercio alto", mrrs[2 * terc:])])
        def edad(f):
            ini = fecha(f.get("first_contract_date"))
            return (HOY - ini).days / 365.25 if ini else None
        cruce("Antiguedad", [("menos de 1 anio", [f for f in filas if (edad(f) or 99) < 1]),
                             ("1 a 3 anios", [f for f in filas if 1 <= (edad(f) or 99) < 3]),
                             ("3+ anios", [f for f in filas if (edad(f) or 0) >= 3])])

        stats[g] = s

    # ================== escribir reportes ==================
    prom = {}
    for k in ("mrr_prom", "silencio_mediana", "concentracion_top10", "antiguedad_mediana"):
        prom[k] = statistics.mean(stats[g][k] for g in grams)
    prom["tasa_churn"] = statistics.mean(pct(stats[g]["churn"], stats[g]["filas"]) for g in grams)
    prom["tasa_exp"] = statistics.mean(pct(stats[g]["expansion"], stats[g]["filas"]) for g in grams)
    prom["tasa_con"] = statistics.mean(pct(stats[g]["contraccion"], stats[g]["filas"]) for g in grams)

    for g in grams:
        s = stats[g]
        L = []
        L.append("# Cartera %s — reporte descriptivo\n" % g)
        L.append("Fuente: maestro/ (verificado). Fecha de corte: %s. Dinero en USD (MXN/18.74).\n" % HOY)
        L.append("## Tamano\n")
        L.append("- Cuentas reales: **%d** (%d activas + %d churneadas) | Clientes unicos: %d" %
                 (s["filas"], s["activas"], s["churn"], s["clientes"]))
        L.append("- Monedas: %s%s" % (s["monedas"],
                 " | %d cuentas EUR excluidas de agregados de dinero" % s["eur_excluidas"] if s["eur_excluidas"] else ""))
        L.append("\n## Dinero (solo activas)\n")
        L.append("- MRR total: **$%s USD** | promedio $%.0f (equipo: $%.0f) | mediana $%.0f" %
                 (format(round(s["mrr_total"]), ","), s["mrr_prom"], prom["mrr_prom"], s["mrr_mediana"]))
        L.append("- Concentracion: el top 10%% de cuentas trae el **%.0f%%** del MRR (equipo: %.0f%%)" %
                 (s["concentracion_top10"], prom["concentracion_top10"]))
        L.append("\n## Los 3 desenlaces (ventana comun de 3 anios, %% sobre las %d cuentas)\n" % s["filas"])
        L.append("- Expansion: **%.1f%%** (equipo %.1f%%) | Contraccion: **%.1f%%** (equipo %.1f%%) | Churn: **%.1f%%** (equipo %.1f%%)" %
                 (pct(s["expansion"], s["filas"]), prom["tasa_exp"],
                  pct(s["contraccion"], s["filas"]), prom["tasa_con"],
                  pct(s["churn"], s["filas"]), prom["tasa_churn"]))
        L.append("- Balance de MRR en la ventana: gano $%s por expansion, perdio $%s por contraccion y $%s por churn -> neto **$%s USD**" %
                 (format(round(s["mrr_ganado_exp"]), ","), format(round(-s["mrr_perdido_con"]), ","),
                  format(round(-s["mrr_perdido_chu"]), ","), format(round(s["mrr_neto"]), ",")))
        tot_ch_ev = s["churn_propio"] + s["churn_heredado"]
        if tot_ch_ev:
            L.append("- Atribucion del churn: %d ocurrieron bajo el dueño actual, **%d son heredados** (ocurrieron bajo otro dueño) — %.0f%% del churn de esta cartera no es de su gestion" %
                     (s["churn_propio"], s["churn_heredado"], pct(s["churn_heredado"], tot_ch_ev)))
        L.append("\n## Antiguedad y silencio\n")
        L.append("- Antiguedad mediana del cliente: **%.1f anios** (equipo %.1f) | el mas viejo: %.1f anios" %
                 (s["antiguedad_mediana"], prom["antiguedad_mediana"], s["antiguedad_max"]))
        L.append("- Silencio (activas sin ningun evento): mediana **%d dias** (equipo %d) | %.0f%% llevan 180+ dias sin un solo evento" %
                 (s["silencio_mediana"], prom["silencio_mediana"], s["silencio_180"]))
        L.append("\n## Mix de plan\n")
        L.append("- Por duracion: %s" % ", ".join("%s %.0f%%" % (p, pct(n, s["filas"]))
                                                  for p, n in list(s["planes"].items())[:5]))
        L.append("- Standard vs Custom: %s" % ", ".join("%s %.0f%%" % (t, pct(n, s["filas"]))
                                                        for t, n in s["tipo_plan"].items()))
        L.append("- Hosting: %s" % ", ".join("%s %.0f%%" % (h, pct(n, s["filas"]))
                                             for h, n in s["hosting"].items()))
        L.append("\n## Industria\n")
        L.append("- Registrada en el **%.0f%%** de la cartera. Sobre esas: %s" %
                 (s["industria_fill"],
                  ", ".join("%s (%d)" % (i, n) for i, n in s["industrias"])))
        L.append("\n## Uso real (de %d activas con dato de conexion)\n" % s["con_dato_conexion"])
        if s["uso_prom"] is not None:
            L.append("- Usuarios activos vs comprados: **%.0f%%** de aprovechamiento promedio" % s["uso_prom"])
        L.append("- **%.0f%%** de las activas llevan 30+ dias sin que nadie entre a su base" % s["sin_conectar_30d"])
        L.append("- Versiones de Odoo mas comunes: %s" % ", ".join("%s (%d)" % (v, n) for v, n in s["versiones"]))
        L.append("\n## Cruces (n, %exp, %con, %churn)\n")
        for nombre, tabla in s["cruces"].items():
            L.append("**%s**\n" % nombre)
            L.append("| segmento | n | expansion | contraccion | churn |")
            L.append("|---|---|---|---|---|")
            for etiqueta, n, e_, c_, ch in tabla:
                L.append("| %s | %d | %.1f%% | %.1f%% | %.1f%% |" % (etiqueta, n, e_, c_, ch))
            L.append("")
        with open(os.path.join(REPORTES, "%s.md" % g), "w") as fh:
            fh.write("\n".join(L) + "\n")

    # ---------- comparativo ----------
    C = ["# Comparativo de las 9 carteras\n",
         "Fuente: maestro/. USD a 18.74. Los 3 desenlaces sobre la ventana comun de 3 anios.\n",
         "| Metrica | " + " | ".join(grams) + " | promedio |",
         "|---|" + "---|" * (len(grams) + 1)]
    def fila(nombre, fn, fmt="%.1f"):
        vals = [fn(stats[g]) for g in grams]
        p = statistics.mean(vals)
        C.append("| %s | " % nombre + " | ".join(fmt % v for v in vals) + " | " + fmt % p + " |")
    fila("Cuentas reales", lambda s: s["filas"], "%d")
    fila("Activas", lambda s: s["activas"], "%d")
    fila("Churn %", lambda s: pct(s["churn"], s["filas"]))
    fila("Expansion %", lambda s: pct(s["expansion"], s["filas"]))
    fila("Contraccion %", lambda s: pct(s["contraccion"], s["filas"]))
    fila("Churn heredado %", lambda s: pct(s["churn_heredado"], (s["churn_propio"] + s["churn_heredado"]) or 1))
    fila("MRR total (kUSD)", lambda s: s["mrr_total"] / 1000, "%.0f")
    fila("MRR promedio (USD)", lambda s: s["mrr_prom"], "%.0f")
    fila("Concentracion top10 %", lambda s: s["concentracion_top10"], "%.0f")
    fila("MRR neto ventana (kUSD)", lambda s: s["mrr_neto"] / 1000, "%+.0f")
    fila("Antiguedad mediana (anios)", lambda s: s["antiguedad_mediana"])
    fila("Silencio mediano (dias)", lambda s: s["silencio_mediana"], "%d")
    fila("Activas 180+ dias sin evento %", lambda s: s["silencio_180"], "%.0f")
    fila("Sin conectarse 30+ dias %", lambda s: s["sin_conectar_30d"], "%.0f")
    fila("Uso (activos/comprados) %", lambda s: s["uso_prom"] or 0, "%.0f")
    fila("Custom %", lambda s: pct(s["tipo_plan"].get("Custom", 0), s["filas"]), "%.0f")
    fila("Industria registrada %", lambda s: s["industria_fill"], "%.0f")
    with open(os.path.join(REPORTES, "_comparativo.md"), "w") as fh:
        fh.write("\n".join(C) + "\n")

    print("Listo: %d reportes individuales + _comparativo.md en %s" % (len(grams), REPORTES))


if __name__ == "__main__":
    main()
