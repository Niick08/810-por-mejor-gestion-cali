-- =====================================================================
-- Trazabilidad geográfica de RCD — Cali
-- 02_funciones_triggers.sql : las reglas del diseño (docs/02_diseno_funcional.md §2)
-- programadas en la base de datos, para que no se puedan saltar desde la interfaz.
--
-- Reglas:
--   R1 cierre solo dentro de la geocerca del receptor ........ trg_entrada_validar
--   R2 gestor integrado: GPS dentro de su planta ............. trg_procesar_entrada
--   R3 faltante (recibido < declarado) ....................... trg_procesar_entrada
--   R4 sin cierre a las 24 h (con agravante si hubo rechazo) . fn_marcar_sin_cierre()
--   R5 rechazo: sigue abierto + receptores sugeridos ......... trg_procesar_entrada, fn_receptores_sugeridos()
--   R6 parada sospechosa / en zona prohibida (GPS) ........... fn_paradas(), fn_generar_alertas_paradas()
--   R7 compuerta abierta en tránsito ......................... trg_sensor_compuerta
--   R8 peso estimado con densidad (Res. 0472, art. 19 par. 1)  trg_entrada_validar
--   +  línea de tiempo y auditoría ........................... trg_movimiento_auditar
--   +  arrojo cruzado con movimientos cercanos (capa 3) ...... trg_arrojo_cruzar
-- =====================================================================
SET search_path = rcd, public;

INSERT INTO parametro (clave, valor, descripcion) VALUES
  ('radio_origen_m',          100, 'Radio alrededor del punto de origen que no cuenta como "en tránsito"'),
  ('ventana_gps_cierre_min',   15, 'Minutos antes o después del cierre para buscar GPS (gestor integrado)'),
  ('radio_arrojo_m',         2000, 'Radio para relacionar un arrojo con movimientos'),
  ('ventana_arrojo_h',         48, 'Horas hacia atrás para relacionar un arrojo con movimientos')
ON CONFLICT (clave) DO NOTHING;

-- ---------------------------------------------------------------------
-- Utilidades
-- ---------------------------------------------------------------------
CREATE OR REPLACE FUNCTION fn_param(p_clave text) RETURNS numeric
LANGUAGE sql STABLE AS $$ SELECT valor FROM rcd.parametro WHERE clave = p_clave $$;

-- "xyz-123", "XYZ 123" → "XYZ123": la placa es la llave del hilo, debe escribirse siempre igual
CREATE OR REPLACE FUNCTION fn_normalizar_placa(p text) RETURNS text
LANGUAGE sql IMMUTABLE AS $$ SELECT regexp_replace(upper(coalesce(p, '')), '[^A-Z0-9]', '', 'g') $$;

CREATE OR REPLACE FUNCTION trg_vehiculo_placa() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  NEW.placa := rcd.fn_normalizar_placa(NEW.placa);
  RETURN NEW;
END $$;

CREATE TRIGGER vehiculo_placa BEFORE INSERT OR UPDATE OF placa ON vehiculo
FOR EACH ROW EXECUTE FUNCTION trg_vehiculo_placa();

-- ---------------------------------------------------------------------
-- MOVIMIENTO: preparar al abrir (código, placa, vehículo, barrio)
-- ---------------------------------------------------------------------
CREATE OR REPLACE FUNCTION trg_movimiento_preparar() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  NEW.placa := rcd.fn_normalizar_placa(NEW.placa);
  IF NEW.codigo IS NULL THEN
    NEW.codigo := 'RCD-' || upper(substr(md5(gen_random_uuid()::text), 1, 6));
  END IF;
  IF NEW.vehiculo_id IS NULL THEN
    SELECT id INTO NEW.vehiculo_id FROM rcd.vehiculo WHERE placa = NEW.placa;
  END IF;
  IF NEW.transportador_id IS NULL AND NEW.vehiculo_id IS NOT NULL THEN
    SELECT transportador_id INTO NEW.transportador_id FROM rcd.vehiculo WHERE id = NEW.vehiculo_id;
  END IF;
  IF NEW.barrio_id IS NULL THEN            -- relación espacial, no por llave
    SELECT id INTO NEW.barrio_id FROM rcd.barrio WHERE ST_Intersects(geom, NEW.geom_origen) LIMIT 1;
  END IF;
  RETURN NEW;
