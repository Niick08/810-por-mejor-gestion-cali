"""Puente hacia el geocodificador propio (Geocod-IngeoGOP, proyecto del curso anterior).

Se conecta de una de dos formas (variables de entorno):

  GEOCODIFICADOR_URL     URL base de su API REST (FastAPI). Ejemplo, el Lenovo por Tailscale:
                         http://100.109.154.10/api   → se llama GET {URL}/geocode?direccion=...
  GEOCODIFICADOR_MODULO  (alternativa) módulo de Python con geocodificar(texto) -> (lon, lat)

Devuelve siempre un diccionario con lon, lat, confianza (0–100), dirección normalizada,
barrio y comuna. Si la confianza es baja, la pantalla le pide al usuario revisar el punto.
"""
import importlib
import json
import urllib.error
import urllib.parse
import urllib.request

from flask import current_app

from .comun import ErrorUsuario

NO_ENCONTRADA = "No se encontró esa dirección. Revísala o ubica el punto en el mapa."


def geocodificar(direccion):
    url = current_app.config.get("GEOCODIFICADOR_URL")
    if url:
        resultado = _por_http(url, direccion)
    elif current_app.config.get("GEOCODIFICADOR_MODULO"):
        resultado = _por_modulo(current_app.config["GEOCODIFICADOR_MODULO"], direccion)
    else:
        raise ErrorUsuario("La búsqueda por dirección aún no está configurada. "
                           "Ubica el punto con el mapa o con el GPS.", 503)
    minima = current_app.config["GEOCODIFICADOR_CONFIANZA_MIN"]
    confianza = resultado.get("confianza")
    resultado["verificar_en_mapa"] = confianza is not None and confianza < minima
    return resultado


def _por_http(url_base, direccion):
    url = f"{url_base.rstrip('/')}/geocode?{urllib.parse.urlencode({'direccion': direccion})}"
    try:
        with urllib.request.urlopen(url, timeout=current_app.config["GEOCODIFICADOR_TIMEOUT_S"]) as r:
            datos = json.load(r)
    except urllib.error.HTTPError as e:
        if e.code in (404, 422):
            raise ErrorUsuario(NO_ENCONTRADA, 404)
        raise ErrorUsuario("El servicio de direcciones respondió con un error. Usa el mapa o el GPS.", 503)
    except (urllib.error.URLError, TimeoutError, ValueError):
        current_app.logger.warning("Geocodificador no disponible en %s", url_base)
        raise ErrorUsuario("El servicio de direcciones no está disponible. Usa el mapa o el GPS.", 503)
    return {
        "lon": float(datos["lon"]),
        "lat": float(datos["lat"]),
        "confianza": datos.get("confianza"),
        "direccion_normalizada": datos.get("direccion_normalizada"),
        "barrio": datos.get("barrio"),
        "comuna": datos.get("comuna"),
        "fuente": datos.get("fuentes"),
    }


def _por_modulo(nombre_modulo, direccion):
    resultado = importlib.import_module(nombre_modulo).geocodificar(direccion)
    if not resultado:
        raise ErrorUsuario(NO_ENCONTRADA, 404)
    lon, lat = resultado
    return {"lon": float(lon), "lat": float(lat), "confianza": None,
            "direccion_normalizada": direccion, "barrio": None, "comuna": None, "fuente": "modulo"}
