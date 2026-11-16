# API REST (Flask)

> v1 · 16-nov-2026 · Código en [`api/`](../api). Pruebas en [`tests/test_api.py`](../tests/test_api.py) (22, todas pasan).

## Cómo funciona

```
Pantalla (celular / PC) ──HTTP + JSON / GeoJSON──► API Flask ──SQL──► PostgreSQL/PostGIS (reglas R1–R8)
```

- **Sesión con cookie** (`POST /api/sesion`). Cada ruta verifica el **rol** (`admin` / `usuario`) y el **perfil** (`portero`, `conductor`, `inspector`).
- **Cada empresa solo ve lo suyo:** todas las consultas filtran por la empresa de quien inició sesión (`fn_movimientos_empresa`).
- **Las reglas viven en la base de datos.** Si una regla no se cumple, la API devuelve **400** con el mensaje del trigger. Ejemplo: *"el dispositivo está a 9208 m de la geocerca de Planta Sur"*.
- **Auditoría:** la API le dice a la base quién está haciendo cada cambio (`rcd.usuario_id`).
- **Mapas:** las capas salen en **GeoJSON** armado en PostGIS, listas para Leaflet.
- **Tareas automáticas:** cada 5 min corre R4 (sin cierre) y R6 (paradas). Se configura con `TAREAS_CADA_MIN`.

## Rutas por pantalla

### Sin cuenta: enlace del generador (M1)
| Método | Ruta | Para qué |
|---|---|---|
| POST | `/api/publico/movimientos` | Abrir un movimiento (fotos, ubicación, m³, placa) → código y enlace |
| GET | `/api/publico/movimientos/<codigo>` | Estado y línea de tiempo |
| GET | `/api/publico/movimientos/<codigo>/certificado` | Constancia imprimible (cuando se cierra) |
| GET | `/api/publico/movimientos/<codigo>/sugeridos` | Receptores que aceptan el material (tras un rechazo) |
| GET | `/api/publico/transportador?placa=` | ¿La placa es de un transportador inscrito? |
| GET | `/api/publico/tipos-rcd` | Catálogo de tipos de RCD |
| GET | `/api/publico/geocodificar?q=` | Dirección → punto con el geocodificador propio (lon, lat, confianza, dirección normalizada, barrio, `verificar_en_mapa`) |

### Portero (M2 Entradas, M3 Salidas)
| Método | Ruta | Para qué |
|---|---|---|
| GET | `/api/entradas/abiertos?placa=` | Movimientos abiertos de una placa (registro común) |
| POST | `/api/entradas` | Recibir y cerrar · rechazar · entrada sin origen |
| GET | `/api/entradas/hoy` | Entradas del día |
| POST | `/api/salidas` | Despachar material a otro receptor |
| GET | `/api/receptores/mios` | Receptores de la empresa |

### Conductor e inspector (M4–M6)
| Método | Ruta | Para qué |
|---|---|---|
| POST | `/api/movimientos` | Abrir un movimiento de obra o particular |
| GET | `/api/movimientos` | Lista filtrable (estado, obra, fechas, placa) |
| GET | `/api/movimientos/resumen` | m³ por tipo y avance de la meta por obra |
| POST | `/api/arrojos` | Reportar un arrojo (capa 3) |
| POST | `/api/gps` | Posición del camión durante el viaje (caso ideal) |
| GET | `/api/obras` | Obras de la empresa |

### Administrador (P1–P6)
| Método | Ruta | Para qué |
|---|---|---|
| GET | `/api/admin/dashboard` | Meta 50% y cuánto falta, indicadores, balance, operarios más activos, tendencia |
| GET | `/api/admin/reporte-trimestral` | Cantidades y destino por trimestre (art. 16) |
| GET | `/api/admin/seguimiento` | Camiones en tránsito, última posición, sensores |
| GET / PATCH | `/api/admin/alertas[/<id>]` | Ver alertas por gravedad · marcar revisada o escalada |
| PATCH | `/api/admin/movimientos/<codigo>/ubicacion` | Corregir la ubicación (queda auditado) |
| POST | `/api/admin/movimientos/<codigo>/anular` | Anular un movimiento |
| POST | `/api/admin/movimientos/anular-rango` | Anular por rango de fechas (no toca los cerrados) |
| GET / POST / PUT / DELETE | `/api/admin/receptores…` | Geocercas propias |
| POST / PUT / DELETE | `/api/admin/zonas-prohibidas…` | Zonas del art. 20 |
| GET / POST | `/api/admin/flota`, `/vehiculos`, `/usuarios` | Flota y usuarios |

### Mapas (GeoJSON)
| Ruta | Capa | Requisito |
|---|---|---|
| `/api/mapas/normativa` | Receptores vigentes y zonas prohibidas | Capa 1 |
| `/api/mapas/obras` | Obras por estado | Usuario: mapa temático |
| `/api/mapas/movimientos` | Orígenes con m³ | Usuario: calor y clúster |
| `/api/mapas/flujos` | Líneas obra → receptor | Admin: flujos |
| `/api/mapas/densidad?celda=500` | Grilla de densidad (`ST_SquareGrid`) | Admin: densidad |
| `/api/mapas/alertas` | Alertas abiertas | Admin |
| `/api/mapas/arrojos` | Arrojos y movimientos cercanos | Capa 3 |
| `/api/mapas/recorrido/<placa>` | Trayecto GPS y paradas | Admin: seguimiento |

## Geocodificador propio (Geocod-IngeoGOP)

La búsqueda por dirección usa el geocodificador desarrollado en el curso anterior. Corre en un servidor propio (Lenovo, Ubuntu) con FastAPI, PostgreSQL/PostGIS y datos abiertos de Cali, y está publicado con nginx:

```
Plataforma RCD ──HTTP (Tailscale)──► http://100.109.154.10/api/geocode?direccion=Calle 5 # 39-20
                ◄── {"lat": 3.4242, "lon": -76.5468, "confianza": 75, "direccion_normalizada": "CALLE 5 # 39-20",
                     "barrio": "Urbanización Nueva Granada", "comuna": "19", ...}
```

- Configuración: `GEOCODIFICADOR_URL`, `GEOCODIFICADOR_CONFIANZA_MIN` (60) y `GEOCODIFICADOR_TIMEOUT_S` (8).
- Con confianza baja, la respuesta trae `verificar_en_mapa: true` y la pantalla pide confirmar el pin.
- Si el servicio no responde, se devuelve 503 con la indicación de usar el mapa o el GPS. El resto de la plataforma sigue funcionando.

## Decisión de diseño: anular, no borrar

El requisito pide al Admin *"eliminar reportes dentro de un periodo"*. Aquí se **anulan**: el movimiento queda con estado `anulado` y deja de contar, pero no se borra. En un sistema de trazabilidad exigido por la norma, borrar registros destruiría la evidencia. Los movimientos ya cerrados no se pueden anular.