END $$;

CREATE TRIGGER movimiento_preparar BEFORE INSERT ON movimiento
FOR EACH ROW EXECUTE FUNCTION trg_movimiento_preparar();

CREATE OR REPLACE FUNCTION trg_movimiento_abierto() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  INSERT INTO rcd.movimiento_evento (movimiento_id, tipo, ocurrido_en, usuario_id, detalle)
  VALUES (NEW.id, 'abierto', NEW.abierto_en, NEW.abierto_por_usuario_id,
          jsonb_build_object('placa', NEW.placa, 'volumen_m3', NEW.volumen_declarado_m3,
                             'mecanismo', NEW.mecanismo_ingreso));
  RETURN NULL;
END $$;

CREATE TRIGGER movimiento_abierto AFTER INSERT ON movimiento
FOR EACH ROW EXECUTE FUNCTION trg_movimiento_abierto();

-- ---------------------------------------------------------------------
-- MOVIMIENTO: transiciones de estado permitidas (diagrama de estados, docs/04 §4)
-- ---------------------------------------------------------------------
CREATE OR REPLACE FUNCTION trg_movimiento_transicion() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF NEW.estado IS DISTINCT FROM OLD.estado THEN
    IF OLD.estado IN ('cerrado', 'cerrado_faltante', 'anulado') THEN
      RAISE EXCEPTION 'El movimiento % ya está "%" y no puede cambiar de estado', OLD.codigo, OLD.estado;
    END IF;
    IF OLD.estado = 'sin_cierre' AND NEW.estado NOT IN ('cerrado', 'cerrado_faltante', 'anulado') THEN
      RAISE EXCEPTION 'El movimiento % está "sin cierre": solo se puede cerrar (cierre tardío) o anular', OLD.codigo;
    END IF;
    IF NEW.estado IN ('cerrado', 'cerrado_faltante') AND NEW.cerrado_en IS NULL THEN
      NEW.cerrado_en := now();
    END IF;
  END IF;
  RETURN NEW;
END $$;

CREATE TRIGGER movimiento_transicion BEFORE UPDATE ON movimiento
FOR EACH ROW EXECUTE FUNCTION trg_movimiento_transicion();

-- Línea de tiempo y auditoría. El usuario que hace cambios administrativos se pasa con:
--   SET LOCAL rcd.usuario_id = '<id>';   (la API lo hace en cada transacción)
CREATE OR REPLACE FUNCTION trg_movimiento_auditar() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
  v_usuario  integer := nullif(current_setting('rcd.usuario_id', true), '')::integer;
  v_entrada  bigint;
  v_receptor text;
BEGIN
  IF NEW.estado IS DISTINCT FROM OLD.estado THEN
    IF NEW.estado IN ('rechazado', 'cerrado', 'cerrado_faltante') THEN
      SELECT e.id, e.usuario_id, r.nombre INTO v_entrada, v_usuario, v_receptor
      FROM rcd.movimiento_entrada me
      JOIN rcd.entrada  e ON e.id = me.entrada_id
      JOIN rcd.receptor r ON r.id = e.receptor_id
      WHERE me.movimiento_id = NEW.id
      ORDER BY e.registrada_en DESC, e.id DESC
      LIMIT 1;
    END IF;
    INSERT INTO rcd.movimiento_evento (movimiento_id, tipo, usuario_id, entrada_id, detalle)
    VALUES (NEW.id, NEW.estado, v_usuario, v_entrada,
            jsonb_strip_nulls(jsonb_build_object(
              'desde', OLD.estado,
              'receptor', v_receptor,
              'cierre_tardio', CASE WHEN OLD.estado = 'sin_cierre' THEN true END,
              'agravante', CASE WHEN NEW.con_agravante THEN true END)));
  END IF;

  IF NOT ST_Equals(NEW.geom_origen, OLD.geom_origen) THEN
    INSERT INTO rcd.movimiento_evento (movimiento_id, tipo, usuario_id, detalle)
    VALUES (NEW.id, 'ubicacion_corregida', v_usuario,
            jsonb_build_object('antes', ST_AsGeoJSON(OLD.geom_origen)::jsonb,
                               'despues', ST_AsGeoJSON(NEW.geom_origen)::jsonb,
                               'desplazamiento_m', round(ST_Distance(OLD.geom_origen::geography,
                                                                     NEW.geom_origen::geography))));
  END IF;
  RETURN NULL;
