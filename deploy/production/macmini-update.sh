#!/bin/sh
# Poll the public production branch; deploy only its successful push CI revision.
set -eu
export PATH=/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin
ROOT="${HONGIK_REPOSITORY_ROOT:?Set repository root}"
cd "$ROOT"
STATE="$ROOT/.production-runtime"
umask 077
mkdir -p "$STATE"
if ! mkdir "$STATE/update.lock" 2>/dev/null; then exit 0; fi
trap 'rmdir "$STATE/update.lock"' EXIT HUP INT TERM
if ! docker info >/dev/null 2>&1; then
  open -a Docker
  exit 0
fi
git fetch --quiet origin master
REVISION="$(git rev-parse origin/master)"
if test -f "$STATE/deployed-sha" && test "$(cat "$STATE/deployed-sha")" = "$REVISION"; then exit 0; fi
VERIFIED="$(gh run list --repo nemanic3/HONGIK_BOT --workflow verify.yml --branch master --commit "$REVISION" --event push --limit 1 --json conclusion --jq '.[0].conclusion // ""')"
if test "$VERIFIED" != success; then exit 0; fi
RELEASE="$STATE/releases/$REVISION"
mkdir -p "$RELEASE"
git archive "$REVISION" | tar -x -C "$RELEASE"
ln -sf "$ROOT/.env.production" "$RELEASE/.env.production"
mkdir -p "$RELEASE/deploy/production/secrets"
ln -sf "$ROOT/deploy/production/secrets/tunnel-token" "$RELEASE/deploy/production/secrets/tunnel-token"
ln -sf "$STATE/backups" "$RELEASE/.backups"
mkdir -p "$STATE/backups"
cd "$RELEASE"
sh deploy/production/release.sh
printf '%s\n' "$REVISION" > "$STATE/deployed-sha"
printf '%s deployed %s\n' "$(date -u +%FT%TZ)" "$REVISION"
