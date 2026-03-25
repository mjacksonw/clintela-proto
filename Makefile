# Clintela Development Commands

.PHONY: help install sync dev test coverage lint lint-fix format format-check pre-commit check setup clean docker-up docker-down docker-logs docker-shell docker-migrate docker-test

# Default target
help: ## Show this help message
	@echo "Clintela Development Commands"
	@echo "=============================="
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)

# UV Installation and Setup
install: ## Install project dependencies using UV
	@echo "Installing dependencies with UV..."
	uv pip install -e ".[dev]"

sync: ## Sync dependencies from pyproject.toml (removes extraneous packages)
	@echo "Syncing dependencies..."
	uv pip sync pyproject.toml --reinstall

lock: ## Generate uv.lock file with hashes
	@echo "Generating lock file..."
	uv pip compile pyproject.toml --generate-hashes -o uv.lock

# Development Commands
dev: ## Start Django development server
	python manage.py runserver

dev-worker: ## Start Channels worker for async tasks
	python manage.py runworker

shell: ## Open Django shell with extensions
	python manage.py shell_plus --print-sql

dbshell: ## Open PostgreSQL shell
	python manage.py dbshell

# Database Commands
migrations: ## Create new database migrations
	python manage.py makemigrations

migrate: ## Run database migrations
	python manage.py migrate

migrations-check: ## Check for missing migrations
	python manage.py makemigrations --check --dry-run

# Testing Commands
test: ## Run all tests
	pytest

test-watch: ## Run tests in watch mode (requires pytest-watch)
	pytest-watch --clear

test-fast: ## Run fast tests only (skip slow/integration)
	pytest -m "not slow and not integration"

coverage: ## Run tests with coverage report
	pytest --cov=apps --cov=config --cov-report=html --cov-report=term-missing
	@echo "Coverage report: htmlcov/index.html"

coverage-report: ## Open coverage report in browser
	open htmlcov/index.html

# Linting and Formatting
lint: ## Run ruff linter
	ruff check .

lint-fix: ## Run ruff linter with auto-fix
	ruff check --fix .

format: ## Format code with ruff
	ruff format .

format-check: ## Check code formatting
	ruff format --check .

mypy: ## Run mypy type checking
	mypy apps config

# Pre-commit
pre-commit: ## Run all pre-commit hooks
	pre-commit run --all-files

pre-commit-install: ## Install pre-commit hooks
	pre-commit install

# Security
security: ## Run security checks (bandit)
	bandit -r apps/ -f json -o bandit-report.json || true
	@echo "Security report: bandit-report.json"

secrets-scan: ## Scan for secrets in codebase
	detect-secrets scan --baseline .secrets.baseline

# Combined Checks
check: lint format-check test ## Run all checks (lint, format, test)

check-full: lint format-check mypy test security ## Run full checks including security

# Setup Commands
setup: ## Initial setup (install deps, migrate, create superuser)
	@echo "Setting up Clintela development environment..."
	@make install
	@make migrate
	@echo "Setup complete! Run 'make dev' to start the server."

setup-clean: clean ## Clean setup (removes cache, reinstalls)
	@make setup

# Cleanup
clean: ## Clean up cache files and temporary files
	@echo "Cleaning up..."
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	rm -rf .mypy_cache .ruff_cache htmlcov .coverage
	rm -f bandit-report.json
	@echo "Cleanup complete!"

# Backing Services (dev-on-host workflow)
bootstrap: ## Bootstrap full dev environment from scratch
	./bootstrap.sh

services-up: ## Start backing services (db, redis, ollama)
	docker compose -f docker-compose.services.yml up -d

services-down: ## Stop backing services
	docker compose -f docker-compose.services.yml down

services-logs: ## Tail backing service logs
	docker compose -f docker-compose.services.yml logs -f

services-ps: ## Show backing service status
	docker compose -f docker-compose.services.yml ps

# Docker Commands (full-stack — runs Django in container)
docker-up: ## Start Docker development environment
	docker-compose up -d

docker-down: ## Stop Docker development environment
	docker-compose down

docker-down-volumes: ## Stop Docker and remove volumes (WARNING: deletes data)
	docker-compose down -v

docker-logs: ## View Docker logs
	docker-compose logs -f

docker-logs-web: ## View web container logs only
	docker-compose logs -f web

docker-shell: ## Open shell in web container
	docker-compose exec web bash

docker-migrate: ## Run migrations in Docker
	docker-compose exec web python manage.py migrate

docker-migrations: ## Create migrations in Docker
	docker-compose exec web python manage.py makemigrations

docker-test: ## Run tests in Docker
	docker-compose exec web pytest

docker-coverage: ## Run coverage in Docker
	docker-compose exec web pytest --cov=apps --cov=config --cov-report=html

docker-build: ## Rebuild Docker containers
	docker-compose build --no-cache

# Utilities
dump-env: ## Dump current environment variables (excluding secrets)
	@echo "Environment Variables (excluding secrets):"
	@echo "=========================================="
	@echo "DEBUG: $$(echo $$DEBUG)"
	@echo "DATABASE_URL: $$(echo $$DATABASE_URL | cut -d'@' -f2 | cut -d'/' -f1)"
	@echo "PYTHONPATH: $$(echo $$PYTHONPATH)"
	@echo "DJANGO_SETTINGS_MODULE: $$(echo $$DJANGO_SETTINGS_MODULE)"

check-env: ## Check environment is configured correctly
	@echo "Checking environment..."
	@python -c "import sys; print(f'Python: {sys.version}')"
	@python -c "import django; print(f'Django: {django.VERSION}')"
	@python manage.py check --deploy --fail-level WARNING 2>/dev/null || echo "⚠️  Deploy checks found issues (expected in dev)"
	@echo "✓ Environment looks good!"

# Static Files
collectstatic: ## Collect static files
	python manage.py collectstatic --noinput

findstatic: ## Find static files location
	@echo "Static files locations:"
	@python manage.py findstatic --verbosity 0 . 2>/dev/null | head -1 || echo "Run collectstatic first"

# Project Structure
show-structure: ## Display project structure
	@tree -L 3 -I '__pycache__|*.pyc|node_modules|venv|.venv|.git|htmlcov|.pytest_cache|.mypy_cache|.ruff_cache' || find . -maxdepth 3 -type d -not -path '*/\.*' -not -path '*/node_modules/*' | head -50

# Maintenance
update-deps: ## Update dependencies in pyproject.toml
	@echo "Updating dependencies..."
	@echo "Run: uv pip install --upgrade <package>"
	@echo "Then update pyproject.toml manually"

# Aliases for common workflows
run: dev ## Alias for 'make dev'
t: test ## Alias for 'make test'
fmt: format ## Alias for 'make format'
fix: lint-fix ## Alias for 'make lint-fix'
up: services-up ## Alias for 'make services-up'
down: services-down ## Alias for 'make services-down'
