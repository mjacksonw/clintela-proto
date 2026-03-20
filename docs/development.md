# Development Setup

**Getting started with Clintela development**

---

## Quick Start (Docker - Recommended)

The fastest way to get started with a complete, production-like environment:

```bash
# Clone the repository
git clone <repository-url>
cd clintela

# Copy environment file
cp .env.example .env

# Install UV (if not already installed)
curl -LsSf https://astral.sh/uv/install.sh | sh
# Or: pip install uv

# Install dependencies and create virtual environment
uv pip install -e ".[dev]"

# Start services (PostgreSQL + Redis)
make docker-up

# Run migrations
make migrate

# Start development server
make dev
```

**Access the application:**
- Web: http://localhost:8000
- Admin: http://localhost:8000/admin
- Database: postgres://clintela:clintela@localhost:5434/clintela (port 5434 to avoid conflicts)

---

## Quick Start (Local)

For local development without Docker:

```bash
# Clone the repository
git clone <repository-url>
cd clintela

# Set up Python environment (Python 3.11+)
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
make install
# Or: pip install -r requirements.txt

# Set up environment and database
cp .env.example .env
make setup
# This runs: install dependencies + migrations

# Start development server
make dev
# Or: python manage.py runserver

# In another terminal, start the worker (if using async tasks)
python manage.py runworker
```

**Access:** http://127.0.0.1:8000

---

## Prerequisites

### Required Software

- **Python:** 3.11 or higher
- **PostgreSQL:** 14 or higher
- **Redis:** 7 or higher (for caching and WebSockets)
- **Node.js:** 18 or higher (for frontend build tools)
- **Git:** Latest version

### Optional but Recommended

- **Docker:** For containerized development
- **direnv:** For automatic environment variable loading
- **pyenv:** For Python version management

---

## Environment Setup

### 1. Python Environment

**Using pyenv (recommended):**
```bash
# Install Python 3.11
pyenv install 3.11.0
pyenv local 3.11.0

# Create virtual environment
python -m venv venv
source venv/bin/activate
```

**Using venv directly:**
```bash
python3.11 -m venv venv
source venv/bin/activate
```

### 2. Database Setup

**PostgreSQL:**
```bash
# Create database
createdb clintela

# Create user
createuser -P clintela_user
# Enter password when prompted

# Grant privileges
psql -c "GRANT ALL PRIVILEGES ON DATABASE clintela TO clintela_user;"
```

**Database Configuration (in .env):**
```env
DATABASE_URL=postgres://clintela_user:password@localhost:5432/clintela
```

### 3. Redis Setup

**Local Redis:**
```bash
# macOS with Homebrew
brew install redis
brew services start redis

# Ubuntu/Debian
sudo apt-get install redis-server
sudo systemctl start redis

# Verify
redis-cli ping
# Should return: PONG
```

**Redis Configuration (in .env):**
```env
REDIS_URL=redis://localhost:6379/0
```

### 4. Environment Variables

Create `.env` file:

```env
# Django
DEBUG=True
SECRET_KEY=your-secret-key-here-change-in-production
ALLOWED_HOSTS=localhost,127.0.0.1

# Database
DATABASE_URL=postgres://clintela_user:password@localhost:5432/clintela

# Redis
REDIS_URL=redis://localhost:6379/0

# LLM (Ollama Cloud for development)
OLLAMA_API_KEY=your-ollama-api-key
OLLAMA_BASE_URL=https://api.ollama.com/v1

# Twilio (for SMS/Voice - optional for local dev)
TWILIO_ACCOUNT_SID=your-account-sid
TWILIO_AUTH_TOKEN=your-auth-token
TWILIO_PHONE_NUMBER=+1234567890

# Email (for notifications - optional for local dev)
EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend
# Or for real email:
# EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
# EMAIL_HOST=smtp.gmail.com
# EMAIL_PORT=587
# EMAIL_USE_TLS=True
# EMAIL_HOST_USER=your-email@gmail.com
# EMAIL_HOST_PASSWORD=your-app-password

# Security (change in production)
CSRF_COOKIE_SECURE=False
SESSION_COOKIE_SECURE=False

# Logging
LOG_LEVEL=DEBUG
```

