# Deliverable 1 -- Optimization & Performance Report

**Project:** TTG Distributed Computation System
**Date:** February 10, 2026
**Version:** 1.3.0
**Author:** Xavier / TTG Team

---

## 1. Executive Summary

This report documents the performance optimization journey of the TTG Distributed Computation System across three milestones. Starting from a basic static distribution model (M1), we implemented dynamic queue-based distribution with Redis Streams (M2), added a production-grade RabbitMQ backend (M3), and hardened the infrastructure with security, persistence, and operational tooling.

**Key result:** The system evolved from a fragile static model with zero fault tolerance to a dual-backend, fault-tolerant distributed system that achieves **100% task completion with zero data loss** even when workers are killed mid-processing.

---

## 2. Baseline Performance (Milestone 1)

**Date:** January 27, 2026
**Architecture:** Static range partitioning with Kubernetes Jobs

### How It Worked

Each worker was pre-assigned a fixed range of parameters at startup using its `JOB_COMPLETION_INDEX`. Worker 0 got parameters 0-3,333, Worker 1 got 3,334-6,666, and Worker 2 got 6,667-9,999. There was no coordination between workers -- each processed its range independently and wrote results to stdout.

### Baseline Metrics

| Metric                     | Value                           |
|----------------------------|---------------------------------|
| Total Parameters Processed | 10,000                          |
| Number of Workers          | 3 (parallel)                    |
| Kubernetes Nodes           | 4 (1 control-plane + 3 workers) |
| Total Execution Time       | ~8-9 seconds                    |
| Throughput (per worker)    | ~499 params/sec                 |
| Throughput (aggregate)     | ~1,250-1,500 params/sec         |
| Success Rate               | 100%                            |
| Docker Image Size          | 186 MB                          |

### Baseline Limitations

| Limitation | Impact | Severity |
|-----------|--------|----------|
| No fault tolerance | If a worker dies, its parameter range is permanently lost | Critical |
| Static load balancing | Fast workers sit idle while slow workers finish | Medium |
| No dynamic scaling | Adding/removing workers requires redeployment | Medium |
| No visibility | No way to see progress except parsing logs | Low |
| All-or-nothing | Cannot pause, resume, or prioritize work | Low |

---

## 3. Optimization 1 -- Dynamic Queue Distribution (Milestone 2)

**Date:** February 3, 2026
**Architecture:** Redis Streams with Consumer Groups

### What Changed

Static range assignment was replaced with a Redis Streams message queue. Work is split into 100 chunks and pushed into a shared queue. Workers pull chunks dynamically using `XREADGROUP` and acknowledge completion with `XACK`. If a worker dies before acknowledging, the chunk is reclaimed by another worker via `XCLAIM` after a 30-second timeout.

### Key Optimizations Implemented

1. **Dynamic task distribution:** Workers pull the next available chunk instead of being pre-assigned ranges. Faster workers automatically get more work.
2. **Fault tolerance via XCLAIM:** Unacknowledged tasks are reclaimed after a configurable stale threshold, ensuring zero data loss.
3. **Consumer Groups:** Redis Streams Consumer Groups ensure each chunk is delivered to exactly one worker (no duplicates).
4. **Standalone Pods:** Moved from Kubernetes Jobs to standalone Pods so that killing one worker does not cascade to others (Jobs with `backoffLimit: 0` terminate all pods on any failure).
5. **Graceful shutdown:** Workers handle SIGTERM/SIGINT signals for clean termination.

### Before/After Comparison (M1 vs M2)

| Metric | M1 (Before) | M2 (After) | Change |
|--------|-------------|------------|--------|
| Task Distribution | Static (pre-calculated) | Dynamic (queue-based) | Eliminated idle workers |
| Fault Tolerance | None | Verified (XCLAIM recovery) | Critical improvement |
| Worker Killed at 30% | All work lost | 100/100 chunks completed | Zero data loss |
| Monitoring | Logs only | RedisInsight + CLI monitor | Real-time visibility |
| Scaling Model | Fixed at deploy time | Add/remove workers on-the-fly | Elastic scaling |
| Cleanup Safety | Manual | Safe script with dry-run | Operational safety |

