#!/bin/sh
# ============================================================
# Migration runner — the container entrypoint.
#
# 1. Waits for Postgres to accept connections (fresh CNPG clusters
#    take ~30s on first boot).
# 2. Applies migrations/*.sql in filename order, exactly once each,
#    tracked in a schema_migrations table. Each row records the
#    pantry-db release that applied it (applied_by), so the cluster
#    can say which release brought in a migration.
# 3. Applies seeds/seed.sql on EVERY run (the file is idempotent —
#    upserts + per-recipe delete/re-insert).
#
# Runs as an ArgoCD PreSync Job: every sync migrates before the app
# workloads roll. Config via env: DB_HOST, DB_PORT, DB_NAME, DB_USER,
# DB_PASSWORD (from the CNPG-generated credential secret).
# PANTRY_DB_VERSION is baked into the image by the Dockerfile.
# MIGRATIONS_DIR and SEED_FILE default to the image's paths; CI points
# them at the checkout to run this same script against a test database.
# ============================================================
set -eu

: "${DB_HOST:?DB_HOST is required}"
: "${DB_USER:?DB_USER is required}"
: "${DB_PASSWORD:?DB_PASSWORD is required}"
DB_PORT="${DB_PORT:-5432}"
DB_NAME="${DB_NAME:-pantry}"
MIGRATIONS_DIR="${MIGRATIONS_DIR:-/migrations}"
SEED_FILE="${SEED_FILE:-/seeds/seed.sql}"
# A local build has no release; say so rather than leave the column empty,
# which already means "applied before the runner recorded it".
APPLIED_BY="${PANTRY_DB_VERSION:-unknown}"

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
# Added in place, never by a migration: this table belongs to the runner.
# Rows from before the column existed keep NULL (not recorded).
$PSQL -c "ALTER TABLE schema_migrations ADD COLUMN IF NOT EXISTS applied_by text;"

echo "pantry-db release: $APPLIED_BY"
for f in "$MIGRATIONS_DIR"/*.sql; do
  [ -e "$f" ] || { echo "no migrations in $MIGRATIONS_DIR"; exit 1; }
  version="$(basename "$f" .sql)"
  if [ "$($PSQL -c "SELECT 1 FROM schema_migrations WHERE version = '$version'")" = "1" ]; then
    echo "skip  $version (already applied)"
    continue
  fi
  echo "apply $version"
  $PSQL -f "$f"
  # psql variables, read from stdin (they are not expanded in -c), so the
  # release string is quoted by psql rather than spliced into the SQL.
  $PSQL -v version="$version" -v applied_by="$APPLIED_BY" <<'SQL'
INSERT INTO schema_migrations (version, applied_by) VALUES (:'version', :'applied_by');
SQL
done

echo "seed  $SEED_FILE (idempotent)"
$PSQL -f "$SEED_FILE"

echo "Done. Applied migrations:"
$PSQL -c "SELECT version || '  ' || applied_at || '  ' || coalesce(applied_by, '(release not recorded)')
          FROM schema_migrations ORDER BY version;"
