FROM python:3.12-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /build

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY services/user-service/pyproject.toml services/user-service/pyproject.toml
COPY services/user-service/app services/user-service/app

WORKDIR /build/services/user-service

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir --prefix=/install .

FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app/services/user-service

COPY --from=builder /install /usr/local

COPY services/user-service /app/services/user-service

RUN useradd --create-home --uid 10002 appuser \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 8002

HEALTHCHECK --interval=15s --timeout=5s --retries=10 CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8002/v1/health/live', timeout=2)"]

CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8002"]
