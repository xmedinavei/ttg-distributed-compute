# Milestone 2: Message Queue Architecture

## Distributed Task Queue Implementation

**Document Created:** January 30, 2026  
**Completed:** February 3, 2026  
**Status:** ✅ **COMPLETE**

---

## 🎉 MILESTONE 2 COMPLETE

> **Final Results:** Fault tolerance verified with 100/100 chunks completed in 44 seconds (22 params/sec) despite worker killed at 30% progress.

### Achievement Summary

| Metric              | Result                                 |
| ------------------- | -------------------------------------- |
| **Total Chunks**    | 100/100 completed                      |
| **Workers**         | 3 parallel (standalone pods)           |
| **Fault Injection** | Worker killed at 30% progress          |
| **Completion Time** | 44 seconds                             |
| **Throughput**      | 22 params/sec                          |
| **Fault Tolerance** | ✅ **VERIFIED** - 100% despite failure |

### Key Deliverables

| Deliverable          | Status      | Notes                            |
| -------------------- | ----------- | -------------------------------- |
| Redis Streams in K8s | ✅ Complete | Pod + Service + PVC              |
| Queue-based workers  | ✅ Complete | v1.2.1 with QueueWorker class    |
| Consumer Groups      | ✅ Complete | XREADGROUP + XACK pattern        |
| Fault tolerance      | ✅ Complete | Standalone pods, XCLAIM recovery |
| Demo script          | ✅ Complete | `run-demo.sh --fault-demo`       |
| Cleanup script       | ✅ Complete | `cleanup-ttg.sh` with safety     |
| Documentation        | ✅ Complete | All guides updated               |

---

## Original Timeline (Compressed to 1 Day)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    MILESTONE 2: 2-WEEK SPRINT                               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  WEEK 1: Core Implementation              WEEK 2: Testing & Documentation   │
│  ══════════════════════════               ═══════════════════════════════   │
│                                                                             │
│  Day 1-2      Day 3-4       Day 5        Day 6-7      Day 8-9     Day 10   │
│  ┌──────┐    ┌──────┐    ┌──────┐      ┌──────┐    ┌──────┐    ┌──────┐   │
│  │Redis │    │Worker│    │ Kind │      │Fault │    │ Docs │    │Buffer│   │
│  │Setup │───▶│Refact│───▶│Deploy│─────▶│Tests │───▶│Update│───▶│/Demo │   │
│  │+Learn│    │ +Test│    │ E2E  │      │Scale │    │Clean │    │      │   │
│  └──────┘    └──────┘    └──────┘      └──────┘    └──────┘    └──────┘   │
│                                                                             │
│  ✓ Redis works  ✓ Queue mode  ✓ 10K test  ✓ Fault OK  ✓ Runbook  ✓ Done!  │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Key Simplifications for 2-Week Delivery

| Original Plan            | Simplified Approach        | Time Saved |
| ------------------------ | -------------------------- | ---------- |
| Separate Coordinator job | Worker 0 initializes tasks | 3 days     |
| Separate Aggregator job  | Query Redis manually       | 2 days     |
| Persistent Redis storage | In-memory (MVP acceptable) | 1 day      |
| Helm chart deployment    | Simple Pod + Service YAML  | 0.5 day    |
| Celery integration       | Deferred to future         | 2 weeks    |
| Complex error handling   | Simple retry + logging     | 1 day      |

### What's IN Scope (MVP)

✅ Redis Streams in Kubernetes  
✅ Workers pull tasks dynamically  
✅ Fault tolerance (unacked tasks requeue)  
✅ Feature toggle (old mode still works)  
✅ 10K & 100K parameter tests  
✅ Updated documentation

### What's OUT of Scope (Deferred)

❌ Celery integration  
❌ Flower monitoring dashboard  
❌ Persistent Redis storage  
❌ Separate Coordinator/Aggregator jobs  
❌ Complex dead-letter queue  
❌ Azure AKS deployment

---

## Executive Summary

This document outlines the plan for Milestone 2: implementing a **message queue-based architecture** to replace the current static range partitioning system. This evolution will provide dynamic load balancing, fault tolerance, and better scalability for the TTG distributed computation system.

### Current State vs. Target State

| Aspect            | Milestone 1 (Current)          | Milestone 2 (Target)                  |
| ----------------- | ------------------------------ | ------------------------------------- |
| Work Distribution | Static (calculated at startup) | Dynamic (pulled from queue)           |
| Fault Tolerance   | None (failed work is lost)     | Automatic retry & requeue             |
| Load Balancing    | Fixed ranges per worker        | Work stealing (fast workers get more) |
| Scalability       | Requires reconfiguration       | Add workers on-the-fly                |
| Visibility        | Logs only                      | Queue depth, progress tracking        |
| Task Granularity  | Fixed per worker               | Configurable chunk sizes              |

