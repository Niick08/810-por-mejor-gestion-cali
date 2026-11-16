"""Genera la memoria del proyecto sobre la plantilla del curso (Modelo_Informe_Geoinform.docx).
Uso:  .venv/Scripts/python scripts/memoria/generar_memoria.py --plantilla <ruta .docx>
Antes: scripts/memoria/capturas.py y scripts/memoria/diagramas.py (imágenes en docs/memoria/img).
"""
import argparse
import os

from docx import Document
from docx.enum.style import WD_STYLE_TYPE
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor
from PIL import Image

RAIZ = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
IMG = os.path.join(RAIZ, "docs", "memoria", "img")
REPO = "https://github.com/Niick08/810-por-mejor-gestion-cali"
ANCHO = 15.6                      # cm útiles (21,6 − 2 × 3)
figuras = [0]
tablas = [0]


# ====================================================================== utilidades
def preparar_estilos(doc):
    estilos = doc.styles
    if "Heading 2" not in [s.name for s in estilos]:
        h2 = estilos.add_style("Heading 2", WD_STYLE_TYPE.PARAGRAPH)
        h2.base_style = estilos["Heading 1"]
        h2.font.size = Pt(13)
        h2.paragraph_format.space_before = Pt(12)
        h2.paragraph_format.space_after = Pt(4)
        h2.paragraph_format.keep_with_next = True
        ppr = h2.element.get_or_add_pPr()
        nivel = OxmlElement("w:outlineLvl")
        nivel.set(qn("w:val"), "1")
        ppr.append(nivel)


def reemplazar(doc, original, nuevo):
    for p in doc.paragraphs:
        if p.text.strip() == original.strip() and p.runs:
            p.runs[0].text = nuevo
            for r in p.runs[1:]:
                r.text = ""
            return
    raise ValueError(f"No encontré «{original}» en la plantilla")


def borrar_desde(doc, texto_inicio):
    """Borra el contenido de relleno de la plantilla a partir del primer Título 1 con ese texto."""
    cuerpo = doc.element.body
    inicio = next(p for p in doc.paragraphs if p.style.name == "Heading 1" and p.text.strip() == texto_inicio)
    borrar = False
    for el in list(cuerpo):
        if el is inicio._p:
            borrar = True
        if borrar and el.tag != qn("w:sectPr"):
            cuerpo.remove(el)


def t(doc, texto, negrita_inicial=None, estilo=None, alinear=WD_ALIGN_PARAGRAPH.JUSTIFY):
    p = doc.add_paragraph(style=estilo)
    if negrita_inicial:
        p.add_run(negrita_inicial).bold = True
    p.add_run(texto)
    p.alignment = alinear
    return p


def viñetas(doc, items):
    for item in items:
        p = doc.add_paragraph()
        p.paragraph_format.left_indent = Cm(0.8)
        p.paragraph_format.first_line_indent = Cm(-0.4)
        p.paragraph_format.space_after = Pt(2)
        if isinstance(item, tuple):
            p.add_run("• ")
            p.add_run(item[0]).bold = True
            p.add_run(item[1])
        else:
            p.add_run("• " + item)


def h1(doc, texto):
    doc.add_heading(texto, level=1)


def h2(doc, texto):
    doc.add_paragraph(texto, style="Heading 2")


def leyenda(doc, prefijo, contador, texto):
    contador[0] += 1
    p = doc.add_paragraph(style="Caption")
    p.add_run(f"{prefijo} {contador[0]}. ").bold = True
    p.add_run(texto)
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    return contador[0]


def figura(doc, archivo, texto, ancho=ANCHO, alto_max=19):
    ruta = os.path.join(IMG, archivo)
    w, h = Image.open(ruta).size
    ancho = min(ancho, alto_max * w / h)
    doc.add_picture(ruta, width=Cm(ancho))
    doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
    doc.paragraphs[-1].paragraph_format.keep_with_next = True
    return leyenda(doc, "Figura", figuras, texto)


