# ═════════════════════════════════════════════════════════════════════════════
# NANDI — backend dev Makefile (Member 1).
#
# Convenience wrappers around the local .venv + the DEV-ONLY docker-compose.yml.
# Member 4 owns the canonical infra/ + prod tooling; this is for local hacking.
#
# Typical first run:
#     make venv install     # create .venv and install deps
#     make db-up            # start Postgres / Neo4j / Redis (docker compose)
#     make migrate seed     # apply schema, load Nashik topology
#     make run              # uvicorn with --reload
#
# All Python is run through the project .venv so no global activation is needed.
# POSIX/macOS friendly: uses python3 and plain sh.
# ═════════════════════════════════════════════════════════════════════════════

# .venv binaries (override on the command line, e.g. `make PY=python3.11 venv`).
VENV    := .venv
PY      := python3
PYTHON  := $(VENV)/bin/python
PIP     := $(VENV)/bin/pip
ALEMBIC := $(VENV)/bin/alembic
UVICORN := $(VENV)/bin/uvicorn

COMPOSE := docker compose

.DEFAULT_GOAL := help

.PHONY: help venv install db-up db-down migrate seed run test emit-cypher

help: ## Show this help.
	@echo "NANDI dev targets:"
	@echo "  venv         create the .venv virtualenv ($(VENV))"
	@echo "  install      pip install -r requirements.txt into .venv"
	@echo "  db-up        docker compose up -d (Postgres + Neo4j + Redis)"
	@echo "  db-down      docker compose down (keeps named volumes)"
	@echo "  migrate      alembic upgrade head"
	@echo "  seed         seed Postgres + Neo4j with the Nashik topology"
	@echo "  run          uvicorn api.main:app --reload"
	@echo "  test         python -m pytest -q"
	@echo "  emit-cypher  regenerate graph/seed_nashik.cypher from seed_data"

venv: ## Create the .venv virtualenv if missing.
	@test -d $(VENV) || $(PY) -m venv $(VENV)
	@echo "virtualenv ready at $(VENV)"

install: ## Install Python dependencies into .venv.
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements.txt

db-up: ## Start the dev stack (detached).
	$(COMPOSE) up -d

db-down: ## Stop the dev stack (named volumes are preserved).
	$(COMPOSE) down

migrate: ## Apply database migrations to the latest revision.
	$(ALEMBIC) upgrade head

seed: ## Seed Postgres + Neo4j (idempotent).
	$(PYTHON) -m scripts.seed_postgres
	$(PYTHON) -m scripts.seed_neo4j

run: ## Run the API with autoreload.
	$(UVICORN) api.main:app --reload

test: ## Run the test suite quietly.
	$(PYTHON) -m pytest -q

emit-cypher: ## Regenerate graph/seed_nashik.cypher from scripts/seed_data.py.
	$(PYTHON) -m scripts.seed_neo4j --emit-cypher graph/seed_nashik.cypher
