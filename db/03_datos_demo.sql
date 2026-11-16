-- =====================================================================
-- Trazabilidad geográfica de RCD — Cali
-- 03_datos_demo.sql : datos de DEMOSTRACIÓN
--
-- ⚠ Todo es ficticio: empresas, personas, receptores y polígonos.
--   · Comunas y barrios son rectángulos de prueba: reemplazar con la capa de la IDESC.
--   · Las horas son relativas a now(): los escenarios siempre se ven "recientes".
--
-- Escenarios (cada uno pasa por los triggers, como en la vida real):
--   E1 Doña Marta + obra → Jairo (XYZ123) → Planta Sur ............ cerrado ✓ (peso estimado)
--   E2 Obra → ABC456 → Punto Limpio, llegan 4 de 6 m³ ............... cerrado con faltante ⚠
--   E3 Particular → XYZ123 → Planta Sur rechaza (mezcla con basura) . rechazado (sigue abierto)
--   E4 Rechazado hace 29 h y nadie lo recibió ...................... sin cierre ✕ con agravante
--   E5 Abierto hace 26 h ............................................ sin cierre ✕
--   E6 ABC456 en tránsito: se detiene 14 min sobre el canal y abre la compuerta → 2 alertas altas
--   E7 KLM901 (gestor integrado) cierra en su propia planta con GPS dentro ... cerrado ✓
--   E8 Arrojo reportado cerca de movimientos sin cerrar ............ alerta arrojo_cercano
--   E9 Camión sin movimiento abierto ................................ entrada sin origen
--   E10 El admin corrige la ubicación de un movimiento .............. evento ubicacion_corregida
-- =====================================================================
SET search_path = rcd, public;

-- ---------------------------------------------------------------------
-- Referencia
-- ---------------------------------------------------------------------
INSERT INTO comuna (id, nombre, geom) VALUES
  (1, 'Comuna Norte (demo)',   ST_Multi(ST_MakeEnvelope(-76.56, 3.45, -76.47, 3.50, 4326))),
  (2, 'Comuna Oriente (demo)', ST_Multi(ST_MakeEnvelope(-76.56, 3.40, -76.47, 3.45, 4326))),
  (3, 'Comuna Sur (demo)',     ST_Multi(ST_MakeEnvelope(-76.56, 3.33, -76.47, 3.40, 4326)));

INSERT INTO barrio (id, nombre, comuna_id, geom) VALUES
  (101, 'Norte A (demo)',   1, ST_Multi(ST_MakeEnvelope(-76.560, 3.45, -76.515, 3.50, 4326))),
  (102, 'Norte B (demo)',   1, ST_Multi(ST_MakeEnvelope(-76.515, 3.45, -76.470, 3.50, 4326))),
  (201, 'Oriente A (demo)', 2, ST_Multi(ST_MakeEnvelope(-76.560, 3.40, -76.515, 3.45, 4326))),
  (202, 'Oriente B (demo)', 2, ST_Multi(ST_MakeEnvelope(-76.515, 3.40, -76.470, 3.45, 4326))),
  (301, 'Sur A (demo)',     3, ST_Multi(ST_MakeEnvelope(-76.560, 3.33, -76.515, 3.40, 4326))),
  (302, 'Sur B (demo)',     3, ST_Multi(ST_MakeEnvelope(-76.515, 3.33, -76.470, 3.40, 4326)));

-- Catálogo según la clasificación de la Res. 0472/2017 (verificar contra el texto vigente).
-- Densidades: NSR-10, Título B, Tabla B.3.2-1 "Masas de los materiales" (kg/m³ ÷ 1000), como permite la
-- Res. 0472, art. 19, par. 1. Son densidades de material SÓLIDO: sobreestiman el peso del escombro suelto
-- (esponjamiento). Cada gestor puede reemplazarlas por la densidad medida en una muestra.
INSERT INTO tipo_rcd (codigo, nombre, categoria, grupo, densidad_t_m3) VALUES
  ('EXC', 'Productos de excavación y sobrantes de adecuación de terreno', 'aprovechable',    'Excavación',      1.60),  -- Arena y grava seca suelta
  ('CIM', 'Productos de cimentaciones y pilotajes',                       'aprovechable',    'Cimentaciones',   1.75),  -- Arcilla húmeda
  ('PET', 'Pétreos: concreto, ladrillo, bloque, cerámica, mezclas',       'aprovechable',    'Pétreos',         2.15),  -- Mampostería de concreto
  ('MET', 'Metales (chatarra)',                                           'aprovechable',    'No pétreos',      7.80),  -- Acero
  ('MAD', 'Madera',                                                       'aprovechable',    'No pétreos',      0.60),  -- Madera seca (450–750)
  ('VID', 'Vidrio',                                                       'aprovechable',    'No pétreos',      2.60),  -- Vidrio
  ('PLA', 'Plásticos, cauchos y drywall',                                 'aprovechable',    'No pétreos',      0.80),  -- Yeso en tableros para muros
  ('NAP', 'No aprovechable (mezcla no separable)',                        'no_aprovechable', 'No aprovechable', 1.60);  -- Arcilla y grava seca

