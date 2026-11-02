"""
Construye las columnas del modelo LEYENDO EL PANEL, no una lista que Claude
escribio a mano. Regla del proyecto: la matematica elige, no yo.

Como decide que hacer con cada columna (por su contenido, no por su nombre):
 - numerica  -> entra tal cual, normalizada
 - booleana  -> entra como 0/1
 - categorica con pocos valores -> una columna 0/1 por cada valor con soporte
   suficiente; los valores raros se agrupan en "otros" en vez de tirarse
 - categorica con demasiados valores -> se agrupa igual, sin explotar el modelo

Nada se excluye por criterio propio: lo que no sirva lo apaga la regularizacion
L1 durante el entrenamiento (pone su peso en cero), y eso queda visible en el
reporte de pesos.
"""
import collections
import math

NO_SON_FEATURES = {
    "suscripcion_id", "cliente_id", "gram", "anio", "mes", "cierre_mes",
    "etiqueta_churn_120d", "etiqueta_expansion_90d", "etiqueta_contraccion_90d",
    "para_puntuar",
}

SOPORTE_MINIMO_CATEGORIA = 100  # un valor con menos filas se manda a "otros"
MAX_CATEGORIAS = 12


def _tipo(valores):
    no_nulos = [v for v in valores if v is not None]
    if not no_nulos:
        return "vacia"
    if all(isinstance(v, bool) for v in no_nulos):
        return "booleana"
    if all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in no_nulos):
        # muchos ids de Odoo son enteros pero son CATEGORIAS, no cantidades.
        # Se distingue por cardinalidad: pocos valores distintos = categoria.
        return "numerica" if len(set(no_nulos)) > MAX_CATEGORIAS else "categorica"
    return "categorica"


def construir_esquema(panel):
    """Recorre el panel una vez y decide que hacer con cada columna."""
    columnas = [c for c in panel[0] if c not in NO_SON_FEATURES]
    esquema = []
    for col in columnas:
        valores = [f.get(col) for f in panel]
        tipo = _tipo(valores)
        if tipo == "vacia":
            continue
        if tipo in ("numerica", "booleana"):
            esquema.append({"col": col, "tipo": tipo})
        else:
            conteo = collections.Counter(
                str(v) for v in valores if v is not None and not isinstance(v, (list, dict)))
            frecuentes = [v for v, n in conteo.most_common(MAX_CATEGORIAS)
                          if n >= SOPORTE_MINIMO_CATEGORIA]
            if not frecuentes:
                continue
            esquema.append({"col": col, "tipo": "categorica", "valores": frecuentes})
    return esquema


def nombres_de_columnas(esquema):
    nombres = []
    for e in esquema:
        if e["tipo"] in ("numerica", "booleana"):
            nombres.append(e["col"])
        else:
            for v in e["valores"]:
                nombres.append("%s=%s" % (e["col"], v))
            nombres.append("%s=otros" % e["col"])
    return nombres


def construir_x(fila, esquema):
    """Una fila del panel -> dict {nombre_columna: valor}."""
    x = {}
    for e in esquema:
        col = e["col"]
        v = fila.get(col)
        if e["tipo"] == "numerica":
            # log con signo: comprime valores extremos sin aplanarlos.
            # Medido el 22-ago-2026 (medir_escalas.py, 9 carteras, 3
            # desenlaces) contra z-score puro y clip p99: expansion 2.2x->2.6x
            # (12 cuentas mas capturadas), contraccion igual, churn -1 cuenta
            # (ruido). Motivo original: una cuenta de mnav con 12
            # contracciones (p99 del universo: 4) dominaba sola su prediccion
            # con +1.7 de logit e inflaba el techo de toda su cartera.
            x[col] = None if v is None else math.copysign(math.log1p(abs(v)), v)
        elif e["tipo"] == "booleana":
            x[col] = None if v is None else (1.0 if v else 0.0)
        else:
            s = str(v)
            encontrado = False
            for valor in e["valores"]:
                hit = 1.0 if s == valor else 0.0
                x["%s=%s" % (col, valor)] = hit
                if hit:
                    encontrado = True
            x["%s=otros" % col] = 0.0 if encontrado else 1.0
    return x
