# Supervisor Report - Milestone 3 (RabbitMQ Phased Migration)

**Date:** February 9, 2026  
**Owner:** Xavier / TTG Team  
**Environment:** Local Kind cluster only  
**Overall Status:** 🟢 On Track

---

## Executive Summary

Milestone 3 introduces a phased RabbitMQ migration for TTG queue processing.  
The system now supports `QUEUE_BACKEND=redis|rabbitmq`, allowing safe adoption of RabbitMQ while preserving the proven Redis fallback.

The implementation adds:
- Broker-native retry and dead-letter queue behavior (RabbitMQ path)
- Visual monitoring for demos (RabbitMQ Management UI + CLI snapshots)
- Updated operator guide and report artifacts for supervisor review

---

## Why RabbitMQ (Business + Technical Rationale)

- Standard message-broker pattern for task queues with clearer operational semantics.
- Built-in messaging workflows for retry and dead-letter handling.
- Better visual operations view via RabbitMQ management UI.
- Keeps architecture explainable for reviews and stakeholder demos.

Why phased migration:
- Reduces delivery risk by preserving Redis path during transition.
- Allows side-by-side validation before any full cutover decision.

---

## Delivered Scope

| Deliverable | File | Status |
| --- | --- | --- |
| RabbitMQ backend implementation | `src/rabbitmq_queue.py` | ✅ |
| Queue backend toggle in worker | `src/worker.py` | ✅ |
| Updated runtime env defaults | `docker/Dockerfile` | ✅ |
| RabbitMQ dependency | `requirements.txt` | ✅ |
| RabbitMQ broker manifest | `k8s/manifests/rabbitmq.yaml` | ✅ |
| RabbitMQ worker manifest | `k8s/manifests/parallel-jobs-queue-rabbitmq.yaml` | ✅ |
| CLI monitoring helper | `scripts/rabbitmq_monitor.sh` | ✅ |
| Queue operations guide update | `docs/guides/QUEUE_MODE_GUIDE.md` | ✅ |
| M3 results report | `docs/results/TEST_RESULTS_M3_RABBITMQ_MONITORING.md` | ✅ |

---

## Monitoring Points for Demo

### Visual (RabbitMQ UI)

- Queue depth trend for `ttg.tasks` from high to low.
- Active consumers count during processing.
- Unacked message trend during processing windows.
- Publish/Deliver/Ack rates.
- Retry/DLQ queue behavior in failure scenarios.

### CLI (Repeatable Evidence)

- `./scripts/rabbitmq_monitor.sh --watch 2`
- `kubectl get pods -l ttg.io/queue-backend=rabbitmq`
- `kubectl logs -l ttg.io/queue-backend=rabbitmq -f`

---

## Validation Plan for Final Acceptance

1. Run RabbitMQ backend workers in Kind with 10K parameters.
2. Capture monitoring checkpoints at start, mid-run, and completion.
3. Run controlled failure scenario and confirm retry/DLQ behavior.
4. Confirm Redis fallback is still deployable.
5. Finalize metrics in results report and export DOCX summary.

---

## Risks and Mitigations

| Risk | Mitigation |
| --- | --- |
| Migration instability | Keep Redis fallback active during M3 |
| Broker semantic differences | Explicit retry + DLQ policy documented and implemented |
| Demo ambiguity | Fixed visual checkpoint list and CLI evidence commands |

---

## Out-of-Scope and Future Work

- AKS deployment is out of current scope.
- Prometheus + Grafana in Kind is documented as future extension for persistent dashboards and alerting.

---

## Supervisor Decision Request

Please confirm whether the project should:
1. Continue phased validation in Kind until RabbitMQ is fully accepted, or
2. Plan a full RabbitMQ cutover milestone after validation evidence is complete.
