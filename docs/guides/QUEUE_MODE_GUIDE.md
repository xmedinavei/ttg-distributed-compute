# TTG Queue Mode Guide (Milestone 2 + M3 Phased Migration)

**Version:** 1.3.0  
**Status:** ✅ Redis queue stable + RabbitMQ phased path added  
**Date:** February 2026

---

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Milestone 3: RabbitMQ Backend (Phased)](#milestone-3-rabbitmq-backend-phased)
4. [Quick Start](#quick-start)
5. [Configuration Reference](#configuration-reference)
6. [Running Queue Mode](#running-queue-mode)
7. [Monitoring & Observability](#monitoring--observability)
8. [Fault Tolerance](#fault-tolerance) ⭐ NEW
9. [Troubleshooting](#troubleshooting)
10. [API Reference](#api-reference)
11. [FAQ](#faq)

---

## Overview

### What is Queue Mode?

Queue Mode (Milestone 2) introduces a **message queue architecture** using Redis Streams for distributed task processing. Instead of each worker processing a fixed range of parameters, workers dynamically pull tasks from a shared queue.

### Key Benefits

| Feature           | Static Mode (v1.1)      | Queue Mode (v1.2)     |
| ----------------- | ----------------------- | --------------------- |
| Task Distribution | Fixed per worker        | Dynamic pulling       |
| Fault Tolerance   | ❌ Lost work on failure | ✅ Auto-recovery      |
| Load Balancing    | ❌ Uneven if tasks vary | ✅ Naturally balanced |
| Scalability       | Manual reconfiguration  | Add workers anytime   |
| Result Storage    | Stdout only             | Redis persistent      |

### When to Use Queue Mode

- ✅ Long-running computations with varying task complexity
- ✅ Need fault tolerance (task recovery on worker failure)
- ✅ Want to dynamically scale workers up/down
- ✅ Need centralized result storage
- ✅ Want real-time progress monitoring

---

## Architecture

### System Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        Kind Kubernetes Cluster                           │
│                         (kind-ttg-sandbox)                               │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│    ┌─────────────────────────────────────────────────────────────────┐  │
│    │                      Worker Pods (Job)                          │  │
│    │  ┌───────────┐    ┌───────────┐    ┌───────────┐               │  │
│    │  │ Worker-0  │    │ Worker-1  │    │ Worker-2  │    ...        │  │
│    │  │ (v1.2.0)  │    │ (v1.2.0)  │    │ (v1.2.0)  │               │  │
│    │  └─────┬─────┘    └─────┬─────┘    └─────┬─────┘               │  │
│    └────────┼────────────────┼────────────────┼─────────────────────┘  │
│             │                │                │                         │
│             │   XREADGROUP   │   XREADGROUP   │   (Consumer Group)      │
│             │   (pull task)  │   (pull task)  │                         │
│             └────────┬───────┴───────┬────────┘                         │
│                      │               │                                   │
│                      ▼               ▼                                   │
│    ┌─────────────────────────────────────────────────────────────────┐  │
│    │                          Redis Pod                              │  │
│    │                        (ttg-redis)                              │  │
│    │  ┌────────────────────────────────────────────────────────────┐ │  │
│    │  │  Stream: ttg:tasks                                         │ │  │
│    │  │  ┌──────────────────────────────────────────────────────┐  │ │  │
│    │  │  │ chunk_00 │ chunk_01 │ chunk_02 │ ... │ chunk_99      │  │ │  │
│    │  │  └──────────────────────────────────────────────────────┘  │ │  │
│    │  │  Consumer Group: ttg-workers                               │ │  │
│    │  │  Consumers: worker-0, worker-1, worker-2                   │ │  │
│    │  └────────────────────────────────────────────────────────────┘ │  │
│    │                                                                  │  │
│    │  ┌────────────────────────────────────────────────────────────┐ │  │
│    │  │  Stream: ttg:results                                       │ │  │
│    │  │  ┌──────────────────────────────────────────────────────┐  │ │  │
│    │  │  │ result_00 │ result_01 │ result_02 │ ... │            │  │ │  │
│    │  │  └──────────────────────────────────────────────────────┘  │ │  │
│    │  └────────────────────────────────────────────────────────────┘ │  │
│    └─────────────────────────────────────────────────────────────────┘  │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### Data Flow

1. **Initialization** (Worker 0 only):
   - Worker 0 detects empty queue
   - Creates 100 task chunks (for 10,000 params with chunk_size=100)
   - Each chunk: `{chunk_id, start_param, end_param, total_params}`

2. **Task Consumption** (All workers):
   - Workers use `XREADGROUP` to pull tasks from consumer group
   - Each task delivered to exactly one worker
   - Task marked as "pending" until acknowledged

3. **Processing**:
   - Worker processes chunk (applies algorithm to parameters)
   - Computes statistics: sum, count, min, max, avg

4. **Acknowledgment & Results**:
   - Worker calls `XACK` to acknowledge task completion
   - Worker publishes result to `ttg:results` stream
   - Result includes: chunk_id, worker_id, duration, result_data

5. **Idle Timeout**:
   - When no tasks for 30 seconds, worker exits gracefully
   - Kubernetes Job tracks completion

### Redis Streams Concepts

| Concept                      | Description                                                   |
| ---------------------------- | ------------------------------------------------------------- |
| **Stream**                   | Append-only log of messages (like Kafka topic)                |
| **Consumer Group**           | Named group that tracks which messages each consumer has seen |
| **Consumer**                 | Individual worker identified by name (e.g., `worker-0`)       |
| **Pending Entry List (PEL)** | Messages delivered but not yet acknowledged                   |
| **XACK**                     | Acknowledge message processed, removes from PEL               |

---

## Milestone 3: RabbitMQ Backend (Phased)

Milestone 2 Redis Streams remains supported and is the fallback path. Milestone 3 adds a RabbitMQ queue backend so we can use broker-native retry and dead-letter handling while keeping local Kind operations simple.

### Backend Toggle

| Variable | Value | Effect |
| --- | --- | --- |
| `USE_QUEUE` | `true` | Enables queue worker mode |
| `QUEUE_BACKEND` | `redis` | Uses existing Redis Streams flow |
| `QUEUE_BACKEND` | `rabbitmq` | Uses RabbitMQ task/retry/DLQ flow |

### RabbitMQ Topology

- Task queue: `ttg.tasks`
- Retry queue: `ttg.tasks.retry` (delay queue)
- Dead-letter queue: `ttg.tasks.dlq`
- Results queue: `ttg.results`

### RabbitMQ Quick Deploy (Kind)

```bash
# Deploy RabbitMQ broker + management UI
kubectl apply -f k8s/manifests/rabbitmq.yaml

# Build/load worker image with RabbitMQ backend code
docker build -t ttg-worker:v1.3.0 -f docker/Dockerfile .
kind load docker-image ttg-worker:v1.3.0 --name ttg-sandbox

# Run workers in RabbitMQ mode
kubectl apply -f k8s/manifests/parallel-jobs-queue-rabbitmq.yaml
```

---

## Quick Start

### Prerequisites

- Kind cluster running (`kind-ttg-sandbox`)
- Redis deployed to cluster
- Docker image `ttg-worker:v1.2.0` loaded into Kind

### Step 1: Verify Infrastructure

```bash
# Check Kind cluster
kubectl cluster-info --context kind-ttg-sandbox

# Check Redis is running
kubectl get pod ttg-redis

# Verify image is loaded
docker exec kind-ttg-sandbox-control-plane crictl images | grep ttg-worker
```

### Step 2: Clear Previous Data (Optional)

```bash
kubectl exec ttg-redis -- redis-cli FLUSHALL
```

### Step 3: Deploy Queue Mode Workers

```bash
kubectl apply -f k8s/manifests/parallel-jobs-queue.yaml
```

### Step 4: Monitor Progress

```bash
# Watch pods
kubectl get pods -l ttg.io/mode=queue -w

# View logs
kubectl logs -l ttg.io/mode=queue -f

# Check results count
kubectl exec ttg-redis -- redis-cli XLEN ttg:results
```

### Step 5: Aggregate Results

```bash
# Port-forward Redis
kubectl port-forward pod/ttg-redis 16379:6379 &

# Run aggregation
python scripts/aggregate_results.py --port 16379
```

---

## Configuration Reference

### Environment Variables

| Variable               | Default     | Description                                         |
| ---------------------- | ----------- | --------------------------------------------------- |
| `USE_QUEUE`            | `false`     | Enable queue mode (`true`) or static mode (`false`) |
| `QUEUE_BACKEND`        | `redis`     | Queue backend (`redis` or `rabbitmq`)               |
| `REDIS_HOST`           | `ttg-redis` | Redis server hostname                               |
| `REDIS_PORT`           | `6379`      | Redis server port                                   |
| `RABBITMQ_HOST`        | `ttg-rabbitmq` | RabbitMQ server hostname                         |
| `RABBITMQ_PORT`        | `5672`      | RabbitMQ AMQP port                                  |
| `RABBITMQ_MAX_RETRIES` | `3`         | Max retries before dead-letter queue                |
| `RABBITMQ_RETRY_DELAY_MS` | `5000`   | Retry delay before message returns to main queue    |
| `CHUNK_SIZE`           | `100`       | Parameters per task chunk                           |
| `IDLE_TIMEOUT_SECONDS` | `30`        | Exit after this many seconds with no tasks          |
| `WORKER_ID`            | `0`         | Unique worker identifier (set by K8s)               |
| `TOTAL_PARAMS`         | `10000`     | Total parameters to process                         |
| `SIMULATE_WORK_MS`     | `1`         | Milliseconds of simulated work per parameter        |

### Redis Keys

| Key           | Type           | Description                          |
| ------------- | -------------- | ------------------------------------ |
| `ttg:tasks`   | Stream         | Task queue with chunks to process    |
| `ttg:results` | Stream         | Completed results from workers       |
| `ttg-workers` | Consumer Group | Consumer group for task distribution |

### Kubernetes Labels

| Label              | Value        | Description            |
| ------------------ | ------------ | ---------------------- |
| `app`              | `ttg-worker` | Application identifier |
| `version`          | `v1.2.0`     | Version identifier     |
| `ttg.io/mode`      | `queue`      | Processing mode        |
| `ttg.io/milestone` | `2`          | Milestone number       |

---

## Running Queue Mode

### One-Command Demo (Recommended)

Use the same script for both queue backends:

```bash
# Redis backend demo
./scripts/run-demo.sh --backend redis --scale small --fault-demo --monitor both

# RabbitMQ backend demo
./scripts/run-demo.sh --backend rabbitmq --scale small --fault-demo --monitor both
```

This keeps demo operations consistent while you compare backends.

### Using kubectl

```bash
# Deploy workers
kubectl apply -f k8s/manifests/parallel-jobs-queue.yaml

# Scale workers (edit completions in manifest first)
kubectl delete job ttg-computation-queue
# Edit parallel-jobs-queue.yaml: completions: 5, parallelism: 5
kubectl apply -f k8s/manifests/parallel-jobs-queue.yaml

# Clean up
kubectl delete job ttg-computation-queue
```

### RabbitMQ Backend Mode (M3)

```bash
# Deploy RabbitMQ backend
kubectl apply -f k8s/manifests/rabbitmq.yaml

# Deploy RabbitMQ queue workers
kubectl apply -f k8s/manifests/parallel-jobs-queue-rabbitmq.yaml

# Watch queue workers
kubectl get pods -l ttg.io/queue-backend=rabbitmq -w
```

### Custom Configuration

Edit `k8s/manifests/parallel-jobs-queue.yaml`:

```yaml
spec:
  completions: 5 # Total worker pods to run
  parallelism: 5 # Max concurrent workers
  template:
    spec:
      containers:
        - env:
            - name: TOTAL_PARAMS
              value: "100000" # Process 100K params
            - name: CHUNK_SIZE
              value: "500" # Larger chunks
            - name: IDLE_TIMEOUT_SECONDS
              value: "60" # Longer timeout
```

### Running Locally (Development)

```bash
# Start Redis locally
docker run -d --name redis-local -p 6379:6379 redis:7.2-alpine

# Run worker
cd /path/to/TTG
source venv/bin/activate
USE_QUEUE=true REDIS_HOST=localhost WORKER_ID=0 python src/worker.py
```

---

## Monitoring & Observability

<<<<<<< Current (Your changes)
### RabbitMQ Visual Monitoring (Recommended for M3 demos)

```bash
# Open RabbitMQ management UI
kubectl port-forward pod/ttg-rabbitmq 15672:15672
# URL: http://localhost:15672
# user/pass: guest / guest
```

UI checkpoints for demos and supervisor reviews:
- Queue depth: `ttg.tasks` decreases to zero by run completion.
- Consumers: active consumer count aligns with worker pods.
- Unacked messages: spikes during processing, returns to near zero at end.
- Throughput rates: publish/deliver/ack charts show active flow.
- Reliability path: `ttg.tasks.retry` and `ttg.tasks.dlq` reflect retry/failure behavior.

### RabbitMQ CLI Monitoring Points

```bash
# One-time queue snapshot
./scripts/rabbitmq_monitor.sh

# Live queue snapshot every 2 seconds
./scripts/rabbitmq_monitor.sh --watch 2

# Worker pods and logs
kubectl get pods -l ttg.io/queue-backend=rabbitmq
kubectl logs -l ttg.io/queue-backend=rabbitmq -f
```

Expected lifecycle:
- Start: `ttg.tasks` high, `ttg.results` low.
- Mid-run: `ttg.tasks` decreasing, `ttg.results` increasing.
- End: `ttg.tasks` near zero, `ttg.results` equals chunk count.
- Failure test: retry queue may increase briefly; DLQ only grows if retries are exhausted.

Future extension (out of current project scope): add Prometheus + Grafana in Kind for long-running dashboards, SLO tracking, and alerting.
=======
### Live Demo Monitoring by Backend

- Redis backend:
  - `python3 scripts/queue_monitor.py --total-params 10000`
  - `python3 scripts/aggregate_results.py --port 6379`
- RabbitMQ backend:
  - `./scripts/rabbitmq_monitor.sh --watch 2`
  - RabbitMQ UI: `kubectl port-forward pod/ttg-rabbitmq 15672:15672` then open `http://localhost:15672`

Visual checkpoints for supervisor demos:
- Queue depth decreases toward zero.
- Active consumers match running workers.
- Unacked messages return near zero by completion.
- Retry/DLQ queues show expected behavior under failures.
>>>>>>> Incoming (Background Agent changes)

### Real-time Queue Stats

```bash
# Queue length (pending tasks)
kubectl exec ttg-redis -- redis-cli XLEN ttg:tasks

# Results count
kubectl exec ttg-redis -- redis-cli XLEN ttg:results

# Pending (in-progress) tasks
kubectl exec ttg-redis -- redis-cli XPENDING ttg:tasks ttg-workers

# Consumer info
kubectl exec ttg-redis -- redis-cli XINFO GROUPS ttg:tasks
```

### Log Monitoring

```bash
# All workers (live)
kubectl logs -l ttg.io/mode=queue -f

# Specific worker
kubectl logs ttg-computation-queue-0-xxxxx -f

# JSON summary from completed worker
kubectl logs ttg-computation-queue-0-xxxxx | grep "FINAL SUMMARY" -A 20
```

### Result Aggregation

```bash
# Port-forward Redis
kubectl port-forward pod/ttg-redis 16379:6379 &

# Pretty report
python scripts/aggregate_results.py --port 16379

# JSON output
python scripts/aggregate_results.py --port 16379 --json

# Verbose (show all chunks)
python scripts/aggregate_results.py --port 16379 --verbose
```

### Sample Aggregation Output

```
╔══════════════════════════════════════════════════════════════════════╗
║             TTG Queue Mode - Results Aggregation Report              ║
╠══════════════════════════════════════════════════════════════════════╣
║ 📊 COMPUTATION SUMMARY                                                ║
╠──────────────────────────────────────────────────────────────────────╣
║  Total Parameters Processed:        10,000                           ║
║  Total Chunks Processed:               100                           ║
║  Grand Sum:                   5,000,355.00                           ║
║  Global Min:                          0.41                           ║
║  Global Max:                        999.98                           ║
║  Overall Average:                 500.0355                           ║
╠──────────────────────────────────────────────────────────────────────╣
║ 🚀 THROUGHPUT ANALYSIS                                                ║
╠──────────────────────────────────────────────────────────────────────╣
║  Effective Throughput:            1,276.03 params/sec                ║
║  CPU Throughput:                    504.38 params/sec                ║
║  Parallelism Factor:                  2.53x speedup                  ║
╠──────────────────────────────────────────────────────────────────────╣
║ 👷 WORKER DISTRIBUTION                                                ║
╠──────────────────────────────────────────────────────────────────────╣
║    worker-0:  40 chunks ( 40.0%) ████████░░░░░░░░░░░░                ║
║    worker-1:  30 chunks ( 30.0%) ██████░░░░░░░░░░░░░░                ║
║    worker-2:  30 chunks ( 30.0%) ██████░░░░░░░░░░░░░░                ║
╚══════════════════════════════════════════════════════════════════════╝
```

---

## Troubleshooting

### Common Issues

#### Workers Not Starting

```bash
# Check pod status
kubectl get pods -l ttg.io/mode=queue

# Check events
kubectl describe pod <pod-name>

# Common fixes:
# - Image not loaded: kind load docker-image ttg-worker:v1.2.0 --name ttg-sandbox
# - Redis not running: kubectl get pod ttg-redis
```

#### Workers Stuck "Waiting for Worker 0"

Workers 1, 2, etc. wait for Worker 0 to initialize the queue:

```bash
# Check Worker 0 logs
kubectl logs -l ttg.io/mode=queue | grep "WORKER-0"

# Verify tasks were created
kubectl exec ttg-redis -- redis-cli XLEN ttg:tasks
```

#### Connection Refused to Redis

```bash
# Verify Redis service
kubectl get svc ttg-redis

# Test connectivity from a pod
kubectl run -it --rm debug --image=redis:7.2-alpine -- redis-cli -h ttg-redis ping
```

#### RabbitMQ Connectivity Issues

```bash
# Check RabbitMQ pod and service
kubectl get pod ttg-rabbitmq
kubectl get svc ttg-rabbitmq

# Check broker health
kubectl exec ttg-rabbitmq -- rabbitmq-diagnostics -q ping

# Validate queue backend env in worker
kubectl logs -l ttg.io/queue-backend=rabbitmq | grep -i "Queue Backend"
```

#### Tasks Not Being Processed

```bash
# Check pending entries
kubectl exec ttg-redis -- redis-cli XPENDING ttg:tasks ttg-workers

# Check consumer group exists
kubectl exec ttg-redis -- redis-cli XINFO GROUPS ttg:tasks

# Reset if needed (will lose progress)
kubectl exec ttg-redis -- redis-cli XGROUP DESTROY ttg:tasks ttg-workers
```

### Cleanup Commands

```bash
# Strict TTG-only cleanup (recommended for shared machines)
./scripts/cleanup-ttg.sh --all

# Preview only (no changes)
./scripts/cleanup-ttg.sh --all --dry-run
```

Safety note: cleanup scripts are configured to target only TTG project resources and avoid deleting unrelated Docker workloads.

---

## API Reference

### TaskQueue Class (queue_utils.py)

```python
from queue_utils import TaskQueue

# Initialize
queue = TaskQueue(
    host='ttg-redis',
    port=6379,
    task_stream='ttg:tasks',
    result_stream='ttg:results',
    consumer_group='ttg-workers'
)

# Connect
queue.connect()

# Initialize tasks (Worker 0 only)
count = queue.initialize_tasks(total_params=10000, chunk_size=100)

# Get next task
task = queue.get_next_task(consumer_name='worker-0', block_ms=5000)
# Returns: {'chunk_id': '00042', 'start_param': 4200, 'end_param': 4300, ...}

# Acknowledge completion
queue.ack_task(task['message_id'])

# Publish result
queue.publish_result(
    chunk_id='00042',
    worker_id='worker-0',
    status='completed',
    duration_seconds=0.20,
    result_data={'sum': 45000.5, 'count': 100, ...}
)

# Get queue statistics
stats = queue.get_queue_stats()
# Returns: {'tasks_total': 100, 'tasks_pending': 5, 'results_count': 95, ...}

# Claim stale tasks (fault recovery)
claimed = queue.claim_stale_tasks(
    consumer_name='worker-0',
    min_idle_ms=60000,  # Tasks idle > 1 minute
    count=10
)

# Disconnect
queue.disconnect()
```

### QueueWorker Class (worker.py)

```python
from worker import QueueWorker

worker = QueueWorker(
    worker_id=0,
    redis_host='ttg-redis',
    redis_port=6379,
    total_params=10000,
    chunk_size=100,
    idle_timeout_seconds=30,
    simulate_work_ms=1
)

# Run (blocking)
result = worker.run()
# Returns: {'status': 'completed', 'chunks_processed': 40, ...}
```

---

## Fault Tolerance

### Overview

Version 1.2.1 includes **verified fault tolerance** using Redis Streams' XCLAIM mechanism and standalone pod architecture. When a worker crashes mid-processing, surviving workers continue independently and complete all tasks.

### ✅ VERIFIED Results (February 3, 2026)

| Metric               | Result                         |
| -------------------- | ------------------------------ |
| **Chunks Completed** | 100/100 (100%)                 |
| **Workers Deployed** | 3 (standalone pods)            |
| **Worker Killed At** | 30% progress                   |
| **Total Time**       | 44 seconds                     |
| **Throughput**       | 22 params/sec                  |
| **Data Loss**        | **ZERO** - all tasks completed |

### How It Works

1. **Standalone Pods**: Workers are deployed as independent pods, NOT managed by Job controller
2. **Task Tracking**: Every task claimed by a worker is added to Redis's Pending Entry List (PEL)
3. **Independent Processing**: When one worker dies, others continue unaffected
4. **Stale Detection**: Workers periodically check for tasks that have been pending "too long"
5. **Automatic Recovery**: Stale tasks are claimed using XCLAIM and processed by surviving workers
6. **At-Least-Once Delivery**: Tasks are only removed from PEL after acknowledgment

### Key Configuration

| Environment Variable           | Default | Description                                                   |
| ------------------------------ | ------- | ------------------------------------------------------------- |
| `STALE_CHECK_INTERVAL_SECONDS` | 30      | How often workers check for stale tasks                       |
| `STALE_THRESHOLD_MS`           | 60000   | Tasks pending longer than this are considered stale           |
| `IDLE_TIMEOUT_SECONDS`         | 30      | How long to wait before exiting (should be > stale threshold) |

### Running the Fault Tolerance Demo

```bash
# Full demo with fault injection (RECOMMENDED)
./scripts/run-demo.sh --scale small --fault-demo --monitor cli

# Options:
#   --scale small|medium    (1K or 10K params)
#   --workers N             (number of workers, default 3)
#   --fault-demo            (kill worker at 30%)
#   --monitor cli|web|both  (monitoring tools)
```

### Fault Recovery Flow

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        FAULT RECOVERY FLOW                               │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  Time 0s: Worker-2 claims task chunk_42                                  │
│           ├─ PEL: {chunk_42: worker-2, idle: 0s}                        │
│                                                                          │
│  Time 5s: Worker-2 CRASHES (killed, OOM, network failure)                │
│           ├─ PEL: {chunk_42: worker-2, idle: 5s}                        │
│           └─ Task still in PEL, NOT acknowledged                        │
│                                                                          │
│  Time 35s: Worker-0 runs stale check (interval=30s)                     │
│            ├─ Finds chunk_42 with idle=35s > threshold=30s              │
│            ├─ XCLAIM chunk_42 from worker-2 to worker-0                 │
│            └─ PEL: {chunk_42: worker-0, idle: 0s}                       │
│                                                                          │
│  Time 36s: Worker-0 processes chunk_42                                   │
│            ├─ Computes result                                           │
│            ├─ XACK chunk_42 (removes from PEL)                          │
│            └─ XADD result to ttg:results                                │
│                                                                          │
│  Result: Zero data loss despite worker crash!                            │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### Why Standalone Pods (Not Jobs)?

**Key Discovery:** Kubernetes Job controller with `backoffLimit: 0` terminates ALL pods when one fails. For fault tolerance demos, use **standalone pods** instead.

```yaml
# GOOD: Standalone pods (workers independent)
apiVersion: v1
kind: Pod
metadata:
  name: ttg-worker-0
spec:
  restartPolicy: Never
  ...

# BAD for fault demos: Job controller (cascading termination)
apiVersion: batch/v1
kind: Job
metadata:
  name: ttg-computation
spec:
  backoffLimit: 0  # <-- Will kill all pods on any failure!
```

### Viewing Recovery Logs

```bash
# Filter logs for recovery messages
kubectl logs -l app.kubernetes.io/name=ttg-worker | grep -i "FAULT\|RECOVERY\|claimed"

# Example output:
# [2026-02-03 ...] 🔄 FAULT RECOVERY: Found 1 stale tasks
# [2026-02-03 ...] 🔄 FAULT RECOVERY: Claimed chunk_42 from worker-2
# [2026-02-03 ...] 🔄 FAULT RECOVERY: Successfully processed recovered task
```

### Tuning Fault Tolerance

**For Faster Recovery (Demo/Testing):**

```yaml
env:
  - name: STALE_CHECK_INTERVAL_SECONDS
    value: "15" # Check more frequently
  - name: STALE_THRESHOLD_MS
    value: "30000" # 30 seconds (faster recovery)
```

**For Production (Avoid False Positives):**

```yaml
env:
  - name: STALE_CHECK_INTERVAL_SECONDS
    value: "60" # Check every minute
  - name: STALE_THRESHOLD_MS
    value: "120000" # 2 minutes (avoid claiming active tasks)
```

### Limitations

1. **At-Least-Once Delivery**: Tasks may be processed twice if a worker completes but crashes before ACK
2. **Recovery Time**: Recovery is not instant; depends on stale check interval + threshold
3. **Consumer Group Required**: Only works with consumer groups (XREADGROUP), not XREAD

---

## FAQ

### Q: How is this different from Milestone 1?

**Milestone 1 (Static Mode):**

- Workers get pre-assigned parameter ranges
- No fault tolerance - if worker crashes, work is lost
- Results printed to stdout

**Milestone 2 (Queue Mode):**

- Workers pull tasks dynamically from Redis
- Fault tolerant - crashed tasks can be recovered
- Results stored persistently in Redis

### Q: What happens if a worker crashes mid-task?

The task remains in the Pending Entry List (PEL). After the configured timeout, another worker can claim it using `XCLAIM` (implemented in `claim_stale_tasks`).

### Q: Can I run both modes simultaneously?

Yes, but they use different manifests and don't share data:

- Static mode: `parallel-jobs.yaml`
- Queue mode: `parallel-jobs-queue.yaml`

### Q: How do I scale to more workers?

Edit `k8s/manifests/parallel-jobs-queue.yaml`:

```yaml
spec:
  completions: 10 # Total workers
  parallelism: 10 # Max concurrent
```

### Q: What's the optimal chunk size?

It depends on task complexity:

- **Small chunks (50-100)**: Better load balancing, more overhead
- **Large chunks (500-1000)**: Less overhead, risk of uneven distribution

For our simulated work (1ms/param), 100 is optimal.

---

## Version History

| Version | Date     | Changes                                |
| ------- | -------- | -------------------------------------- |
| 1.2.0   | Feb 2026 | Initial queue mode implementation      |
| 1.1.0   | Jan 2026 | Parallel Kubernetes jobs (static mode) |
| 1.0.0   | Dec 2025 | Basic containerized worker             |

---

## Related Documentation

- [PROJECT_OVERVIEW.md](../tracking/PROJECT_OVERVIEW.md) - High-level project description
- [KUBERNETES_SETUP.md](../setup/KUBERNETES_SETUP.md) - Cluster setup guide
- [CONFIGURATION_GUIDE.md](CONFIGURATION_GUIDE.md) - Environment variables
- [TEST_RESULTS_M1_PARALLEL_JOBS.md](../results/TEST_RESULTS_M1_PARALLEL_JOBS.md) - Milestone 1 results
