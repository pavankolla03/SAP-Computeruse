.PHONY: help setup dev test train-sft train-rl serve-model benchmark recorder clean docker-build docker-up docker-down

SHELL := /bin/bash
PYTHON := python3
PIP := pip
PROJECT := sap-cua

help: ## Show this help message
	@echo 'Usage: make [target]'
	@echo ''
	@echo 'Available targets:'
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  %-15s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

setup: ## Bootstrap the development environment
	@echo "=== Setting up $(PROJECT) development environment ==="
	$(PIP) install --upgrade pip
	$(PIP) install poetry
	poetry install
	pre-commit install || true
	@echo "=== Creating data directories ==="
	mkdir -p datasets/raw datasets/sanitized datasets/grounding datasets/trajectories datasets/benchmark
	mkdir -p model_registry infra/gpu/jobs
	@echo "=== Setup complete ==="

dev: ## Start all development services
	docker-compose -f infra/docker/docker-compose.yml up -d
	@echo "=== Services started ==="
	@echo "API: http://localhost:8000"
	@echo "Dashboard: http://localhost:3000"
	@echo "MLflow: http://localhost:5000"
	@echo "MinIO: http://localhost:9000"

docker-build: ## Build Docker images
	docker-compose -f infra/docker/docker-compose.yml build

docker-up: ## Start Docker stack
	docker-compose -f infra/docker/docker-compose.yml up -d

docker-down: ## Stop Docker stack
	docker-compose -f infra/docker/docker-compose.yml down

test: ## Run test suite
	$(PYTHON) -m pytest tests/ -v --tb=short --cov=sap_cua --cov-report=term-missing

test-unit: ## Run unit tests only
	$(PYTHON) -m pytest tests/unit/ -v

test-integration: ## Run integration tests
	$(PYTHON) -m pytest tests/integration/ -v

test-e2e: ## Run end-to-end tests
	playwright install chromium
	$(PYTHON) -m pytest tests/e2e/ -v

benchmark: ## Run SAPBench benchmark
	$(PYTHON) -m sap_cua.evaluation.sapbench.runner --suite sapbench-v1 --output results/

recorder: ## Start the recorder UI
	$(PYTHON) -m sap_cua.recorder.app --port 8080

serve-model: ## Serve the model with vLLM or transformers
	@if [ "$(USE_VLLM)" = "true" ]; then \
		vllm serve sap-cua-7b-v0 --port 8001 --gpu-memory-utilization $(VLLM_GPU_MEMORY_UTILIZATION); \
	else \
		$(PYTHON) -m sap_cua.services.inference.server --port 8001; \
	fi

train-sft: ## Run SFT training
	$(PYTHON) -m sap_cua.training.sft.train \
		--dataset $(TRAJECTORY_DATASET) \
		--output model_registry/sap-cua-7b-v0-sft \
		--config configs/sft_lora.yaml

train-rl: ## Run RL training
	$(PYTHON) -m sap_cua.training.rl.train \
		--suite sapbench-train \
		--base-model model_registry/sap-cua-7b-v0-sft \
		--output model_registry/sap-cua-7b-v0-rl

train-grounding: ## Run grounding pretraining
	$(PYTHON) -m sap_cua.training.grounding.train \
		--dataset $(GROUNDING_DATASET) \
		--output model_registry/sap-cua-7b-v0-grounding

train-recovery: ## Run recovery training
	$(PYTHON) -m sap_cua.training.recovery.train \
		--dataset $(RECOVERY_DATASET) \
		--base-model model_registry/sap-cua-7b-v0-sft \
		--output model_registry/sap-cua-7b-v0-recovery

train-transition: ## Run state transition pretraining
	$(PYTHON) -m sap_cua.training.transition.train \
		--dataset datasets/transitions/sap-transitions-v1 \
		--output model_registry/sap-cua-7b-v0-transition

eval-benchmark: ## Run full benchmark evaluation
	$(PYTHON) -m sap_cua.evaluation.runner \
		--suite sapbench-v1 \
		--models sap-cua-7b-v0,OpenCUA-7B,UI-TARS-1.5-7B \
		--runs 5 \
		--output results/

lint: ## Run linter
	ruff check sap_cua/ tests/ scripts/

format: ## Format code
	ruff format sap_cua/ tests/ scripts/
	$(PYTHON) -m py_compile sap_cua/**/*.py

typecheck: ## Run type checker
	mypy sap_cua/ --ignore-missing-imports

security-scan: ## Run security scan
	bandit -r sap_cua/ -f json -o reports/security.json || true
	trufflehog filesystem . --json > reports/secrets.json || true

dataset-validate: ## Validate dataset schemas
	$(PYTHON) -m sap_cua.datasets.validate_all

experiment-register: ## Register current experiment
	$(PYTHON) -m sap_cua.experiments.register

clean: ## Clean build artifacts
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true

migrate: ## Run database migrations
	alembic upgrade head

migrate-create: ## Create a new migration
	@read -p "Migration message: " msg; \
	alembic revision --autogenerate -m "$$msg"
