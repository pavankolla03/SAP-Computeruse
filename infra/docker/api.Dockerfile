FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml README.md LICENSE ./
COPY src ./src
RUN pip install --no-cache-dir .
RUN useradd --create-home app && mkdir -p /data && chown app:app /data
USER app
ENV SAP_CUA_DATA_DIR=/data
ENV SAP_CUA_ALLOW_CONTAINER=1
EXPOSE 8000
CMD ["sap-cua", "serve", "--host", "0.0.0.0", "--port", "8000"]