-- ---------------------------------------------------------------------
-- Empresas y usuarios (el hash real lo crea la API; aquí es un marcador)
-- ---------------------------------------------------------------------
INSERT INTO empresa (id, nombre, nit, pin_dagma) VALUES
  (1, 'Planta Sur SAS (demo)',          '900000001', 'DEMO-E001'),
  (2, 'Reciclados del Valle (demo)',    '900000002', 'DEMO-E002'),
  (3, 'Transportes y Obras (demo)',     '900000003', 'DEMO-E003');

INSERT INTO usuario (id, empresa_id, nombre, email, password_hash, rol, perfil) VALUES
  (1, 1, 'Admin Planta Sur',      'admin@plantasur.demo',   'DEMO', 'admin',   NULL),
  (2, 1, 'Portero Planta Sur',    'porteria@plantasur.demo','DEMO', 'usuario', 'portero'),
  (3, 2, 'Admin Reciclados',      'admin@reciclados.demo',  'DEMO', 'admin',   NULL),
  (4, 2, 'Portero Punto Limpio',  'porteria@reciclados.demo','DEMO','usuario', 'portero'),
  (5, 3, 'Admin Transportes',     'admin@transportes.demo', 'DEMO', 'admin',   NULL),
  (6, 3, 'Conductor Transportes', 'conductor@transportes.demo','DEMO','usuario','conductor'),
  (7, 3, 'Inspector Transportes', 'inspector@transportes.demo','DEMO','usuario','inspector');

-- ---------------------------------------------------------------------
-- Capa 1: norma (receptores con geocerca y zonas prohibidas)
-- ---------------------------------------------------------------------
INSERT INTO receptor (id, empresa_id, nombre, tipo, pin_dagma, vigente_hasta, geocerca) VALUES
  (1, 1,    'Planta Sur (demo)',                  'planta_aprovechamiento', 'DEMO-R001', NULL,
       ST_Multi(ST_MakeEnvelope(-76.5365, 3.3435, -76.5335, 3.3465, 4326))),
  (2, 2,    'Punto Limpio Oriente (demo)',        'punto_limpio',           'DEMO-R002', NULL,
       ST_Multi(ST_MakeEnvelope(-76.4910, 3.4190, -76.4890, 3.4210, 4326))),
  (3, NULL, 'Estación de transferencia (demo)',   'estacion_transferencia', 'DEMO-R003', NULL,
       ST_Multi(ST_MakeEnvelope(-76.5465, 3.4035, -76.5435, 3.4065, 4326))),
  (4, NULL, 'Sitio de disposición final (demo)',  'disposicion_final',      'DEMO-R004', NULL,
       ST_Multi(ST_MakeEnvelope(-76.4030, 3.4080, -76.3970, 3.4120, 4326))),
  (5, NULL, 'Planta con inscripción vencida (demo)', 'planta_aprovechamiento', 'DEMO-R005', DATE '2025-12-31',
       ST_Multi(ST_MakeEnvelope(-76.5210, 3.3600, -76.5190, 3.3620, 4326)));
SELECT setval('receptor_id_seq', 5);

INSERT INTO receptor_acepta (receptor_id, tipo_rcd_id)
SELECT 1, id FROM tipo_rcd WHERE codigo IN ('EXC', 'CIM', 'PET')
UNION ALL SELECT 2, id FROM tipo_rcd WHERE categoria = 'aprovechable'
UNION ALL SELECT 3, id FROM tipo_rcd WHERE categoria = 'aprovechable'
UNION ALL SELECT 4, id FROM tipo_rcd
UNION ALL SELECT 5, id FROM tipo_rcd WHERE codigo = 'PET';