---

## Why Message Queue?

### Current Limitations

The Milestone 1 implementation uses **static range partitioning**:

```python
# Current approach (worker.py)
def _calculate_range(self) -> tuple:
    params_per_worker = self.total_parameters // self.total_workers
    start = self.worker_id * params_per_worker
    end = start + params_per_worker
    return start, end
```

**Problems with this approach:**

1. **No Fault Tolerance**: If Worker 1 crashes after processing 50% of its range, that work is lost. The job either fails completely or produces incomplete results.

2. **No Dynamic Load Balancing**: If Worker 1's parameters are computationally harder, it becomes a bottleneck while Workers 2 and 3 sit idle after finishing.

3. **Rigid Scaling**: Adding or removing workers requires reconfiguring and redeploying the entire job.

4. **No Visibility**: We can't see how much work is pending vs. completed without parsing logs.

5. **All-or-Nothing**: Can't pause, resume, or prioritize work.

### Message Queue Benefits

```
┌─────────────────────────────────────────────────────────────────────────┐
│                     MESSAGE QUEUE ADVANTAGES                            │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ✅ FAULT TOLERANCE                                                     │
│     Worker crashes → Message returns to queue → Another worker picks up │
│                                                                         │
│  ✅ DYNAMIC LOAD BALANCING                                              │
│     Fast workers pull more tasks → No idle workers                      │
│                                                                         │
│  ✅ ELASTIC SCALING                                                     │
│     Add workers anytime → They start pulling tasks immediately          │
│                                                                         │
│  ✅ VISIBILITY & CONTROL                                                │
│     See queue depth → Estimate completion → Pause/resume work           │
│                                                                         │
│  ✅ RETRY & ERROR HANDLING                                              │
│     Failed tasks → Dead letter queue → Debug and reprocess              │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Message Queue Broker Comparison

### Overview of Options

We evaluated five message queue solutions for TTG:

| Solution          | Type                                | Primary Use Case                     |
| ----------------- | ----------------------------------- | ------------------------------------ |
| **Redis (Lists)** | In-memory store + queue patterns    | Simple, fast task queues             |
| **Redis Streams** | Persistent log with consumer groups | Reliable task queues with ACK        |
| **RabbitMQ**      | Traditional AMQP message broker     | Complex routing, guaranteed delivery |
| **Apache Kafka**  | Distributed event streaming         | High throughput, event sourcing      |
| **Celery**        | Python task queue framework         | Python apps with rich task features  |

---

### 1. Redis (List-based Queue)

**Architecture:**

```
Producer ──LPUSH──▶ [ Redis List ] ◀──BRPOP── Workers
                    [task][task][task]
```

**How it works:**

- Producer pushes tasks with `LPUSH`
- Workers pop tasks with `BRPOP` (blocking pop)
- Simple, fast, minimal overhead

**Pros:**
| ✅ Advantage | Description |
|-------------|-------------|
| Simplicity | 5 commands to learn (LPUSH, BRPOP, LLEN, etc.) |
| Speed | Sub-millisecond latency |
| Ubiquity | Already deployed in most K8s environments |
| Dual-purpose | Can serve as queue AND result store |
| Low resources | Single pod, ~256MB RAM for millions of tasks |

**Cons:**
| ❌ Disadvantage | Description |
|----------------|-------------|
| No acknowledgment | If worker crashes mid-task, message is lost |
| No consumer groups | Manual work distribution needed |
| No persistence | Default is in-memory only (AOF optional) |
| No dead-letter queue | Must implement manually |

**Verdict:** Good for simple cases, but lacks reliability for production workloads.

---

### 2. Redis Streams

**Architecture:**

```
Producer ──XADD──▶ [ Redis Stream ] ◀──XREADGROUP── Consumer Group
                   │ ID: 1-0 │ task │              ├── Worker 1
                   │ ID: 1-1 │ task │              ├── Worker 2
                   │ ID: 1-2 │ task │              └── Worker 3
                   └─────────┴──────┘
                        │
                    XACK (acknowledge)
