"""
Embebe dashboard/modelo.json DENTRO de dashboard/index.html.

Por que existe: el dashboard se abre con file:// (sin servidor), y los
navegadores bloquean fetch() a otro archivo local por CORS. La unica forma
de que un solo archivo funcione sin friccion es que el modelo YA este adentro.

modelo.json sigue siendo la fuente real (la genera Python, se puede leer y
diferenciar en git); este script solo lo copia al marcador que hay en
index.html. Se corre una vez cada vez que el modelo cambia:

    python3 exportar_modelo_para_dashboard.py
    python3 inyectar_modelo.py
"""
import json
import os
import re

from exportar_modelo_para_dashboard import _carpeta_dashboard

DASH = _carpeta_dashboard()
MODELO = os.path.join(DASH, "modelo.json")
INDEX = os.path.join(DASH, "index.html")
MARCADOR = re.compile(
    r"const MODELO = /\*__MODELO_JSON__\*/.*?;",
    re.DOTALL,
)


def main():
    with open(MODELO) as f:
        datos = json.load(f)
    compacto = json.dumps(datos, ensure_ascii=False, separators=(",", ":"))

    with open(INDEX) as f:
        html = f.read()

    nuevo, n = MARCADOR.subn(
        "const MODELO = /*__MODELO_JSON__*/ " + compacto + ";", html)
    if n == 0:
        raise SystemExit(
            "No encontre el marcador 'const MODELO = /*__MODELO_JSON__*/' "
            "en index.html. No se toco el archivo.")
    if n > 1:
        raise SystemExit("El marcador aparece %d veces — deberia ser 1." % n)

    with open(INDEX, "w") as f:
        f.write(nuevo)

    print("Modelo embebido: %.0f KB -> %s" % (len(compacto) / 1024, INDEX))


if __name__ == "__main__":
    main()