### Fault Tolerance Test Results

| Metric               | Result                    |
|----------------------|---------------------------|
| Total Chunks         | 100/100 completed         |
| Workers Deployed     | 3 (standalone pods)       |
| Worker Killed At     | 30% progress              |
| Completion Time      | 44 seconds                |
| Throughput           | 22 params/sec             |
| Data Loss            | ZERO                      |
| Recovery Mechanism   | XCLAIM (stale task reclaim) |

### Full Scale Test Results (No Fault Injection)

| Metric                     | Value                 |
|----------------------------|-----------------------|
| Total Parameters Processed | 10,000                |
| Number of Workers          | 3 (queue-based)       |
| Task Chunks                | 100 (100 params each) |
| Wall Clock Time            | ~8 seconds            |
| Effective Throughput       | 1,276 params/sec      |
| Parallelism Factor         | 2.53x speedup         |
| Success Rate               | 100%                  |

---

## 4. Optimization 2 -- Production Queue Backend (Milestone 3)

**Date:** February 9, 2026
**Architecture:** Dual-backend (Redis Streams + RabbitMQ)

### What Changed

RabbitMQ was added as a production-grade alternative to Redis Streams. The worker selects the backend via the `QUEUE_BACKEND` environment variable (`redis` or `rabbitmq`). RabbitMQ provides richer operational semantics: retry queues with configurable TTL, dead-letter queues (DLQ), and a built-in management UI.

### Key Optimizations Implemented

1. **RabbitMQ backend:** AMQP-based message broker with built-in retry and DLQ semantics.
2. **Retry queue with TTL:** Failed tasks automatically re-enter the main queue after a configurable delay.
3. **Dead-Letter Queue:** Tasks that exhaust retries are routed to a DLQ for manual inspection.
4. **Management UI:** Real-time web dashboard showing queue depths, consumer counts, and message rates.
5. **Dual-backend toggle:** Single environment variable switches between Redis and RabbitMQ; Redis preserved as rollback-safe fallback.
6. **Unified demo script:** `run-demo.sh` supports both backends with identical CLI interface.

### Backend Comparison (Small Scale -- 1,000 Parameters)

| Metric | Redis (no fault) | RabbitMQ (no fault) | Redis (fault) | RabbitMQ (fault) |
|--------|------------------|---------------------|---------------|------------------|
| Chunks | 100/100 | 100/100 | 100/100 | 100/100 |
| Runtime | 36s | 39s | 48s | 49s |
| Throughput | 27 p/s | 25 p/s | 20 p/s | 20 p/s |
| Recovery | XCLAIM | Auto-requeue | XCLAIM | Auto-requeue |
| Data Loss | ZERO | ZERO | ZERO | ZERO |

### Backend Comparison (Medium Scale -- 10,000 Parameters)

| Metric | Redis (medium) | RabbitMQ (medium) |
|--------|---------------|-------------------|
| Chunks | 100/100 | 100/100 |
| Runtime | 41s | 38-39s |
| Throughput | 243 p/s | 256-263 p/s |
| Data Loss | ZERO | ZERO |

### Key Observations

- Both backends achieve 100% completion with zero data loss under all test conditions.
- At medium scale (10K params), RabbitMQ is slightly faster (256-263 p/s vs 243 p/s).
- Throughput drops ~20-25% under fault conditions (2 vs 3 workers) -- expected and proportional.
- RabbitMQ provides richer operational visibility (retry queue, DLQ, management UI).
- Redis remains as a tested, simpler fallback path.

---

## 5. Optimization 3 -- Infrastructure Hardening

Throughout all milestones, we implemented progressive infrastructure hardening:

### Container Security

| Hardening Measure | Implementation |
|-------------------|----------------|
| Non-root user | Dockerfile creates `ttg-worker` user (UID 1000) |
| Read-only filesystem | `readOnlyRootFilesystem: true` in SecurityContext |
| Dropped capabilities | `drop: ["ALL"]` in SecurityContext |
| Minimal base image | `python:3.11-slim` (not full Python image) |
| OCI labels | Image traceability (version, git commit, build date) |

