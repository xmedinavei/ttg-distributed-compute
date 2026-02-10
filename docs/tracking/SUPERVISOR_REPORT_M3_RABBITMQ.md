# Supervisor Report - Milestone 3: Production Queue (RabbitMQ)

**Report Date:** February 9, 2026  
**Owner:** Xavier / TTG Team  
**Environment:** Kind (local Kubernetes)  
**Status:** ✅ Complete

---

## Executive Summary

Milestone 3 adds **RabbitMQ** as a production-grade queue backend while preserving Redis Streams as a rollback-safe fallback. The worker automatically selects the backend via the `QUEUE_BACKEND` environment variable (`redis` or `rabbitmq`).

All 100 task chunks complete with **zero data loss** on both backends, even when a worker is forcefully killed mid-processing. The system is demonstrated via a single command with live progress, fault injection, and strict TTG-only cleanup.

---

## Deliverables

| # | Deliverable | Status |
|---|---|---|
| 1 | RabbitMQ backend code (`src/rabbitmq_queue.py`) | ✅ Complete |
| 2 | Dual-backend worker toggle (`QUEUE_BACKEND=redis\|rabbitmq`) | ✅ Complete |
| 3 | RabbitMQ Kubernetes manifests (Pod + PVC + Service) | ✅ Complete |
| 4 | Retry queue with configurable TTL + Dead Letter Queue | ✅ Complete |
| 5 | Unified one-command demo script (`run-demo.sh`) | ✅ Complete |
| 6 | RabbitMQ Management UI monitoring (port 15672) | ✅ Complete |
| 7 | CLI queue monitor (`rabbitmq_monitor.sh`) | ✅ Complete |
| 8 | Configurable fault simulation (`SIMULATE_FAULT_RATE`) | ✅ Complete |
| 9 | Strict TTG-only cleanup for shared machines | ✅ Complete |
| 10 | Comprehensive documentation and test results | ✅ Complete |

---

## Test Results

### Backend Comparison (Same Hardware, Same Config)

| Metric | Redis (no fault) | RabbitMQ (no fault) | Redis (fault) | RabbitMQ (fault) |
|---|---|---|---|---|
| Chunks | 100/100 | 100/100 | 100/100 | 100/100 |
| Runtime | 36s | 39s | 48s | 49s |
| Throughput | 27 p/s | 25 p/s | 20 p/s | 20 p/s |
| Recovery | XCLAIM stale tasks | Auto-requeue | XCLAIM | Auto-requeue |
| Data loss | ZERO | ZERO | ZERO | ZERO |

### RabbitMQ Queue Stats (After Completion)

| Queue | Messages | Status |
|---|---|---|
| ttg.tasks | 0 | All consumed |
| ttg.results | 100 | All results collected |
| ttg.tasks.retry | 0 | No retries needed |
| ttg.tasks.dlq | 0 | No dead letters |

---

## Why RabbitMQ

| Aspect | Redis Streams (M2) | RabbitMQ (M3) |
|---|---|---|
| Protocol | Redis RESP | AMQP 0-9-1 |
| Retry logic | Manual (stale check interval) | Retry queue with TTL + DLQ |
| Monitoring | RedisInsight + CLI | Management UI + CLI |
| Fault recovery | XCLAIM (explicit) | Auto-requeue (native) |
| Operational maturity | Simpler | Richer semantics |

---

## Demo Commands

```bash
# RabbitMQ demo with fault injection (RECOMMENDED)
./scripts/run-demo.sh --backend rabbitmq --scale small --fault-demo --monitor both

# Redis demo for comparison
./scripts/run-demo.sh --backend redis --scale small --fault-demo --monitor both

# Safe cleanup (TTG resources only)
./scripts/cleanup-ttg.sh --all --force

# Preview cleanup (dry-run)
./scripts/cleanup-ttg.sh --all --dry-run
```

---

## Risks & Mitigations

| Risk | Mitigation |
|---|---|
| RabbitMQ adds infrastructure complexity | Redis remains as tested fallback |
| Cleanup scripts could affect other Docker workloads | Strict TTG-label selectors; cluster/image deletion disabled |
| At-least-once delivery may cause duplicate processing | Acceptable for parameter computation; idempotent results |

---

## Next Steps

1. Continue phased hardening in Kind, **or**
2. Plan full RabbitMQ cutover milestone
3. Add Prometheus + Grafana monitoring dashboards (optional)
4. Scale testing with 100K+ parameters

---

## DOCX Report

A formatted `.docx` report with the same styling as the M1+M2 report is available at:

**`docs/tracking/TTG_Project_Status_Report_M1_M2_M3.docx`**

To regenerate it:

```bash
python3 scripts/generate_docx_report.py
```

---

_Report Version: 3.0_  
_Next Review: February 17, 2026_