END $$;

CREATE TRIGGER movimiento_auditar AFTER UPDATE ON movimiento
FOR EACH ROW EXECUTE FUNCTION trg_movimiento_auditar();

-- ---------------------------------------------------------------------
-- ENTRADA: R1 (geocerca) y R8 (peso estimado)
-- ---------------------------------------------------------------------
CREATE OR REPLACE FUNCTION trg_entrada_validar() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
  r        rcd.receptor;
  v_emp    integer;
  v_dist   numeric;
  v_dens   numeric;
BEGIN
  NEW.placa := rcd.fn_normalizar_placa(NEW.placa);
  SELECT * INTO r FROM rcd.receptor WHERE id = NEW.receptor_id;

  IF r.empresa_id IS NULL THEN
    RAISE EXCEPTION 'El receptor "%" no opera en la plataforma: no puede registrar entradas', r.nombre;
  END IF;

  SELECT empresa_id INTO v_emp FROM rcd.usuario
  WHERE id = NEW.usuario_id AND rol = 'usuario' AND perfil = 'portero' AND activo;
  IF v_emp IS DISTINCT FROM r.empresa_id THEN
    RAISE EXCEPTION 'El usuario % no es portero activo de "%"', NEW.usuario_id, r.nombre;
  END IF;

  -- R1: el celular del portero debe estar físicamente en el receptor
  IF NOT ST_DWithin(NEW.geom_dispositivo::geography, r.geocerca::geography,
                    rcd.fn_param('tolerancia_geocerca_m')) THEN
    v_dist := round(ST_Distance(NEW.geom_dispositivo::geography, r.geocerca::geography));
    RAISE EXCEPTION 'Entrada rechazada: el dispositivo está a % m de la geocerca de "%"', v_dist, r.nombre;
  END IF;

  IF NEW.resultado IN ('recibida', 'parcial', 'sin_origen') AND NEW.volumen_recibido_m3 IS NULL THEN
    RAISE EXCEPTION 'Una entrada "%" debe indicar el volumen recibido', NEW.resultado;
  END IF;

  -- R8: si no se pesó, se estima con la densidad del tipo de material
  IF NEW.peso_t IS NULL AND NEW.volumen_recibido_m3 IS NOT NULL AND NEW.tipo_rcd_id IS NOT NULL THEN
    SELECT densidad_t_m3 INTO v_dens FROM rcd.tipo_rcd WHERE id = NEW.tipo_rcd_id;
    NEW.peso_t      := round(NEW.volumen_recibido_m3 * v_dens, 2);
    NEW.peso_medido := false;
  END IF;
  RETURN NEW;
END $$;

CREATE TRIGGER entrada_validar BEFORE INSERT ON entrada
FOR EACH ROW EXECUTE FUNCTION trg_entrada_validar();

-- ---------------------------------------------------------------------
-- MOVIMIENTO_ENTRADA: validar el vínculo (inmediato)
-- ---------------------------------------------------------------------
CREATE OR REPLACE FUNCTION trg_vinculo_validar() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
  m rcd.movimiento;
  e rcd.entrada;
