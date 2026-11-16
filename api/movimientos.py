"""Abrir un movimiento: lógica compartida por el enlace del generador (M1),
la app del conductor (M4) y las salidas de un receptor (M3)."""
from .comun import ErrorUsuario, coordenadas, entero, guardar_foto, numero, texto
from .db import uno
from .geocodificador import geocodificar

MECANISMOS = ("gps", "direccion", "mapa")
VERDADERO = ("true", "1", "on", "si", "sí")


def abrir_movimiento(datos, archivos, usuario=None, receptor_origen=None):
    placa = texto(datos, "placa", obligatorio=True)
    tipo_rcd = entero(datos, "tipo_rcd", obligatorio=True)
    volumen = numero(datos, "volumen", obligatorio=True, minimo=0.1)
    direccion = texto(datos, "direccion")
    mecanismo = texto(datos, "mecanismo") or ("gps" if receptor_origen else None)
    if mecanismo not in MECANISMOS:
        raise ErrorUsuario("Indica cómo se ubicó el punto: gps, direccion o mapa")

    # Ubicación: coordenadas del GPS o del mapa, o la dirección geocodificada
    punto = coordenadas(datos, obligatorio=False)
    if punto is None and not receptor_origen:
        if mecanismo == "direccion" and direccion:
            ubicado = geocodificar(direccion)
            punto = (ubicado["lon"], ubicado["lat"])
            direccion = ubicado["direccion_normalizada"] or direccion
        else:
            raise ErrorUsuario("Falta la ubicación de los escombros")
    lon, lat = punto if punto else (None, None)

    # Origen: obra de la empresa, receptor (salida) o particular
    obra_id = entero(datos, "obra_id")
    if receptor_origen:
        origen = "receptor"
        obra_id = None
    elif obra_id:
        if not usuario:
            raise ErrorUsuario("Solo un usuario de una empresa puede registrar movimientos de obra", 403)
        if not uno("SELECT 1 FROM obra WHERE id = %s AND empresa_id = %s", (obra_id, usuario["empresa_id"])):
            raise ErrorUsuario("Esa obra no pertenece a tu empresa", 404)
        origen = "obra"
    else:
        origen = "particular"

    celular = texto(datos, "celular")
    acepta_datos = str(datos.get("acepta_datos", "")).lower() in VERDADERO
    if celular and not acepta_datos:
        raise ErrorUsuario("Para guardar tu celular debes autorizar el uso de tus datos (Ley 1581 de 2012)")

    foto_carga = guardar_foto(archivos.get("foto_carga"), obligatoria=True, nombre_campo="foto_de_la_carga")
    foto_placa = guardar_foto(archivos.get("foto_placa"), obligatoria=False)

    fila = uno("""
        INSERT INTO movimiento (placa, origen_tipo, obra_id, receptor_origen_id, empresa_origen_id,
                                abierto_por_usuario_id, generador_celular, acepta_datos,
                                mecanismo_ingreso, direccion_texto, geom_origen, tipo_rcd_id,
                                volumen_declarado_m3, foto_carga_url, foto_placa_url, precinto)
        VALUES (%(placa)s, %(origen)s, %(obra)s, %(receptor)s, %(empresa)s, %(usuario)s, %(celular)s,
                %(acepta)s, %(mecanismo)s, %(direccion)s,
                coalesce(ST_SetSRID(ST_MakePoint(%(lon)s, %(lat)s), 4326),
                         (SELECT ST_PointOnSurface(geocerca) FROM receptor WHERE id = %(receptor)s)),
                %(tipo)s, %(volumen)s, %(foto_carga)s, %(foto_placa)s, %(precinto)s)
        RETURNING codigo, placa, estado, vehiculo_id IS NOT NULL AS placa_registrada""",
        dict(placa=placa, origen=origen, obra=obra_id, receptor=receptor_origen,
             empresa=usuario["empresa_id"] if usuario else None,
             usuario=usuario["id"] if usuario else None,
             celular=celular, acepta=acepta_datos, mecanismo=mecanismo, direccion=direccion,
             lon=lon, lat=lat, tipo=tipo_rcd, volumen=volumen, foto_carga=foto_carga,
             foto_placa=foto_placa, precinto=texto(datos, "precinto")))
    return fila
