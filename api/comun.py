"""Piezas compartidas: errores para el usuario, sesión y roles, fotos y lectura de datos."""
import os
import uuid
from functools import wraps

from flask import current_app, jsonify, session

EXTENSIONES_FOTO = {".jpg", ".jpeg", ".png", ".webp"}


class ErrorUsuario(Exception):
    """Error que se le muestra tal cual a quien usa la aplicación."""

    def __init__(self, mensaje, estado=400):
        super().__init__(mensaje)
        self.mensaje = mensaje
        self.estado = estado


# ---------------------------------------------------------------- sesión y roles
def usuario_actual():
    return session.get("usuario")


def requiere(rol=None, perfiles=None):
    """Exige sesión iniciada y, opcionalmente, un rol ('admin' / 'usuario') o perfiles."""
    def decorador(funcion):
        @wraps(funcion)
        def envoltura(*args, **kwargs):
            u = session.get("usuario")
            if not u:
                return jsonify(error="Inicia sesión para continuar"), 401
            if rol and u["rol"] != rol:
                return jsonify(error="Tu rol no tiene permiso para esto"), 403
            if perfiles and u.get("perfil") not in perfiles:
                return jsonify(error="Tu perfil no tiene permiso para esto"), 403
            return funcion(*args, **kwargs)
        return envoltura
    return decorador


# ---------------------------------------------------------------- fotos
def guardar_foto(archivo, obligatoria=True, nombre_campo="foto"):
    """Guarda la foto con un nombre aleatorio y devuelve su URL relativa."""
    if archivo is None or not archivo.filename:
        if obligatoria:
            raise ErrorUsuario(f"Falta la {nombre_campo.replace('_', ' ')}")
        return None
    extension = os.path.splitext(archivo.filename)[1].lower()
    if extension not in EXTENSIONES_FOTO:
        raise ErrorUsuario("La foto debe ser JPG, PNG o WEBP")
    carpeta = current_app.config["CARPETA_FOTOS"]
    os.makedirs(carpeta, exist_ok=True)
    nombre = f"{uuid.uuid4().hex}{extension}"
    archivo.save(os.path.join(carpeta, nombre))
    return f"/fotos/{nombre}"


# ---------------------------------------------------------------- lectura de datos
def texto(datos, campo, obligatorio=False):
    valor = (datos.get(campo) or "").strip()
    if obligatorio and not valor:
        raise ErrorUsuario(f"Falta el campo «{campo}»")
    return valor or None


def numero(datos, campo, obligatorio=False, minimo=None):
    valor = datos.get(campo)
    if valor in (None, ""):
        if obligatorio:
            raise ErrorUsuario(f"Falta el campo «{campo}»")
        return None
    try:
        valor = float(str(valor).replace(",", "."))
    except ValueError:
        raise ErrorUsuario(f"«{campo}» debe ser un número")
    if minimo is not None and valor < minimo:
        raise ErrorUsuario(f"«{campo}» debe ser mayor o igual a {minimo}")
    return valor


def entero(datos, campo, obligatorio=False):
    valor = numero(datos, campo, obligatorio)
    return int(valor) if valor is not None else None


def lista(datos, campo):
    """Acepta 'a,b,c', una lista JSON o el mismo campo repetido en un formulario."""
    if hasattr(datos, "getlist") and len(datos.getlist(campo)) > 1:
        valores = datos.getlist(campo)
    else:
        valor = datos.get(campo) or []
        valores = valor.split(",") if isinstance(valor, str) else valor
    return [v.strip() for v in valores if v and v.strip()]


def coordenadas(datos, obligatorio=True):
    lon, lat = numero(datos, "lon"), numero(datos, "lat")
    if lon is None or lat is None:
        if obligatorio:
            raise ErrorUsuario("Falta la ubicación (lon, lat)")
        return None
    if not (-180 <= lon <= 180 and -90 <= lat <= 90):
        raise ErrorUsuario("Ubicación inválida")
    return lon, lat
