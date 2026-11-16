"""Rutas del Administrador (pantallas P1–P6). Todo se limita a la empresa de quien inició sesión."""
import json

from flask import Blueprint, request
from werkzeug.security import generate_password_hash

from ..comun import ErrorUsuario, coordenadas, entero, numero, requiere, texto, usuario_actual
from ..db import confirmar, consultar, ejecutar, uno

bp = Blueprint("admin", __name__, url_prefix="/api/admin")
ADMIN = dict(rol="admin")


def _empresa():
    return usuario_actual()["empresa_id"]


def _movimiento_propio(codigo):
    """Solo se corrigen o anulan movimientos que abrió la propia empresa."""
    m = uno("SELECT id, codigo, estado FROM movimiento WHERE codigo = %s AND empresa_origen_id = %s",
            (codigo.upper(), _empresa()))
    if not m:
        raise ErrorUsuario("No hay un movimiento con ese código en tu empresa", 404)
    return m


def _geometria(datos):
    """Polígono en GeoJSON (dibujado en el mapa o cargado de un archivo)."""
    geom = datos.get("geometria")
    if not geom:
        raise ErrorUsuario("Falta la geometría (GeoJSON)")
    if isinstance(geom, str):
        geom = json.loads(geom)
    if geom.get("type") not in ("Polygon", "MultiPolygon"):
        raise ErrorUsuario("La geometría debe ser un polígono")
    return json.dumps(geom)


# ===================================================================== P5 MOVIMIENTOS
@bp.patch("/movimientos/<codigo>/ubicacion")
@requiere(**ADMIN)
def corregir_ubicacion(codigo):
    """Corregir la ubicación espacial (requisito Admin: modificar). Queda auditado (E10)."""
    m = _movimiento_propio(codigo)
    lon, lat = coordenadas(request.get_json(silent=True) or request.form)
    ejecutar("UPDATE movimiento SET geom_origen = ST_SetSRID(ST_MakePoint(%s, %s), 4326) WHERE id = %s",
             (lon, lat, m["id"]))
    confirmar()
    return uno("""SELECT tipo, usuario_id, detalle FROM movimiento_evento
                  WHERE movimiento_id = %s ORDER BY id DESC LIMIT 1""", (m["id"],))


@bp.post("/movimientos/<codigo>/anular")
@requiere(**ADMIN)
def anular(codigo):
    m = _movimiento_propio(codigo)
    ejecutar("UPDATE movimiento SET estado = 'anulado' WHERE id = %s", (m["id"],))
    confirmar()
    return {"codigo": m["codigo"], "estado": "anulado"}


@bp.post("/movimientos/anular-rango")
@requiere(**ADMIN)
def anular_rango():
    """Anular por periodo (requisito Admin: eliminar por rango de fechas). Se anula y no se borra,
    para conservar la trazabilidad; los movimientos ya cerrados no se tocan."""
    datos = request.get_json(silent=True) or request.form
    desde, hasta = texto(datos, "desde", True), texto(datos, "hasta", True)
    n = ejecutar("""UPDATE movimiento SET estado = 'anulado'
                    WHERE empresa_origen_id = %s
                      AND estado IN ('abierto', 'rechazado', 'sin_cierre')
                      AND abierto_en >= %s::date AND abierto_en < %s::date + 1""",
                 (_empresa(), desde, hasta))
    confirmar()
    return {"anulados": n}


# ===================================================================== P3 ALERTAS
@bp.get("/alertas")
@requiere(**ADMIN)
def alertas():
    estado = request.args.get("estado", "abierta")
    return {"alertas": consultar("""
        SELECT a.id, a.tipo, a.gravedad, a.estado, a.creada_en, a.detalle,
               m.codigo, coalesce(m.placa, v.placa) AS placa,
               ST_X(a.geom) AS lon, ST_Y(a.geom) AS lat
        FROM alerta a
        LEFT JOIN movimiento m ON m.id = a.movimiento_id
        LEFT JOIN vehiculo v   ON v.id = a.vehiculo_id
        WHERE a.empresa_id = %s AND (%s = 'todas' OR a.estado = %s)
        ORDER BY CASE a.gravedad WHEN 'alta' THEN 1 WHEN 'media' THEN 2 ELSE 3 END, a.creada_en DESC""",
        (_empresa(), estado, estado))}


