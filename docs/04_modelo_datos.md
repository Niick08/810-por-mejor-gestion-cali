# Modelo de datos y diagramas UML

> v1 · 15-nov-2026 · Se basa en [02_diseno_funcional.md](02_diseno_funcional.md) v2. El SQL está en [`db/01_esquema.sql`](../db/01_esquema.sql).
> Los diagramas están en Mermaid: se ven en GitHub, en VS Code (con la extensión de Mermaid) o en https://mermaid.live.

## 1. Convenciones

- **SRID de almacenamiento: 4326 (WGS84)**, el que usan Leaflet y el GPS. Los cálculos en metros se hacen con `::geography`. Los datos oficiales (IDESC, en MAGNA-SIRGAS) se transforman al importarlos; la cartografía oficial nacional usa EPSG:9377.
- Las tablas **privadas** tienen `empresa_id`. Las del **registro común** se exponen con vistas de campos mínimos.
- Los estados y tipos se controlan con `CHECK` para que la base de datos rechace valores inválidos.
- Los parámetros de negocio (24 h, tolerancias, meta) están en la tabla `parametro`, no escritos en el código.

## 2. Entidades por capa

| Capa | Tabla | Qué guarda | ¿Privada? |
|---|---|---|---|
| **Referencia** | `comuna`, `barrio` | Límites de Cali (IDESC) | Común |
| | `tipo_rcd` | Catálogo de RCD: categoría aprovechable / no aprovechable y densidad (t/m³) para estimar el peso | Común |
| | `parametro` | Horas para "sin cierre", tolerancias, meta de aprovechamiento | Común |
| **1. Norma** | `receptor` | Gestores receptores inscritos con su **geocerca** (polígono). `empresa_id` vacío = inscrito pero no usa la plataforma | Común |
| | `receptor_acepta` | Qué tipos de RCD acepta cada receptor | Común |
| | `zona_prohibida` | Polígonos del art. 20 (ríos y canales con franja, parques, humedales…) | Común |
| **Empresa** | `empresa` | Gestoras que usan la plataforma | — |
| | `usuario` | Rol `admin` / `usuario`, con perfil `portero` / `conductor` / `inspector` | Privada |
| | `transportador` | Transportadores (con o sin empresa) y su PIN | Común (mínimo) |
| | `vehiculo` | Placa, capacidad, si tiene GPS o cámara | Común (placa) |
| | `obra` | Obras de los clientes de la empresa (generadores) con su geocerca | Privada |
| **2. Operación** | `movimiento` | El hilo: origen, placa, volumen declarado, estado | **Registro común** (vista mínima) |
| | `entrada` | Lo que registra el portero: placa, volumen recibido, peso, resultado | Privada del receptor |
| | `movimiento_entrada` | Qué movimientos cerró o rechazó cada entrada (una entrada puede cerrar varios) | — |
| | `movimiento_evento` | Línea de tiempo y auditoría (abierto, rechazado, cerrado, corregido, anulado…) | — |
| | `posicion_gps` | Rastro GPS de los vehículos (simulado) | Privada |
| | `evento_sensor` | Motor, compuerta, movimiento en la carga, con video (simulado) | Privada |
| | `alerta` | Sin cierre, faltante, zona prohibida, parada sospechosa, compuerta en tránsito… | Privada |
| **3. Problema** | `punto_arrojo` | Arrojos reportados en campo | Privada |

## 3. Diagrama entidad-relación

```mermaid
erDiagram
    EMPRESA ||--o{ USUARIO : tiene
    EMPRESA ||--o{ OBRA : gestiona
    EMPRESA ||--o{ VEHICULO : posee
    EMPRESA |o--o{ RECEPTOR : opera
    EMPRESA |o--o{ TRANSPORTADOR : emplea
    TRANSPORTADOR ||--o{ VEHICULO : conduce
    RECEPTOR ||--o{ RECEPTOR_ACEPTA : acepta
    TIPO_RCD ||--o{ RECEPTOR_ACEPTA : ""
    OBRA |o--o{ MOVIMIENTO : origina
    RECEPTOR |o--o{ MOVIMIENTO : "origina (salidas)"
    VEHICULO |o--o{ MOVIMIENTO : "transporta (por placa)"
    TIPO_RCD ||--o{ MOVIMIENTO : clasifica
    RECEPTOR ||--o{ ENTRADA : registra
    USUARIO ||--o{ ENTRADA : "registra (portero)"
    MOVIMIENTO ||--o{ MOVIMIENTO_ENTRADA : ""
    ENTRADA ||--o{ MOVIMIENTO_ENTRADA : "cierra o rechaza"
    MOVIMIENTO ||--o{ MOVIMIENTO_EVENTO : historial
    VEHICULO ||--o{ POSICION_GPS : rastro
    VEHICULO ||--o{ EVENTO_SENSOR : sensores
    MOVIMIENTO |o--o{ ALERTA : genera
    VEHICULO |o--o{ ALERTA : genera
    PUNTO_ARROJO |o--o{ ALERTA : genera
    EMPRESA ||--o{ ALERTA : recibe
    EMPRESA ||--o{ PUNTO_ARROJO : reporta
    COMUNA ||--o{ BARRIO : contiene

    MOVIMIENTO {
        uuid id PK
        text codigo UK "RCD-4F7K"
        text placa "llave del hilo"
        text origen_tipo "obra | particular | receptor"
        point geom_origen
        text mecanismo_ingreso "gps | direccion | mapa"
        numeric volumen_declarado_m3
        text estado "abierto | rechazado | cerrado | cerrado_faltante | sin_cierre | anulado"
        bool con_agravante
        timestamptz abierto_en
        timestamptz cerrado_en
    }
    ENTRADA {
        bigint id PK
        bigint receptor_id FK
        text placa
        numeric volumen_recibido_m3
        numeric peso_t
        bool peso_medido "medido o estimado"
        text resultado "recibida | rechazada | parcial | sin_origen"
        point geom_dispositivo "debe estar en la geocerca"
    }
    RECEPTOR {
        bigint id PK
        text tipo "punto_limpio | planta | transferencia | disposicion_final"
        text pin_dagma
        multipolygon geocerca
    }
    ZONA_PROHIBIDA {
        bigint id PK
        text tipo "rio | canal | humedal | parque | ..."
        multipolygon geom "ya incluye la franja"
    }
```

