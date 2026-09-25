# Firstlook local development. Run `make help` for targets.
COMPOSE := docker compose -f compose/docker-compose.yml --env-file .env

.PHONY: help setup up up-full down dev seed seed-llm migrate add-user sourcing test test-py test-ts lint fmt build logs reset

help:
	@grep -E '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  %-10s %s\n", $$1, $$2}'

.env:
	cp .env.example .env

setup: .env ## Install Python and Node dependencies
	uv sync
	pnpm install

up: .env ## Start core infrastructure (Postgres, Redis, S3, Redpanda, Temporal, ClickHouse, LiteLLM, Mailpit)
	$(COMPOSE) up -d --wait

up-full: .env ## Infrastructure plus Langfuse and Grafana (observability profile)
	$(COMPOSE) --profile observability up -d --wait

down: ## Stop infrastructure (data volumes are kept)
	$(COMPOSE) --profile observability down

migrate: ## Apply database migrations
	uv run python -m firstlook_core.migrate

seed: migrate ## Load the synthetic funds with golden extractions (no model calls)
	uv run python -m firstlook_fixtures.seed --reset

seed-llm: migrate ## Load the synthetic funds, extracting through the LLM gateway (needs ANTHROPIC_API_KEY)
	uv run python -m firstlook_fixtures.seed --reset --llm gateway

add-user: ## Add a user who can sign in: make add-user EMAIL=you@fund.vc NAME="Your Name" [ROLE=admin] [TENANT=savanna]
	@test -n "$(EMAIL)" -a -n "$(NAME)" || (echo 'usage: make add-user EMAIL=you@fund.vc NAME="Your Name" [ROLE=admin] [TENANT=savanna]' && exit 1)
	uv run python -m firstlook_core.admin add-user --email "$(EMAIL)" --name "$(NAME)" --role "$(or $(ROLE),admin)" --tenant "$(or $(TENANT),savanna)"

sourcing: ## Collect signals (network sources) and re-rank every thesis: make sourcing [TENANT=savanna]
	uv run python -m firstlook_sourcing collect --tenant "$(or $(TENANT),savanna)"
	uv run python -m firstlook_sourcing score --tenant "$(or $(TENANT),savanna)"

dev: up ## Infrastructure + every service with reload (web on http://localhost:13000)
	uv run honcho -f Procfile.dev start

test: test-py test-ts ## All tests (needs `make up` for DB tests)

test-py:
	uv run pytest

test-ts:
	pnpm -r --filter './services/*' --filter './apps/*' test --if-present

lint: ## Lint and typecheck everything
	uv run ruff check .
	uv run ruff format --check .
	pnpm typecheck

fmt:
	uv run ruff format .
	uv run ruff check --fix .

build: ## Build all apps and container images
	pnpm build
	docker build -f infra/docker/python.Dockerfile -t firstlook/python .
	docker build -f infra/docker/api.Dockerfile -t firstlook/api .
	docker build -f infra/docker/web.Dockerfile -t firstlook/web .

logs:
	$(COMPOSE) logs -f --tail=100

reset: ## Destroy local data volumes (asks first)
	@read -p "Delete all local Firstlook data? [y/N] " a && [ "$$a" = y ] && $(COMPOSE) --profile observability down -v
