#!/usr/bin/env bash
set -euo pipefail

# sap-cua bootstrap — one command to provision the development environment
# Usage: ./scripts/bootstrap.sh [--gpu] [--no-docker] [--ci]

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

GPU_MODE=false
DOCKER_MODE=true
CI_MODE=false

for arg in "$@"; do
  case "$arg" in
    --gpu) GPU_MODE=true ;;
    --no-docker) DOCKER_MODE=false ;;
    --ci) CI_MODE=true ;;
    *)
      echo "Unknown flag: $arg"
      echo "Usage: $0 [--gpu] [--no-docker] [--ci]"
      exit 1
      ;;
  esac
done

echo "=== SAP-CUA Bootstrap ==="
echo "  Project: $PROJECT_ROOT"
echo "  GPU: $GPU_MODE"
echo "  Docker: $DOCKER_MODE"
echo ""

# Detect platform
OS="$(uname -s)"
ARCH="$(uname -m)"

echo "[1/6] Detecting platform: $OS/$ARCH"
if [[ "$OS" == "Darwin" && "$GPU_MODE" == true ]]; then
  echo "WARNING: Apple Silicon detected. GPU training requires Metal/MLX or remote GPU."
  echo "         Falling back to CPU/mock mode for local development."
  GPU_MODE=false
fi

# Python version check
echo "[2/6] Checking Python..."
PYTHON_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>/dev/null || echo "none")
if [[ "$PYTHON_VERSION" == "none" ]]; then
  echo "ERROR: Python 3.11+ required. Install from python.org."
  exit 1
fi
echo "  Python $PYTHON_VERSION"

# Install dependencies
echo "[3/6] Installing dependencies..."
pip install --upgrade pip 2>/dev/null || pip3 install --upgrade pip
pip install poetry 2>/dev/null || pip3 install poetry

if [[ -f "pyproject.toml" ]]; then
  if command -v poetry &>/dev/null; then
    poetry install --with dev 2>&1 | tail -5 || true
  else
    pip install -e ".[all]" 2>&1 | tail -5 || true
  fi
fi

# Create directories
echo "[4/6] Creating directories..."
mkdir -p datasets/{raw,sanitized,grounding,transitions,trajectories,failures,benchmark}
mkdir -p model_registry infra/gpu/jobs logs reports scripts tests

# Docker services
if [[ "$DOCKER_MODE" == true ]]; then
  echo "[5/6] Starting Docker services..."
  if command -v docker-compose &>/dev/null || command -v docker &>/dev/null; then
    docker compose -f infra/docker/docker-compose.yml up -d postgres redis minio 2>&1 || true
    echo "  Waiting for services..."
    sleep 5
  else
    echo "  Docker not available, skipping services"
  fi
else
  echo "[5/6] Docker disabled, skipping services"
fi

# Run tests
echo "[6/6] Running tests..."
if [[ "$CI_MODE" == true ]]; then
  python -m pytest tests/ -v --tb=short --no-header 2>&1 | tail -20 || true
else
  python -m pytest tests/ -v --tb=short 2>&1 | tail -20 || true
fi

echo ""
echo "=== Bootstrap complete ==="
echo "  API:          http://localhost:8000"
echo "  Dashboard:    http://localhost:3000"
echo "  MLflow:       http://localhost:5000"
echo "  MinIO:        http://localhost:9000"
echo ""
