# Deliverable 2 -- Technical Artifacts & Configurations

**Project:** TTG Distributed Computation System
**Date:** February 10, 2026
**Version:** 1.3.0
**Author:** Xavier / TTG Team

---

## 1. Overview

This document provides a complete inventory of all technical artifacts, configurations, and operational tools created during the TTG project. Each artifact includes its location, purpose, and key configuration details.

> **NDA Note:** Where an NDA applies, files should be redacted to remove proprietary data while preserving technical structure. Items flagged with `[REDACT-CHECK]` contain environment-specific values (hostnames, paths, credentials) that may need review before external distribution.

---

## 2. Source Code

### Application Code (`src/`)

| File | Version | Lines | Purpose |
|------|---------|-------|---------|
| `src/worker.py` | v1.3.0 | ~400 | Main worker application. Dual mode: static (M1) and queue (M2/M3). Contains `StaticWorker` and `QueueWorker` classes. Handles graceful shutdown (SIGTERM/SIGINT), structured logging, and backend selection via `QUEUE_BACKEND` env var. |
| `src/queue_utils.py` | v1.2.1 | ~250 | Redis Streams wrapper. `TaskQueue` class encapsulating XADD, XREADGROUP, XACK, XCLAIM, XPENDING operations. Manages consumer groups and stale task recovery. |
| `src/rabbitmq_queue.py` | v1.3.0 | ~300 | RabbitMQ wrapper. `RabbitMQTaskQueue` class managing AMQP connections, queue topology declaration (main, retry with TTL, DLQ, results), message publishing and consumption with manual acknowledgment. |
| `src/logging_config.py` | v1.1.0 | ~150 | Structured logging infrastructure. Supports text and JSON output formats. Injects worker context (worker_id, hostname, pod_name, node_name). Includes `@timed` decorator and `log_timing` context manager. |

### Dependencies

| File | Contents |
|------|----------|
| `requirements.txt` | `redis>=4.5.0` (Redis client), `pika>=1.3.0` (RabbitMQ AMQP client). Future dependencies (Prometheus client, OpenTelemetry) commented out. |

---

## 3. Database/Queue Configurations

### Redis Configuration (`k8s/manifests/redis.yaml`)

| Setting | Value | Purpose |
|---------|-------|---------|
| Image | `redis:7.2-alpine` | Lightweight Redis with Streams support |
| Persistence | AOF enabled (`--appendonly yes`) | Data survives pod restarts |
| Storage | 1Gi PersistentVolumeClaim | Durable storage |
| CPU | 100m request / 500m limit | Resource boundaries |
| Memory | 128Mi request / 256Mi limit | Resource boundaries |
| Service | ClusterIP on port 6379 | Internal DNS: `ttg-redis.default.svc.cluster.local` |
| Liveness Probe | `redis-cli ping` every 30s | Auto-restart on failure |
| Readiness Probe | `redis-cli ping` every 10s | Traffic routing |

### RabbitMQ Configuration (`k8s/manifests/rabbitmq.yaml`)

| Setting | Value | Purpose |
|---------|-------|---------|
| Image | `rabbitmq:3.13-management` | RabbitMQ with Management UI plugin |
| Storage | 2Gi PersistentVolumeClaim | Durable message storage |
| CPU | 200m request / 1000m limit | Resource boundaries |
| Memory | 256Mi request / 1Gi limit | Resource boundaries |
| AMQP Service | ClusterIP on port 5672 | Internal DNS: `ttg-rabbitmq.default.svc.cluster.local` |
| Management Service | ClusterIP on port 15672 | Web UI for monitoring |
| Credentials | `guest/guest` `[REDACT-CHECK]` | Default credentials (not production-ready) |
| Liveness Probe | `rabbitmq-diagnostics -q ping` | Auto-restart on failure |

### RabbitMQ Queue Topology

| Queue | Type | Configuration |
|-------|------|---------------|
| `ttg.tasks` | Main task queue | Durable, workers consume via `basic_get` with `prefetch=1` |
| `ttg.results` | Results queue | Durable, workers publish completed results |
| `ttg.tasks.retry` | Retry queue | TTL-based; failed messages re-enter `ttg.tasks` after delay |
| `ttg.tasks.dlq` | Dead-letter queue | Captures messages that exhaust retry attempts |

### Redis Streams Topology

| Stream | Consumer Group | Purpose |
|--------|---------------|---------|
| `ttg:tasks` | `ttg-workers` | Task distribution (XREADGROUP delivers to one consumer) |
| `ttg:results` | N/A | Result storage (XADD by workers) |

---

## 4. Kubernetes Manifests

### Worker Manifests

