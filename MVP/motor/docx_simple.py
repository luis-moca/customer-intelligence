"""Escribe un .docx desde cero, con SOLO la libreria estandar de Python.

POR QUE EXISTE
--------------
Un .docx es un ZIP con unos cuantos archivos XML adentro. No hace falta Word,
ni LibreOffice, ni node, ni python-docx — nada de eso esta instalado en la Mac
de Luis, y la regla del proyecto es "Python 3 y nada mas" para que el motor
corra en cualquier maquina sin preparar entorno.

Esto NO es una libreria general de Word: cubre exactamente lo que la hoja de
revision necesita (titulos, parrafos, tablas con encabezado y celdas vacias
para escribir a mano). Si algun dia se necesita mas, se agrega aqui.

Unidades: DXA (1440 = 1 pulgada). Carta = 12240 x 15840.
"""
import zipfile

CARTA_ANCHO, CARTA_ALTO = 12240, 15840
MARGEN = 1080                      # 0.75"
ANCHO_UTIL = CARTA_ANCHO - 2 * MARGEN


def esc(t):
    return (str(t).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def _runs(texto, negrita=False, tam=20, color=None, cursiva=False, mono=False):
    props = []
    if mono:
        props.append('<w:rFonts w:ascii="Consolas" w:hAnsi="Consolas"/>')
    if negrita:
        props.append("<w:b/>")
    if cursiva:
        props.append("<w:i/>")
    if color:
        props.append('<w:color w:val="%s"/>' % color)
    props.append('<w:sz w:val="%d"/>' % tam)
    return ('<w:r><w:rPr>%s</w:rPr><w:t xml:space="preserve">%s</w:t></w:r>'
            % ("".join(props), esc(texto)))


def parrafo(texto="", negrita=False, tam=20, color=None, cursiva=False,
            espacio_antes=0, espacio_despues=100, alineacion=None,
            borde_abajo=None, mono=False):
    pr = ['<w:spacing w:before="%d" w:after="%d"/>' % (espacio_antes, espacio_despues)]
    if alineacion:
        pr.append('<w:jc w:val="%s"/>' % alineacion)
    if borde_abajo:
        pr.append('<w:pBdr><w:bottom w:val="single" w:sz="6" w:space="4" '
                  'w:color="%s"/></w:pBdr>' % borde_abajo)
    run = _runs(texto, negrita, tam, color, cursiva, mono) if texto else ""
    return "<w:p><w:pPr>%s</w:pPr>%s</w:p>" % ("".join(pr), run)


def celda(contenido, ancho, fondo=None, alineacion=None, alto_minimo=None):
    """contenido: string (un parrafo) o lista de strings XML de parrafos."""
    props = ['<w:tcW w:w="%d" w:type="dxa"/>' % ancho]
    if fondo:
        props.append('<w:shd w:val="clear" w:color="auto" w:fill="%s"/>' % fondo)
    props.append('<w:vAlign w:val="center"/>')
    # contenido puede ser: texto plano (se envuelve en un parrafo), UN parrafo
    # ya armado (string que empieza con <w:p>), o una lista de parrafos.
    # Distinguir el segundo caso importa: sin esto, un parrafo ya armado se
    # re-escapaba y salia el XML crudo como texto visible en la celda.
    if isinstance(contenido, str):
        if contenido.startswith("<w:p>"):
            cuerpo = contenido
        else:
            cuerpo = parrafo(contenido, alineacion=alineacion, espacio_despues=0)
    else:
        cuerpo = "".join(contenido) or parrafo("", espacio_despues=0)
    return "<w:tc><w:tcPr>%s</w:tcPr>%s</w:tc>" % ("".join(props), cuerpo)


def fila(celdas, alto=None, encabezado=False):
    pr = []
    if alto:
        pr.append('<w:trHeight w:val="%d" w:hRule="atLeast"/>' % alto)
    if encabezado:
        pr.append("<w:tblHeader/>")
    props = "<w:trPr>%s</w:trPr>" % "".join(pr) if pr else ""
    return "<w:tr>%s%s</w:tr>" % (props, "".join(celdas))


def tabla(filas, anchos, color_borde="D0D0D8"):
    borde = ('<w:tblBorders>' + "".join(
        '<w:%s w:val="single" w:sz="4" w:space="0" w:color="%s"/>' % (b, color_borde)
        for b in ("top", "left", "bottom", "right", "insideH", "insideV")) +
        '</w:tblBorders>')
    grid = "".join('<w:gridCol w:w="%d"/>' % a for a in anchos)
    return ('<w:tbl><w:tblPr><w:tblW w:w="%d" w:type="dxa"/>%s'
            '<w:tblCellMar>'
            '<w:top w:w="70" w:type="dxa"/><w:bottom w:w="70" w:type="dxa"/>'
            '<w:left w:w="100" w:type="dxa"/><w:right w:w="100" w:type="dxa"/>'
            '</w:tblCellMar></w:tblPr>'
            '<w:tblGrid>%s</w:tblGrid>%s</w:tbl>'
            % (sum(anchos), borde, grid, "".join(filas)))


def salto_pagina():
    return '<w:p><w:r><w:br w:type="page"/></w:r></w:p>'


def guardar(ruta, cuerpo):
    """cuerpo: lista de strings XML (parrafos y tablas)."""
    document = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        '<w:body>%s'
        '<w:sectPr>'
        '<w:pgSz w:w="%d" w:h="%d"/>'
        '<w:pgMar w:top="%d" w:right="%d" w:bottom="%d" w:left="%d" '
        'w:header="720" w:footer="720" w:gutter="0"/>'
        '</w:sectPr></w:body></w:document>'
        % ("".join(cuerpo), CARTA_ANCHO, CARTA_ALTO, MARGEN, MARGEN, MARGEN, MARGEN))

    content_types = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
        '<Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>'
        '</Types>')

    rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>'
        '</Relationships>')

    doc_rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>'
        '</Relationships>')

    # Tipografia base del documento. Sin esto Word usa su default (Calibri 11)
    # y el tamano de cada run se pelea con el del estilo.
    styles = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        '<w:docDefaults><w:rPrDefault><w:rPr>'
        '<w:rFonts w:ascii="Calibri" w:hAnsi="Calibri" w:cs="Calibri"/>'
        '<w:sz w:val="20"/><w:szCs w:val="20"/>'
        '</w:rPr></w:rPrDefault></w:docDefaults>'
        '<w:style w:type="paragraph" w:default="1" w:styleId="Normal">'
        '<w:name w:val="Normal"/><w:qFormat/>'
        '</w:style></w:styles>')

    with zipfile.ZipFile(ruta, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", content_types)
        z.writestr("_rels/.rels", rels)
        z.writestr("word/_rels/document.xml.rels", doc_rels)
        z.writestr("word/styles.xml", styles)
        z.writestr("word/document.xml", document)
