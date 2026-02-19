#!/usr/bin/env bash
set -euo pipefail

source .env

CONTAINER="mcp_mesh_postgres"

for f in infra/migrations/*.sql; do
  echo "Applying $f"
  docker exec -i "$CONTAINER" psql \
    -U "$POSTGRES_USER" \
    -d "$POSTGRES_DB" \
    -v ON_ERROR_STOP=1 < "$f"
done

echo "Done."