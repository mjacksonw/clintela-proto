#!/usr/bin/env bash
# =============================================================================
# Clintela Dev Environment Bootstrap
#
# Takes a fresh Debian/Ubuntu VM from zero to a running dev environment.
# Idempotent — safe to re-run.
#
# Usage:
#   ./bootstrap.sh                    # full setup
#   ./bootstrap.sh --with-claude-code # also install Claude Code CLI
#   ./bootstrap.sh --no-demo-data     # skip demo data seeding
#   ./bootstrap.sh --no-ollama        # skip Ollama service + model pull
# =============================================================================
set -euo pipefail

# ---------------------------------------------------------------------------
# Flags
# ---------------------------------------------------------------------------
WITH_CLAUDE_CODE=false
WITH_DEMO_DATA=true
WITH_OLLAMA=true

for arg in "$@"; do
  case "$arg" in
    --with-claude-code) WITH_CLAUDE_CODE=true ;;
    --no-demo-data)     WITH_DEMO_DATA=false ;;
    --no-ollama)        WITH_OLLAMA=false ;;
    --help|-h)
      echo "Usage: ./bootstrap.sh [--with-claude-code] [--no-demo-data] [--no-ollama]"
      exit 0
      ;;
    *)
      echo "Unknown flag: $arg"
      echo "Usage: ./bootstrap.sh [--with-claude-code] [--no-demo-data] [--no-ollama]"
      exit 1
      ;;
  esac
done

# ---------------------------------------------------------------------------
# Colors
# ---------------------------------------------------------------------------
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
RED='\033[0;31m'
NC='\033[0m'

step()  { echo -e "\n${CYAN}==> $1${NC}"; }
ok()    { echo -e "    ${GREEN}$1${NC}"; }
warn()  { echo -e "    ${YELLOW}$1${NC}"; }
fail()  { echo -e "    ${RED}$1${NC}"; }

# ---------------------------------------------------------------------------
# 1. Sudoers (passwordless sudo for dev commands)
# ---------------------------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [ ! -f /etc/sudoers.d/clintela-dev ]; then
  step "Setting up passwordless sudo for dev commands"
  sudo "$SCRIPT_DIR/setup-sudoers.sh"
  ok "Sudoers configured"
else
  step "Sudoers"
  ok "Already configured (/etc/sudoers.d/clintela-dev)"
fi

# ---------------------------------------------------------------------------
# 2. System packages
# ---------------------------------------------------------------------------
step "Installing system packages"

sudo apt-get update -qq

PKGS=(git curl wget build-essential libpq-dev libmagic1 python3-dev
      # Playwright E2E test dependencies (headless Chromium)
      libxcomposite1 libxrandr2 libxfixes3 libgbm1
      libatk1.0-0t64 libatk-bridge2.0-0t64 libcups2 libxdamage1
      libxkbcommon0 libpango-1.0-0 libcairo2 libasound2t64
      libatspi2.0-0t64 libnspr4 libnss3)
MISSING=()
for pkg in "${PKGS[@]}"; do
  if ! dpkg -s "$pkg" &>/dev/null; then
    MISSING+=("$pkg")
  fi
done

