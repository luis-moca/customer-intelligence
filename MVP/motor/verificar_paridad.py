"""PRUEBA: el dashboard y Python dan EXACTAMENTE lo mismo, cartera por cartera.

POR QUE EXISTE
--------------
El calculo de features desde el export crudo esta escrito dos veces: en Python
(panel_fase2.py) y a mano en JavaScript (dentro de index.html). Todo lo que es
matematica pura viaja como DATO en modelo.json y no puede desincronizarse —
pero esa parte portada a mano SI puede. El dia que una cambie y la otra no, el
dashboard miente sin avisar y nadie se entera.

Hasta el 23-ago-2026 esto se verificaba A MANO, cargando el archivo en un
navegador y comparando. Servia una vez; no servia para mañana. Esto lo vuelve
una prueba que corre sola.

LO IMPORTANTE — POR QUE **CARTERA POR CARTERA** Y NO SOBRE EL MAESTRO
---------------------------------------------------------------------
De los 6 bugs que aparecieron el 23-ago-2026, TRES solo se manifiestan al
puntuar UNA cartera sola:

  - la ventana del panel se calculaba desde los datos de esa cartera, asi que
    "hoy" cambiaba segun de quien fuera el archivo;
  - el desempate entre pings del mismo dia;
  - el desempate entre variables con el mismo peso en el texto del "por que".

Ninguno se ve trabajando contra el maestro consolidado — y una cartera sola es
EXACTAMENTE lo que hace cada persona con su archivo. Por eso esta prueba corre
sobre los exports individuales, nunca sobre el maestro.

COMO CORRE EL JAVASCRIPT SIN NAVEGADOR
---------------------------------------
macOS trae JavaScriptCore, al que se llega con `osascript -l JavaScript`. No
hace falta instalar Node ni abrir Chrome. Se extrae del index.html el bloque
entre /*__MOTOR_INICIO__*/ y /*__MOTOR_FIN__*/ (el motor puro, sin nada de
pantalla) mas el MODELO embebido, y se corre tal cual: es el MISMO codigo que
ejecuta el navegador, no una copia.

Uso:
    python3 verificar_paridad.py            # todas las carteras en salida/
    python3 verificar_paridad.py luesp      # una sola

Devuelve codigo 0 si todo coincide, 1 si hay una sola diferencia — para que
pueda encadenarse con otras pruebas.
"""
import json
import os
import re
import subprocess
import sys
import tempfile

from rutas import MAESTRO  # noqa: F401  (deja motor/ en el camino de busqueda)

AQUI = os.path.dirname(os.path.abspath(__file__))


def _carpeta_salida():
    """Donde viven los <gram>_export.json, corra esto desde Motor/ o desde MVP/.

    En el paquete de traspaso los scripts estan en MVP/motor/ pero los exports
    siguen en Motor/salida/ — se prueban las dos en vez de asumir una. Si no
    encuentra ninguna, esta prueba NO puede dar un OK vacio (ver main()).
    """
    for ruta in (os.path.join(AQUI, "salida"),
                 os.path.join(AQUI, "..", "..", "Motor", "salida")):
        if os.path.isdir(ruta):
            return os.path.normpath(ruta)
    return os.path.join(AQUI, "salida")   # no existe; main() lo reporta


SALIDA = _carpeta_salida()
TOLERANCIA = 0.0001   # las probabilidades se guardan con 4 decimales

# Todo lo que el dashboard muestra o usa para decidir. Si alguno difiere, el
# usuario ve algo distinto a lo que dice Python — no importa cual "tenga razon".
CAMPOS_EXACTOS = ["cliente", "codigo", "orden", "gram", "acciones",
                  "porque_churn", "porque_expansion", "porque_contraccion",
                  "cuenta_llena", "excluida", "nota_largo_plazo"]
CAMPOS_NUMERICOS = ["p_churn", "p_expansion", "p_contraccion", "mrr"]


def _carpeta_dashboard():
    for ruta in (os.path.join(AQUI, "..", "MVP", "dashboard"),
                 os.path.join(AQUI, "..", "dashboard")):
        if os.path.isdir(ruta):
            return ruta
    raise SystemExit("No encontre la carpeta dashboard/.")


def motor_javascript():
    """Saca del index.html el MODELO y el motor puro, tal cual los corre el navegador."""
    index = os.path.join(_carpeta_dashboard(), "index.html")
    html = open(index).read()

    modelo = re.search(r'const MODELO = /\*__MODELO_JSON__\*/.*?;\n', html, re.S)
    motor = re.search(r'/\*__MOTOR_INICIO__\*/(.*?)/\*__MOTOR_FIN__\*/', html, re.S)
    if not modelo or not motor:
        raise SystemExit(
            "No encontre los marcadores del motor en index.html.\n"
            "Deben existir /*__MODELO_JSON__*/, /*__MOTOR_INICIO__*/ y "
            "/*__MOTOR_FIN__*/ — sin ellos esta prueba no puede correr.")
    return modelo.group(0) + motor.group(1)


