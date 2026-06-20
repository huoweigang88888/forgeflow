# =============================================================================
# ForgeFlow AI - API Dockerfile
# =============================================================================
# Multi-stage build for Python FastAPI application.
#
# Build:
#   docker build -t forgeflow-api -f apps/api/Dockerfile .
# Run:
#   docker run -p 8000:8000 --env-file .env forgeflow-api

# ---- Stage 1: Build dependencies ----
FROM python:3.11-slim AS builder

WORKDIR /app

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Install project dependencies
COPY apps/api/pyproject.toml apps/api/uv.lock* ./
RUN uv sync --frozen --no-dev --no-install-project

# ---- Stage 2: Runtime ----
FROM python:3.11-slim AS runtime

WORKDIR /app

# Create non-root user
RUN groupadd -r forgeflow && useradd -r -g forgeflow forgeflow

# Copy dependencies from builder
COPY --from=builder /app/.venv /app/.venv

# Copy application code
COPY apps/api/src/ /app/src/
COPY apps/api/alembic.ini /app/

# Set environment
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PATH="/app/.venv/bin:$PATH"

# Switch to non-root user
USER forgeflow

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/health')"

# Run the application
CMD ["uvicorn", "forgeflow.main:app", "--host", "0.0.0.0", "--port", "8000"]