def sin_bordes(tabla):
    borde = OxmlElement("w:tblBorders")
    for lado in ("top", "left", "bottom", "right", "insideH", "insideV"):
        e = OxmlElement(f"w:{lado}")
        e.set(qn("w:val"), "nil")
        borde.append(e)
    tabla._tbl.tblPr.append(borde)


def mosaico(doc, imagenes, texto, alto=9.5):
    """Varias capturas de celular lado a lado, cada una con su rótulo."""
    n = len(imagenes)
    tabla = doc.add_table(rows=2, cols=n)
    tabla.alignment = WD_TABLE_ALIGNMENT.CENTER
    sin_bordes(tabla)
    ancho_celda = ANCHO / n - 0.3
    for i, (archivo, rotulo) in enumerate(imagenes):
        w, h = Image.open(os.path.join(IMG, archivo)).size
        ancho = min(ancho_celda, alto * w / h)
        celda = tabla.cell(0, i)
        celda.paragraphs[0].add_run().add_picture(os.path.join(IMG, archivo), width=Cm(ancho))
        celda.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
        r = tabla.cell(1, i).paragraphs[0]
        r.add_run(rotulo).font.size = Pt(8.5)
        r.alignment = WD_ALIGN_PARAGRAPH.CENTER
    return leyenda(doc, "Figura", figuras, texto)


def sombrear(celda, color):
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), color)
    celda._tc.get_or_add_tcPr().append(shd)


def tabla(doc, encabezado, filas, anchos, texto):
    leyenda(doc, "Tabla", tablas, texto)
    doc.paragraphs[-1].paragraph_format.keep_with_next = True
    tb = doc.add_table(rows=1, cols=len(encabezado))
    tb.style = "Table Grid"
    tb.alignment = WD_TABLE_ALIGNMENT.CENTER
    for i, titulo in enumerate(encabezado):
        c = tb.rows[0].cells[i]
        c.text = ""
        run = c.paragraphs[0].add_run(titulo)
        run.bold = True
        run.font.size = Pt(9)
        run.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
        sombrear(c, "1F6F8B")
    for fila in filas:
        celdas = tb.add_row().cells
        for i, valor in enumerate(fila):
            celdas[i].text = ""
            celdas[i].paragraphs[0].add_run(str(valor)).font.size = Pt(9)
    for fila in tb.rows:
        for i, ancho in enumerate(anchos):
            fila.cells[i].width = Cm(ancho)
    doc.add_paragraph()
    return tablas[0]


def salto(doc):
    doc.add_paragraph().add_run().add_break(WD_BREAK.PAGE)


# ====================================================================== contenido
def portada(doc):
    reemplazar(doc, "Entregable #", "Entregable: Proyecto final")
    reemplazar(doc, "Título de la Actividad", "Trazabilidad geográfica de RCD en Cali")
    reemplazar(doc, "Nombres y Apellidos", "Nicolás Mera")
    reemplazar(doc, "01/02/2026", "Diciembre de 2026")


def resumen(doc):
    h1(doc, "Resumen")
    t(doc, "Los residuos de construcción y demolición (RCD) que no llegan a un sitio autorizado terminan en separadores, "
           "lotes, parques y canales de Santiago de Cali, donde obstruyen el drenaje y contribuyen a las inundaciones. "
           "La Resolución 0472 de 2017 del Ministerio de Ambiente define quiénes pueden gestionar estos residuos, dónde se "
           "pueden llevar y dónde está prohibido; sin embargo, su control sigue siendo documental: constancias en papel y "
           "reportes trimestrales que llegan tarde.")
    t(doc, "Este proyecto desarrolla una plataforma web de geoinformación, con software libre y arquitectura "
           "cliente-servidor, que convierte esa norma en geometría. Cada movimiento de escombros se abre en el origen, se "
           "amarra a la placa del vehículo y solo lo puede cerrar el receptor que lo recibe, desde dentro de su geocerca. "
           "Si nadie lo cierra en 24 horas, el sistema genera una alerta: el material no llegó a un sitio legal. Las reglas "
           "se implementan como funciones y triggers en PostgreSQL/PostGIS, de modo que no se pueden saltar desde la "
           "interfaz. La plataforma integra una API REST en Flask, pantallas para celular y PC con Leaflet, un servidor de "
           "mapas GeoServer (WMS/WFS), un geocodificador propio para direcciones de Cali y datos oficiales de la IDESC. "
           "Todo el sistema corre en contenedores Docker y se desplegó en un servidor propio.")
    t(doc, "trazabilidad, RCD, PostGIS, geocercas, GeoServer, Leaflet, Resolución 0472 de 2017, Cali.",
      negrita_inicial="Palabras clave: ")


