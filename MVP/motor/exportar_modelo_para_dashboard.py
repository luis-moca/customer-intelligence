"""
Exporta el modelo YA ENTRENADO como DATOS (pesos, vocabulario, calibracion,
umbrales) para que el dashboard puntue en el navegador sin depender de Python.

POR QUE EXISTE (el riesgo que Luis señalo): si la logica de features se
escribe dos veces — una en panel_fase2.py, otra a mano en JavaScript — el dia
que una cambie y la otra no, el dashboard va a mentir SIN AVISAR.

La forma de cerrar ese riesgo no es "tener mucho cuidado". Es reducir a el
minimo lo que se vuelve a escribir en JS. Este script saca del entrenamiento
TODO lo que es matematica pura (pesos, medias, desviaciones, que categorias
sobrevivieron, en que orden van las columnas, los umbrales de decision) y lo
guarda como JSON plano. Eso es DATO, no LOGICA — no hay forma de que un dato
"se desincronice de si mismo".

Lo UNICO que sigue existiendo en dos lenguajes despues de esto es el calculo
de features desde el export crudo (leer un ping, sumar un evento, etc.) — eso
si es logica de verdad y si tiene que portarse a mano. Para blindar ESA parte
existe verificar_paridad.py: corre la MISMA cartera por el camino Python y
por el camino del dashboard y compara cuenta por cuenta. Si algun dia
divergen, esa prueba truena — no se entera el usuario primero que nosotros.

Uso:    python3 exportar_modelo_para_dashboard.py
Salida: dashboard/modelo.json (se versiona junto con el dashboard)
"""
import json
import os

from calibrar import ajustar_platt
from features import construir_esquema, construir_x, nombres_de_columnas
from modelo_simple import entrenar, normalizar, predecir, vectorizar
from panel_fase2 import (ATRIBUTOS_ESTATICOS, MODULOS_APP, MULTI_YEAR,
                         ODOO_SH, PLAN_CUSTOM, PLAN_STANDARD, SUCCESS_PACK)

from rutas import MAESTRO


def _carpeta_dashboard():
    """Donde vive el dashboard, corra esto desde Motor/ o desde el paquete MVP.

    En el repo el script esta en CC/Motor/ y el dashboard en CC/MVP/dashboard/.
    En el paquete de traspaso el script esta en MVP/motor/ y el dashboard en
    MVP/dashboard/ — un nivel distinto. Se prueban las dos en vez de asumir una:
    copiar el paquete a otra maquina no deberia romper esto.
    """
    aqui = os.path.dirname(os.path.abspath(__file__))
    for ruta in (os.path.join(aqui, "..", "MVP", "dashboard"),   # CC/Motor/
                 os.path.join(aqui, "..", "dashboard")):          # MVP/motor/
        if os.path.isdir(ruta):
            return ruta
    raise SystemExit("No encontre la carpeta dashboard/ ni en ../MVP/ ni en ../")


DESTINO = os.path.join(_carpeta_dashboard(), "modelo.json")

UMBRALES = {"churn": 0.23, "contraccion": 0.20, "expansion": 0.50}
MIN_LICENCIAS_PARA_SATURACION = 2
DIAS_RENOVACION_RECIENTE = 120
OBJETIVOS = [("etiqueta_expansion_90d", "expansion"),
             ("etiqueta_contraccion_90d", "contraccion"),
             ("etiqueta_churn_120d", "churn")]
ACCION = {"churn": "RESCATAR", "contraccion": "RIESGO DOWNGRADE",
          "expansion": "PROBABLE CRECIMIENTO"}
PRIORIDAD = ["RESCATAR", "RIESGO DOWNGRADE", "PROBABLE CRECIMIENTO",
             "LARGO PLAZO (pendiente)", "SIN ACCION"]


