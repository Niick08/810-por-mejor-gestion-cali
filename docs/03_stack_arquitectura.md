# Stack tecnológico, arquitectura y metodología

> Propuesta v1 · 15-nov-2026 · Pendiente de aprobación. Criterios: todo de código libre (requisito del curso), usar lo visto en clase y no complicarse.

## 1. Arquitectura cliente-servidor

```
┌──────────────────────── CLIENTE (navegador: celular y PC) ────────────────────────┐
│  HTML + CSS (Bootstrap) + JavaScript                                               │
│  Leaflet · Leaflet.markercluster · Leaflet.heat · Turf.js · Chart.js               │
│  Pantallas: M1–M6 (celular) y P1–P6 (PC), una sola web adaptable                    │
└───────────────┬───────────────────────────────────────────────┬────────────────────┘
                │ JSON / GeoJSON (API REST)                     │ WMS / WFS
┌───────────────▼──────────────────────────┐   ┌────────────────▼───────────────────┐
│  SERVIDOR DE APLICACIÓN: Flask (Python)  │   │  SERVIDOR DE MAPAS: GeoServer      │
│  · autenticación y roles                 │   │  · capa normativa (receptores,     │
│  · espacio por empresa (empresa_id)      │   │    zonas prohibidas)               │
│  · movimientos, cierre por placa         │   │  · capas base de Cali (IDESC)      │
│  · geocodificador propio (módulo)        │   │  · estilos SLD                     │
│  · fotos, QR, certificados PDF           │   └────────────────┬───────────────────┘
│  · simulador de GPS y sensores           │                    │
└───────────────┬──────────────────────────┘                    │
                │ SQL                                           │ SQL
┌───────────────▼───────────────────────────────────────────────▼───────────────────┐
│  BASE DE DATOS: PostgreSQL 16 + PostGIS + pgRouting                                │
│  · modelo espacial (movimientos, geocercas, rastros GPS, arrojos)                  │
│  · funciones PL/pgSQL y TRIGGERS: estados, faltante, geocercas, alertas            │
│  · pgRouting: ruta al receptor más cercano que acepta el material                  │
│  · tarea programada: movimientos sin cierre a las 24 h                             │
└────────────────────────────────────────────────────────────────────────────────────┘
```

## 2. Componentes y justificación

| Capa | Tecnología | Licencia | Por qué |
|---|---|---|---|
| Base de datos | **PostgreSQL 16 + PostGIS** | PostgreSQL / GPL | Visto en clase (semanas 2–4). `ST_Within`, `ST_DWithin` y `ST_ClusterDBSCAN` resuelven geocercas, zonas prohibidas y clústeres. Ya está instalado en el equipo |
| Ruteo | **pgRouting** | GPL | Visto en clase (taller 1). Ruta obra → receptor más cercano que acepta el material, sobre la red vial de OpenStreetMap |
| Lógica en la BD | **PL/pgSQL + triggers** | — | Visto en clase (semanas 3–4). Las reglas críticas (cierre, faltante, alertas) viven en la base de datos y no se pueden saltar desde la interfaz |
| API | **Flask** (Python) | BSD | Visto en clase (semana 10, REST API con Flask). Liviano y suficiente para el proyecto |
| Servidor de mapas | **GeoServer** | GPL | Visto en clase (semana 5). Publica la capa normativa como WMS/WFS estándar OGC |
| Mapa web | **Leaflet** + markercluster + heat | BSD / MIT | Visto en clase (semana 6). Clúster y mapa de calor como plugins |
| Análisis en el navegador | **Turf.js** | MIT | Visto en clase (semana 8). Buffers y distancias rápidas sin ir al servidor |
| Gráficos | **Chart.js** | MIT | Gráficos del dashboard y de los datos |
| Interfaz adaptable | **Bootstrap 5** | MIT | La misma web en celular y PC (D11), sin herramientas de compilación |
| Geocodificación | **Geocodificador propio** (proyecto anterior) | — | Mecanismo de ingreso por dirección, mejorado dentro del proyecto |
| QR y PDF | `qrcode` y `reportlab` (Python) | BSD | QR del movimiento y certificado para el generador |
| Rastreo GPS real (planteado) | **Traccar** | Apache 2.0 | Servidor GPS libre. En el curso se reemplaza por un simulador |
| Datos | IDESC, OpenStreetMap, listado DAGMA | Abiertos | Capas base, red vial, receptores inscritos |
| Código y gestión | **Git + GitHub** | — | Entregable obligatorio del curso |

**Decisión de simplicidad:** el frontend se hace sin frameworks ni herramientas de compilación (sin React ni Node). Son HTML y JavaScript con librerías desde CDN, como en los ejemplos de clase. Así hay menos piezas que pueden fallar.

## 3. Multiempresa (cómo se separa cada espacio)

- Cada tabla privada tiene una columna `empresa_id`.
- La API filtra **siempre** por la empresa del usuario que inició sesión.
- El registro común (movimientos abiertos y capa normativa) se consulta mediante **vistas** que solo exponen los campos mínimos (placa, hora, m³, tipo, barrio, foto).
- Opcional, para más rigor: *Row Level Security* de PostgreSQL, para que la propia base de datos impida ver datos de otra empresa.

## 4. Seguridad básica

- Contraseñas con hash (`werkzeug.security`).
- Sesión con roles: `admin` y `usuario` (con perfil: portero, conductor, inspector).
- El enlace del generador usa un código único difícil de adivinar (por ejemplo, `RCD-4F7K…`), sin cuenta.
- El cierre se valida en el servidor: rol receptor + ubicación del dispositivo dentro de la geocerca.

## 5. Estructura del repositorio (propuesta)

```
cali-sin-escombros/
├── docs/            decisiones, planteamiento, diseño, stack, modelo, UML
├── db/              01_esquema.sql · 02_funciones.sql · 03_triggers.sql · 04_vistas.sql · 05_datos_demo.sql
├── api/             app Flask (rutas, autenticación, geocodificador, QR/PDF)
├── web/             HTML, CSS y JS (pantallas M1–M6 y P1–P6)
├── geoserver/       estilos SLD y configuración de capas
├── simulador/       scripts que generan rastros GPS y eventos de sensores
└── README.md
```

## 6. Metodología (requisito del curso)

**Kanban con entregas semanales**, gestionado en **GitHub Projects** (tablero: Por hacer · En curso · Revisión · Hecho).

| Semana | Entregable |
|---|---|
| 1 | Modelo de datos + UML + SQL del esquema con datos de demostración |
| 2 | Triggers y funciones (cierre, faltante, sin cierre, geocercas) + API Flask básica + autenticación |
| 3 | Pantallas de celular (M1–M6) + geocodificador integrado |
| 4 | Pantallas de PC (P1–P6) + GeoServer + simulador de GPS y sensores |
| 5 | Pruebas, memoria, video de sustentación |

*Ajustar según la fecha real de la última semana de clase.*

## 7. Por verificar

1. Si GeoServer está instalado en este equipo o en la máquina virtual del curso (no se encontró en `Program Files`; Java 21 sí está).
2. Ubicación del proyecto del geocodificador anterior, para integrarlo.
3. Fecha exacta de entrega.
