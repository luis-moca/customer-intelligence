"""
Explica la diferencia entre el número que muestra el frontend de Odoo y las
cuentas reales que trae el export.

Uso:   python3 verificar_conteo.py falg

El export filtra state='sale' (contratos firmados). El frontend cuenta además
las cotizaciones en borrador. Esta consulta trae TODO sin filtrar por state
para que la resta cuadre sola. Una sola consulta, solo lectura.
"""
import collections
import sys

# 'rutas' va PRIMERO: es quien pone motor/ en el camino de busqueda — sin eso,
# el import de abajo falla al correr desde esta carpeta.
import rutas  # noqa: F401
from fuente_odoo import conectar


def main():
    if len(sys.argv) < 2:
        print("Falta el gram. Ejemplo:  python3 verificar_conteo.py falg")
        raise SystemExit(1)
    gram = sys.argv[1].strip().lower()

    _, consultar = conectar()
    dominio = [("user_id", "ilike", "(%s)" % gram), ("is_subscription", "=", True)]
    filas = consultar("sale.order", "search_read", [dominio],
                      {"fields": ["subscription_state", "state"]})

    print("Gram: %s" % gram)
    print("Documentos totales en sale.order (cualquier state): %d\n" % len(filas))

    conteo = collections.Counter(str(f["subscription_state"]) for f in filas)
    print("Por subscription_state:")
    for estado, n in conteo.most_common():
        print("   %-12s %4d" % (estado, n))

    activas = conteo.get("3_progress", 0)
    churn = conteo.get("6_churn", 0)
    draft = conteo.get("1_draft", 0)
    print("\nLo que ve el frontend  = activas + churn + borradores")
    print("                       = %d + %d + %d = %d"
          % (activas, churn, draft, activas + churn + draft))
    print("Lo que trae el export  = activas + churn = %d" % (activas + churn))
    print("Diferencia esperada    = %d borradores (cotizaciones sin firmar)" % draft)


if __name__ == "__main__":
    main()
