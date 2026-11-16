"""Configuración. Todo se puede cambiar con variables de entorno (ver .env.example)."""
import os

RAIZ = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "solo-para-desarrollo-cambiar")
    DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://postgres@localhost:5432/rcd")
    CARPETA_FOTOS = os.environ.get("CARPETA_FOTOS", os.path.join(RAIZ, "fotos"))
    CARPETA_WEB = os.path.join(RAIZ, "web")
    URL_PUBLICA = os.environ.get("URL_PUBLICA", "http://localhost:5000")
    MAX_CONTENT_LENGTH = 10 * 1024 * 1024          # fotos de hasta 10 MB
    TAREAS_CADA_MIN = int(os.environ.get("TAREAS_CADA_MIN", "5"))   # 0 = no correr tareas automáticas
    # Geocodificador propio (Geocod-IngeoGOP). Lo normal: su API REST en el Lenovo por Tailscale.
    GEOCODIFICADOR_URL = os.environ.get("GEOCODIFICADOR_URL", "")          # p. ej. http://100.109.154.10/api
    GEOCODIFICADOR_MODULO = os.environ.get("GEOCODIFICADOR_MODULO", "")    # alternativa: módulo de Python
    GEOCODIFICADOR_TIMEOUT_S = float(os.environ.get("GEOCODIFICADOR_TIMEOUT_S", "8"))
    GEOCODIFICADOR_CONFIANZA_MIN = int(os.environ.get("GEOCODIFICADOR_CONFIANZA_MIN", "60"))
    # GeoServer (en Docker: http://geoserver:8080/geoserver). La API lo expone en /geoserver/rcd/wms
    GEOSERVER_URL = os.environ.get("GEOSERVER_URL", "")
    # Modo demostración: permite simular la ubicación del portero dentro de su receptor
    # (para presentar desde un PC). NUNCA activarlo en producción.
    MODO_DEMO = os.environ.get("MODO_DEMO", "0").lower() in ("1", "true", "si", "sí")
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
