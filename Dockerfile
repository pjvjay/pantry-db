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

# The release this image is. build.yml passes them (RELEASING.md in
# pantry-platform); run-migrations.sh records PANTRY_DB_VERSION on every
# migration it applies, and the labels let anyone holding only the image
# find its commit. A plain `docker build` leaves them empty and the runner
# records "unknown".
ARG APP_VERSION=""
ARG GIT_SHA=""
ARG BUILD_TIME=""
ENV PANTRY_DB_VERSION=$APP_VERSION
LABEL org.opencontainers.image.title="pantry-db-migrate" \
      org.opencontainers.image.source="https://github.com/pjvjay/pantry-db" \
      org.opencontainers.image.version=$APP_VERSION \
      org.opencontainers.image.revision=$GIT_SHA \
      org.opencontainers.image.created=$BUILD_TIME

# Run as the unprivileged postgres user the base image ships with.
USER postgres

ENTRYPOINT ["/run-migrations.sh"]