```

**How it works:**

- Persistent append-only log (like Kafka, but simpler)
- Consumer groups distribute messages to workers
- XACK confirms processing; unacked messages are redelivered
- XPENDING shows stuck/failed messages

**Pros:**
| ✅ Advantage | Description |
|-------------|-------------|
| Acknowledgment | XACK ensures at-least-once delivery |
| Consumer groups | Built-in work distribution |
| Persistence | Survives Redis restart (with AOF) |
| Pending tracking | XPENDING shows unprocessed messages |
| Replayability | Can re-read stream from any point |
| Same Redis | No new infrastructure if already using Redis |

**Cons:**
| ❌ Disadvantage | Description |
|----------------|-------------|
| Learning curve | More commands (XADD, XREADGROUP, XACK, XPENDING) |
| Manual DLQ | Dead-letter pattern requires custom logic |
| No routing | All messages go to same stream (unlike RabbitMQ exchanges) |
| Memory | Streams grow; need XTRIM to manage |

**Verdict:** ⭐ **Strong candidate** - balances simplicity with reliability.

---

### 3. RabbitMQ

**Architecture:**

```
Producer ──▶ [ Exchange ] ──routing──▶ [ Queue ] ◀── Consumer
                  │                        │
             (direct, topic,          (durable,
              fanout, headers)         exclusive,
                                       auto-delete)
```

**How it works:**

- AMQP protocol (industry standard)
- Exchanges route messages to queues based on rules
- Queues hold messages until acknowledged
- Dead-letter exchanges for failed messages

**Pros:**
| ✅ Advantage | Description |
|-------------|-------------|
| Rich routing | Direct, topic, fanout, headers exchanges |
| Reliability | Persistent messages, publisher confirms |
| Dead-letter queues | Built-in, configurable |
| Management UI | Web dashboard for monitoring |
| Mature | 15+ years, battle-tested |
| Plugins | Shovel, Federation, MQTT, STOMP |

**Cons:**
| ❌ Disadvantage | Description |
|----------------|-------------|
| Complexity | Exchanges, bindings, virtual hosts to learn |
| Resource usage | ~500MB+ RAM, Java/Erlang runtime |
| Operations | Cluster management, upgrades more complex |
| Overkill | For simple task queues, too much machinery |

**Verdict:** Excellent for complex routing needs, but overkill for TTG's current requirements.

---

### 4. Apache Kafka

**Architecture:**

```
Producer ──▶ [ Topic: ttg-tasks        ] ◀── Consumer Group
             │ Partition 0 │ Partition 1 │      ├── Consumer 1 (P0)
             │ msg│msg│msg │ msg│msg│msg │      └── Consumer 2 (P1)
             └─────────────┴─────────────┘
                    │
              Offset tracking
              (committed offsets)
```

**How it works:**

- Distributed commit log
- Topics divided into partitions
- Consumer groups track offsets per partition
- Extremely high throughput (millions/sec)

**Pros:**
| ✅ Advantage | Description |
|-------------|-------------|
| Throughput | 1M+ messages/second |
| Durability | Replicated, persistent log |
| Replayability | Re-consume from any offset |
| Scalability | Horizontal scaling via partitions |
| Ecosystem | Kafka Streams, ksqlDB, Connectors |

**Cons:**
| ❌ Disadvantage | Description |
|----------------|-------------|
| Complexity | Zookeeper (or KRaft), brokers, partitions |
| Latency | Higher than Redis (~10-100ms) |
| Resources | 3+ brokers, significant RAM/disk |
| Learning curve | Steep; many concepts to master |
| Cost | Expensive to run (compute + storage) |
| Partition ceiling | Consumer count limited by partition count |

**Verdict:** Massive overkill for TTG. Designed for event streaming, not task queues.

---

### 5. Celery (with Redis backend)

**Architecture:**

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Client    │────▶│   Broker    │◀────│   Workers   │
│ (send_task) │     │   (Redis)   │     │  (Celery)   │
└─────────────┘     └─────────────┘     └─────────────┘
                          │                   │
                          │                   ▼
                    ┌─────────────┐     ┌─────────────┐
                    │   Flower    │     │   Backend   │
                    │ (dashboard) │     │  (results)  │
                    └─────────────┘     └─────────────┘
```

**How it works:**

- Python framework wrapping Redis/RabbitMQ
- Decorators define tasks: `@app.task`
- Workers managed by Celery (not K8s directly)
- Result backend stores return values

**Pros:**
| ✅ Advantage | Description |
|-------------|-------------|
| Python-native | Decorators, async support, type hints |
| Rich features | Retry, rate limits, task chains, groups |
| Monitoring | Flower dashboard (beautiful!) |
| Backend flexibility | Redis, RabbitMQ, SQS, etc. |
| Scheduling | Celery Beat for periodic tasks |
| Battle-tested | Used by Instagram, Mozilla, Yandex |

**Cons:**
| ❌ Disadvantage | Description |
|----------------|-------------|
| Python only | Can't use with other languages |
| Abstraction | Hides underlying broker details |
| Overhead | Extra layer (Celery + Broker + Backend) |
| Learning curve | Celery concepts on top of queue concepts |
| Worker management | Celery workers vs. K8s pods (some overlap) |

