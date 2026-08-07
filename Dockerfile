# syntax=docker/dockerfile:1
# Single self-contained image: FastAPI serves the built SPA + the /api/v1 API on
# one port, with the mock buffer + price CSVs baked in. `docker compose up` and
# open http://localhost:8000.

# ---- stage 1: build the frontend (same-origin API, hydrates from /api/v1) ----
FROM node:20-alpine AS frontend
WORKDIR /fe
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
ENV VITE_API_BASE=/api/v1 VITE_DATA_SOURCE=api
RUN npm run build            # -> /fe/dist

# ---- stage 2: python runtime ----
FROM python:3.12-slim AS app
WORKDIR /app

# Install the package (deps resolve from manylinux wheels; no compilers needed).
# The [backtest] extra is required, not optional: it carries yfinance, without
# which the price fetch below cannot run at all.
COPY pyproject.toml ./
COPY src/ ./src/
RUN pip install --no-cache-dir -e ".[backtest]"

COPY universe/ ./universe/
COPY scripts/ ./scripts/

# Bake the dataset into the image: mock extractions + a synthetic-price fallback,
# then overwrite the fallback with REAL ETF/SPY prices from yfinance when the
# build has network. Offline builds keep the synthetic fallback (build still succeeds).
#
# The import is checked separately, and fatally, on purpose: a missing yfinance
# is a packaging bug that `|| echo` would otherwise disguise as a routine offline
# build - which is exactly how it went unnoticed through several deploys. Only a
# genuine fetch failure (no network, rate limit) is allowed to fall back.
RUN python scripts/seed_mock.py \
 && python -c "import yfinance" \
 && (filingsignal fetch-prices --start 2019-01-01 \
     || echo "offline build: keeping synthetic price fallback")

# Bake the REAL host buffer + prices over the mock, so the image is
# self-contained for cloud deploys with no volume mount (compose still mounts
# ./data over this locally, so local behaviour is unchanged).
COPY data/ ./data/

# Built SPA from stage 1.
COPY --from=frontend /fe/dist ./frontend/dist

ENV FILINGSIGNAL_BUFFER_PATH=/app/data/buffer.sqlite \
    FILINGSIGNAL_PRICES_DIR=/app/data/prices \
    FILINGSIGNAL_UNIVERSE_DIR=/app/universe \
    FILINGSIGNAL_FRONTEND_DIST=/app/frontend/dist \
    FILINGSIGNAL_BACKTEST_SINCE="2024 Q1" \
    FILINGSIGNAL_API_HOST=0.0.0.0 \
    FILINGSIGNAL_API_PORT=8000 \
    PYTHONUNBUFFERED=1

EXPOSE 8000
CMD ["filingsignal", "serve"]