BEGIN
  SELECT * INTO m FROM rcd.movimiento WHERE id = NEW.movimiento_id;
  SELECT * INTO e FROM rcd.entrada    WHERE id = NEW.entrada_id;
  IF e.resultado = 'sin_origen' THEN
    RAISE EXCEPTION 'Una entrada sin origen no se vincula a movimientos';
  END IF;
  IF m.placa <> e.placa THEN
    RAISE EXCEPTION 'El movimiento % es de la placa %, no de %', m.codigo, m.placa, e.placa;
  END IF;
  IF m.estado NOT IN ('abierto', 'rechazado', 'sin_cierre') THEN
    RAISE EXCEPTION 'El movimiento % ya está "%"', m.codigo, m.estado;
  END IF;
  RETURN NEW;
END $$;

CREATE TRIGGER vinculo_validar BEFORE INSERT ON movimiento_entrada
FOR EACH ROW EXECUTE FUNCTION trg_vinculo_validar();

-- ---------------------------------------------------------------------
-- MOVIMIENTO_ENTRADA: procesar la entrada completa (R2, R3, R5)
-- Es un trigger DIFERIDO: corre al final de la transacción, cuando ya están todos los
-- vínculos de la entrada, para sumar bien lo declarado. Usar fn_registrar_entrada().
-- ---------------------------------------------------------------------
CREATE OR REPLACE FUNCTION trg_procesar_entrada() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
  e       rcd.entrada;
  r       rcd.receptor;
  veh     rcd.vehiculo;
  v_ids   uuid[];
  v_decl  numeric;
  v_estado text;
  v_ventana interval;
BEGIN
  SELECT * INTO e FROM rcd.entrada WHERE id = NEW.entrada_id;

  -- Idempotencia: la entrada ya se procesó (el trigger corre una vez por vínculo)
  IF EXISTS (SELECT 1 FROM rcd.movimiento_evento WHERE entrada_id = e.id) THEN
    RETURN NULL;
  END IF;

  SELECT array_agg(m.id), sum(m.volumen_declarado_m3) INTO v_ids, v_decl
  FROM rcd.movimiento_entrada me
  JOIN rcd.movimiento m ON m.id = me.movimiento_id
  WHERE me.entrada_id = e.id;

  SELECT * INTO r   FROM rcd.receptor WHERE id = e.receptor_id;
  SELECT * INTO veh FROM rcd.vehiculo WHERE placa = e.placa;

  -- R2: gestor integrado (el camión es de la misma empresa que recibe)
  IF e.resultado IN ('recibida', 'parcial') AND veh.empresa_id IS NOT NULL
     AND veh.empresa_id = r.empresa_id THEN
    IF NOT veh.tiene_gps THEN
      RAISE EXCEPTION 'Gestor integrado: el vehículo % debe tener GPS para cerrar sus propios movimientos', e.placa;
    END IF;
    v_ventana := make_interval(mins => rcd.fn_param('ventana_gps_cierre_min')::integer);
    IF NOT EXISTS (
         SELECT 1 FROM rcd.posicion_gps p
         WHERE p.vehiculo_id = veh.id
           AND p.registrado_en BETWEEN e.registrada_en - v_ventana AND e.registrada_en + v_ventana
           AND ST_DWithin(p.geom::geography, r.geocerca::geography, rcd.fn_param('tolerancia_geocerca_m'))) THEN
      RAISE EXCEPTION 'Gestor integrado: no hay posición GPS de % dentro de "%" cerca de la hora del cierre',
                      e.placa, r.nombre;
    END IF;
  END IF;

  IF e.resultado = 'rechazada' THEN
    -- R5: el movimiento sigue abierto ("rechazado"); se registra el evento aunque ya estuviera rechazado
    INSERT INTO rcd.movimiento_evento (movimiento_id, tipo, usuario_id, entrada_id, detalle)
    SELECT m.id, 'rechazado', e.usuario_id, e.id,
           jsonb_build_object('receptor', r.nombre, 'motivo', e.motivo_rechazo, 'estado_previo', m.estado)
    FROM rcd.movimiento m
    WHERE m.id = ANY (v_ids) AND m.estado IN ('rechazado', 'sin_cierre');

    UPDATE rcd.movimiento SET estado = 'rechazado'
    WHERE id = ANY (v_ids) AND estado = 'abierto';

    INSERT INTO rcd.alerta (empresa_id, tipo, gravedad, movimiento_id, vehiculo_id, geom, detalle)
    SELECT coalesce(m.empresa_origen_id, v.empresa_id), 'rechazo', 'media', m.id, m.vehiculo_id,
           ST_PointOnSurface(r.geocerca),
           jsonb_build_object('codigo', m.codigo, 'placa', m.placa, 'receptor', r.nombre,
                              'motivo', e.motivo_rechazo)
    FROM rcd.movimiento m
    LEFT JOIN rcd.vehiculo v ON v.id = m.vehiculo_id
    WHERE m.id = ANY (v_ids);

  ELSE
    -- R3: faltante si llega menos de lo declarado (con tolerancia) o si fue rechazo parcial
    IF e.resultado = 'parcial'
       OR e.volumen_recibido_m3 < v_decl * (1 - rcd.fn_param('tolerancia_faltante_pct') / 100) THEN
      v_estado := 'cerrado_faltante';
    ELSE
      v_estado := 'cerrado';
    END IF;

    UPDATE rcd.movimiento SET estado = v_estado, cerrado_en = e.registrada_en
    WHERE id = ANY (v_ids);

    IF v_estado = 'cerrado_faltante' THEN
      INSERT INTO rcd.alerta (empresa_id, tipo, gravedad, movimiento_id, vehiculo_id, geom, detalle)
      SELECT coalesce(m.empresa_origen_id, v.empresa_id), 'faltante', 'media', m.id, m.vehiculo_id,
             ST_PointOnSurface(r.geocerca),
             jsonb_build_object('codigo', m.codigo, 'placa', m.placa, 'receptor', r.nombre,
                                'declarado_total_m3', v_decl, 'recibido_m3', e.volumen_recibido_m3,
                                'faltante_m3', v_decl - e.volumen_recibido_m3,
                                'motivo', e.motivo_rechazo)
      FROM rcd.movimiento m
      LEFT JOIN rcd.vehiculo v ON v.id = m.vehiculo_id
      WHERE m.id = ANY (v_ids);
    END IF;
  END IF;
  RETURN NULL;
