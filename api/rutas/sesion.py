"""Inicio y cierre de sesión."""
from flask import Blueprint, request, session
from werkzeug.security import check_password_hash

from ..comun import ErrorUsuario, requiere, texto
from ..db import uno

bp = Blueprint("sesion", __name__, url_prefix="/api/sesion")


@bp.post("")
def iniciar():
    datos = request.get_json(silent=True) or request.form
    email = (texto(datos, "email", obligatorio=True)).lower()
    clave = texto(datos, "clave", obligatorio=True)
    u = uno("""SELECT u.id, u.nombre, u.email, u.rol, u.perfil, u.empresa_id, u.password_hash,
                      e.nombre AS empresa
               FROM usuario u JOIN empresa e ON e.id = u.empresa_id
               WHERE lower(u.email) = %s AND u.activo AND e.activa""", (email,))
    if not u or not check_password_hash(u["password_hash"], clave):
        raise ErrorUsuario("Correo o clave incorrectos", 401)
    del u["password_hash"]
    session.clear()
    session["usuario"] = u
    return u


@bp.get("")
@requiere()
def actual():
    return session["usuario"]


@bp.delete("")
def cerrar():
    session.clear()
    return {"ok": True}
