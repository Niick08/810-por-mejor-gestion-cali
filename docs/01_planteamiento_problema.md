# Planteamiento del problema — Trazabilidad geográfica de RCD en Cali

> Borrador v0.2 · Proyecto final · Geoinformación en la Web (2026-II) · Especialización en Geomática, Universidad del Valle
> *Las cifras están marcadas para verificar contra la fuente más reciente antes de la entrega.*

## 1. Contexto

Los residuos de construcción y demolición (RCD, "escombros") que no llegan a un sitio autorizado terminan en separadores, lotes, parques y canales de Santiago de Cali. La Alcaldía ha señalado la incorrecta disposición de residuos como **la principal causa de las inundaciones** en varios puntos de la ciudad [1] y ha identificado **119 puntos de arrojo clandestino** [2]. Tras el sismo de agosto de 2026, el volumen de RCD creció de forma extraordinaria: más de **232.000 toneladas** han llegado al centro de acopio de la Calle 5 con Carrera 50 [3].

El marco legal ya define quién puede manejar estos residuos y dónde:

- La **Resolución 0472 de 2017**, modificada por la **Resolución 1257 de 2021** (MinAmbiente), regula la gestión integral de RCD [4][5]:
  - Los gestores de puntos limpios, plantas de aprovechamiento y sitios de disposición final deben **inscribirse ante la autoridad ambiental**, expedir **constancias** al generador y presentar **reportes trimestrales** con cantidades y destino (art. 16).
  - La autoridad debe **publicar y actualizar cada trimestre el listado de gestores inscritos** (art. 18).
  - El **gran generador** (obra con licencia y 2.000 m² o más construidos) debe tener un **Programa de Manejo Ambiental de RCD** y reportarlo cada trimestre (arts. 2 y 13).
  - Se **prohíbe** abandonar RCD, disponerlos en espacio público o rellenos sanitarios, y almacenarlos en zonas verdes, parques, ríos, quebradas, canales, humedales y zonas ribereñas (art. 20).
  - Para municipios de **categoría especial, como Cali**, la meta de aprovechamiento es del **50% desde 2026** y del **75% en 2030** (art. 19).
- En Cali, el **Decreto 0771 de 2018** encarga al DAGMA de inscribir a los gestores de RCD (con un PIN) y hacerles seguimiento [6]. El DAGMA publica el listado de gestores autorizados [7].
- El control también existe. Las personas naturales reciben comparendos por el art. 111 de la Ley 1801 de 2016 (estrategia "Caza Infractor") [8], y el DAGMA ha sancionado constructoras [9].

## 2. Descripción del problema

La norma es **esencialmente geográfica**: dice dónde se puede llevar el material y dónde no. Sin embargo, las empresas gestoras no cuentan con una herramienta que verifique en el mapa cada movimiento de RCD. Hoy:

1. **La trazabilidad es documental, no espacial.** Las constancias y los reportes trimestrales registran cantidades, pero no prueban geográficamente que la carga llegó a un sitio autorizado.
2. **Nadie detecta a tiempo una entrega irregular.** Un viaje que termina junto a un canal o en un lote, en lugar de en una planta inscrita, solo se descubre después, cuando ya es un punto crítico.
3. **La meta de aprovechamiento no se sigue en tiempo real.** Sin datos por obra y por tipo de RCD, la gestora no sabe si va a cumplir el 50% exigido.
4. **Los arrojos no se conectan con su posible origen.** Los puntos de arrojo y las obras activas cercanas están en fuentes separadas.

Los programas de gestión de obra existentes (por ejemplo, Edificar, para costos y presupuestos) no cubren este componente.

**Pregunta:** ¿Cómo puede una plataforma de geoinformación en la web, con tecnologías libres, convertir las reglas de la Resolución 0472 de 2017 en validaciones espaciales automáticas que apoyen la trazabilidad de los RCD de una empresa gestora en Cali?

## 3. Árbol de problemas (resumen)

| Causas | Problema central | Consecuencias |
|---|---|---|
| Reportes en papel u hojas de cálculo, sin ubicación | Falta de trazabilidad geográfica de los RCD entre la obra y el destino | Arrojos en canales y zonas verdes → **inundaciones** |
| La norma no está disponible como capas geográficas | | Sanciones a generadores y gestores |
| Transportistas informales o sin control | | Incumplimiento de la meta de aprovechamiento |
| Fuentes separadas: obras, viajes, arrojos | | Pérdida de material que podría aprovecharse |

