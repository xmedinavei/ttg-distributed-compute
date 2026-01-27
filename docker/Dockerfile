# TTG Distributed Worker Dockerfile
#
# Multi-stage build for a lean production image
# Base image: Python 3.11 slim (Debian-based)
#
# Build:
#   docker build -t ttg-worker:latest -f docker/Dockerfile .
#
# Run locally (for testing):
#   docker run -e WORKER_ID=0 -e TOTAL_WORKERS=3 -e TOTAL_PARAMETERS=1000 ttg-worker:latest

# ============================================
# Stage 1: Build stage (install dependencies)
# ============================================
FROM python:3.11-slim as builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first (for layer caching)
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir --user -r requirements.txt

# ============================================
# Stage 2: Production stage (minimal image)
# ============================================
FROM python:3.11-slim

WORKDIR /app

# Create non-root user for security
RUN useradd --create-home --shell /bin/bash worker

# Copy installed packages from builder
COPY --from=builder /root/.local /home/worker/.local

# Copy application code
COPY src/ ./src/

# Set ownership
RUN chown -R worker:worker /app

# Switch to non-root user
USER worker

# Add local bin to PATH
ENV PATH=/home/worker/.local/bin:$PATH

# Environment variables with defaults
# These can be overridden at runtime
ENV WORKER_ID=0 \
    TOTAL_WORKERS=3 \
    TOTAL_PARAMETERS=10000 \
    BATCH_SIZE=100 \
    SIMULATE_WORK_MS=1 \
    SAVE_OUTPUT=false \
    PYTHONUNBUFFERED=1

# Health check (optional, useful for deployments)
# HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
#     CMD python -c "print('healthy')" || exit 1

# Default command: run the worker
CMD ["python", "src/worker.py"]

# ============================================
# Labels for metadata
# ============================================
LABEL maintainer="TTG Team" \
      version="1.0.0" \
      description="TTG Distributed Computation Worker" \
      org.opencontainers.image.source="https://github.com/ttg/distributed-compute"
