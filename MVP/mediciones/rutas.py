"""Donde estan los datos, sin depender de atajos ni de desde donde se corra.

POR QUE EXISTE
--------------
Antes cada script hacia:

    MAESTRO = os.path.join(os.path.dirname(__file__), "maestro")

y para que eso funcionara en el paquete de traspaso hacia falta un enlace
simbolico (motor/maestro -> ../datos). Funcionaba, pero era fragil: copiar la
carpeta con Finder entre discos, mandarla por Drive, o descomprimirla con una
herramienta que no preserve enlaces, y el enlace se convierte en un archivo
roto. El motor tronaba con un error que no dice nada util.

Ahora la carpeta se BUSCA en los lugares donde razonablemente puede estar, en
orden. El enlace simbolico ya no hace falta — si esta, se usa; si no esta, se
encuentra igual.

Tambien resuelve el otro problema del paquete: los scripts de mediciones/
importan modulos que viven en motor/ (evaluar, features, modelo_simple). Al
importar este archivo, esa carpeta queda disponible sola.

USO
---
    from rutas import MAESTRO
"""
import os
import sys

_AQUI = os.path.dirname(os.path.abspath(__file__))

# En orden de preferencia. El primero que exista y tenga datos adentro gana.
_CANDIDATOS = (
    os.path.join(_AQUI, "maestro"),        # repo original (Motor/maestro/)
    os.path.join(_AQUI, "..", "datos"),    # paquete de traspaso (MVP/datos/)
    os.path.join(_AQUI, "datos"),          # todo junto en una sola carpeta
)

# Un archivo que SIEMPRE esta en la carpeta de datos. Sirve para no confundirse
# con una carpeta que exista pero este vacia (pasa cuando un enlace se rompe al
# copiar: queda el nombre, no el contenido).
_SENA = "foto_maestra.json"


def _buscar():
    for ruta in _CANDIDATOS:
        if os.path.isfile(os.path.join(ruta, _SENA)):
            return os.path.normpath(ruta)
    # Ninguna sirvio: se falla con un mensaje que dice que hacer, no con un
    # "archivo no encontrado" a 3 funciones de profundidad.
    raise SystemExit(
        "No encontre la carpeta de datos (la que tiene %s).\n"
        "Busque en:\n  %s\n\n"
        "Si moviste el proyecto, deja la carpeta de datos en uno de esos\n"
        "lugares — no hace falta ningun enlace ni editar codigo."
        % (_SENA, "\n  ".join(os.path.normpath(c) for c in _CANDIDATOS)))


MAESTRO = _buscar()

# Los scripts de mediciones/ importan modulos que viven en motor/ (evaluar,
# features, modelo_simple). Sin esto no corren fuera de su carpeta.
for _hermana in (os.path.join(_AQUI, "..", "motor"), os.path.join(_AQUI, "..", "Motor")):
    if os.path.isdir(_hermana) and os.path.normpath(_hermana) != _AQUI:
        _hermana = os.path.normpath(_hermana)
        if _hermana not in sys.path:
            sys.path.insert(0, _hermana)
