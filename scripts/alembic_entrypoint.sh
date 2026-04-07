#!/bin/sh
set -e
# Match Dockerfile WORKDIR (/app) or older layout (/src).
if [ -f /app/src/infrastructure/db/alembic.ini ]; then
  cd /app
else
  echo "alembic_entrypoint: no alembic.ini under /app" >&2
  exit 1
fi
alembic -c src/infrastructure/db/alembic.ini upgrade head
exec "$@"