### Kubernetes Resource Management

| Resource | Request | Limit |
|----------|---------|-------|
| Worker CPU | 100m | 500m |
| Worker Memory | 128Mi | 256Mi |
| Redis CPU | 100m | 500m |
| Redis Memory | 128Mi | 256Mi |
| RabbitMQ CPU | 200m | 1000m |
| RabbitMQ Memory | 256Mi | 1Gi |

### Data Persistence

| Component | Storage | Persistence Method |
|-----------|---------|-------------------|
| Redis | 1Gi PVC | AOF (Append-Only File) |
| RabbitMQ | 2Gi PVC | Mnesia database |

### Health Monitoring

| Component | Liveness Probe | Readiness Probe |
|-----------|---------------|-----------------|
| Redis | `redis-cli ping` | `redis-cli ping` |
| RabbitMQ | `rabbitmq-diagnostics -q ping` | `rabbitmq-diagnostics -q ping` |
| Workers | Process exit code | N/A (run-to-completion) |

### Operational Safety

| Tool | Purpose |
|------|---------|
| `cleanup-ttg.sh` | TTG-only resource cleanup with `--dry-run` preview |
| `recover-infra.sh` | Infrastructure recovery after reboot |
| `list-resources.sh` | Resource inventory across Docker and Kubernetes |
| Structured logging | Text and JSON formats with worker context injection |

---

## 6. Consolidated Before/After Summary

### Architecture Evolution

| Aspect | M1 (Baseline) | M2 (Redis Queue) | M3 (Dual Backend) |
|--------|---------------|-------------------|-------------------|
| Distribution | Static partitioning | Dynamic queue | Dynamic queue (dual) |
| Fault Tolerance | None | XCLAIM recovery | XCLAIM + auto-requeue |
| Queue Backend | N/A | Redis Streams | Redis + RabbitMQ |
| Retry Logic | None | Stale check + XCLAIM | Retry queue + DLQ |
| Monitoring | Logs only | RedisInsight + CLI | RabbitMQ UI + CLI |
| Scaling | Fixed at deploy | Add workers on-the-fly | Add workers on-the-fly |
| Cleanup | Manual | Safe script | Safe script (TTG-only) |
| Security | Basic | Non-root, resource limits | Non-root, resource limits |
| Persistence | None | Redis AOF (1Gi PVC) | Redis AOF + RabbitMQ Mnesia |

### Performance Evolution

| Metric | M1 | M2 | M3 (Redis) | M3 (RabbitMQ) |
|--------|----|----|-----------|---------------|
| 10K params (no fault) | ~8s | ~8s | 41s | 38-39s |
| Throughput (no fault) | 1,250 p/s | 1,276 p/s | 243 p/s | 256-263 p/s |
| 1K params (with fault) | N/A (lost) | 44s | 48s | 49s |
| Fault tolerance | None | Verified | Verified | Verified |
| Data loss under fault | 100% of killed worker | ZERO | ZERO | ZERO |
| Recovery method | None | XCLAIM (30s) | XCLAIM (30s) | Auto-requeue |

> **Note on throughput differences:** M1 and M2 full-scale tests used `SIMULATE_WORK_MS=1` (1ms simulated work per parameter), while M3 medium-scale tests used `SIMULATE_WORK_MS=10` (10ms per parameter). The "small" preset uses `SIMULATE_WORK_MS=100` (100ms per chunk). Throughput numbers are only directly comparable within the same `SIMULATE_WORK_MS` setting.

### All Verified Demo Runs

