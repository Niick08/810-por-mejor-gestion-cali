"""Rutas del rol Usuario: portero (M2, M3), conductor e inspector (M4–M6)."""
from flask import Blueprint, request

from ..comun import (ErrorUsuario, coordenadas, entero, guardar_foto, lista, numero, requiere,
                     texto, usuario_actual)
from ..db import confirmar, consultar, uno
from ..movimientos import abrir_movimiento

bp = Blueprint("operacion", __name__, url_prefix="/api")

PORTERO = dict(rol="usuario", perfiles=("portero",))
CAMPO = dict(rol="usuario", perfiles=("conductor", "inspector"))
RESULTADOS = ("recibida", "rechazada", "parcial", "sin_origen")


def _receptor_propio(datos):
    """Receptor de la empresa del portero; si la empresa tiene uno solo, se usa ese."""
    u = usuario_actual()
    receptor_id = entero(datos, "receptor_id")
    propios = consultar("SELECT id, nombre FROM receptor WHERE empresa_id = %s AND activo ORDER BY id",
                        (u["empresa_id"],))
    if receptor_id:
        if receptor_id not in [r["id"] for r in propios]:
            raise ErrorUsuario("Ese receptor no es de tu empresa", 403)
        return receptor_id
    if len(propios) == 1:
        return propios[0]["id"]
    raise ErrorUsuario("Indica el receptor (receptor_id)")


# ===================================================================== PORTERO
@bp.get("/receptores/mios")
@requiere(**PORTERO)
def mis_receptores():
    return {"receptores": consultar("""SELECT id, nombre, tipo,
                                              ST_X(ST_PointOnSurface(geocerca)) AS lon,
                                              ST_Y(ST_PointOnSurface(geocerca)) AS lat
                                       FROM receptor
                                       WHERE empresa_id = %s AND activo ORDER BY id""",
                                    (usuario_actual()["empresa_id"],))}


@bp.get("/entradas/abiertos")
@requiere(**PORTERO)
def abiertos_por_placa():
    """Paso 2 de Entradas: movimientos abiertos de una placa, desde el registro común."""
    placa = texto(request.args, "placa", obligatorio=True)
    return {"placa": uno("SELECT fn_normalizar_placa(%s) AS p", (placa,))["p"],
            "movimientos": consultar("""SELECT * FROM v_movimientos_abiertos
                                        WHERE placa = fn_normalizar_placa(%s)
                                        ORDER BY abierto_en""", (placa,))}


@bp.post("/entradas")
@requiere(**PORTERO)
def registrar_entrada():
    """Pasos 3 y 4 de Entradas: recibir y cerrar, o rechazar. Las reglas R1, R2, R3, R5 y R8
    las aplica la base de datos; si algo no cumple, la respuesta trae el motivo."""
    u, datos = usuario_actual(), request.form
    resultado = texto(datos, "resultado", obligatorio=True)
    if resultado not in RESULTADOS:
        raise ErrorUsuario(f"Resultado inválido. Opciones: {', '.join(RESULTADOS)}")
    codigos = [c.upper() for c in lista(datos, "codigos")]
    if resultado != "sin_origen" and not codigos:
        raise ErrorUsuario("Selecciona al menos un movimiento")
    if codigos:
        encontrados = uno("SELECT count(*) AS n FROM movimiento WHERE codigo = ANY(%s::text[])", (codigos,))["n"]
        if encontrados != len(codigos):
            raise ErrorUsuario("Alguno de los movimientos seleccionados no existe", 404)
    lon, lat = coordenadas(datos)            # ubicación del celular del portero (R1)
    receptor_id = _receptor_propio(datos)
    foto = guardar_foto(request.files.get("foto"), obligatoria=resultado in ("rechazada", "parcial"))
    peso = numero(datos, "peso", minimo=0)

    entrada_id = uno("""
        SELECT fn_registrar_entrada(
          p_receptor => %(receptor)s::int, p_usuario => %(usuario)s::int, p_placa => %(placa)s::text,
          p_resultado => %(resultado)s::text, p_lon => %(lon)s::float8, p_lat => %(lat)s::float8,
          p_movimientos => ARRAY(SELECT id FROM movimiento WHERE codigo = ANY(%(codigos)s::text[])),
          p_volumen => %(volumen)s::numeric, p_tipo => %(tipo)s::int, p_foto => %(foto)s::text,
          p_motivo => %(motivo)s::text, p_peso => %(peso)s::numeric, p_precinto => %(precinto)s::text,
          p_barrio_origen => %(barrio)s::int) AS id""",
        dict(receptor=receptor_id, usuario=u["id"], placa=texto(datos, "placa", obligatorio=True),
             resultado=resultado, lon=lon, lat=lat, codigos=codigos,
             volumen=numero(datos, "volumen", minimo=0), tipo=entero(datos, "tipo_rcd"), foto=foto,
             motivo=texto(datos, "motivo"), peso=peso, precinto=texto(datos, "precinto"),
             barrio=entero(datos, "barrio_origen")))["id"]
    confirmar()        # aquí corre el trigger diferido que cierra o rechaza los movimientos

    return {"entrada_id": entrada_id,
            "movimientos": consultar("""SELECT codigo, estado FROM movimiento
                                        WHERE codigo = ANY(%s::text[]) ORDER BY codigo""", (codigos,)),
            "alertas": consultar("""SELECT a.tipo, a.gravedad, a.detalle FROM alerta a
                                    JOIN movimiento m ON m.id = a.movimiento_id
                                    WHERE m.codigo = ANY(%s::text[]) AND a.creada_en >= now() - interval '1 minute'""",
                                 (codigos,))}, 201


