"""Carga datos oficiales de Santiago de Cali (IDESC) en la base de la plataforma.

Reemplaza las comunas, los barrios y las zonas prohibidas de prueba por las capas oficiales:

  comuna          ← dapm:pdt_dpa_comunas                    (Planeación, división político-administrativa)
  barrio          ← dapm:pdt_dpa_barrios_sectores
  zona_prohibida  ← pot_2014:amb_eep_afp_recurso_hidrico    (áreas forestales protectoras del recurso
                                                              hídrico, POT 2014, ya con su franja de protección)
                  ← pot_2014:bcs_hid_rios                    (cauces de los ríos)
                  ← dagma:hid_sup_humedales_urbanos           (humedales urbanos)
                  ← dapm:epou_epu_espacio_publico_efectivo    (solo parques y zonas verdes)

Las zonas se recortan a la zona urbana (unión de las 22 comunas). Los movimientos existentes
se reasignan a su barrio real por geometría. Todo ocurre en una sola transacción.

Uso (desde la raíz del proyecto):
    .venv/Scripts/python scripts/cargar_datos_reales.py --url postgresql://postgres:CLAVE@localhost:5432/rcd
    # --descargar  vuelve a bajar las capas de la IDESC (si no, usa db/datos_reales/*.geojson)
"""
import argparse
import json
import os
import sys
import urllib.parse
import urllib.request

import psycopg

WFS = "https://ws-idesc.cali.gov.co/geoserver/wfs"
CARPETA = os.path.join(os.path.dirname(__file__), "..", "db", "datos_reales")
CAPAS = {
    "comunas": "dapm:pdt_dpa_comunas",
    "barrios": "dapm:pdt_dpa_barrios_sectores",
    "afp_hidrico": "pot_2014:amb_eep_afp_recurso_hidrico",
    "rios": "pot_2014:bcs_hid_rios",
    "humedales": "dagma:hid_sup_humedales_urbanos",
    "espacio_publico": "dapm:epou_epu_espacio_publico_efectivo",
}
PROPIEDADES = {   # solo los atributos que se usan (los archivos guardados quedan más livianos)
    "comunas": ["comcodigo", "comnombre"],
    "barrios": ["barcodigo", "barnombre", "barcomuna"],
    "afp_hidrico": ["nombre", "buff_dist"],
    "rios": ["nombre"],
    "humedales": ["humnombre"],
    "espacio_publico": ["epepotele", "epepottip", "epebarrio"],
}


def redondear(c):
    """2D y 6 decimales (~10 cm): suficiente para estas capas y mucho más liviano."""
    if c and isinstance(c[0], (int, float)):
        return [round(c[0], 6), round(c[1], 6)]
    return [redondear(x) for x in c]


def caja(c):
    if c and isinstance(c[0], (int, float)):
        return c[0], c[1], c[0], c[1]
    cajas = [caja(x) for x in c]
    return (min(b[0] for b in cajas), min(b[1] for b in cajas), max(b[2] for b in cajas), max(b[3] for b in cajas))


ZONA_URBANA = (-76.60, 3.32, -76.45, 3.51)    # caja aproximada de las 22 comunas (para aligerar archivos)


def descargar(nombre, capa):
    params = {"service": "WFS", "version": "2.0.0", "request": "GetFeature", "typeNames": capa,
              "outputFormat": "application/json", "srsName": "EPSG:4326"}
    print(f"  descargando {capa}…", flush=True)
    with urllib.request.urlopen(f"{WFS}?{urllib.parse.urlencode(params)}", timeout=300) as r:
        datos = json.load(r)
    claves = PROPIEDADES[nombre]
    x0, y0, x1, y1 = ZONA_URBANA
    conservadas = []
    for f in datos["features"]:
        if not f.get("geometry"):
            continue
        bx0, by0, bx1, by1 = caja(f["geometry"]["coordinates"])
        if bx1 < x0 or bx0 > x1 or by1 < y0 or by0 > y1:
            continue                                   # fuera de la zona urbana
        f["geometry"]["coordinates"] = redondear(f["geometry"]["coordinates"])
        f["properties"] = {k: f["properties"].get(k) for k in claves}
        f.pop("id", None)
        conservadas.append(f)
    datos = {"type": "FeatureCollection", "fuente": f"IDESC · {capa}", "features": conservadas}
    os.makedirs(CARPETA, exist_ok=True)
    with open(os.path.join(CARPETA, f"{nombre}.geojson"), "w", encoding="utf-8") as f:
        json.dump(datos, f, ensure_ascii=False, separators=(",", ":"))
    return datos


def leer(nombre, capa, forzar):
    ruta = os.path.join(CARPETA, f"{nombre}.geojson")
    if forzar or not os.path.exists(ruta):
        return descargar(nombre, capa)
    with open(ruta, encoding="utf-8") as f:
        return json.load(f)


