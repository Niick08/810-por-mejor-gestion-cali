-- =====================================================================
-- Pruebas de las reglas (correr DESPUÉS de 01, 02 y 03).
-- Todo corre dentro de una transacción que se deshace al final: no ensucia los datos.
-- Cada prueba imprime "OK: ..." o detiene el script con "FALLA: ...".
-- =====================================================================
\set ON_ERROR_STOP on
SET search_path = rcd, public;
SET client_min_messages = notice;
BEGIN;

CREATE FUNCTION pg_temp.ok(p_condicion boolean, p_msg text) RETURNS void LANGUAGE plpgsql AS $$
BEGIN
  IF p_condicion IS TRUE THEN RAISE NOTICE 'OK: %', p_msg;
  ELSE RAISE EXCEPTION 'FALLA: %', p_msg; END IF;
END $$;

-- Ejecuta una sentencia que DEBE fallar con un mensaje que contenga p_esperado
CREATE FUNCTION pg_temp.debe_fallar(p_sql text, p_esperado text, p_msg text) RETURNS void LANGUAGE plpgsql AS $$
BEGIN
  BEGIN
    EXECUTE p_sql;
    EXECUTE 'SET CONSTRAINTS ALL IMMEDIATE';     -- dispara los triggers diferidos
  EXCEPTION WHEN OTHERS THEN
    IF position(p_esperado IN SQLERRM) > 0 THEN
      RAISE NOTICE 'OK: % → bloqueado ("%")', p_msg, SQLERRM;
      RETURN;
    END IF;
    RAISE EXCEPTION 'FALLA: % → falló, pero con otro error: %', p_msg, SQLERRM;
  END;
  RAISE EXCEPTION 'FALLA: % → NO fue bloqueado', p_msg;
END $$;

CREATE FUNCTION pg_temp.estado(p_codigo text) RETURNS text LANGUAGE sql AS
$$ SELECT estado FROM rcd.movimiento WHERE codigo = p_codigo $$;

-- ---------------------------------------------------------------------
-- Escenarios de la demo
-- ---------------------------------------------------------------------
SELECT pg_temp.ok(pg_temp.estado('RCD-DEMO01') = 'cerrado' AND pg_temp.estado('RCD-DEMO02') = 'cerrado',
  'E1 una entrada cierra 2 movimientos de la misma placa');
SELECT pg_temp.ok((SELECT peso_t = 10.75 AND NOT peso_medido FROM entrada WHERE placa = 'XYZ123' AND resultado = 'recibida'),
  'R8 peso estimado: 5 m³ × 2,15 t/m³ (NSR-10) = 10,75 t');
SELECT pg_temp.ok((SELECT vehiculo_id = 1 AND transportador_id = 1 AND barrio_id = 301 FROM movimiento WHERE codigo = 'RCD-DEMO01'),
  'placa "XYZ-123" normalizada y enlazada a vehículo, transportador y barrio (relación espacial)');
SELECT pg_temp.ok(pg_temp.estado('RCD-DEMO03') = 'cerrado_faltante'
  AND EXISTS (SELECT 1 FROM alerta a JOIN movimiento m ON m.id = a.movimiento_id
              WHERE m.codigo = 'RCD-DEMO03' AND a.tipo = 'faltante' AND (a.detalle->>'faltante_m3')::numeric = 2),
  'R3 E2 faltante de 2 m³ con alerta');
SELECT pg_temp.ok(pg_temp.estado('RCD-DEMO04') = 'rechazado',
  'R5 E3 rechazado sigue abierto');
SELECT pg_temp.ok((SELECT count(*) = 3 AND bool_and(nombre <> 'Planta Sur (demo)') AND bool_and(nombre NOT LIKE '%vencida%')
                   FROM fn_receptores_sugeridos((SELECT id FROM movimiento WHERE codigo = 'RCD-DEMO04'))),
  'R5 receptores sugeridos: aceptan pétreos, excluyen al que rechazó y al de inscripción vencida');