| File | Mode | Workers | Backend | Use Case |
|------|------|---------|---------|----------|
| `k8s/manifests/parallel-jobs.yaml` | Static (M1) | 3 (indexed Job) | N/A | Baseline parallel execution |
| `k8s/manifests/parallel-jobs-queue.yaml` | Queue (M2) | 3 (indexed Job) | Redis | Queue-based distribution |
| `k8s/manifests/parallel-jobs-queue-rabbitmq.yaml` | Queue (M3) | 3 (indexed Job) | RabbitMQ | RabbitMQ backend |
| `k8s/manifests/parallel-workers-standalone.yaml` | Queue (M2) | 3 (standalone Pods) | Redis | Fault tolerance demos |
| `k8s/manifests/worker-job.yaml` | Static | 1 | N/A | Single worker testing |

### Infrastructure Manifests

| File | Component | Purpose |
|------|-----------|---------|
| `k8s/manifests/redis.yaml` | Redis 7.2 | Task queue + result storage (M2) |
| `k8s/manifests/rabbitmq.yaml` | RabbitMQ 3.13 | Task queue + result storage (M3) |
| `k8s/manifests/redis-insight.yaml` | RedisInsight | Web GUI for Redis monitoring |

### Test Manifests

| File | Purpose |
|------|---------|
| `k8s/manifests/parallel-jobs-fault-test.yaml` | Fault tolerance test (Job-based, discovered limitation) |
| `k8s/manifests/parallel-jobs-fault-demo.yaml` | Fault tolerance demo configuration |
| `k8s/manifests/test-fault-controlled.yaml` | Controlled fault injection test |

### Cluster Configuration

| File | Purpose |
|------|---------|
| `k8s/local/kind-config.yaml` | Kind cluster topology: 1 control-plane + 3 worker nodes |
| `k8s/azure/setup-aks.sh` | Azure AKS cluster provisioning script (documented, not fully deployed) |

---

## 5. Security Settings

### Container Security

| Setting | Location | Value |
|---------|----------|-------|
| Non-root user | `docker/Dockerfile` | `USER ttg-worker` (UID 1000) |
| Read-only filesystem | K8s manifests | `readOnlyRootFilesystem: true` |
| Dropped capabilities | K8s manifests | `drop: ["ALL"]` |
| Minimal base image | `docker/Dockerfile` | `python:3.11-slim` |
| Image pull policy | K8s manifests | `imagePullPolicy: Never` (local Kind) |

### Secrets Management

| Item | Approach |
|------|----------|
| `.gitignore` exclusions | `*.env`, `*.env.local`, `*-secret.yaml`, `aks-config.env` |
| RabbitMQ credentials | Default `guest/guest` -- must be changed for production `[REDACT-CHECK]` |
| Redis authentication | None (cluster-internal access only) |
| TLS/SSL | Not implemented (plain TCP within cluster) -- recommended for production |

---

## 6. Monitoring & Observability

### Monitoring Dashboard Exports

| Tool | Type | Access | Purpose |
|------|------|--------|---------|
| RabbitMQ Management UI | Web Dashboard | `http://localhost:15672` (port-forward) | Queue depths, consumer counts, message rates, connection details |
| RedisInsight | Web GUI | `http://localhost:8001` (port-forward) | Stream inspection, consumer group state, key browser |

### CLI Monitoring Tools

| Script | Language | Purpose |
|--------|----------|---------|
| `scripts/queue_monitor.py` | Python (Rich) | Real-time CLI dashboard for Redis queues: queue depth, pending tasks, worker breakdown, throughput, ETA |
| `scripts/rabbitmq_monitor.sh` | Bash | RabbitMQ queue snapshot via Management API: messages, consumers, unacked, ready counts |
| `scripts/aggregate_results.py` | Python | Post-run analytics: reads Redis results, computes throughput, parallelism factor, timing |

### Logging Configuration

| Setting | Options | Default |
|---------|---------|---------|
| `LOG_FORMAT` | `text` (human-readable) / `json` (machine-parseable) | `text` |
| `LOG_LEVEL` | `DEBUG`, `INFO`, `WARNING`, `ERROR` | `INFO` |
| Context fields | `worker_id`, `hostname`, `pod_name`, `node_name` | Auto-injected |
| Lifecycle events | `STARTING`, `INITIALIZED`, `RUNNING`, `PROGRESS`, `COMPLETED`, `FAILED` | All logged |

---

## 7. Operational Scripts

### Build & Deploy

| Script | Usage | Purpose |
|--------|-------|---------|
| `scripts/build.sh` | `./scripts/build.sh --version 1.3.0 --load-kind` | Build Docker image with OCI labels, load into Kind cluster |
| `scripts/deploy.sh` | `./scripts/deploy.sh --workers 5 --params 100000` | Deploy workers with configurable count and parameters |
| `k8s/local/setup-local.sh` | `./k8s/local/setup-local.sh` | Create Kind cluster from scratch (checks prerequisites, creates 4 nodes, builds image) |

