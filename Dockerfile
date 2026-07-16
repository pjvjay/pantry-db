# Migration runner image — psql + migrations + seeds.
#
# postgres:17-alpine gives us a psql whose version exactly matches the
# CNPG server (both 17), multi-arch (amd64 + arm64), ~240 MB.
# We never start a server; the entrypoint just runs psql against DB_HOST.
FROM postgres:17-alpine

COPY migrations/ /migrations/
COPY seeds/seed.sql /seeds/seed.sql
COPY scripts/run-migrations.sh /run-migrations.sh
RUN chmod +x /run-migrations.sh

# Run as the unprivileged postgres user the base image ships with.
USER postgres

ENTRYPOINT ["/run-migrations.sh"]
