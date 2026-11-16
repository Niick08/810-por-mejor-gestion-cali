# Fuentes de datos

> v1 · 16-nov-2026 · Cargador: [`scripts/cargar_datos_reales.py`](../scripts/cargar_datos_reales.py) · Copias: [`db/datos_reales/`](../db/datos_reales)

## 1. Capas oficiales de Santiago de Cali (IDESC)

Se descargan por **WFS** del GeoServer de la Infraestructura de Datos Espaciales de Santiago de Cali (`https://ws-idesc.cali.gov.co/geoserver/wfs`) en EPSG:4326. Las zonas se recortan a la zona urbana (unión de las 22 comunas).

| Tabla de la plataforma | Capa IDESC | Entidades cargadas | Qué aporta |
|---|---|---|---|
| `comuna` | `dapm:pdt_dpa_comunas` | 22 | División político-administrativa (DAPM) |
| `barrio` | `dapm:pdt_dpa_barrios_sectores` | 342 | Barrios y sectores, con su comuna |
| `zona_prohibida` · quebrada / río / canal / humedal | `pot_2014:amb_eep_afp_recurso_hidrico` | 123 + 16 + 1 + 48 | **Áreas forestales protectoras del recurso hídrico** del POT 2014 (Acuerdo 0373), ya con su franja oficial (30 m en quebradas, ríos y humedales; 100 m en nacimientos) |
| `zona_prohibida` · río | `pot_2014:bcs_hid_rios` | (incluidos arriba) | Cauces de los ríos |
| `zona_prohibida` · humedal | `dagma:hid_sup_humedales_urbanos` | 60 | Humedales urbanos (DAGMA) |
| `zona_prohibida` · parque / zona verde | `dapm:epou_epu_espacio_publico_efectivo` | 1.241 + 646 | Solo los elementos "Parque" y "Zona verde" del espacio público efectivo |

**Relación con la norma:** el art. 20 de la Res. 0472/2017 prohíbe almacenar RCD en zonas verdes, parques, ríos, quebradas, canales, humedales y zonas ribereñas. Cada una de esas categorías tiene aquí una capa oficial. La franja de protección **no la definimos nosotros**: es la que trae el POT.

**Para dibujar** en el mapa, la capa se simplifica a unos 2 m (`ST_SimplifyPreserveTopology`), lo que la reduce de 5,2 MB a 0,75 MB. Las reglas de la base de datos usan siempre la geometría completa.

## 2. Densidades para estimar el peso

Fuente: **NSR-10, Título B, Tabla B.3.2-1 "Masas de los materiales"**, como permite la Res. 0472/2017, art. 19, par. 1.

| Tipo de RCD | Fila de la tabla | kg/m³ | t/m³ usado |
|---|---|---|---|
| Excavación (EXC) | Arena y grava seca suelta | 1 600 | 1,60 |
| Cimentaciones (CIM) | Arcilla húmeda | 1 750 | 1,75 |
| Pétreos (PET) | Mampostería de concreto (concreto simple 2 300; ladrillo macizo 1 850) | 2 150 | 2,15 |
| Metales (MET) | Acero | 7 800 | 7,80 |
| Madera (MAD) | Madera seca | 450–750 | 0,60 (punto medio) |
| Vidrio (VID) | Vidrio | 2 600 | 2,60 |
| Plásticos y drywall (PLA) | Yeso en tableros para muros | 800 | 0,80 |
| Mezclado (NAP) | Arcilla y grava seca | 1 600 | 1,60 |

⚠ **Limitación (para la memoria):** son densidades de material **sólido**. El escombro suelto ocupa más volumen (esponjamiento), así que el peso estimado queda **por encima** del real. Por eso cada registro guarda si el peso fue *medido* o *estimado*, y el gestor puede reemplazar la densidad por la que mida en una muestra, que la misma norma también permite.

## 3. Datos que siguen siendo de demostración

- **Empresas, receptores, obras, vehículos, personas y movimientos:** ficticios. El listado de gestores del DAGMA tiene nombres, pero no geometrías de sus predios.
- **GPS y sensores:** simulados.

## 4. Cómo cargar

```bash
# Base nueva: 01, 02, 04 y 03 (ver README), y luego los datos oficiales:
.venv/Scripts/python scripts/cargar_datos_reales.py --url postgresql://postgres:CLAVE@localhost:5432/rcd
# --descargar vuelve a bajar las capas de la IDESC
```

El cargador es repetible: reemplaza comunas, barrios y zonas prohibidas, y reubica por geometría los movimientos existentes en su barrio real. Las pruebas automáticas siguen usando los polígonos de prueba de `03_datos_demo.sql`, para que sus resultados no cambien cuando la IDESC actualice sus capas.

La capa de rondas hídricas (`afp_hidrico.geojson`, 29 MB) no se sube a git: el cargador la descarga si no existe.