END $$;

CREATE CONSTRAINT TRIGGER procesar_entrada AFTER INSERT ON movimiento_entrada
DEFERRABLE INITIALLY DEFERRED
FOR EACH ROW EXECUTE FUNCTION trg_procesar_entrada();

-- Registrar una entrada y sus vínculos en una sola llamada (una sola transacción).
-- Es la función que usa la pantalla Entradas (M2).
CREATE OR REPLACE FUNCTION fn_registrar_entrada(
  p_receptor      integer,
  p_usuario       integer,
  p_placa         text,
  p_resultado     text,
  p_lon           double precision,
  p_lat           double precision,
  p_movimientos   uuid[]      DEFAULT '{}',
  p_volumen       numeric     DEFAULT NULL,
  p_tipo          integer     DEFAULT NULL,
  p_foto          text        DEFAULT NULL,
  p_motivo        text        DEFAULT NULL,
  p_peso          numeric     DEFAULT NULL,
  p_precinto      text        DEFAULT NULL,
  p_barrio_origen integer     DEFAULT NULL,
  p_registrada    timestamptz DEFAULT now())
RETURNS bigint LANGUAGE plpgsql AS $$
DECLARE v_id bigint;
BEGIN
  INSERT INTO rcd.entrada (receptor_id, usuario_id, placa, registrada_en, resultado, motivo_rechazo,
                           tipo_rcd_id, volumen_recibido_m3, peso_t, peso_medido, precinto, foto_url,
                           barrio_origen_id, geom_dispositivo)
  VALUES (p_receptor, p_usuario, p_placa, p_registrada, p_resultado, p_motivo,
          p_tipo, p_volumen, p_peso, p_peso IS NOT NULL, p_precinto, p_foto,
          p_barrio_origen, ST_SetSRID(ST_MakePoint(p_lon, p_lat), 4326))
  RETURNING id INTO v_id;

  INSERT INTO rcd.movimiento_entrada (movimiento_id, entrada_id)
  SELECT unnest(p_movimientos), v_id;
  RETURN v_id;