## 4. Propuesta: tres capas

1. **Norma:** gestores inscritos (dónde sí) y zonas prohibidas del art. 20 (dónde no), como polígonos.
2. **Operación:** obra → viaje → destino. Cada entrega se valida automáticamente contra la capa 1 (✓ válida, ! sospechosa, ✕ infracción).
3. **Problema:** puntos de arrojo reportados en campo y cruzados con las obras activas cercanas.

El detalle de pantallas y botones está en [02_diseno_funcional.md](02_diseno_funcional.md).

## 5. Justificación

- **Para el área:** la gestora obtiene evidencia geográfica de cada viaje para sus constancias y reportes trimestrales (art. 16), alertas tempranas de entregas irregulares y el seguimiento de la meta de aprovechamiento (art. 19).
- **Ambiental y de riesgo:** detectar a tiempo una entrega cerca de un canal previene obstrucciones e inundaciones.
- **Geomática:** el aporte central es **traducir una norma a geometría** y dejar que la base de datos espacial la aplique.
- **Académica:** integra las tecnologías del curso (PostgreSQL/PostGIS, PL/pgSQL, triggers, GeoServer, Leaflet, Turf.js, API REST) en una arquitectura cliente-servidor con software libre.

## 6. Objetivos

### General
Desarrollar una plataforma web de geoinformación, con software libre y arquitectura cliente-servidor, que apoye la trazabilidad geográfica de los residuos de construcción y demolición de una empresa gestora en Santiago de Cali, validando cada entrega frente a las disposiciones espaciales de la Resolución 0472 de 2017.

### Específicos
1. Representar como capas geográficas los gestores inscritos y las zonas de prohibición del art. 20 de la Resolución 0472 de 2017.
2. Diseñar e implementar un modelo de datos espacial que soporte obras, viajes, destinos, puntos de arrojo y usuarios con roles.
3. Implementar al menos tres mecanismos de registro georreferenciado (mapa, dirección geocodificada y GPS) con evidencia fotográfica.
4. Automatizar en la base de datos la validación de cada entrega frente a la capa normativa.
5. Desarrollar visualizaciones espaciales y alfanuméricas diferenciadas para el operario y el administrador, incluido el seguimiento de la meta de aprovechamiento.

## 7. Alcance

- **Área:** zona urbana de Santiago de Cali.
- **Usuario objetivo:** una empresa gestora de RCD. Rol Usuario = operario de campo; rol Administrador = coordinador.
- **Datos de demostración:** capas de la IDESC y OpenStreetMap, listado de gestores del DAGMA, y obras, viajes y arrojos sintéticos basados en los comunicados oficiales.
- **No incluye:** integración con sistemas oficiales, facturación ni validación jurídica de las sanciones.

## Referencias

1. Alcaldía de Cali. *Fuertes lluvias e incorrecta disposición de basuras causan afectaciones en Cali.* https://www.cali.gov.co/publicaciones/180375/
2. Alcaldía de Cali. *Con 119 puntos de arrojo clandestino identificados…* https://www.cali.gov.co/serviciospublicos/publicaciones/181351/
3. Alcaldía de Cali. *Cali transforma los escombros del terremoto en materiales para reconstruir la ciudad.* https://www.cali.gov.co/publicaciones/194964/
4. MinAmbiente. *Resolución 0472 de 2017* (texto compilado). https://normograma.mintic.gov.co/mintic/compilacion/docs/resolucion_minambienteds_0472_2017.htm
5. MinAmbiente. *Resolución 1257 de 2021.* https://normas.cra.gov.co/gestor/docs/resolucion_minambienteds_1257_2021.htm
6. Alcaldía de Cali. *Decreto 0771 de 2018.* https://normagrama.cali.gov.co/compilacion/docs/pdf/d_alcacali_0771_2018.pdf
7. DAGMA. *Listado de gestores de RCD autorizados.* https://www.cali.gov.co/dagma/publicaciones/147925/
8. Alcaldía de Cali. *Caza Infractor.* https://www.cali.gov.co/publicaciones/193338/
9. Alcaldía de Cali. *En lo corrido del año, 15 constructoras han sido sancionadas por el Dagma.* https://www.cali.gov.co/publicaciones/177001/
