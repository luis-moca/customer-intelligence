"""Mete las 3 tipografias del dashboard DENTRO de index.html.

POR QUE EXISTE
--------------
Aunque embeber_librerias.py ya quito los CDN de JavaScript, quedaban tres
<link> a fonts.googleapis.com. Sin internet — o con un firewall que bloquee
ese dominio — la pagina funcionaba, pero se veia con la tipografia del sistema
en vez de Space Grotesk / Inter / JetBrains Mono. La mezcla de esas tres es
deliberada (titulos / texto / numeros e IDs), no cosmetica: con la del sistema
el tablero pierde la jerarquia visual que lo hace legible de un vistazo.

Con esto, index.html no pide UN SOLO recurso a la red. Funciona igual con
internet, sin internet, o detras de cualquier firewall.

QUE SE EMBEBE Y QUE NO
----------------------
Solo el subset 'latin' de cada peso — 9 archivos woff2, 325 KB. Ese subset
cubre todo el espanol: a-z, A-Z, 0-9, acentos, ñÑ, ¿¡, € y $. Los subsets
cyrillic / greek / vietnamese / latin-ext se dejan fuera a proposito: pesan
mas del doble y este tablero nunca los va a mostrar. Si un nombre de cliente
trajera un caracter fuera de ese rango, el navegador usa la fuente del
sistema para ESE caracter — degradacion normal, nada se rompe.

USO
---
    python3 embeber_fuentes.py

Es idempotente: si ya estan embebidas, avisa y no hace nada.
El CSS con las fuentes en base64 vive en libs/fonts_latin.css.
"""
import os
import re

AQUI = os.path.dirname(os.path.abspath(__file__))
CSS_FUENTES = os.path.join(AQUI, "libs", "fonts_latin.css")
MARCA = "/*__FUENTES_EMBEBIDAS__*/"


def _carpeta_dashboard():
    for ruta in (os.path.join(AQUI, "..", "MVP", "dashboard"),
                 os.path.join(AQUI, "..", "dashboard")):
        if os.path.isdir(ruta):
            return ruta
    raise SystemExit("No encontre la carpeta dashboard/.")


def main():
    index = os.path.join(_carpeta_dashboard(), "index.html")
    html = open(index).read()

    if MARCA in html:
        print("Las fuentes YA estan embebidas en %s. No se toco nada." % index)
        return
    if not os.path.exists(CSS_FUENTES):
        raise SystemExit("Falta %s — no puedo embeber las fuentes." % CSS_FUENTES)

    css = open(CSS_FUENTES).read()
    antes = len(html)

    # Los tres <link> de Google: dos preconnect y la hoja de estilos.
    patron = re.compile(r'<link[^>]+fonts\.(?:googleapis|gstatic)\.com[^>]*>\s*')
    encontrados = patron.findall(html)
    if not encontrados:
        raise SystemExit("No encontre ningun <link> a Google Fonts. No se toco el archivo.")

    for etiqueta in encontrados:
        html = html.replace(etiqueta, "", 1)

    bloque = ("<style>%s\n/* Space Grotesk, Inter y JetBrains Mono (subset latin) "
              "embebidas: el dashboard no pide un solo recurso a la red */\n%s\n</style>\n"
              % (MARCA, css))

    # Va justo despues de <head> para que las fuentes esten listas antes de
    # que se pinte el primer texto.
    pos = html.find("<head>")
    if pos == -1:
        raise SystemExit("No encontre <head> en index.html.")
    pos += len("<head>")
    html = html[:pos] + "\n" + bloque + html[pos:]

    with open(index, "w") as fh:
        fh.write(html)

    print("   quitados %d <link> a Google Fonts" % len(encontrados))
    print("   embebidas 9 fuentes (subset latin): %.0f KB de CSS" % (len(css) / 1024))
    print("\n%s: %.0f KB -> %.0f KB" % (os.path.basename(index),
                                         antes / 1024, len(html) / 1024))
    print("El dashboard ya no pide NINGUN recurso a internet.")


if __name__ == "__main__":
    main()
