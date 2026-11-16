"""Recorridos completos por la API, con los escenarios de db/03_datos_demo.sql."""
from conftest import entrar, foto

PORTERO = "porteria@plantasur.demo"
ADMIN_TRANSPORTES = "admin@transportes.demo"
ADMIN_RECICLADOS = "admin@reciclados.demo"
CONDUCTOR = "conductor@transportes.demo"
EN_PLANTA_SUR = {"lon": "-76.5350", "lat": "3.3450"}


# ------------------------------------------------------------------ sesión y permisos
def test_clave_incorrecta(cliente):
    r = cliente.post("/api/sesion", json={"email": PORTERO, "clave": "otra"})
    assert r.status_code == 401


def test_permisos_por_rol(cliente):
    assert cliente.get("/api/admin/dashboard").status_code == 401          # sin sesión
    entrar(cliente, CONDUCTOR)
    assert cliente.get("/api/admin/dashboard").status_code == 403          # conductor no es admin
    assert cliente.get("/api/entradas/abiertos?placa=XYZ123").status_code == 403   # ni portero


# ------------------------------------------------------------------ enlace del generador (M1)
def test_generador_abre_movimiento_sin_cuenta(cliente):
    r = cliente.post("/api/publico/movimientos", data={
        "placa": "xyz-123", "tipo_rcd": "3", "volumen": "2", "mecanismo": "gps",
        "lon": "-76.527", "lat": "3.373", "celular": "3000000099", "acepta_datos": "true",
        "foto_carga": foto()}, content_type="multipart/form-data")
    assert r.status_code == 201, r.json
    assert r.json["placa"] == "XYZ123" and r.json["placa_registrada"]
    codigo = r.json["codigo"]

    estado = cliente.get(f"/api/publico/movimientos/{codigo}").json
    assert estado["estado"] == "abierto" and estado["barrio"] == "Sur A (demo)"
    assert "generador_celular" not in estado                     # sin datos personales
    assert [e["tipo"] for e in estado["eventos"]] == ["abierto"]


def test_generador_sin_autorizar_datos(cliente):
    r = cliente.post("/api/publico/movimientos", data={
        "placa": "XYZ123", "tipo_rcd": "3", "volumen": "1", "mecanismo": "mapa",
        "lon": "-76.52", "lat": "3.37", "celular": "3000000098", "foto_carga": foto()},
        content_type="multipart/form-data")
    assert r.status_code == 400 and "1581" in r.json["error"]


def test_direccion_sin_geocodificador_configurado(cliente):
    r = cliente.get("/api/publico/geocodificar?q=Calle 5 # 39-20")
    assert r.status_code == 503


def test_transportador_inscrito(cliente):
    r = cliente.get("/api/publico/transportador?placa=xyz 123").json
    assert r["inscrito"] and "Jairo" in r["nombre"]


# ------------------------------------------------------------------ portero (M2)
def test_portero_cierra_un_rechazado_y_sale_certificado(cliente):
    entrar(cliente, PORTERO)
    abiertos = cliente.get("/api/entradas/abiertos?placa=xyz-123").json
    codigos = [m["codigo"] for m in abiertos["movimientos"]]
    assert "RCD-DEMO04" in codigos

    # E3 había sido rechazado por Planta Sur; ahora llega separado y se recibe
    r = cliente.post("/api/entradas", data={
        "placa": "XYZ123", "resultado": "recibida", "codigos": "RCD-DEMO04", "volumen": "2",
        "tipo_rcd": "3", "foto": foto(), **EN_PLANTA_SUR}, content_type="multipart/form-data")
    assert r.status_code == 201, r.json
    assert r.json["movimientos"] == [{"codigo": "RCD-DEMO04", "estado": "cerrado"}]

    linea = cliente.get("/api/publico/movimientos/RCD-DEMO04").json
    assert [e["tipo"] for e in linea["eventos"]] == ["abierto", "rechazado", "cerrado"]
    assert linea["recibido_en"]["nombre"] == "Planta Sur (demo)"

    cert = cliente.get("/api/publico/movimientos/RCD-DEMO04/certificado")
    assert cert.status_code == 200 and b"Planta Sur (demo)" in cert.data and b"estimado" in cert.data


