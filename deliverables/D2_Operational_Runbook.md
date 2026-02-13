# Deliverable 2 -- Operational Runbook

**Project:** TTG Distributed Computation System
**Date:** February 10, 2026
**Version:** 1.3.0
**Author:** Xavier / TTG Team

---

## Table of Contents

1. [Prerequisites](#1-prerequisites)
2. [Initial Setup (From Scratch)](#2-initial-setup-from-scratch)
3. [Build & Deploy Workflow](#3-build--deploy-workflow)
4. [Running Demos](#4-running-demos)
5. [Monitoring Procedures](#5-monitoring-procedures)
6. [Recovery Procedures](#6-recovery-procedures)
7. [Cleanup Procedures](#7-cleanup-procedures)
8. [Troubleshooting Guide](#8-troubleshooting-guide)
9. [Configuration Reference](#9-configuration-reference)

---

## 1. Prerequisites

### Required Software

| Software | Version | Installation |
|----------|---------|-------------|
| Docker | 20.10+ | https://docs.docker.com/get-docker/ |
| kubectl | 1.27+ | https://kubernetes.io/docs/tasks/tools/ |
| Kind | 0.20+ | https://kind.sigs.k8s.io/docs/user/quick-start/#installation |
| Python | 3.11+ | https://www.python.org/downloads/ |
| pip packages | - | `pip3 install redis pika python-docx rich` |

### Verify Prerequisites

```bash
# Check all tools are installed
docker --version
kubectl version --client
kind --version
python3 --version

# Check Docker is running
docker info > /dev/null 2>&1 && echo "Docker is running" || echo "Docker is NOT running"
```

---

## 2. Initial Setup (From Scratch)

### Step 1: Clone the Repository

```bash
git clone https://github.com/xmedinavei/ttg-distributed-compute.git
cd ttg-distributed-compute
```

### Step 2: Create the Kubernetes Cluster

This script creates a 4-node Kind cluster (1 control-plane + 3 workers), builds the Docker image, and loads it into the cluster.

```bash
chmod +x k8s/local/setup-local.sh
./k8s/local/setup-local.sh
```

**Expected output:**
- Checks Docker, kind, kubectl are installed
- Creates cluster `ttg-sandbox` with 4 nodes
- Builds `ttg-worker:latest` image
- Loads image into all cluster nodes
- Reports: "Your Kubernetes sandbox is ready!"

**Duration:** 2-5 minutes

### Step 3: Build the Versioned Image

```bash
chmod +x scripts/build.sh
./scripts/build.sh --version 1.3.0 --load-kind
```

This builds `ttg-worker:v1.3.0` with OCI labels and loads it into the Kind cluster.

### Step 4: Verify the Cluster

```bash
# Check nodes are ready
kubectl get nodes

# Expected: 4 nodes, all STATUS=Ready
# NAME                        STATUS   ROLES           AGE
# ttg-sandbox-control-plane   Ready    control-plane   5m
# ttg-sandbox-worker          Ready    <none>          5m
# ttg-sandbox-worker2         Ready    <none>          5m
# ttg-sandbox-worker3         Ready    <none>          5m
```

---

## 3. Build & Deploy Workflow

### Building a New Image Version

```bash
# Build with specific version
./scripts/build.sh --version 1.3.0 --load-kind

# Build without cache (clean rebuild)
./scripts/build.sh --version 1.3.0 --load-kind --no-cache

# Build for Azure Container Registry (future)
./scripts/build.sh --version 1.3.0 --acr <registry-name> --push
```

### Deploying Workers (Manual)

```bash
# Deploy M1 static mode (3 workers, 10K params)
kubectl apply -f k8s/manifests/parallel-jobs.yaml

# Deploy M2 Redis queue mode
kubectl apply -f k8s/manifests/parallel-jobs-queue.yaml

# Deploy M3 RabbitMQ queue mode
kubectl apply -f k8s/manifests/parallel-jobs-queue-rabbitmq.yaml

# Deploy standalone pods (for fault tolerance demos)
kubectl apply -f k8s/manifests/parallel-workers-standalone.yaml
```

### Deploying Infrastructure (Manual)

```bash
# Deploy Redis
kubectl apply -f k8s/manifests/redis.yaml
kubectl wait --for=condition=ready pod/ttg-redis --timeout=60s

# Deploy RabbitMQ
kubectl apply -f k8s/manifests/rabbitmq.yaml
kubectl wait --for=condition=ready pod/ttg-rabbitmq --timeout=120s

# Deploy RedisInsight (optional monitoring)
kubectl apply -f k8s/manifests/redis-insight.yaml
```

---

## 4. Running Demos

### Recommended: One-Command Demo

The `run-demo.sh` script handles everything: infrastructure deployment, task loading, worker deployment, optional fault injection, result reporting, and cleanup.

```bash
# RabbitMQ with fault injection (RECOMMENDED for supervisor demo)
./scripts/run-demo.sh --backend rabbitmq --scale small --fault-demo --monitor both

# Redis with fault injection
./scripts/run-demo.sh --backend redis --scale small --fault-demo --monitor both

# Medium-scale throughput test (no fault)
./scripts/run-demo.sh --backend rabbitmq --scale medium --monitor both

# Redis comparison at medium scale
./scripts/run-demo.sh --backend redis --scale medium --monitor both
```

### Demo Options

| Option | Values | Default | Description |
|--------|--------|---------|-------------|
| `--backend` | `redis`, `rabbitmq` | `redis` | Queue backend to use |
| `--scale` | `small`, `medium` | `small` | Workload size (1K or 10K params) |
| `--workers` | Any integer | 3 | Number of worker pods |
| `--fault-demo` | Flag | Off | Kill one worker at ~30% progress |
| `--monitor` | `cli`, `web`, `both`, `none` | `none` | Monitoring tools to start |
| `--skip-cleanup` | Flag | Off | Keep resources after demo |

### Scale Presets

| Preset | Parameters | Chunks | Chunk Size | Simulated Work |
|--------|-----------|--------|------------|----------------|
| `small` | 1,000 | 100 | 10 params | 100ms per chunk |
| `medium` | 10,000 | 100 | 100 params | 10ms per chunk |

### What the Demo Does

1. Checks prerequisites (kubectl, kind, docker)
2. Verifies the Kind cluster is running
3. Deploys the selected queue backend (Redis or RabbitMQ)
4. Loads task chunks into the queue
5. Deploys 3 worker pods
6. (If `--fault-demo`) Waits for ~30% completion, then kills one worker
7. Waits for 100% completion
8. Reports results (chunks, runtime, throughput, data loss)
9. Prompts for cleanup (unless `--skip-cleanup`)

---

## 5. Monitoring Procedures

### RabbitMQ Management UI

```bash
# Port-forward to access the UI
kubectl port-forward pod/ttg-rabbitmq 15672:15672

# Open in browser
# URL: http://localhost:15672
# Credentials: guest / guest
```

**What to check:**
- `ttg.tasks`: Should decrease as workers consume tasks
- `ttg.results`: Should increase until all tasks complete
- `ttg.tasks.retry`: Should be 0 (no retries needed)
- `ttg.tasks.dlq`: Should be 0 (no dead letters)
- Consumers: Should show active worker connections

### RedisInsight

```bash
# Port-forward to access RedisInsight
kubectl port-forward pod/redis-insight 8001:8001

# Open in browser: http://localhost:8001
# Add connection: Host=ttg-redis, Port=6379
```

**What to check:**
- Stream `ttg:tasks`: Message count and consumer group state
- Stream `ttg:results`: Growing result count
- Consumer Group `ttg-workers`: Pending messages per consumer

### CLI Monitoring

```bash
# Redis queue monitor (real-time dashboard)
python3 scripts/queue_monitor.py

# RabbitMQ queue snapshot
./scripts/rabbitmq_monitor.sh

# Continuous RabbitMQ monitoring (every 2 seconds)
./scripts/rabbitmq_monitor.sh --watch 2
```

### Kubernetes Pod Monitoring

```bash
# Watch pod status in real-time
kubectl get pods -w

# Watch TTG worker pods specifically
kubectl get pods -l ttg.io/project=distributed-compute -w

# View logs from all workers
kubectl logs -l ttg.io/component=worker --all-containers -f

# View logs from a specific worker
kubectl logs ttg-worker-0

# Check which node each pod runs on
kubectl get pods -o wide

# Check resource usage
kubectl top pods
kubectl top nodes
```

---

## 6. Recovery Procedures

### After System Reboot

```bash
# Run the recovery script
./scripts/recover-infra.sh
```

This script:
1. Checks if the Kind cluster exists
2. Restarts stopped Kind Docker containers
3. Waits for Kubernetes API to become ready
4. Waits for CoreDNS (required for service discovery)
5. Verifies all 4 nodes are ready
6. Checks/redeploys Redis
7. Checks/redeploys RedisInsight
8. Verifies the Docker image is loaded

### Manual Recovery Steps

If the recovery script fails:

```bash
# Step 1: Check if Kind cluster exists
kind get clusters

# Step 2: If cluster exists but containers are stopped
docker start ttg-sandbox-control-plane ttg-sandbox-worker ttg-sandbox-worker2 ttg-sandbox-worker3

# Step 3: Wait for API and check nodes
sleep 15
kubectl get nodes

# Step 4: Redeploy infrastructure
kubectl apply -f k8s/manifests/redis.yaml
kubectl apply -f k8s/manifests/rabbitmq.yaml
kubectl wait --for=condition=ready pod/ttg-redis --timeout=60s
kubectl wait --for=condition=ready pod/ttg-rabbitmq --timeout=120s

# Step 5: Reload image if needed
kind load docker-image ttg-worker:v1.3.0 --name ttg-sandbox
```

### Recreating the Cluster from Scratch

If the cluster is corrupted beyond recovery:

```bash
# Delete the old cluster
kind delete cluster --name ttg-sandbox

# Recreate everything
./k8s/local/setup-local.sh
./scripts/build.sh --version 1.3.0 --load-kind
```

---

## 7. Cleanup Procedures

### Safe Cleanup (TTG Resources Only)

```bash
# Preview what will be deleted (NO changes made)
./scripts/cleanup-ttg.sh --all --dry-run

# Remove worker pods only (keep Redis, RabbitMQ)
./scripts/cleanup-ttg.sh --pods --force

# Remove worker pods + purge RabbitMQ queues
./scripts/cleanup-ttg.sh --pods --rabbitmq --force

# Full TTG cleanup (pods + Redis + RabbitMQ)
./scripts/cleanup-ttg.sh --all --force
```

### Safety Guarantees

The cleanup script NEVER touches:
- Non-TTG Docker containers (e.g., MongoDB, other projects)
- Non-TTG Kubernetes resources
- System containers
- Docker images (only removes TTG-labeled pods)

### Deleting the Cluster Entirely

```bash
# Delete the Kind cluster (removes all containers and resources)
kind delete cluster --name ttg-sandbox
```

---

## 8. Troubleshooting Guide

### Pods Stuck in "Pending"

```bash
# Check why the pod is pending
kubectl describe pod <pod-name>
# Look at the "Events" section for scheduling failures

# Common causes:
# - Insufficient CPU/memory on nodes
kubectl describe nodes | grep -A 10 "Allocated resources"

# - Image not loaded into Kind
kind load docker-image ttg-worker:v1.3.0 --name ttg-sandbox
```

### Pods in "ImagePullBackOff"

```bash
# For Kind (local), images must be loaded, not pulled
kind load docker-image ttg-worker:v1.3.0 --name ttg-sandbox

# Verify image is in cluster
docker exec ttg-sandbox-control-plane crictl images | grep ttg-worker
```

### Redis Connection Refused

```bash
# Check Redis pod is running
kubectl get pod ttg-redis

# Check Redis is responding
kubectl exec ttg-redis -- redis-cli ping
# Expected: PONG

# If not running, redeploy
kubectl apply -f k8s/manifests/redis.yaml
kubectl wait --for=condition=ready pod/ttg-redis --timeout=60s
```

### RabbitMQ Connection Refused

```bash
# Check RabbitMQ pod is running
kubectl get pod ttg-rabbitmq

# Check RabbitMQ is responding
kubectl exec ttg-rabbitmq -- rabbitmq-diagnostics -q ping
# Expected: Ping succeeded

# If not running, redeploy
kubectl apply -f k8s/manifests/rabbitmq.yaml
kubectl wait --for=condition=ready pod/ttg-rabbitmq --timeout=120s
```

### Workers Complete But Results Missing

```bash
# Check Redis results
kubectl exec ttg-redis -- redis-cli XLEN ttg:results

# Check RabbitMQ results
kubectl exec ttg-rabbitmq -- rabbitmqctl list_queues name messages
```

### Kind Cluster Not Responding

```bash
# Check if Kind containers are running
docker ps --filter "name=ttg-sandbox"

# If containers are stopped, restart them
docker start ttg-sandbox-control-plane ttg-sandbox-worker ttg-sandbox-worker2 ttg-sandbox-worker3

# Wait for API
sleep 15
kubectl cluster-info --context kind-ttg-sandbox
```

### Demo Script Fails at Prerequisites

```bash
# Ensure the Kind context is set
kubectl config use-context kind-ttg-sandbox

# Verify cluster connectivity
kubectl cluster-info --context kind-ttg-sandbox
```

---

## 9. Configuration Reference

### Worker Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `WORKER_ID` | `0` | Unique worker identifier |
| `TOTAL_WORKERS` | `3` | Total number of workers |
| `TOTAL_PARAMETERS` | `10000` | Total parameters to process |
| `BATCH_SIZE` | `500` | Parameters per progress update |
| `CHUNK_SIZE` | `100` | Parameters per queue chunk |
| `SIMULATE_WORK_MS` | `1` | Simulated work time per parameter (ms) |
| `LOG_LEVEL` | `INFO` | Logging verbosity |
| `LOG_FORMAT` | `text` | Log output format (`text` or `json`) |
| `QUEUE_MODE` | `false` | Enable queue-based distribution |
| `QUEUE_BACKEND` | `redis` | Queue backend (`redis` or `rabbitmq`) |
| `REDIS_HOST` | `ttg-redis` | Redis service hostname |
| `REDIS_PORT` | `6379` | Redis port |
| `RABBITMQ_HOST` | `ttg-rabbitmq` | RabbitMQ service hostname |
| `RABBITMQ_PORT` | `5672` | RabbitMQ AMQP port |
| `IDLE_TIMEOUT_SECONDS` | `30` | Worker exits after this many seconds without tasks |
| `STALE_CHECK_INTERVAL_SECONDS` | `30` | How often to check for stale tasks |
| `STALE_THRESHOLD_MS` | `60000` | When a task is considered stale (ms) |
| `SIMULATE_FAULT_RATE` | `0.0` | Probability of simulated fault per chunk (0.0-1.0) |

### Kubernetes Resource Defaults

| Component | CPU Request | CPU Limit | Memory Request | Memory Limit |
|-----------|-------------|-----------|----------------|--------------|
| Worker | 100m | 500m | 128Mi | 256Mi |
| Redis | 100m | 500m | 128Mi | 256Mi |
| RabbitMQ | 200m | 1000m | 256Mi | 1Gi |

---

**Runbook Version:** 1.0
**Prepared By:** Xavier / TTG Team
**Repository:** https://github.com/xmedinavei/ttg-distributed-compute