def problema(doc):
    h1(doc, "Planteamiento del problema")
    h2(doc, "Contexto")
    t(doc, "La Alcaldía de Cali ha señalado la incorrecta disposición de residuos como la principal causa de inundaciones "
           "en varios sectores de la ciudad e identificó 119 puntos de arrojo clandestino. Tras el sismo de agosto de 2026, "
           "más de 232.000 toneladas de RCD llegaron al centro de acopio de la Calle 5 con Carrera 50. El marco legal ya "
           "existe: la Resolución 0472 de 2017, modificada por la Resolución 1257 de 2021, obliga a los gestores "
           "(puntos limpios, plantas de aprovechamiento y sitios de disposición final) a inscribirse ante la autoridad "
           "ambiental, a expedir constancias de lo recibido y a reportar cada trimestre (art. 16); obliga al gran generador "
           "a tener un Programa de Manejo Ambiental de RCD (art. 13); prohíbe almacenar RCD en zonas verdes, parques, ríos, "
           "quebradas, canales y humedales (art. 20), y fija para Cali, municipio de categoría especial, una meta de "
           "aprovechamiento del 50 % desde 2026 (art. 19). En Cali, el Decreto 0771 de 2018 encarga al DAGMA de inscribir "
           "a los gestores.")
    h2(doc, "Descripción del problema")
    t(doc, "La norma es esencialmente geográfica, pero su control no lo es. La trazabilidad se basa en documentos que "
           "registran cantidades sin probar dónde terminó el material; una entrega irregular se descubre meses después, "
           "cuando ya es un punto crítico; la meta de aprovechamiento solo se conoce al cerrar la obra, y los arrojos no se "
           "relacionan con su posible origen. Además, el eslabón más débil es el transportador informal, que tiene "
           "incentivos económicos para no llevar el material a un sitio autorizado y no se delataría a sí mismo.")
    t(doc, "¿Cómo puede una plataforma de geoinformación en la web, con tecnologías libres, convertir las reglas de la "
           "Resolución 0472 de 2017 en validaciones espaciales automáticas que apoyen la trazabilidad de los RCD entre "
           "generadores, transportadores y receptores en Cali?", negrita_inicial="Pregunta: ")
    h2(doc, "Objetivos")
    t(doc, "Desarrollar una plataforma web de geoinformación, con software libre y arquitectura cliente-servidor, que "
           "apoye la trazabilidad geográfica de los residuos de construcción y demolición en Santiago de Cali, validando "
           "cada movimiento frente a las disposiciones espaciales de la Resolución 0472 de 2017.",
      negrita_inicial="Objetivo general. ")
    t(doc, "", negrita_inicial="Objetivos específicos.")
    viñetas(doc, [
        "Representar como capas geográficas los receptores inscritos (dónde sí) y las zonas de prohibición del art. 20 "
        "(dónde no), a partir de datos oficiales.",
        "Diseñar e implementar un modelo de datos espacial multiempresa que soporte movimientos, entradas, vehículos, "
        "geocercas, alertas y usuarios con roles.",
        "Implementar al menos tres mecanismos de ingreso georreferenciado: GPS del dispositivo, dirección geocodificada "
        "y selección en el mapa.",
        "Automatizar en la base de datos la validación de cada cierre y la generación de alertas (sin cierre, faltante, "
        "parada en zona prohibida, compuerta abierta en tránsito).",
        "Desarrollar visualizaciones espaciales y alfanuméricas diferenciadas para el operario y el administrador, "
        "incluido el seguimiento de la meta de aprovechamiento.",
        "Publicar las capas comunes mediante servicios OGC (WMS/WFS) y desplegar el sistema de forma reproducible.",
    ])
    h2(doc, "Alcance")
    t(doc, "Zona urbana de Santiago de Cali (22 comunas). Se construye la lógica real (movimientos, cierre por placa, "
           "geocercas, estados y alertas) con datos geográficos oficiales; las empresas, receptores, vehículos y "
           "movimientos son de demostración, y el GPS, los sensores y la cámara de los vehículos se simulan. Quedan fuera "
           "del alcance la integración con los sistemas oficiales del DAGMA y la UAESP, y la facturación.")


