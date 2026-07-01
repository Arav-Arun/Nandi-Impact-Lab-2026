#!/usr/bin/env bash
# Apply DB migrations, then hand off to the CMD (uvicorn). The DB/Neo4j/Redis are
# gated healthy by compose depends_on, so they are reachable by the time we run.
set -euo pipefail

echo "[entrypoint] running migrations…"
python -m alembic upgrade head

# Seed is NOT run automatically - production starts with a clean database.
# To load the demo topology + sample data in a staging box, run manually:
#   docker compose -f docker-compose.prod.yml exec backend python -m scripts.seed_postgres
#   docker compose -f docker-compose.prod.yml exec backend python -m scripts.seed_neo4j

echo "[entrypoint] starting: $*"
exec "$@"