**Verdict:** ⭐ **Strong candidate** - excellent for Python projects with task management needs.

---

## Comparison Matrix

### Feature Comparison

| Feature               | Redis Lists | Redis Streams |    RabbitMQ    |     Kafka      |     Celery     |
| --------------------- | :---------: | :-----------: | :------------: | :------------: | :------------: |
| **Setup Complexity**  |   ⭐ Easy   |  ⭐⭐ Medium  | ⭐⭐⭐ Complex | ⭐⭐⭐⭐ Hard  |  ⭐⭐ Medium   |
| **Latency**           |    ~1ms     |     ~1ms      |      ~5ms      |   ~10-100ms    |    ~5-10ms     |
| **Throughput**        |    High     |     High      |     Medium     |   Very High    |     Medium     |
| **Persistence**       | ⚠️ Optional |    ✅ Yes     |     ✅ Yes     |     ✅ Yes     |    Backend     |
| **Acknowledgments**   |    ❌ No    |    ✅ XACK    |     ✅ Yes     |   ✅ Offsets   |     ✅ Yes     |
| **Consumer Groups**   |    ❌ No    |    ✅ Yes     |     ✅ Yes     |     ✅ Yes     |     ✅ Yes     |
| **Dead Letter Queue** |   ❌ DIY    |   ⚠️ Manual   |  ✅ Built-in   |   ⚠️ Manual    |  ✅ Built-in   |
| **Message Routing**   |   ❌ None   |   ❌ Basic    |    ✅ Rich     |  ⭐⭐ Topics   | ✅ Task routes |
| **Monitoring**        |  ⚠️ Basic   |   ⚠️ Basic    |     ✅ UI      |    ✅ Tools    |   ✅ Flower    |
| **K8s Integration**   | ⭐⭐⭐ Easy |  ⭐⭐⭐ Easy  |   ⭐⭐ Helm    | ⭐⭐ Operators | ⭐⭐⭐ Native  |
| **Memory Usage**      |     Low     |      Low      |     Medium     |      High      |    Depends     |
| **Learning Curve**    |    Easy     |    Medium     |     Steep      |   Very Steep   |     Medium     |

### Resource Requirements (Kubernetes)

| Solution          |       Pods       |       RAM (min)        | CPU (min) |    Storage     |
| ----------------- | :--------------: | :--------------------: | :-------: | :------------: |
| Redis (single)    |        1         |         256MB          |   100m    |    1GB PVC     |
| Redis Cluster     |        6+        |         1.5GB          |   600m    |    6GB PVC     |
| RabbitMQ (single) |        1         |         512MB          |   250m    |    2GB PVC     |
| RabbitMQ Cluster  |        3+        |         1.5GB          |   750m    |    6GB PVC     |
| Kafka (minimal)   |        3+        |          3GB+          |   1000m   |   30GB+ PVC    |
| Celery            | Workers + Broker | Broker + ~100MB/worker | Variable  | Broker storage |

### Cost Estimate (Cloud/Production)

| Solution           | Monthly Cost (small) | Monthly Cost (production) |
| ------------------ | :------------------: | :-----------------------: |
| Redis (managed)    |        $15-30        |          $50-200          |
| RabbitMQ (managed) |        $30-50        |         $100-300          |
| Kafka (managed)    |       $150-300       |         $500-2000         |
| Celery             |     Broker cost      |     Broker + workers      |

---

## Weighted Decision Matrix

Scoring criteria specific to TTG project needs (1-5 scale):

| Criteria           | Weight | Redis Lists | Redis Streams | RabbitMQ |  Kafka   | Celery+Redis |
| ------------------ | :----: | :---------: | :-----------: | :------: | :------: | :----------: |
| Simplicity         |  25%   |      5      |       4       |    3     |    1     |      4       |
| Fault Tolerance    |  25%   |      2      |       4       |    5     |    5     |      4       |
| K8s Fit            |  20%   |      5      |       5       |    4     |    3     |      4       |
| Python Ecosystem   |  15%   |      4      |       4       |    4     |    3     |      5       |
| Scalability        |  15%   |      3      |       4       |    4     |    5     |      4       |
| **WEIGHTED TOTAL** |  100%  |  **3.65**   |   **4.15**    | **3.95** | **3.15** |   **4.15**   |

### Ranking

