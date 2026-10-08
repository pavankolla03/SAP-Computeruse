.PHONY: setup dev test build benchmark doctor download-model browser-install
PYTHON ?= python3
setup:
	$(PYTHON) -m pip install -e '.[dev]'
dev:
	$(PYTHON) -m sap_cua.cli serve
test:
	$(PYTHON) -m pytest tests/ -q
build:
	$(PYTHON) -m build
benchmark:
	$(PYTHON) -m sap_cua.cli benchmark
doctor:
	$(PYTHON) -m sap_cua.cli doctor
download-model:
	$(PYTHON) -m sap_cua.cli download-model
browser-install:
	$(PYTHON) -m playwright install chromium
