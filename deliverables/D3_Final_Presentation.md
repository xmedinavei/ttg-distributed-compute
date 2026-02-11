# Deliverable 3 -- Final Presentation

**Project:** TTG Distributed Computation System
**Date:** February 10, 2026
**Author:** Xavier / TTG Team
**Program:** AME-UP Final Submission

---

<!-- This document is structured as a presentation outline. Each section maps to one or more slides. -->

---

## Slide 1: Title

**TTG -- Distributed Computation on Kubernetes**

- Fault-Tolerant, Dual-Backend, Queue-Based Parameter Processing
- AME-UP Final Presentation
- Xavier / TTG Team
- February 2026

---

## Slide 2: Timeline & Milestones

| Milestone | Date | Duration | Key Deliverable |
|-----------|------|----------|----------------|
| M1: Basic Setup | Jan 27, 2026 | 1 day | K8s cluster + parallel workers |
| M2: Message Queue | Feb 3, 2026 | 1 week | Redis Streams + fault tolerance |
| M3: Production Queue | Feb 9, 2026 | 1 week | RabbitMQ dual-backend |
| **Final Submission** | **Feb 14, 2026** | -- | **Deliverables 1-3** |

**Total project duration:** ~3 weeks (January 26 - February 14, 2026)

---

## Slide 3: Problem Statement

### The Challenge

Our algorithm processes **millions of parameters** (up to 10M). Each parameter calculation is independent, making this an "embarrassingly parallel" problem.

**Running sequentially on one machine:**
- 10M parameters at 1ms each = ~2.7 hours
- No fault tolerance -- a crash means starting over
- No visibility into progress

**What we need:**
- Distribute work across multiple machines
- Recover automatically from failures
- Monitor progress in real time

---

## Slide 4: Objectives

1. **Parallel Execution** -- Split work across multiple Kubernetes worker nodes
2. **Dynamic Distribution** -- Workers pull tasks from a queue (no static assignment)
3. **Fault Tolerance** -- Zero data loss when workers crash
4. **Dual Backend** -- Support both Redis Streams and RabbitMQ
5. **Operational Tooling** -- Monitoring, cleanup, recovery, and demo scripts
6. **Documentation** -- Complete guides for setup, operation, and troubleshooting

---

## Slide 5: Solution Architecture

```
+---------------------------------------------------------------+
|                   KUBERNETES CLUSTER (Kind)                     |
|                                                                 |
|   +-----------+   +-----------+   +-----------+                 |
|   | Worker 0  |   | Worker 1  |   | Worker 2  |                 |
|   | (Node 1)  |   | (Node 2)  |   | (Node 3)  |                 |
|   +-----+-----+   +-----+-----+   +-----+-----+                |
|         |               |               |                        |
|         +-------+-------+-------+-------+                        |
|                 |                                                 |
|           +-----v-----+                                          |
|           |  REDIS or  |                                          |
|           |  RabbitMQ  |                                          |
|           +-----------+                                           |
|                                                                   |
|   Workers pull tasks from queue, process, acknowledge.            |
|   If Worker 1 dies, Workers 0 and 2 continue.                    |
|   Unfinished tasks are automatically reclaimed.                   |
+-------------------------------------------------------------------+
```

**Key design decisions:**
- Queue-based (not static) distribution
- Standalone Pods (not Jobs) for fault isolation
- Consumer Groups ensure each task goes to exactly one worker
- `QUEUE_BACKEND` env var switches between Redis and RabbitMQ

---

## Slide 6: Milestone 1 -- Basic Setup

**Goal:** Prove parallel execution works on Kubernetes

**What we built:**
- Local Kind cluster (4 nodes: 1 control-plane + 3 workers)
- Dockerized Python worker with structured logging
- Kubernetes Job with indexed completions
- Build and deployment scripts

**Results:**

| Metric | Value |
|--------|-------|
| Parameters | 10,000 |
| Workers | 3 |
| Execution Time | ~8 seconds |
| Throughput | ~1,250 params/sec |
| Success Rate | 100% |

**Limitation:** No fault tolerance. If a worker dies, its work is lost.

---

## Slide 7: Milestone 2 -- Redis Streams & Fault Tolerance

