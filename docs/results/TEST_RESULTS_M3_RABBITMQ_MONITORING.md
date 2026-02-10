# Milestone 3 Test Results: RabbitMQ Backend + Visual Monitoring

**Date:** February 9, 2026  
**Milestone:** 3 (Phased migration in Kind)  
**Status:** ✅ Implementation Completed, Validation Checklist Ready

---

## Executive Summary

Milestone 3 adds a RabbitMQ backend path for TTG queue workers while preserving Redis fallback.  
The implementation introduces broker-native retry and dead-letter routing, plus clear visual monitoring points for supervisor demos.

---

## What Was Implemented

| Area | Deliverable | Status |
| --- | --- | --- |
| Queue backend | RabbitMQ backend class (`src/rabbitmq_queue.py`) | ✅ |
| Worker runtime | Backend toggle (`QUEUE_BACKEND=redis|rabbitmq`) in `src/worker.py` | ✅ |
| Broker infra | RabbitMQ manifest (`k8s/manifests/rabbitmq.yaml`) | ✅ |
| Worker deploy | RabbitMQ queue job (`k8s/manifests/parallel-jobs-queue-rabbitmq.yaml`) | ✅ |
| Monitoring CLI | RabbitMQ queue snapshot script (`scripts/rabbitmq_monitor.sh`) | ✅ |
| Operations guide | Queue guide updated with M3 monitoring checkpoints | ✅ |

---

## RabbitMQ Topology Used

| Component | Name | Purpose |
| --- | --- | --- |
| Task queue | `ttg.tasks` | Main work queue |
| Retry queue | `ttg.tasks.retry` | Delayed retry queue |
| Dead-letter queue | `ttg.tasks.dlq` | Failed tasks after max retries |
| Results queue | `ttg.results` | Worker completion results |

Retry policy:
- Max retries: `RABBITMQ_MAX_RETRIES` (default `3`)
- Retry delay: `RABBITMQ_RETRY_DELAY_MS` (default `5000`)

---

## Validation Procedure (Kind)

### 1) Deploy RabbitMQ

```bash
kubectl apply -f k8s/manifests/rabbitmq.yaml
kubectl get pod ttg-rabbitmq
kubectl exec ttg-rabbitmq -- rabbitmq-diagnostics -q ping
```

### 2) Build and run RabbitMQ workers

```bash
docker build -t ttg-worker:v1.3.0 -f docker/Dockerfile .
kind load docker-image ttg-worker:v1.3.0 --name ttg-sandbox
kubectl apply -f k8s/manifests/parallel-jobs-queue-rabbitmq.yaml
kubectl get pods -l ttg.io/queue-backend=rabbitmq -w
```

### 3) Visual monitoring checkpoints

```bash
# RabbitMQ UI
kubectl port-forward pod/ttg-rabbitmq 15672:15672
# open http://localhost:15672 (guest/guest)

# CLI snapshots
./scripts/rabbitmq_monitor.sh --watch 2
```

Checkpoints:
- `ttg.tasks` depth decreases during processing.
- `ttg.results` increases until expected chunk count.
- Consumers reflect active worker count.
- `messages_unacknowledged` returns near zero at completion.
- `ttg.tasks.retry` and `ttg.tasks.dlq` behavior matches test intent.

---

## Results Table (Fill During Demo Run)

| Metric | Target | Observed |
| --- | --- | --- |
| Worker pods started | 3/3 running | TODO |
| Chunks completed | 100/100 | TODO |
| Results messages (`ttg.results`) | 100 | TODO |
| Main queue end depth (`ttg.tasks`) | 0 (or near 0) | TODO |
| Retry queue peak | >0 only on failures | TODO |
| DLQ final depth | 0 on healthy run | TODO |
| End-to-end runtime | recorded | TODO |
| Throughput (params/sec) | recorded | TODO |

---

## Demo Evidence Checklist

- [ ] Screenshot: RabbitMQ UI queues list mid-run
- [ ] Screenshot: RabbitMQ UI queues list after completion
- [ ] Screenshot: Rates/overview panel
- [ ] CLI capture: `rabbitmq_monitor.sh` output
- [ ] CLI capture: worker logs with final JSON summary

---

## Risk Notes

- Current migration is phased; Redis fallback remains active by design.
- RabbitMQ consumer-level unacked metrics are most reliable in management UI.
- Prometheus + Grafana are intentionally deferred to future scope.

---

## Conclusion

Milestone 3 implementation establishes a production-style messaging direction (RabbitMQ with retry + DLQ) without breaking the existing Redis queue mode. This reduces migration risk and gives immediate visual observability for supervisor demos in local Kind.