def metodologia(doc):
    h1(doc, "Metodología")
    t(doc, "Se trabajó con un enfoque incremental tipo Kanban, en fases cortas que terminan en un entregable verificable. "
           "Cada decisión de diseño se registró con su fecha y su justificación en un registro de decisiones "
           "(docs/00_decisiones.md, decisiones D1 a D25), que permite reconstruir cómo y por qué evolucionó el proyecto. "
           "La validación fue continua: cada fase técnica se cerró con pruebas automáticas.")
    tabla(doc, ["Fase", "Resultado", "Verificación"], [
        ["1. Idea y problema", "Tema RCD; enfoque en gestores; tres capas (norma, operación, problema)", "Revisión de la norma (Res. 0472/2017, 1257/2021, Decreto 0771/2018)"],
        ["2. Diseño funcional", "Modelo multiempresa; cierre por placa; bocetos de 12 pantallas", "Aprobación de cada boceto"],
        ["3. Stack y arquitectura", "Tecnologías del curso, todas de código libre", "Justificación por componente"],
        ["4. Modelo de datos", "20 tablas, diagrama entidad-relación y UML", "Esquema probado en PostGIS"],
        ["5. Reglas", "R1–R8 como triggers y funciones PL/pgSQL; 10 escenarios demo", "25 pruebas automáticas en SQL"],
        ["6. API REST", "47 rutas en Flask; geocodificador propio conectado", "27 pruebas automáticas (pytest)"],
        ["7. Pantallas web", "Celular (M1–M6) y PC (P1–P6)", "Pruebas en navegador, sin errores de consola"],
        ["8. Datos oficiales", "IDESC (WFS) y densidades de la NSR-10", "Recarga y pruebas"],
        ["9. Despliegue", "Docker Compose + GeoServer; servidor propio; GitHub", "Mismo resultado en dos equipos"],
    ], [3.2, 6.6, 5.8], "Fases del proyecto")