**Generate a secret key:**
```bash
python -c "import secrets; print(secrets.token_urlsafe(50))"
```

---

## Project Structure

```
clintela/
├── config/                    # Django configuration
│   ├── __init__.py
│   ├── settings/             # Split settings
│   │   ├── __init__.py
│   │   ├── base.py          # Common settings
│   │   ├── development.py   # Development-specific
│   │   ├── production.py    # Production-specific
│   │   └── test.py          # Test-specific
│   ├── urls.py              # Root URL configuration
│   ├── wsgi.py              # WSGI application
│   └── asgi.py              # ASGI application (for WebSockets)
├── apps/                     # Django applications
│   ├── accounts/            # User accounts, authentication
│   ├── patients/            # Patient management
│   ├── caregivers/          # Caregiver portal
│   ├── clinicians/          # Clinician dashboard
│   ├── agents/              # AI agent system
│   ├── messages_app/        # SMS, web chat, voice
│   ├── pathways/            # Clinical pathways
│   ├── notifications/       # Notifications, escalations
│   └── analytics/           # Metrics and reporting
├── templates/               # Django templates
│   ├── base.html
│   ├── patients/
│   ├── clinicians/
│   └── admin/
├── static/                   # Static files (CSS, JS, images)
│   ├── css/
│   ├── js/
│   └── images/
├── media/                    # User-uploaded files
├── docs/                     # Documentation
├── tests/                    # Test suite
├── requirements/             # Dependency files
│   ├── base.txt
│   ├── development.txt
│   └── production.txt
├── manage.py
├── .env                      # Environment variables (not in git)
├── .env.example             # Example environment file
├── .gitignore
├── README.md
└── DESIGN.md                 # Design system
```

---

## Running the Application

### Development Mode

**Standard Django server:**
```bash
python manage.py runserver
# Access at http://127.0.0.1:8000
```

**With WebSocket support and Celery (Phase 3+):**
```bash
# Terminal 1: Django HTTP server (with ASGI for WebSockets)
python manage.py runserver

# Terminal 2: Django Channels ASGI worker (WebSocket consumers)
python manage.py runworker

# Terminal 3: Celery worker (async notifications, SMS delivery, voice cleanup)
celery -A config worker -l info

# Terminal 4: Redis (if not running as service)
redis-server
```

### Docker Development

**Using Docker Compose:**
```bash
# Build and start all services
docker-compose up -d

# View logs
docker-compose logs -f

# Run migrations
docker-compose exec web python manage.py migrate

# Create superuser
docker-compose exec web python manage.py createsuperuser

# Stop services
docker-compose down
```

**Docker Compose file includes:**
- Web application (Django)
- PostgreSQL database
- Redis cache/message broker
- Celery worker (for background tasks)

---

## Development Workflow

### Database Migrations

**Create migration:**
```bash
python manage.py makemigrations
```

**Apply migrations:**
```bash
python manage.py migrate
```

**Check migration status:**
```bash
python manage.py showmigrations
```

### Static Files

**Collect static files:**
```bash
python manage.py collectstatic
```

**During development:**
Django serves static files automatically when `DEBUG=True`

### Testing

**Run all tests:**
```bash
pytest
```

**Run specific test file:**
```bash
pytest tests/test_agents.py
```

**Run with coverage:**
```bash
pytest --cov=apps --cov-report=html
```

**Coverage report:**
```bash
open htmlcov/index.html
```

### Code Quality with Ruff

**Ruff** replaces black, isort, and flake8 — faster and simpler.

**Check all files:**
```bash
ruff check .
```

**Check specific directory:**
```bash
ruff check apps/
```

**Fix auto-fixable issues:**
```bash
ruff check --fix .
```

**Format code:**
```bash
ruff format .
```

**Check and format (pre-commit style):**
```bash
ruff check --fix . && ruff format .
```

---

## Development Tools

### direnv (Recommended)

**direnv** automatically loads environment variables when you enter the project directory.

**Setup:**
```bash
# Install direnv
brew install direnv  # macOS
# or
apt-get install direnv  # Ubuntu/Debian

# Hook into shell
echo 'eval "$(direnv hook zsh)"' >> ~/.zshrc  # for zsh
echo 'eval "$(direnv hook bash)"' >> ~/.bashrc  # for bash
```

