"""Conexión con el geocodificador propio. Se simula su API para no depender de la red;
la prueba real contra el Lenovo se hace aparte (ver docs/05_api.md)."""
import io
import json
import urllib.error

import pytest

from api import geocodificador
from conftest import foto

URL = "http://geocodificador.prueba/api"
RESPUESTA = {"lat": 3.42423, "lon": -76.54684, "confianza": 75, "direccion_normalizada": "CALLE 5 # 39-20",
             "fuentes": "interpolacion", "barrio": "Urbanización Nueva Granada", "comuna": "19"}


class Respuesta(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.close()


@pytest.fixture
def con_geocodificador(app, monkeypatch):
    monkeypatch.setitem(app.config, "GEOCODIFICADOR_URL", URL)

    def responder(cuerpo=None, error=None):
        def urlopen(url, timeout):
            assert url.startswith(f"{URL}/geocode?direccion=")
            if error:
                raise error
            return Respuesta(json.dumps(cuerpo).encode())
        monkeypatch.setattr(geocodificador.urllib.request, "urlopen", urlopen)
    return responder


def test_direccion_encontrada(cliente, con_geocodificador):
    con_geocodificador(RESPUESTA)
    r = cliente.get("/api/publico/geocodificar?q=Calle 5 # 39-20")
    assert r.status_code == 200
    assert r.json["lat"] == pytest.approx(3.42423) and r.json["confianza"] == 75
    assert r.json["verificar_en_mapa"] is False


def test_confianza_baja_pide_verificar(cliente, con_geocodificador):
    con_geocodificador({**RESPUESTA, "confianza": 45})
    assert cliente.get("/api/publico/geocodificar?q=Cra 39 con 5").json["verificar_en_mapa"] is True


def test_direccion_no_encontrada(cliente, con_geocodificador):
    con_geocodificador(error=urllib.error.HTTPError(URL, 404, "no", {}, None))
    r = cliente.get("/api/publico/geocodificar?q=direccion inventada")
    assert r.status_code == 404 and "mapa" in r.json["error"]


def test_geocodificador_caido(cliente, con_geocodificador):
    con_geocodificador(error=urllib.error.URLError("sin red"))
    r = cliente.get("/api/publico/geocodificar?q=Calle 5 # 39-20")
    assert r.status_code == 503 and "GPS" in r.json["error"]


def test_abrir_movimiento_solo_con_la_direccion(cliente, con_geocodificador):
    con_geocodificador(RESPUESTA)
    r = cliente.post("/api/publico/movimientos", data={
        "placa": "XYZ123", "tipo_rcd": "3", "volumen": "1", "mecanismo": "direccion",
        "direccion": "cl 5 # 39 20", "foto_carga": foto()}, content_type="multipart/form-data")
    assert r.status_code == 201, r.json
    estado = cliente.get(f"/api/publico/movimientos/{r.json['codigo']}").json
    assert estado["barrio"] == "Oriente A (demo)"          # el punto geocodificado cayó en ese barrio
