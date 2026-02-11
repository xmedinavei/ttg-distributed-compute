# TTG Demo Guide -- Quick Reference

**For:** Running demos and inspecting results
**Last Updated:** February 10, 2026

---

## 1. Run the Demo

### RabbitMQ (Recommended)

```bash
cd /home/xavierand_/Desktop/TTG

# Fault tolerance demo (kill a worker, prove 100% completion)
./scripts/run-demo.sh --backend rabbitmq --scale small --fault-demo --skip-cleanup

# Medium-scale throughput test (no fault injection)
./scripts/run-demo.sh --backend rabbitmq --scale medium --skip-cleanup
```

### Redis

```bash
# Fault tolerance demo
./scripts/run-demo.sh --backend redis --scale small --fault-demo --skip-cleanup

# Medium-scale throughput test
./scripts/run-demo.sh --backend redis --scale medium --skip-cleanup
```

> **IMPORTANT:** Always use `--skip-cleanup` if you want to inspect results after the demo. Without it, the cleanup step purges all queues and results are lost.

### Options Reference

| Option | Values | Default | Description |
|--------|--------|---------|-------------|
| `--backend` | `redis`, `rabbitmq` | `redis` | Queue backend |
| `--scale` | `small`, `medium` | `small` | `small`=1K params, `medium`=10K params |
| `--workers` | Any integer | `3` | Number of worker pods |
| `--fault-demo` | Flag | Off | Kill one worker at ~30% progress |
| `--monitor` | `cli`, `web`, `both`, `none` | `none` | Open monitoring tools |
| `--skip-cleanup` | Flag | Off | Keep results after demo |

---

## 2. See Results During the Demo

The demo script shows a live progress bar:

```
  [████████████░░░░░░░░] 60/100 chunks (60%) | 25 params/sec | 24s
```

And a summary at the end:

```
  Backend: rabbitmq
  Total params: 1000
  Chunks: 100/100
  Time: 39s
  Throughput: 25 params/sec
  Workers running: 0, completed: 3
```

### Real-Time Monitoring (Optional)

Open a **second terminal** while the demo runs:

```bash
# RabbitMQ: CLI queue snapshot (refreshes every 2 seconds)
./scripts/rabbitmq_monitor.sh --watch 2

# Redis: CLI dashboard (real-time)
kubectl port-forward pod/ttg-redis 6379:6379 &
python3 scripts/queue_monitor.py
```

### Web UI Monitoring (Optional)

```bash
# RabbitMQ Management UI
kubectl port-forward pod/ttg-rabbitmq 15672:15672 &
# Open: http://localhost:15672 (user: guest, pass: guest)
# Look at: ttg.tasks (should go to 0), ttg.results (should reach 100)

# RedisInsight
kubectl apply -f k8s/manifests/redis-insight.yaml
kubectl port-forward pod/redis-insight 8001:8001 &
# Open: http://localhost:8001
```

---

## 3. See Detailed Results After the Demo

### Redis Backend -- Detailed Aggregation

After the demo (with `--skip-cleanup`), use the aggregation script:

```bash
# Start port-forward to Redis
kubectl port-forward pod/ttg-redis 6379:6379 &

# Run the aggregation report
python3 scripts/aggregate_results.py

# Verbose mode (per-chunk breakdown)
python3 scripts/aggregate_results.py --verbose

# JSON output (for piping to other tools)
python3 scripts/aggregate_results.py --json
```

**What you'll see:**

```
╔══════════════════════════════════════════════════════════════════════╗
║          TTG Queue Mode - Results Aggregation Report                ║
╠══════════════════════════════════════════════════════════════════════╣
║ COMPUTATION SUMMARY                                                 ║
╠──────────────────────────────────────────────────────────────────────╣
║  Total Parameters Processed:          1,000                         ║
║  Total Chunks Processed:                100                         ║
║  Grand Sum:                      50,035.00                          ║
║ TIMING METRICS                                                      ║
╠──────────────────────────────────────────────────────────────────────╣
║  Wall Clock Time:                    36.00 seconds                  ║
║ THROUGHPUT ANALYSIS                                                 ║
╠──────────────────────────────────────────────────────────────────────╣
║  Effective Throughput:               27.78 params/sec               ║
║  Parallelism Factor:                  2.53x speedup                 ║
║ WORKER DISTRIBUTION                                                 ║
╠──────────────────────────────────────────────────────────────────────╣
║  worker-0:  38 chunks (38.0%) ████████░░░░░░░░░░░░                 ║
║  worker-1:  29 chunks (29.0%) ██████░░░░░░░░░░░░░░                 ║
║  worker-2:  33 chunks (33.0%) ███████░░░░░░░░░░░░░                 ║
╚══════════════════════════════════════════════════════════════════════╝
```