**Goal:** Add dynamic distribution and prove fault tolerance

**What changed:**
- Replaced static ranges with Redis Streams queue
- Added Consumer Groups (XREADGROUP/XACK/XCLAIM)
- Moved to standalone Pods for fault isolation
- Built demo script with fault injection

**Fault Tolerance Proof:**

| Metric | Result |
|--------|--------|
| Worker killed at | 30% progress |
| Chunks completed | **100/100** |
| Data loss | **ZERO** |
| Recovery mechanism | XCLAIM (stale task reclaim) |
| Time to complete | 44 seconds |

**Key discovery:** Kubernetes Jobs with `backoffLimit: 0` terminate ALL pods when one fails. Solution: use standalone Pods.

---

## Slide 8: Milestone 3 -- RabbitMQ Dual Backend

**Goal:** Add production-grade message broker with operational visibility

**What we added:**
- RabbitMQ backend with AMQP protocol
- Retry queue with configurable TTL
- Dead-Letter Queue (DLQ) for exhausted retries
- Management UI (web dashboard on port 15672)
- Dual-backend toggle via `QUEUE_BACKEND` env var
- Redis preserved as rollback-safe fallback

**Why RabbitMQ in addition to Redis:**

| Feature | Redis Streams | RabbitMQ |
|---------|--------------|----------|
| Retry logic | Manual (XCLAIM) | Built-in (retry queue + TTL) |
| Dead-letter queue | Manual | Built-in |
| Monitoring UI | RedisInsight (external) | Management UI (built-in) |
| Fault recovery | Explicit (stale check) | Automatic (unacked requeue) |
| Protocol | Redis RESP | AMQP (industry standard) |

---

## Slide 9: Performance Results

### Backend Comparison (Medium Scale -- 10K Parameters)

| Metric | Redis | RabbitMQ |
|--------|-------|----------|
| Chunks | 100/100 | 100/100 |
| Runtime | 41s | 38-39s |
| Throughput | 243 p/s | 256-263 p/s |
| Data Loss | ZERO | ZERO |

### Under Fault Conditions (Small Scale -- 1K Parameters)

| Metric | Redis (fault) | RabbitMQ (fault) |
|--------|--------------|------------------|
| Worker killed at | ~33% | ~36% |
| Chunks | 100/100 | 100/100 |
| Runtime | 48s | 49s |
| Throughput | 20 p/s | 20 p/s |
| Data Loss | **ZERO** | **ZERO** |

**9 out of 9 verified demo runs achieved 100% completion with zero data loss.**

---

## Slide 10: Fault Tolerance Proof

### The Test

1. Deploy 3 workers connected to queue (Redis or RabbitMQ)
2. Start processing 100 task chunks
3. At ~30% completion, **forcefully kill one worker** (`kubectl delete pod`)
4. Observe: remaining 2 workers continue without interruption
5. Result: **100/100 chunks completed, ZERO data loss**

### Why It Works

**Redis path:** Killed worker's unacknowledged tasks become "stale" after 30 seconds. Surviving workers detect stale tasks via `XPENDING` and reclaim them with `XCLAIM`.

**RabbitMQ path:** When the killed worker's connection drops, RabbitMQ automatically requeues all unacknowledged messages. Surviving workers pick them up immediately.

### Throughput Under Fault

- Normal: 3 workers, ~25-27 p/s (small scale)
- Under fault: 2 workers, ~20 p/s
- Drop: ~20-25% -- expected and proportional to losing 1/3 of workers

---

## Slide 11: Technology Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| Orchestration | Kubernetes 1.27+ | Container scheduling, scaling, health management |
| Local Development | Kind (Kubernetes IN Docker) | Multi-node cluster on a single machine |
| Containerization | Docker (multi-stage builds) | Worker image: Python 3.11-slim, non-root, OCI labels |
| Queue (Option A) | Redis 7.2 + Redis Streams | Lightweight queue with Consumer Groups |
| Queue (Option B) | RabbitMQ 3.13 | Production-grade AMQP broker with retry/DLQ |
| Application | Python 3.11 | Worker logic, queue wrappers, structured logging |
| Monitoring | RedisInsight, RabbitMQ Management UI, CLI tools | Queue visibility and operational awareness |

