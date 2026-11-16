# Docker y despliegue

> v1 · 16-nov-2026 · Funciona igual en Windows (Docker Desktop) y en Linux (servidor Lenovo).

## 1. Servicios

```
docker-compose.yml
├── db                PostgreSQL 16 + PostGIS 3.5 + pgRouting 3.8 (imagen pgrouting/pgrouting:16-3.5-3.8.0)
│                     → la primera vez carga 01, 02, 04 y 03 (docker/initdb.sh)
├── geoserver         GeoServer 2.28.0 (imagen oficial docker.osgeo.org/geoserver)
├── geoserver-config  Se ejecuta una vez: workspace "rcd", almacén PostGIS, 3 estilos SLD y 3 capas
├── api               Flask + pantallas web con gunicorn (3 workers)
│                     → al arrancar: claves demo (si MODO_DEMO=1) y datos de la IDESC (solo la primera vez)
└── tareas            Cada 5 min: R4 (sin cierre a las 24 h) y R6 (paradas sospechosas)
```

| Puerto en el equipo | Servicio | Uso |
|---|---|---|
| `8085` (`APP_PORT`) | api | **La plataforma**: `http://equipo:8085` |
| `8086` (`GEOSERVER_PORT`) | geoserver | Administración de GeoServer: `http://equipo:8086/geoserver` |
| `127.0.0.1:5433` (`DB_PORT`) | db | Solo desde el mismo equipo (psql, QGIS) |

Los datos viven en volúmenes de Docker (`datos_db`, `datos_geoserver`, `fotos`): sobreviven a reinicios y a reconstrucciones.

## 2. GeoServer: qué se publica y por qué

| Capa | Fuente | Estilo |
|---|---|---|
| `rcd:capa_normativa` | vista `v_capa_normativa` | Receptores en verde; agua y rondas en rojo; parques y zonas verdes en naranja |
| `rcd:comunas` | tabla `comuna` (IDESC) | Límite discontinuo con el nombre |
| `rcd:barrios` | tabla `barrio` (IDESC) | Límite fino; nombres al acercarse (escala < 1:20.000) |

- **Solo se publican capas comunes.** Los datos privados de cada empresa (movimientos, entradas, GPS) nunca pasan por GeoServer, porque WMS/WFS no conoce las sesiones ni las empresas. Esos datos salen únicamente por la API, que sí controla quién los ve.
- **La web llega a GeoServer a través de la API** (`/geoserver/rcd/wms`), que solo deja pasar WMS/WFS del workspace `rcd`. Así hay un solo origen y un solo puerto, sin problemas de CORS, y la administración no queda expuesta por ese puerto.
- **Los estilos están en archivos SLD** (`docker/geoserver/*.sld`) y la configuración es un script (`docker/geoserver/configurar.py`, API REST). Nada se hace a mano en la interfaz de GeoServer, así que el resultado es reproducible.

En los mapas, las capas aparecen como *Comunas / Barrios / Capa normativa (WMS · GeoServer)*, junto a las capas GeoJSON de la API.

## 3. Cómo levantarlo

```bash
cp docker.env.example docker.env      # y cambia las claves
docker compose --env-file docker.env up -d --build
docker compose --env-file docker.env ps
```

Para borrar todo y empezar de cero (⚠ elimina los datos):

```bash
docker compose --env-file docker.env down -v
```

## 4. Instalación en el Lenovo (hecha el 16-nov-2026)

- Carpeta: `~/rcd-trazabilidad` · `docker.env` con claves aleatorias (permisos 600).
- Plataforma: **http://100.109.154.10:8085** (por Tailscale) · GeoServer: http://100.109.154.10:8086/geoserver.
- El geocodificador se alcanza desde el contenedor en `http://host.docker.internal/api` (nginx del propio Lenovo).
- Convive con lo que ya corría (PostgreSQL 18 en 5432, nginx en 80): no hay puertos en conflicto.

Para actualizar después de cambiar el código: copiar el proyecto y correr `docker compose --env-file docker.env up -d --build`. La base de datos **no** se recrea, porque su volumen se conserva.

## 5. Docker en este PC (Windows)

Docker Desktop necesita WSL2. Se instala con permisos de administrador (PowerShell "Ejecutar como administrador"):

```powershell
wsl --install
```

Reiniciar, y luego:

```powershell
winget install -e --id Docker.DockerDesktop
```

Abrir Docker Desktop una vez y, en la carpeta del proyecto, usar los mismos comandos de la sección 3. En Windows `GEOCODIFICADOR_URL` debe ser `http://100.109.154.10/api` (por Tailscale).

**Estado (16-nov-2026): instalado y funcionando.** Docker 29.9.3 con WSL2 (Ubuntu). Plataforma en http://localhost:8085 y GeoServer en http://localhost:8086/geoserver. Diferencias con el Lenovo:
- `DB_PORT=5434`, porque en este PC el 5432 y el 5433 ya los usan PostgreSQL 16 y 18 instalados en Windows.
- El geocodificador se alcanza desde el contenedor por Tailscale (`http://100.109.154.10/api`). Funciona porque este PC está en la red Tailscale.

## 6. Si el registro de OSGeo no responde

El 16-nov-2026 `docker.osgeo.org` devolvió **502 Bad Gateway** y no se pudo descargar la imagen de GeoServer. Solución: copiarla desde un equipo que ya la tenga (por ejemplo, el Lenovo):

```bash
# en el equipo que tiene la imagen
docker save docker.osgeo.org/geoserver:2.28.0 | gzip -1 > geoserver-2.28.0.tar.gz      # ~334 MB
# en el equipo que la necesita (después de copiar el archivo)
docker load -i geoserver-2.28.0.tar.gz
```

Para la sustentación conviene tener ese archivo guardado: si el registro falla ese día, no hace falta internet para levantar GeoServer.