1. 🥇 **Redis Streams** (4.15) - Best balance of simplicity and reliability
2. 🥇 **Celery+Redis** (4.15) - Best for Python with rich task features (tie)
3. 🥉 **RabbitMQ** (3.95) - Solid choice if complex routing needed later
4. 4th: **Redis Lists** (3.65) - Too simple, lacks fault tolerance
5. 5th: **Kafka** (3.15) - Overkill, expensive, complex

---

## Recommendation

### Primary Choice: Redis Streams

**Why Redis Streams wins for TTG:**

1. **Right-sized complexity**: More reliable than Redis Lists, simpler than RabbitMQ/Kafka
2. **Kubernetes native**: Easy to deploy, single pod for development
3. **Fault tolerance**: XACK pattern ensures no lost work
4. **Visibility**: XPENDING shows exactly what's stuck
5. **Existing knowledge**: If you know Redis, Streams is incremental learning
6. **Cost-effective**: Minimal resources, free in kind cluster

### Secondary Choice: Celery+Redis (Phase 2b)

If we need advanced features:

- Automatic retry with exponential backoff
- Rate limiting
- Task chains (A → B → C)
- Beautiful monitoring (Flower)

Celery can be added on top of Redis Streams architecture.

### When to Consider RabbitMQ

- Need complex routing (messages to different queues based on content)
- Regulatory requirement for AMQP protocol
- Team already has RabbitMQ expertise

### When to Consider Kafka

- Processing millions of events per second
- Need event sourcing / audit log pattern
- Multi-datacenter replication required
- Budget allows for infrastructure cost

---

## Chosen Architecture: Redis Streams

### High-Level Design

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                     TTG MILESTONE 2 ARCHITECTURE                            │
│                                                                             │
│  ┌──────────────┐                                                           │
│  │  COORDINATOR │  Creates task chunks, pushes to Redis Stream              │
│  │  (Job/Pod)   │                                                           │
│  └──────┬───────┘                                                           │
│         │ XADD ttg:tasks                                                    │
│         ▼                                                                   │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │                         REDIS (StatefulSet)                           │  │
│  │  ┌─────────────────────────┐  ┌─────────────────────────┐            │  │
│  │  │    Stream: ttg:tasks    │  │   Stream: ttg:results   │            │  │
│  │  │    Consumer Group:      │  │   (completed work)      │            │  │
│  │  │    ttg-workers          │  │                         │            │  │
│  │  └─────────────────────────┘  └─────────────────────────┘            │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│         │ XREADGROUP                      ▲ XADD                            │
│         ▼                                 │                                 │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                      │
│  │   WORKER 0   │  │   WORKER 1   │  │   WORKER 2   │  ... (N workers)    │
│  │              │  │              │  │              │                      │
│  │ 1. XREADGROUP│  │ 1. XREADGROUP│  │ 1. XREADGROUP│                      │
│  │ 2. Process   │  │ 2. Process   │  │ 2. Process   │                      │
│  │ 3. XADD reslt│  │ 3. XADD reslt│  │ 3. XADD reslt│                      │
│  │ 4. XACK      │  │ 4. XACK      │  │ 4. XACK      │                      │
│  └──────────────┘  └──────────────┘  └──────────────┘                      │
│         │                                                                   │
│         └─────────────────────┬─────────────────────────────────────────   │
│                               ▼                                             │
│  ┌──────────────┐                                                           │
│  │  AGGREGATOR  │  Reads results, combines, outputs final result           │
│  │  (Job/Pod)   │                                                           │
│  └──────────────┘                                                           │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Component Responsibilities

| Component       | Type              | Responsibility                                 |
| --------------- | ----------------- | ---------------------------------------------- |
| **Redis**       | StatefulSet       | Task queue, result storage, state persistence  |
| **Coordinator** | K8s Job           | Split work into chunks, populate task stream   |
| **Worker**      | K8s Job (indexed) | Pull tasks, process, push results, acknowledge |
| **Aggregator**  | K8s Job           | Combine partial results into final output      |

### Data Flow

```
1. COORDINATOR: Splits 10M parameters into 1000 chunks (10K each)
                ↓
2. COORDINATOR: XADD ttg:tasks * chunk_id 001 start 0 end 9999
                XADD ttg:tasks * chunk_id 002 start 10000 end 19999
                ... (1000 times)
                ↓
3. WORKERS:     XREADGROUP GROUP ttg-workers CONSUMER worker-0 ...
                (Each worker pulls next available chunk)
                ↓
4. WORKERS:     Process chunk, compute results
                ↓
5. WORKERS:     XADD ttg:results * chunk_id 001 status complete ...
                XACK ttg:tasks ttg-workers <message-id>
                ↓
6. AGGREGATOR:  XREAD STREAMS ttg:results 0
                Combine all partial results
                ↓
7. OUTPUT:      Final aggregated result (file/database/stdout)
```

