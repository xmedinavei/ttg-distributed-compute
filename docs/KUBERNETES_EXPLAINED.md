# Kubernetes Explained: A Complete Guide for Beginners

## For the TTG Distributed Computation Project

*This guide explains Kubernetes concepts from the ground up, specifically in the context of solving the distributed computation problem.*

---

## Table of Contents

1. [What Problem Are We Solving?](#what-problem-are-we-solving)
2. [Why Kubernetes?](#why-kubernetes)
3. [The Container Revolution](#the-container-revolution)
4. [Kubernetes Architecture](#kubernetes-architecture)
5. [Core Concepts Deep Dive](#core-concepts-deep-dive)
6. [How Kubernetes Solves Our Problem](#how-kubernetes-solves-our-problem)
7. [The Complete Picture](#the-complete-picture)
8. [Common Patterns](#common-patterns)
9. [Glossary](#glossary)

---

## What Problem Are We Solving?

### The Original Problem

You have an algorithm that needs to process **10 million parameters**. Each parameter calculation takes some time. Running sequentially:

```
Parameter 1 → compute → result
Parameter 2 → compute → result
Parameter 3 → compute → result
...
Parameter 10,000,000 → compute → result

Total time: 10,000,000 × compute_time = A VERY LONG TIME
```

### The Pizza Factory Analogy 🍕

Let's think of this as a **pizza factory**:

```
YOUR PROBLEM:
┌─────────────────────────────────────────────────────────────────┐
│                                                                 │
│   You need to make 10 MILLION pizzas                           │
│                                                                 │
│   With ONE chef:                                                │
│   👨‍🍳 → 🍕 → 🍕 → 🍕 → ... → 🍕 (10M times)                    │
│   Time: 10 million × 5 minutes = 95 YEARS                      │
│                                                                 │
│   With 1000 chefs:                                              │
│   👨‍🍳👨‍🍳👨‍🍳...👨‍🍳 → 🍕🍕🍕...🍕                                │
│   Each makes 10,000 pizzas                                      │
│   Time: 10,000 × 5 minutes = 35 DAYS                           │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### The Challenge

But managing 1000 chefs is hard:
- Who assigns work to each chef?
- What if a chef gets sick (crashes)?
- What if we need more chefs during rush hour?
- How do we collect all the pizzas at the end?
- How do we ensure chefs don't fight over ingredients (resources)?

**This is exactly what Kubernetes solves!**

---

## Why Kubernetes?

### What is Kubernetes?

**Kubernetes** (K8s) is a **container orchestration platform**. Let's break that down:

- **Container**: A lightweight, isolated package containing your application and all its dependencies
- **Orchestration**: Automatically managing, scheduling, and coordinating many containers
- **Platform**: A system that handles the complex infrastructure work for you

### The Factory Manager Analogy

Think of Kubernetes as the **factory manager** who:

| Task | Without K8s (Manual) | With K8s (Automatic) |
|------|---------------------|---------------------|
| **Assign work** | You tell each worker what to do | K8s schedules work automatically |
| **Handle failures** | You notice and restart manually | K8s detects and restarts automatically |
| **Scale up/down** | You hire/fire workers | K8s adds/removes containers |
| **Balance load** | You manage workload distribution | K8s distributes work evenly |
| **Resource management** | You track who uses what | K8s enforces limits |

### Before and After Kubernetes

```
BEFORE K8s:
┌─────────────────────────────────────────────────────────────────┐
│  You (the developer/operator):                                  │
│                                                                 │
│  • SSH into server1, start worker1                              │
│  • SSH into server2, start worker2                              │
│  • SSH into server3, start worker3                              │
│  • Monitor each one manually                                    │
│  • If one crashes, SSH and restart                              │
│  • If you need more workers, provision more servers             │
│  • Track which worker does which parameters                     │
│                                                                 │
│  😰 Exhausting and error-prone!                                 │
└─────────────────────────────────────────────────────────────────┘

AFTER K8s:
┌─────────────────────────────────────────────────────────────────┐
│  You (the developer/operator):                                  │
│                                                                 │
│  • Write ONE YAML file: "I need 3 workers"                      │
│  • kubectl apply -f workers.yaml                                │
│  • Done! ☕                                                     │
│                                                                 │
│  Kubernetes:                                                    │
│  • Schedules workers on available nodes                         │
│  • Monitors health, restarts failures                           │
│  • Scales up/down on command                                    │
│  • Manages networking between workers                           │
│                                                                 │
│  😎 Let the robots handle it!                                   │
└─────────────────────────────────────────────────────────────────┘
```

---

## The Container Revolution

Before understanding Kubernetes, you need to understand **containers**.

### What is a Container?

A container is like a **shipping container** for software:

```
SHIPPING CONTAINER (Physical):
┌─────────────────────────────────────┐
│  📦 Standard size                   │
│  📦 Contains everything needed      │
│  📦 Works on any ship, truck, train │
│  📦 Isolated from other containers  │
└─────────────────────────────────────┘

SOFTWARE CONTAINER (Docker):
┌─────────────────────────────────────┐
│  🐳 Standard format                 │
│  🐳 Contains app + dependencies     │
│  🐳 Works on any Linux/Mac/Windows  │
│  🐳 Isolated from other containers  │
└─────────────────────────────────────┘
```

### Container vs Virtual Machine

```
VIRTUAL MACHINE:
┌─────────────────────────────────────────────────────┐
│  Your App                                           │
├─────────────────────────────────────────────────────┤
│  Guest OS (Ubuntu, Windows, etc.) - FULL OS!        │
│  ~2-10 GB, boots in minutes                         │
├─────────────────────────────────────────────────────┤
│  Hypervisor (VMware, VirtualBox)                    │
├─────────────────────────────────────────────────────┤
│  Host OS                                            │
├─────────────────────────────────────────────────────┤
│  Hardware                                           │
└─────────────────────────────────────────────────────┘

CONTAINER:
┌─────────────────────────────────────────────────────┐
│  Your App                                           │
├─────────────────────────────────────────────────────┤
│  Container Runtime (Docker) - LIGHTWEIGHT!          │
│  ~100 MB, starts in seconds                         │
├─────────────────────────────────────────────────────┤
│  Host OS (shares kernel)                            │
├─────────────────────────────────────────────────────┤
│  Hardware                                           │
└─────────────────────────────────────────────────────┘
```

### Why Containers Matter for Our Project

For our distributed computation:

| Aspect | Without Containers | With Containers |
|--------|-------------------|-----------------|
| **Dependency hell** | "Works on my machine" | Same image everywhere |
| **Deployment** | Install Python, libs, configure | `docker run worker` |
| **Isolation** | Workers might interfere | Each worker is isolated |
| **Scaling** | Install on each new server | Same image, just run more |
| **Consistency** | Dev ≠ Staging ≠ Production | Identical everywhere |

---

## Kubernetes Architecture

### The Big Picture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         KUBERNETES CLUSTER                              │
│                                                                         │
│  ┌───────────────────────────────────────────────────────────────────┐ │
│  │                      CONTROL PLANE                                 │ │
│  │  (The Brain - Makes decisions)                                     │ │
│  │                                                                     │ │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐                │ │
│  │  │ API Server  │  │ Scheduler   │  │ Controller  │                │ │
│  │  │             │  │             │  │ Manager     │                │ │
│  │  │ Entry point │  │ Assigns pods│  │ Maintains   │                │ │
│  │  │ for all     │  │ to nodes    │  │ desired     │                │ │
│  │  │ commands    │  │             │  │ state       │                │ │
│  │  └─────────────┘  └─────────────┘  └─────────────┘                │ │
│  │                                                                     │ │
│  │  ┌─────────────────────────────────────────────────────────────┐  │ │
│  │  │                         etcd                                 │  │ │
│  │  │  (The Memory - Stores all cluster data)                      │  │ │
│  │  └─────────────────────────────────────────────────────────────┘  │ │
│  └───────────────────────────────────────────────────────────────────┘ │
│                                    │                                    │
│                                    │ Communicates                       │
│                                    ▼                                    │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐     │
│  │   WORKER NODE 1  │  │   WORKER NODE 2  │  │   WORKER NODE 3  │     │
│  │  (The Hands)     │  │  (The Hands)     │  │  (The Hands)     │     │
│  │                  │  │                  │  │                  │     │
│  │  ┌────────────┐  │  │  ┌────────────┐  │  │  ┌────────────┐  │     │
│  │  │   kubelet  │  │  │  │   kubelet  │  │  │  │   kubelet  │  │     │
│  │  │  (Agent)   │  │  │  │  (Agent)   │  │  │  │  (Agent)   │  │     │
│  │  └────────────┘  │  │  └────────────┘  │  │  └────────────┘  │     │
│  │                  │  │                  │  │                  │     │
│  │  ┌────┐ ┌────┐   │  │  ┌────┐ ┌────┐   │  │  ┌────┐ ┌────┐   │     │
│  │  │Pod │ │Pod │   │  │  │Pod │ │Pod │   │  │  │Pod │ │Pod │   │     │
│  │  └────┘ └────┘   │  │  └────┘ └────┘   │  │  └────┘ └────┘   │     │
│  └──────────────────┘  └──────────────────┘  └──────────────────┘     │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### Component Breakdown

#### Control Plane Components

| Component | Role | Pizza Factory Analogy |
|-----------|------|----------------------|
| **API Server** | Entry point for all commands | Reception desk - all orders come here |
| **Scheduler** | Decides which node runs which pod | Manager who assigns chefs to stations |
| **Controller Manager** | Ensures desired state is maintained | Quality control - ensures 3 chefs are always working |
| **etcd** | Stores all cluster data | Filing cabinet with all records |

#### Worker Node Components

| Component | Role | Pizza Factory Analogy |
|-----------|------|----------------------|
| **kubelet** | Agent on each node, manages pods | Supervisor at each station |
| **Container Runtime** | Runs containers (Docker) | The actual kitchen equipment |
| **kube-proxy** | Handles networking | Internal phone system |

---

## Core Concepts Deep Dive

### 1. Pod 🫛

**The smallest deployable unit in Kubernetes.**

A Pod is a wrapper around one or more containers that:
- Share the same network namespace (same IP)
- Share storage volumes
- Are scheduled together on the same node

```
┌────────────────────────────────────────┐
│                 POD                     │
│  ┌──────────────────────────────────┐  │
│  │         CONTAINER                │  │
│  │   ┌──────────────────────────┐   │  │
│  │   │   Your Python Worker     │   │  │
│  │   │   (processes params)     │   │  │
│  │   └──────────────────────────┘   │  │
│  └──────────────────────────────────┘  │
│                                        │
│  Network: 10.1.0.5                     │
│  Volumes: /data (shared)               │
└────────────────────────────────────────┘
```

**For Our Project:**
- Each worker runs in its own Pod
- Pod gets environment variables (WORKER_ID, TOTAL_PARAMETERS)
- Pod is scheduled to a Node by the Scheduler

**YAML Example:**
```yaml
apiVersion: v1
kind: Pod
metadata:
  name: worker-pod
spec:
  containers:
    - name: worker
      image: ttg-worker:latest
      env:
        - name: WORKER_ID
          value: "0"
```

---

### 2. Node 🖥️

**A machine (physical or virtual) in the cluster.**

```
┌──────────────────────────────────────────────────────────────┐
│                         NODE                                  │
│  Machine: 4 CPU, 16GB RAM, 100GB Disk                        │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  Kubelet (Agent)                                     │   │
│  │  - Receives instructions from Control Plane          │   │
│  │  - Manages pods on this node                         │   │
│  │  - Reports health status                             │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                              │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐            │
│  │   Pod 1    │  │   Pod 2    │  │   Pod 3    │            │
│  │ (Worker 0) │  │ (App X)    │  │ (App Y)    │            │
│  │ CPU: 0.5   │  │ CPU: 1     │  │ CPU: 0.5   │            │
│  │ RAM: 256MB │  │ RAM: 1GB   │  │ RAM: 512MB │            │
│  └────────────┘  └────────────┘  └────────────┘            │
│                                                              │
│  Available: 2 CPU, 13.75GB RAM                              │
└──────────────────────────────────────────────────────────────┘
```

**Types of Nodes:**
- **Control Plane Node**: Runs the brain components (API server, scheduler, etc.)
- **Worker Node**: Runs your application pods

**For Our Project:**
- We have 3 worker nodes
- Each runs one of our computation workers
- Scheduler distributes pods across nodes for parallel processing

---

### 3. Job 📋

**Creates Pods that run to completion.**

Unlike Deployments (which keep pods running forever), Jobs are for **batch workloads**:
- Run once, then finish
- Can run in parallel
- Track successful completions

```
┌─────────────────────────────────────────────────────────────┐
│                          JOB                                 │
│  Name: ttg-computation                                       │
│  Completions: 3 (need 3 successful completions)              │
│  Parallelism: 3 (run 3 at once)                              │
│                                                              │
│  Status:                                                     │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐                   │
│  │  Pod 0   │  │  Pod 1   │  │  Pod 2   │                   │
│  │ ✅ Done  │  │ 🔄 Run   │  │ ✅ Done  │                   │
│  └──────────┘  └──────────┘  └──────────┘                   │
│                                                              │
│  Completions: 2/3                                            │
└─────────────────────────────────────────────────────────────┘
```

**For Our Project:**
- We use an **Indexed Job** where each pod gets a unique index (0, 1, 2)
- This index becomes the WORKER_ID
- Each worker processes parameters: `start = index * (total / workers)`

**YAML Example:**
```yaml
apiVersion: batch/v1
kind: Job
metadata:
  name: ttg-computation
spec:
  completions: 3        # Total completions needed
  parallelism: 3        # Run in parallel
  completionMode: Indexed  # Each pod gets unique index
  template:
    spec:
      containers:
        - name: worker
          image: ttg-worker:latest
          env:
            - name: WORKER_ID
              valueFrom:
                fieldRef:
                  fieldPath: metadata.annotations['batch.kubernetes.io/job-completion-index']
```

---

### 4. Deployment 🚀

**Manages long-running applications.**

Deployments ensure a specified number of pod replicas are always running:
- If a pod crashes, Deployment creates a new one
- Supports rolling updates
- Supports rollbacks

```
┌─────────────────────────────────────────────────────────────┐
│                      DEPLOYMENT                              │
│  Name: web-server                                            │
│  Replicas: 3 (always keep 3 running)                         │
│                                                              │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐                   │
│  │  Pod 1   │  │  Pod 2   │  │  Pod 3   │                   │
│  │ 🟢 Run   │  │ 🟢 Run   │  │ 🟢 Run   │                   │
│  └──────────┘  └──────────┘  └──────────┘                   │
│                                                              │
│  If Pod 2 crashes:                                           │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐                   │
│  │  Pod 1   │  │  Pod 2   │  │  Pod 4   │ ← Auto-created    │
│  │ 🟢 Run   │  │ 💀 Dead  │  │ 🟢 Run   │                   │
│  └──────────┘  └──────────┘  └──────────┘                   │
└─────────────────────────────────────────────────────────────┘
```

**For Our Project:**
- We use **Jobs** (not Deployments) because our workers run to completion
- In future phases, we might use Deployments for:
  - Long-running queue workers
  - API servers
  - Monitoring services

---

### 5. Service 🌐

**Provides stable networking for Pods.**

Pods have ephemeral IPs (change when pod restarts). Services provide:
- Stable IP/DNS name
- Load balancing across pods
- Service discovery

```
┌─────────────────────────────────────────────────────────────┐
│                       SERVICE                                │
│  Name: my-service                                            │
│  IP: 10.96.0.100 (stable)                                   │
│  DNS: my-service.default.svc.cluster.local                   │
│                                                              │
│                    ▼ Load Balance ▼                          │
│                                                              │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐                   │
│  │  Pod 1   │  │  Pod 2   │  │  Pod 3   │                   │
│  │ 10.1.0.5 │  │ 10.1.0.6 │  │ 10.1.0.7 │  (ephemeral IPs) │
│  └──────────┘  └──────────┘  └──────────┘                   │
└─────────────────────────────────────────────────────────────┘
```

**For Our Project:**
- First milestone doesn't need Services (workers don't talk to each other)
- Future: Services for queue workers to connect to message broker

---

### 6. ConfigMap & Secret 🔧🔐

**External configuration for your applications.**

```
ConfigMap (non-sensitive):                Secret (sensitive):
┌────────────────────────┐                ┌────────────────────────┐
│ TOTAL_PARAMETERS=10M   │                │ DB_PASSWORD=***        │
│ BATCH_SIZE=1000        │                │ API_KEY=***            │
│ LOG_LEVEL=INFO         │                │ TLS_CERT=***           │
└────────────────────────┘                └────────────────────────┘
```

**For Our Project:**
- ConfigMaps store: TOTAL_PARAMETERS, BATCH_SIZE, SIMULATE_WORK_MS
- Secrets would store: API keys, database passwords (when needed)

---

### 7. Namespace 📁

**Virtual cluster within a cluster.**

Namespaces provide:
- Logical separation of resources
- Access control boundaries
- Resource quota boundaries

```
┌─────────────────────────────────────────────────────────────┐
│                     KUBERNETES CLUSTER                       │
│                                                              │
│  ┌──────────────────┐  ┌──────────────────┐                 │
│  │ Namespace: dev   │  │ Namespace: prod  │                 │
│  │                  │  │                  │                 │
│  │  - Pod: worker-0 │  │  - Pod: worker-0 │                 │
│  │  - Pod: worker-1 │  │  - Pod: worker-1 │                 │
│  │  - Service: api  │  │  - Pod: worker-2 │                 │
│  │                  │  │  - Service: api  │                 │
│  └──────────────────┘  └──────────────────┘                 │
│                                                              │
│  Same names, different namespaces = no conflict!            │
└─────────────────────────────────────────────────────────────┘
```

**For Our Project:**
- We use `default` namespace for simplicity
- Production might use separate namespaces for isolation

---

### 8. Resource Requests & Limits 📊

**Controls how much CPU/memory a container can use.**

```yaml
resources:
  requests:      # Minimum guaranteed resources
    cpu: "100m"  # 0.1 CPU cores
    memory: "128Mi"
  limits:        # Maximum allowed resources
    cpu: "500m"  # 0.5 CPU cores
    memory: "256Mi"
```

**Why This Matters (The Sandbox Reason):**

```
WITHOUT LIMITS:
┌─────────────────────────────────────────────────────────────┐
│  Node: 4 CPU cores, 16GB RAM                                │
│                                                              │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  Your Worker                                         │   │
│  │  CPU: 100% (4 cores) 😱                              │   │
│  │  RAM: 14GB 😱                                        │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                              │
│  ┌──────┐                                                   │
│  │ App  │ STARVED! Can't get resources → CRASH!            │
│  └──────┘                                                   │
└─────────────────────────────────────────────────────────────┘

WITH LIMITS:
┌─────────────────────────────────────────────────────────────┐
│  Node: 4 CPU cores, 16GB RAM                                │
│                                                              │
│  ┌─────────────────┐  ┌─────────────────┐                   │
│  │  Your Worker    │  │  Other Apps     │                   │
│  │  CPU: 0.5 max   │  │  CPU: 3.5 avail │                   │
│  │  RAM: 256MB max │  │  RAM: 15GB avail│                   │
│  └─────────────────┘  └─────────────────┘                   │
│                                                              │
│  Everyone gets their fair share! ✅                          │
└─────────────────────────────────────────────────────────────┘
```

---

## How Kubernetes Solves Our Problem

### The Complete Flow

```
┌─────────────────────────────────────────────────────────────────────────┐
│  STEP 1: You submit a Job                                               │
│                                                                         │
│  $ kubectl apply -f parallel-jobs.yaml                                  │
│  "I need 3 workers to process 10M parameters"                           │
│                                                                         │
└───────────────────────────────────────┬─────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  STEP 2: API Server receives the request                                │
│                                                                         │
│  API Server: "Got it! Creating Job object in etcd"                      │
│  etcd: Stores Job specification                                         │
│                                                                         │
└───────────────────────────────────────┬─────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  STEP 3: Job Controller creates Pods                                    │
│                                                                         │
│  Controller: "Job needs 3 completions with parallelism 3"               │
│  Controller: "Creating Pod-0, Pod-1, Pod-2"                             │
│  Each pod gets: JOB_COMPLETION_INDEX (0, 1, 2)                          │
│                                                                         │
└───────────────────────────────────────┬─────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  STEP 4: Scheduler assigns Pods to Nodes                                │
│                                                                         │
│  Scheduler: "Pod-0 → Node-1 (has resources)"                            │
│  Scheduler: "Pod-1 → Node-2 (has resources)"                            │
│  Scheduler: "Pod-2 → Node-3 (has resources)"                            │
│                                                                         │
│  (Anti-affinity rule tries to spread across nodes)                      │
│                                                                         │
└───────────────────────────────────────┬─────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  STEP 5: Kubelets start containers                                      │
│                                                                         │
│  Node-1 kubelet: "Starting ttg-worker container for Pod-0"              │
│  Node-2 kubelet: "Starting ttg-worker container for Pod-1"              │
│  Node-3 kubelet: "Starting ttg-worker container for Pod-2"              │
│                                                                         │
│  Each container gets environment variables:                             │
│  - WORKER_ID = JOB_COMPLETION_INDEX                                     │
│  - TOTAL_WORKERS = 3                                                    │
│  - TOTAL_PARAMETERS = 10000000                                          │
│                                                                         │
└───────────────────────────────────────┬─────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  STEP 6: Workers compute in parallel                                    │
│                                                                         │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐         │
│  │   WORKER 0      │  │   WORKER 1      │  │   WORKER 2      │         │
│  │   Node-1        │  │   Node-2        │  │   Node-3        │         │
│  │                 │  │                 │  │                 │         │
│  │ range: 0-3.3M   │  │ range: 3.3M-6.6M│  │ range: 6.6M-10M │         │
│  │ 🔄 Computing... │  │ 🔄 Computing... │  │ 🔄 Computing... │         │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘         │
│                                                                         │
│                    All running SIMULTANEOUSLY!                          │
│                                                                         │
└───────────────────────────────────────┬─────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  STEP 7: Workers complete, Job tracks progress                          │
│                                                                         │
│  Pod-0: Exit 0 (success) ✅                                             │
│  Pod-2: Exit 0 (success) ✅                                             │
│  Pod-1: Exit 0 (success) ✅                                             │
│                                                                         │
│  Job Status: 3/3 completions - SUCCEEDED                                │
│                                                                         │
└───────────────────────────────────────┬─────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  STEP 8: You collect results                                            │
│                                                                         │
│  $ kubectl logs -l job-name=ttg-computation --all-containers            │
│                                                                         │
│  [WORKER 0] Processed: 3,333,334 parameters                             │
│  [WORKER 1] Processed: 3,333,333 parameters                             │
│  [WORKER 2] Processed: 3,333,333 parameters                             │
│                                                                         │
│  Total: 10,000,000 parameters ✅                                        │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### Time Comparison

```
SEQUENTIAL (1 worker):
10M params × 1ms/param = 10,000 seconds ≈ 2.8 hours

PARALLEL (3 workers):
3.3M params × 1ms/param = 3,333 seconds ≈ 55 minutes
Speedup: ~3x

PARALLEL (100 workers):
100K params × 1ms/param = 100 seconds ≈ 1.7 minutes
Speedup: ~100x

PARALLEL (1000 workers):
10K params × 1ms/param = 10 seconds
Speedup: ~1000x
```

---

## The Complete Picture

### How Everything Connects

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        YOUR LAPTOP/WORKSTATION                          │
│  ┌───────────────────────────────────────────────────────────────────┐ │
│  │  Terminal: kubectl apply -f parallel-jobs.yaml                    │ │
│  └───────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────┬───────────────────────────────┘
                                          │
                                          │ HTTPS (via kubectl)
                                          ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                        KUBERNETES CLUSTER                               │
│                                                                         │
│  ┌─────────────────────── CONTROL PLANE ───────────────────────────┐   │
│  │                                                                   │   │
│  │   ┌─────────────┐      ┌─────────────┐      ┌─────────────┐    │   │
│  │   │ API Server  │◄────►│  Scheduler  │◄────►│ Controller  │    │   │
│  │   │             │      │             │      │ Manager     │    │   │
│  │   └──────┬──────┘      └─────────────┘      └─────────────┘    │   │
│  │          │                                                       │   │
│  │          ▼                                                       │   │
│  │   ┌─────────────────────────────────────────────────────────┐  │   │
│  │   │                        etcd                              │  │   │
│  │   │  Job: ttg-computation (completions: 3, parallelism: 3)  │  │   │
│  │   │  Pod-0: running on node-1                                │  │   │
│  │   │  Pod-1: running on node-2                                │  │   │
│  │   │  Pod-2: running on node-3                                │  │   │
│  │   └─────────────────────────────────────────────────────────┘  │   │
│  │                                                                   │   │
│  └───────────────────────────────────────────────────────────────────┘   │
│                                          │                              │
│              ┌───────────────────────────┼───────────────────────────┐  │
│              │                           │                           │  │
│              ▼                           ▼                           ▼  │
│  ┌─────────────────────┐   ┌─────────────────────┐   ┌─────────────────────┐
│  │    WORKER NODE 1    │   │    WORKER NODE 2    │   │    WORKER NODE 3    │
│  │                     │   │                     │   │                     │
│  │  ┌───────────────┐  │   │  ┌───────────────┐  │   │  ┌───────────────┐  │
│  │  │    kubelet    │  │   │  │    kubelet    │  │   │  │    kubelet    │  │
│  │  └───────┬───────┘  │   │  └───────┬───────┘  │   │  └───────┬───────┘  │
│  │          │          │   │          │          │   │          │          │
│  │          ▼          │   │          ▼          │   │          ▼          │
│  │  ┌───────────────┐  │   │  ┌───────────────┐  │   │  ┌───────────────┐  │
│  │  │     Docker    │  │   │  │     Docker    │  │   │  │     Docker    │  │
│  │  │    Runtime    │  │   │  │    Runtime    │  │   │  │    Runtime    │  │
│  │  └───────┬───────┘  │   │  └───────┬───────┘  │   │  └───────┬───────┘  │
│  │          │          │   │          │          │   │          │          │
│  │          ▼          │   │          ▼          │   │          ▼          │
│  │  ┌───────────────┐  │   │  ┌───────────────┐  │   │  ┌───────────────┐  │
│  │  │   CONTAINER   │  │   │  │   CONTAINER   │  │   │  │   CONTAINER   │  │
│  │  │  ttg-worker   │  │   │  │  ttg-worker   │  │   │  │  ttg-worker   │  │
│  │  │               │  │   │  │               │  │   │  │               │  │
│  │  │ WORKER_ID=0   │  │   │  │ WORKER_ID=1   │  │   │  │ WORKER_ID=2   │  │
│  │  │ Params: 0-3M  │  │   │  │ Params: 3M-6M │  │   │  │ Params: 6M-10M│  │
│  │  │               │  │   │  │               │  │   │  │               │  │
│  │  │ 🔄 Computing  │  │   │  │ 🔄 Computing  │  │   │  │ 🔄 Computing  │  │
│  │  └───────────────┘  │   │  └───────────────┘  │   │  └───────────────┘  │
│  │                     │   │                     │   │                     │
│  │  CPU: 0.5 / 4 cores │   │  CPU: 0.5 / 4 cores │   │  CPU: 0.5 / 4 cores │
│  │  RAM: 256MB / 16GB  │   │  RAM: 256MB / 16GB  │   │  RAM: 256MB / 16GB  │
│  └─────────────────────┘   └─────────────────────┘   └─────────────────────┘
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Common Patterns

### Pattern 1: Indexed Job (What We Use)

Best for: Work that can be divided by index/range

```
Job with completionMode: Indexed
├── Pod-0 (index 0) → processes params 0 to N/3
├── Pod-1 (index 1) → processes params N/3 to 2N/3
└── Pod-2 (index 2) → processes params 2N/3 to N
```

### Pattern 2: Queue-based Workers (Future)

Best for: Dynamic workloads, varying task sizes

```
┌────────────┐      ┌─────────────┐      ┌────────────┐
│ Coordinator│─────►│ Task Queue  │◄─────│  Workers   │
│            │      │             │      │ (pull work)│
└────────────┘      └─────────────┘      └────────────┘
```

### Pattern 3: Leader-Worker

Best for: Coordination-heavy workloads

```
┌─────────────────────────────────┐
│           LEADER POD            │
│  - Assigns work                 │
│  - Aggregates results           │
└───────────────┬─────────────────┘
                │
    ┌───────────┼───────────┐
    ▼           ▼           ▼
┌────────┐ ┌────────┐ ┌────────┐
│Worker 1│ │Worker 2│ │Worker 3│
└────────┘ └────────┘ └────────┘
```

---

## Glossary

| Term | Definition |
|------|------------|
| **Cluster** | A set of machines (nodes) running Kubernetes |
| **Node** | A single machine in the cluster |
| **Pod** | Smallest deployable unit; wrapper for containers |
| **Container** | Isolated process running your application |
| **Job** | Creates pods that run to completion |
| **Deployment** | Manages long-running pods with auto-healing |
| **Service** | Stable network endpoint for pods |
| **ConfigMap** | Stores non-sensitive configuration |
| **Secret** | Stores sensitive configuration (encrypted) |
| **Namespace** | Virtual cluster for resource isolation |
| **kubelet** | Agent on each node that manages pods |
| **kubectl** | CLI tool to interact with Kubernetes |
| **API Server** | Entry point for all cluster commands |
| **Scheduler** | Assigns pods to nodes |
| **etcd** | Distributed key-value store for cluster state |
| **Control Plane** | Components that manage the cluster |
| **Resource Request** | Minimum resources guaranteed for a pod |
| **Resource Limit** | Maximum resources allowed for a pod |
| **Affinity** | Rules for pod placement preferences |

---

## Next Steps

Now that you understand the concepts:

1. **Set up your cluster**: See [KUBERNETES_SETUP.md](./KUBERNETES_SETUP.md)
2. **Deploy workers**: Follow the Quick Start in [README.md](../README.md)
3. **Configure scaling**: See [CONFIGURATION_GUIDE.md](./CONFIGURATION_GUIDE.md)
4. **Try Azure**: See [AZURE_AKS_GUIDE.md](./AZURE_AKS_GUIDE.md)

---

*Last Updated: 2026-01-26*
*Document: KUBERNETES_EXPLAINED.md*
