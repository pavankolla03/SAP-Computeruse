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
ENV INFERENCE_DEVICE=cuda
ENV MODEL_BASE_PATH=/app/model_registry/sap-cua-7b-v0

EXPOSE 8001

CMD ["python", "-m", "sap_cua.services.inference.server", "--port", "8001"]