**Create `.envrc`:**
```bash
# Automatically load .env
if [ -f .env ]; then
  dotenv .env
fi

# Add project to PYTHONPATH
export PYTHONPATH="${PWD}:${PYTHONPATH}"

# Show helpful message
echo "Clintela development environment loaded"
echo "Python: $(python --version)"
echo "Run 'make help' for available commands"
```

**Allow the .envrc:**
```bash
direnv allow
```

**Now when you cd into the project:**
- Environment variables auto-load
- Python path is set
- Helpful message appears

### Makefile Commands

**Create a `Makefile` in project root:**

```makefile
.PHONY: help install dev test coverage lint format migrate shell clean docker-up docker-down

# Default target
help: ## Show this help message
	@echo "Clintela Development Commands"
	@echo "=============================="
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)

install: ## Install dependencies
	pip install -r requirements.txt
	pip install -r requirements-dev.txt

dev: ## Start development server
	python manage.py runserver

migrate: ## Run database migrations
	python manage.py migrate

migrations: ## Create new migrations
	python manage.py makemigrations

shell: ## Open Django shell
	python manage.py shell

test: ## Run all tests
	pytest

test-watch: ## Run tests in watch mode
	pytest -f

coverage: ## Run tests with coverage report
	pytest --cov=apps --cov-report=html --cov-report=term-missing
	@echo "Coverage report: htmlcov/index.html"

lint: ## Run ruff linter
	ruff check .

lint-fix: ## Run ruff linter with auto-fix
	ruff check --fix .

format: ## Format code with ruff
	ruff format .

format-check: ## Check code formatting
	ruff format --check .

pre-commit: ## Run all pre-commit checks
	pre-commit run --all-files

check: lint format-check test ## Run all checks (lint, format, test)

setup: install migrate ## Initial setup (install deps, run migrations)
	@echo "Setup complete! Run 'make dev' to start the server."

clean: ## Clean up cache files, etc.
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	rm -rf .pytest_cache htmlcov .coverage

docker-up: ## Start Docker development environment
	docker-compose up -d

docker-down: ## Stop Docker development environment
	docker-compose down

docker-logs: ## View Docker logs
	docker-compose logs -f

docker-shell: ## Open shell in Docker web container
	docker-compose exec web bash

docker-migrate: ## Run migrations in Docker
	docker-compose exec web python manage.py migrate

docker-test: ## Run tests in Docker
	docker-compose exec web pytest
```

**Usage:**
```bash
make help          # Show all commands
make setup         # Initial project setup
make dev           # Start development server
make test          # Run tests
make coverage      # Run tests with coverage
make lint          # Check code style
make lint-fix      # Fix code style issues
make format        # Format code
make check         # Run all checks
make docker-up     # Start with Docker
```

### Pre-commit Hooks

**Install pre-commit:**
```bash
pip install pre-commit
pre-commit install
```

**Create `.pre-commit-config.yaml`:**

```yaml
repos:
  # Ruff - linting and formatting
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.3.0
    hooks:
      - id: ruff
        args: [--fix]
      - id: ruff-format

  # Django checks
  - repo: local
    hooks:
      - id: django-check
        name: Django Check
        entry: python manage.py check
        language: system
        types: [python]
        pass_filenames: false

  # Run tests with coverage
  - repo: local
    hooks:
      - id: pytest-coverage
        name: Pytest with Coverage
        entry: pytest --cov=apps --cov-report=term-missing --cov-fail-under=90
        language: system
        types: [python]
        pass_filenames: false
        stages: [pre-push]

  # Security checks
  - repo: https://github.com/PyCQA/bandit
    rev: 1.7.7
    hooks:
      - id: bandit
        args: ["-c", "pyproject.toml"]
        additional_dependencies: ["bandit[toml]"]

  # Check for secrets
  - repo: https://github.com/Yelp/detect-secrets
    rev: v1.4.0
    hooks:
      - id: detect-secrets
        args: ['--baseline', '.secrets.baseline']
```

**Setup secrets baseline:**
```bash
detect-secrets scan > .secrets.baseline
detect-secrets audit .secrets.baseline
```

**Manual run:**
```bash
pre-commit run --all-files      # Run all hooks
pre-commit run ruff             # Run specific hook
```

