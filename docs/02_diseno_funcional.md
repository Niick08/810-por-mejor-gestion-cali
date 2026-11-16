# Diseño funcional — Plataforma de trazabilidad geográfica de RCD

> Versión 2.0 · 15-nov-2026 · Consolida las decisiones D1–D16 de [00_decisiones.md](00_decisiones.md). Es la referencia para el modelo de datos y la implementación.

## 1. Visión

Plataforma web **multiempresa** para gestores de residuos de construcción y demolición (RCD) en Cali. Cada empresa gestora tiene su **espacio privado** para controlar su operación. Un **registro común mínimo** permite que cualquier receptor cierre un movimiento abierto por otra persona, buscándolo por la **placa** del camión. Cada movimiento se valida contra la Resolución 0472 de 2017 convertida en capas geográficas.

## 2. Conceptos

| Concepto | Definición |
|---|---|
| **Empresa (gestora)** | Espacio privado: camiones, operarios, clientes, geocercas propias, entradas y salidas, dashboard, reportes |
| **Registro común** | Capa normativa + movimientos abiertos (placa, hora, m³, tipo, barrio, foto). Nada comercial |
| **Movimiento** | Unidad básica: origen → placa → receptor → volumen → estado. Lo abre el generador o el transportador; **solo lo cierra el receptor** |
| **Receptor** | Punto limpio, planta de aprovechamiento, estación de transferencia o sitio de disposición final inscrito. Cierra movimientos y puede ser origen de nuevos (salidas) |
| **Geocerca** | Polígono de un receptor u obra. Los cierres y las alertas dependen de ella |

### Estados del movimiento

```
abierto ──► rechazado (sigue abierto) ──┐
   │                                     │
   ├──► cerrado ✓ ◄──────────────────────┤
   ├──► cerrado con faltante ⚠ ◄─────────┤
   └──► sin cierre ✕ (24 h) ◄────────────┘  (con agravante si hubo rechazo)
```

### Reglas
1. **Cierre:** solo una cuenta de receptor, con el dispositivo dentro de su geocerca.
2. **Gestor integrado:** para cerrar sus propios movimientos, el GPS del camión debe estar dentro de la geocerca de su planta.
3. **Faltante:** si el volumen recibido es menor que el declarado → "cerrado con faltante" + alerta.
4. **Sin cierre:** a las 24 h (configurable) sin cierre → alerta.
5. **Rechazo:** motivo + foto obligatoria. El movimiento sigue abierto y se le sugieren al transportador receptores que sí acepten ese material.
6. **Parada sospechosa (si hay GPS):** parada de más de N minutos fuera de toda geocerca autorizada; si cae en una zona prohibida, la alerta es grave.
7. **Cámara de carga:** apertura de compuerta o movimiento en la carga, en tránsito y fuera de geocercas autorizadas → alerta.
8. **Peso:** medido u opcional; si no hay, se estima con la densidad por tipo de material (Res. 0472, art. 19, par. 1).

## 3. Roles y perfiles

| Rol (curso) | Perfil | Dispositivo | Qué hace |
|---|---|---|---|
| **Administrador** | Coordinador de la empresa gestora | PC | Dashboard, seguimiento, alertas, geocercas, flota, usuarios, reportes; corrige y anula |
| **Usuario** | Portero / receptor | Celular | Entradas (cerrar o rechazar) y salidas |
| **Usuario** | Conductor | Celular | Abre movimientos, GPS y ruta, registra arrojos vistos en la vía |
| **Usuario** | Inspector | Celular | Registra obras y puntos de arrojo |
| — | Pequeño generador | Celular, por enlace | Abre un movimiento sin cuenta y descarga su certificado |

## 4. Pantallas

### Celular (operativo)

| # | Pantalla | Perfil | Contenido principal | Botón principal |
|---|---|---|---|---|
| M1 | Enlace del generador | Sin cuenta | Ubicación (GPS / dirección / mapa) · foto · tipo · m³ · foto de la placa · celular | **Entregar escombros** → QR → línea de tiempo y certificado |
| M2 | Entradas | Portero | Placa → movimientos abiertos → lo recibido (m³ −/+, peso, tipo, precinto, foto) | **Recibir y cerrar** / Rechazar carga |
| M3 | Salidas | Portero | Despachos de la planta hacia otros receptores (abre un movimiento nuevo) | **Despachar** |
| M4 | Mi jornada | Conductor / inspector | Mapa con capas: obras por estado, calor de m³, clúster, receptores, zonas prohibidas | **Nuevo registro** (movimiento · arrojo) |
| M5 | Ruta | Conductor | Ruta al receptor más cercano que acepta el material (pgRouting) | **Iniciar viaje** |
| M6 | Mis viajes y datos | Conductor | Lista filtrable · gráfico por tipo · tabla por obra | — |

Barra inferior del portero: Entradas · Salidas · Hoy. Barra del conductor: Mapa · Viajes · Datos.

### PC (control)

| # | Pantalla | Contenido principal | Botones |
|---|---|---|---|
| P1 | Dashboard | **Meta de aprovechamiento (50%) y cuánto falta**, m³ gestionados, alertas abiertas, balance entradas/salidas, operarios más activos, tendencia de m³ por tipo | **Reporte trimestral** |
| P2 | Seguimiento | Viajes en tránsito · mapa con trayecto GPS y geocercas · **cámara de carga** · línea de tiempo de eventos | Ver grabación · Marcar revisada · Escalar |
| P3 | Control | Alertas por gravedad · mapa: flujos obra → receptor, clúster, densidad, arrojos con movimientos cercanos · detalle | **Validar** · Corregir ubicación · Anular |
| P4 | Geocercas y capa normativa | Receptores propios e inscritos, zonas prohibidas (art. 20) | + Receptor · Dibujar polígono · Cargar GeoJSON · Editar · Eliminar |
| P5 | Movimientos | Tabla filtrable con todos los movimientos de la empresa | Editar · **Anular por rango de fechas** · Exportar |
| P6 | Flota y usuarios | Camiones (placa, GPS, cámara) y operarios (perfil) | + Camión · + Usuario |

## 5. Trazabilidad de requisitos del curso

| Requisito | Mín. | Cómo se cumple | Pantalla |
|---|---|---|---|
| Usuario: ingreso espacial y alfanumérico | 3 | GPS · dirección (geocodificador propio) · clic en mapa, con foto y atributos | M1, M4 |
| Usuario: visualización espacial | 3 | Temático de obras por estado · calor de m³ · clúster | M4 |
| Usuario: visualización alfanumérica | 3 | Lista filtrable · gráfico por tipo · tabla por obra | M6 |
| Admin: modificar o eliminar | 2 | Corregir ubicación · anular · anular por rango · editar/eliminar geocercas | P3, P4, P5 |
| Admin: visualización espacial | 2 | Flujos obra → receptor · clúster · densidad · trayecto GPS | P2, P3 |
| Admin: visualización alfanumérica | 2 | Operarios más activos · tendencia por tipo · meta de aprovechamiento | P1 |
| Roles diferenciados | — | Administrador / Usuario (con perfiles) | todas |

## 6. Alcance

- **Se construye:** todas las pantallas, la lógica real de movimientos, estados, geocercas y alertas, con datos de demostración.
- **Se simula:** GPS de los camiones, sensores de compuerta y cámara (un recuadro con video de ejemplo).
- **Se deja planteado:** dispositivos físicos, integración con Traccar, supervisión de transportadores independientes por la autoridad ambiental e integración con sistemas oficiales.