@bp.post("/salidas")
@requiere(**PORTERO)
def registrar_salida():
    """M3: la planta o el punto limpio despacha material hacia otro receptor (abre un movimiento)."""
    receptor_id = _receptor_propio(request.form)
    fila = abrir_movimiento(request.form, request.files, usuario_actual(), receptor_origen=receptor_id)
    confirmar()
    return fila, 201


@bp.get("/entradas/hoy")
@requiere(**PORTERO)
def entradas_hoy():
    return {"entradas": consultar("""
        SELECT e.id, e.registrada_en, e.placa, e.resultado, e.motivo_rechazo, e.volumen_recibido_m3,
               e.peso_t, e.peso_medido, r.nombre AS receptor,
               (SELECT array_agg(m.codigo ORDER BY m.codigo) FROM movimiento_entrada me
                JOIN movimiento m ON m.id = me.movimiento_id WHERE me.entrada_id = e.id) AS codigos,
               (SELECT bool_or(m.estado = 'cerrado_faltante') FROM movimiento_entrada me
                JOIN movimiento m ON m.id = me.movimiento_id WHERE me.entrada_id = e.id) AS con_faltante
        FROM entrada e JOIN receptor r ON r.id = e.receptor_id
        WHERE r.empresa_id = %s AND e.registrada_en >= current_date
        ORDER BY e.registrada_en DESC""", (usuario_actual()["empresa_id"],))}


# ===================================================================== CONDUCTOR E INSPECTOR
@bp.get("/obras")
@requiere()
def obras():
    return {"obras": consultar("""SELECT id, nombre, generador, tipo_generador, estado,
                                         ST_X(punto) AS lon, ST_Y(punto) AS lat
                                  FROM obra WHERE empresa_id = %s ORDER BY nombre""",
                               (usuario_actual()["empresa_id"],))}


@bp.post("/movimientos")
@requiere(**CAMPO)
def abrir():
    fila = abrir_movimiento(request.form, request.files, usuario_actual())
    confirmar()
    return fila, 201


