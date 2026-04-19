#!/bin/sh
set -e
# Match Dockerfile WORKDIR (/app): Alembic config lives under apps/backend/...
if [ -f /app/apps/backend/infrastructure/db/alembic.ini ]; then
  cd /app
else
  echo "alembic_entrypoint: no alembic.ini under /app/apps/backend/infrastructure/db" >&2
  exit 1
fi
alembic -c apps/backend/infrastructure/db/alembic.ini upgrade head
exec "$@"
