FROM node:22-bookworm-slim AS ui
WORKDIR /build
COPY package.json package-lock.json ./
RUN npm ci
COPY frontend/ frontend/
COPY tailwind.config.js ./
COPY backend/app/templates/ backend/app/templates/
COPY backend/app/static/ backend/app/static/
RUN npm run build:ui

FROM python:3.14-slim-bookworm AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    APP_ENV=production
WORKDIR /app
COPY requirements.txt ./
RUN python -m pip install --no-cache-dir -r requirements.txt \
    && groupadd --gid 10001 app \
    && useradd --uid 10001 --gid app --no-create-home app \
    && mkdir /app/data \
    && chown app:app /app/data
COPY backend/__init__.py backend/__init__.py
COPY backend/app/ backend/app/
COPY knowledge/ knowledge/
COPY --from=ui /build/backend/app/static/vendor/ backend/app/static/vendor/
COPY scripts/container_healthcheck.py scripts/container_healthcheck.py
USER app
EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=5s --start-period=60s --retries=6 \
    CMD ["python", "scripts/container_healthcheck.py"]
# One synchronous worker serializes writes to the current JSON file storage.
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "1", "--threads", "1", "--timeout", "120", "--access-logfile", "-", "--error-logfile", "-", "backend.app.app:app"]
