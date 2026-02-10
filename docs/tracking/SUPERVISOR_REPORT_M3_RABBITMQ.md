# Supervisor Report - Milestone 3 RabbitMQ (Phased)

**Date:** February 9, 2026  
**Owner:** Xavier / TTG Team  
**Environment:** Kind (local only)

## Executive Summary

Milestone 3 adds RabbitMQ as a queue backend while keeping Redis as a rollback-safe fallback.  
The demo workflow is now one command (`run-demo.sh`) with backend selection and strict TTG-only cleanup.

## Delivered

- RabbitMQ backend code (`src/rabbitmq_queue.py`)
- Backend toggle in worker (`QUEUE_BACKEND=redis|rabbitmq`)
- RabbitMQ manifests for Kind
- Unified demo script for Redis/RabbitMQ
- RabbitMQ CLI monitor + documented visual checkpoints
- Strict TTG-only cleanup rules for shared developer machines

## Why This Matters

- Improves queue operational semantics (retry + DLQ path).
- Provides visual proof points for stakeholder demos.
- Reduces risk by preserving existing Redis mode.
- Prevents accidental cleanup impact on unrelated Docker workloads.

## Demo Commands

```bash
./scripts/run-demo.sh --backend rabbitmq --scale small --fault-demo --monitor both
./scripts/cleanup-ttg.sh --all --dry-run
./scripts/cleanup-ttg.sh --all
```

## Next Decision

After demo validation, choose:
1. Continue phased hardening in Kind, or
2. Plan full RabbitMQ cutover milestone.
