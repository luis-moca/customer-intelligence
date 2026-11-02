"""Mete las 4 librerias del dashboard DENTRO de index.html.

POR QUE EXISTE
--------------
El dashboard cargaba Chart.js, su plugin de zoom, Hammer y GSAP desde CDNs
publicos (jsDelivr y cdnjs). Con internet funciona; sin internet — o con un
firewall corporativo que bloquee esos dominios — la pagina abre pero no dibuja
la matriz ni anima nada, y el usuario no tiene forma de saber por que.

Eso importa porque el dashboard se comparte por correo/Drive con otras
personas: no se puede depender de que la red de cada quien deje pasar dos
dominios especificos.

Este script reemplaza los <script src="https://..."> por el contenido real de
cada libreria, que vive en libs/. El resultado es UN archivo que funciona
100% sin conexion.

QUE NO HACE
-----------
No toca las fuentes de Google (Inter / Space Grotesk / JetBrains Mono). Esas
son cosmeticas y tienen respaldo del sistema: si no cargan, la pagina se ve
con la tipografia del sistema pero funciona igual. Las librerias JS no: sin
ellas no hay grafica.

USO
---
    python3 embeber_librerias.py

Es idempotente: si ya estan embebidas, avisa y no hace nada.
Las librerias se bajaron una vez de sus CDNs oficiales y viven en libs/.
"""
import os
import re

AQUI = os.path.dirname(os.path.abspath(__file__))
LIBS = os.path.join(AQUI, "libs")

# (marca que identifica el <script src> en el HTML, archivo local, nombre)
LIBRERIAS = [
    ("chart.js@4.4.1", "chart.js", "Chart.js 4.4.1"),
    ("hammerjs@2.0.8", "hammer.js", "Hammer.js 2.0.8"),
    ("chartjs-plugin-zoom@2.0.1", "zoom.js", "chartjs-plugin-zoom 2.0.1"),
    ("gsap/3.12.5", "gsap.js", "GSAP 3.12.5"),
]


def _carpeta_dashboard():
    for ruta in (os.path.join(AQUI, "..", "MVP", "dashboard"),
                 os.path.join(AQUI, "..", "dashboard")):
        if os.path.isdir(ruta):
            return ruta
    raise SystemExit("No encontre la carpeta dashboard/.")


def main():
    index = os.path.join(_carpeta_dashboard(), "index.html")
    html = open(index).read()

    if "/*__LIB_EMBEBIDA__*/" in html:
        print("Las librerias YA estan embebidas en %s. No se toco nada." % index)
        return

    antes = len(html)
    for marca, archivo, nombre in LIBRERIAS:
        ruta = os.path.join(LIBS, archivo)
        if not os.path.exists(ruta):
            raise SystemExit("Falta libs/%s — no puedo embeber %s." % (archivo, nombre))
        codigo = open(ruta).read()

        # Un '</script>' dentro del codigo cerraria la etiqueta antes de tiempo
        # y romperia el HTML. Se parte en dos para que el navegador no lo lea
        # como cierre; JavaScript ve exactamente el mismo texto.
        codigo = codigo.replace("</script>", "<\\/script>")

        patron = re.compile(
            r'<script src="https?://[^"]*' + re.escape(marca) + r'[^"]*"></script>')
        reemplazo = ('<script>/*__LIB_EMBEBIDA__*/ /* %s — embebida para que el '
                     'dashboard funcione sin internet */\n%s\n</script>' % (nombre, codigo))

        # OJO: nada de patron.subn(reemplazo, ...). El codigo minificado trae
        # secuencias como \s o \1 que re interpretaria como referencias de
        # grupo y truena ("bad escape \s"). Se busca la posicion y se pega el
        # texto tal cual, sin que re lo toque.
        encontrados = patron.findall(html)
        if len(encontrados) != 1:
            raise SystemExit(
                "Esperaba 1 <script src> de %s y encontre %d. No se toco el archivo."
                % (nombre, len(encontrados)))
        html = html.replace(encontrados[0], reemplazo, 1)
        print("   embebida: %-28s %6.0f KB" % (nombre, len(codigo) / 1024))

    with open(index, "w") as fh:
        fh.write(html)

    print("\n%s: %.0f KB -> %.0f KB" % (os.path.basename(index),
                                         antes / 1024, len(html) / 1024))
    print("Cero dependencias de CDN. Las fuentes de Google siguen siendo")
    print("remotas, pero son cosmeticas: sin ellas la pagina funciona igual.")


if __name__ == "__main__":
    main()
