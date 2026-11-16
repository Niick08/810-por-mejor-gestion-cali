"""Configura GeoServer por su API REST: workspace, conexión a PostGIS, estilos SLD y capas.

Solo se publican capas COMUNES (sin datos privados de las empresas):
  rcd:capa_normativa  ← vista v_capa_normativa (receptores vigentes + zonas prohibidas del art. 20)
  rcd:comunas         ← tabla comuna
  rcd:barrios         ← tabla barrio
Es repetible: si algo ya existe, lo deja y sigue.
"""
import base64
import json
import os
import time
import urllib.error
import urllib.request

URL = os.environ.get("GEOSERVER_URL", "http://geoserver:8080/geoserver").rstrip("/")
AUTH = "Basic " + base64.b64encode(f"admin:{os.environ['GEOSERVER_PASSWORD']}".encode()).decode()
WS = "rcd"
CARPETA = os.path.dirname(os.path.abspath(__file__))
CAPAS = [  # (nombre publicado, tabla o vista, título, estilo)
    ("capa_normativa", "v_capa_normativa", "Capa normativa RCD: receptores inscritos y zonas prohibidas (Res. 0472, art. 20)", "rcd_normativa"),
    ("comunas", "comuna", "Comunas de Santiago de Cali (IDESC)", "rcd_comunas"),
    ("barrios", "barrio", "Barrios de Santiago de Cali (IDESC)", "rcd_barrios"),
]


def pedir(metodo, ruta, cuerpo=None, tipo="application/json"):
    datos = json.dumps(cuerpo).encode() if isinstance(cuerpo, dict) else cuerpo
    req = urllib.request.Request(f"{URL}/rest/{ruta}", data=datos, method=metodo,
                                 headers={"Authorization": AUTH, "Content-Type": tipo, "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status
    except urllib.error.HTTPError as e:
        return e.code


def existe(ruta):
    return pedir("GET", ruta) == 200


def paso(texto, estado, ok=(200, 201)):
    marca = "ok" if estado in ok else f"ERROR {estado}"
    print(f"[geoserver] {texto}: {marca}", flush=True)
    if estado not in ok:
        raise SystemExit(1)


def main():
    for _ in range(60):                                   # esperar a que GeoServer responda
        if pedir("GET", "about/version.json") == 200:
            break
        time.sleep(5)

    if not existe(f"workspaces/{WS}"):
        paso("workspace rcd", pedir("POST", "workspaces", {"workspace": {"name": WS}}))

    if not existe(f"workspaces/{WS}/datastores/rcd_postgis"):
        conexion = {"host": "db", "port": "5432", "database": "rcd", "schema": "rcd", "user": "rcd",
                    "passwd": os.environ["DB_PASSWORD"], "dbtype": "postgis", "Expose primary keys": "true"}
        cuerpo = {"dataStore": {"name": "rcd_postgis", "connectionParameters": {"entry": [
            {"@key": k, "$": v} for k, v in conexion.items()]}}}
        paso("almacén PostGIS", pedir("POST", f"workspaces/{WS}/datastores", cuerpo))

    for nombre_estilo in {c[3] for c in CAPAS}:
        if not existe(f"workspaces/{WS}/styles/{nombre_estilo}"):
            with open(os.path.join(CARPETA, f"{nombre_estilo}.sld"), "rb") as f:
                paso(f"estilo {nombre_estilo}", pedir("POST", f"workspaces/{WS}/styles?name={nombre_estilo}",
                                                       f.read(), "application/vnd.ogc.sld+xml"))

    for nombre, tabla, titulo, estilo in CAPAS:
        if not existe(f"workspaces/{WS}/datastores/rcd_postgis/featuretypes/{nombre}"):
            cuerpo = {"featureType": {"name": nombre, "nativeName": tabla, "title": titulo, "srs": "EPSG:4326",
                                      "projectionPolicy": "FORCE_DECLARED", "enabled": True}}
            paso(f"capa {nombre}", pedir("POST", f"workspaces/{WS}/datastores/rcd_postgis/featuretypes", cuerpo))
        paso(f"estilo de {nombre}", pedir("PUT", f"layers/{WS}:{nombre}",
                                          {"layer": {"defaultStyle": {"name": f"{WS}:{estilo}"}}}))
    print("[geoserver] listo: WMS en /geoserver/rcd/wms", flush=True)


if __name__ == "__main__":
    main()
