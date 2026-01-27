# TTG - Distributed Computation on Kubernetes

[![Status](https://img.shields.io/badge/status-development-yellow.svg)]()
[![Kubernetes](https://img.shields.io/badge/kubernetes-1.27+-blue.svg)]()
[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)]()

A framework for running distributed computation workloads across a Kubernetes cluster. Designed to accelerate parameter-heavy algorithms by distributing work across multiple worker nodes.

## 🚀 Quick Start (5 minutes)

### Prerequisites

- Docker installed and running
- `kubectl` installed
- `kind` installed (for local testing)

### 1. Create the Cluster

```bash
# Clone/navigate to project
cd /home/xavierand_/Desktop/TTG

# Create local Kubernetes cluster with 3 worker nodes
chmod +x k8s/local/setup-local.sh
./k8s/local/setup-local.sh
```

### 2. Build the Worker Image

```bash
chmod +x scripts/build.sh
./scripts/build.sh
```

### 3. Deploy Workers

```bash
chmod +x scripts/deploy.sh
./scripts/deploy.sh
```

### 4. Watch the Magic! ✨

```bash
# Watch pods being created and running
kubectl get pods -l job-name=ttg-computation -w

# See which node each pod runs on
kubectl get pods -l job-name=ttg-computation -o wide

# View logs from all workers
kubectl logs -l job-name=ttg-computation --all-containers -f
```

### 5. Clean Up

```bash
chmod +x scripts/cleanup.sh
./scripts/cleanup.sh

# To delete the entire cluster:
./scripts/cleanup.sh --all
```

---

## 📖 Documentation

| Document                                             | Description                                          |
| ---------------------------------------------------- | ---------------------------------------------------- |
| [docs/PROJECT_OVERVIEW.md](docs/PROJECT_OVERVIEW.md) | Full project explanation, K8s concepts, architecture |
| [docs/KUBERNETES_SETUP.md](docs/KUBERNETES_SETUP.md) | Detailed setup instructions (local & Azure)          |

---

## 🏗️ Project Structure

```
TTG/
├── docs/                     # Documentation
│   ├── PROJECT_OVERVIEW.md   # Problem explanation & architecture
│   └── KUBERNETES_SETUP.md   # Setup instructions
├── docker/
│   └── Dockerfile            # Worker container definition
├── src/
│   ├── worker.py             # Main computation worker
│   └── utils.py              # Utility functions
├── k8s/
│   ├── local/
│   │   ├── kind-config.yaml  # 3-node cluster config
│   │   └── setup-local.sh    # Local setup script
│   ├── azure/
│   │   └── setup-aks.sh      # Azure AKS setup script
│   └── manifests/
│       ├── parallel-jobs.yaml # Parallel worker jobs
│       └── worker-job.yaml    # Single worker job
├── scripts/
│   ├── build.sh              # Build Docker image
│   ├── deploy.sh             # Deploy to Kubernetes
│   ├── cleanup.sh            # Clean up resources
│   └── run-local.sh          # Run worker locally
├── requirements.txt          # Python dependencies
└── README.md                 # This file
```

---

## 🎯 How It Works

### The Problem

You have **10 million parameters** to calculate. Running sequentially takes forever.

### The Solution

Split the work across multiple Kubernetes workers:

```
Worker 0: Parameters 0 - 3,333,333
Worker 1: Parameters 3,333,334 - 6,666,666
Worker 2: Parameters 6,666,667 - 9,999,999
```

Each worker runs in a container on a different node, processing in parallel.

### The Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    KUBERNETES CLUSTER                        │
│                                                             │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │
│  │  Worker 0   │  │  Worker 1   │  │  Worker 2   │         │
│  │  Node 1     │  │  Node 2     │  │  Node 3     │         │
│  │             │  │             │  │             │         │
│  │ Params:     │  │ Params:     │  │ Params:     │         │
│  │ 0-3.3M      │  │ 3.3M-6.6M   │  │ 6.6M-10M    │         │
│  └─────────────┘  └─────────────┘  └─────────────┘         │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## ⚙️ Configuration

### Environment Variables

| Variable           | Default | Description                       |
| ------------------ | ------- | --------------------------------- |
| `WORKER_ID`        | 0       | Unique worker identifier          |
| `TOTAL_WORKERS`    | 3       | Total number of workers           |
| `TOTAL_PARAMETERS` | 10000   | Total parameters to process       |
| `BATCH_SIZE`       | 100     | Parameters per progress update    |
| `SIMULATE_WORK_MS` | 1       | Simulated work time per parameter |

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

See [docs/KUBERNETES_SETUP.md](docs/KUBERNETES_SETUP.md) for detailed Azure instructions.

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

_Created: 2026-01-26 | First Milestone: Kubernetes Sandbox Setup_
