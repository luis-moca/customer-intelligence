"""
FASE 1 — Consolidacion. Aprobada por Luis el 22-ago-2026.

Junta las 9 carteras de salida/ en 3 archivos maestros. Solo lee archivos
locales, no toca Odoo. Se detiene aqui: no arma el panel cuenta-mes (Fase 2),
eso espera aprobacion aparte.

Decisiones tomadas, documentadas tambien en maestro/DECISIONES.txt:

1. foto_maestra EXCLUYE subscription_state='5_renewed' (el "papeleo": contratos
   viejos ya reemplazados por otro). Quedan solo cuentas reales: activas o
   churneadas. Instruccion explicita de Luis al aprobar el plan de Fase 1.

2. eventos_maestros y conexiones_maestras NO se filtran igual — se quedan
   COMPLETOS, incluyendo eventos/conexiones de ordenes renovadas. Se necesitan
   completos para reconstruir en Fase 2 la linea de tiempo continua por
   cliente (decision de Luis: reasignacion de cartera = una sola linea de
   tiempo, no partida por dueño — necesita ver el antes Y el despues de cada
   renovacion).

3. El log se recorta a la ventana mas restrictiva (2023-08-23) en las 9
   carteras, incluyendo luram (que venia sin cortar desde 2020). Sin esto,
   la cartera de Luis se veria artificialmente mas rica en eventos solo por
   haberse exportado con mas historia.

4. Clientes que aparecen en mas de una cartera (reasignacion de enero) NO se
   fusionan ni se borran aqui — se documentan y se quedan tal cual, cada fila
   con su gram de origen. Fusionar esas historias es trabajo de Fase 2.

5. upsell_content SOLO existe en luram (133 campos vs 132 en el resto, por el
   bug de lote que obligo a leerlo aparte). No se rellena con nulo fabricado
   para los demas ni se elimina de luram: se documenta la asimetria tal cual.
"""
import collections
import json
import os

CARPETA_SALIDA = os.path.join(os.path.dirname(__file__), "salida")
from rutas import MAESTRO as CARPETA_MAESTRO

VENTANA_LOG = "2023-08-23"
GRAMS = ["luram", "edara", "falg", "mnav", "queb", "mseb", "lusan", "lgcr", "mjmc"]


def cargar(gram, sufijo):
    ruta = os.path.join(CARPETA_SALIDA, gram, "%s_%s.json" % (gram, sufijo))
    with open(ruta) as f:
        return json.load(f)


def idv(v):
    return v[0] if isinstance(v, list) else v


def main():
    os.makedirs(CARPETA_MAESTRO, exist_ok=True)
    reporte = []

    def log(linea):
        print(linea)
        reporte.append(linea)

    log("=== FASE 1 — Consolidacion (%d carteras) ===\n" % len(GRAMS))

    # ---------- 1. foto_maestra ----------
    foto_todas = []
    renovadas_excluidas = collections.Counter()
    reales_por_gram = collections.Counter()
    campos_por_gram = {}

    for gram in GRAMS:
        datos = cargar(gram, "foto")
        campos_por_gram[gram] = set(datos[0].keys()) if datos else set()
        for fila in datos:
            fila = dict(fila)
            fila["_gram"] = gram
            if str(fila.get("subscription_state")) == "5_renewed":
                renovadas_excluidas[gram] += 1
                continue
            reales_por_gram[gram] += 1
            foto_todas.append(fila)

    log("--- foto_maestra ---")
    for gram in GRAMS:
        log("   %-8s reales=%4d   renovadas excluidas=%4d"
            % (gram, reales_por_gram[gram], renovadas_excluidas[gram]))
    log("   TOTAL reales consolidadas: %d" % len(foto_todas))
    log("   TOTAL renovadas excluidas: %d\n" % sum(renovadas_excluidas.values()))

    # Sanity check: ids duplicados (no deberia haber, los dominios son
    # mutuamente excluyentes por vendedor)
    ids = [f["id"] for f in foto_todas]
    dup_ids = [i for i, n in collections.Counter(ids).items() if n > 1]
    log("Chequeo de duplicados de 'id' en foto_maestra: %d encontrados%s"
        % (len(dup_ids), (" -> %s" % dup_ids[:10]) if dup_ids else " (OK)"))

    # Campos: confirmar simetria 132 vs 133 (upsell_content solo en luram)
    todos_los_campos = set.union(*campos_por_gram.values())
    for gram in GRAMS:
        faltantes = todos_los_campos - campos_por_gram[gram] - {"_gram"}
        if faltantes:
            log("   [asimetria] %s no trae: %s" % (gram, sorted(faltantes)))

    # Clientes repetidos entre carteras (solo se documenta, no se toca)
    partner_a_grams = collections.defaultdict(set)
    for f in foto_todas:
        pid = idv(f.get("partner_id"))
        if pid:
            partner_a_grams[pid].add(f["_gram"])
    compartidos = {p: sorted(g) for p, g in partner_a_grams.items() if len(g) > 1}
    log("\nClientes con presencia en mas de 1 cartera: %d de %d unicos\n"
        % (len(compartidos), len(partner_a_grams)))

    with open(os.path.join(CARPETA_MAESTRO, "foto_maestra.json"), "w") as f:
        json.dump(foto_todas, f, ensure_ascii=False, indent=2)

    # ---------- 2. eventos_maestros ----------
    eventos_todos = []
    antes_del_corte = collections.Counter()
    despues_del_corte = collections.Counter()

    for gram in GRAMS:
        datos = cargar(gram, "eventos_log")
        for ev in datos:
            fecha = str(ev.get("event_date"))[:10]
            if fecha < VENTANA_LOG:
                antes_del_corte[gram] += 1
                continue
            despues_del_corte[gram] += 1
            ev = dict(ev)
            ev["_gram"] = gram
            eventos_todos.append(ev)

    log("--- eventos_maestros (ventana comun desde %s) ---" % VENTANA_LOG)
    for gram in GRAMS:
        log("   %-8s dentro de ventana=%5d   recortados=%4d"
            % (gram, despues_del_corte[gram], antes_del_corte[gram]))
    log("   TOTAL eventos consolidados: %d\n" % len(eventos_todos))

    with open(os.path.join(CARPETA_MAESTRO, "eventos_maestros.json"), "w") as f:
        json.dump(eventos_todos, f, ensure_ascii=False, indent=2)

    # ---------- 3. conexiones_maestras ----------
    conexiones_todas = []
    for gram in GRAMS:
        datos = cargar(gram, "conexiones")
        for c in datos:
            c = dict(c)
            c["_gram"] = gram
            conexiones_todas.append(c)

    log("--- conexiones_maestras ---")
    log("   TOTAL conexiones consolidadas: %d\n" % len(conexiones_todas))

    with open(os.path.join(CARPETA_MAESTRO, "conexiones_maestras.json"), "w") as f:
        json.dump(conexiones_todas, f, ensure_ascii=False, indent=2)

    # ---------- Documentacion ----------
    with open(os.path.join(CARPETA_MAESTRO, "DECISIONES.txt"), "w") as f:
        f.write("\n".join(reporte) + "\n")

    log("Guardado en: %s" % CARPETA_MAESTRO)


if __name__ == "__main__":
    main()