def desarrollo(doc):
    h1(doc, "Desarrollo del proyecto")

    h2(doc, "Concepto: tres capas y cierre por placa")
    t(doc, "La plataforma se organiza en tres capas. La capa normativa contiene los receptores inscritos con su geocerca "
           "y las zonas prohibidas del art. 20. La capa de operación registra los movimientos de RCD (origen → placa → "
           "receptor). La capa del problema registra los puntos de arrojo y los cruza con los movimientos cercanos que no "
           "se han cerrado.")
    t(doc, "Cada empresa gestora tiene un espacio privado (vehículos, operarios, clientes, entradas, alertas y reportes) y "
           "comparte un registro común mínimo: la capa normativa y los movimientos abiertos (placa, hora, volumen, tipo y "
           "barrio). La unidad básica es el movimiento: lo abre el generador o el transportador y solo lo cierra el "
           "receptor, buscando la placa en su portería. Así, el receptor no necesita saber de antemano de dónde viene el "
           "camión, y el sistema no depende de que el transportador se reporte a sí mismo. Si nadie cierra el movimiento en "
           "24 horas, queda «sin cierre» y genera una alerta, aunque no se sepa dónde terminó el material.")

    h2(doc, "Arquitectura y tecnologías")
    figura(doc, "30_arquitectura.png", "Arquitectura cliente-servidor de la plataforma.", ancho=ANCHO)
    tabla(doc, ["Componente", "Tecnología", "Justificación"], [
        ["Base de datos", "PostgreSQL 16 + PostGIS 3.5", "Funciones espaciales (ST_Within, ST_DWithin, ST_SquareGrid); vistas para el registro común"],
        ["Reglas", "PL/pgSQL y triggers", "Las reglas viven en la base de datos y no se pueden saltar desde la interfaz"],
        ["Ruteo", "pgRouting 3.8", "Previsto para la ruta al receptor más cercano"],
        ["API", "Flask (Python) + gunicorn", "API REST ligera; sesión con roles; GeoJSON armado en PostGIS"],
        ["Servidor de mapas", "GeoServer 2.28", "Publica capas comunes por WMS/WFS con estilos SLD"],
        ["Mapas web", "Leaflet + markercluster + heat + draw", "Mapa temático, calor, clúster, dibujo de geocercas"],
        ["Análisis en el navegador", "Turf.js", "Franja de protección de ríos y canales dibujados; áreas"],
        ["Gráficos", "Chart.js", "Tendencias, estados y avance de la meta"],
        ["Interfaz", "Bootstrap 5", "Misma web adaptable a celular y PC, sin compilación"],
        ["Geocodificación", "Geocodificador propio (FastAPI)", "Direcciones de Cali con nivel de confianza"],
        ["Despliegue", "Docker Compose", "El mismo sistema en cualquier equipo con un solo comando"],
    ], [3.3, 4.4, 7.9], "Componentes tecnológicos (todos de código libre).")

    h2(doc, "Modelo de datos")
    t(doc, "El modelo tiene 20 tablas en el esquema rcd, con geometrías en EPSG:4326 y cálculos métricos con el tipo "
           "geography. Una entrada en la portería puede cerrar varios movimientos de la misma placa (tabla "
           "movimiento_entrada). Las zonas prohibidas, las comunas y los barrios no se relacionan por llaves foráneas sino "
           "espacialmente (ST_Within, ST_Intersects). Los parámetros de negocio (24 horas, tolerancias, meta del 50 %) "
           "están en una tabla y se cambian sin tocar código.")
    figura(doc, "31_entidad_relacion.png", "Diagrama entidad-relación del modelo de datos.", ancho=ANCHO)
    tabla(doc, ["Capa", "Tablas", "Alcance"], [
        ["Referencia", "comuna, barrio, tipo_rcd, parametro", "Común"],
        ["1. Norma", "receptor, receptor_acepta, zona_prohibida", "Común"],
        ["Empresa", "empresa, usuario, transportador, vehiculo, obra", "Privada por empresa"],
        ["2. Operación", "movimiento, entrada, movimiento_entrada, movimiento_evento, posicion_gps, evento_sensor, alerta", "Movimientos abiertos: común; el resto: privado"],
        ["3. Problema", "punto_arrojo", "Privada"],
    ], [2.8, 8.6, 4.2], "Tablas del modelo por capa.")

    h2(doc, "Diagramas UML")
    figura(doc, "34_uml_casos_de_uso.png", "Diagrama de casos de uso por perfil.", ancho=12.5)
    figura(doc, "32_uml_estados.png", "Diagrama de estados del movimiento.", ancho=12.5)
    figura(doc, "33_uml_secuencia_cierre.png", "Diagrama de secuencia del cierre por placa.", ancho=ANCHO)

    h2(doc, "Reglas en la base de datos")
    tabla(doc, ["Regla", "Qué hace", "Implementación"], [
        ["R1", "Solo se cierra con el dispositivo del portero dentro de la geocerca del receptor", "Trigger en entrada (ST_DWithin)"],
        ["R2", "El gestor integrado cierra sus propios viajes solo con GPS del camión dentro de su planta", "Trigger diferido"],
        ["R3", "Si llega menos de lo declarado: «cerrado con faltante» + alerta", "Trigger diferido (suma de lo declarado)"],
        ["R4", "Sin cierre a las 24 h: alerta alta (con agravante si fue rechazado)", "fn_marcar_sin_cierre() cada 5 min"],
        ["R5", "El rechazo deja el movimiento abierto y sugiere receptores que aceptan el material", "Trigger + fn_receptores_sugeridos()"],
        ["R6", "Paradas largas fuera de geocercas; alta si están en zona prohibida", "fn_paradas() sobre el rastro GPS"],
        ["R7", "Compuerta abierta o movimiento en la carga en tránsito", "Trigger en evento_sensor"],
        ["R8", "Peso estimado con la densidad si no se pesa (Res. 0472, art. 19, par. 1)", "Trigger en entrada"],
    ], [1.4, 8.6, 5.6], "Reglas implementadas en PostgreSQL/PostGIS.")

    h2(doc, "Datos oficiales")
    t(doc, "Las comunas (22), los barrios (342) y las zonas prohibidas (2.139) se descargan por WFS del GeoServer de la "
           "Infraestructura de Datos Espaciales de Santiago de Cali (IDESC). Las rondas de ríos y quebradas son las "
           "áreas forestales protectoras del recurso hídrico del POT 2014 (Acuerdo 0373), que ya traen su franja oficial "
           "(30 m en quebradas y humedales, 100 m en nacimientos); a ellas se suman los humedales urbanos del DAGMA y los "
           "parques y zonas verdes del espacio público efectivo. Las densidades para estimar el peso provienen de la "
           "Tabla B.3.2-1 de la NSR-10 (por ejemplo, 2,15 t/m³ para pétreos).")

    h2(doc, "Servicios web geográficos")
    viñetas(doc, [
        ("API REST: ", "47 rutas agrupadas por pantalla; las capas salen en GeoJSON armado en PostGIS y cada empresa "
                       "solo ve lo suyo. Los errores de las reglas llegan al usuario con su mensaje."),
        ("GeoServer: ", "publica solo capas comunes (capa normativa, comunas y barrios) con estilos SLD versionados y "
                        "configurados por su API REST. Los datos privados nunca pasan por GeoServer, porque WMS/WFS no "
                        "controla sesiones ni empresas. La web lo consume a través de la API (/geoserver/rcd/wms), que "
                        "solo deja pasar los servicios OGC."),
        ("Geocodificador propio: ", "desarrollado en el curso anterior; convierte direcciones de Cali en coordenadas "
                                    "con un nivel de confianza. Si la confianza es menor a 60, la pantalla pide confirmar "
                                    "el punto en el mapa."),
    ])

    h2(doc, "Interfaces de usuario")
    t(doc, "Las pantallas operativas están pensadas para celular (botones grandes, un paso por pantalla) y las de control "
           "para PC. El pequeño generador no necesita cuenta: registra sus escombros con un enlace y recibe su "
           "certificado.")
    mosaico(doc, [("01_inicio_sesion.png", "Inicio de sesión"), ("02_generador_registro.png", "Registro sin cuenta (M1)"),
                  ("03_generador_estado_cerrado.png", "Estado y certificado")],
            "Inicio de sesión y enlace del pequeño generador.")
    mosaico(doc, [("06_portero_placa.png", "1. Placa"), ("07_portero_movimientos.png", "2. Movimientos abiertos"),
                  ("08_portero_recibido.png", "3. Lo recibido"), ("09_portero_rechazo.png", "4. Rechazo")],
            "Entradas del receptor (M2): cierre por placa en cuatro pasos.", alto=8.5)
    mosaico(doc, [("10_campo_mapa.png", "Mapa (M4)"), ("13_campo_registro.png", "Registro"),
                  ("11_campo_viajes.png", "Viajes (M6)"), ("12_campo_datos.png", "Datos (M6)")],
            "Pantallas del conductor e inspector.", alto=8.5)
    figura(doc, "20_admin_dashboard.png", "Dashboard del administrador (P1): meta de aprovechamiento, indicadores, "
                                          "tendencias, avance por obra y operarios más activos.")
    figura(doc, "21_admin_seguimiento.png", "Seguimiento (P2): viajes en tránsito, recorrido GPS, cámara de carga "
                                            "simulada y línea de tiempo de sensores.")
    figura(doc, "22_admin_control_wms.png", "Control (P3): alertas por gravedad y mapa con flujos, comunas y capa "
                                            "normativa servidas por GeoServer (WMS).")
    figura(doc, "23_admin_geocercas.png", "Geocercas y capa normativa (P4) con los datos oficiales de la IDESC.")
    figura(doc, "24_admin_movimientos.png", "Movimientos (P5): tabla filtrable, corrección de ubicación y anulación.")

    h2(doc, "Despliegue")
    t(doc, "El sistema completo se describe en un archivo docker-compose.yml con cinco servicios: base de datos "
           "(PostgreSQL + PostGIS + pgRouting), GeoServer, un servicio que configura GeoServer automáticamente, la API y "
           "las tareas periódicas. La primera vez carga el esquema, las reglas, los datos de demostración y los datos de la "
           "IDESC. Se desplegó con resultados idénticos en un PC con Windows (Docker Desktop) y en un servidor propio con "
           f"Ubuntu, que se actualiza desde el repositorio público {REPO}.")