| Run | Milestone | Backend | Fault | Workers | Params | Chunks | Time | Throughput | Data Loss |
|-----|-----------|---------|-------|---------|--------|--------|------|------------|-----------|
| 1 | M1 | Static | No | 3 | 10,000 | N/A | ~8s | 1,250 p/s | ZERO |
| 2 | M2 | Redis | No | 3 | 10,000 | 100/100 | ~8s | 1,276 p/s | ZERO |
| 3 | M2 | Redis | Yes (30%) | 3->2 | 10,000 | 100/100 | 44s | 227 p/s | ZERO |
| 4 | M3 | Redis | No | 3 | 1,000 | 100/100 | 36s | 27 p/s | ZERO |
| 5 | M3 | Redis | Yes (33%) | 3->2 | 1,000 | 100/100 | 48s | 20 p/s | ZERO |
| 6 | M3 | RabbitMQ | No | 3 | 1,000 | 100/100 | 39s | 25 p/s | ZERO |
| 7 | M3 | RabbitMQ | Yes (36%) | 3->2 | 1,000 | 100/100 | 49s | 20 p/s | ZERO |
| 8 | M3 | Redis | No | 3 | 10,000 | 100/100 | 41s | 243 p/s | ZERO |
| 9 | M3 | RabbitMQ | No | 3 | 10,000 | 100/100 | 38s | 256 p/s | ZERO |

**Result: 9/9 runs achieved 100% completion with zero data loss.**

---

## 7. Recommendations for Future Improvements

### High Priority

| Recommendation | Rationale | Estimated Effort |
|---------------|-----------|------------------|
| **Prometheus + Grafana monitoring** | Production systems need persistent metrics, alerting, and dashboards. Currently monitoring is ad-hoc (CLI tools, management UIs). | 2-3 days |
| **Scale testing with 100K+ parameters** | Current testing is at 10K scale. Production workloads will be 10M+. Need to validate queue throughput, memory usage, and chunk sizing at scale. | 1-2 days |
| **Real algorithm integration** | Current workers use a placeholder computation (`SIMULATE_WORK_MS`). Replace with the actual parameter calculation algorithm. | Variable |

### Medium Priority

| Recommendation | Rationale | Estimated Effort |
|---------------|-----------|------------------|
| **Azure AKS deployment** | Move from local Kind to a production cloud environment with real multi-node infrastructure. | 1 week |
| **Horizontal Pod Autoscaler (HPA)** | Automatically scale workers based on queue depth. Add more workers when queue grows, remove when idle. | 1-2 days |
| **Result aggregation pipeline** | Add a dedicated aggregator component that combines partial results into a final output (currently done manually via `aggregate_results.py`). | 2-3 days |
| **CI/CD pipeline** | Automate build, test, and deployment with GitHub Actions or Azure DevOps. | 2-3 days |

### Low Priority

| Recommendation | Rationale | Estimated Effort |
|---------------|-----------|------------------|
| **Redis Cluster mode** | For production Redis HA (currently single-pod with AOF persistence). | 1-2 days |
| **RabbitMQ clustering** | For production RabbitMQ HA (currently single-pod with PVC). | 1-2 days |
| **TLS encryption** | Encrypt Redis and RabbitMQ connections in transit. Currently using plain TCP within the cluster. | 1 day |
| **Network policies** | Restrict pod-to-pod communication to only necessary paths. | 0.5 day |
| **Celery integration** | Add Celery as a Python-native task framework on top of Redis/RabbitMQ for richer task management (chains, groups, rate limiting). | 2 weeks |

---

## 8. Conclusion

The TTG project successfully evolved from a basic static computation model to a production-ready, fault-tolerant distributed system across 3 milestones in approximately 2 weeks:

1. **M1** established the foundation: Kubernetes cluster, containerized workers, parallel execution.
2. **M2** solved the critical problem: dynamic distribution and verified fault tolerance with Redis Streams.
3. **M3** added production maturity: RabbitMQ with retry/DLQ semantics, dual-backend flexibility, and operational monitoring.

The system now achieves **100% task completion with zero data loss** across all tested conditions, including forced worker termination. Both queue backends (Redis and RabbitMQ) are operational and can be selected at deployment time.

---

**Report Version:** 1.0
**Prepared By:** Xavier / TTG Team
**Repository:** https://github.com/xmedinavei/ttg-distributed-compute