`ZONA_PROHIBIDA`, `COMUNA`/`BARRIO` y `PARAMETRO` no tienen llaves foráneas: se relacionan **espacialmente** (`ST_Within`, `ST_Intersects`), no por llaves. Eso también vale la pena explicarlo en la memoria.

## 4. UML: diagrama de estados del movimiento

```mermaid
stateDiagram-v2
    [*] --> abierto : generador o transportador lo abre
    abierto --> rechazado : receptor rechaza (motivo + foto)
    rechazado --> rechazado : otro receptor también rechaza
    abierto --> cerrado : receptor recibe completo
    rechazado --> cerrado : otro receptor recibe completo
    abierto --> cerrado_faltante : recibido < declarado
    rechazado --> cerrado_faltante : recibido < declarado
    abierto --> sin_cierre : pasan 24 h
    rechazado --> sin_cierre : pasan 24 h (con agravante)
    sin_cierre --> cerrado : cierre tardío (llegó después)
    abierto --> anulado : admin anula
    cerrado --> [*]
    cerrado_faltante --> [*]
    sin_cierre --> [*]
    anulado --> [*]
```

## 5. UML: diagrama de secuencia, cierre por placa

```mermaid
sequenceDiagram
    actor G as Generador (enlace)
    actor P as Portero (receptor)
    participant W as Web (Leaflet)
    participant A as API Flask
    participant D as PostgreSQL/PostGIS

    G->>W: fotos, ubicación, m³, placa
    W->>A: POST /movimientos
    A->>D: INSERT movimiento (estado = abierto)
    D-->>A: código RCD-4F7K
    A-->>G: QR + enlace de seguimiento

    Note over P: el camión llega a la planta
    P->>W: escribe la placa XYZ-123
    W->>A: GET /entradas/abiertos?placa=XYZ-123
    A->>D: SELECT vista de movimientos abiertos
    D-->>P: 2 movimientos abiertos (m³, barrio, foto)
    P->>W: selecciona, confirma m³, foto, ubicación del celular
    W->>A: POST /entradas
    A->>D: INSERT entrada + movimiento_entrada
    D->>D: TRIGGER: ¿celular dentro de la geocerca? ¿faltante?
    D-->>A: movimientos cerrados (o cerrado_faltante + alerta)
    A-->>G: estado "Recibido en Planta Sur" + certificado
```

## 6. UML: casos de uso

```mermaid
flowchart LR
    G([Generador<br/>sin cuenta])
    C([Usuario:<br/>conductor])
    P([Usuario:<br/>portero])
    I([Usuario:<br/>inspector])
    AD([Administrador])

    subgraph Plataforma
      U1(Abrir movimiento)
      U2(Ver estado y certificado)
      U3(Ver ruta a receptor)
      U4(Registrar arrojo)
      U5(Registrar entrada y cerrar)
      U6(Rechazar carga)
      U7(Registrar salida)
      U8(Registrar obra)
      U9(Ver dashboard y meta)
      U10(Seguir viajes y cámara)
      U11(Revisar alertas)
      U12(Corregir o anular)
      U13(Gestionar geocercas)
      U14(Exportar reporte trimestral)
    end

    G --- U1
    G --- U2
    C --- U1
    C --- U3
    C --- U4
    P --- U5
    P --- U6
    P --- U7
    I --- U8
    I --- U4
    AD --- U9
    AD --- U10
    AD --- U11
    AD --- U12
    AD --- U13
    AD --- U14
```

## 7. Dónde vive cada regla (siguiente fase: triggers y funciones)

| Regla (diseño §2) | Implementación prevista |
|---|---|
| Cierre solo dentro de la geocerca | Trigger en `entrada`: `ST_Within(geom_dispositivo, ST_Buffer(geocerca::geography, tolerancia))` |
| Faltante | Trigger en `movimiento_entrada`: suma de lo declarado contra lo recibido |
| Sin cierre a las 24 h | Función `marcar_sin_cierre()` ejecutada periódicamente |
| Zona prohibida / parada sospechosa | Función sobre `posicion_gps`: paradas > N min fuera de geocercas |
| Compuerta en tránsito | Trigger en `evento_sensor` |
| Peso estimado | `volumen × tipo_rcd.densidad_t_m3` cuando `peso_medido = false` |
| Línea de tiempo | Trigger que escribe en `movimiento_evento` en cada cambio de estado |