END $$;

-- ---------------------------------------------------------------------
-- R4: sin cierre a las 24 h. Se ejecuta periódicamente (la API la llama cada pocos minutos).
-- ---------------------------------------------------------------------
CREATE OR REPLACE FUNCTION fn_marcar_sin_cierre() RETURNS integer LANGUAGE plpgsql AS $$
DECLARE n integer;
BEGIN
  WITH vencidos AS (
    UPDATE rcd.movimiento m
    SET estado = 'sin_cierre',
        con_agravante = (m.estado = 'rechazado')          -- valor anterior: hubo rechazo
    WHERE m.estado IN ('abierto', 'rechazado')
      AND m.abierto_en < now() - make_interval(hours => rcd.fn_param('horas_sin_cierre')::integer)
    RETURNING m.*)
  INSERT INTO rcd.alerta (empresa_id, tipo, gravedad, movimiento_id, vehiculo_id, geom, detalle)
  SELECT coalesce(v.empresa_origen_id, veh.empresa_id), 'sin_cierre', 'alta', v.id, v.vehiculo_id,
         v.geom_origen,
         jsonb_build_object('codigo', v.codigo, 'placa', v.placa,
                            'horas_abierto', round(extract(epoch FROM now() - v.abierto_en) / 3600),
                            'agravante', v.con_agravante)
  FROM vencidos v
  LEFT JOIN rcd.vehiculo veh ON veh.id = v.vehiculo_id;
  GET DIAGNOSTICS n = ROW_COUNT;
  RETURN n;
END $$;

-- ---------------------------------------------------------------------
-- R5: receptores sugeridos tras un rechazo (los que aceptan el material y no lo han rechazado).
-- Distancia en línea recta; la ruta real por la red vial se calcula con pgRouting en la API.
-- ---------------------------------------------------------------------
CREATE OR REPLACE FUNCTION fn_receptores_sugeridos(p_movimiento uuid, p_limite integer DEFAULT 3)
RETURNS TABLE (receptor_id integer, nombre text, tipo text, distancia_m numeric, usa_plataforma boolean)
LANGUAGE sql STABLE AS $$
  SELECT r.id, r.nombre, r.tipo,
         round(ST_Distance(r.geocerca::geography, m.geom_origen::geography)),
         r.empresa_id IS NOT NULL
  FROM rcd.movimiento m
  JOIN rcd.receptor_acepta ra ON ra.tipo_rcd_id = m.tipo_rcd_id
  JOIN rcd.receptor r         ON r.id = ra.receptor_id
  WHERE m.id = p_movimiento
    AND r.activo
    AND (r.vigente_hasta IS NULL OR r.vigente_hasta >= current_date)
    AND NOT EXISTS (SELECT 1
                    FROM rcd.movimiento_entrada me
                    JOIN rcd.entrada e ON e.id = me.entrada_id
                    WHERE me.movimiento_id = m.id AND e.receptor_id = r.id AND e.resultado = 'rechazada')
  ORDER BY 4
  LIMIT p_limite
$$;

-- ---------------------------------------------------------------------
-- R7: compuerta abierta o movimiento en la carga, en tránsito y fuera de geocercas autorizadas
-- ---------------------------------------------------------------------
CREATE OR REPLACE FUNCTION trg_sensor_compuerta() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
  veh    rcd.vehiculo;
  mov    rcd.movimiento;
  v_zona text;
  v_tol  numeric := rcd.fn_param('tolerancia_geocerca_m');
