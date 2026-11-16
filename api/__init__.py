"""API de la plataforma de trazabilidad geográfica de RCD.

Ejecutar desde la raíz del proyecto:
    flask --app api run                 # servidor de desarrollo en http://localhost:5000
    flask --app api claves-demo         # asigna la clave 'demo1234' a los usuarios de demostración
    flask --app api tareas              # corre una vez las tareas periódicas (sin cierre, paradas)
"""
import datetime
import decimal
import os
import threading
import urllib.error
import urllib.request

import click
import psycopg
from flask import Flask, Response, jsonify, request, send_from_directory
from flask.json.provider import DefaultJSONProvider
from werkzeug.security import generate_password_hash

from . import db
from .comun import ErrorUsuario
from .config import Config


class ProveedorJSON(DefaultJSONProvider):
    """Números de PostgreSQL (numeric) como números y fechas en formato ISO 8601."""

    @staticmethod
    def default(o):
        if isinstance(o, decimal.Decimal):
            return float(o)
        if isinstance(o, (datetime.datetime, datetime.date)):
            return o.isoformat()
        return DefaultJSONProvider.default(o)


def create_app(config=None):
    app = Flask(__name__, static_folder=None)
    app.json = ProveedorJSON(app)
    app.config.from_object(Config)
    if config:
        app.config.update(config)

    app.teardown_appcontext(db.cerrar)

    from .rutas import admin, mapas, operacion, publico, sesion
    for modulo in (sesion, publico, operacion, admin, mapas):
        app.register_blueprint(modulo.bp)

    _registrar_errores(app)
    _registrar_archivos(app)
    _registrar_comandos(app)
    _iniciar_tareas(app)
    return app


# ---------------------------------------------------------------- errores
def _registrar_errores(app):
    @app.errorhandler(ErrorUsuario)
    def error_usuario(e):
        return jsonify(error=e.mensaje), e.estado

    @app.errorhandler(psycopg.Error)
    def error_bd(e):
        # Los RAISE EXCEPTION de los triggers (reglas R1–R8) y las restricciones
        # llegan aquí y se muestran al usuario con su mensaje.
        diag = getattr(e, "diag", None)
        mensaje = (diag.message_primary if diag else None) or str(e)
        if isinstance(e, (psycopg.errors.RaiseException, psycopg.errors.IntegrityError,
                          psycopg.errors.DataError)):
            return jsonify(error=mensaje), 400
        app.logger.exception("Error de base de datos")
        return jsonify(error="Error interno de la base de datos"), 500

    @app.errorhandler(404)
    def no_encontrado(_e):
        return jsonify(error="No encontrado"), 404

    @app.errorhandler(413)
    def muy_grande(_e):
        return jsonify(error="El archivo es demasiado grande (máximo 10 MB)"), 413


# ---------------------------------------------------------------- archivos (fotos y web)
def _registrar_archivos(app):
    @app.get("/fotos/<path:nombre>")
    def foto(nombre):
        return send_from_directory(app.config["CARPETA_FOTOS"], nombre)

    @app.get("/geoserver/rcd/<servicio>")
    def geoserver(servicio):
        """Intermediario hacia GeoServer: solo los servicios OGC del workspace rcd (WMS/WFS),
        nunca la administración. Así la web usa un solo origen y un solo puerto."""
        base = app.config["GEOSERVER_URL"]
        if not base or servicio not in ("wms", "wfs", "ows"):
            return jsonify(error="No encontrado"), 404
        url = f"{base.rstrip('/')}/rcd/{servicio}?{request.query_string.decode()}"
        try:
            with urllib.request.urlopen(url, timeout=30) as r:
                return Response(r.read(), r.status, content_type=r.headers.get("Content-Type"),
                                headers={"Cache-Control": "public, max-age=300"})
        except urllib.error.HTTPError as e:
            return Response(e.read(), e.code, content_type=e.headers.get("Content-Type"))
        except urllib.error.URLError:
            return jsonify(error="GeoServer no está disponible"), 503

    @app.get("/")
    @app.get("/<path:ruta>")
    def web(ruta="index.html"):
        carpeta = app.config["CARPETA_WEB"]
        if ruta.startswith("m/"):                    # enlace público del generador: /m/RCD-XXXX
            ruta = "generador.html"
        if os.path.isfile(os.path.join(carpeta, ruta)):
            return send_from_directory(carpeta, ruta)
        return jsonify(error="No encontrado"), 404


# ---------------------------------------------------------------- comandos y tareas
def ejecutar_tareas(app):
    """Tareas periódicas: R4 (sin cierre a las 24 h) y R6 (paradas sospechosas)."""
    with psycopg.connect(app.config["DATABASE_URL"]) as conn:
        sin_cierre = conn.execute("SELECT rcd.fn_marcar_sin_cierre()").fetchone()[0]
        paradas = conn.execute("SELECT rcd.fn_generar_alertas_paradas()").fetchone()[0]
    return sin_cierre, paradas


def asignar_claves_demo(database_url, clave="demo1234"):
    with psycopg.connect(database_url) as conn:
        filas = conn.execute("SELECT id FROM rcd.usuario WHERE password_hash = 'DEMO'").fetchall()
        for (id_usuario,) in filas:
            conn.execute("UPDATE rcd.usuario SET password_hash = %s WHERE id = %s",
                         (generate_password_hash(clave), id_usuario))
    return len(filas)


def _registrar_comandos(app):
    @app.cli.command("tareas")
    def comando_tareas():
        """Corre una vez las tareas periódicas."""
        sin_cierre, paradas = ejecutar_tareas(app)
        click.echo(f"Movimientos marcados sin cierre: {sin_cierre} · alertas por paradas: {paradas}")

    @app.cli.command("claves-demo")
    @click.option("--clave", default="demo1234", show_default=True)
    def comando_claves(clave):
        """Asigna una clave a los usuarios de demostración."""
        n = asignar_claves_demo(app.config["DATABASE_URL"], clave)
        click.echo(f"Clave asignada a {n} usuarios de demostración")


def _iniciar_tareas(app):
    minutos = app.config["TAREAS_CADA_MIN"]
    if minutos <= 0 or app.config.get("TESTING"):
        return
    if app.debug and os.environ.get("WERKZEUG_RUN_MAIN") != "true":
        return                                        # evita el doble arranque del recargador

    def ciclo():
        try:
            ejecutar_tareas(app)
        except Exception:                             # una falla no debe tumbar el servidor
            app.logger.exception("Falló la tarea periódica")
        temporizador = threading.Timer(minutos * 60, ciclo)
        temporizador.daemon = True
        temporizador.start()

    ciclo()
