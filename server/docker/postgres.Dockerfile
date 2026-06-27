# ─────────────────────────────────────────────────────────────────────────────
# NANDI dev PostgreSQL image: PostGIS + pgvector in one container.
#
# No single official image ships BOTH PostGIS and pgvector, and NANDI needs both
# (PostGIS for booth/zone geometry, pgvector for the 1024/512-dim embedding ANN
# search). We start from the official PostGIS image and add the Debian-packaged
# pgvector extension for PostgreSQL 16.
#
# DEV-ONLY: Member 4 owns the canonical infra/ stack used for staging/prod. This
# Dockerfile exists purely so a backend dev can `docker compose up` a local DB.
# ─────────────────────────────────────────────────────────────────────────────
FROM postgis/postgis:16-3.4

# postgresql-16-pgvector provides the `vector` extension matching the PG 16 server
# bundled in the base image. CREATE EXTENSION is still required per-database; the
# Alembic initial migration handles `CREATE EXTENSION IF NOT EXISTS vector`.
RUN apt-get update \
    && apt-get install -y --no-install-recommends postgresql-16-pgvector \
    && rm -rf /var/lib/apt/lists/*