def puntuar_con_javascript(js_motor, ruta_export):
    """Corre el motor del dashboard sobre un export y devuelve sus cuentas."""
    with tempfile.TemporaryDirectory() as tmp:
        salida = os.path.join(tmp, "resultado.json")
        script = os.path.join(tmp, "correr.js")
        with open(script, "w") as fh:
            fh.write(js_motor + """
var texto = $.NSString.stringWithContentsOfFileEncodingError(%s, 4, $());
var cuentas = puntuarLocal(JSON.parse(ObjC.unwrap(texto)), MODELO);
$.NSString.alloc.initWithUTF8String(JSON.stringify(cuentas))
 .writeToFileAtomicallyEncodingError(%s, true, 4, $());
"undefined";
""" % (json.dumps(ruta_export), json.dumps(salida)))

        r = subprocess.run(["osascript", "-l", "JavaScript", script],
                           capture_output=True, text=True)
        if r.returncode != 0 or not os.path.exists(salida):
            raise SystemExit("El motor de JavaScript fallo:\n%s" % (r.stderr or r.stdout))
        return json.load(open(salida))


def comparar(py, js):
    """Diferencias entre las dos listas de cuentas, campo por campo."""
    P = {c["suscripcion_id"]: c for c in py}
    J = {c["suscripcion_id"]: c for c in js}
    difs = []
    peor = 0.0

    for sid in sorted(set(P) | set(J)):
        if sid not in J:
            difs.append((sid, "solo en Python", None, None))
            continue
        if sid not in P:
            difs.append((sid, "solo en el dashboard", None, None))
            continue
        a, b = P[sid], J[sid]
        for campo in CAMPOS_NUMERICOS:
            d = abs((a.get(campo) or 0) - (b.get(campo) or 0))
            peor = max(peor, d)
            if d > TOLERANCIA:
                difs.append((sid, campo, a.get(campo), b.get(campo)))
        for campo in CAMPOS_EXACTOS:
            va, vb = a.get(campo), b.get(campo)
            if campo == "acciones":
                va, vb = sorted(va or []), sorted(vb or [])
            if json.dumps(va, sort_keys=True) != json.dumps(vb, sort_keys=True):
                difs.append((sid, campo, va, vb))
    return difs, peor


def main():
    if not os.path.isdir(SALIDA):
        raise SystemExit(
            "No encontre la carpeta salida/ (busque en %s).\n"
            "Sin exports no hay nada que comparar — y una prueba sin datos NO "
            "es una prueba que pasa." % SALIDA)

    grams = sys.argv[1:]
    if not grams:
        grams = sorted(g for g in os.listdir(SALIDA)
                       if os.path.exists(os.path.join(SALIDA, g, "%s_export.json" % g)))
    if not grams:
        raise SystemExit(
            "No hay ningun <gram>_export.json en %s.\n"
            "Corre primero armar_exports_desde_maestro.py (o "
            "exportar_para_dashboard.py <gram>)." % SALIDA)

    print("=== Paridad Python <-> dashboard, cartera por cartera ===")
    print("Motor de JavaScript: el mismo de index.html, corrido con "
          "JavaScriptCore (sin navegador)\n")
    js_motor = motor_javascript()

    print("%-8s %8s %8s %11s %s" % ("cartera", "Python", "dashb.", "delta max", "veredicto"))
    total_cuentas = total_difs = 0
    peor_global = 0.0
    detalles = []

    for g in grams:
        ruta_export = os.path.join(SALIDA, g, "%s_export.json" % g)
        ruta_py = os.path.join(SALIDA, g, "%s_puntuacion.json" % g)
        if not os.path.exists(ruta_py):
            print("%-8s %8s %8s %11s  falta %s_puntuacion.json — corre primero "
                  "puntuar_cartera_nueva.py %s" % (g, "-", "-", "-", g, g))
            continue

        py = json.load(open(ruta_py))
        js = puntuar_con_javascript(js_motor, ruta_export)
        difs, peor = comparar(py, js)

        total_cuentas += len(py)
        total_difs += len(difs)
        peor_global = max(peor_global, peor)
        print("%-8s %8d %8d %11.6f  %s"
              % (g, len(py), len(js), peor, "OK" if not difs else "%d DIFERENCIAS" % len(difs)))
        for d in difs[:6]:
            detalles.append((g,) + d)

    # Cero cuentas comparadas NO es "todo coincide" — es que no se comparo
    # nada. Un OK vacio es peor que una falla: da confianza sin respaldo.
    if total_cuentas == 0:
        raise SystemExit(
            "\nNo se comparo NI UNA cuenta. Falta el <gram>_puntuacion.json de "
            "cada cartera:\n   python3 puntuar_cartera_nueva.py <gram>\n"
            "Esto NO cuenta como prueba superada.")

    print("\n%-8s %8d %8s %11.6f  %s"
          % ("TOTAL", total_cuentas, "", peor_global,
             "TODO COINCIDE" if not total_difs else "%d diferencias" % total_difs))

    if detalles:
        print("\n--- primeras diferencias ---")
        for g, sid, campo, va, vb in detalles[:20]:
            print("  [%s] %s  %s:" % (g, sid, campo))
            print("      Python:    %r" % (va,))
            print("      dashboard: %r" % (vb,))

    if total_difs:
        print("\nHAY DIVERGENCIA. El dashboard le mostraria al usuario algo distinto")
        print("a lo que dice Python. Arreglar antes de compartir el archivo.")
        raise SystemExit(1)

    print("\nEl dashboard y Python dan lo mismo en las %d cuentas, hasta el "
          "ultimo decimal." % total_cuentas)


if __name__ == "__main__":
    main()
