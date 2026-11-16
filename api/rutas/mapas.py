"""Capas en GeoJSON para Leaflet. Las geometrías se arman en PostGIS (db.geojson)."""
from flask import Blueprint, request

from ..comun import entero, numero, requiere, usuario_actual
from ..db import geojson

bp = Blueprint("mapas", __name__, url_prefix="/api/mapas")


def _e():
    return usuario_actual()["empresa_id"]


@bp.get("/normativa")
@requiere()
def normativa():
    """Capa 1: receptores vigentes (dónde sí) y zonas prohibidas (dónde no). Registro común.
    Para dibujar se simplifica a ~2 m (5 MB → 0,75 MB con los datos de la IDESC); las reglas
    de la base de datos siempre usan la geometría completa."""
    return geojson("""SELECT capa, id, tipo, nombre, pin_dagma,
                             ST_SimplifyPreserveTopology(geom, 0.00002) AS geom
                      FROM v_capa_normativa""")


@bp.get("/obras")
@requiere()
def obras():
    """Mapa temático de obras por estado (M4)."""
    return geojson("""
        SELECT o.id, o.nombre, o.estado, o.tipo_generador,
               (SELECT count(*) FROM movimiento m WHERE m.obra_id = o.id
                AND m.estado IN ('abierto', 'rechazado')) AS movimientos_en_curso,
               o.punto AS geom
        FROM obra o WHERE o.empresa_id = %s""", (_e(),))


@bp.get("/movimientos")
@requiere()
def movimientos():
    """Puntos de origen con su volumen: sirven para el clúster y el mapa de calor (M4)."""
    a = request.args
    return geojson("""
        SELECT m.codigo, m.placa, m.estado, t.categoria, m.volumen_declarado_m3 AS m3, m.abierto_en,
               m.geom_origen AS geom
        FROM fn_movimientos_empresa(%(e)s) m JOIN tipo_rcd t ON t.id = m.tipo_rcd_id
        WHERE m.estado <> 'anulado'
          AND (%(desde)s::date IS NULL OR m.abierto_en >= %(desde)s::date)
          AND (%(hasta)s::date IS NULL OR m.abierto_en < %(hasta)s::date + 1)""",
        dict(e=_e(), desde=a.get("desde") or None, hasta=a.get("hasta") or None))


@bp.get("/flujos")
@requiere(rol="admin")
def flujos():
    """P3: líneas obra → receptor de los movimientos cerrados (grosor = m³)."""
    return geojson("""
        SELECT m.codigo, m.estado, m.volumen_declarado_m3 AS m3, rc.nombre AS receptor, rc.tipo,
               ST_MakeLine(m.geom_origen, ST_PointOnSurface(rc.geocerca)) AS geom
        FROM fn_movimientos_empresa(%s) m
        JOIN LATERAL fn_receptor_cierre(m.id) rc ON true
        WHERE m.estado IN ('cerrado', 'cerrado_faltante')""", (_e(),))


@bp.get("/densidad")
@requiere(rol="admin")
def densidad():
    """P3: densidad de generación en una grilla de celdas cuadradas (por defecto 500 m)."""
    celda = numero(request.args, "celda", minimo=100) or 500
    return geojson("""
        WITH pts AS (
          SELECT ST_Transform(m.geom_origen, 3857) AS g, m.volumen_declarado_m3 AS m3
          FROM fn_movimientos_empresa(%(e)s) m WHERE m.estado <> 'anulado'),
        grilla AS (
          SELECT c.i, c.j, c.geom
          FROM ST_SquareGrid(%(celda)s, (SELECT ST_SetSRID(ST_Extent(g)::geometry, 3857) FROM pts)) c)
        SELECT count(*) AS movimientos, coalesce(sum(p.m3), 0) AS m3,
               ST_Transform(grilla.geom, 4326) AS geom
        FROM grilla JOIN pts p ON ST_Intersects(grilla.geom, p.g)
        GROUP BY grilla.i, grilla.j, grilla.geom""", dict(e=_e(), celda=celda))


@bp.get("/alertas")
@requiere(rol="admin")
def alertas():
    return geojson("""SELECT id, tipo, gravedad, estado, creada_en, geom FROM alerta
                      WHERE empresa_id = %s AND estado = 'abierta' AND geom IS NOT NULL""", (_e(),))


@bp.get("/arrojos")
@requiere()
def arrojos():
    """Capa 3: arrojos reportados y cuántos movimientos sin cerrar tienen cerca."""
    return geojson("""
        SELECT p.id, p.estado, p.volumen_estimado_m3 AS m3, p.reportado_en, p.foto_url,
               coalesce(jsonb_array_length(a.detalle -> 'movimientos'), 0) AS movimientos_cercanos,
               p.geom
        FROM punto_arrojo p
        LEFT JOIN alerta a ON a.arrojo_id = p.id AND a.tipo = 'arrojo_cercano'
        WHERE p.empresa_id = %s""", (_e(),))


@bp.get("/recorrido/<placa>")
@requiere(rol="admin")
def recorrido(placa):
    """P2: trayecto GPS de un vehículo de la empresa y sus paradas."""
    horas = entero(request.args, "horas") or 6
    return geojson("""
        WITH v AS (SELECT id FROM vehiculo WHERE placa = fn_normalizar_placa(%(placa)s) AND empresa_id = %(e)s)
        SELECT 'trayecto' AS tipo, NULL::numeric AS minutos, NULL::text AS zona_prohibida,
               ST_MakeLine(p.geom ORDER BY p.registrado_en) AS geom
        FROM posicion_gps p JOIN v ON v.id = p.vehiculo_id
        WHERE p.registrado_en >= now() - make_interval(hours => %(h)s)
        HAVING count(*) > 1
        UNION ALL
        SELECT 'parada', pr.minutos, pr.zona_prohibida, pr.geom
        FROM v CROSS JOIN LATERAL fn_paradas(v.id, now() - make_interval(hours => %(h)s), now()) pr""",
        dict(placa=placa, e=_e(), h=horas))