def resultados(doc):
    h1(doc, "Resultados y análisis")
    h2(doc, "Cumplimiento de los requisitos del curso")
    tabla(doc, ["Requisito", "Mín.", "Cómo se cumple"], [
        ["Usuario: ingreso espacial y alfanumérico", "3", "GPS · dirección (geocodificador propio) · clic en el mapa, con foto y atributos"],
        ["Usuario: visualización espacial", "3", "Mapa temático de obras · mapa de calor de m³ · clúster de movimientos"],
        ["Usuario: visualización alfanumérica", "3", "Lista filtrable de viajes · gráfico por tipo de RCD · tabla de avance por obra"],
        ["Admin: modificar o eliminar", "2", "Corregir ubicación (auditado) · anular · anular por rango de fechas · editar/eliminar geocercas"],
        ["Admin: visualización espacial", "2", "Flujos obra → receptor · clúster · densidad en grilla · recorrido GPS · capas WMS"],
        ["Admin: visualización alfanumérica", "2", "Operarios más activos · tendencia por tipo · meta de aprovechamiento · reporte trimestral"],
        ["Roles diferenciados", "—", "Administrador y Usuario (perfiles portero, conductor, inspector)"],
        ["Código libre y cliente-servidor", "—", "Todo el stack es libre; navegador ↔ API ↔ PostGIS/GeoServer"],
    ], [5.0, 1.1, 9.5], "Cumplimiento de los requisitos.")
    h2(doc, "Pruebas")
    t(doc, "Se escribieron 25 pruebas automáticas en SQL para las reglas (por ejemplo, intentar cerrar desde 9 km de la "
           "planta, cerrar un movimiento con otra placa o reabrir uno cerrado: todas son bloqueadas con un mensaje claro) "
           "y 27 pruebas de la API con pytest (permisos por rol, aislamiento entre empresas, recorrido completo del "
           "generador, geocodificador y capas GeoJSON). Todas se aprueban. Las pantallas se probaron en el navegador en "
           "formato celular y PC.")
    h2(doc, "Análisis")
    t(doc, "El aporte principal es convertir la norma en geometría y dejar que la base de datos espacial la aplique. "
           "La regla «solo cierra quien recibe» resuelve el punto débil identificado al inicio: el transportador informal "
           "no necesita usar la aplicación para que su viaje quede controlado, porque el registro se abre en el origen y "
           "se verifica en el destino. El único caso que escapa al sistema es el viaje que nadie registra en el origen y "
           "termina botado; incluso entonces queda una señal indirecta en el historial de la placa y en los arrojos "
           "reportados.")
    t(doc, "", negrita_inicial="Limitaciones.")
    viñetas(doc, [
        "Las empresas, receptores y movimientos son de demostración; el listado de gestores del DAGMA no incluye la "
        "geometría de sus predios.",
        "Las densidades de la NSR-10 son de material sólido y sobreestiman el peso del escombro suelto; por eso cada "
        "registro guarda si el peso fue medido o estimado.",
        "El GPS, los sensores y la cámara de los vehículos se simulan.",
        "El modelo solo cierra movimientos en receptores que usan la plataforma, y nadie supervisa a los "
        "transportadores independientes (rol natural de la autoridad ambiental).",
    ])


