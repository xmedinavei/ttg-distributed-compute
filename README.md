# TTG - Distributed Computation on Kubernetes

[![Status](https://img.shields.io/badge/status-milestone_3_complete-brightgreen.svg)]()
[![Version](https://img.shields.io/badge/version-1.3.0-blue.svg)]()
[![Kubernetes](https://img.shields.io/badge/kubernetes-1.27+-blue.svg)]()
[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)]()
[![Fault Tolerant](https://img.shields.io/badge/fault_tolerant-verified-success.svg)]()

A framework for running distributed computation workloads across a Kubernetes cluster. Designed to accelerate parameter-heavy algorithms by distributing work across multiple worker nodes.

> **📊 Latest Test (Milestone 3, medium scale):** RabbitMQ 100/100 chunks in 38-39s (256-263 params/sec), Redis 100/100 in 41s (243 params/sec)  
> **✅ Fault tolerance VERIFIED**

## 🎉 Milestone 3 Complete

**Dual-backend queue architecture with fault tolerance (Redis + RabbitMQ)**

| Metric | Result |
| --- | --- |
| Chunks Completed | 100/100 (100%) on both backends |
| Workers Deployed | 3 |
| Medium Scale (10K) | RabbitMQ: 38-39s (256-263 p/s), Redis: 41s (243 p/s) |
| Fault Demo (small) | RabbitMQ: 49s (20 p/s), Redis: 48s (20 p/s) |
| Data Loss | ZERO |
| **Fault Tolerance** | ✅ **VERIFIED** |

## 🚀 Quick Start

### Option A: Full Demo with Fault Tolerance (Recommended)

```bash
cd /home/xavierand_/Desktop/TTG

# RabbitMQ backend (Milestone 3 default)
./scripts/run-demo.sh --backend rabbitmq --scale medium --monitor both

# Redis backend comparison
./scripts/run-demo.sh --backend redis --scale medium --monitor both

# Fault tolerance demo (small scale, kill one worker)
./scripts/run-demo.sh --backend rabbitmq --scale small --fault-demo --monitor both
```

This will:

1. Verify infrastructure is ready (Kind cluster, queue backend, Docker image)
2. Deploy 3 workers connected to the selected queue backend
3. Start 100 parameter chunks (medium: 10,000 params; small: 1,000 params)
4. **Kill a worker at ~30%** to demonstrate fault tolerance
5. Show 100% completion despite failure (zero data loss)
6. Prompt for cleanup (TTG resources only)

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
./scripts/build.sh --version 1.3.0 --load-kind
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
# Preview what will be deleted (safe, no changes)
./scripts/cleanup-ttg.sh --all --dry-run

# Remove TTG worker pods + purge queues
./scripts/cleanup-ttg.sh --pods --rabbitmq --force

# Full TTG cleanup (pods + Redis + RabbitMQ)
./scripts/cleanup-ttg.sh --all --force
```

> **Safety:** `cleanup-ttg.sh` only touches TTG-labeled Kubernetes resources. Non-TTG Docker containers and databases are never affected.

---

## Quick Reference

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
# RESOURCES & CLEANUP (TTG-only, safe for shared machines)
# ══════════════════════════════════════════════════════════════
./scripts/cleanup-ttg.sh --all --dry-run          # Preview cleanup
./scripts/cleanup-ttg.sh --pods --force           # Remove worker pods only
./scripts/cleanup-ttg.sh --pods --rabbitmq --force # Pods + purge RabbitMQ
./scripts/cleanup-ttg.sh --all --force            # Full TTG cleanup
```

---

## 📖 Documentation

> **📚 Full documentation index:** [docs/README.md](docs/README.md)

| Category | Key Documents |
|----------|---------------|
| **Quick Start** | [SUPERVISOR_REPORT.md](SUPERVISOR_REPORT.md) - Executive summary |
| **Project Guide** | [Project Explained](docs/knowledge/PROJECT_EXPLAINED.md) - Full project explanation |
| **Guides** | [Queue Mode Guide](docs/guides/QUEUE_MODE_GUIDE.md) ・ [Configuration](docs/guides/CONFIGURATION_GUIDE.md) |
| **Results** | [M3 RabbitMQ + Monitoring](docs/results/TEST_RESULTS_M3_RABBITMQ_MONITORING.md) ・ [M2 Fault Tolerance](docs/results/TEST_RESULTS_M2_FAULT_TOLERANCE.md) ・ [M1 Parallel Jobs](docs/results/TEST_RESULTS_M1_PARALLEL_JOBS.md) |
| **Setup** | [Local K8s](docs/setup/KUBERNETES_SETUP.md) ・ [Azure AKS](docs/setup/AZURE_AKS_GUIDE.md) |
| **Knowledge** | [Kubernetes Explained](docs/knowledge/KUBERNETES_EXPLAINED.md) ・ [Kind Tutorial](docs/knowledge/KIND_EXPLAINED.md) |
| **Tracking** | [Project Tracker](docs/tracking/PROJECT_TRACKER.md) ・ [Overview](docs/tracking/PROJECT_OVERVIEW.md) |
| **AME-UP Deliverables** | [Deliverables Folder](deliverables/) - Performance Report, Technical Artifacts, Presentation, Playbook |

---

## 🏗️ Project Structure

```
TTG/
├── src/                          # Source code
│   ├── worker.py                 # Main worker (v1.3.0, dual backend)
│   ├── queue_utils.py            # Redis Streams queue wrapper
│   ├── rabbitmq_queue.py         # RabbitMQ queue wrapper (retry + DLQ)
│   └── logging_config.py         # Structured logging infrastructure
│
├── docker/
│   └── Dockerfile                # Multi-stage build with OCI labels
│
├── k8s/
│   ├── manifests/
│   │   ├── parallel-jobs.yaml           # M1 static mode
│   │   ├── redis.yaml                   # Redis deployment
│   │   ├── rabbitmq.yaml                # RabbitMQ deployment + service
│   │   ├── parallel-jobs-queue.yaml     # Redis queue mode
│   │   ├── parallel-jobs-queue-rabbitmq.yaml # RabbitMQ queue mode
│   │   └── parallel-workers-standalone.yaml  # M2 fault-tolerance demo
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
├── deliverables/                 # AME-UP final submission
│   ├── D1_Optimization_Performance_Report.md
│   ├── D2_Technical_Artifacts_Index.md
│   ├── D2_Operational_Runbook.md
│   ├── D3_Final_Presentation.md
│   ├── D3_Engineering_Playbook.md
│   └── docx/                    # Word document versions
│
├── SUPERVISOR_REPORT.md          # Executive summary
├── requirements.txt              # Python dependencies
└── README.md                     # This file
```

---

## 🎯 How It Works

### The Problem

You have **10 million parameters** to calculate. Running sequentially takes forever.

### The Solution (Milestone 3 - Dual Queue Mode)

Workers dynamically pull tasks from Redis Streams or RabbitMQ:

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
│                    │ REDIS or  │                            │
│                    │ RabbitMQ  │                            │
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
| `QUEUE_MODE`       | false     | Enable queue mode                  |
| `QUEUE_BACKEND`    | redis     | Queue backend: redis or rabbitmq   |
| `REDIS_HOST`       | ttg-redis | Redis service hostname            |
| `REDIS_PORT`       | 6379      | Redis port                        |
| `RABBITMQ_HOST`    | ttg-rabbitmq | RabbitMQ service hostname      |
| `RABBITMQ_PORT`    | 5672      | RabbitMQ AMQP port                |

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

## 📊 Future Enhancements (Post Milestone 3)

- [x] **Message Queue**: Redis Streams + RabbitMQ dual-backend support complete
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

_Last Updated: 2026-02-10 | Version: 1.3.0 | Milestone 3: ✅ Complete | AME-UP Deliverables: ✅ Ready_