if [ ${#MISSING[@]} -gt 0 ]; then
  sudo apt-get install -y -qq "${MISSING[@]}"
  ok "Installed: ${MISSING[*]}"
else
  ok "All system packages present"
fi

# ---------------------------------------------------------------------------
# 2. Docker
# ---------------------------------------------------------------------------
step "Setting up Docker"

if ! command -v docker &>/dev/null; then
  curl -fsSL https://get.docker.com | sudo sh
  ok "Docker installed"
else
  ok "Docker already installed"
fi

# Ensure docker compose plugin is available
if ! docker compose version &>/dev/null; then
  sudo apt-get install -y -qq docker-compose-plugin
  ok "Docker Compose plugin installed"
else
  ok "Docker Compose plugin present"
fi

# Add current user to docker group (takes effect on next login)
if ! groups "$USER" | grep -q docker; then
  sudo usermod -aG docker "$USER"
  warn "Added $USER to docker group — you may need to log out and back in"
fi

# Ensure Docker daemon is running
if ! sudo systemctl is-active --quiet docker; then
  sudo systemctl start docker
  sudo systemctl enable docker
fi

# ---------------------------------------------------------------------------
# 3. UV (Python package manager)
# ---------------------------------------------------------------------------
step "Setting up UV"

if ! command -v uv &>/dev/null; then
  curl -LsSf https://astral.sh/uv/install.sh | sh
  # Source the env so uv is available in this script
  export PATH="$HOME/.local/bin:$PATH"
  ok "UV installed"
else
  ok "UV already installed ($(uv --version))"
fi

# ---------------------------------------------------------------------------
# 4. Environment file
# ---------------------------------------------------------------------------
step "Setting up .env"

if [ ! -f .env ]; then
  cp .env.example .env
  # Set local Ollama embedding URL for dev-on-host
  if grep -q "^OLLAMA_EMBEDDING_BASE_URL=" .env; then
    sed -i 's|^OLLAMA_EMBEDDING_BASE_URL=.*|OLLAMA_EMBEDDING_BASE_URL=http://localhost:11434|' .env
  fi
  ok "Created .env from .env.example"
  warn "Edit .env to add your API keys (Ollama cloud, LangSmith, Twilio)"
else
  ok ".env already exists"
fi

# ---------------------------------------------------------------------------
# 5. Start backing services
# ---------------------------------------------------------------------------
step "Starting backing services (PostgreSQL, Redis${WITH_OLLAMA:+, Ollama})"

COMPOSE_FILE="docker-compose.services.yml"
SERVICES="db redis"
if $WITH_OLLAMA; then
  SERVICES="$SERVICES ollama"
fi

# Use sudo if user isn't in docker group yet (first run)
DOCKER_CMD="docker compose -f $COMPOSE_FILE"
if ! docker info &>/dev/null 2>&1; then
  DOCKER_CMD="sudo docker compose -f $COMPOSE_FILE"
  warn "Using sudo for Docker (re-run after logout/login to skip sudo)"
fi

$DOCKER_CMD up -d $SERVICES
ok "Services starting"

# ---------------------------------------------------------------------------
# 6. Wait for healthy services
# ---------------------------------------------------------------------------
step "Waiting for services to be healthy"

wait_for_service() {
  local name="$1" check="$2" max_wait="${3:-60}"
  local elapsed=0
  while [ $elapsed -lt $max_wait ]; do
    if eval "$check" &>/dev/null 2>&1; then
      ok "$name ready"
      return 0
    fi
    sleep 2
    elapsed=$((elapsed + 2))
  done
  fail "$name not ready after ${max_wait}s"
  return 1
}

wait_for_service "PostgreSQL" "$DOCKER_CMD exec db pg_isready -U clintela" 60
wait_for_service "Redis" "$DOCKER_CMD exec redis redis-cli ping" 30

if $WITH_OLLAMA; then
  wait_for_service "Ollama" "curl -sf http://localhost:11434/api/tags" 90
fi

# ---------------------------------------------------------------------------
# 7. Pull embedding model
# ---------------------------------------------------------------------------
if $WITH_OLLAMA; then
  step "Pulling embedding model (qwen3-embedding:4b — this may take a few minutes)"

  if $DOCKER_CMD exec ollama ollama list 2>/dev/null | grep -q "qwen3-embedding:4b"; then
    ok "Model already pulled"
  else
    $DOCKER_CMD exec ollama ollama pull qwen3-embedding:4b
    ok "Model pulled"
  fi
fi

# ---------------------------------------------------------------------------
# 8. Python environment
# ---------------------------------------------------------------------------
step "Setting up Python environment"

uv sync
ok "Python dependencies installed (.venv created)"

# ---------------------------------------------------------------------------
# 8b. Pre-commit hooks
# ---------------------------------------------------------------------------
step "Installing pre-commit hooks"

if [ -f .pre-commit-config.yaml ]; then
  .venv/bin/pre-commit install
  ok "Pre-commit hooks installed (ruff lint/format, security, Django checks)"
else
  warn "No .pre-commit-config.yaml found — skipping"
fi

# ---------------------------------------------------------------------------
# 9. Database migrations
# ---------------------------------------------------------------------------
step "Running database migrations"

.venv/bin/python manage.py migrate --no-input
ok "Migrations applied"

# ---------------------------------------------------------------------------
# 10. Demo data
# ---------------------------------------------------------------------------
if $WITH_DEMO_DATA; then
  step "Seeding demo data"
  ENABLE_CLINICAL_DATA=True .venv/bin/python manage.py reset_demo
  ok "Demo data loaded"
fi

# ---------------------------------------------------------------------------
# 11. Claude Code (optional)
# ---------------------------------------------------------------------------
if $WITH_CLAUDE_CODE; then
  step "Installing Claude Code"

  # Install fnm (Fast Node Manager) if needed
  if ! command -v fnm &>/dev/null; then
    curl -fsSL https://fnm.vercel.app/install | bash
    export PATH="$HOME/.local/share/fnm:$PATH"
    eval "$(fnm env)"
    ok "fnm installed"
  fi

  # Install Node.js LTS
  if ! command -v node &>/dev/null; then
    fnm install --lts
    fnm use lts-latest
    ok "Node.js $(node --version) installed"
  else
    ok "Node.js $(node --version) already installed"
  fi

  # Install Claude Code
  if ! command -v claude &>/dev/null; then
    npm install -g @anthropic-ai/claude-code
    ok "Claude Code installed ($(claude --version))"
  else
    ok "Claude Code already installed ($(claude --version))"
  fi
fi

# ---------------------------------------------------------------------------
# Deploy key check
# ---------------------------------------------------------------------------
DEPLOY_KEY_MISSING=false
if [ ! -f "$HOME/.ssh/clintela_deploy" ]; then
  DEPLOY_KEY_MISSING=true
fi

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
LAN_IP=$(hostname -I 2>/dev/null | awk '{print $1}' || echo "localhost")

echo ""
echo -e "${GREEN}======================================${NC}"
echo -e "${GREEN}  Clintela dev environment is ready!  ${NC}"
echo -e "${GREEN}======================================${NC}"
echo ""
echo -e "  ${CYAN}Start the dev server:${NC}"
echo "    source .venv/bin/activate"
echo "    python manage.py runserver 0.0.0.0:8001"
echo ""
echo -e "  ${CYAN}Access from your network:${NC}"
echo "    http://${LAN_IP}:8001/"
echo ""
echo -e "  ${CYAN}Logins:${NC}"
echo "    Clinician:  /clinician/login/       dr_smith / testpass123"
echo "    Admin:      /admin-dashboard/login/  admin_test / testpass123"
echo ""
echo -e "  ${CYAN}Useful commands:${NC}"
echo "    make services-up     Start backing services"
echo "    make services-down   Stop backing services"
echo "    make test            Run test suite"
echo "    make dev             Start Django dev server (localhost only)"
echo ""
if [ -f .env ] && grep -q "your-ollama-api-key-here" .env 2>/dev/null; then
  echo -e "  ${YELLOW}Reminder: Edit .env to add your API keys${NC}"
  echo "    - OLLAMA_API_KEY (for LLM chat)"
  echo "    - LANGSMITH_API_KEY (optional, for tracing)"
  echo ""
fi
if $DEPLOY_KEY_MISSING; then
  echo -e "  ${YELLOW}Recommendation: Set up a GitHub deploy key${NC}"
  echo "    ./setup-deploy-key.sh"
  echo "    (Avoids needing ssh -A for git pull/push)"
  echo ""
fi