def test_portero_fuera_de_la_geocerca_es_bloqueado(cliente):
    entrar(cliente, PORTERO)
    r = cliente.post("/api/entradas", data={
        "placa": "XYZ123", "resultado": "recibida", "codigos": "RCD-DEMO05", "volumen": "1",
        "tipo_rcd": "3", "lon": "-76.60", "lat": "3.40"}, content_type="multipart/form-data")
    assert r.status_code == 400 and "geocerca" in r.json["error"]


def test_rechazo_exige_foto(cliente):
    entrar(cliente, PORTERO)
    r = cliente.post("/api/entradas", data={
        "placa": "XYZ123", "resultado": "rechazada", "codigos": "RCD-DEMO05", "motivo": "mezcla_basura",
        **EN_PLANTA_SUR}, content_type="multipart/form-data")
    assert r.status_code == 400 and "foto" in r.json["error"]


def test_sugeridos_tras_rechazo(cliente):
    r = cliente.get("/api/publico/movimientos/RCD-DEMO05/sugeridos").json
    nombres = [x["nombre"] for x in r["receptores"]]
    assert nombres and "Punto Limpio Oriente (demo)" not in nombres          # ese ya lo rechazó


def test_entradas_de_hoy(cliente):
    entrar(cliente, PORTERO)
    r = cliente.get("/api/entradas/hoy").json
    assert all(e["receptor"] == "Planta Sur (demo)" for e in r["entradas"])


# ------------------------------------------------------------------ conductor (M4–M6)
def test_conductor_abre_movimiento_de_obra_y_ve_sus_viajes(cliente):
    entrar(cliente, CONDUCTOR)
    r = cliente.post("/api/movimientos", data={
        "placa": "ABC456", "tipo_rcd": "3", "volumen": "6", "mecanismo": "gps", "obra_id": "1",
        "lon": "-76.530", "lat": "3.370", "foto_carga": foto()}, content_type="multipart/form-data")
    assert r.status_code == 201, r.json
    viajes = cliente.get("/api/movimientos?placa=ABC456").json["movimientos"]
    assert r.json["codigo"] in [v["codigo"] for v in viajes]
    resumen = cliente.get("/api/movimientos/resumen").json
    assert resumen["por_tipo"] and resumen["por_obra"]


def test_conductor_no_usa_obras_ajenas(cliente):
    entrar(cliente, CONDUCTOR)
    r = cliente.post("/api/movimientos", data={
        "placa": "ABC456", "tipo_rcd": "3", "volumen": "6", "mecanismo": "gps", "obra_id": "999",
        "lon": "-76.53", "lat": "3.37", "foto_carga": foto()}, content_type="multipart/form-data")
    assert r.status_code == 404


def test_arrojo_cruza_con_movimientos_cercanos(cliente):
    entrar(cliente, CONDUCTOR)
    r = cliente.post("/api/arrojos", data={
        "mecanismo": "gps", "lon": "-76.5265", "lat": "3.3725", "volumen": "1", "tipo_rcd": "3",
        "foto": foto()}, content_type="multipart/form-data")
    assert r.status_code == 201 and len(r.json["movimientos_cercanos"]) >= 1


# ------------------------------------------------------------------ administrador (P1–P6)
def test_cada_empresa_solo_ve_lo_suyo(cliente):
    entrar(cliente, ADMIN_RECICLADOS)
    r = cliente.patch("/api/admin/movimientos/RCD-DEMO07/ubicacion", json={"lon": -76.52, "lat": 3.43})
    assert r.status_code == 404                                   # RCD-DEMO07 es de Transportes

    entrar(cliente, ADMIN_TRANSPORTES)
    r = cliente.patch("/api/admin/movimientos/RCD-DEMO07/ubicacion", json={"lon": -76.5204, "lat": 3.4301})
    assert r.status_code == 200 and r.json["tipo"] == "ubicacion_corregida"


