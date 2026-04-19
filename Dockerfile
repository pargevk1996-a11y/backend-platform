# syntax=docker/dockerfile:1.7
#
# Multi-stage, reproducible production image for backend-platform microservices.
# Targets: auth-service, user-service, api-gateway, notification-service.
# Build one with: docker build --target auth-service -t bp/auth:$(git rev-parse --short HEAD) .
#

ARG PYTHON_VERSION=3.12.11-slim-bookworm

############################
# 1) Patched base
############################
FROM python:${PYTHON_VERSION} AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_ROOT_USER_ACTION=ignore

RUN apt-get update \
    && apt-get upgrade -y \
    && apt-get install -y --no-install-recommends tini ca-certificates \
    && apt-get purge -y --auto-remove \
    && rm -rf /var/lib/apt/lists/* /var/cache/apt/archives/* \
    && groupadd --system app \
    && useradd --system --create-home --shell /usr/sbin/nologin --gid app --uid 10000 appuser \
    && pip install --upgrade "pip==24.2"

############################
# 2) Builder with toolchain
############################
FROM base AS builder
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential libpq-dev \
    && rm -rf /var/lib/apt/lists/*

############################
# 2b) shared-python wheel (consumed by every service)
############################
FROM builder AS shared-wheel
WORKDIR /build
COPY shared/python /build/shared-python
RUN pip wheel --wheel-dir=/wheels /build/shared-python

############################
# 3) Per-service wheel builds
############################
FROM builder AS auth-wheels
WORKDIR /build
COPY --from=shared-wheel /wheels /wheels
COPY services/auth-service/pyproject.toml services/auth-service/requirements.lock /build/
COPY services/auth-service /build/src
RUN pip wheel --wheel-dir=/wheels --find-links=/wheels -r /build/requirements.lock \
    && pip wheel --wheel-dir=/wheels --no-deps /build/src

FROM builder AS user-wheels
WORKDIR /build
COPY --from=shared-wheel /wheels /wheels
COPY services/user-service/pyproject.toml services/user-service/requirements.lock /build/
COPY services/user-service /build/src
RUN pip wheel --wheel-dir=/wheels --find-links=/wheels -r /build/requirements.lock \
    && pip wheel --wheel-dir=/wheels --no-deps /build/src

FROM builder AS gateway-wheels
WORKDIR /build
COPY --from=shared-wheel /wheels /wheels
COPY services/api-gateway/pyproject.toml services/api-gateway/requirements.lock /build/
COPY services/api-gateway /build/src
RUN pip wheel --wheel-dir=/wheels --find-links=/wheels -r /build/requirements.lock \
    && pip wheel --wheel-dir=/wheels --no-deps /build/src

FROM builder AS notification-wheels
WORKDIR /build
COPY --from=shared-wheel /wheels /wheels
COPY services/notification-service/pyproject.toml services/notification-service/requirements.lock /build/
COPY services/notification-service /build/src
RUN pip wheel --wheel-dir=/wheels --find-links=/wheels -r /build/requirements.lock \
    && pip wheel --wheel-dir=/wheels --no-deps /build/src

############################
# 4) Runtime images
############################
FROM base AS auth-service
WORKDIR /app
COPY --from=auth-wheels /wheels /wheels
RUN pip install --no-cache-dir --no-index --find-links=/wheels /wheels/*.whl \
    && rm -rf /wheels
COPY --chown=appuser:app services/auth-service/app /app/app
COPY --chown=appuser:app services/auth-service/alembic.ini /app/alembic.ini
COPY --chown=appuser:app services/auth-service/migrations /app/migrations
USER appuser
EXPOSE 8001
ENTRYPOINT ["/usr/bin/tini", "--"]
HEALTHCHECK --interval=15s --timeout=5s --retries=10 --start-period=10s \
  CMD python -c "import urllib.request,sys; r=urllib.request.urlopen('http://127.0.0.1:8001/v1/health/live',timeout=2); sys.exit(0 if r.status==200 else 1)"
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port 8001 --workers ${UVICORN_WORKERS:-2}"]


FROM base AS user-service
WORKDIR /app
COPY --from=user-wheels /wheels /wheels
RUN pip install --no-cache-dir --no-index --find-links=/wheels /wheels/*.whl \
    && rm -rf /wheels
COPY --chown=appuser:app services/user-service/app /app/app
COPY --chown=appuser:app services/user-service/alembic.ini /app/alembic.ini
COPY --chown=appuser:app services/user-service/migrations /app/migrations
USER appuser
EXPOSE 8002
ENTRYPOINT ["/usr/bin/tini", "--"]
HEALTHCHECK --interval=15s --timeout=5s --retries=10 --start-period=10s \
  CMD python -c "import urllib.request,sys; r=urllib.request.urlopen('http://127.0.0.1:8002/v1/health/live',timeout=2); sys.exit(0 if r.status==200 else 1)"
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port 8002 --workers ${UVICORN_WORKERS:-2}"]


FROM base AS api-gateway
WORKDIR /app
COPY --from=gateway-wheels /wheels /wheels
RUN pip install --no-cache-dir --no-index --find-links=/wheels /wheels/*.whl \
    && rm -rf /wheels
COPY --chown=appuser:app services/api-gateway/app /app/app
USER appuser
EXPOSE 8000
ENTRYPOINT ["/usr/bin/tini", "--"]
HEALTHCHECK --interval=15s --timeout=5s --retries=10 --start-period=10s \
  CMD python -c "import urllib.request,sys; r=urllib.request.urlopen('http://127.0.0.1:8000/v1/health/live',timeout=2); sys.exit(0 if r.status==200 else 1)"
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers ${UVICORN_WORKERS:-2}"]


FROM base AS notification-service
WORKDIR /app
COPY --from=notification-wheels /wheels /wheels
RUN pip install --no-cache-dir --no-index --find-links=/wheels /wheels/*.whl \
    && rm -rf /wheels
COPY --chown=appuser:app services/notification-service/app /app/app
USER appuser
EXPOSE 8003
ENTRYPOINT ["/usr/bin/tini", "--"]
HEALTHCHECK --interval=15s --timeout=5s --retries=10 --start-period=10s \
  CMD python -c "import urllib.request,sys; r=urllib.request.urlopen('http://127.0.0.1:8003/v1/health/live',timeout=2); sys.exit(0 if r.status==200 else 1)"
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port 8003 --workers ${UVICORN_WORKERS:-1}"]
