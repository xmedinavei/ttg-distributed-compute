# Deliverable 3 -- Engineering Playbook

**Project:** TTG Distributed Computation System
**Date:** February 10, 2026
**Version:** 1.3.0
**Author:** Xavier / TTG Team

---

## Table of Contents

1. [Architecture Diagrams](#1-architecture-diagrams)
2. [Data Flow Diagrams](#2-data-flow-diagrams)
3. [Queue Topology Reference](#3-queue-topology-reference)
4. [Configuration Reference](#4-configuration-reference)
5. [Step-by-Step Implementation Guides](#5-step-by-step-implementation-guides)
6. [Decision Log](#6-decision-log)

---

## 1. Architecture Diagrams

### 1.1 Milestone 1 -- Static Distribution

```
+-------------------------------------------------------------------+
|                  KUBERNETES CLUSTER (Kind)                          |
|                                                                     |
|   +-----------+                                                     |
|   | CONTROL   |  Schedules Jobs across worker nodes                 |
|   | PLANE     |                                                     |
|   +-----------+                                                     |
|         |                                                           |
|   +-----+-------+-------+                                          |
|   |             |       |                                           |
|   v             v       v                                           |
|  +----------+ +----------+ +----------+                             |
|  | Worker 0 | | Worker 1 | | Worker 2 |                             |
|  | Node 1   | | Node 2   | | Node 3   |                             |
|  |          | |          | |          |                             |
|  | Params:  | | Params:  | | Params:  |                             |
|  | 0-3333   | | 3334-6666| | 6667-9999|                             |
|  +----+-----+ +----+-----+ +----+-----+                             |
|       |             |            |                                   |
|       v             v            v                                   |
|    STDOUT        STDOUT       STDOUT                                 |
|                                                                     |
|  NO COORDINATION -- each worker calculates its own range            |
|  NO FAULT TOLERANCE -- if Worker 1 dies, params 3334-6666 are LOST  |
+---------------------------------------------------------------------+
```

**Components:** Kubernetes Job with indexed completions (`JOB_COMPLETION_INDEX`).

### 1.2 Milestone 2 -- Redis Streams Queue

```
+---------------------------------------------------------------------+
|                   KUBERNETES CLUSTER                                  |
|                                                                       |
|  +----------+  +----------+  +----------+                             |
|  | Worker 0 |  | Worker 1 |  | Worker 2 |                             |
|  |          |  |  X DIES  |  |          |                             |
|  +----+-----+  +----+-----+  +----+-----+                             |
|       |              |             |                                   |
|       | XREADGROUP   |             | XREADGROUP                        |
|       | XACK         |             | XACK + XCLAIM                     |
|       |              |             |                                   |
|       +------+-------+------+------+                                   |
|              |                                                         |
|        +-----v------+                                                  |
|        |   REDIS    |                                                  |
|        |            |                                                  |
|        | ttg:tasks  |-- Task Stream (100 chunks)                       |
|        | ttg:results|-- Results Stream                                  |
|        | Consumer   |                                                  |
|        | Group:     |                                                  |
|        | ttg-workers|                                                  |
|        +------------+                                                  |
|                                                                        |
|  FAULT TOLERANCE: Worker 1 dies -> stale tasks -> XCLAIM -> 100% done  |
+------------------------------------------------------------------------+
```

**Components:** Redis Pod + Service, standalone worker Pods, Consumer Group.

### 1.3 Milestone 3 -- Dual Backend (Redis + RabbitMQ)

```
+------------------------------------------------------------------------+
|                     KUBERNETES CLUSTER                                   |
|                                                                          |
|  +----------+  +----------+  +----------+                                |
|  | Worker 0 |  | Worker 1 |  | Worker 2 |                                |
|  +----+-----+  +----+-----+  +----+-----+                                |
|       |              |             |                                      |
|       +------+-------+------+------+                                      |
|              |                                                            |
|   QUEUE_BACKEND env var selects path:                                     |
|              |                                                            |
|     +--------+--------+                                                   |
|     |                 |                                                   |
|     v                 v                                                   |
|  +--------+    +-----------+                                              |
|  | REDIS  |    | RABBITMQ  |                                              |
|  | :6379  |    | :5672     |                                              |
|  |        |    | :15672 UI |                                              |
|  | Streams|    |           |                                              |
|  | + CG   |    | ttg.tasks |-- Main queue                                |
|  |        |    | ttg.results -- Results queue                             |
|  |        |    | ttg.tasks.retry -- Retry queue (TTL)                     |
|  |        |    | ttg.tasks.dlq -- Dead-letter queue                       |
|  +--------+    +-----------+                                              |
|                                                                           |
|  Both backends: 100% completion, ZERO data loss under fault               |
+---------------------------------------------------------------------------+
```

**Components:** Redis Pod, RabbitMQ Pod (with Management UI), standalone worker Pods.

---

## 2. Data Flow Diagrams

### 2.1 Task Lifecycle (Redis Path)

```
Step 1: INITIALIZATION
  Worker 0 checks if ttg:tasks stream is empty
  If empty, Worker 0 creates 100 task chunks via XADD
  Creates consumer group "ttg-workers"

Step 2: DISTRIBUTION
  Each worker: XREADGROUP GROUP ttg-workers CONSUMER worker-N BLOCK 5000 STREAMS ttg:tasks >
  Redis delivers the next undelivered message to exactly one consumer

Step 3: PROCESSING
  Worker receives chunk: {chunk_id, start_param, end_param, total_in_chunk}
  Worker processes all parameters in the chunk
  Worker publishes result: XADD ttg:results * chunk_id ... status complete ...

Step 4: ACKNOWLEDGMENT
  Worker: XACK ttg:tasks ttg-workers <message-id>
  Redis marks the message as processed (will not be redelivered)

Step 5: FAULT RECOVERY (if a worker dies before XACK)
  Every 30 seconds, surviving workers check: XPENDING ttg:tasks ttg-workers
  If a message has been pending > 60 seconds (STALE_THRESHOLD_MS):
    Worker: XCLAIM ttg:tasks ttg-workers <consumer-name> 60000 <message-id>
    Worker processes the reclaimed chunk
    Worker: XACK

Step 6: COMPLETION
  Workers poll for new tasks until queue is empty
  After IDLE_TIMEOUT_SECONDS (30s) with no tasks, worker exits gracefully
```

### 2.2 Task Lifecycle (RabbitMQ Path)

```
Step 1: INITIALIZATION
  Worker 0 declares queue topology:
    - ttg.tasks (main queue, durable)
    - ttg.results (results queue, durable)
    - ttg.tasks.retry (retry queue with x-message-ttl, routes to ttg.tasks)
    - ttg.tasks.dlq (dead-letter queue)
  Worker 0 publishes 100 task chunks to ttg.tasks

Step 2: DISTRIBUTION
  Each worker: channel.basic_get(queue='ttg.tasks', auto_ack=False)
  RabbitMQ delivers one message to one consumer (prefetch=1)

Step 3: PROCESSING
  Worker receives chunk: {chunk_id, start_param, end_param, total_in_chunk}
  Worker processes all parameters in the chunk
  Worker publishes result to ttg.results

Step 4: ACKNOWLEDGMENT
  Worker: channel.basic_ack(delivery_tag=...)
  RabbitMQ removes message from the queue

Step 5: FAULT RECOVERY (if a worker dies before basic_ack)
  Worker's TCP connection drops
  RabbitMQ automatically requeues all unacknowledged messages
  Surviving workers immediately see the requeued messages

Step 6: FAILURE HANDLING (if processing fails)
  Worker: channel.basic_nack(delivery_tag=..., requeue=False)
  Message routes to ttg.tasks.retry (waits for TTL)
  After TTL expires, message re-enters ttg.tasks
  If retry count exhausted, message routes to ttg.tasks.dlq

Step 7: COMPLETION
  Workers poll until queue is empty
  After IDLE_TIMEOUT_SECONDS with no tasks, worker exits gracefully
```

### 2.3 Message Schemas

**Task Message:**

```json
{
  "chunk_id": "00042",
  "start_param": 4100,
  "end_param": 4199,
  "total_in_chunk": 100,
  "created_at": "2026-02-09T10:00:00Z"
}
```

**Result Message:**

```json
{
  "chunk_id": "00042",
  "worker_id": "worker-0",
  "status": "complete",
  "params_processed": 100,
  "duration_seconds": 0.35,
  "result_summary": {"sum": 421950, "count": 100},
  "completed_at": "2026-02-09T10:00:12Z"
}
```

---

## 3. Queue Topology Reference

### 3.1 Redis Streams Topology

```
+-------------------+       +-------------------+
|  ttg:tasks        |       |  ttg:results      |
|  (Task Stream)    |       |  (Result Stream)  |
|                   |       |                   |
|  Consumer Group:  |       |  No consumer      |
|  ttg-workers      |       |  group (append)   |
|                   |       |                   |
|  Consumers:       |       |                   |
|  - worker-0       |       |                   |
|  - worker-1       |       |                   |
|  - worker-2       |       |                   |
+-------------------+       +-------------------+
```

**Key commands:**
- `XADD ttg:tasks * key value` -- Add task to stream
- `XGROUP CREATE ttg:tasks ttg-workers 0 MKSTREAM` -- Create consumer group
- `XREADGROUP GROUP ttg-workers CONSUMER worker-0 BLOCK 5000 STREAMS ttg:tasks >` -- Read next task
- `XACK ttg:tasks ttg-workers <msg-id>` -- Acknowledge completion
- `XCLAIM ttg:tasks ttg-workers worker-0 60000 <msg-id>` -- Reclaim stale task
- `XPENDING ttg:tasks ttg-workers` -- List pending (unacknowledged) messages
- `XLEN ttg:tasks` -- Count messages in stream

### 3.2 RabbitMQ Queue Topology

```
                         +------------------+
                         |  Default Exchange|
                         +--------+---------+
                                  |
                    +-------------+-------------+
                    |                           |
                    v                           v
          +-----------------+         +-------------------+
          |  ttg.tasks      |         |  ttg.results      |
          |  (Main Queue)   |         |  (Results Queue)  |
          |  Durable: yes   |         |  Durable: yes     |
          +---------+-------+         +-------------------+
                    |
          (on nack/reject)
                    |
                    v
        +---------------------+
        | ttg.tasks.retry     |
        | (Retry Queue)       |
        | x-message-ttl: 5000 |
        | x-dead-letter-      |
        |   exchange: ""      |
        | x-dead-letter-      |
        |   routing-key:      |
        |   ttg.tasks         |
        +----------+----------+
                   |
           (after TTL expires)
                   |
                   v
          +-----------------+
          |  ttg.tasks      |   <-- message re-enters main queue
          +-----------------+
                   |
           (if max retries
            exceeded)
                   |
                   v
        +---------------------+
        | ttg.tasks.dlq       |
        | (Dead Letter Queue) |
        | For manual review   |
        +---------------------+
```

---

## 4. Configuration Reference

### 4.1 Worker Environment Variables

| Variable | Default | Description | Affects |
|----------|---------|-------------|---------|
| `WORKER_ID` | `0` | Unique worker identifier | Logging, consumer name |
| `TOTAL_WORKERS` | `3` | Total number of workers | M1 range calculation |
| `TOTAL_PARAMETERS` | `10000` | Parameters to process | Workload size |
| `BATCH_SIZE` | `500` | Progress update interval | Log frequency |
| `CHUNK_SIZE` | `100` | Params per queue chunk | Queue granularity |
| `SIMULATE_WORK_MS` | `1` | Simulated work per param | Processing speed |
| `LOG_LEVEL` | `INFO` | Log verbosity | Output detail |
| `LOG_FORMAT` | `text` | Log format | `text` or `json` |
| `QUEUE_MODE` | `false` | Enable queue distribution | M1 vs M2/M3 mode |
| `QUEUE_BACKEND` | `redis` | Queue backend | `redis` or `rabbitmq` |
| `REDIS_HOST` | `ttg-redis` | Redis hostname | Redis connection |
| `REDIS_PORT` | `6379` | Redis port | Redis connection |
| `RABBITMQ_HOST` | `ttg-rabbitmq` | RabbitMQ hostname | RabbitMQ connection |
| `RABBITMQ_PORT` | `5672` | RabbitMQ AMQP port | RabbitMQ connection |
| `IDLE_TIMEOUT_SECONDS` | `30` | Exit after no tasks for N seconds | Worker lifecycle |
| `STALE_CHECK_INTERVAL_SECONDS` | `30` | Stale task check frequency | Redis fault recovery |
| `STALE_THRESHOLD_MS` | `60000` | Task staleness threshold | Redis fault recovery |
| `SIMULATE_FAULT_RATE` | `0.0` | Fault simulation probability | Testing |

### 4.2 Kubernetes Resource Defaults

| Component | CPU Request | CPU Limit | Memory Request | Memory Limit | Storage |
|-----------|-------------|-----------|----------------|--------------|---------|
| Worker | 100m | 500m | 128Mi | 256Mi | -- |
| Redis | 100m | 500m | 128Mi | 256Mi | 1Gi PVC |
| RabbitMQ | 200m | 1000m | 256Mi | 1Gi | 2Gi PVC |

### 4.3 Demo Presets

| Preset | Parameters | Chunks | Chunk Size | Simulated Work | Expected Runtime |
|--------|-----------|--------|------------|----------------|-----------------|
| `small` | 1,000 | 100 | 10 | 100ms/chunk | ~36-49s |
| `medium` | 10,000 | 100 | 100 | 10ms/chunk | ~38-41s |

---

## 5. Step-by-Step Implementation Guides

### 5.1 Setting Up the Cluster from Scratch

**Prerequisites:** Docker, kind, kubectl installed.

```bash
# Clone the repository
git clone https://github.com/xmedinavei/ttg-distributed-compute.git
cd ttg-distributed-compute

# Create Kind cluster (4 nodes) and build initial image
./k8s/local/setup-local.sh

# Build versioned image and load into Kind
./scripts/build.sh --version 1.3.0 --load-kind

# Verify
kubectl get nodes    # Expect 4 nodes, all Ready
kubectl get pods     # Expect no pods yet
```

### 5.2 Running with Redis Backend

```bash
# Deploy Redis
kubectl apply -f k8s/manifests/redis.yaml
kubectl wait --for=condition=ready pod/ttg-redis --timeout=60s

# Verify Redis
kubectl exec ttg-redis -- redis-cli ping  # Expect: PONG

# Run demo (one command)
./scripts/run-demo.sh --backend redis --scale small --fault-demo --monitor cli

# Or deploy manually
kubectl apply -f k8s/manifests/parallel-workers-standalone.yaml

# Monitor
python3 scripts/queue_monitor.py

# Cleanup
./scripts/cleanup-ttg.sh --pods --force
```

### 5.3 Running with RabbitMQ Backend

```bash
# Deploy RabbitMQ
kubectl apply -f k8s/manifests/rabbitmq.yaml
kubectl wait --for=condition=ready pod/ttg-rabbitmq --timeout=120s

# Verify RabbitMQ
kubectl exec ttg-rabbitmq -- rabbitmq-diagnostics -q ping  # Expect: Ping succeeded

# Access Management UI
kubectl port-forward pod/ttg-rabbitmq 15672:15672
# Open: http://localhost:15672 (guest/guest)

# Run demo (one command)
./scripts/run-demo.sh --backend rabbitmq --scale small --fault-demo --monitor both

# Or deploy manually
kubectl apply -f k8s/manifests/parallel-jobs-queue-rabbitmq.yaml

# Monitor
./scripts/rabbitmq_monitor.sh --watch 2

# Cleanup
./scripts/cleanup-ttg.sh --pods --rabbitmq --force
```

### 5.4 Monitoring and Observability

```bash
# === Redis Monitoring ===

# CLI dashboard (real-time)
python3 scripts/queue_monitor.py

# RedisInsight web UI
kubectl apply -f k8s/manifests/redis-insight.yaml
kubectl port-forward pod/redis-insight 8001:8001
# Open: http://localhost:8001

# Manual Redis checks
kubectl exec ttg-redis -- redis-cli XLEN ttg:tasks        # Task count
kubectl exec ttg-redis -- redis-cli XLEN ttg:results      # Result count
kubectl exec ttg-redis -- redis-cli XPENDING ttg:tasks ttg-workers  # Pending tasks

# === RabbitMQ Monitoring ===

# CLI snapshot
./scripts/rabbitmq_monitor.sh

# Continuous monitoring
./scripts/rabbitmq_monitor.sh --watch 2

# Management UI
kubectl port-forward pod/ttg-rabbitmq 15672:15672
# Open: http://localhost:15672 (guest/guest)

# Manual RabbitMQ checks
kubectl exec ttg-rabbitmq -- rabbitmqctl list_queues name messages consumers

# === Kubernetes Monitoring ===

# Pod status
kubectl get pods -w

# Worker logs (all)
kubectl logs -l ttg.io/component=worker --all-containers -f

# Specific worker log
kubectl logs ttg-worker-0

# Node placement
kubectl get pods -o wide

# Resource usage
kubectl top pods
kubectl top nodes
```

### 5.5 Fault Tolerance Verification

```bash
# Method 1: Automated via demo script
./scripts/run-demo.sh --backend rabbitmq --scale small --fault-demo --monitor both

# Method 2: Manual fault injection
# Terminal 1: Start workers
kubectl apply -f k8s/manifests/parallel-workers-standalone.yaml

# Terminal 2: Watch progress
kubectl logs -l ttg.io/component=worker -f

# Terminal 3: After ~30% completion, kill a worker
kubectl delete pod ttg-worker-1

# Observe: remaining workers continue
# Check final results:
kubectl exec ttg-redis -- redis-cli XLEN ttg:results  # Should be 100
```

---

## 6. Decision Log

### Technology Decisions

| Date | Decision | Rationale | Alternatives Considered |
|------|----------|-----------|------------------------|
| Jan 26 | Use Kind for local K8s | Free, fast, real multi-node cluster | minikube (single-node), k3s (lighter but less realistic) |
| Jan 26 | Python for workers | Team expertise, good Redis/AMQP libraries | Go (better performance), Java (enterprise standard) |
| Jan 26 | 3 worker nodes | Matches milestone requirement; enough to demo fault tolerance | More nodes (higher resource cost) |
| Jan 26 | Kubernetes Jobs (M1) | Native K8s pattern, no external dependencies | Manual pod creation |
| Jan 30 | Redis Streams for M2 | Best balance: simplicity + reliability. Scored 4.15/5 in weighted matrix | Redis Lists (no ACK), RabbitMQ (overkill for MVP), Kafka (way overkill), Celery (tied score but adds abstraction layer) |
| Feb 3 | Standalone Pods for fault demos | Jobs with backoffLimit=0 terminate ALL pods on any failure | Jobs with backoffLimit>0 (restarts but doesn't demonstrate independent pods) |
| Feb 9 | Add RabbitMQ (M3) | Production-grade retry/DLQ, management UI, AMQP standard | Replace Redis entirely (too risky without fallback) |
| Feb 9 | Keep Redis as fallback | Proven, tested path; provides rollback safety | Deprecate Redis immediately (too aggressive) |

### Architecture Decisions

| Decision | Why | Impact |
|----------|-----|--------|
| Queue-based (not static) distribution | Enables fault tolerance, dynamic scaling, visibility | Core architecture change from M1 to M2 |
| Consumer Groups (not competing consumers) | Exactly-once delivery guarantee per chunk | No duplicate processing |
| XCLAIM for fault recovery | Reclaims stale tasks from dead consumers | Automatic fault tolerance |
| Dual-backend via env var | Easy switching, A/B testing, rollback safety | Operational flexibility |
| Non-root containers | Security best practice; reduces attack surface | All manifests and Dockerfile updated |
| PVC for Redis and RabbitMQ | Data survives pod restarts | Reliability without external storage |
| Safe cleanup scripts | Shared machine protection (never delete non-TTG resources) | Operational safety |
| Structured logging (text + JSON) | Human-readable for dev, machine-parseable for prod | Future log aggregation ready |

---

**Playbook Version:** 1.0
**Prepared By:** Xavier / TTG Team
**Repository:** https://github.com/xmedinavei/ttg-distributed-compute
