#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
SAP_CUA_PYTHON="${SAP_CUA_PYTHON:-python3}"
"$SAP_CUA_PYTHON" -c 'import sys; assert sys.version_info >= (3,11), "Python 3.11+ required"'
"$SAP_CUA_PYTHON" -m venv .venv
.venv/bin/python -m pip install -e '.[dev]'
.venv/bin/python -m pytest tests/ -q
printf '\nSetup verified. Start with .venv/bin/sap-cua serve\n'
