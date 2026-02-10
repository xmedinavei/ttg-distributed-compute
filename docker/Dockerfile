# TTG Distributed Worker Dockerfile
#
# Multi-stage build for a lean production image
# Base image: Python 3.11 slim (Debian-based)
#
# Build with versioning:
#   docker build -t ttg-worker:v1.1.0 -f docker/Dockerfile \
#     --build-arg VERSION=1.1.0 \
#     --build-arg BUILD_DATE=$(date -u +"%Y-%m-%dT%H:%M:%SZ") \
#     --build-arg GIT_COMMIT=$(git rev-parse --short HEAD) .
#
# Run locally (for testing):
#   docker run --name ttg-worker-test-0 \
#     -e WORKER_ID=0 -e TOTAL_WORKERS=3 -e TOTAL_PARAMETERS=1000 \
#     ttg-worker:v1.1.0

# ============================================
# Build arguments for versioning
# ============================================
ARG VERSION=1.1.0
ARG BUILD_DATE=unknown
ARG GIT_COMMIT=unknown

# ============================================
# Stage 1: Build stage (install dependencies)
# ============================================
FROM python:3.11-slim AS builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first (for layer caching)
COPY requirements.txt .

# Install Python dependencies to a known location
RUN pip install --no-cache-dir --target=/app/deps -r requirements.txt

# ============================================
# Stage 2: Production stage (minimal image)
# ============================================
FROM python:3.11-slim

WORKDIR /app

# Create non-root user for security
RUN useradd --create-home --shell /bin/bash worker

# Copy installed packages from builder
COPY --from=builder /app/deps /home/worker/.local/lib/python3.11/site-packages

# Copy application code
COPY src/ ./src/

# Set ownership
RUN chown -R worker:worker /app

# Switch to non-root user
USER worker

# Add local bin to PATH and set PYTHONPATH
ENV PATH=/home/worker/.local/bin:$PATH \
    PYTHONPATH=/home/worker/.local/lib/python3.11/site-packages

# Environment variables with defaults
# These can be overridden at runtime
# 
# MILESTONE 1 (Static Mode):
#   WORKER_ID, TOTAL_WORKERS, TOTAL_PARAMETERS, BATCH_SIZE
#
# MILESTONE 2+ (Queue Mode):
#   USE_QUEUE=true, QUEUE_BACKEND=redis|rabbitmq
#   Redis: REDIS_HOST, REDIS_PORT
#   RabbitMQ: RABBITMQ_HOST, RABBITMQ_PORT
#   Shared: CHUNK_SIZE, IDLE_TIMEOUT_SECONDS
#
ENV WORKER_ID=0 \
    TOTAL_WORKERS=3 \
    TOTAL_PARAMETERS=10000 \
    BATCH_SIZE=100 \
    SIMULATE_WORK_MS=1 \
    SAVE_OUTPUT=false \
    PYTHONUNBUFFERED=1 \
    LOG_LEVEL=INFO \
    LOG_FORMAT=text \
    # Milestone 2: Queue mode settings
    USE_QUEUE=false \
    QUEUE_BACKEND=redis \
    REDIS_HOST=ttg-redis \
    REDIS_PORT=6379 \
    RABBITMQ_HOST=ttg-rabbitmq \
    RABBITMQ_PORT=5672 \
    RABBITMQ_MAX_RETRIES=3 \
    RABBITMQ_RETRY_DELAY_MS=5000 \
    CHUNK_SIZE=100 \
    IDLE_TIMEOUT_SECONDS=30 \
    SIMULATE_FAULT_RATE=0.0

# Health check (optional, useful for deployments)
# HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
#     CMD python -c "print('healthy')" || exit 1

# Default command: run the worker
CMD ["python", "src/worker.py"]

# ============================================
# OCI Labels for metadata and identification
# These help identify which containers/images
# belong to the TTG project
# ============================================
ARG VERSION
ARG BUILD_DATE
ARG GIT_COMMIT

LABEL org.opencontainers.image.title="TTG Distributed Worker" \
      org.opencontainers.image.description="Distributed computation worker for the TTG project" \
      org.opencontainers.image.version="${VERSION}" \
      org.opencontainers.image.created="${BUILD_DATE}" \
      org.opencontainers.image.revision="${GIT_COMMIT}" \
      org.opencontainers.image.vendor="TTG Team" \
      org.opencontainers.image.source="https://github.com/ttg/distributed-compute" \
      org.opencontainers.image.licenses="MIT" \
      # Custom TTG labels for easy identification
      ttg.project="distributed-compute" \
      ttg.component="worker" \
      ttg.version="${VERSION}"