### Message Schemas

**Task Message (ttg:tasks stream):**

```json
{
  "chunk_id": "00001",
  "start_param": 0,
  "end_param": 9999,
  "total_in_chunk": 10000,
  "created_at": "2026-01-30T10:00:00Z",
  "priority": 1
}
```

**Result Message (ttg:results stream):**

```json
{
  "chunk_id": "00001",
  "worker_id": "worker-0",
  "status": "complete",
  "params_processed": 10000,
  "duration_seconds": 12.5,
  "result_summary": { "sum": 12345678, "count": 10000 },
  "completed_at": "2026-01-30T10:00:12Z"
}
```

---

## Implementation Plan

### 🗓️ Day-by-Day Schedule (2 Weeks)

---

#### **DAY 1: Redis Setup & Learning** (4-6 hours)

**Morning - Infrastructure:**

- [ ] Deploy minimal Redis pod to kind cluster
- [ ] Create Redis Service for internal DNS
- [ ] Verify connectivity: `kubectl exec -it <pod> -- redis-cli ping`

**Afternoon - Learning:**

- [ ] Practice Redis Streams commands hands-on:
  ```bash
  XADD ttg:tasks * chunk_id 001 start 0 end 999
  XGROUP CREATE ttg:tasks ttg-workers 0 MKSTREAM
  XREADGROUP GROUP ttg-workers CONSUMER w0 BLOCK 5000 STREAMS ttg:tasks >
  XACK ttg:tasks ttg-workers <msg-id>
  XPENDING ttg:tasks ttg-workers
  ```
- [ ] Document commands in personal notes

**Deliverables:**

- `k8s/manifests/redis.yaml` (Pod + Service)
- Redis running and accessible in kind

---

#### **DAY 2: Queue Utilities Module** (6 hours)

**Morning - Core Functions:**

- [ ] Create `src/queue_utils.py`:
  ```python
  def connect_redis() -> redis.Redis
  def ensure_stream_exists(r, stream, group) -> bool
  def add_tasks(r, stream, chunks: List[dict]) -> int
  ```

**Afternoon - Worker Functions:**

- [ ] Continue `src/queue_utils.py`:
  ```python
  def get_next_task(r, stream, group, consumer, timeout=5000) -> dict
  def ack_task(r, stream, group, msg_id) -> bool
  def get_pending_count(r, stream, group) -> int
  def publish_result(r, result_stream, result: dict) -> str
  ```
- [ ] Write quick test script to verify functions

**Deliverables:**

- `src/queue_utils.py` with all functions
- Manual test showing add → get → ack works

---

#### **DAY 3: Worker Integration** (6-8 hours)

**Morning - Feature Toggle:**

- [ ] Add `USE_QUEUE` environment variable
- [ ] Create `QueueWorker` class in `worker.py`:

  ```python
  class QueueWorker:
      def __init__(self):
          self.redis = connect_redis()
          self.consumer_name = f"worker-{os.getenv('WORKER_ID')}"

      def run(self):
          # If worker 0 and stream empty, initialize tasks
          # Loop: get_next_task → process → ack → repeat
  ```

**Afternoon - Task Initialization:**

- [ ] Worker 0 checks if stream is empty
- [ ] If empty, Worker 0 creates all task chunks
- [ ] Other workers wait briefly, then start pulling

**Deliverables:**

- `worker.py` updated with `USE_QUEUE` mode
- Feature toggle working: `USE_QUEUE=true` vs `USE_QUEUE=false`

---

#### **DAY 4: Local Testing** (6 hours)

**Morning - Docker Compose:**

- [ ] Create `docker-compose.yml`:
  ```yaml
  services:
    redis:
      image: redis:7-alpine
      ports: ["6379:6379"]
    worker:
      build: .
      environment:
        - USE_QUEUE=true
        - REDIS_HOST=redis
        - WORKER_ID=0
        - TOTAL_WORKERS=3
        - TOTAL_PARAMETERS=1000
      depends_on: [redis]
  ```
- [ ] Test single worker: `docker-compose up`

**Afternoon - Multi-Worker Test:**

- [ ] Scale workers: `docker-compose up --scale worker=3`
- [ ] Verify all tasks processed
- [ ] Verify no duplicates (check result count)

**Deliverables:**

- `docker-compose.yml` for local testing
- Successful 3-worker test with 1000 params

---

#### **DAY 5: Kind Cluster Deployment** (6 hours)

**Morning - K8s Manifests:**

- [ ] Update `k8s/manifests/parallel-jobs.yaml` → `parallel-jobs-queue.yaml`:
  ```yaml
  env:
    - name: USE_QUEUE
      value: "true"
    - name: REDIS_HOST
      value: "redis.default.svc.cluster.local"
  ```
