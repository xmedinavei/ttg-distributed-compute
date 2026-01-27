# TTG - Distributed Computation on Kubernetes

## Project Status

| Item                   | Status             | Date       |
| ---------------------- | ------------------ | ---------- |
| Project Initialized    | ✅ Complete        | 2026-01-26 |
| Documentation          | ✅ Complete        | 2026-01-26 |
| Local K8s Setup (kind) | 🔄 Ready to Deploy | 2026-01-26 |
| Worker Implementation  | ✅ Complete        | 2026-01-26 |
| Azure AKS Alternative  | 📋 Documented      | 2026-01-26 |
| First Milestone        | 🎯 In Progress     | -          |

---

## 📖 Table of Contents

1. [Understanding the Problem](#understanding-the-problem)
2. [Why Kubernetes?](#why-kubernetes)
3. [Why a Sandbox Environment?](#why-a-sandbox-environment)
4. [Kubernetes Concepts Explained](#kubernetes-concepts-explained)
5. [Architecture Overview](#architecture-overview)
6. [Milestone 1 Requirements](#milestone-1-requirements)
7. [Decision Log](#decision-log)
8. [Challenges & Risks](#challenges--risks)

---

## 🍕 Understanding the Problem

### The Pizza Analogy

Imagine you have a **giant pizza with 10 million slices** (10M parameters to calculate), and you need to eat all of them.

**The Sequential Approach (Current Problem):**

```
You alone eating 10M slices:
Slice 1 → Slice 2 → Slice 3 → ... → Slice 10,000,000
Time: FOREVER 😱
```

**The Parallel Approach (Our Solution):**

```
You invite 10 friends (workers), each eats 1M slices:
Worker 1: Slices 1 - 1,000,000
Worker 2: Slices 1,000,001 - 2,000,000
Worker 3: Slices 2,000,001 - 3,000,000
...
Worker 10: Slices 9,000,001 - 10,000,000

Time: 10x faster! 🚀
```

### The Technical Reality

Your algorithm needs to process **10 million parameters**. Each parameter calculation is (presumably) independent, meaning:

- Parameter #1's result doesn't depend on Parameter #2's result
- They can be calculated **in parallel** by different machines
- Results are collected and aggregated at the end

**This is called "Embarrassingly Parallel" computation** - work that's easy to split because there are no dependencies between tasks.

### Visual Representation

```
                    ┌─────────────────────────────────────────────┐
                    │          10 MILLION PARAMETERS              │
                    │  [1, 2, 3, 4, 5, ... 9,999,998, 9,999,999, 10,000,000]  │
                    └─────────────────────────────────────────────┘
                                          │
                                          ▼
                              ┌───────────────────┐
                              │    COORDINATOR    │
                              │  (splits work)    │
                              └───────────────────┘
                                          │
              ┌───────────────────────────┼───────────────────────────┐
              ▼                           ▼                           ▼
    ┌─────────────────┐         ┌─────────────────┐         ┌─────────────────┐
    │    WORKER 1     │         │    WORKER 2     │         │    WORKER 3     │
    │   Node: node-1  │         │   Node: node-2  │         │   Node: node-3  │
    │                 │         │                 │         │                 │
    │ Parameters:     │         │ Parameters:     │         │ Parameters:     │
    │ 1 - 3,333,333   │         │ 3,333,334 -     │         │ 6,666,668 -     │
    │                 │         │ 6,666,667       │         │ 10,000,000      │
    └─────────────────┘         └─────────────────┘         └─────────────────┘
              │                           │                           │
              ▼                           ▼                           ▼
    ┌─────────────────┐         ┌─────────────────┐         ┌─────────────────┐
    │  Partial Result │         │  Partial Result │         │  Partial Result │
    │      #1         │         │      #2         │         │      #3         │
    └─────────────────┘         └─────────────────┘         └─────────────────┘
              │                           │                           │
              └───────────────────────────┼───────────────────────────┘
                                          ▼
                              ┌───────────────────┐
                              │    AGGREGATOR     │
                              │ (combines results)│
                              └───────────────────┘
                                          │
                                          ▼
                    ┌─────────────────────────────────────────────┐
                    │              FINAL RESULT                   │
                    └─────────────────────────────────────────────┘
```

---

## 🤔 Why Kubernetes?

### What is Kubernetes (K8s)?

Kubernetes is a **container orchestration platform**. Think of it as a **smart manager** that:

1. **Schedules work**: Decides which machine runs which task
2. **Manages resources**: Ensures no machine is overloaded
3. **Handles failures**: Restarts crashed workers automatically
4. **Scales**: Easily add/remove workers as needed

### Why Not Just Use Multiple VMs or Docker Compose?

| Feature                  | VMs/Docker Compose | Kubernetes   |
| ------------------------ | ------------------ | ------------ |
| Auto-restart on failure  | ❌ Manual          | ✅ Automatic |
| Scale to 100s of workers | 😓 Painful         | ✅ Easy      |
| Resource limits          | ❌ Manual config   | ✅ Built-in  |
| Load distribution        | ❌ Manual          | ✅ Automatic |
| Production-ready         | ❌ DIY             | ✅ Yes       |
| Learning curve           | Low                | Medium       |

### Kubernetes Value for This Project

```
Without K8s:
- You manually SSH into 10 machines
- You manually start workers on each
- If one crashes, you manually restart it
- If you need more workers, you manually provision machines

With K8s:
- Tell K8s: "Run 10 workers"
- K8s figures out where to run them
- K8s restarts crashed workers
- Tell K8s: "Now run 100 workers" → Done
```

---

## 🏖️ Why a Sandbox Environment?

### The Risk Without Sandbox

Your production Kubernetes cluster (`PROD k8s`) already runs critical applications. If you deploy your computation workload directly:

```
DANGER SCENARIO:
┌─────────────────────────────────────────────────────────────┐
│                    PROD K8s CLUSTER                         │
├─────────────────────────────────────────────────────────────┤
│  App A (critical)    App B (critical)    App C (critical)   │
│  CPU: 20%            CPU: 30%            CPU: 15%           │
│  Memory: 4GB         Memory: 8GB         Memory: 2GB        │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  🚨 YOUR ALGORITHM DEPLOYS 🚨                               │
│  Worker 1: CPU 100%, Memory 16GB                           │
│  Worker 2: CPU 100%, Memory 16GB                           │
│  Worker 3: CPU 100%, Memory 16GB                           │
│                                                             │
│  RESULT: App A, B, C CRASH! 💀                              │
│  (No resources left for them)                              │
└─────────────────────────────────────────────────────────────┘
```

### Sandbox Benefits

| Benefit             | Description                             |
| ------------------- | --------------------------------------- |
| **Isolation**       | Your tests don't affect production apps |
| **Experimentation** | Try different configs without fear      |
| **Cost Control**    | Know exact resources before production  |
| **Learning**        | Make mistakes safely                    |
| **Reproducibility** | Document setup for future use           |

### Sandbox Options

We have two options for sandbox:

1. **Local (kind/minikube)** - Recommended for learning
2. **Azure AKS** - For production-like testing

---

## 📚 Kubernetes Concepts Explained

### For Absolute Beginners

#### 1. Cluster

A **cluster** is a group of machines (physical or virtual) working together.

```
┌─────────────────────────────────────────────────────────┐
│                    KUBERNETES CLUSTER                    │
│                                                         │
│   ┌─────────────┐   ┌─────────────┐   ┌─────────────┐  │
│   │  Machine 1  │   │  Machine 2  │   │  Machine 3  │  │
│   │   (Node)    │   │   (Node)    │   │   (Node)    │  │
│   └─────────────┘   └─────────────┘   └─────────────┘  │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

#### 2. Node

A **node** is a single machine in the cluster. There are two types:

- **Control Plane Node**: The "brain" - schedules work, manages state
- **Worker Node**: The "hands" - actually runs your containers

```
Control Plane: "Hey Worker Node 2, run this container"
Worker Node 2: "On it, boss!" *runs container*
```

#### 3. Pod

A **Pod** is the smallest deployable unit. It's a wrapper around one or more containers.

```
┌──────────────────────────────┐
│            POD               │
│  ┌────────────────────────┐  │
│  │      CONTAINER         │  │
│  │   (your Python app)    │  │
│  └────────────────────────┘  │
│                              │
│  Shared network, storage     │
└──────────────────────────────┘
```

#### 4. Job

A **Job** creates Pods to run a task to completion, then stops.

Perfect for our use case:

```
Job: "Process parameters 1-1000"
  → Creates Pod
  → Pod runs calculation
  → Pod completes
  → Job marks as "Completed"
```

#### 5. Deployment

A **Deployment** manages Pods that should run continuously (24/7 services).

```
Deployment: "Always keep 3 web servers running"
  → If one crashes, automatically start a new one
```

#### 6. Service

A **Service** provides a stable network endpoint to access Pods.

```
Without Service:
  Pod IP: 10.0.0.5 (changes if Pod restarts!)

With Service:
  Service IP: 10.1.0.1 (stable)
  → Routes to Pod 10.0.0.5
  → If Pod restarts as 10.0.0.6, Service auto-updates
```

#### 7. ConfigMap & Secret

**ConfigMap**: Store configuration data (non-sensitive)
**Secret**: Store sensitive data (passwords, keys)

```yaml
# ConfigMap example
TOTAL_PARAMETERS: "10000000"
BATCH_SIZE: "1000"

# Secret example
DATABASE_PASSWORD: "***encrypted***"
```

### Quick Reference Table

| Concept    | Purpose                | Analogy              |
| ---------- | ---------------------- | -------------------- |
| Cluster    | Group of machines      | A company            |
| Node       | Single machine         | An employee          |
| Pod        | Container wrapper      | A desk               |
| Job        | Run-to-completion task | A one-time task      |
| Deployment | Long-running service   | A permanent position |
| Service    | Network endpoint       | Reception desk       |
| ConfigMap  | Configuration          | Employee handbook    |
| Secret     | Sensitive config       | Safe combination     |

---

## 🏗️ Architecture Overview

### Phase 1: Simple Job-based Architecture (First Milestone)

For the first milestone, we use Kubernetes **Jobs** with **indexed completions**:

```
┌─────────────────────────────────────────────────────────────────┐
│                     LOCAL K8s CLUSTER (kind)                    │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                    CONTROL PLANE                         │   │
│  │                    (kind-control-plane)                  │   │
│  └─────────────────────────────────────────────────────────┘   │
│                              │                                  │
│         ┌────────────────────┼────────────────────┐            │
│         ▼                    ▼                    ▼            │
│  ┌─────────────┐      ┌─────────────┐      ┌─────────────┐    │
│  │   WORKER    │      │   WORKER    │      │   WORKER    │    │
│  │   NODE 1    │      │   NODE 2    │      │   NODE 3    │    │
│  │             │      │             │      │             │    │
│  │ ┌─────────┐ │      │ ┌─────────┐ │      │ ┌─────────┐ │    │
│  │ │  Job-0  │ │      │ │  Job-1  │ │      │ │  Job-2  │ │    │
│  │ │ params: │ │      │ │ params: │ │      │ │ params: │ │    │
│  │ │ 0-3333  │ │      │ │ 3334-   │ │      │ │ 6667-   │ │    │
│  │ │         │ │      │ │ 6666    │ │      │ │ 9999    │ │    │
│  │ └─────────┘ │      │ └─────────┘ │      │ └─────────┘ │    │
│  └─────────────┘      └─────────────┘      └─────────────┘    │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Phase 2: Queue-based Architecture (Future)

For more complex scenarios, use a message queue:

```
┌─────────────────────────────────────────────────────────────────┐
│                     K8s CLUSTER (future)                        │
│                                                                 │
│  ┌───────────────┐                                              │
│  │  COORDINATOR  │                                              │
│  │  (creates     │                                              │
│  │   tasks)      │                                              │
│  └───────┬───────┘                                              │
│          │ publishes tasks                                      │
│          ▼                                                      │
│  ┌───────────────────────────────────────────────┐              │
│  │              MESSAGE QUEUE                    │              │
│  │     (Redis/RabbitMQ/Azure Service Bus)        │              │
│  │  [Task1][Task2][Task3][Task4][Task5]...       │              │
│  └───────────────────────────────────────────────┘              │
│          │                                                      │
│          │ workers pull tasks                                   │
│          ▼                                                      │
│  ┌─────────┐   ┌─────────┐   ┌─────────┐   ┌─────────┐        │
│  │ Worker1 │   │ Worker2 │   │ Worker3 │   │ Worker4 │  ...   │
│  └─────────┘   └─────────┘   └─────────┘   └─────────┘        │
│          │           │             │             │              │
│          └───────────┴─────────────┴─────────────┘              │
│                              │                                  │
│                              ▼                                  │
│                    ┌─────────────────┐                          │
│                    │   RESULT STORE  │                          │
│                    │ (Redis/Storage) │                          │
│                    └─────────────────┘                          │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🎯 Milestone 1 Requirements

### Goal

Setup sandbox Kubernetes environment with 3 worker nodes and run distributed computation.

### Success Criteria

| #   | Criterion             | Measurable Outcome                        |
| --- | --------------------- | ----------------------------------------- |
| 1   | K8s cluster running   | `kubectl get nodes` shows 3+ nodes        |
| 2   | Workers containerized | Docker image built successfully           |
| 3   | Jobs distributed      | Jobs run on different nodes               |
| 4   | Work partitioned      | Each job processes unique parameter range |
| 5   | Results visible       | `kubectl logs` shows computation output   |
| 6   | Documented            | All steps reproducible from docs          |

### Deliverables

1. ✅ Documentation (this file + setup guides)
2. ✅ Local K8s cluster configuration (kind)
3. ✅ Python worker implementation
4. ✅ Docker image for worker
5. ✅ Kubernetes Job manifests
6. ✅ Azure AKS alternative documentation

---

## 📝 Decision Log

| Date       | Decision                         | Rationale                             | Alternatives Considered |
| ---------- | -------------------------------- | ------------------------------------- | ----------------------- |
| 2026-01-26 | Use kind for local K8s           | Faster setup, free, good for learning | minikube, k3s           |
| 2026-01-26 | Start with K8s Jobs (not queues) | Simpler for first milestone           | Celery, RabbitMQ, Kafka |
| 2026-01-26 | Python for workers               | User preference, good ecosystem       | Go, Java                |
| 2026-01-26 | 3 worker nodes                   | Matches milestone requirement         | More nodes              |
| 2026-01-26 | Indexed Jobs for distribution    | K8s native, no external dependencies  | Job arrays, manual      |

---

## ⚠️ Challenges & Risks

### Current Challenges

| Challenge               | Impact | Mitigation                            |
| ----------------------- | ------ | ------------------------------------- |
| Learning curve (K8s)    | Medium | Detailed docs, simple first milestone |
| Resource limits unknown | Medium | Start small, profile, adjust          |
| No actual algorithm yet | Low    | Use placeholder computation           |

### Potential Risks

| Risk                               | Probability | Impact | Mitigation                 |
| ---------------------------------- | ----------- | ------ | -------------------------- |
| Local machine can't handle 3 nodes | Medium      | High   | Use lightweight config     |
| Docker not installed               | Low         | High   | Include installation steps |
| Network issues with kind           | Low         | Medium | Troubleshooting guide      |

---

## 📂 Project Structure

```
TTG/
├── docs/
│   ├── PROJECT_OVERVIEW.md      # ← You are here
│   └── KUBERNETES_SETUP.md      # Setup instructions
├── docker/
│   └── Dockerfile               # Worker container
├── src/
│   ├── worker.py                # Computation worker
│   └── utils.py                 # Utilities
├── k8s/
│   ├── local/
│   │   ├── kind-config.yaml     # 3-node cluster config
│   │   └── setup-local.sh       # Local setup script
│   ├── azure/
│   │   └── setup-aks.sh         # Azure AKS setup
│   └── manifests/
│       ├── worker-job.yaml      # Single job template
│       └── parallel-jobs.yaml   # Parallel job spec
├── scripts/
│   ├── build.sh                 # Build Docker image
│   ├── deploy.sh                # Deploy to K8s
│   └── cleanup.sh               # Clean up resources
├── requirements.txt             # Python dependencies
└── README.md                    # Quick start
```

---

## 🔜 Next Steps

1. **Read** [KUBERNETES_SETUP.md](./KUBERNETES_SETUP.md) for setup instructions
2. **Choose** Local (kind) or Azure (AKS)
3. **Follow** the step-by-step guide
4. **Run** your first distributed computation!

---

## 📚 Additional Resources

- [Kubernetes Official Docs](https://kubernetes.io/docs/home/)
- [kind Documentation](https://kind.sigs.k8s.io/)
- [Azure AKS Documentation](https://docs.microsoft.com/en-us/azure/aks/)
- [Docker Documentation](https://docs.docker.com/)

---

_Last Updated: 2026-01-26_
_Author: TTG Team_