### Repository Stats

| Metric | Value |
|--------|-------|
| Source code files | 4 (worker, Redis wrapper, RabbitMQ wrapper, logging) |
| K8s manifests | 11 |
| Operational scripts | 10 |
| Documentation files | 21+ |
| Python dependencies | 2 (redis, pika) |
| Docker image size | 186 MB |

---

## Slide 12: Lessons Learned

### What Worked Well

1. **Incremental milestones:** Starting simple (static M1) and building up (queue M2, dual-backend M3) kept complexity manageable and provided clear progress markers.
2. **Redis Streams as first queue:** Low overhead, fast iteration. Perfect for proving the concept before adding RabbitMQ complexity.
3. **Standalone Pods for fault demos:** Critical discovery -- Kubernetes Jobs terminate all pods when one fails. Standalone pods solved this.
4. **One-command demo script:** `run-demo.sh` with `--fault-demo` made it easy to repeatedly demonstrate fault tolerance.
5. **Safe cleanup scripts:** `cleanup-ttg.sh` with TTG-only label selectors prevented accidentally deleting other workloads on shared machines.

### What We Would Do Differently

1. **Start with RabbitMQ earlier:** Its built-in retry/DLQ and management UI are superior to Redis for production queuing.
2. **Add Prometheus from the start:** Ad-hoc monitoring (CLI tools, management UIs) does not scale. Prometheus + Grafana should have been part of the base infrastructure.
3. **Use Helm charts:** Manual YAML manifests become unwieldy as the number of components grows. Helm would simplify deployments.
4. **Automated testing:** The project relies on manual demo runs. CI/CD with automated integration tests would increase confidence.

### Key Technical Decisions

| Decision | Why | Alternative Considered |
|----------|-----|----------------------|
| Kind for local K8s | Free, fast, real multi-node | minikube (single-node), k3s |
| Redis Streams (M2) | Best balance of simplicity + reliability | Kafka (overkill), RabbitMQ (too complex for MVP) |
| RabbitMQ (M3) | Production-grade retry/DLQ, management UI | Keep Redis only |
| Standalone Pods | Fault isolation (Jobs cascade failures) | Kubernetes Jobs with backoffLimit |
| Python 3.11 | Team expertise, good Redis/AMQP libraries | Go (better for containerized workers) |

---

## Slide 13: Future Roadmap

| Enhancement | Priority | Estimated Effort |
|-------------|----------|------------------|
| Prometheus + Grafana monitoring | High | 2-3 days |
| Scale testing (100K+ params) | High | 1-2 days |
| Real algorithm integration | High | Variable |
| Azure AKS deployment | Medium | 1 week |
| Horizontal Pod Autoscaler (HPA) | Medium | 1-2 days |
| Result aggregation pipeline | Medium | 2-3 days |
| CI/CD pipeline | Medium | 2-3 days |
| TLS encryption | Low | 1 day |
| Redis/RabbitMQ clustering (HA) | Low | 1-2 days |

---

## Slide 14: Live Demo

### One-Command Demo

```bash
cd /home/xavierand_/Desktop/TTG

# RabbitMQ fault tolerance demo
./scripts/run-demo.sh --backend rabbitmq --scale small --fault-demo --monitor both
```

**What you will see:**
1. Infrastructure check and deployment
2. 3 workers consuming tasks from RabbitMQ
3. One worker killed at ~30% progress
4. Remaining 2 workers complete ALL 100 chunks
5. Final report: 100/100, ZERO data loss

---

## Slide 15: Q&A

**Key Takeaways:**

- **Fault tolerance is verified:** 9/9 runs, 100% completion, zero data loss.
- **Dual backend flexibility:** Redis for simplicity, RabbitMQ for production features.
- **Production-ready tooling:** One-command demos, safe cleanup, recovery scripts.
- **Comprehensive documentation:** 21+ docs, operational runbooks, architecture guides.

**Repository:** https://github.com/xmedinavei/ttg-distributed-compute

---

**Presentation Version:** 1.0
**Prepared By:** Xavier / TTG Team