---

## CI/CD with GitHub Actions

**Create `.github/workflows/ci.yml`:**

```yaml
name: CI

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest

    services:
      postgres:
        image: postgres:15
        env:
          POSTGRES_USER: postgres
          POSTGRES_PASSWORD: postgres
          POSTGRES_DB: clintela_test
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
        ports:
          - 5432:5432

    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
          cache: 'pip'

      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install -r requirements-dev.txt

      - name: Run ruff
        run: ruff check .

      - name: Check formatting
        run: ruff format --check .

      - name: Run Django checks
        env:
          DATABASE_URL: postgres://postgres:postgres@localhost:5432/clintela_test
          SECRET_KEY: test-secret-key
        run: python manage.py check

      - name: Run tests with coverage
        env:
          DATABASE_URL: postgres://postgres:postgres@localhost:5432/clintela_test
          SECRET_KEY: test-secret-key
        run: pytest --cov=apps --cov-report=xml --cov-fail-under=90

      - name: Upload coverage to Codecov
        uses: codecov/codecov-action@v3
        with:
          file: ./coverage.xml
          fail_ci_if_error: true

  security:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Run Bandit security checks
        uses: PyCQA/bandit@main
        with:
          args: "-r apps/ -f json -o bandit-report.json"

      - name: Upload security report
        uses: actions/upload-artifact@v3
        if: failure()
        with:
          name: security-report
          path: bandit-report.json
```

**Create `.github/workflows/deploy-staging.yml`:**

```yaml
name: Deploy to Staging

on:
  push:
    branches: [develop]

jobs:
  deploy:
    runs-on: ubuntu-latest
    needs: test

    steps:
      - uses: actions/checkout@v4

      - name: Deploy to staging
        run: |
          echo "Deploy to staging environment"
          # Add your deployment commands here
```

**Create `.github/workflows/deploy-production.yml`:**

```yaml
name: Deploy to Production

on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    needs: test
    environment: production

    steps:
      - uses: actions/checkout@v4

      - name: Deploy to production
        run: |
          echo "Deploy to production environment"
          # Add your deployment commands here
```

---

## External Services Setup

### Ollama Cloud (LLM)

**Sign up:**
1. Visit https://ollama.com/cloud
2. Create account
3. Generate API key

**Add to .env:**
```env
OLLAMA_API_KEY=your-api-key
OLLAMA_BASE_URL=https://api.ollama.com/v1
```

**Test connection:**
```bash
python -c "from apps.agents.llm import test_connection; test_connection()"
```

### Twilio (SMS/Voice)

**Sign up:**
1. Visit https://www.twilio.com/try-twilio
2. Create account
3. Get Account SID and Auth Token
4. Buy a phone number

**Add to .env:**
```env
TWILIO_ACCOUNT_SID=your-account-sid
TWILIO_AUTH_TOKEN=your-auth-token
TWILIO_PHONE_NUMBER=+1234567890
```

**For local development without Twilio:**
Messages are logged to the console via the console backend — no Twilio credentials needed for development.

---

## Debugging

### Django Debug Toolbar

**Install:**
```bash
pip install django-debug-toolbar
```

**Access:**
Visit any page and look for the debug toolbar on the right side.

### Logging

**View logs:**
```bash
# Real-time logs
tail -f logs/debug.log

# Filter for specific app
tail -f logs/debug.log | grep "agents"
```

**Log levels:**
- DEBUG: Development details
- INFO: General information
- WARNING: Potential issues
- ERROR: Errors that don't crash the app
- CRITICAL: Serious errors

### Database Queries

**Enable query logging:**
```python
# In settings/development.py
LOGGING = {
    'loggers': {
        'django.db.backends': {
            'level': 'DEBUG',
            'handlers': ['console'],
        },
    },
}
```

**Check query count:**
```python
from django.db import connection
print(f"Query count: {len(connection.queries)}")
```

---

## Common Issues

### Database Connection Error

**Problem:** `django.db.utils.OperationalError: could not connect to server`

**Solution:**
```bash
# Check PostgreSQL is running
brew services list | grep postgresql

# Start PostgreSQL
brew services start postgresql

# Verify connection
psql -U clintela_user -d clintela
```

### Migration Conflicts

