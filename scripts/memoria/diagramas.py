"""Convierte a PNG los diagramas Mermaid de docs/04_modelo_datos.md y el de arquitectura (Edge + Mermaid).
Uso:  .venv/Scripts/python scripts/memoria/diagramas.py
"""
import os
import re

from playwright.sync_api import sync_playwright

RAIZ = os.path.join(os.path.dirname(__file__), "..", "..")
SALIDA = os.path.join(RAIZ, "docs", "memoria", "img")

ARQUITECTURA = """
flowchart TB
  subgraph CLIENTE["Cliente: navegador web"]
    direction LR
    M["Celular<br/>generador · portero · conductor"]
    P["PC<br/>administrador"]
  end
  subgraph DOCKER["Servidor: Docker Compose"]
    direction LR
    A["API Flask + pantallas web<br/>(gunicorn)"]
    G["GeoServer 2.28<br/>WMS / WFS · estilos SLD"]
    T["Tareas<br/>R4 y R6 cada 5 min"]
    D[("PostgreSQL 16 · PostGIS · pgRouting<br/>modelo de datos + reglas R1–R8")]
  end
  subgraph EXT["Servicios externos"]
    direction LR
    GEO["Geocodificador propio<br/>FastAPI · servidor Lenovo"]
    IDESC["IDESC Cali<br/>WFS oficial"]
  end
  M -- "HTTPS · JSON / GeoJSON" --> A
  P -- "HTTPS · JSON / GeoJSON / WMS" --> A
  A -- "intermediario /geoserver/rcd/wms" --> G
  A -- SQL --> D
  G -- SQL --> D
  T -- SQL --> D
  A -- "dirección → punto" --> GEO
  IDESC -. "carga de comunas, barrios y zonas" .-> D
"""

PLANTILLA = """<!doctype html><html><head><meta charset="utf-8">
<script src="https://cdn.jsdelivr.net/npm/mermaid@10.9.1/dist/mermaid.min.js"></script>
<style>body{margin:0;background:#fff;font-family:Arial,sans-serif}#d{display:inline-block;padding:16px}</style>
</head><body><div id="d"></div></body></html>"""


def bloques_mermaid():
    with open(os.path.join(RAIZ, "docs", "04_modelo_datos.md"), encoding="utf-8") as f:
        texto = f.read()
    bloques = re.findall(r"```mermaid\n(.*?)```", texto, flags=re.S)
    nombres = ["31_entidad_relacion", "32_uml_estados", "33_uml_secuencia_cierre", "34_uml_casos_de_uso"]
    return dict(zip(nombres, bloques))


def main():
    os.makedirs(SALIDA, exist_ok=True)
    diagramas = {"30_arquitectura": ARQUITECTURA, **bloques_mermaid()}
    with sync_playwright() as pw:
        nav = pw.chromium.launch(channel="msedge")
        pg = nav.new_page(device_scale_factor=2, viewport={"width": 1600, "height": 1200})
        pg.set_content(PLANTILLA)
        pg.wait_for_function("window.mermaid !== undefined")
        pg.evaluate("mermaid.initialize({startOnLoad:false, theme:'neutral', fontFamily:'Arial', er:{useMaxWidth:false}, flowchart:{useMaxWidth:false}, sequence:{useMaxWidth:false}})")
        for nombre, codigo in diagramas.items():
            pg.evaluate("""async ([id, codigo]) => {
                const {svg} = await mermaid.render(id, codigo);
                document.getElementById('d').innerHTML = svg; }""", [f"g{nombre}", codigo])
            pg.locator("#d").screenshot(path=os.path.join(SALIDA, f"{nombre}.png"))
            print("  ✓", nombre)
        nav.close()


if __name__ == "__main__":
    main()
