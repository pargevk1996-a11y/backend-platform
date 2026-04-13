.PHONY: help deps test test-auth test-user test-gateway test-e2e-auth test-e2e-stack lint-auth lint-user lint-gateway migrate-auth migrate-user run-auth run-user run-gateway up down

help:
	@echo "Available targets:"
	@echo "  deps            - install auth-service dependencies into .venv"
	@echo "  test            - run all tests for all services"
	@echo "  test-auth       - run all auth-service tests"
	@echo "  test-user       - run all user-service tests"
	@echo "  test-gateway    - run all api-gateway tests"
	@echo "  test-e2e-auth   - run gateway auth security e2e flow (stack must be up)"
	@echo "  test-e2e-stack  - run full docker e2e stack test with migrations and teardown"
	@echo "  lint-auth       - run ruff for auth-service"
	@echo "  lint-user       - run ruff for user-service"
	@echo "  lint-gateway    - run ruff for api-gateway"
	@echo "  migrate-auth    - apply auth-service alembic migrations"
	@echo "  migrate-user    - apply user-service alembic migrations"
	@echo "  run-auth        - run auth-service locally"
	@echo "  run-user        - run user-service locally"
	@echo "  run-gateway     - run api-gateway locally"
	@echo "  up              - start docker compose dev stack"
	@echo "  down            - stop docker compose dev stack"

deps:
	python3 -m venv .venv
	.venv/bin/pip install -r services/auth-service/requirements.lock
	.venv/bin/pip install -r services/user-service/requirements.lock
	.venv/bin/pip install -r services/api-gateway/requirements.lock

test: test-auth test-user test-gateway

test-auth:
	PYTHONPATH=services/auth-service .venv/bin/python -m pytest -q services/auth-service/tests

test-user:
	PYTHONPATH=services/user-service .venv/bin/python -m pytest -q services/user-service/tests

test-gateway:
	PYTHONPATH=services/api-gateway .venv/bin/python -m pytest -q services/api-gateway/tests

test-e2e-auth:
	GATEWAY_BASE_URL=$${GATEWAY_BASE_URL:-http://localhost:8000} .venv/bin/python -m pytest -q tests/e2e/test_gateway_auth_security_flow.py

test-e2e-stack:
	infra/scripts/run_e2e_stack.sh

lint-auth:
	.venv/bin/python -m ruff check services/auth-service

lint-user:
	.venv/bin/python -m ruff check services/user-service

lint-gateway:
	.venv/bin/python -m ruff check services/api-gateway

migrate-auth:
	docker compose --env-file infra/compose/.env.compose -f infra/compose/docker-compose.dev.yml run --rm auth-service alembic upgrade head

migrate-user:
	docker compose --env-file infra/compose/.env.compose -f infra/compose/docker-compose.dev.yml run --rm user-service alembic upgrade head

run-auth:
	cd services/auth-service && PYTHONPATH=. ../../.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload

run-user:
	cd services/user-service && PYTHONPATH=. ../../.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8002 --reload

run-gateway:
	cd services/api-gateway && PYTHONPATH=. ../../.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

up:
	docker compose --env-file infra/compose/.env.compose -f infra/compose/docker-compose.dev.yml up -d

down:
	docker compose --env-file infra/compose/.env.compose -f infra/compose/docker-compose.dev.yml down