### Demo & Testing

| Script | Usage | Purpose |
|--------|-------|---------|
| `scripts/run-demo.sh` | `./scripts/run-demo.sh --backend rabbitmq --scale small --fault-demo` | Full demo: deploy infra, start workers, inject faults, report results, cleanup |
| `scripts/fault-tolerance-demo.sh` | `./scripts/fault-tolerance-demo.sh` | Dedicated fault tolerance demonstration |

### Safety & Recovery

| Script | Usage | Purpose |
|--------|-------|---------|
| `scripts/cleanup-ttg.sh` | `./scripts/cleanup-ttg.sh --all --dry-run` | Safe cleanup (TTG resources only), preview with dry-run |
| `scripts/recover-infra.sh` | `./scripts/recover-infra.sh` | Recover after reboot: restart Kind containers, redeploy Redis/RabbitMQ |
| `scripts/list-resources.sh` | `./scripts/list-resources.sh` | Inventory of all TTG resources across Docker and Kubernetes |

---

## 8. Docker Configuration

### Dockerfile (`docker/Dockerfile`)

| Feature | Detail |
|---------|--------|
| Build strategy | Multi-stage (builder + runtime) |
| Base image | `python:3.11-slim` |
| User | `ttg-worker` (UID 1000, non-root) |
| Dependencies | Installed via `pip install --no-cache-dir` |
| OCI labels | `org.opencontainers.image.*` (version, source, description, licenses, vendor) |
| TTG labels | `ttg.project`, `ttg.component`, `ttg.version` |
| Build args | `VERSION`, `BUILD_DATE`, `GIT_COMMIT` |

### Build Context

| File | Purpose |
|------|---------|
| `.dockerignore` | Excludes `.git`, `docs/`, `k8s/`, `scripts/`, `*.md`, `__pycache__` from build context |

---

## 9. Documentation Artifacts

### Architecture Documents

| File | Content |
|------|---------|
| `docs/architecture/M2_QUEUE_ARCHITECTURE.md` | Queue broker comparison (Redis Lists, Redis Streams, RabbitMQ, Kafka, Celery), weighted decision matrix, chosen architecture, data flow diagrams, message schemas, implementation timeline |

### Operational Guides

| File | Content |
|------|---------|
| `docs/guides/CONFIGURATION_GUIDE.md` | All environment variables, defaults, and effects |
| `docs/guides/QUEUE_MODE_GUIDE.md` | Running in queue mode (Redis and RabbitMQ), monitoring, troubleshooting |

### Test Results

| File | Content |
|------|---------|
| `docs/results/TEST_RESULTS_M1_PARALLEL_JOBS.md` | M1 build, deployment, logging, and performance test results |
| `docs/results/TEST_RESULTS_M2_FAULT_TOLERANCE.md` | M2 fault tolerance verification (Job vs standalone, demo script, known limitations) |
| `docs/results/TEST_RESULTS_M3_RABBITMQ_MONITORING.md` | M3 backend comparison, medium-scale results, queue stats |

### Supervisor Reports

| File | Content |
|------|---------|
| `SUPERVISOR_REPORT.md` | Executive summary (M1+M2) with demo commands |
| `SUPERVISOR_REPORT_M2.md` | Detailed M2 report with architecture diagrams and technical details |
| `docs/tracking/SUPERVISOR_REPORT_M3_RABBITMQ.md` | M3 report with backend comparison and demo instructions |

### Generated Reports (Word)

| File | Content |
|------|---------|
| `docs/tracking/TTG_Project_Status_Report_M1_M2_M3.docx` | Formal status report (planning, milestones, metrics, test results) |
| `docs/tracking/TTG_PM_Report_PARAGRAPHS.docx` | PM report (paragraph format) |
| `docs/tracking/TTG_PM_Report_TABLES.docx` | PM report (table format) |

---

## 10. Artifact Summary

| Category | Count | Key Files |
|----------|-------|-----------|
| Source code files | 4 | `worker.py`, `queue_utils.py`, `rabbitmq_queue.py`, `logging_config.py` |
| K8s manifests | 11 | Worker, infrastructure, and test manifests |
| Operational scripts | 10 | Build, deploy, demo, cleanup, monitoring, recovery |
| Configuration files | 4 | `kind-config.yaml`, `Dockerfile`, `.gitignore`, `.dockerignore` |
| Documentation files | 21+ | Architecture, guides, results, setup, tracking, knowledge |
| Generated reports | 3 | `.docx` files in `docs/tracking/` |

---

**Report Version:** 1.0
**Prepared By:** Xavier / TTG Team
**Repository:** https://github.com/xmedinavei/ttg-distributed-compute