**Problem:** `django.db.migrations.exceptions.InconsistentMigrationHistory`

**Solution:**
```bash
# Reset database (WARNING: deletes all data)
dropdb clintela
createdb clintela
python manage.py migrate

# Or squash migrations
python manage.py squashmigrations app_name 0001 0005
```

### Static Files Not Loading

**Problem:** CSS/JS not loading in development

**Solution:**
```bash
# Ensure DEBUG=True in settings
# Check static files configuration
python manage.py findstatic css/main.css

# Collect static files
python manage.py collectstatic --clear
```

---

## IDE Setup

### VS Code

**Recommended extensions:**
- Python (Microsoft)
- Django (batisteo)
- Pylance (Microsoft)
- Black Formatter (Microsoft)
- isort (Microsoft)
- Django Template (bibhasdn)

**Settings (.vscode/settings.json):**
```json
{
    "python.defaultInterpreterPath": "./venv/bin/python",
    "python.linting.enabled": true,
    "python.linting.flake8Enabled": true,
    "python.formatting.provider": "black",
    "editor.formatOnSave": true,
    "python.testing.pytestEnabled": true,
    "python.testing.pytestArgs": ["tests"]
}
```

### PyCharm

**Configuration:**
1. Open project in PyCharm
2. Set Python interpreter to `./venv/bin/python`
3. Enable Django support in Settings > Languages & Frameworks > Django
4. Set project root and settings file

---

## Deployment Preparation

### Pre-Deployment Checklist

- [ ] All tests passing
- [ ] Code coverage >90%
- [ ] Security audit passed
- [ ] Environment variables configured
- [ ] Database migrations ready
- [ ] Static files collected
- [ ] Documentation updated

### Production Settings

**Key changes from development:**
```python
# config/settings/production.py
DEBUG = False
ALLOWED_HOSTS = ['clintela.com', 'www.clintela.com']

# Security
SECRET_KEY = os.environ.get('SECRET_KEY')
CSRF_COOKIE_SECURE = True
SESSION_COOKIE_SECURE = True
SECURE_SSL_REDIRECT = True

# Database
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.environ.get('DB_NAME'),
        'USER': os.environ.get('DB_USER'),
        'PASSWORD': os.environ.get('DB_PASSWORD'),
        'HOST': os.environ.get('DB_HOST'),
        'PORT': os.environ.get('DB_PORT'),
        'CONN_MAX_AGE': 600,
    }
}

# Logging
LOGGING = {
    'version': 1,
    'handlers': {
        'file': {
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': '/var/log/clintela/app.log',
            'maxBytes': 10485760,  # 10MB
            'backupCount': 10,
        },
    },
    'root': {
        'handlers': ['file'],
        'level': 'INFO',
    },
}
```

---

## Getting Help

### Documentation

- [Django Docs](https://docs.djangoproject.com/)
- [Django REST Framework](https://www.django-rest-framework.org/)
- [HTMX](https://htmx.org/docs/)
- [LangChain](https://python.langchain.com/)

### Internal Resources

- [Architecture Overview](./architecture.md)
- [Agent System Design](./agents.md)
- [Security & Compliance](./security.md)
- [API Documentation](./api.md)

### Team Communication

- **Slack:** #clintela-dev
- **GitHub Issues:** For bugs and feature requests
- **Weekly Standup:** Mondays at 10am

---

## Contributing

### Code Style

- Follow PEP 8
- Use Black for formatting
- Use isort for import sorting
- Write docstrings for all public functions
- Keep functions focused and small

### Commit Messages

```
type(scope): subject

body (optional)

footer (optional)
```

**Types:**
- `feat:` New feature
- `fix:` Bug fix
- `docs:` Documentation
- `style:` Formatting
- `refactor:` Code restructuring
- `test:` Tests
- `chore:` Maintenance

**Example:**
```
feat(agents): add nurse triage agent

Implement the nurse triage agent for symptom assessment.
Includes routing from supervisor and escalation logic.

Closes #123
```

### Pull Request Process

1. Create feature branch from `main`
2. Make changes with tests
3. Ensure all tests pass
4. Update documentation
5. Submit PR with description
6. Request review from team
7. Merge after approval

---

*Development Setup — Ready to build*