SQL_REEMPLAZO = """
-- Comunas y barrios oficiales (las referencias se reasignan después por geometría)
UPDATE rcd.movimiento SET barrio_id = NULL WHERE barrio_id IS NOT NULL;
UPDATE rcd.entrada    SET barrio_origen_id = NULL WHERE barrio_origen_id IS NOT NULL;
DELETE FROM rcd.barrio;
DELETE FROM rcd.comuna;

INSERT INTO rcd.comuna (id, nombre, geom)
SELECT (props->>'comcodigo')::int, props->>'comnombre', ST_Multi(geom)
FROM carga WHERE capa = 'comunas';

INSERT INTO rcd.barrio (id, nombre, comuna_id, geom)
SELECT DISTINCT ON ((props->>'barcodigo')::int)
       (props->>'barcodigo')::int, props->>'barnombre',
       (SELECT c.id FROM rcd.comuna c WHERE c.id = (props->>'barcomuna')::int), ST_Multi(geom)
FROM carga WHERE capa = 'barrios' AND props->>'barcodigo' ~ '^[0-9]+$'
ORDER BY (props->>'barcodigo')::int, ST_Area(geom) DESC;

UPDATE rcd.movimiento m
SET barrio_id = (SELECT b.id FROM rcd.barrio b WHERE ST_Intersects(b.geom, m.geom_origen) LIMIT 1);

-- Zonas prohibidas (Res. 0472/2017, art. 20), recortadas a la zona urbana
DELETE FROM rcd.zona_prohibida;
CREATE TEMP TABLE urbano AS SELECT ST_Union(geom) AS geom FROM rcd.comuna;

INSERT INTO rcd.zona_prohibida (tipo, nombre, fuente, franja_m, geom)
SELECT tipo, nombre, fuente, franja, geom FROM (
  SELECT CASE WHEN props->>'nombre' ILIKE '%humedal%'    THEN 'humedal'
              WHEN props->>'nombre' ILIKE '%canal%'      THEN 'canal'
              WHEN props->>'nombre' ~* 'r[ií]o'          THEN 'rio'
              WHEN props->>'nombre' ILIKE '%nacimiento%' THEN 'otra'       -- nacimientos de agua (100 m)
              ELSE 'quebrada' END AS tipo,                                  -- quebradas y cauces menores
         -- nombre del POT (p. ej. "Afp Quebradas 30m": área forestal protectora y su franja)
         initcap(props->>'nombre') AS nombre,
         'IDESC · POT 2014 (Acuerdo 0373) · áreas forestales protectoras del recurso hídrico' AS fuente,
         nullif(props->>'buff_dist', '')::numeric AS franja,
         ST_Multi(ST_CollectionExtract(ST_Intersection(c.geom, u.geom), 3)) AS geom
  FROM carga c, urbano u WHERE c.capa = 'afp_hidrico' AND ST_Intersects(c.geom, u.geom)
  UNION ALL
  SELECT 'rio', props->>'nombre', 'IDESC · POT 2014 · cauces de ríos', NULL,
         ST_Multi(ST_CollectionExtract(ST_Intersection(c.geom, u.geom), 3))
  FROM carga c, urbano u WHERE c.capa = 'rios' AND ST_Intersects(c.geom, u.geom)
  UNION ALL
  SELECT 'humedal', props->>'humnombre', 'IDESC · DAGMA · humedales urbanos', NULL, ST_Multi(geom)
  FROM carga WHERE capa = 'humedales'
  UNION ALL
  SELECT CASE WHEN props->>'epepotele' ILIKE '%parque%' THEN 'parque' ELSE 'zona_verde' END,
         props->>'epepottip', 'IDESC · DAPM · espacio público efectivo', NULL, ST_Multi(geom)
  FROM carga WHERE capa = 'espacio_publico'
    AND (props->>'epepotele' ILIKE '%parque%' OR props->>'epepotele' ILIKE '%zona%verde%')
) z
WHERE NOT ST_IsEmpty(geom);
"""


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--url", default=os.environ.get("DATABASE_URL"), help="conexión a PostgreSQL")
    p.add_argument("--descargar", action="store_true", help="volver a descargar las capas de la IDESC")
    args = p.parse_args()
    if not args.url:
        sys.exit("Indica la base con --url o con la variable DATABASE_URL")

    capas = {n: leer(n, c, args.descargar) for n, c in CAPAS.items()}
    with psycopg.connect(args.url) as conn:
        conn.execute("CREATE TEMP TABLE carga (capa text, props jsonb, gj text, geom geometry)")
        with conn.cursor().copy("COPY carga (capa, props, gj) FROM STDIN") as copia:
            for nombre, datos in capas.items():
                for f in datos["features"]:
                    if f.get("geometry"):
                        copia.write_row((nombre, json.dumps(f["properties"], ensure_ascii=False),
                                         json.dumps(f["geometry"])))
        # GeoJSON → geometría válida (solo polígonos) en EPSG:4326
        conn.execute("""UPDATE carga SET geom = ST_CollectionExtract(ST_MakeValid(
                          ST_Force2D(ST_SetSRID(ST_GeomFromGeoJSON(gj), 4326))), 3)""")
        conn.execute("CREATE INDEX ON carga USING gist (geom)")
        conn.execute(SQL_REEMPLAZO)
        resumen = conn.execute("""
            SELECT 'comunas' AS capa, count(*) FROM rcd.comuna UNION ALL
            SELECT 'barrios', count(*) FROM rcd.barrio UNION ALL
            SELECT 'zonas prohibidas · ' || tipo, count(*) FROM rcd.zona_prohibida GROUP BY tipo UNION ALL
            SELECT 'movimientos con barrio', count(*) FROM rcd.movimiento WHERE barrio_id IS NOT NULL
            ORDER BY 1""").fetchall()
    print("Carga terminada:")
    for capa, n in resumen:
        print(f"  {capa:<34} {n:>6}")


if __name__ == "__main__":
    main()
