-- =====================================================================
-- Trazabilidad geográfica de RCD — Cali
-- 01_esquema.sql : tablas, restricciones, índices y vistas del registro común
-- Modelo descrito en docs/04_modelo_datos.md
-- SRID de almacenamiento: 4326. Cálculos métricos con ::geography.
-- =====================================================================

CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS pgrouting;
CREATE EXTENSION IF NOT EXISTS pgcrypto;   -- gen_random_uuid()

CREATE SCHEMA IF NOT EXISTS rcd;
SET search_path = rcd, public;

-- ---------------------------------------------------------------------
-- REFERENCIA
-- ---------------------------------------------------------------------
CREATE TABLE comuna (
    id      integer PRIMARY KEY,
    nombre  text NOT NULL,
    geom    geometry(MultiPolygon, 4326) NOT NULL
);

CREATE TABLE barrio (
    id         integer PRIMARY KEY,
    nombre     text NOT NULL,
    comuna_id  integer REFERENCES comuna(id),
    geom       geometry(MultiPolygon, 4326) NOT NULL
);

CREATE TABLE tipo_rcd (
    id             smallserial PRIMARY KEY,
    codigo         text UNIQUE NOT NULL,
    nombre         text NOT NULL,
    categoria      text NOT NULL CHECK (categoria IN ('aprovechable', 'no_aprovechable')),
    grupo          text,                        -- p. ej. excavación, pétreos, no pétreos
    densidad_t_m3  numeric(5,3) NOT NULL CHECK (densidad_t_m3 > 0)  -- para estimar peso (Res. 0472, art. 19, par. 1)
);

CREATE TABLE parametro (
    clave        text PRIMARY KEY,
    valor        numeric NOT NULL,
    descripcion  text
);

