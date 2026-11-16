"""Acceso a PostgreSQL/PostGIS. Una conexión por petición; las rutas confirman con confirmar()."""
import psycopg
from psycopg.rows import dict_row
from flask import g, current_app, session


def conexion():
    if "db" not in g:
        g.db = psycopg.connect(current_app.config["DATABASE_URL"], row_factory=dict_row,
                               options="-c search_path=rcd,public")
        usuario = session.get("usuario")
        if usuario:
            # Para la auditoría: los triggers saben quién hizo cada cambio administrativo
            g.db.execute("SELECT set_config('rcd.usuario_id', %s, false)", (str(usuario["id"]),))
    return g.db


def consultar(sql, params=None):
    return conexion().execute(sql, params).fetchall()


def uno(sql, params=None):
    return conexion().execute(sql, params).fetchone()


def ejecutar(sql, params=None):
    return conexion().execute(sql, params).rowcount


def confirmar():
    """Confirma la transacción. Aquí corren los triggers diferidos (cierre de movimientos)."""
    conexion().commit()


def cerrar(_error=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()          # lo no confirmado se deshace


def geojson(sql, params=None):
    """Envuelve una consulta con columna `geom` en un FeatureCollection, armado en PostGIS."""
    envuelta = f"""
        SELECT json_build_object(
          'type', 'FeatureCollection',
          'features', coalesce(json_agg(json_build_object(
              'type', 'Feature',
              'geometry', ST_AsGeoJSON(t.geom, 6)::json,
              'properties', to_jsonb(t) - 'geom')), '[]'::json)) AS fc
        FROM ({sql}) AS t"""
    return uno(envuelta, params)["fc"]