@bp.patch("/alertas/<int:alerta_id>")
@requiere(**ADMIN)
def revisar_alerta(alerta_id):
    estado = texto(request.get_json(silent=True) or request.form, "estado", True)
    if estado not in ("revisada", "escalada", "abierta"):
        raise ErrorUsuario("Estado inválido: revisada, escalada o abierta")
    n = ejecutar("""UPDATE alerta SET estado = %s, revisada_por = %s
                    WHERE id = %s AND empresa_id = %s""",
                 (estado, usuario_actual()["id"], alerta_id, _empresa()))
    if not n:
        raise ErrorUsuario("Alerta no encontrada", 404)
    confirmar()
    return {"id": alerta_id, "estado": estado}


# ===================================================================== P1 DASHBOARD
@bp.get("/dashboard")
@requiere(**ADMIN)
def dashboard():
    e = _empresa()
    obras = consultar("SELECT * FROM fn_aprovechamiento_obras(%s)", (e,))
    generado = sum(o["generado_t"] or 0 for o in obras)
    aprovechado = sum(o["aprovechado_t"] or 0 for o in obras)
    meta = uno("SELECT fn_param('meta_aprovechamiento_pct') AS m")["m"]
    return {
        "meta": {
            "meta_pct": meta,
            "generado_t": generado,
            "aprovechado_t": aprovechado,
            "porcentaje": round(100 * aprovechado / generado, 1) if generado else None,
            "falta_t": max(round(meta / 100 * generado - aprovechado, 2), 0),
            "por_obra": obras,
        },
        "indicadores": uno("""
            SELECT (SELECT coalesce(sum(e.volumen_recibido_m3), 0) FROM entrada e
                    JOIN receptor r ON r.id = e.receptor_id
                    WHERE r.empresa_id = %(e)s AND e.resultado IN ('recibida', 'parcial', 'sin_origen')) AS m3_recibidos,
                   (SELECT coalesce(sum(volumen_declarado_m3), 0) FROM fn_movimientos_empresa(%(e)s)
                    WHERE estado <> 'anulado') AS m3_movimientos,
                   (SELECT count(*) FROM fn_movimientos_empresa(%(e)s)
                    WHERE estado IN ('abierto', 'rechazado')) AS en_curso,
                   (SELECT count(*) FROM alerta WHERE empresa_id = %(e)s AND estado = 'abierta') AS alertas_abiertas,
                   (SELECT count(*) FROM alerta WHERE empresa_id = %(e)s AND estado = 'abierta'
                    AND gravedad = 'alta') AS alertas_altas,
                   (SELECT count(*) FROM punto_arrojo WHERE empresa_id = %(e)s
                    AND reportado_en >= date_trunc('month', now())) AS arrojos_mes""", dict(e=e)),
        "estados": consultar("""SELECT estado, count(*) AS n FROM fn_movimientos_empresa(%s)
                                GROUP BY estado ORDER BY n DESC""", (e,)),
        "balance_receptores": consultar("""
            SELECT r.nombre,
                   coalesce((SELECT sum(en.volumen_recibido_m3) FROM entrada en
                             WHERE en.receptor_id = r.id AND en.resultado <> 'rechazada'), 0) AS entradas_m3,
                   coalesce((SELECT sum(m.volumen_declarado_m3) FROM movimiento m
                             WHERE m.receptor_origen_id = r.id AND m.estado <> 'anulado'), 0) AS salidas_m3
            FROM receptor r WHERE r.empresa_id = %s ORDER BY r.nombre""", (e,)),
        "operarios_activos": consultar("""
            SELECT *, movimientos + entradas + arrojos AS total
            FROM (SELECT u.nombre, u.perfil,
                         (SELECT count(*) FROM movimiento m WHERE m.abierto_por_usuario_id = u.id) AS movimientos,
                         (SELECT count(*) FROM entrada en WHERE en.usuario_id = u.id) AS entradas,
                         (SELECT count(*) FROM punto_arrojo p WHERE p.reportado_por = u.id) AS arrojos
                  FROM usuario u WHERE u.empresa_id = %s AND u.rol = 'usuario') x
            ORDER BY total DESC, nombre""", (e,)),
        "tendencia_por_tipo": consultar("""
            SELECT date_trunc('week', m.abierto_en)::date AS semana, t.categoria, t.nombre AS tipo_rcd,
                   sum(m.volumen_declarado_m3) AS m3
            FROM fn_movimientos_empresa(%s) m JOIN tipo_rcd t ON t.id = m.tipo_rcd_id
            WHERE m.estado <> 'anulado'
            GROUP BY 1, 2, 3 ORDER BY 1, 3""", (e,)),
    }


