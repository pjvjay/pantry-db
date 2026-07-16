#!/bin/sh
# ============================================================
# Migration runner — the container entrypoint.
#
# 1. Waits for Postgres to accept connections (fresh CNPG clusters
#    take ~30s on first boot).
# 2. Applies migrations/*.sql in filename order, exactly once each,
#    tracked in a schema_migrations table.
# 3. Applies seeds/seed.sql on EVERY run (the file is idempotent —
#    upserts + per-recipe delete/re-insert).
#
# Runs as an ArgoCD PreSync Job: every sync migrates before the app
# workloads roll. Config via env: DB_HOST, DB_PORT, DB_NAME, DB_USER,
# DB_PASSWORD (from the CNPG-generated credential secret).
# ============================================================
set -eu

: "${DB_HOST:?DB_HOST is required}"
: "${DB_USER:?DB_USER is required}"
: "${DB_PASSWORD:?DB_PASSWORD is required}"
DB_PORT="${DB_PORT:-5432}"
DB_NAME="${DB_NAME:-pantry}"

export PGPASSWORD="$DB_PASSWORD"
PSQL="psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d $DB_NAME -v ON_ERROR_STOP=1 -qtA"

echo "Waiting for Postgres at $DB_HOST:$DB_PORT ..."
i=0
until pg_isready -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" >/dev/null 2>&1; do
  i=$((i + 1))
  [ "$i" -ge 30 ] && { echo "Postgres not ready after 150s, giving up"; exit 1; }
  sleep 5
done

$PSQL -c "CREATE TABLE IF NOT EXISTS schema_migrations (
            version    text PRIMARY KEY,
            applied_at timestamptz NOT NULL DEFAULT now()
          );"

for f in /migrations/*.sql; do
  version="$(basename "$f" .sql)"
  if [ "$($PSQL -c "SELECT 1 FROM schema_migrations WHERE version = '$version'")" = "1" ]; then
    echo "skip  $version (already applied)"
    continue
  fi
  echo "apply $version"
  $PSQL -f "$f"
  $PSQL -c "INSERT INTO schema_migrations (version) VALUES ('$version');"
done

echo "seed  seeds/seed.sql (idempotent)"
$PSQL -f /seeds/seed.sql

echo "Done. Applied migrations:"
$PSQL -c "SELECT version || '  ' || applied_at FROM schema_migrations ORDER BY version;"
