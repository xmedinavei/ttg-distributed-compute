# TTG - Distributed Computation on Kubernetes

[![Status](https://img.shields.io/badge/status-milestone_2_complete-brightgreen.svg)]()
[![Version](https://img.shields.io/badge/version-1.2.1-blue.svg)]()
[![Kubernetes](https://img.shields.io/badge/kubernetes-1.27+-blue.svg)]()
[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)]()
[![Fault Tolerant](https://img.shields.io/badge/fault_tolerant-verified-success.svg)]()

A framework for running distributed computation workloads across a Kubernetes cluster. Designed to accelerate parameter-heavy algorithms by distributing work across multiple worker nodes.

> **📊 Latest Test (Milestone 2):** 100/100 chunks completed in 44 seconds (22 params/sec) despite worker killed at 30%  
> **✅ Fault tolerance VERIFIED**

## 🎉 Milestone 2 Complete!

**Queue-Based Architecture with Fault Tolerance**

| Metric              | Result          |
| ------------------- | --------------- |
| Chunks Completed    | 100/100 (100%)  |
| Workers Deployed    | 3               |
| Worker Killed At    | 30% progress    |
| Total Time          | 44 seconds      |
| Throughput          | 22 params/sec   |
| **Fault Tolerance** | ✅ **VERIFIED** |

## 🚀 Quick Start

### Option A: Full Demo with Fault Tolerance (Recommended)

```bash
cd /home/xavierand_/Desktop/TTG

# Run the full demo (handles setup, deployment, and cleanup)
./scripts/run-demo.sh --scale small --fault-demo --monitor cli
```

This will:

1. Verify infrastructure is ready
2. Deploy Redis and 3 workers
3. Start 100 parameter chunks
4. **Kill a worker at 30%** to demonstrate fault tolerance
5. Show 100% completion despite failure
6. Cleanup automatically

### Option B: Manual Setup (5 minutes)

### Prerequisites

- Docker installed and running
- `kubectl` installed
- `kind` installed (for local testing)

### 1. Create the Cluster

```bash
cd /home/xavierand_/Desktop/TTG

# Create local Kubernetes cluster with 3 worker nodes
./k8s/local/setup-local.sh
```

### 2. Build the Worker Image

```bash
# Build with version and load into kind cluster
./scripts/build.sh --version 1.1.0 --load-kind
```

### 3. Deploy Workers

```bash
kubectl apply -f k8s/manifests/parallel-jobs.yaml
```

### 4. Watch the Magic! ✨

```bash
# Watch pods being created and running
kubectl get pods -l app.kubernetes.io/name=ttg-worker -w

# See which node each pod runs on
kubectl get pods -l app.kubernetes.io/name=ttg-worker -o wide

# View logs from all workers (with enhanced logging)
kubectl logs -l app.kubernetes.io/name=ttg-worker -f
```

### 5. View Resources

```bash
# See all TTG resources (Docker + Kubernetes)
./scripts/list-resources.sh
```

### 6. Clean Up

```bash
# Preview what will be deleted
./scripts/cleanup-all.sh --dry-run

# Delete job only (keep cluster for next run)
./scripts/cleanup-all.sh --keep-cluster

# Delete everything including cluster
./scripts/cleanup-all.sh --force
```

---

## � Quick Reference

Copy-paste commands for daily use:

```bash
# ══════════════════════════════════════════════════════════════
# BUILD & DEPLOY
# ══════════════════════════════════════════════════════════════
./scripts/build.sh --version 1.1.0 --load-kind    # Build image
kubectl apply -f k8s/manifests/parallel-jobs.yaml # Deploy workers

# ══════════════════════════════════════════════════════════════
# MONITOR & LOGS
# ══════════════════════════════════════════════════════════════
kubectl get pods -l app.kubernetes.io/name=ttg-worker -w      # Watch pods
kubectl get pods -o wide                                       # See node placement
kubectl logs -l app.kubernetes.io/name=ttg-worker -f          # Stream all logs
kubectl logs <pod-name>                                        # Single pod logs
kubectl get job ttg-computation                                # Job status

# ══════════════════════════════════════════════════════════════
# RESOURCES & CLEANUP
# ══════════════════════════════════════════════════════════════
./scripts/list-resources.sh                       # View all TTG resources
./scripts/cleanup-all.sh --dry-run                # Preview cleanup
./scripts/cleanup-all.sh --keep-cluster           # Delete job, keep cluster
./scripts/cleanup-all.sh --force                  # Delete everything
kubectl delete job ttg-computation                # Quick job reset
```

---

## 📖 Documentation

> **📚 Full documentation index:** [docs/README.md](docs/README.md)

| Category | Key Documents |
|----------|---------------|
| **Quick Start** | [SUPERVISOR_REPORT.md](SUPERVISOR_REPORT.md) - Executive summary |
| **Guides** | [Queue Mode Guide](docs/guides/QUEUE_MODE_GUIDE.md) ・ [Configuration](docs/guides/CONFIGURATION_GUIDE.md) |
| **Results** | [M2 Fault Tolerance](docs/results/TEST_RESULTS_M2_FAULT_TOLERANCE.md) ・ [M1 Parallel Jobs](docs/results/TEST_RESULTS_M1_PARALLEL_JOBS.md) |
| **Setup** | [Local K8s](docs/setup/KUBERNETES_SETUP.md) ・ [Azure AKS](docs/setup/AZURE_AKS_GUIDE.md) |
| **Knowledge** | [Kubernetes Explained](docs/knowledge/KUBERNETES_EXPLAINED.md) ・ [Kind Tutorial](docs/knowledge/KIND_EXPLAINED.md) |
| **Tracking** | [Project Tracker](docs/tracking/PROJECT_TRACKER.md) ・ [Overview](docs/tracking/PROJECT_OVERVIEW.md) |

---

## 🏗️ Project Structure

```
TTG/
├── src/                          # Source code
│   ├── worker.py                 # Main worker (v1.2.1 with queue mode)
│   ├── queue_utils.py            # Redis Streams wrapper
│   └── logging_config.py         # Structured logging infrastructure
│
├── docker/
│   └── Dockerfile                # Multi-stage build with OCI labels
│
├── k8s/
│   ├── manifests/
│   │   ├── parallel-jobs.yaml           # M1 static mode
│   │   ├── redis.yaml                   # Redis deployment
│   │   └── parallel-workers-standalone.yaml  # M2 queue mode
│   ├── local/
│   │   ├── kind-config.yaml      # Kind cluster configuration
│   │   └── setup-local.sh        # Cluster setup script
│   └── azure/
│       └── setup-aks.sh          # Azure AKS setup (future)
│
├── scripts/
│   ├── run-demo.sh               # Full demo with fault tolerance
│   ├── cleanup-ttg.sh            # Safe cleanup (protected resources)
│   ├── recover-infra.sh          # Infrastructure recovery
│   ├── build.sh                  # Versioned image building
│   ├── list-resources.sh         # Resource inventory
│   └── aggregate_results.py      # Results aggregation
│
├── docs/                         # Documentation
│   ├── README.md                 # Docs index
│   ├── architecture/             # System design docs
│   ├── guides/                   # Operational guides
│   ├── knowledge/                # Learning materials
│   ├── results/                  # Test results
│   ├── setup/                    # Installation guides
│   └── tracking/                 # Project tracking
│
├── SUPERVISOR_REPORT.md          # Executive summary
├── requirements.txt              # Python dependencies
└── README.md                     # This file
```

---

## 🎯 How It Works

### The Problem

You have **10 million parameters** to calculate. Running sequentially takes forever.

### The Solution (Milestone 2 - Queue Mode)

Workers dynamically pull tasks from a Redis queue:

```
┌─────────────────────────────────────────────────────────────┐
│                    KUBERNETES CLUSTER                        │
│                                                             │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │
│  │  Worker 0   │  │  Worker 1   │  │  Worker 2   │         │
│  │  Node 1     │  │  Node 2     │  │  Node 3     │         │
│  │             │  │    ╳ DIES   │  │             │         │
│  │ Pulls tasks │  │             │  │ Picks up    │         │
│  │ from queue  │  │             │  │ stale tasks │         │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘         │
│         │                │                │                 │
│         └────────────────┼────────────────┘                 │
│                          │                                  │
│                    ┌─────▼─────┐                            │
│                    │   REDIS   │                            │
│                    │  Streams  │                            │
│                    └───────────┘                            │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

**Fault Tolerance:** If Worker 1 dies, Workers 0 and 2 continue. Stale tasks are automatically reclaimed.

---

## ⚙️ Configuration

### Environment Variables

| Variable           | Default   | Description                       |
| ------------------ | --------- | --------------------------------- |
| `WORKER_ID`        | 0         | Unique worker identifier          |
| `TOTAL_WORKERS`    | 3         | Total number of workers           |
| `TOTAL_PARAMETERS` | 10000     | Total parameters to process       |
| `BATCH_SIZE`       | 500       | Parameters per progress update    |
| `SIMULATE_WORK_MS` | 1         | Simulated work time per parameter |
| `LOG_LEVEL`        | INFO      | DEBUG, INFO, WARNING, ERROR       |
| `LOG_FORMAT`       | text      | text (human) or json (machine)    |
| `QUEUE_MODE`       | false     | Enable queue mode (M2)            |
| `REDIS_HOST`       | ttg-redis | Redis service hostname            |
| `REDIS_PORT`       | 6379      | Redis port                        |

### Kubernetes Resources

Workers are configured with resource limits to prevent starving other applications:

```yaml
resources:
  requests:
    cpu: "100m" # 0.1 CPU requested
    memory: "128Mi" # 128MB RAM requested
  limits:
    cpu: "500m" # Max 0.5 CPU
    memory: "256Mi" # Max 256MB RAM
```

---

## 🔧 Customizing the Worker

The worker (`src/worker.py`) contains a placeholder computation. Replace the `_compute_parameter` method with your actual algorithm:

```python
def _compute_parameter(self, param_id: int) -> Dict[str, Any]:
    """
    Process a single parameter and return the result.

    REPLACE THIS WITH YOUR ACTUAL ALGORITHM
    """
    # Your computation here
    result = your_algorithm(param_id)

    return {
        'param_id': param_id,
        'result': result,
        'worker_id': self.worker_id
    }
```

---

## ☁️ Azure Deployment

For production-like testing on Azure AKS:

```bash
# Setup AKS cluster
chmod +x k8s/azure/setup-aks.sh
./k8s/azure/setup-aks.sh

# Build and push to Azure Container Registry
az acr login --name <your-acr-name>
docker build -t <your-acr-name>.azurecr.io/ttg-worker:latest -f docker/Dockerfile .
docker push <your-acr-name>.azurecr.io/ttg-worker:latest

# Update image reference in manifest and deploy
# (edit k8s/manifests/parallel-jobs.yaml)
kubectl apply -f k8s/manifests/parallel-jobs.yaml
```

See [docs/setup/KUBERNETES_SETUP.md](docs/setup/KUBERNETES_SETUP.md) for detailed Azure instructions.

---

## 📊 Future Enhancements (Post Milestone 1)

- [ ] **Message Queue**: Add Redis/RabbitMQ for dynamic work distribution
- [ ] **Checkpointing**: Save progress for fault tolerance
- [ ] **Result Aggregation**: Collect and combine worker outputs
- [ ] **Observability**: Add Prometheus metrics and Grafana dashboards
- [ ] **Auto-scaling**: Scale workers based on queue depth
- [ ] **Persistent Storage**: Mount volumes for result persistence

---

## 🐛 Troubleshooting

### Pods stuck in "Pending"

```bash
kubectl describe pod <pod-name>
# Check Events section for issues
```

Usually caused by insufficient resources. Check node capacity:

```bash
kubectl describe nodes | grep -A 10 "Allocated resources"
```

### Image not found

For kind (local):

```bash
kind load docker-image ttg-worker:latest --name ttg-sandbox
```

For AKS:

```bash
az acr login --name <acr-name>
docker push <acr-name>.azurecr.io/ttg-worker:latest
```

### View worker logs

```bash
# All workers
kubectl logs -l job-name=ttg-computation --all-containers

# Specific pod
kubectl logs <pod-name>

# Follow logs
kubectl logs -f <pod-name>
```

---

## 📝 License

MIT License - See LICENSE file for details.

---

_Last Updated: 2026-01-27 | Version: 1.1.0 | Milestone 1: ✅ Complete_