BEGIN
  IF NEW.tipo NOT IN ('compuerta_abierta', 'movimiento_carga') OR NEW.geom IS NULL THEN
    RETURN NULL;
  END IF;
  SELECT * INTO veh FROM rcd.vehiculo WHERE id = NEW.vehiculo_id;

  -- "En tránsito" = la placa tiene un movimiento abierto
  SELECT * INTO mov FROM rcd.movimiento
  WHERE placa = veh.placa AND estado IN ('abierto', 'rechazado') AND abierto_en <= NEW.registrado_en
  ORDER BY abierto_en DESC LIMIT 1;
  IF NOT FOUND THEN
    RETURN NULL;
  END IF;

  -- Abrir la compuerta en un receptor o en el origen es normal
  IF EXISTS (SELECT 1 FROM rcd.receptor r
             WHERE r.activo AND ST_DWithin(r.geocerca::geography, NEW.geom::geography, v_tol))
     OR ST_DWithin(mov.geom_origen::geography, NEW.geom::geography, rcd.fn_param('radio_origen_m'))
     OR EXISTS (SELECT 1 FROM rcd.obra o
                WHERE o.id = mov.obra_id AND o.geocerca IS NOT NULL
                  AND ST_DWithin(o.geocerca::geography, NEW.geom::geography, v_tol)) THEN
    RETURN NULL;
  END IF;

  SELECT z.tipo INTO v_zona FROM rcd.zona_prohibida z WHERE ST_Intersects(z.geom, NEW.geom) LIMIT 1;

  INSERT INTO rcd.alerta (empresa_id, tipo, gravedad, movimiento_id, vehiculo_id, geom, detalle)
  VALUES (coalesce(veh.empresa_id, mov.empresa_origen_id), 'compuerta_en_transito', 'alta',
          mov.id, veh.id, NEW.geom,
          jsonb_strip_nulls(jsonb_build_object(
            'evento', NEW.tipo, 'hora', NEW.registrado_en, 'placa', veh.placa,
            'zona_prohibida', v_zona, 'video', NEW.video_url,
            'distancia_receptor_m', (SELECT round(min(ST_Distance(r.geocerca::geography, NEW.geom::geography)))
                                     FROM rcd.receptor r WHERE r.activo))));
  RETURN NULL;
END $$;

CREATE TRIGGER sensor_compuerta AFTER INSERT ON evento_sensor
FOR EACH ROW EXECUTE FUNCTION trg_sensor_compuerta();

-- ---------------------------------------------------------------------
-- R6: paradas a partir del rastro GPS (método "islas": puntos consecutivos con velocidad < 3 km/h)
-- ---------------------------------------------------------------------
CREATE OR REPLACE FUNCTION fn_paradas(p_vehiculo integer, p_desde timestamptz, p_hasta timestamptz)
RETURNS TABLE (inicio timestamptz, fin timestamptz, minutos numeric, geom geometry,
               en_geocerca boolean, zona_prohibida text)
LANGUAGE sql STABLE AS $$
  WITH p AS (
    SELECT registrado_en, geom, coalesce(velocidad_kmh, 0) < 3 AS quieto
    FROM rcd.posicion_gps
    WHERE vehiculo_id = p_vehiculo AND registrado_en BETWEEN p_desde AND p_hasta),
  g AS (
    SELECT *, sum(CASE WHEN quieto THEN 0 ELSE 1 END) OVER (ORDER BY registrado_en) AS isla
    FROM p),
  s AS (
    SELECT min(registrado_en) AS inicio, max(registrado_en) AS fin,
           ST_Centroid(ST_Collect(geom)) AS geom
    FROM g WHERE quieto GROUP BY isla)
  SELECT s.inicio, s.fin,
         round(extract(epoch FROM s.fin - s.inicio) / 60.0, 1),
         s.geom,
         EXISTS (SELECT 1 FROM rcd.receptor r
                 WHERE r.activo AND ST_DWithin(r.geocerca::geography, s.geom::geography,
                                               rcd.fn_param('tolerancia_geocerca_m')))
         OR EXISTS (SELECT 1 FROM rcd.obra o
                    WHERE o.estado = 'activa'
                      AND ST_DWithin(coalesce(o.geocerca, o.punto)::geography, s.geom::geography,
                                     rcd.fn_param('radio_origen_m'))),
         (SELECT z.tipo FROM rcd.zona_prohibida z WHERE ST_Intersects(z.geom, s.geom) LIMIT 1)
  FROM s
  WHERE s.fin > s.inicio
