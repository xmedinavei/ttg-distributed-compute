# TTG Distributed Computation - Project Tracker

**Project Name:** TTG Distributed Computation on Kubernetes  
**Owner:** TTG Team  
**Last Updated:** 2026-02-09  
**Overall Status:** 🟢 On Track

---

## Executive Summary

Distributed computation system using Kubernetes to process 10,000 parameters across multiple worker nodes. Milestone 1 and Milestone 2 are complete. **Milestone 3 (RabbitMQ migration) is complete** with dual backend operation, retry/DLQ flow, verified fault tolerance, and medium-scale comparison runs.

---

## Milestones & Deliverables

| Milestone             | Deliverables                                    | Status      | Completion Date | Notes                                       |
| --------------------- | ----------------------------------------------- | ----------- | --------------- | ------------------------------------------- |
| **M1: Basic Setup**   | K8s cluster, worker container, parallel jobs    | ✅ Complete | 2026-01-27      | 3 workers, 10K params, 8s runtime           |
| **M2: Message Queue** | Redis Streams, dynamic scaling, fault tolerance | ✅ Complete | 2026-02-03      | 100/100 chunks, 44s, fault tolerance proven |
| **M3: RabbitMQ Migration (Kind)** | RabbitMQ backend + visual monitoring + reports | ✅ Complete | 2026-02-09 | Redis fallback retained as rollback-safe path |

---

## Current Sprint (Week of Feb 9-13) - Milestone 3

**Milestone 3: Phased RabbitMQ Migration (COMPLETE)**

| Task | Status | Owner | Due Date | Notes |
| ---- | ------ | ----- | -------- | ----- |
| RabbitMQ broker manifest in Kind | ✅ Complete | Team | 2026-02-09 | `k8s/manifests/rabbitmq.yaml` |
| Worker backend toggle (`QUEUE_BACKEND`) | ✅ Complete | Team | 2026-02-09 | Redis + RabbitMQ phased path |
| RabbitMQ retry + DLQ path | ✅ Complete | Team | 2026-02-09 | Main/retry/DLQ queues configured |
| RabbitMQ job manifest | ✅ Complete | Team | 2026-02-09 | `parallel-jobs-queue-rabbitmq.yaml` |
| Visual monitoring points (UI + CLI) | ✅ Complete | Team | 2026-02-09 | RabbitMQ UI + `rabbitmq_monitor.sh` |
| Queue guide update | ✅ Complete | Team | 2026-02-09 | M3 section + future Prom/Grafana note |
| M3 results report | ✅ Complete | Team | 2026-02-09 | New results document in `docs/results` |
| Supervisor report + DOCX template | ✅ Complete | Team | 2026-02-09 | New tracking docs created |

---

## Milestone 2 Achievement Summary (COMPLETE)

### Fault Tolerance Demo Results (Final)

| Metric               | Value                                  |
| -------------------- | -------------------------------------- |
| **Total Chunks**     | 100/100 completed                      |
| **Workers Deployed** | 3 (parallel, queue-based)              |
| **Worker Killed At** | 30% progress                           |
| **Total Time**       | **44 seconds**                         |
| **Throughput**       | **22 params/sec**                      |
| **Fault Tolerance**  | ✅ **VERIFIED** - 100% despite failure |

### Full Scale Test Results

| Metric                         | Value                                    |
| ------------------------------ | ---------------------------------------- |
| **Total Parameters Processed** | 10,000                                   |
| **Number of Workers**          | 3 (parallel, queue-based)                |
| **Task Chunks**                | 100 (100 params each)                    |
| **Wall Clock Time**            | ~8 seconds                               |
| **Total CPU Time**             | 19.83 seconds                            |
| **Effective Throughput**       | 1,276 params/sec                         |
| **Parallelism Factor**         | 2.53x speedup                            |
| **Grand Sum**                  | 5,000,355.00                             |
| **Success Rate**               | 100% (all 100 results in Redis)          |
| **Worker Distribution**        | Worker-0: 40, Worker-1: 30, Worker-2: 30 |

### Key Files Created/Modified (v1.2.0)

| File                                             | Status   | Purpose                                |
| ------------------------------------------------ | -------- | -------------------------------------- |
| `src/queue_utils.py`                             | NEW      | Redis Streams wrapper (TaskQueue)      |
| `src/worker.py`                                  | MODIFIED | Added QueueWorker class, v1.2.1        |
| `k8s/manifests/redis.yaml`                       | NEW      | Redis Pod + Service + PVC              |
| `k8s/manifests/parallel-workers-standalone.yaml` | NEW      | Standalone pods for fault demo         |
| `docker/Dockerfile`                              | MODIFIED | Added queue environment variables      |
| `scripts/run-demo.sh`                            | NEW      | Full demo with fault injection         |
| `scripts/cleanup-ttg.sh`                         | NEW      | Safe cleanup with protected resources  |
| `scripts/recover-infra.sh`                       | NEW      | Infrastructure recovery script         |
| `scripts/aggregate_results.py`                   | NEW      | Results aggregation from Redis         |
| `docs/guides/QUEUE_MODE_GUIDE.md`                | NEW      | Comprehensive queue mode documentation |
| `docs/results/TEST_RESULTS_M2_FAULT_TOLERANCE.md`| NEW      | Fault tolerance test results           |