def conclusiones(doc):
    h1(doc, "Conclusiones")
    viñetas(doc, [
        "Las disposiciones de la Resolución 0472 de 2017 son esencialmente espaciales y pueden convertirse en geocercas y "
        "zonas prohibidas que se validan automáticamente con PostGIS.",
        "Ubicar las reglas en la base de datos, mediante triggers y funciones, garantiza que se cumplan sin importar la "
        "interfaz desde la que se use el sistema.",
        "El cierre por placa en el receptor permite controlar a los transportadores informales sin depender de su "
        "colaboración.",
        "Los datos abiertos de la IDESC, en particular las áreas protectoras del recurso hídrico del POT 2014, permiten "
        "trabajar con franjas de protección oficiales en lugar de supuestas.",
        "Separar las capas comunes (GeoServer) de los datos privados (API con sesiones) conserva la confidencialidad de "
        "cada empresa sin renunciar a los estándares OGC.",
        "La integración del geocodificador propio demuestra la reutilización de un servicio de geoinformación entre "
        "proyectos mediante una API.",
        "Docker hace que el sistema completo, incluido GeoServer, se despliegue igual en cualquier equipo.",
    ])
    t(doc, "", negrita_inicial="Trabajo futuro.")
    viñetas(doc, [
        "Ruta al receptor más cercano por la red vial con pgRouting.",
        "Integración con dispositivos GPS reales (por ejemplo, con el servidor libre Traccar) y con los sistemas de la "
        "autoridad ambiental.",
        "Publicación en internet con HTTPS, necesaria para usar el GPS y la cámara del celular.",
    ])


