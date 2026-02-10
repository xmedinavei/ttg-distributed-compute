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

## Fill During Live Demo

| Metric | Target | Observed |
| --- | --- | --- |
| Workers started | 3/3 | TODO |
| Completed chunks | 100/100 | TODO |
| Runtime (seconds) | record | TODO |
| Throughput (params/sec) | record | TODO |
| Retry queue behavior | expected on injected failure | TODO |
| DLQ final state | expected for exhausted retries only | TODO |
