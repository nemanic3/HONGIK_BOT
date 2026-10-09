#!/bin/sh
# Run only in a dedicated server checkout; never point this at local user data.
set -eu
cd "$(dirname "$0")/../.."
ENV_FILE="${HONGIK_ENV_FILE:-.env.production}"
dc() { docker compose --env-file "$ENV_FILE" -f deploy/production/compose.yaml "$@"; }
test -s "$ENV_FILE"
test -s deploy/production/secrets/tunnel-token
dc build api worker
dc up -d postgres redis
# Stop API/worker before migrations or backups; tunnel serves errors temporarily.
dc stop api worker
umask 077
mkdir -p .backups/production
BACKUP_DIR=".backups/production/$(date -u +%Y%m%dT%H%M%SZ)"
mkdir "$BACKUP_DIR"
dc exec -T postgres pg_dump -U hongikbot -d hongikbot -Fc > "$BACKUP_DIR/database.dump"
dc run --rm --no-deps -T api tar -C /state -czf - . > "$BACKUP_DIR/uploads.tar.gz"
dc run --rm -T api python manage.py migrate --noinput
dc run --rm -T api python manage.py check --deploy --fail-level WARNING
dc run --rm -T warmup
dc up -d --wait api worker tunnel