SELECT pg_temp.ok((SELECT estado = 'sin_cierre' AND con_agravante FROM movimiento WHERE codigo = 'RCD-DEMO05'),
  'R4 E4 sin cierre CON agravante (había sido rechazado)');
SELECT pg_temp.ok((SELECT estado = 'sin_cierre' AND NOT con_agravante FROM movimiento WHERE codigo = 'RCD-DEMO06'),
  'R4 E5 sin cierre sin agravante');
SELECT pg_temp.ok((SELECT count(*) = 2 FROM alerta WHERE tipo = 'sin_cierre' AND gravedad = 'alta'),
  'R4 dos alertas altas de sin cierre');
SELECT pg_temp.ok(EXISTS (SELECT 1 FROM alerta WHERE tipo = 'compuerta_en_transito' AND detalle->>'zona_prohibida' = 'canal'),
  'R7 E6 compuerta abierta en tránsito, sobre el canal');
SELECT pg_temp.ok(EXISTS (SELECT 1 FROM alerta WHERE tipo = 'zona_prohibida' AND (detalle->>'minutos')::numeric >= 10),
  'R6 E6 parada de más de 10 min en zona prohibida');
SELECT pg_temp.ok(pg_temp.estado('RCD-DEMO08') = 'cerrado'
  AND (SELECT peso_medido FROM entrada WHERE placa = 'KLM901'),
  'R2 E7 gestor integrado cierra con GPS dentro de su planta (peso medido)');
SELECT pg_temp.ok(EXISTS (SELECT 1 FROM alerta WHERE tipo = 'arrojo_cercano'
                          AND jsonb_array_length(detalle->'movimientos') >= 1),
  'Capa 3 E8 arrojo relacionado con movimientos cercanos sin cerrar');
SELECT pg_temp.ok(EXISTS (SELECT 1 FROM entrada WHERE resultado = 'sin_origen' AND placa = 'RTY332'),
  'E9 entrada sin origen registrada');
SELECT pg_temp.ok(EXISTS (SELECT 1 FROM movimiento_evento ev JOIN movimiento m ON m.id = ev.movimiento_id
                          WHERE m.codigo = 'RCD-DEMO07' AND ev.tipo = 'ubicacion_corregida' AND ev.usuario_id = 5),
  'E10 corrección de ubicación auditada con el usuario que la hizo');
SELECT pg_temp.ok((SELECT array_agg(ev.tipo ORDER BY ev.ocurrido_en, ev.id) = ARRAY['abierto', 'cerrado']
                   FROM movimiento_evento ev JOIN movimiento m ON m.id = ev.movimiento_id WHERE m.codigo = 'RCD-DEMO01'),
  'Línea de tiempo de E1: abierto → cerrado');
SELECT pg_temp.ok((SELECT count(*) = 3 FROM v_movimientos_abiertos WHERE placa = 'XYZ123'),
  'Vista común: XYZ123 tiene 3 movimientos por cerrar (1 rechazado + 2 sin cierre)');
SELECT pg_temp.ok((SELECT count(*) = 6 FROM v_capa_normativa),
  'Capa normativa: 4 receptores vigentes + 2 zonas prohibidas (la vencida no aparece)');

-- ---------------------------------------------------------------------
-- Trampas que deben ser bloqueadas
-- ---------------------------------------------------------------------
SELECT pg_temp.debe_fallar(
  $q$ SELECT rcd.fn_registrar_entrada(p_receptor => 1, p_usuario => 2, p_placa => 'XYZ123', p_resultado => 'recibida',
        p_lon => -76.60, p_lat => 3.40, p_movimientos => ARRAY(SELECT id FROM rcd.movimiento WHERE codigo = 'RCD-DEMO04'),
        p_volumen => 2, p_tipo => 3) $q$,
  'de la geocerca', 'R1 cerrar desde fuera de la planta');