INSERT INTO zona_prohibida (tipo, nombre, fuente, franja_m, geom) VALUES
  ('canal',  'Canal de aguas lluvias (demo)', 'digitalizado', 30,
     ST_Multi(ST_Buffer(ST_SetSRID(ST_MakeLine(ST_MakePoint(-76.50, 3.40), ST_MakePoint(-76.50, 3.45)), 4326)::geography, 30)::geometry)),
  ('parque', 'Parque (demo)', 'digitalizado', NULL,
     ST_Multi(ST_MakeEnvelope(-76.525, 3.455, -76.520, 3.460, 4326)));

-- ---------------------------------------------------------------------
-- Transporte y obras
-- ---------------------------------------------------------------------
INSERT INTO transportador (id, empresa_id, nombre, documento, pin_dagma) VALUES
  (1, NULL, 'Jairo R. (demo, chanero independiente)', 'DEMO-1001', 'DEMO-T001'),
  (2, 3,    'Conductor Transportes (demo)',           'DEMO-1002', 'DEMO-T002'),
  (3, 1,    'Conductor Planta Sur (demo)',            'DEMO-1003', 'DEMO-T003');

INSERT INTO vehiculo (id, placa, empresa_id, transportador_id, tipo, capacidad_m3, tiene_gps, tiene_camara) VALUES
  (1, 'xyz-123', NULL, 1, 'volqueta pequeña', 3, false, false),
  (2, 'ABC 456', 3,    2, 'volqueta',         6, true,  true),
  (3, 'KLM901',  1,    3, 'volqueta',         8, true,  false);

INSERT INTO obra (id, empresa_id, nombre, generador, tipo_generador, licencia, area_m2, punto, geocerca) VALUES
  (1, 3, 'Torres del Lili (demo)', 'Constructora Altos (demo)',  'grande', 'DEMO-LIC-1', 8000,
      ST_SetSRID(ST_MakePoint(-76.530, 3.370), 4326),
      ST_Multi(ST_MakeEnvelope(-76.531, 3.369, -76.529, 3.371, 4326))),
  (2, 3, 'Edificio Centro (demo)', 'Constructora Altos (demo)',  'grande', 'DEMO-LIC-2', 5200,
      ST_SetSRID(ST_MakePoint(-76.520, 3.430), 4326),
      ST_Multi(ST_MakeEnvelope(-76.521, 3.429, -76.519, 3.431, 4326)));

SELECT setval('empresa_id_seq', 3), setval('usuario_id_seq', 7), setval('transportador_id_seq', 3),
       setval('vehiculo_id_seq', 3), setval('obra_id_seq', 2);

-- ---------------------------------------------------------------------
-- Movimientos (se abren como lo haría el enlace o la app)
-- ---------------------------------------------------------------------
INSERT INTO movimiento (codigo, placa, origen_tipo, obra_id, empresa_origen_id, abierto_por_usuario_id,
                        generador_celular, acepta_datos, mecanismo_ingreso, direccion_texto,
                        geom_origen, tipo_rcd_id, volumen_declarado_m3, foto_carga_url, abierto_en)
