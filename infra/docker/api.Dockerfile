FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    git curl build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
RUN pip install --no-cache-dir -e ".[all]"

COPY src/ ./src/
COPY configs/ ./configs/

ENV PYTHONPATH=/app/src

CMD ["uvicorn", "sap_cua.api.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
