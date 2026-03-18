# Clintela Dockerfile
# Multi-stage build: development and production targets

# =============================================================================
# BASE STAGE - Common dependencies
# =============================================================================
FROM python:3.12-slim-bookworm AS base

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONFAULTHANDLER=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    libmagic1 \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Install UV for faster Python package management
RUN pip install uv

# Set working directory
WORKDIR /app

# =============================================================================
# DEVELOPMENT STAGE
# =============================================================================
FROM base AS development

# Copy only requirements files first for better caching
COPY pyproject.toml .
COPY uv.lock* ./

# Install dependencies with dev extras
RUN uv pip install -e ".[dev]" --system

# Copy project files
COPY . .

# Create necessary directories
RUN mkdir -p staticfiles media logs

# Expose port
EXPOSE 8000

# Default command (overridden by docker-compose)
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]

# =============================================================================
# PRODUCTION STAGE
# =============================================================================
FROM base AS production

# Install system dependencies for production
RUN apt-get update && apt-get install -y --no-install-recommends \
    # Security updates
    apt-transport-https \
    ca-certificates \
    # PostgreSQL client for migrations
    postgresql-client \
    # Required for some Python packages
    libffi-dev \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Create non-root user for security
RUN groupadd -r clintela && useradd -r -g clintela clintela

# Copy and install production dependencies
COPY pyproject.toml .
RUN uv pip install -e ".[prod]" --system

# Copy project files
COPY . .

# Create necessary directories with proper permissions
RUN mkdir -p staticfiles media logs && \
    chown -R clintela:clintela /app

# Collect static files
RUN python manage.py collectstatic --noinput --clear

# Switch to non-root user
USER clintela

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health/')" || exit 1

# Expose port
EXPOSE 8000

# Production command
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "4", "--threads", "2", "--access-logfile", "-", "--error-logfile", "-", "config.wsgi:application"]
