# PostgreSQL 16 + PostGIS 3.5 + pgRouting 3.8 (imagen oficial del proyecto pgRouting)
FROM pgrouting/pgrouting:16-3.5-3.8.0
# Scripts del proyecto: se ejecutan solo la primera vez (volumen de datos vacío)
COPY db/*.sql /sql/
COPY docker/initdb.sh /docker-entrypoint-initdb.d/50-rcd.sh