- [ ] Rebuild Docker image with queue_utils
- [ ] Load image into kind

**Afternoon - End-to-End Test:**

- [ ] Deploy Redis
- [ ] Deploy workers (3 replicas)
- [ ] Run 10K parameter test
- [ ] Verify completion: `kubectl logs`, `redis-cli XLEN`

**Deliverables:**

- `k8s/manifests/parallel-jobs-queue.yaml`
- Successful 10K param test in kind

---

#### **DAY 6: Fault Tolerance Testing** (4-6 hours)

**Morning - Kill Tests:**

- [ ] Start job with 10K params
- [ ] Mid-run: `kubectl delete pod <worker-pod>`
- [ ] Verify: Task returns to pending (XPENDING)
- [ ] Verify: Another worker picks it up
- [ ] Verify: Job completes successfully

**Afternoon - Edge Cases:**

- [ ] Test: Redis connection lost mid-task
- [ ] Test: Worker timeout scenarios
- [ ] Document all test results

**Deliverables:**

- Fault tolerance verified and documented
- Known limitations documented

---

#### **DAY 7: Scale Testing** (4-6 hours)

**Morning - 100K Test:**

- [ ] Configure 100,000 parameters
- [ ] Run with 3 workers
- [ ] Measure total time, throughput
- [ ] Compare with Milestone 1 static approach

**Afternoon - Analysis:**

- [ ] Identify any bottlenecks
- [ ] Tune chunk size if needed
- [ ] Document performance results

**Deliverables:**

- Performance comparison table
- Recommended settings for production

---

#### **DAY 8: Documentation Update** (4-6 hours)

**Morning - Technical Docs:**

- [ ] Update this document with actual results
- [ ] Create operational runbook:
  - How to deploy
  - How to monitor (XLEN, XPENDING)
  - How to troubleshoot

**Afternoon - User Docs:**

- [ ] Update README.md with queue mode
- [ ] Update SUPERVISOR_REPORT.md
- [ ] Add troubleshooting FAQ

**Deliverables:**

- All documentation updated
- Runbook for operations

---

#### **DAY 9: Code Cleanup** (4-6 hours)

**Morning - Code Quality:**

- [ ] Self code review
- [ ] Add docstrings to all functions
- [ ] Handle edge cases discovered in testing
- [ ] Remove debug code

**Afternoon - Final Testing:**

- [ ] Full regression test (both modes)
- [ ] Verify feature toggle works
- [ ] Clean up temporary files

**Deliverables:**

- Production-quality code
- All tests passing

---

#### **DAY 10: Buffer & Demo** (4 hours)

- [ ] Buffer for any overrun
- [ ] Prepare demo for supervisor
- [ ] Final review
- [ ] Celebrate! 🎉

---

## Success Criteria (MVP)

| #   | Criterion                      | Verification                    | Priority |
| --- | ------------------------------ | ------------------------------- | -------- |
| 1   | Redis deployed in kind         | `kubectl get pods -l app=redis` | **P0**   |
| 2   | Workers pull tasks dynamically | Logs show XREADGROUP            | **P0**   |
| 3   | Fault tolerance works          | Kill pod → task reprocessed     | **P0**   |
| 4   | 10K params completes           | Job finishes successfully       | **P0**   |
| 5   | Feature toggle works           | Both modes operational          | **P1**   |
| 6   | 100K params successful         | Scale test passes               | **P1**   |
| 7   | Documentation updated          | Runbook exists                  | **P1**   |
| 8   | No duplicate processing        | Each param exactly once         | **P1**   |

---

## Deferred to Future Phase

| Feature              | Why Deferred         | Estimated Effort |
| -------------------- | -------------------- | ---------------- |
| Celery integration   | Not needed for MVP   | 2 weeks          |
| Flower monitoring    | Can use redis-cli    | 1 day            |
| Persistent Redis     | In-memory OK for MVP | 0.5 day          |
| Separate Coordinator | Worker 0 handles it  | N/A              |
| Separate Aggregator  | Query Redis manually | N/A              |
| Dead letter queue    | Log failures instead | 1 day            |
| Azure AKS deploy     | Stick with kind      | 1 week           |

---

## Risk Assessment

| Risk                         | Probability | Impact | Mitigation                      |
| ---------------------------- | :---------: | :----: | ------------------------------- |
| Redis Streams learning curve |   Medium    | Medium | Day 1 dedicated to learning     |
| Integration bugs             |   Medium    | Medium | Feature toggle allows fallback  |
| Time overrun on specific day |    High     |  Low   | Days 9-10 are buffer            |
| Redis pod crashes            |     Low     | Medium | Restart policy, rerun if needed |
| Scope creep                  |   Medium    |  High  | Explicit "deferred" list above  |

