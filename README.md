# Trazabilidad geográfica de RCD — Cali

*(Nombre del proyecto provisional)*

Plataforma web **multiempresa** para gestores de residuos de construcción y demolición (RCD). Cada movimiento de escombros (origen → placa → receptor) se abre en el origen y **solo lo cierra quien lo recibe**. Si nadie lo cierra en 24 h, se genera una alerta, porque el material no llegó a un sitio legal. Todo se valida contra la Resolución 0472 de 2017 convertida en capas geográficas.

Proyecto final · Geoinformación en la Web (2026-II) · Especialización en Geomática, Universidad del Valle.

## Documentos (leer en este orden)

| Archivo | Contenido | Estado |
|---|---|---|
| [docs/00_decisiones.md](docs/00_decisiones.md) | Registro de decisiones D1–D16 y pendientes. **Fuente de verdad** | Vigente |
| [docs/01_planteamiento_problema.md](docs/01_planteamiento_problema.md) | Problema, norma, objetivos, alcance | Borrador v0.2 (actualizar con el modelo multiempresa) |
| [docs/02_diseno_funcional.md](docs/02_diseno_funcional.md) | Conceptos, estados, reglas, roles, pantallas, requisitos | v2, aprobado |
| [docs/03_stack_arquitectura.md](docs/03_stack_arquitectura.md) | Stack, arquitectura, multiempresa, metodología | Aprobado |
| [docs/04_modelo_datos.md](docs/04_modelo_datos.md) | Entidades, diagrama ER, UML (estados, secuencia, casos de uso) | v1 |
| [db/01_esquema.sql](db/01_esquema.sql) | Tablas, restricciones, índices, vistas del registro común | v1, probado |
| [db/02_funciones_triggers.sql](db/02_funciones_triggers.sql) | Reglas R1–R8 como triggers y funciones PL/pgSQL | v1, probado |
| [db/03_datos_demo.sql](db/03_datos_demo.sql) | 10 escenarios de demostración (todo ficticio) | v1 |
| [db/tests/pruebas_reglas.sql](db/tests/pruebas_reglas.sql) | 25 pruebas automáticas de las reglas | Todas pasan |
| [db/04_funciones_api.sql](db/04_funciones_api.sql) | Consultas de apoyo: movimientos por empresa, meta por obra | v1 |
| [docs/05_api.md](docs/05_api.md) | Rutas de la API por pantalla | v1 |
| [api/](api) · [tests/](tests) | API Flask y sus 27 pruebas (incluye el geocodificador) | Todas pasan |
| [web/](web) | Pantallas: inicio, generador (M1), portero (M2–M3), campo (M4–M6), admin (P1–P6) | v1, probadas en el navegador |
| [docs/06_datos.md](docs/06_datos.md) · [scripts/cargar_datos_reales.py](scripts/cargar_datos_reales.py) | Datos oficiales de la IDESC y densidades de la NSR-10 | v1 |

## Cómo correrlo (recomendado: Docker)

```bash
cp docker.env.example docker.env      # cambia las claves
docker compose --env-file docker.env up -d --build
```

Plataforma en http://localhost:8085 y GeoServer en http://localhost:8086/geoserver. Los detalles están en [docs/07_docker_despliegue.md](docs/07_docker_despliegue.md). En el servidor Lenovo ya está desplegado: http://100.109.154.10:8085 (por Tailscale).

Lo que sigue abajo es para desarrollar **sin** Docker.

## Cómo cargar la base de datos

Requiere PostgreSQL 16 con PostGIS y pgRouting. Desde la carpeta `db/`:

```bash
createdb rcd
psql -d rcd -v ON_ERROR_STOP=1 -f 01_esquema.sql
psql -d rcd -v ON_ERROR_STOP=1 -f 02_funciones_triggers.sql
psql -d rcd -v ON_ERROR_STOP=1 -f 04_funciones_api.sql
psql -d rcd -v ON_ERROR_STOP=1 -f 03_datos_demo.sql
psql -d rcd -f tests/pruebas_reglas.sql      # debe terminar con "TODAS LAS PRUEBAS PASARON"
```

Para la presentación, reemplaza las comunas, barrios y zonas de prueba por los **datos oficiales de la IDESC** (desde la raíz del proyecto):

```bash
.venv/Scripts/python scripts/cargar_datos_reales.py --url postgresql://postgres:TU_CLAVE@localhost:5432/rcd
```

## Cómo correr la API

Desde la raíz del proyecto (Windows, Git Bash):

```bash
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt
export DATABASE_URL="postgresql://postgres:TU_CLAVE@localhost:5432/rcd"
export GEOCODIFICADOR_URL="http://100.109.154.10/api"   # geocodificador propio en el Lenovo (Tailscale)
.venv/Scripts/flask --app api claves-demo     # clave "demo1234" para los usuarios de demostración
.venv/Scripts/flask --app api run             # http://localhost:5000
```

También se pueden poner esas variables en un archivo `.env` en la raíz (ver `.env.example`); Flask lo lee solo. Para presentar desde un PC, agrega `MODO_DEMO=1`: la portería mostrará un botón para simular que el celular está dentro de la planta. **Nunca lo actives en producción.**

| Página | Quién | Para qué |
|---|---|---|
| `/` | Todos | Iniciar sesión (en modo demo muestra los usuarios de prueba) |
| `/generador.html` · `/m/<código>` | Sin cuenta | Registrar escombros, QR para el conductor, estado y certificado |
| `/portero.html` | Portero (celular) | Entradas por placa, rechazos, salidas, entradas de hoy |
| `/campo.html` | Conductor e inspector (celular) | Mapa, registrar movimientos y arrojos, viajes y datos |
| `/admin.html` | Administrador (PC) | Dashboard, seguimiento, control, geocercas, movimientos, flota |

Usuarios de demostración: `porteria@plantasur.demo`, `admin@transportes.demo`, `conductor@transportes.demo` (ver `db/03_datos_demo.sql`).

Pruebas de la API (contra una base de prueba cargada con 01, 02, 04 y 03):

```bash
TEST_DATABASE_URL="postgresql://postgres:TU_CLAVE@localhost:5432/rcd_test" .venv/Scripts/python -m pytest tests -q
```

## Estado

| Fase | Estado |
|---|---|
| Idea y planteamiento | Borrador |
| Diseño funcional y bocetos | **Aprobado** (15-nov-2026) |
| Stack y arquitectura | Aprobado |
| Modelo de datos y UML | v1 hecho (15-nov-2026) |
| Triggers, funciones y datos de demostración | Hecho, 25/25 pruebas (16-nov-2026) |
| API Flask y autenticación | Hecho, 22/22 pruebas (16-nov-2026) |
| Pantallas web (celular y PC) | Hecho, v1 probada en el navegador (16-nov-2026) |
| Datos reales (IDESC, NSR-10) | Hecho (16-nov-2026) |
| Docker + GeoServer, desplegado en el Lenovo | Hecho (16-nov-2026) |
| Repositorio en GitHub | Hecho: [Niick08/810-por-mejor-gestion-cali](https://github.com/Niick08/810-por-mejor-gestion-cali) |
| Memoria, video y publicación en internet (Funnel) | Siguiente |
| Implementación | Pendiente |
| Memoria y video | Pendiente |