@bp.get("/movimientos")
@requiere()
def mis_viajes():
    """M6: lista filtrable de los movimientos de la empresa."""
    a = request.args
    return {"movimientos": consultar("""
        SELECT m.codigo, m.placa, m.estado, m.con_agravante, m.origen_tipo, o.nombre AS obra,
               t.nombre AS tipo_rcd, t.categoria, m.volumen_declarado_m3, m.abierto_en, m.cerrado_en,
               rc.nombre AS receptor, ST_X(m.geom_origen) AS lon, ST_Y(m.geom_origen) AS lat
        FROM fn_movimientos_empresa(%(e)s) m
        JOIN tipo_rcd t  ON t.id = m.tipo_rcd_id
        LEFT JOIN obra o ON o.id = m.obra_id
        LEFT JOIN LATERAL fn_receptor_cierre(m.id) rc ON true
        WHERE (%(estado)s::text IS NULL OR m.estado = %(estado)s)
          AND (%(obra)s::int IS NULL OR m.obra_id = %(obra)s)
          AND (%(desde)s::date IS NULL OR m.abierto_en >= %(desde)s::date)
          AND (%(hasta)s::date IS NULL OR m.abierto_en < %(hasta)s::date + 1)
          AND (%(placa)s::text IS NULL OR m.placa = fn_normalizar_placa(%(placa)s))
        ORDER BY m.abierto_en DESC
        LIMIT 500""", dict(e=usuario_actual()["empresa_id"], estado=a.get("estado") or None,
                           obra=a.get("obra_id") or None, desde=a.get("desde") or None,
                           hasta=a.get("hasta") or None, placa=a.get("placa") or None))}


@bp.get("/movimientos/resumen")
@requiere()
def resumen():
    """M6: m³ por tipo de RCD y avance de la meta por obra."""
    e = usuario_actual()["empresa_id"]
    return {
        "por_tipo": consultar("""
            SELECT t.nombre AS tipo_rcd, t.categoria, count(*) AS movimientos,
                   sum(m.volumen_declarado_m3) AS m3
            FROM fn_movimientos_empresa(%s) m JOIN tipo_rcd t ON t.id = m.tipo_rcd_id
            WHERE m.estado <> 'anulado'
            GROUP BY t.nombre, t.categoria ORDER BY m3 DESC""", (e,)),
        "por_obra": consultar("SELECT * FROM fn_aprovechamiento_obras(%s)", (e,)),
    }


@bp.post("/arrojos")
@requiere(**CAMPO)
def reportar_arrojo():
    """Capa 3: el conductor o el inspector reporta un arrojo que vio en la vía."""
    u, datos = usuario_actual(), request.form
    mecanismo = texto(datos, "mecanismo", obligatorio=True)
    lon, lat = coordenadas(datos)
    foto = guardar_foto(request.files.get("foto"))
    fila = uno("""
        INSERT INTO punto_arrojo (empresa_id, reportado_por, mecanismo_ingreso, direccion_texto, geom,
                                  tipo_rcd_id, volumen_estimado_m3, foto_url)
        VALUES (%s, %s, %s, %s, ST_SetSRID(ST_MakePoint(%s, %s), 4326), %s, %s, %s)
        RETURNING id""",
        (u["empresa_id"], u["id"], mecanismo, texto(datos, "direccion"), lon, lat,
         entero(datos, "tipo_rcd"), numero(datos, "volumen", minimo=0.1), foto))
    confirmar()
    alerta = uno("SELECT detalle FROM alerta WHERE arrojo_id = %s", (fila["id"],))
    return {"id": fila["id"], "movimientos_cercanos": alerta["detalle"]["movimientos"] if alerta else []}, 201


@bp.post("/gps")
@requiere(rol="usuario", perfiles=("conductor",))
def posicion_gps():
    """Caso ideal (D6): el celular del conductor envía su posición durante el viaje."""
    datos = request.get_json(silent=True) or request.form
    lon, lat = coordenadas(datos)
    vehiculo = uno("SELECT id FROM vehiculo WHERE placa = fn_normalizar_placa(%s) AND empresa_id = %s",
                   (texto(datos, "placa", obligatorio=True), usuario_actual()["empresa_id"]))
    if not vehiculo:
        raise ErrorUsuario("Ese vehículo no es de tu empresa", 404)
    uno("""INSERT INTO posicion_gps (vehiculo_id, registrado_en, geom, velocidad_kmh)
           VALUES (%s, now(), ST_SetSRID(ST_MakePoint(%s, %s), 4326), %s) RETURNING id""",
        (vehiculo["id"], lon, lat, numero(datos, "velocidad", minimo=0)))
    confirmar()
    return {"ok": True}, 201