VALUES
  -- E1: Doña Marta (particular) y una obra, mismo camión de Jairo
  ('RCD-DEMO01', 'XYZ-123', 'particular', NULL, NULL, NULL, '3000000001', true, 'direccion', 'Dirección demo Sur A',
     ST_SetSRID(ST_MakePoint(-76.528, 3.372), 4326), (SELECT id FROM tipo_rcd WHERE codigo='PET'), 2, 'demo/e1a.jpg', now() - interval '5 hours'),
  ('RCD-DEMO02', 'XYZ123',  'obra', 1, 3, 7, NULL, false, 'gps', NULL,
     ST_SetSRID(ST_MakePoint(-76.530, 3.370), 4326), (SELECT id FROM tipo_rcd WHERE codigo='PET'), 3, 'demo/e1b.jpg', now() - interval '4 hours'),
  -- E2: obra con camión de empresa, llegará con faltante
  ('RCD-DEMO03', 'ABC456',  'obra', 2, 3, 6, NULL, false, 'gps', NULL,
     ST_SetSRID(ST_MakePoint(-76.520, 3.430), 4326), (SELECT id FROM tipo_rcd WHERE codigo='PET'), 6, 'demo/e2.jpg', now() - interval '6 hours'),
  -- E3: particular, será rechazado por mezcla con basura
  ('RCD-DEMO04', 'XYZ123',  'particular', NULL, NULL, NULL, '3000000002', true, 'mapa', NULL,
     ST_SetSRID(ST_MakePoint(-76.525, 3.375), 4326), (SELECT id FROM tipo_rcd WHERE codigo='PET'), 2, 'demo/e3.jpg', now() - interval '3 hours'),
  -- E4: particular, rechazado hace 29 h y nadie lo recibió
  ('RCD-DEMO05', 'XYZ123',  'particular', NULL, NULL, NULL, '3000000003', true, 'gps', NULL,
     ST_SetSRID(ST_MakePoint(-76.495, 3.425), 4326), (SELECT id FROM tipo_rcd WHERE codigo='PET'), 1, 'demo/e4.jpg', now() - interval '30 hours'),
  -- E5: particular, abierto hace 26 h
  ('RCD-DEMO06', 'XYZ123',  'particular', NULL, NULL, NULL, '3000000004', true, 'direccion', 'Dirección demo Oriente B',
     ST_SetSRID(ST_MakePoint(-76.505, 3.415), 4326), (SELECT id FROM tipo_rcd WHERE codigo='MAD'), 1, 'demo/e5.jpg', now() - interval '26 hours'),
  -- E6: obra, ABC456 en tránsito ahora mismo
  ('RCD-DEMO07', 'ABC456',  'obra', 2, 3, 6, NULL, false, 'gps', NULL,
     ST_SetSRID(ST_MakePoint(-76.520, 3.430), 4326), (SELECT id FROM tipo_rcd WHERE codigo='PET'), 6, 'demo/e6.jpg', now() - interval '60 minutes'),
  -- E7: gestor integrado, camión propio de Planta Sur
  ('RCD-DEMO08', 'KLM901',  'obra', 1, 1, 1, NULL, false, 'gps', NULL,
     ST_SetSRID(ST_MakePoint(-76.530, 3.370), 4326), (SELECT id FROM tipo_rcd WHERE codigo='PET'), 8, 'demo/e7.jpg', now() - interval '90 minutes');

-- ---------------------------------------------------------------------
-- GPS y sensores (simulados)
-- ---------------------------------------------------------------------
-- E6: ABC456 sale de la obra 2, se detiene 14 min sobre el canal y sigue hacia el Punto Limpio
INSERT INTO posicion_gps (vehiculo_id, registrado_en, geom, velocidad_kmh)
SELECT 2, now() - interval '60 minutes' + make_interval(mins => i),
       CASE WHEN i <= 20 THEN ST_SetSRID(ST_MakePoint(-76.520 + 0.0199 * i / 20, 3.430 - 0.0067 * i / 20), 4326)
            WHEN i <= 36 THEN ST_SetSRID(ST_MakePoint(-76.5001, 3.4233), 4326)
            ELSE ST_SetSRID(ST_MakePoint(-76.5001 + 0.0101 * (i - 36) / 14, 3.4233 - 0.0033 * (i - 36) / 14), 4326)
       END,
       CASE WHEN i > 20 AND i <= 36 THEN 0 ELSE 25 END
FROM generate_series(0, 50, 2) AS i;

INSERT INTO evento_sensor (vehiculo_id, tipo, registrado_en, geom, video_url) VALUES
  (2, 'motor_encendido',   now() - interval '62 minutes', ST_SetSRID(ST_MakePoint(-76.520, 3.430), 4326), NULL),
  (2, 'compuerta_abierta', now() - interval '30 minutes', ST_SetSRID(ST_MakePoint(-76.5001, 3.4233), 4326), 'demo/video_abc456.mp4');

-- E7: KLM901 dentro de Planta Sur cuando el portero cierra
INSERT INTO posicion_gps (vehiculo_id, registrado_en, geom, velocidad_kmh)
SELECT 3, now() - interval '35 minutes' + make_interval(mins => i),
       ST_SetSRID(ST_MakePoint(-76.5350, 3.3450), 4326), 0
FROM generate_series(0, 10, 2) AS i;

-- ---------------------------------------------------------------------
-- Entradas en los receptores (pantalla M2). Cada llamada es una transacción.
-- ---------------------------------------------------------------------
-- E1: Jairo entrega 2 movimientos juntos (2 + 3 m³) en Planta Sur → cerrado, peso estimado
SELECT fn_registrar_entrada(
  p_receptor => 1, p_usuario => 2, p_placa => 'xyz 123', p_resultado => 'recibida',
  p_lon => -76.5352, p_lat => 3.3451,
  p_movimientos => ARRAY(SELECT id FROM movimiento WHERE codigo IN ('RCD-DEMO01', 'RCD-DEMO02')),
  p_volumen => 5, p_tipo => (SELECT id FROM tipo_rcd WHERE codigo='PET'),
  p_foto => 'demo/llegada_e1.jpg', p_registrada => now() - interval '2 hours');