def main():
    panel = json.load(open(os.path.join(MAESTRO, "panel_cuenta_mes.json")))
    ent = [f for f in panel if not f["para_puntuar"]]
    ultimo = max(f["cierre_mes"] for f in ent)
    train = [f for f in ent if f["cierre_mes"] < ultimo]
    cal = [f for f in ent if f["cierre_mes"] == ultimo]
    print("Entrena: %d filas | calibra: %d (%s)\n" % (len(train), len(cal), ultimo))

    esquema = construir_esquema(train)
    columnas = nombres_de_columnas(esquema)
    Xtr_d = [construir_x(f, esquema) for f in train]
    stats = normalizar(Xtr_d, columnas)
    Xtr = [vectorizar(x, columnas, stats) for x in Xtr_d]
    Xcal = [vectorizar(construir_x(f, esquema), columnas, stats) for f in cal]

    modelos = {}
    for objetivo, nombre in OBJETIVOS:
        m = entrenar(Xtr, [f[objetivo] for f in train], columnas)
        A, B = ajustar_platt([predecir(m, x) for x in Xcal],
                             [f[objetivo] for f in cal])
        vivas = sum(1 for w in m["w"] if abs(w) > 1e-9)
        print("   %-12s L1 dejo %d/%d variables vivas | calibracion A=%.3f B=%.3f"
              % (nombre, vivas, len(columnas), A, B))
        modelos[nombre] = {"w": m["w"], "b": m["b"], "A": A, "B": B}

    # Como ESCRIBE Python el valor crudo de cada columna en el texto del
    # "por que" (ese texto lo lee el AM, y tiene que decir lo mismo en los dos
    # motores). JS no puede distinguir 5616 de 5616.0 — para el son el mismo
    # numero — asi que el tipo se mide aqui, sobre las filas reales, y viaja
    # como dato. Una columna cuenta como float si CUALQUIER fila la trae float.
    tipos_valor = {}
    for e in esquema:
        col, tipo = e["col"], None
        for f in train:
            v = f.get(col)
            if v is None:
                continue
            if isinstance(v, bool):
                tipo = "bool"
                break
            if isinstance(v, float):
                tipo = "float"
                break
            if isinstance(v, int):
                tipo = tipo or "int"
            else:
                tipo = "str"
                break
        tipos_valor[col] = tipo or "int"

    artefacto = {
        "generado": ultimo,
        "esquema": esquema,       # como leer cada columna CRUDA del panel
        "tipos_valor": tipos_valor,   # como se imprime cada valor en el "por que"
        "columnas": columnas,     # orden exacto del vector, post one-hot
        "stats": stats,           # {columna_final: [media, desv]}
        "modelos": modelos,       # {churn|expansion|contraccion: {w,b,A,B}}
        "umbrales": UMBRALES,
        "min_licencias_saturacion": MIN_LICENCIAS_PARA_SATURACION,
        "dias_renovacion_reciente": DIAS_RENOVACION_RECIENTE,
        "prioridad": PRIORIDAD,
        "accion": ACCION,
        # Constantes que antes solo vivian en panel_fase2.py. Se exportan
        # tambien como DATO — la lista de que campo es "estatico", que
        # producto es que cosa, nunca se vuelve a escribir a mano en JS.
        # Si un dia se aprueba excluir o agregar un campo, este archivo se
        # regenera y el dashboard lo hereda solo, sin tocar una linea de JS.
        "atributos_estaticos": ATRIBUTOS_ESTATICOS,
        "modulos_app": {str(k): v for k, v in MODULOS_APP.items()},
        "success_pack": sorted(SUCCESS_PACK),
        "odoo_sh": sorted(ODOO_SH),
        "plan_standard": PLAN_STANDARD,
        "plan_custom": PLAN_CUSTOM,
        "multi_year": MULTI_YEAR,
    }
    os.makedirs(os.path.dirname(DESTINO), exist_ok=True)
    with open(DESTINO, "w") as fh:
        json.dump(artefacto, fh, ensure_ascii=False)

    print("\nGuardado: %s (%.0f KB)" % (DESTINO, os.path.getsize(DESTINO) / 1024))
    print("Columnas del vector: %d | columnas crudas en el esquema: %d"
          % (len(columnas), len(esquema)))


if __name__ == "__main__":
    main()
