# FilingSignal — single-container deployment.
#
# Bundles the FastAPI backend, the built React frontend, and the pre-baked
# data (SQLite buffer + cached ETF prices) into one image. No API key is
# required at runtime: the ranking falls back to rules mode without one, and
# every other endpoint is read-only over the bundled buffer. Set
# ANTHROPIC_API_KEY + ALGO_TRADE_RANKING_MODE=recommender as runtime secrets
# to get Agent #2's cited ranking (one LLM call per buffer version, cached).
#
#   docker build -t filingsignal .
#   docker run -p 7860:7860 filingsignal

# --- Stage 1: build the frontend ---------------------------------------- #
FROM node:20-slim AS frontend
WORKDIR /build/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
# vite.config.ts's mock plugin reads ../backend/mock/v1 relative to repo root
COPY backend/mock /build/backend/mock
# Live-API mode against the same origin; mock JSON ships in dist/ as fallback.
ENV VITE_DATA_SOURCE=api \
    VITE_API_BASE=/api/v1
RUN npm run build

# --- Stage 2: the app ---------------------------------------------------- #
FROM python:3.12-slim
WORKDIR /app

COPY pyproject.toml README.md ./
COPY src ./src
COPY backend ./backend
RUN pip install --no-cache-dir .

# Pre-baked data: the extracted buffer, cached prices, and the frozen Agent #2
# ranking snapshot (backend/scripts/make-ranking-snapshot.py). All gitignored
# in the repo, so build the image from a working tree that has them.
COPY data/buffer.sqlite ./data/buffer.sqlite
COPY data/prices ./data/prices
COPY data/ranking-snapshot.json ./data/ranking-snapshot.json

COPY --from=frontend /build/frontend/dist ./frontend/dist

# All paths explicit: the pip-installed `api` package cannot resolve
# repo-relative defaults from site-packages.
ENV ALGO_TRADE_BUFFER_PATH=/app/data/buffer.sqlite \
    ALGO_TRADE_UNIVERSE_DIR=/app/backend/universe \
    ALGO_TRADE_PRICES_DIR=/app/data/prices \
    ALGO_TRADE_RANKING_SNAPSHOT=/app/data/ranking-snapshot.json \
    ALGO_TRADE_FRONTEND_DIST=/app/frontend/dist

# HuggingFace Spaces injects PORT=7860; default matches for local runs.
EXPOSE 7860
CMD ["sh", "-c", "uvicorn api.main:app --host 0.0.0.0 --port ${PORT:-7860}"]