@bp.get("/reporte-trimestral")
@requiere(**ADMIN)
def reporte_trimestral():
    """Cantidades recibidas y su destino en el trimestre (Res. 0472, art. 16, num. 4)."""
    anio = entero(request.args, "anio") or uno("SELECT extract(year FROM now())::int AS a")["a"]
    trimestre = entero(request.args, "trimestre") or uno("SELECT extract(quarter FROM now())::int AS t")["t"]
    return {"anio": anio, "trimestre": trimestre, "filas": consultar("""
        SELECT r.nombre AS receptor, r.tipo, t.nombre AS tipo_rcd, t.categoria,
               count(*) AS entradas, sum(e.volumen_recibido_m3) AS m3, sum(e.peso_t) AS toneladas,
               bool_and(e.peso_medido) AS todo_pesado
        FROM entrada e
        JOIN receptor r ON r.id = e.receptor_id
        LEFT JOIN tipo_rcd t ON t.id = e.tipo_rcd_id
        WHERE r.empresa_id = %s AND e.resultado <> 'rechazada'
          AND extract(year FROM e.registrada_en) = %s AND extract(quarter FROM e.registrada_en) = %s
        GROUP BY 1, 2, 3, 4 ORDER BY 1, 3""", (_empresa(), anio, trimestre))}


# ===================================================================== P2 SEGUIMIENTO
@bp.get("/seguimiento")
@requiere(**ADMIN)
def seguimiento():
    """Vehículos de la empresa en tránsito: última posición, sensores y alertas."""
    return {"vehiculos": consultar("""
        SELECT v.placa, v.tiene_gps, v.tiene_camara, m.codigo, m.estado, m.abierto_en,
               o.nombre AS obra, p.registrado_en AS ultima_posicion_en,
               ST_X(p.geom) AS lon, ST_Y(p.geom) AS lat,
               (SELECT json_agg(json_build_object('tipo', s.tipo, 'hora', s.registrado_en, 'video', s.video_url)
                                ORDER BY s.registrado_en)
                FROM evento_sensor s WHERE s.vehiculo_id = v.id
                  AND s.registrado_en >= now() - interval '12 hours') AS sensores,
               (SELECT count(*) FROM alerta a WHERE a.vehiculo_id = v.id AND a.estado = 'abierta') AS alertas
        FROM vehiculo v
        JOIN LATERAL (SELECT * FROM movimiento mm WHERE mm.placa = v.placa
                      AND mm.estado IN ('abierto', 'rechazado') ORDER BY mm.abierto_en DESC LIMIT 1) m ON true
        LEFT JOIN obra o ON o.id = m.obra_id
        LEFT JOIN LATERAL (SELECT * FROM posicion_gps pp WHERE pp.vehiculo_id = v.id
                           ORDER BY pp.registrado_en DESC LIMIT 1) p ON true
        WHERE v.empresa_id = %s
        ORDER BY alertas DESC, v.placa""", (_empresa(),))}


# ===================================================================== P4 GEOCERCAS Y CAPA NORMATIVA
@bp.get("/receptores")
@requiere(**ADMIN)
def receptores():
    return {"receptores": consultar("""
        SELECT r.id, r.nombre, r.tipo, r.pin_dagma, r.vigente_hasta, r.activo,
               ST_AsGeoJSON(r.geocerca)::json AS geometria,
               (SELECT array_agg(t.codigo ORDER BY t.id) FROM receptor_acepta ra
                JOIN tipo_rcd t ON t.id = ra.tipo_rcd_id WHERE ra.receptor_id = r.id) AS acepta
        FROM receptor r WHERE r.empresa_id = %s ORDER BY r.nombre""", (_empresa(),))}


@bp.post("/receptores")
@requiere(**ADMIN)
def crear_receptor():
    datos = request.get_json(silent=True) or {}
    fila = uno("""INSERT INTO receptor (empresa_id, nombre, tipo, pin_dagma, vigente_hasta, direccion, geocerca)
                  VALUES (%s, %s, %s, %s, %s, %s, ST_Multi(ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326)))
                  RETURNING id""",
               (_empresa(), texto(datos, "nombre", True), texto(datos, "tipo", True),
                texto(datos, "pin_dagma"), texto(datos, "vigente_hasta"), texto(datos, "direccion"),
                _geometria(datos)))
    for codigo in datos.get("acepta", []):
        ejecutar("""INSERT INTO receptor_acepta (receptor_id, tipo_rcd_id)
                    SELECT %s, id FROM tipo_rcd WHERE codigo = %s""", (fila["id"], codigo))
    confirmar()
    return fila, 201