---

## Timeline Summary

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    2-WEEK SPRINT: VISUAL TIMELINE                           │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   Mon      Tue      Wed      Thu      Fri      Mon      Tue      Wed-Fri   │
│   Day1     Day2     Day3     Day4     Day5     Day6     Day7     Day8-10   │
│                                                                             │
│  ┌─────┐  ┌─────┐  ┌─────┐  ┌─────┐  ┌─────┐  ┌─────┐  ┌─────┐  ┌───────┐ │
│  │Redis│  │Queue│  │Work-│  │Local│  │Kind │  │Fault│  │Scale│  │Docs + │ │
│  │Setup│  │Utils│  │ er  │  │Test │  │E2E  │  │Test │  │Test │  │Buffer │ │
│  │Learn│  │ .py │  │Integ│  │Dock-│  │10K  │  │Kill │  │100K │  │Demo   │ │
│  │     │  │     │  │     │  │Comp │  │     │  │Pod  │  │     │  │       │ │
│  └──┬──┘  └──┬──┘  └──┬──┘  └──┬──┘  └──┬──┘  └──┬──┘  └──┬──┘  └───┬───┘ │
│     │        │        │        │        │        │        │          │     │
│     ▼        ▼        ▼        ▼        ▼        ▼        ▼          ▼     │
│  Redis    queue_   worker   docker-  parallel  Fault   Perf     Complete  │
│  .yaml    utils    .py      compose  -jobs-    Proof   Data     MVP! 🎉   │
│           .py      updated  .yml     queue.yaml                            │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Next Steps

1. ✅ **Plan reviewed** - Compressed to 2 weeks
2. ⏳ **Start Day 1** - Deploy Redis to kind
3. 📅 **Daily progress** - Check off tasks each day
4. 🎯 **Day 10** - Demo to supervisor

---

## Deliverables Checklist

By end of 2 weeks, these files should exist:

```
TTG/
├── src/
│   ├── queue_utils.py          # NEW: Redis Streams wrapper
│   └── worker.py               # UPDATED: USE_QUEUE mode
├── k8s/manifests/
│   ├── redis.yaml              # NEW: Redis Pod + Service
│   └── parallel-jobs-queue.yaml # NEW: Queue-mode job
├── docker-compose.yml          # NEW: Local testing
└── docs/
    └── MILESTONE_2_*.md        # UPDATED: Results filled in
```

---

## References

- [Redis Streams Documentation](https://redis.io/docs/data-types/streams/)
- [Celery Documentation](https://docs.celeryq.dev/)
- [RabbitMQ Tutorials](https://www.rabbitmq.com/getstarted.html)
- [Apache Kafka Documentation](https://kafka.apache.org/documentation/)
- [Kubernetes Jobs](https://kubernetes.io/docs/concepts/workloads/controllers/job/)

---

## Appendix A: Redis Streams Quick Reference

### Essential Commands

```bash
# Create/add to stream
XADD ttg:tasks * chunk_id 001 start 0 end 9999

# Create consumer group
XGROUP CREATE ttg:tasks ttg-workers 0 MKSTREAM

# Read as consumer (blocking)
XREADGROUP GROUP ttg-workers CONSUMER worker-0 BLOCK 5000 STREAMS ttg:tasks >

# Acknowledge processed message
XACK ttg:tasks ttg-workers 1234567890-0

# Check pending (unacknowledged) messages
XPENDING ttg:tasks ttg-workers

# Stream length
XLEN ttg:tasks

# Trim stream (keep last N entries)
XTRIM ttg:tasks MAXLEN ~ 10000
```

---

## Appendix B: Glossary

| Term                  | Definition                                                     |
| --------------------- | -------------------------------------------------------------- |
| **Consumer Group**    | A set of consumers that cooperatively consume from a stream    |
| **XACK**              | Acknowledge a message as processed (won't be redelivered)      |
| **Pending**           | Messages delivered but not yet acknowledged                    |
| **Dead Letter Queue** | Queue for messages that failed processing multiple times       |
| **At-Least-Once**     | Delivery guarantee: message delivered ≥1 time                  |
| **Idempotent**        | Operation that produces same result if executed multiple times |
| **Chunk**             | A batch of parameters grouped for processing                   |

---

**Document Version:** 2.0 (Compressed Timeline)  
**Created:** January 30, 2026  
**Updated:** January 30, 2026  
**Timeline:** 2 weeks (10 working days)  
**Author:** TTG Team