def recursos(doc):
    h1(doc, "Recursos")
    viñetas(doc, [
        ("Código fuente: ", REPO),
        ("Demostración: ", "enlace público pendiente (publicación con HTTPS en la fase final)"),
        ("Video de sustentación: ", "enlace pendiente"),
    ])
    h2(doc, "Referencias")
    for ref in [
        "Ministerio de Ambiente y Desarrollo Sostenible. Resolución 0472 de 2017, por la cual se reglamenta la gestión integral de los residuos generados en las actividades de construcción y demolición (RCD).",
        "Ministerio de Ambiente y Desarrollo Sostenible. Resolución 1257 de 2021, por la cual se modifica la Resolución 0472 de 2017.",
        "Alcaldía de Santiago de Cali. Decreto 0771 de 2018.",
        "Concejo de Santiago de Cali. Acuerdo 0373 de 2014, Plan de Ordenamiento Territorial.",
        "Asociación Colombiana de Ingeniería Sísmica. Reglamento NSR-10, Título B, Tabla B.3.2-1.",
        "Infraestructura de Datos Espaciales de Santiago de Cali (IDESC). Servicios WFS: https://ws-idesc.cali.gov.co/geoserver/wfs",
        "Alcaldía de Santiago de Cali. Listado de gestores de RCD autorizados por el DAGMA.",
    ]:
        p = doc.add_paragraph()
        p.paragraph_format.left_indent = Cm(0.8)
        p.paragraph_format.first_line_indent = Cm(-0.8)
        p.add_run(ref).font.size = Pt(9.5)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--plantilla", required=True)
    ap.add_argument("--salida", default=os.path.join(RAIZ, "docs", "memoria", "Memoria_Proyecto_Final_RCD.docx"))
    args = ap.parse_args()
    doc = Document(args.plantilla)
    preparar_estilos(doc)
    portada(doc)
    borrar_desde(doc, "Resumen")
    for seccion in (resumen, problema, metodologia, desarrollo, resultados, conclusiones, recursos):
        seccion(doc)
    doc.save(args.salida)
    print(f"Memoria generada: {args.salida} · {figuras[0]} figuras · {tablas[0]} tablas")


if __name__ == "__main__":
    main()