-- E2: llegan 4 de 6 m³ al Punto Limpio → cerrado con faltante
SELECT fn_registrar_entrada(
  p_receptor => 2, p_usuario => 4, p_placa => 'ABC456', p_resultado => 'recibida',
  p_lon => -76.4900, p_lat => 3.4200,
  p_movimientos => ARRAY(SELECT id FROM movimiento WHERE codigo = 'RCD-DEMO03'),
  p_volumen => 4, p_tipo => (SELECT id FROM tipo_rcd WHERE codigo='PET'),
  p_foto => 'demo/llegada_e2.jpg', p_registrada => now() - interval '5 hours');

-- E3: Planta Sur rechaza por mezcla con basura → sigue abierto como "rechazado"
SELECT fn_registrar_entrada(
  p_receptor => 1, p_usuario => 2, p_placa => 'XYZ123', p_resultado => 'rechazada',
  p_lon => -76.5350, p_lat => 3.3450,
  p_movimientos => ARRAY(SELECT id FROM movimiento WHERE codigo = 'RCD-DEMO04'),
  p_motivo => 'mezcla_basura', p_foto => 'demo/rechazo_e3.jpg',
  p_registrada => now() - interval '90 minutes');

-- E4: el Punto Limpio lo rechazó hace 29 h
SELECT fn_registrar_entrada(
  p_receptor => 2, p_usuario => 4, p_placa => 'XYZ123', p_resultado => 'rechazada',
  p_lon => -76.4901, p_lat => 3.4201,
  p_movimientos => ARRAY(SELECT id FROM movimiento WHERE codigo = 'RCD-DEMO05'),
  p_motivo => 'peligrosos', p_foto => 'demo/rechazo_e4.jpg',
  p_registrada => now() - interval '29 hours');

-- E7: gestor integrado; su GPS está dentro de la planta → cerrado, peso medido en báscula
SELECT fn_registrar_entrada(
  p_receptor => 1, p_usuario => 2, p_placa => 'KLM901', p_resultado => 'recibida',
  p_lon => -76.5349, p_lat => 3.3449,
  p_movimientos => ARRAY(SELECT id FROM movimiento WHERE codigo = 'RCD-DEMO08'),
  p_volumen => 8, p_peso => 11.6, p_tipo => (SELECT id FROM tipo_rcd WHERE codigo='PET'),
  p_foto => 'demo/llegada_e7.jpg', p_registrada => now() - interval '28 minutes');

-- E9: camión sin movimiento abierto → entrada sin origen
SELECT fn_registrar_entrada(
  p_receptor => 2, p_usuario => 4, p_placa => 'RTY-332', p_resultado => 'sin_origen',
  p_lon => -76.4899, p_lat => 3.4199,
  p_volumen => 3, p_tipo => (SELECT id FROM tipo_rcd WHERE codigo='PET'),
  p_barrio_origen => 202, p_foto => 'demo/llegada_e9.jpg', p_registrada => now() - interval '3 hours');

-- ---------------------------------------------------------------------
-- Procesos periódicos (en producción los ejecuta la API cada pocos minutos)
-- ---------------------------------------------------------------------
SELECT fn_marcar_sin_cierre()                              AS movimientos_sin_cierre;   -- E4, E5
SELECT fn_generar_alertas_paradas(now() - interval '2 hours') AS alertas_por_paradas;  -- E6

-- E8: el inspector reporta un arrojo cerca del origen de E5
INSERT INTO punto_arrojo (empresa_id, reportado_por, mecanismo_ingreso, geom, tipo_rcd_id,
                          volumen_estimado_m3, foto_url, reportado_en)
VALUES (3, 7, 'gps', ST_SetSRID(ST_MakePoint(-76.502, 3.418), 4326),
        (SELECT id FROM tipo_rcd WHERE codigo='MAD'), 1, 'demo/arrojo_e8.jpg', now() - interval '20 hours');

-- E10: el admin de Transportes corrige la ubicación de origen de E6 (quedó auditado)
BEGIN;
SET LOCAL rcd.usuario_id = '5';
UPDATE movimiento SET geom_origen = ST_SetSRID(ST_MakePoint(-76.5203, 3.4302), 4326)
WHERE codigo = 'RCD-DEMO07';
COMMIT;
