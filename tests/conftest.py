"""Pruebas de la API contra una base con 01–04 + datos de demostración recién cargados.
Base usada: variable TEST_DATABASE_URL (por defecto postgresql://postgres@localhost:5499/rcd_test)."""
import io
import os

import pytest

from api import asignar_claves_demo, create_app

URL = os.environ.get("TEST_DATABASE_URL", "postgresql://postgres@localhost:5499/rcd_test")
CLAVE = "demo1234"


@pytest.fixture(scope="session")
def app(tmp_path_factory):
    asignar_claves_demo(URL, CLAVE)
    return create_app({"TESTING": True, "DATABASE_URL": URL,
                       "CARPETA_FOTOS": str(tmp_path_factory.mktemp("fotos"))})


@pytest.fixture
def cliente(app):
    return app.test_client()


def entrar(cliente, email):
    r = cliente.post("/api/sesion", json={"email": email, "clave": CLAVE})
    assert r.status_code == 200, r.json
    return r.json


def foto(nombre="foto.jpg"):
    return (io.BytesIO(b"\xff\xd8\xff\xe0 foto de prueba"), nombre)