def test_dashboard_y_meta(cliente):
    entrar(cliente, ADMIN_TRANSPORTES)
    d = cliente.get("/api/admin/dashboard").json
    assert d["meta"]["meta_pct"] == 50
    assert {o["obra"] for o in d["meta"]["por_obra"]} == {"Torres del Lili (demo)", "Edificio Centro (demo)"}
    assert d["indicadores"]["alertas_abiertas"] >= 1
    assert d["operarios_activos"] and d["tendencia_por_tipo"]


def test_alertas_ordenadas_y_revision(cliente):
    entrar(cliente, ADMIN_TRANSPORTES)
    alertas = cliente.get("/api/admin/alertas").json["alertas"]
    assert alertas[0]["gravedad"] == "alta"
    r = cliente.patch(f"/api/admin/alertas/{alertas[0]['id']}", json={"estado": "revisada"})
    assert r.status_code == 200


def test_seguimiento_muestra_camion_en_transito(cliente):
    entrar(cliente, ADMIN_TRANSPORTES)
    vehiculos = cliente.get("/api/admin/seguimiento").json["vehiculos"]
    abc = next(v for v in vehiculos if v["placa"] == "ABC456")
    assert abc["lon"] is not None and any(s["tipo"] == "compuerta_abierta" for s in abc["sensores"])


def test_reporte_trimestral(cliente):
    entrar(cliente, "admin@plantasur.demo")
    filas = cliente.get("/api/admin/reporte-trimestral").json["filas"]
    assert filas and filas[0]["receptor"] == "Planta Sur (demo)"


def test_geocerca_nueva_y_capa_normativa(cliente):
    entrar(cliente, ADMIN_RECICLADOS)
    poligono = {"type": "Polygon", "coordinates": [[[-76.48, 3.43], [-76.479, 3.43], [-76.479, 3.431],
                                                     [-76.48, 3.431], [-76.48, 3.43]]]}
    r = cliente.post("/api/admin/receptores", json={"nombre": "Patio nuevo (demo)", "tipo": "punto_limpio",
                                                    "geometria": poligono, "acepta": ["PET", "MET"]})
    assert r.status_code == 201, r.json
    capa = cliente.get("/api/mapas/normativa").json
    assert capa["type"] == "FeatureCollection"
    assert "Patio nuevo (demo)" in [f["properties"]["nombre"] for f in capa["features"]]


def test_anular_por_rango_no_toca_cerrados(cliente):
    entrar(cliente, ADMIN_TRANSPORTES)
    r = cliente.post("/api/admin/movimientos/anular-rango", json={"desde": "2000-01-01", "hasta": "2100-01-01"})
    assert r.status_code == 200 and r.json["anulados"] >= 1
    estados = {m["codigo"]: m["estado"] for m in cliente.get("/api/movimientos").json["movimientos"]}
    assert estados["RCD-DEMO02"] == "cerrado"                    # cerrado: no se anula
    assert estados["RCD-DEMO07"] == "anulado"


# ------------------------------------------------------------------ mapas
def test_capas_geojson(cliente):
    entrar(cliente, ADMIN_TRANSPORTES)
    for capa in ("obras", "movimientos", "flujos", "densidad", "alertas", "arrojos", "recorrido/ABC456"):
        r = cliente.get(f"/api/mapas/{capa}")
        assert r.status_code == 200, (capa, r.json)
        assert r.json["type"] == "FeatureCollection", capa
    flujos = cliente.get("/api/mapas/flujos").json["features"]
    assert flujos and flujos[0]["geometry"]["type"] == "LineString"
    recorrido = cliente.get("/api/mapas/recorrido/ABC456").json["features"]
    assert {"trayecto", "parada"} <= {f["properties"]["tipo"] for f in recorrido}