### Redis -- Manual Quick Checks

```bash
# How many results?
kubectl exec ttg-redis -- redis-cli XLEN ttg:results

# How many tasks left? (should be 0)
kubectl exec ttg-redis -- redis-cli XLEN ttg:tasks

# See pending (unacknowledged) tasks (should be 0)
kubectl exec ttg-redis -- redis-cli XPENDING ttg:tasks ttg-workers

# Read first 5 results raw
kubectl exec ttg-redis -- redis-cli XRANGE ttg:results - + COUNT 5
```

### RabbitMQ Backend -- Checking Results

```bash
# Queue summary (messages in each queue)
kubectl exec ttg-rabbitmq -- rabbitmqctl list_queues name messages consumers

# Expected output after successful demo:
#   ttg.tasks          0    0     <-- all consumed
#   ttg.results      100    0     <-- all results collected
#   ttg.tasks.retry    0    0     <-- no retries needed
#   ttg.tasks.dlq      0    0     <-- no dead letters
```

### RabbitMQ -- Web UI for Detailed View

```bash
# Port-forward if not already running
kubectl port-forward pod/ttg-rabbitmq 15672:15672 &
```

Then open http://localhost:15672 (guest/guest) and navigate to:

1. **Queues tab** -- see message counts for all `ttg.*` queues
2. Click on **`ttg.results`** -- see the 100 messages
3. Click **"Get messages"** -- inspect individual result payloads
4. Check **`ttg.tasks.dlq`** -- should be 0 (no failures)

### Worker Logs

```bash
# All worker logs (most detailed view of what happened)
kubectl logs -l ttg.io/project=distributed-compute --all-containers

# Specific worker
kubectl logs ttg-worker-rabbitmq-<run-id>-0

# Look for completion summary in logs
kubectl logs -l ttg.io/project=distributed-compute --all-containers | grep "COMPLETED"
```

---

## 4. Cleanup After Inspecting Results

Once you're done inspecting, clean up:

```bash
# Preview what will be deleted
./scripts/cleanup-ttg.sh --all --dry-run

# Clean everything
./scripts/cleanup-ttg.sh --all --force
```

---

## 5. Common Demo Scenarios

### Scenario A: Quick Fault Tolerance Proof

```bash
# Run, see fault tolerance, inspect results
./scripts/run-demo.sh --backend rabbitmq --scale small --fault-demo --skip-cleanup

# Check: all 100 chunks completed despite killing a worker
kubectl exec ttg-rabbitmq -- rabbitmqctl list_queues name messages
# ttg.results should show 100

# Cleanup
./scripts/cleanup-ttg.sh --all --force
```

### Scenario B: Backend Comparison

```bash
# Run RabbitMQ first
./scripts/run-demo.sh --backend rabbitmq --scale medium --skip-cleanup
# Note the throughput from the summary

# Cleanup RabbitMQ run
./scripts/cleanup-ttg.sh --pods --rabbitmq --force

# Run Redis
./scripts/run-demo.sh --backend redis --scale medium --skip-cleanup
# Compare throughput

# Detailed Redis results
kubectl port-forward pod/ttg-redis 6379:6379 &
python3 scripts/aggregate_results.py

# Cleanup
./scripts/cleanup-ttg.sh --all --force
```

### Scenario C: Recovery After Reboot

```bash
# If your machine rebooted, run this first
./scripts/recover-infra.sh

# Then run demo as normal
./scripts/run-demo.sh --backend rabbitmq --scale small --fault-demo --skip-cleanup
```

---

## 6. First-Time Setup

If scripts fail with "Permission denied", make them executable:

```bash
chmod +x scripts/*.sh scripts/*.py k8s/local/*.sh k8s/azure/*.sh
```

---

## 7. Troubleshooting

| Problem | Solution |
|---------|----------|
| "Permission denied" on scripts | Run `chmod +x scripts/*.sh scripts/*.py` |
| "Kind cluster not accessible" | Run `./scripts/recover-infra.sh` |
| "Image not found" | Run `./scripts/build.sh --version 1.3.0 --load-kind` |
| Demo hangs at 0% | Check Redis/RabbitMQ pod: `kubectl get pods` |
| Results show 0 after demo | Did you use `--skip-cleanup`? Results are purged during cleanup |
| `aggregate_results.py` can't connect | Start port-forward: `kubectl port-forward pod/ttg-redis 6379:6379 &` |
| Port-forward refused | Kill old port-forwards: `pkill -f "port-forward"` then retry |

---

_For the full operational runbook, see [deliverables/D2_Operational_Runbook.md](../../deliverables/D2_Operational_Runbook.md)_
