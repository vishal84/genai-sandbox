# Copyright 2026 Google LLC
# Stage 1: Build the React + Vite frontend
FROM node:20-slim AS frontend-builder

WORKDIR /build
COPY frontend/package*.json ./
RUN npm ci --silent || npm install --silent
COPY frontend/ ./
RUN npm run build

# Stage 2: Python runtime with ADK 2.0 and FastAPI
FROM python:3.12-slim

RUN pip install --no-cache-dir uv==0.8.13

WORKDIR /code

COPY ./pyproject.toml ./README.md ./uv.lock* ./
COPY ./app ./app

# Copy built frontend assets to app/static
COPY --from=frontend-builder /code/app/static ./app/static

RUN uv sync

ARG COMMIT_SHA=""
ENV COMMIT_SHA=${COMMIT_SHA}

ARG AGENT_VERSION=0.1.0
ENV AGENT_VERSION=${AGENT_VERSION}

EXPOSE 8080

CMD ["uv", "run", "uvicorn", "app.fast_api_app:app", "--host", "0.0.0.0", "--port", "8080"]

