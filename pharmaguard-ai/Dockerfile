# ==============================================================================
# PharmaGuard AI — Production Multi-Stage Dockerfile
# ==============================================================================

# Stage 1: Build & Dependency Resolution
FROM python:3.11-slim AS builder

WORKDIR /build

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt .
RUN pip install --user --no-warn-script-location -r requirements.txt


# Stage 2: Hardened Production Runtime Image
FROM python:3.11-slim AS runner

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH=/root/.local/bin:$PATH \
    APP_ENV=production

# Install essential runtime system libraries (libpq for PostgreSQL, curl for healthchecks)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create non-root application user
RUN groupadd -g 1001 pharmagroup && \
    useradd -u 1001 -g pharmagroup -s /bin/bash -m pharmauser

# Copy installed python dependencies from builder
COPY --from=builder /root/.local /home/pharmauser/.local
ENV PATH=/home/pharmauser/.local/bin:$PATH

# Copy backend source code
COPY --chown=pharmauser:pharmagroup backend/ /app/

# Switch to non-root user
USER pharmauser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