-- ---------------------------------------------------------------------
-- EMPRESAS Y USUARIOS
-- ---------------------------------------------------------------------
CREATE TABLE empresa (
    id         serial PRIMARY KEY,
    nombre     text NOT NULL,
    nit        text UNIQUE,
    pin_dagma  text,
    activa     boolean NOT NULL DEFAULT true,
    creada_en  timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE usuario (
    id             serial PRIMARY KEY,
    empresa_id     integer NOT NULL REFERENCES empresa(id),
    nombre         text NOT NULL,
    email          text UNIQUE NOT NULL,
    password_hash  text NOT NULL,
    rol            text NOT NULL CHECK (rol IN ('admin', 'usuario')),
    perfil         text CHECK (perfil IN ('portero', 'conductor', 'inspector')),
    activo         boolean NOT NULL DEFAULT true,
    creado_en      timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT perfil_segun_rol CHECK (
        (rol = 'admin'   AND perfil IS NULL) OR
        (rol = 'usuario' AND perfil IS NOT NULL))
);

-- ---------------------------------------------------------------------
-- CAPA 1: NORMA
-- ---------------------------------------------------------------------
CREATE TABLE receptor (
    id             serial PRIMARY KEY,
    empresa_id     integer REFERENCES empresa(id),   -- NULL = inscrito, pero no usa la plataforma
    nombre         text NOT NULL,
    tipo           text NOT NULL CHECK (tipo IN
                     ('punto_limpio', 'planta_aprovechamiento',
                      'estacion_transferencia', 'disposicion_final')),
    pin_dagma      text,
    vigente_hasta  date,
    direccion      text,
    geocerca       geometry(MultiPolygon, 4326) NOT NULL,
    activo         boolean NOT NULL DEFAULT true
);

CREATE TABLE receptor_acepta (
    receptor_id  integer  REFERENCES receptor(id) ON DELETE CASCADE,
    tipo_rcd_id  smallint REFERENCES tipo_rcd(id),
    PRIMARY KEY (receptor_id, tipo_rcd_id)
);

CREATE TABLE zona_prohibida (
    id        serial PRIMARY KEY,
    tipo      text NOT NULL CHECK (tipo IN
                ('rio', 'quebrada', 'canal', 'humedal', 'parque',
                 'zona_verde', 'espacio_publico', 'otra')),
    nombre    text,
    fuente    text,                 -- p. ej. IDESC, OSM, digitalizado
    franja_m  numeric,              -- franja aplicada al generar el polígono
    geom      geometry(MultiPolygon, 4326) NOT NULL
);

-- ---------------------------------------------------------------------
-- TRANSPORTE Y OBRAS
-- ---------------------------------------------------------------------
CREATE TABLE transportador (
    id          serial PRIMARY KEY,
    empresa_id  integer REFERENCES empresa(id),     -- NULL = independiente (chanero)
    nombre      text NOT NULL,
    documento   text UNIQUE,
    pin_dagma   text,
    celular     text
);

CREATE TABLE vehiculo (
    id                serial PRIMARY KEY,
    placa             text UNIQUE NOT NULL CHECK (placa = upper(placa)),
    empresa_id        integer REFERENCES empresa(id),   -- NULL = de un independiente
    transportador_id  integer REFERENCES transportador(id),
    tipo              text,                              -- volqueta, camión, ...
    capacidad_m3      numeric CHECK (capacidad_m3 > 0),
    tiene_gps         boolean NOT NULL DEFAULT false,
    tiene_camara      boolean NOT NULL DEFAULT false
);

CREATE TABLE obra (
    id                serial PRIMARY KEY,
    empresa_id        integer NOT NULL REFERENCES empresa(id),
    nombre            text NOT NULL,
    generador         text NOT NULL,                     -- constructora o propietario
    tipo_generador    text NOT NULL CHECK (tipo_generador IN ('grande', 'pequeno')),
    licencia          text,
    area_m2           numeric,
    direccion         text,
    geocerca          geometry(MultiPolygon, 4326),
    punto             geometry(Point, 4326) NOT NULL,
    estado            text NOT NULL DEFAULT 'activa' CHECK (estado IN ('activa', 'suspendida', 'terminada')),
    fecha_inicio      date,
    fecha_fin         date
);

-- ---------------------------------------------------------------------
-- CAPA 2: OPERACIÓN
-- ---------------------------------------------------------------------
CREATE TABLE movimiento (
    id                     uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    codigo                 text UNIQUE NOT NULL,                 -- RCD-4F7K…, va en el QR y en el enlace
    placa                  text NOT NULL CHECK (placa = upper(placa)),   -- llave del hilo
    vehiculo_id            integer REFERENCES vehiculo(id),
    transportador_id       integer REFERENCES transportador(id),
    origen_tipo            text NOT NULL CHECK (origen_tipo IN ('obra', 'particular', 'receptor')),
    obra_id                integer REFERENCES obra(id),
    receptor_origen_id     integer REFERENCES receptor(id),      -- salidas de un receptor
    empresa_origen_id      integer REFERENCES empresa(id),       -- empresa que lo abrió (NULL = particular)
    abierto_por_usuario_id integer REFERENCES usuario(id),
    generador_celular      text,                                 -- dato personal: NO va en la vista común
    acepta_datos           boolean NOT NULL DEFAULT false,       -- autorización Ley 1581
    mecanismo_ingreso      text NOT NULL CHECK (mecanismo_ingreso IN ('gps', 'direccion', 'mapa')),
    direccion_texto        text,
    barrio_id              integer REFERENCES barrio(id),
    geom_origen            geometry(Point, 4326) NOT NULL,
    tipo_rcd_id            smallint NOT NULL REFERENCES tipo_rcd(id),
    volumen_declarado_m3   numeric NOT NULL CHECK (volumen_declarado_m3 > 0),
    foto_carga_url         text NOT NULL,
    foto_placa_url         text,
    precinto               text,
    estado                 text NOT NULL DEFAULT 'abierto' CHECK (estado IN
                             ('abierto', 'rechazado', 'cerrado', 'cerrado_faltante',
                              'sin_cierre', 'anulado')),
    con_agravante          boolean NOT NULL DEFAULT false,       -- fue rechazado antes de quedar sin cierre
    abierto_en             timestamptz NOT NULL DEFAULT now(),
    cerrado_en             timestamptz,
    CONSTRAINT origen_coherente CHECK (
        (origen_tipo = 'obra'       AND obra_id IS NOT NULL) OR
        (origen_tipo = 'receptor'   AND receptor_origen_id IS NOT NULL) OR
        (origen_tipo = 'particular'))
);

CREATE TABLE entrada (
    id                   bigserial PRIMARY KEY,
    receptor_id          integer NOT NULL REFERENCES receptor(id),
    usuario_id           integer NOT NULL REFERENCES usuario(id),     -- portero
    placa                text NOT NULL CHECK (placa = upper(placa)),
    registrada_en        timestamptz NOT NULL DEFAULT now(),
    resultado            text NOT NULL CHECK (resultado IN ('recibida', 'rechazada', 'parcial', 'sin_origen')),
    motivo_rechazo       text CHECK (motivo_rechazo IN
                           ('mezcla_basura', 'peligrosos', 'material_no_aceptado',
                            'sin_capacidad', 'parcial')),
    tipo_rcd_id          smallint REFERENCES tipo_rcd(id),            -- tipo verificado en la portería
    volumen_recibido_m3  numeric CHECK (volumen_recibido_m3 >= 0),
    peso_t               numeric CHECK (peso_t >= 0),
    peso_medido          boolean NOT NULL DEFAULT false,              -- false = estimado con densidad
    precinto             text,
    foto_url             text,
    barrio_origen_id     integer REFERENCES barrio(id),               -- para entradas sin origen
    geom_dispositivo     geometry(Point, 4326) NOT NULL,              -- debe caer en la geocerca
    CONSTRAINT rechazo_con_motivo CHECK (
        resultado NOT IN ('rechazada', 'parcial') OR (motivo_rechazo IS NOT NULL AND foto_url IS NOT NULL))
);

CREATE TABLE movimiento_entrada (
    movimiento_id  uuid   REFERENCES movimiento(id),
    entrada_id     bigint REFERENCES entrada(id),
    PRIMARY KEY (movimiento_id, entrada_id)
);

CREATE TABLE movimiento_evento (
    id             bigserial PRIMARY KEY,
    movimiento_id  uuid NOT NULL REFERENCES movimiento(id),
    tipo           text NOT NULL CHECK (tipo IN
                     ('abierto', 'recogido', 'rechazado', 'cerrado', 'cerrado_faltante',
                      'sin_cierre', 'anulado', 'ubicacion_corregida')),
    ocurrido_en    timestamptz NOT NULL DEFAULT now(),
    usuario_id     integer REFERENCES usuario(id),
    entrada_id     bigint REFERENCES entrada(id),
    detalle        jsonb
);

CREATE TABLE posicion_gps (
    id             bigserial PRIMARY KEY,
    vehiculo_id    integer NOT NULL REFERENCES vehiculo(id),
    registrado_en  timestamptz NOT NULL,
    geom           geometry(Point, 4326) NOT NULL,
    velocidad_kmh  numeric
);

CREATE TABLE evento_sensor (
    id             bigserial PRIMARY KEY,
    vehiculo_id    integer NOT NULL REFERENCES vehiculo(id),
    tipo           text NOT NULL CHECK (tipo IN
                     ('motor_encendido', 'motor_apagado', 'compuerta_abierta',
                      'compuerta_cerrada', 'movimiento_carga')),
    registrado_en  timestamptz NOT NULL,
    geom           geometry(Point, 4326),
    video_url      text
);

-- ---------------------------------------------------------------------
-- CAPA 3: PROBLEMA
-- ---------------------------------------------------------------------
CREATE TABLE punto_arrojo (
    id                   serial PRIMARY KEY,
    empresa_id           integer NOT NULL REFERENCES empresa(id),
    reportado_por        integer NOT NULL REFERENCES usuario(id),
    mecanismo_ingreso    text NOT NULL CHECK (mecanismo_ingreso IN ('gps', 'direccion', 'mapa')),
    direccion_texto      text,
    geom                 geometry(Point, 4326) NOT NULL,
    tipo_rcd_id          smallint REFERENCES tipo_rcd(id),
    volumen_estimado_m3  numeric CHECK (volumen_estimado_m3 > 0),
    foto_url             text NOT NULL,
    reportado_en         timestamptz NOT NULL DEFAULT now(),
    estado               text NOT NULL DEFAULT 'reportado' CHECK (estado IN ('reportado', 'verificado', 'atendido'))
);

-- ---------------------------------------------------------------------
-- ALERTAS
-- ---------------------------------------------------------------------
CREATE TABLE alerta (
    id             bigserial PRIMARY KEY,
    empresa_id     integer REFERENCES empresa(id),     -- NULL = transportador independiente (pendiente 8 de 00_decisiones.md)
    tipo           text NOT NULL CHECK (tipo IN
                     ('sin_cierre', 'faltante', 'rechazo', 'zona_prohibida',
                      'parada_sospechosa', 'compuerta_en_transito', 'cierre_fuera_geocerca',
                      'arrojo_cercano')),
    gravedad       text NOT NULL CHECK (gravedad IN ('alta', 'media', 'baja')),
    movimiento_id  uuid    REFERENCES movimiento(id),
    vehiculo_id    integer REFERENCES vehiculo(id),
    arrojo_id      integer REFERENCES punto_arrojo(id),
    geom           geometry(Point, 4326),
    creada_en      timestamptz NOT NULL DEFAULT now(),
    estado         text NOT NULL DEFAULT 'abierta' CHECK (estado IN ('abierta', 'revisada', 'escalada')),
    revisada_por   integer REFERENCES usuario(id),
    detalle        jsonb
);

-- ---------------------------------------------------------------------
-- ÍNDICES (espaciales y de búsqueda frecuente)
-- ---------------------------------------------------------------------
CREATE INDEX ON comuna         USING gist (geom);
CREATE INDEX ON barrio         USING gist (geom);
CREATE INDEX ON receptor       USING gist (geocerca);
CREATE INDEX ON zona_prohibida USING gist (geom);
CREATE INDEX ON obra           USING gist (punto);
CREATE INDEX ON movimiento     USING gist (geom_origen);
CREATE INDEX ON posicion_gps   USING gist (geom);
CREATE INDEX ON punto_arrojo   USING gist (geom);
CREATE INDEX ON alerta         USING gist (geom);

CREATE INDEX movimiento_placa_abiertos ON movimiento (placa) WHERE estado IN ('abierto', 'rechazado', 'sin_cierre');
CREATE INDEX ON entrada (receptor_id, registrada_en);
CREATE INDEX ON posicion_gps (vehiculo_id, registrado_en);
CREATE INDEX ON evento_sensor (vehiculo_id, registrado_en);
CREATE INDEX ON alerta (empresa_id, estado);

-- ---------------------------------------------------------------------
-- VISTAS DEL REGISTRO COMÚN (solo campos mínimos, sin datos personales)
-- ---------------------------------------------------------------------
CREATE VIEW v_movimientos_abiertos AS
SELECT m.codigo,
       m.placa,
       m.abierto_en,
       m.volumen_declarado_m3,
       t.nombre  AS tipo_rcd,
       b.nombre  AS barrio,
       CASE m.origen_tipo WHEN 'obra' THEN o.nombre ELSE 'Particular' END AS origen,
       m.foto_carga_url,
       m.estado
FROM movimiento m
JOIN tipo_rcd t    ON t.id = m.tipo_rcd_id
LEFT JOIN barrio b ON b.id = m.barrio_id
LEFT JOIN obra o   ON o.id = m.obra_id
WHERE m.estado IN ('abierto', 'rechazado', 'sin_cierre');   -- sin_cierre: permite el cierre tardío

CREATE VIEW v_capa_normativa AS
SELECT 'receptor'::text AS capa, r.id, r.tipo, r.nombre, r.pin_dagma, r.geocerca AS geom
FROM receptor r
WHERE r.activo AND (r.vigente_hasta IS NULL OR r.vigente_hasta >= current_date)
UNION ALL
SELECT 'prohibida', z.id, z.tipo, z.nombre, NULL, z.geom
FROM zona_prohibida z;

-- Parámetros por defecto (D5, D15 y diseño §2)
INSERT INTO parametro (clave, valor, descripcion) VALUES
  ('horas_sin_cierre',          24, 'Horas para marcar un movimiento como sin cierre'),
  ('tolerancia_geocerca_m',     30, 'Tolerancia del GPS alrededor de una geocerca'),
  ('tolerancia_faltante_pct',   10, 'Diferencia aceptada entre declarado y recibido'),
  ('parada_sospechosa_min',     10, 'Minutos detenido fuera de geocercas para alertar'),
  ('meta_aprovechamiento_pct',  50, 'Meta para Cali, categoría especial, desde 2026 (Res. 0472, art. 19)');