$$;

-- Genera alertas por paradas largas de vehículos cargados (con un movimiento en curso)
CREATE OR REPLACE FUNCTION fn_generar_alertas_paradas(p_desde timestamptz DEFAULT now() - interval '1 day')
RETURNS integer LANGUAGE plpgsql AS $$
DECLARE n integer;
BEGIN
  INSERT INTO rcd.alerta (empresa_id, tipo, gravedad, movimiento_id, vehiculo_id, geom, detalle)
  SELECT veh.empresa_id,
         CASE WHEN pr.zona_prohibida IS NOT NULL THEN 'zona_prohibida' ELSE 'parada_sospechosa' END,
         CASE WHEN pr.zona_prohibida IS NOT NULL THEN 'alta' ELSE 'media' END,
         mov.id, veh.id, pr.geom,
         jsonb_strip_nulls(jsonb_build_object('inicio', pr.inicio, 'minutos', pr.minutos,
                                              'placa', veh.placa, 'zona_prohibida', pr.zona_prohibida))
  FROM rcd.vehiculo veh
  CROSS JOIN LATERAL rcd.fn_paradas(veh.id, p_desde, now()) pr
  JOIN LATERAL (
    SELECT m.id FROM rcd.movimiento m
    WHERE m.placa = veh.placa AND m.estado <> 'anulado'
      AND m.abierto_en <= pr.inicio
      AND (m.cerrado_en IS NULL OR m.cerrado_en >= pr.fin)
    ORDER BY m.abierto_en DESC LIMIT 1) mov ON true
  WHERE veh.tiene_gps
    AND NOT pr.en_geocerca
    AND pr.minutos >= rcd.fn_param('parada_sospechosa_min')
    AND NOT EXISTS (SELECT 1 FROM rcd.alerta a
                    WHERE a.vehiculo_id = veh.id
                      AND a.tipo IN ('parada_sospechosa', 'zona_prohibida')
                      AND (a.detalle ->> 'inicio')::timestamptz = pr.inicio);
  GET DIAGNOSTICS n = ROW_COUNT;
  RETURN n;
END $$;

-- ---------------------------------------------------------------------
-- CAPA 3: un arrojo reportado se cruza con movimientos cercanos sin cerrar
-- (es un indicio para priorizar inspecciones, no una prueba)
-- ---------------------------------------------------------------------
CREATE OR REPLACE FUNCTION trg_arrojo_cruzar() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE v_lista jsonb;
BEGIN
  SELECT jsonb_agg(jsonb_build_object(
           'codigo', m.codigo, 'placa', m.placa, 'estado', m.estado,
           'distancia_m', round(ST_Distance(m.geom_origen::geography, NEW.geom::geography)))
         ORDER BY ST_Distance(m.geom_origen::geography, NEW.geom::geography))
  INTO v_lista
  FROM rcd.movimiento m
  WHERE m.estado IN ('abierto', 'rechazado', 'sin_cierre')
    AND m.abierto_en BETWEEN NEW.reportado_en - make_interval(hours => rcd.fn_param('ventana_arrojo_h')::integer)
                         AND NEW.reportado_en
    AND ST_DWithin(m.geom_origen::geography, NEW.geom::geography, rcd.fn_param('radio_arrojo_m'));

  IF v_lista IS NOT NULL THEN
    INSERT INTO rcd.alerta (empresa_id, tipo, gravedad, arrojo_id, geom, detalle)
    VALUES (NEW.empresa_id, 'arrojo_cercano', 'media', NEW.id, NEW.geom,
            jsonb_build_object('movimientos', v_lista));
  END IF;
  RETURN NULL;
END $$;

CREATE TRIGGER arrojo_cruzar AFTER INSERT ON punto_arrojo
FOR EACH ROW EXECUTE FUNCTION trg_arrojo_cruzar();
