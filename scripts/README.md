# TTG Scripts Directory Guide

This directory is intentionally organized by operational purpose.

## Why `aggregate_results.py` and `queue_monitor.py` are in `scripts/`

Both files are **operator tools** (not application runtime code):
- `aggregate_results.py`: post-run analytics/report helper
- `queue_monitor.py`: live Redis queue observability helper

They belong in `scripts/` because they are executed on demand by users/operators, while reusable queue logic remains in `src/`.

## Script Categories

- **Demo/Run**
  - `run-demo.sh` (single live demo entrypoint; Redis or RabbitMQ backend)
  - `run-local.sh`
  - `fault-tolerance-demo.sh`
- **Monitoring**
  - `queue_monitor.py` (Redis)
  - `rabbitmq_monitor.sh` (RabbitMQ)
  - `aggregate_results.py` (results rollup)
- **Build/Deploy**
  - `build.sh`
  - `deploy.sh`
- **Safety/Cleanup**
  - `cleanup-ttg.sh` (strict TTG-only cleanup)
  - `cleanup-all.sh`
  - `list-resources.sh`
  - `recover-infra.sh`

## Safety Rules

- `cleanup-ttg.sh` should be used for demos because it only touches TTG Kubernetes resources.
- No Docker prune/image/container deletion should be required for normal demo runs.