SELECT pg_temp.debe_fallar(
  $q$ SELECT rcd.fn_registrar_entrada(p_receptor => 1, p_usuario => 2, p_placa => 'ABC456', p_resultado => 'recibida',
        p_lon => -76.535, p_lat => 3.345, p_movimientos => ARRAY(SELECT id FROM rcd.movimiento WHERE codigo = 'RCD-DEMO04'),
        p_volumen => 2, p_tipo => 3) $q$,
  'no de ABC456', 'Cerrar un movimiento con otra placa');

SELECT pg_temp.debe_fallar(
  $q$ SELECT rcd.fn_registrar_entrada(p_receptor => 1, p_usuario => 4, p_placa => 'XYZ123', p_resultado => 'recibida',
        p_lon => -76.535, p_lat => 3.345, p_movimientos => ARRAY(SELECT id FROM rcd.movimiento WHERE codigo = 'RCD-DEMO04'),
        p_volumen => 2, p_tipo => 3) $q$,
  'no es portero', 'Portero de otra empresa cerrando en Planta Sur');

SELECT pg_temp.debe_fallar(
  $q$ SELECT rcd.fn_registrar_entrada(p_receptor => 3, p_usuario => 2, p_placa => 'XYZ123', p_resultado => 'recibida',
        p_lon => -76.545, p_lat => 3.405, p_volumen => 2, p_tipo => 3) $q$,
  'no opera en la plataforma', 'Registrar entradas en un receptor que no usa la plataforma');

SELECT pg_temp.debe_fallar(
  $q$ UPDATE rcd.movimiento SET estado = 'abierto' WHERE codigo = 'RCD-DEMO01' $q$,
  'no puede cambiar de estado', 'Reabrir un movimiento cerrado');

-- Gestor integrado sin GPS en la planta: nuevo movimiento de KLM901 y cierre sin posición reciente
INSERT INTO movimiento (codigo, placa, origen_tipo, obra_id, empresa_origen_id, mecanismo_ingreso,
                        geom_origen, tipo_rcd_id, volumen_declarado_m3, foto_carga_url)
VALUES ('RCD-TEST-R2', 'KLM901', 'obra', 1, 1, 'gps', ST_SetSRID(ST_MakePoint(-76.53, 3.37), 4326), 3, 8, 't.jpg');
SELECT pg_temp.debe_fallar(
  $q$ SELECT rcd.fn_registrar_entrada(p_receptor => 1, p_usuario => 2, p_placa => 'KLM901', p_resultado => 'recibida',
        p_lon => -76.535, p_lat => 3.345, p_movimientos => ARRAY(SELECT id FROM rcd.movimiento WHERE codigo = 'RCD-TEST-R2'),
        p_volumen => 8, p_tipo => 3, p_registrada => now() + interval '3 hours') $q$,
  'no hay posición GPS', 'R2 gestor integrado cerrando sin GPS dentro de su planta');

-- ---------------------------------------------------------------------
-- Cierre tardío: E5 (sin cierre) llega al Punto Limpio → cerrado, con evento "cierre tardío"
-- ---------------------------------------------------------------------
SELECT rcd.fn_registrar_entrada(p_receptor => 2, p_usuario => 4, p_placa => 'XYZ123', p_resultado => 'recibida',
  p_lon => -76.49, p_lat => 3.42, p_movimientos => ARRAY(SELECT id FROM rcd.movimiento WHERE codigo = 'RCD-DEMO06'),
  p_volumen => 1, p_tipo => 5);
SET CONSTRAINTS ALL IMMEDIATE;
SELECT pg_temp.ok(pg_temp.estado('RCD-DEMO06') = 'cerrado'
  AND EXISTS (SELECT 1 FROM movimiento_evento ev JOIN movimiento m ON m.id = ev.movimiento_id
              WHERE m.codigo = 'RCD-DEMO06' AND ev.tipo = 'cerrado' AND (ev.detalle->>'cierre_tardio')::boolean),
  'Cierre tardío de un movimiento sin cierre, marcado en la línea de tiempo');

ROLLBACK;
\echo '=== TODAS LAS PRUEBAS PASARON ==='