@bp.put("/receptores/<int:receptor_id>/geocerca")
@requiere(**ADMIN)
def editar_geocerca(receptor_id):
    n = ejecutar("""UPDATE receptor SET geocerca = ST_Multi(ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326))
                    WHERE id = %s AND empresa_id = %s""",
                 (_geometria(request.get_json(silent=True) or {}), receptor_id, _empresa()))
    if not n:
        raise ErrorUsuario("Receptor no encontrado en tu empresa", 404)
    confirmar()
    return {"id": receptor_id}


@bp.delete("/receptores/<int:receptor_id>")
@requiere(**ADMIN)
def desactivar_receptor(receptor_id):
    """Se desactiva (no se borra): las entradas históricas siguen apuntando a él."""
    n = ejecutar("UPDATE receptor SET activo = false WHERE id = %s AND empresa_id = %s",
                 (receptor_id, _empresa()))
    if not n:
        raise ErrorUsuario("Receptor no encontrado en tu empresa", 404)
    confirmar()
    return {"id": receptor_id, "activo": False}


@bp.post("/zonas-prohibidas")
@requiere(**ADMIN)
def crear_zona():
    datos = request.get_json(silent=True) or {}
    fila = uno("""INSERT INTO zona_prohibida (tipo, nombre, fuente, franja_m, geom)
                  VALUES (%s, %s, %s, %s, ST_Multi(ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326)))
                  RETURNING id""",
               (texto(datos, "tipo", True), texto(datos, "nombre"), texto(datos, "fuente") or "digitalizado",
                numero(datos, "franja_m"), _geometria(datos)))
    confirmar()
    return fila, 201


@bp.put("/zonas-prohibidas/<int:zona_id>")
@requiere(**ADMIN)
def editar_zona(zona_id):
    n = ejecutar("UPDATE zona_prohibida SET geom = ST_Multi(ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326)) WHERE id = %s",
                 (_geometria(request.get_json(silent=True) or {}), zona_id))
    if not n:
        raise ErrorUsuario("Zona no encontrada", 404)
    confirmar()
    return {"id": zona_id}


@bp.delete("/zonas-prohibidas/<int:zona_id>")
@requiere(**ADMIN)
def eliminar_zona(zona_id):
    if not ejecutar("DELETE FROM zona_prohibida WHERE id = %s", (zona_id,)):
        raise ErrorUsuario("Zona no encontrada", 404)
    confirmar()
    return {"id": zona_id, "eliminada": True}


# ===================================================================== P6 FLOTA Y USUARIOS
@bp.get("/flota")
@requiere(**ADMIN)
def flota():
    e = _empresa()
    return {
        "vehiculos": consultar("""SELECT v.id, v.placa, v.tipo, v.capacidad_m3, v.tiene_gps, v.tiene_camara,
                                         t.nombre AS transportador
                                  FROM vehiculo v LEFT JOIN transportador t ON t.id = v.transportador_id
                                  WHERE v.empresa_id = %s ORDER BY v.placa""", (e,)),
        "usuarios": consultar("""SELECT id, nombre, email, rol, perfil, activo FROM usuario
                                 WHERE empresa_id = %s ORDER BY rol, nombre""", (e,)),
    }


@bp.post("/vehiculos")
@requiere(**ADMIN)
def crear_vehiculo():
    datos = request.get_json(silent=True) or {}
    fila = uno("""INSERT INTO vehiculo (placa, empresa_id, tipo, capacidad_m3, tiene_gps, tiene_camara)
                  VALUES (%s, %s, %s, %s, %s, %s) RETURNING id, placa""",
               (texto(datos, "placa", True), _empresa(), texto(datos, "tipo"),
                numero(datos, "capacidad_m3", minimo=0.1), bool(datos.get("tiene_gps")),
                bool(datos.get("tiene_camara"))))
    confirmar()
    return fila, 201


@bp.post("/usuarios")
@requiere(**ADMIN)
def crear_usuario():
    datos = request.get_json(silent=True) or {}
    clave = texto(datos, "clave", True)
    if len(clave) < 8:
        raise ErrorUsuario("La clave debe tener al menos 8 caracteres")
    rol = texto(datos, "rol", True)
    fila = uno("""INSERT INTO usuario (empresa_id, nombre, email, password_hash, rol, perfil)
                  VALUES (%s, %s, lower(%s), %s, %s, %s) RETURNING id, nombre, email, rol, perfil""",
               (_empresa(), texto(datos, "nombre", True), texto(datos, "email", True),
                generate_password_hash(clave), rol, texto(datos, "perfil") if rol == "usuario" else None))
    confirmar()
    return fila, 201
