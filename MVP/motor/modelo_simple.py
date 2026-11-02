"""
Regresion logistica en Python puro (sin pandas/sklearn/numpy — no estan
instalados, y el proyecto ya traia la regla de "sin instalar nada").

Decision de Luis (Fase 4, ya aprobada): modelo simple e interpretable, no
sofisticado. Con miles de filas y unos cientos de churns, una logistica le
gana a cualquier cosa compleja y ademas se puede explicar el "por que" a
un CS — cosa que un ensamble de arboles no da igual de claro.
"""
import math


def normalizar(filas, columnas):
    """z-score por columna: (x - media) / desviacion. Necesario porque MRR
    vive en miles y 'num_expansiones' vive en unidades — sin normalizar, el
    gradiente lo domina la columna con la escala mas grande, no la mas util."""
    stats = {}
    for col in columnas:
        vals = [f[col] for f in filas if f.get(col) is not None]
        media = sum(vals) / len(vals) if vals else 0.0
        var = sum((v - media) ** 2 for v in vals) / len(vals) if vals else 1.0
        desv = math.sqrt(var) or 1.0
        stats[col] = (media, desv)
    return stats


def vectorizar(fila, columnas, stats):
    x = []
    for col in columnas:
        v = fila.get(col)
        media, desv = stats[col]
        x.append((v - media) / desv if v is not None else 0.0)
    return x


def sigmoide(z):
    if z < -30:
        return 0.0
    if z > 30:
        return 1.0
    return 1.0 / (1.0 + math.exp(-z))


def entrenar(X, y, columnas, epocas=300, tasa=0.3, l1=0.002):
    """Descenso de gradiente con regularizacion L1.

    L1 (no L2) a proposito: L1 empuja los pesos inutiles EXACTAMENTE a cero,
    asi que el propio entrenamiento apaga las variables que no aportan. Es la
    forma de que la seleccion final de variables la haga la matematica y no
    Claude eligiendo a ojo — regla dura del proyecto.
    """
    n = len(X)
    p = len(columnas)
    w = [0.0] * p
    b = 0.0

    for _ in range(epocas):
        grad_w = [0.0] * p
        grad_b = 0.0
        for xi, yi in zip(X, y):
            z = sum(wj * xj for wj, xj in zip(w, xi)) + b
            pred = sigmoide(z)
            error = pred - yi
            for j in range(p):
                grad_w[j] += error * xi[j]
            grad_b += error
        for j in range(p):
            w[j] -= tasa * grad_w[j] / n
            # umbral suave: si el peso es mas chico que el castigo, cae a cero
            castigo = tasa * l1
            if w[j] > castigo:
                w[j] -= castigo
            elif w[j] < -castigo:
                w[j] += castigo
            else:
                w[j] = 0.0
        b -= tasa * grad_b / n

    return {"w": w, "b": b, "columnas": columnas}


def predecir(modelo, x):
    z = sum(wj * xj for wj, xj in zip(modelo["w"], x)) + modelo["b"]
    return sigmoide(z)


def pesos_ordenados(modelo):
    """Que tanto pesa cada variable, para poder explicarle el 'por que' a un CS."""
    return sorted(zip(modelo["columnas"], modelo["w"]), key=lambda t: -abs(t[1]))
