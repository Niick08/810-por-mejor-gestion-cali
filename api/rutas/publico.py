"""Rutas sin cuenta: el enlace del pequeño generador (pantalla M1) y consultas abiertas.
El código del movimiento (RCD-XXXXXX) funciona como llave del enlace."""
from flask import Blueprint, current_app, render_template_string, request

from ..comun import ErrorUsuario, texto
from ..db import confirmar, consultar, uno
from ..geocodificador import geocodificar
from ..movimientos import abrir_movimiento

bp = Blueprint("publico", __name__, url_prefix="/api/publico")


def _movimiento(codigo):
    m = uno("""SELECT m.id, m.codigo, m.placa, m.estado, m.con_agravante, m.volumen_declarado_m3,
                      m.abierto_en, m.cerrado_en, m.foto_carga_url, t.nombre AS tipo_rcd,
                      b.nombre AS barrio
               FROM movimiento m
               JOIN tipo_rcd t    ON t.id = m.tipo_rcd_id
               LEFT JOIN barrio b ON b.id = m.barrio_id
               WHERE m.codigo = %s""", (codigo.upper(),))
    if not m:
        raise ErrorUsuario("No existe un movimiento con ese código", 404)
    return m


@bp.post("/movimientos")
def abrir():
    """Doña Marta registra sus escombros (o Jairo lo hace por ella)."""
    fila = abrir_movimiento(request.form, request.files)
    confirmar()
    fila["enlace"] = f"{current_app.config['URL_PUBLICA']}/m/{fila['codigo']}"
    return fila, 201


@bp.get("/movimientos/<codigo>")
def estado(codigo):
    """Línea de tiempo del movimiento (pantalla M1, paso 3). No expone datos personales."""
    m = _movimiento(codigo)
    m["eventos"] = consultar("""
        SELECT tipo, ocurrido_en, detalle ->> 'receptor' AS receptor, detalle ->> 'motivo' AS motivo,
               (detalle ->> 'cierre_tardio')::boolean AS cierre_tardio
        FROM movimiento_evento
        WHERE movimiento_id = %s AND tipo <> 'ubicacion_corregida'
        ORDER BY ocurrido_en, id""", (m["id"],))
    m["recibido_en"] = uno("""SELECT nombre, tipo, registrada_en, volumen_recibido_m3
                              FROM fn_receptor_cierre(%s)""", (m["id"],))
    m["horas_para_cierre"] = uno("SELECT fn_param('horas_sin_cierre') AS h")["h"]
    del m["id"]
    return m


@bp.get("/movimientos/<codigo>/sugeridos")
def sugeridos(codigo):
    """Receptores cercanos que aceptan el material (después de un rechazo)."""
    m = _movimiento(codigo)
    return {"receptores": consultar("SELECT * FROM fn_receptores_sugeridos(%s, 5)", (m["id"],))}


CERTIFICADO = """<!doctype html>
<html lang="es"><head><meta charset="utf-8"><title>Certificado {{ m.codigo }}</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
 body{font-family:system-ui,sans-serif;max-width:640px;margin:2rem auto;padding:0 1rem;color:#222}
 h1{font-size:1.3rem} table{width:100%;border-collapse:collapse} td{padding:.4rem;border-bottom:1px solid #ddd}
 td:first-child{color:#666;width:45%} .nota{font-size:.85rem;color:#666;margin-top:1.5rem}
 @media print{button{display:none}}
</style></head><body>
<h1>Constancia de recepción de RCD</h1>
<table>
 <tr><td>Código del movimiento</td><td><b>{{ m.codigo }}</b></td></tr>
 <tr><td>Placa del vehículo</td><td>{{ m.placa }}</td></tr>
 <tr><td>Material declarado</td><td>{{ m.tipo_rcd }} · {{ m.volumen_declarado_m3 }} m³</td></tr>
 <tr><td>Origen (barrio)</td><td>{{ m.barrio or "—" }}</td></tr>
 <tr><td>Recibido por</td><td>{{ r.nombre }} ({{ r.tipo.replace('_', ' ') }}) · PIN {{ r.pin_dagma or "—" }}</td></tr>
 <tr><td>Fecha de recepción</td><td>{{ r.registrada_en.strftime('%d/%m/%Y %H:%M') }}</td></tr>
 <tr><td>Volumen recibido</td><td>{{ r.volumen_recibido_m3 }} m³</td></tr>
 <tr><td>Peso</td><td>{{ r.peso_t or "—" }} t ({{ "medido" if r.peso_medido else "estimado con densidad" }})</td></tr>
 <tr><td>Estado</td><td>{{ "Recibido completo" if m.estado == "cerrado" else "Recibido con faltante" }}</td></tr>
</table>
<p class="nota">Constancia generada a partir del registro georreferenciado de la entrada en el receptor
(Resolución 0472 de 2017, art. 16). Verificable con el código del movimiento.</p>
<button onclick="print()">Imprimir o guardar como PDF</button>
</body></html>"""


@bp.get("/movimientos/<codigo>/certificado")
def certificado(codigo):
    m = _movimiento(codigo)
    if m["estado"] not in ("cerrado", "cerrado_faltante"):
        raise ErrorUsuario("El certificado está disponible cuando un receptor recibe el material", 409)
    r = uno("SELECT * FROM fn_receptor_cierre(%s)", (m["id"],))
    return render_template_string(CERTIFICADO, m=m, r=r)


@bp.get("/transportador")
def transportador():
    """¿La placa es de un transportador inscrito? (pantalla M1: 'Jairo R. · PIN ✓')"""
    placa = texto(request.args, "placa", obligatorio=True)
    fila = uno("""SELECT v.placa, t.nombre, t.pin_dagma IS NOT NULL AS inscrito
                  FROM vehiculo v LEFT JOIN transportador t ON t.id = v.transportador_id
                  WHERE v.placa = fn_normalizar_placa(%s)""", (placa,))
    return fila or {"placa": placa, "nombre": None, "inscrito": False}


@bp.get("/config")
def configuracion():
    c = current_app.config
    return {"demo": c["MODO_DEMO"],
            "geocodificador": bool(c["GEOCODIFICADOR_URL"] or c["GEOCODIFICADOR_MODULO"]),
            "wms": "/geoserver/rcd/wms" if c["GEOSERVER_URL"] else None,
            "horas_sin_cierre": uno("SELECT fn_param('horas_sin_cierre') AS h")["h"]}


@bp.get("/tipos-rcd")
def tipos_rcd():
    return {"tipos": consultar("SELECT id, codigo, nombre, categoria FROM tipo_rcd ORDER BY id")}


@bp.get("/geocodificar")
def buscar_direccion():
    """Dirección → punto, con el geocodificador propio. La pantalla pone el pin y, si
    'verificar_en_mapa' es verdadero (confianza baja), pide al usuario confirmarlo."""
    return geocodificar(texto(request.args, "q", obligatorio=True))
