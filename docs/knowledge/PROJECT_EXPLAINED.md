# TTG Project - Full Explanation

**Last Updated:** February 10, 2026
**Version:** 1.3.0
**Status:** All 3 Milestones Complete

---

## Table of Contents

1. [The Problem](#the-problem)
2. [The Objective](#the-objective)
3. [The Purpose](#the-purpose)
4. [How We Tackled the Problem](#how-we-tackled-the-problem)
5. [Technology Explanations](#technology-explanations)
6. [Project Structure - What Each File Does](#project-structure---what-each-file-does)

---

## The Problem

Our organization has an algorithm that needs to process **millions of parameters** (up to 10 million). Each parameter calculation is independent of the others -- parameter #5's result does not depend on parameter #3's result. Running this sequentially on a single machine is painfully slow. If each parameter takes even 1 millisecond, 10 million parameters would take approximately 2.7 hours on one machine. With 100 machines working in parallel, that drops to roughly 1.6 minutes.

This is what is called an **"embarrassingly parallel"** problem -- the work can be trivially split because there are no dependencies between tasks.

```
Sequential (1 machine):
  Parameter 1 -> Parameter 2 -> ... -> Parameter 10,000,000
  Time: ~2.7 hours

Parallel (100 machines):
  Machine  1: Parameters        1 -   100,000
  Machine  2: Parameters  100,001 -   200,000
  ...
  Machine 100: Parameters 9,900,001 - 10,000,000
  Time: ~1.6 minutes
```

The challenge goes beyond just splitting work. In a real distributed system:

- **Machines fail.** A worker can crash mid-computation, losing its assigned work.
- **Load is uneven.** Some parameters may take longer than others, leaving fast workers idle.
- **Coordination is hard.** Workers need to know what to process without duplicating or missing work.
- **Operations matter.** You need monitoring, cleanup, and recovery procedures.

---

## The Objective

Build a **fault-tolerant distributed computation system** on Kubernetes that:

1. **Splits parameter workloads** across multiple worker nodes automatically.
2. **Dynamically distributes tasks** via a message queue (not statically pre-assigned).
3. **Recovers automatically** when workers crash -- zero data loss, zero manual intervention.
4. **Supports multiple queue backends** (Redis Streams and RabbitMQ) for flexibility and production readiness.
5. **Provides monitoring and operational tooling** so engineers can observe, troubleshoot, and maintain the system.

---

## The Purpose

This project serves as a **proof-of-concept and production-ready framework** for accelerating parameter-heavy computations. It demonstrates that our team can take a sequential bottleneck and turn it into a horizontally scalable, fault-tolerant distributed system using industry-standard tools (Kubernetes, Redis, RabbitMQ).

The work was structured across 3 milestones in the AME-UP program to show progressive engineering maturity:

- **Milestone 1:** Can we run computation in parallel on Kubernetes?
- **Milestone 2:** Can we recover from failures without losing data?
- **Milestone 3:** Can we use a production-grade message broker with operational visibility?

Each milestone built on the previous one, demonstrating incremental engineering capability.

---

## How We Tackled the Problem

The project evolved across **3 milestones**, each building on the previous:

### Milestone 1 -- Static Distribution (January 27, 2026)

We started simple. We set up a local Kubernetes cluster with 3 worker nodes using Kind (Kubernetes IN Docker). Each worker was pre-assigned a fixed range of parameters at startup:

```
Worker 0: Parameters     0 -  3,333
Worker 1: Parameters 3,334 -  6,666
Worker 2: Parameters 6,667 -  9,999
```

Each worker calculates its range based on its index (`JOB_COMPLETION_INDEX`) and the total parameter count. This approach processed 10,000 parameters in approximately 8 seconds.

**What worked:** Simple, fast, easy to understand.

**Critical flaw:** If a worker dies, its entire parameter range is **permanently lost**. There is no recovery mechanism. The Kubernetes Job controller either restarts the failed worker (reprocessing everything) or marks the entire job as failed.

### Milestone 2 -- Queue-Based with Fault Tolerance (February 3, 2026)

We replaced static assignment with **Redis Streams** -- a message queue built into Redis. Instead of pre-assigning ranges, work is split into 100 chunks and pushed into a shared queue. Workers pull chunks dynamically.

```
Before (Static):
  Worker 0 gets params 0-3333 (fixed at startup)
  Worker 1 gets params 3334-6666 (fixed at startup)
  Worker 2 gets params 6667-9999 (fixed at startup)
  --> If Worker 1 dies, params 3334-6666 are LOST

After (Queue):
  Redis queue holds 100 chunks
  Workers pull next available chunk
  Workers acknowledge (XACK) when done
  --> If Worker 1 dies, its unfinished chunk goes back to the queue
  --> Another worker picks it up automatically
```

The key mechanism is **Consumer Groups** in Redis Streams:

- `XREADGROUP`: Each worker pulls the next unassigned chunk (no duplicates).
- `XACK`: Worker confirms it finished processing a chunk.
- `XCLAIM`: If a worker dies before acknowledging, another worker reclaims the "stale" chunk after a timeout (30 seconds).

**Proof:** We killed a worker at 30% progress. The remaining 2 workers continued without interruption. All 100/100 chunks completed with **zero data loss** in 44 seconds.

### Milestone 3 -- Dual Backend with RabbitMQ (February 9, 2026)

We added **RabbitMQ** as a second queue backend. RabbitMQ is a dedicated message broker with richer operational features than Redis Streams:

- **Retry queues with TTL:** Failed messages automatically re-enter the main queue after a configurable delay.
- **Dead-Letter Queue (DLQ):** Messages that fail too many times go to a separate queue for manual inspection.
- **Management UI:** A built-in web dashboard (port 15672) showing queue depths, consumer counts, and message rates in real time.
- **Auto-requeue on disconnect:** If a worker disconnects without acknowledging, RabbitMQ automatically makes the message available to another worker (simpler than Redis XCLAIM).

The worker can switch between Redis and RabbitMQ via a single environment variable:

```bash
QUEUE_BACKEND=redis     # Use Redis Streams (Milestone 2 path)
QUEUE_BACKEND=rabbitmq  # Use RabbitMQ (Milestone 3 path)
```

**Results at medium scale (10,000 parameters):**

| Backend  | Runtime | Throughput  | Data Loss |
|----------|---------|-------------|-----------|
| RabbitMQ | 38-39s  | 256-263 p/s | ZERO      |
| Redis    | 41s     | 243 p/s     | ZERO      |

Both backends achieve 100% completion with zero data loss, even when a worker is killed mid-processing.

---

## Technology Explanations

### Kubernetes (K8s)

Kubernetes is a **container orchestration platform** -- think of it as a smart manager for running containers across multiple machines. You tell Kubernetes "run 3 copies of my worker" and it figures out which machines to put them on, restarts them if they crash, and manages resource allocation.

Key concepts used in this project:

| Concept | What It Is | How We Use It |
|---------|-----------|---------------|
| **Cluster** | A group of machines working together | Our Kind cluster has 4 nodes |
| **Control Plane** | The "brain" that makes scheduling decisions | 1 node runs the Kubernetes API server |
| **Worker Node** | A machine that runs containers | 3 nodes run our worker pods |
| **Pod** | The smallest deployable unit (wraps a container) | Each worker runs as a Pod |
| **Job** | Creates Pods that run a task to completion | M1 uses Jobs with indexed completions |
| **Service** | A stable network address for Pods | Redis and RabbitMQ are accessed via Services |
| **PersistentVolumeClaim** | Durable storage that survives Pod restarts | Redis and RabbitMQ data persists |

Kubernetes automates what would otherwise be manual work:

```
Without Kubernetes:
  - SSH into 10 machines
  - Start workers on each manually
  - If one crashes, manually restart it
  - If you need more workers, provision new machines

With Kubernetes:
  - Tell K8s: "Run 10 workers"
  - K8s schedules them across available nodes
  - K8s restarts crashed workers
  - Tell K8s: "Now run 100 workers" --> done
```

### Kind (Kubernetes IN Docker)

Kind is a tool that lets you run a **full Kubernetes cluster locally on your laptop** using Docker containers. Each "node" in the cluster is actually a Docker container pretending to be a machine. This is perfect for development and testing -- you get a real multi-node Kubernetes cluster without needing cloud infrastructure or paying for virtual machines.

In this project, we use Kind with 4 nodes:
- 1 control-plane node (runs the K8s API)
- 3 worker nodes (run our computation pods)

The cluster is named `ttg-sandbox` and is configured via `k8s/local/kind-config.yaml`.

### Redis and Redis Streams

**Redis** is an in-memory data store, famous for being extremely fast (sub-millisecond latency). It stores data as key-value pairs and supports many data structures (strings, lists, sets, hashes, streams).

**Redis Streams** is a data structure within Redis that works like an append-only log. Producers add messages, and consumers read them. Key operations:

| Command | What It Does |
|---------|-------------|
| `XADD` | Add a message to the stream (producer pushes a task) |
| `XREADGROUP` | Read the next undelivered message as part of a consumer group |
| `XACK` | Acknowledge that a message has been processed |
| `XCLAIM` | Reclaim a message from a dead consumer (fault recovery) |
| `XPENDING` | List messages delivered but not yet acknowledged |

We use **Consumer Groups** so that multiple workers can coordinate: each chunk is delivered to exactly one worker. If a worker dies before acknowledging (`XACK`) a chunk, another worker can reclaim it (`XCLAIM`) after a configurable timeout.

### RabbitMQ

RabbitMQ is a **dedicated message broker** that speaks the AMQP (Advanced Message Queuing Protocol). Unlike Redis (which is a general-purpose data store), RabbitMQ is built specifically for message queuing.

Key advantages of RabbitMQ over Redis Streams for this project:

| Feature | Redis Streams | RabbitMQ |
|---------|--------------|----------|
| Retry logic | Manual (stale check interval + XCLAIM) | Built-in retry queue with configurable TTL |
| Dead-Letter Queue | Must implement manually | Built-in, configurable per queue |
| Monitoring | RedisInsight + CLI | Management UI (web dashboard) + CLI |
| Fault recovery | Explicit (XCLAIM) | Automatic (unacked messages requeue on disconnect) |
| Protocol | Redis RESP (proprietary) | AMQP 0-9-1 (industry standard) |

Our RabbitMQ topology uses 4 queues:
- `ttg.tasks` -- main task queue (workers consume from here)
- `ttg.results` -- results queue (workers publish results here)
- `ttg.tasks.retry` -- retry queue with TTL (failed tasks wait here, then re-enter main queue)
- `ttg.tasks.dlq` -- dead-letter queue (tasks that exhaust all retries go here for inspection)

---

## Project Structure - What Each File Does

### Source Code (`src/`)

| File | What It Does |
|------|-------------|
| `worker.py` | The main worker application (v1.3.0). Runs in two modes: **static mode** (M1 -- calculates a pre-assigned parameter range) or **queue mode** (M2/M3 -- pulls chunks from Redis or RabbitMQ). Contains the `QueueWorker` class that handles task consumption, processing, result reporting, and graceful shutdown (SIGTERM/SIGINT). |
| `queue_utils.py` | Redis Streams wrapper. The `TaskQueue` class encapsulates all Redis operations: creating streams, adding tasks (XADD), reading tasks (XREADGROUP), acknowledging (XACK), reclaiming stale tasks (XCLAIM), and storing results. |
| `rabbitmq_queue.py` | RabbitMQ wrapper. The `RabbitMQTaskQueue` class manages AMQP connections, declares the queue topology (main queue, retry queue with TTL, DLQ, results queue), publishes tasks, consumes with manual acknowledgment, and handles connection recovery. |
| `logging_config.py` | Structured logging configuration. Supports text (human-readable) and JSON (machine-parseable) formats. Injects worker context (worker_id, hostname, pod_name, node_name) into every log line. Includes timing utilities (`@timed` decorator, `log_timing` context manager). |

### Kubernetes Manifests (`k8s/manifests/`)

| File | What It Does |
|------|-------------|
| `parallel-jobs.yaml` | M1 manifest. Kubernetes Job with indexed completions -- runs 3 workers, each gets a `JOB_COMPLETION_INDEX` to calculate its parameter range. |
| `parallel-jobs-queue.yaml` | M2 manifest. Kubernetes Job for Redis queue mode -- workers pull from Redis Streams instead of using static ranges. |
| `parallel-jobs-queue-rabbitmq.yaml` | M3 manifest. Same as above but configured for RabbitMQ backend (`QUEUE_BACKEND=rabbitmq`). |
| `parallel-workers-standalone.yaml` | Standalone pods (not managed by a Job controller). Used for fault tolerance demos -- when one pod is killed, the Job controller does not terminate the others. |
| `redis.yaml` | Redis deployment with PersistentVolumeClaim (1Gi), AOF persistence, resource limits, health probes, and a ClusterIP Service on port 6379. |
| `rabbitmq.yaml` | RabbitMQ deployment with PVC (2Gi), management plugin enabled, resource limits, health probes, and Services on ports 5672 (AMQP) and 15672 (management UI). |
| `redis-insight.yaml` | RedisInsight deployment -- a web GUI for inspecting Redis data, streams, and consumer groups. |
| `worker-job.yaml` | Single worker job template for quick testing. |
| `parallel-jobs-fault-test.yaml` | Fault tolerance test manifest (Job-based, discovered limitation). |
| `parallel-jobs-fault-demo.yaml` | Fault tolerance demo manifest. |
| `test-fault-controlled.yaml` | Controlled fault test configuration. |

### Kind Configuration (`k8s/local/`)

| File | What It Does |
|------|-------------|
| `kind-config.yaml` | Defines the Kind cluster topology: 1 control-plane node + 3 worker nodes. This mimics a real multi-node cluster on your local machine. |
| `setup-local.sh` | Shell script that creates the Kind cluster, loads Docker images into it, and verifies everything is ready. This is the primary "from zero" setup script. |

### Azure Configuration (`k8s/azure/`)

| File | What It Does |
|------|-------------|
| `setup-aks.sh` | Azure AKS setup script for production-like deployment (documented, not fully implemented). |

### Scripts (`scripts/`)

| File | What It Does |
|------|-------------|
| `run-demo.sh` | The main demo script. Supports `--backend redis\|rabbitmq`, `--scale small\|medium`, `--fault-demo` (kills a worker), `--monitor cli\|both`. Orchestrates the full lifecycle: deploy infrastructure, load tasks, start workers, optionally inject faults, wait for completion, report results, cleanup. |
| `cleanup-ttg.sh` | Safe cleanup that ONLY touches TTG-labeled resources. Supports `--dry-run` to preview, `--pods`, `--all`, `--force`. Protects non-TTG Docker containers. |
| `recover-infra.sh` | Recovers infrastructure after a system restart (re-starts stopped Kind containers, re-deploys Redis/RabbitMQ if needed). |
| `build.sh` | Builds the Docker image with versioned tags and OCI labels. Supports `--load-kind` to load into the Kind cluster. |
| `deploy.sh` | Deploys worker manifests to the cluster with configurable worker count and parameter count. |
| `list-resources.sh` | Lists all TTG resources across Docker and Kubernetes. |
| `queue_monitor.py` | Real-time CLI dashboard for Redis queues using the Rich library. Shows queue depth, pending tasks, worker breakdown, throughput, and ETA. |
| `rabbitmq_monitor.sh` | CLI monitor for RabbitMQ -- queries the management API to show queue states (messages, consumers, unacked). |
| `aggregate_results.py` | Reads results from Redis, computes throughput, parallelism factor, and timing metrics. |
| `generate_docx_report.py` | Generates Word (.docx) reports from the project data. |
| `fault-tolerance-demo.sh` | Dedicated fault tolerance demonstration script. |

### Docker (`docker/`)

| File | What It Does |
|------|-------------|
| `Dockerfile` | Multi-stage build for the worker image. Uses `python:3.11-slim`, installs dependencies, copies source code, creates a non-root user (`ttg-worker`), sets OCI labels for identification. Security: runs as non-root, read-only filesystem, dropped capabilities. |

### Documentation (`docs/`)

| Directory | Contents |
|-----------|----------|
| `architecture/` | System design documents (`M2_QUEUE_ARCHITECTURE.md` -- queue broker comparison, chosen architecture, data flow, message schemas) |
| `guides/` | Operational how-to guides (`CONFIGURATION_GUIDE.md` -- all env vars and settings; `QUEUE_MODE_GUIDE.md` -- running in queue mode) |
| `knowledge/` | Tutorial-style explanations (`KUBERNETES_EXPLAINED.md`, `KIND_EXPLAINED.md`, and this file `PROJECT_EXPLAINED.md`) |
| `results/` | Test results for each milestone (`TEST_RESULTS_M1_PARALLEL_JOBS.md`, `TEST_RESULTS_M2_FAULT_TOLERANCE.md`, `TEST_RESULTS_M3_RABBITMQ_MONITORING.md`) |
| `setup/` | Installation and setup guides (`KUBERNETES_SETUP.md` -- local K8s setup; `AZURE_AKS_GUIDE.md` -- Azure AKS deployment) |
| `tracking/` | Project management (`PROJECT_OVERVIEW.md`, `PROJECT_TRACKER.md`, `PROJECT_STATUS_REPORT.md`, `SUPERVISOR_REPORT_M3_RABBITMQ.md`) |

### Root Files

| File | What It Does |
|------|-------------|
| `README.md` | Main project README with quick start, configuration reference, troubleshooting. |
| `SUPERVISOR_REPORT.md` | Executive summary for supervisor (M1+M2+M3). For M3 RabbitMQ details, see `docs/tracking/SUPERVISOR_REPORT_M3_RABBITMQ.md`. |
| `requirements.txt` | Python dependencies: `redis>=4.5.0`, `pika>=1.3.0`. |
| `LICENSE` | MIT License. |
| `.gitignore` | Git ignore rules (excludes `.env`, secrets, `__pycache__`, etc.). |
| `.dockerignore` | Docker build context exclusions. |

---

## How to Replicate the Entire Project from Scratch

If you want to set up the project on a fresh machine:

```bash
# Prerequisites: Docker, kind, kubectl installed

# 1. Clone the repository
git clone https://github.com/xmedinavei/ttg-distributed-compute.git
cd ttg-distributed-compute

# 2. Create the Kind cluster (4 nodes) + build worker image
./k8s/local/setup-local.sh

# 3. Build the v1.3.0 image and load into Kind
./scripts/build.sh --version 1.3.0 --load-kind

# 4. Run the full demo with RabbitMQ and fault injection
./scripts/run-demo.sh --backend rabbitmq --scale small --fault-demo --monitor both

# 5. (Optional) Run with Redis for comparison
./scripts/run-demo.sh --backend redis --scale small --fault-demo --monitor both

# 6. Clean up when done
./scripts/cleanup-ttg.sh --all --force
```

After a system reboot, use:

```bash
./scripts/recover-infra.sh
```

---

_Author: TTG Team_
_Last Updated: February 10, 2026_
