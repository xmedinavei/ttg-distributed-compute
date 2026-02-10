# Milestone 3 Test Results: RabbitMQ Backend + Visual Monitoring

**Date:** February 9, 2026  
**Milestone:** 3 (Phased migration in Kind)  
**Status:** ✅ Implementation Complete, Demo Validation Ready

## Scope

- Added RabbitMQ backend path for queue workers.
- Preserved Redis backend as fallback.
- Added visual monitoring points for supervisor demos (UI + CLI).
- Added strict TTG-only cleanup behavior for shared machines.

## Validation Commands

```bash
# Redis demo
./scripts/run-demo.sh --backend redis --scale small --fault-demo --monitor both

# RabbitMQ demo
./scripts/run-demo.sh --backend rabbitmq --scale small --fault-demo --monitor both
```

## RabbitMQ Monitoring Checkpoints

- `ttg.tasks` goes down during processing.
- `ttg.results` goes up until completion.
- Active consumers align with running workers.
- `ttg.tasks.retry` / `ttg.tasks.dlq` reflect retry/failure behavior.

## Safety Validation

- `./scripts/cleanup-ttg.sh --all` only touches TTG-labeled Kubernetes resources.
- No Docker prune or global container/image deletion is required.
- Existing non-TTG Docker workloads remain untouched.

## Live Demo Results (February 9, 2026)

### Run 1: No Fault Injection

| Metric | Target | Observed |
| --- | --- | --- |
| Workers started | 3/3 | 3/3 |
| Completed chunks | 100/100 | **100/100** |
| Runtime (seconds) | record | **39s** |
| Throughput (params/sec) | record | **25 params/sec** |
| Retry queue (ttg.tasks.retry) | 0 | 0 |
| DLQ (ttg.tasks.dlq) | 0 | 0 |
| Results queue (ttg.results) | 100 | **100** |

### Run 2: With Fault Injection (Worker Killed at ~36%)

| Metric | Target | Observed |
| --- | --- | --- |
| Workers started | 3/3 | 3/3 |
| Worker killed | 1 at ~30% | **1 at ~36%** |
| Completed chunks | 100/100 | **100/100** |
| Runtime (seconds) | record | **49s** |
| Throughput (params/sec) | record | **20 params/sec** |
| Retry queue (ttg.tasks.retry) | 0 | 0 |
| DLQ (ttg.tasks.dlq) | 0 | 0 |
| Results queue (ttg.results) | 100 | **100** |
| Data loss | ZERO | **ZERO** |

### Queue Stats After Completion

```
name               messages  consumers  messages_ready  messages_unacknowledged
ttg.tasks.retry    0         0          0               0
ttg.tasks.dlq      0         0          0               0
ttg.tasks          0         0          0               0
ttg.results        100       0          100             0
```

## Redis Backend Comparison (Same Hardware, Same Config)

### Run 3: Redis, No Fault Injection

| Metric | Result |
| --- | --- |
| Workers started | 3/3 |
| Completed chunks | **100/100** |
| Runtime (seconds) | **36s** |
| Throughput (params/sec) | **27 params/sec** |

### Run 4: Redis, With Fault Injection (Worker Killed at ~33%)

| Metric | Result |
| --- | --- |
| Workers started | 3/3 |
| Worker killed | 1 at ~33% |
| Completed chunks | **100/100** |
| Runtime (seconds) | **48s** |
| Throughput (params/sec) | **20 params/sec** |
| Data loss | **ZERO** (stale task recovery via XCLAIM) |

## Backend Comparison Summary

| Metric | Redis (no fault) | RabbitMQ (no fault) | Redis (fault) | RabbitMQ (fault) |
| --- | --- | --- | --- | --- |
| Chunks | 100/100 | 100/100 | 100/100 | 100/100 |
| Runtime | 36s | 39s | 48s | 49s |
| Throughput | 27 p/s | 25 p/s | 20 p/s | 20 p/s |
| Recovery method | XCLAIM stale tasks | Auto-requeue on disconnect | XCLAIM | Auto-requeue |
| DLQ | N/A | 0 | N/A | 0 |
| Data loss | ZERO | ZERO | ZERO | ZERO |

### Key Observations

- Both backends achieve 100% completion with zero data loss, even under fault conditions.
- Redis is slightly faster (~7-8%) due to lower protocol overhead (in-process vs AMQP).
- RabbitMQ provides richer operational semantics (retry queues, DLQ, management UI).
- Both recover from worker crashes automatically -- no manual intervention needed.
- Throughput drop under fault is consistent (~25%) for both backends (expected: 2 vs 3 workers).