---

## Key Achievements (Milestone 1)

| Metric                         | Value                           |
| ------------------------------ | ------------------------------- |
| **Total Parameters Processed** | 10,000                          |
| **Number of Workers**          | 3 (parallel)                    |
| **Total Execution Time**       | ~8 seconds                      |
| **K8s Nodes**                  | 4 (1 control-plane + 3 workers) |
| **Total Computed Sum**         | 5,000,354                       |
| **Success Rate**               | 100% (all workers completed)    |

---

## Architecture

**Milestone 1 (Complete):**

- Static range partitioning: Each worker calculates parameter range at startup
- Kubernetes Jobs with indexed completions
- Local kind cluster (sandbox environment)

**Milestone 2 (Complete):**

- ✅ Redis Streams for dynamic task distribution
- ✅ Consumer groups for at-least-once delivery
- ✅ Horizontal scaling capability (workers pull dynamically)
- ✅ Message acknowledgment (XACK)
- ✅ Result persistence in Redis
- ✅ Fault tolerance testing (Day 3) - **VERIFIED**
- ✅ Stale task recovery (claim_stale_tasks implemented)
- ✅ Demo script with fault injection (run-demo.sh)
- ✅ Safe cleanup script (cleanup-ttg.sh)

```
┌─────────────────────────────────────────────────────────────────┐
│                    Kind Kubernetes Cluster                       │
├─────────────────────────────────────────────────────────────────┤
│  ┌──────────┐  ┌──────────┐  ┌──────────┐                       │
│  │ Worker-0 │  │ Worker-1 │  │ Worker-2 │  (v1.2.0 Queue Mode)  │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘                       │
│       │             │             │                              │
│       └──────────┬──┴─────────────┘                              │
│                  │ XREADGROUP / XACK                             │
│                  ▼                                               │
│            ┌───────────┐                                         │
│            │   Redis   │  ttg:tasks (100 chunks)                 │
│            │ (ttg-redis)│  ttg:results (100 results)             │
│            └───────────┘                                         │
└─────────────────────────────────────────────────────────────────┘
```

---

## Key Decisions

| Date       | Decision                      | Rationale                             |
| ---------- | ----------------------------- | ------------------------------------- |
| 2026-01-26 | Use kind for local K8s        | Faster setup, free, sandbox           |
| 2026-01-26 | Start with K8s Jobs           | Simpler for first milestone           |
| 2026-01-30 | Redis Streams for M2          | Balance of simplicity + reliability   |
| 2026-01-30 | Compressed M2 to 2 weeks      | Supervisor requirement                |
| 2026-02-03 | Compressed M2 to 4 days       | User request, demo Friday             |
| 2026-02-03 | QueueWorker as separate class | Maintains backward compatibility      |
| 2026-02-03 | K8s Redis only (no local)     | Avoid port conflicts, single source   |
| 2026-02-03 | 30s idle timeout for exit     | Balance responsiveness and efficiency |

---

## Risks & Challenges

| Risk                    | Impact | Probability | Mitigation                                  |
| ----------------------- | ------ | ----------- | ------------------------------------------- |
| 2-week timeline for M2  | High   | Medium      | Simplified scope (no Celery, no Aggregator) |
| Redis learning curve    | Medium | Medium      | Documentation + simple examples             |
| Production AKS cost     | High   | Low         | M3 future scope, not immediate              |
| Resource limits unknown | Medium | Low         | Profiling in Milestone 1                    |

---

## Next Steps

1. Keep Redis fallback path active while RabbitMQ remains primary M3 path.
2. Add Prometheus + Grafana dashboards in Kind for richer observability.
3. Run larger scale tests (100K+ params) to profile queue overhead and tuning.
4. Prepare AKS production hardening plan.

---

## Demo Commands (Quick Reference)

### Milestone 1 (Static Mode)

```bash
# Setup and run (5 minutes)
./k8s/local/setup-local.sh
./scripts/build.sh --version 1.1.0
kind load docker-image ttg-worker:v1.1.0 --name ttg-sandbox
kubectl apply -f k8s/manifests/parallel-jobs.yaml
```

### Milestone 2 (Queue Mode) - RECOMMENDED

```bash
# Full demo with fault tolerance (easiest method)
./scripts/run-demo.sh --scale small --fault-demo --monitor cli

# Or with RedisInsight (visual)
./scripts/run-demo.sh --scale small --fault-demo --monitor both

# Options:
#   --scale small|medium    (1K or 10K params)
#   --workers N             (number of workers, default 3)
#   --fault-demo            (kill worker at 30%)
#   --monitor cli|web|both  (monitoring tools)

# Cleanup after demo
./scripts/cleanup-ttg.sh --pods --force
```

---

**Status Legend:**  
🟢 On Track | 🟡 At Risk | 🔴 Blocked  
✅ Complete | 📋 Planned | ⏳ Future
