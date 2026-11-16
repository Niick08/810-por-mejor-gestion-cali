-- =====================================================================
-- Trazabilidad geográfica de RCD — Cali
-- 04_funciones_api.sql : consultas de apoyo que usa la API
-- =====================================================================
SET search_path = rcd, public;

-- Movimientos que le corresponden a una empresa (su espacio privado, D3):
-- los que abrió, los de sus vehículos y los que entraron a sus receptores.
CREATE OR REPLACE FUNCTION fn_movimientos_empresa(p_empresa integer)
RETURNS SETOF movimiento LANGUAGE sql STABLE AS $$
  SELECT m.*
  FROM rcd.movimiento m
  LEFT JOIN rcd.vehiculo v ON v.id = m.vehiculo_id
  WHERE m.empresa_origen_id = p_empresa
     OR v.empresa_id = p_empresa
     OR EXISTS (SELECT 1
                FROM rcd.movimiento_entrada me
                JOIN rcd.entrada  e ON e.id = me.entrada_id
                JOIN rcd.receptor r ON r.id = e.receptor_id
                WHERE me.movimiento_id = m.id AND r.empresa_id = p_empresa)
$$;

-- Receptor donde se cerró un movimiento (la última entrada que lo recibió)
CREATE OR REPLACE FUNCTION fn_receptor_cierre(p_movimiento uuid)
RETURNS TABLE (receptor_id integer, nombre text, tipo text, pin_dagma text, geocerca geometry,
               entrada_id bigint, registrada_en timestamptz, volumen_recibido_m3 numeric,
               peso_t numeric, peso_medido boolean)
LANGUAGE sql STABLE AS $$
  SELECT r.id, r.nombre, r.tipo, r.pin_dagma, r.geocerca,
         e.id, e.registrada_en, e.volumen_recibido_m3, e.peso_t, e.peso_medido
  FROM rcd.movimiento_entrada me
  JOIN rcd.entrada  e ON e.id = me.entrada_id
  JOIN rcd.receptor r ON r.id = e.receptor_id
  WHERE me.movimiento_id = p_movimiento AND e.resultado IN ('recibida', 'parcial')
  ORDER BY e.registrada_en DESC
  LIMIT 1
$$;

-- Avance de la meta de aprovechamiento por obra (Res. 0472, art. 19).
-- · En peso: volumen declarado × densidad del tipo de material.
-- · No cuentan los productos de excavación (EXC), como indica el art. 19.
-- · Cuenta como aprovechado el material aprovechable cerrado en una planta de
--   aprovechamiento o en un punto limpio.
CREATE OR REPLACE FUNCTION fn_aprovechamiento_obras(p_empresa integer)
RETURNS TABLE (obra_id integer, obra text, tipo_generador text, generado_t numeric,
               aprovechado_t numeric, porcentaje numeric, meta_pct numeric, falta_t numeric)
LANGUAGE sql STABLE AS $$
  WITH base AS (
    SELECT o.id, o.nombre, o.tipo_generador,
           m.volumen_declarado_m3 * t.densidad_t_m3 AS peso_t,
           (m.estado IN ('cerrado', 'cerrado_faltante')
            AND t.categoria = 'aprovechable'
            AND rc.tipo IN ('planta_aprovechamiento', 'punto_limpio')) AS aprovechado
    FROM rcd.obra o
    JOIN rcd.movimiento m ON m.obra_id = o.id AND m.estado <> 'anulado'
    JOIN rcd.tipo_rcd t   ON t.id = m.tipo_rcd_id AND t.codigo <> 'EXC'
    LEFT JOIN LATERAL rcd.fn_receptor_cierre(m.id) rc ON true
    WHERE o.empresa_id = p_empresa)
  SELECT id, nombre, tipo_generador,
         round(sum(peso_t), 2),
         round(coalesce(sum(peso_t) FILTER (WHERE aprovechado), 0), 2),
         round(100 * coalesce(sum(peso_t) FILTER (WHERE aprovechado), 0) / nullif(sum(peso_t), 0), 1),
         rcd.fn_param('meta_aprovechamiento_pct'),
         round(greatest(rcd.fn_param('meta_aprovechamiento_pct') / 100 * sum(peso_t)
                        - coalesce(sum(peso_t) FILTER (WHERE aprovechado), 0), 0), 2)
  FROM base
  GROUP BY id, nombre, tipo_generador
  ORDER BY nombre
$$;
