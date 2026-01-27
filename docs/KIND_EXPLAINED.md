# Kind Explained: Kubernetes IN Docker

## A Comprehensive Guide for TTG Distributed Computation

_Your complete reference for understanding and working with kind_

---

## Table of Contents

1. [What is Kind?](#what-is-kind)
2. [How Kind Works](#how-kind-works)
3. [Kind vs Other Options](#kind-vs-other-options)
4. [Installation](#installation)
5. [Essential Commands](#essential-commands)
6. [Cluster Configuration](#cluster-configuration)
7. [Working with Images](#working-with-images)
8. [Networking](#networking)
9. [Troubleshooting](#troubleshooting)
10. [Best Practices](#best-practices)

---

## What is Kind?

**Kind** stands for **K**ubernetes **IN** **D**ocker. It's a tool for running local Kubernetes clusters using Docker containers as "nodes".

### The Big Picture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           YOUR COMPUTER                                     │
│                                                                             │
│  ┌───────────────────────────────────────────────────────────────────────┐ │
│  │                         DOCKER ENGINE                                  │ │
│  │                                                                        │ │
│  │  ┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐          │ │
│  │  │   CONTAINER     │ │   CONTAINER     │ │   CONTAINER     │          │ │
│  │  │  (K8s Node)     │ │  (K8s Node)     │ │  (K8s Node)     │          │ │
│  │  │                 │ │                 │ │                 │          │ │
│  │  │ ttg-cluster-    │ │ ttg-cluster-    │ │ ttg-cluster-    │          │ │
│  │  │ control-plane   │ │ worker          │ │ worker2         │          │ │
│  │  │                 │ │                 │ │                 │          │ │
│  │  │ ┌─────────────┐ │ │ ┌─────────────┐ │ │ ┌─────────────┐ │          │ │
│  │  │ │ kubelet     │ │ │ │ kubelet     │ │ │ │ kubelet     │ │          │ │
│  │  │ │ containerd  │ │ │ │ containerd  │ │ │ │ containerd  │ │          │ │
│  │  │ │ kube-proxy  │ │ │ │ kube-proxy  │ │ │ │ kube-proxy  │ │          │ │
│  │  │ └─────────────┘ │ │ └─────────────┘ │ │ └─────────────┘ │          │ │
│  │  │                 │ │                 │ │                 │          │ │
│  │  │  Running YOUR   │ │  Running YOUR   │ │  Running YOUR   │          │ │
│  │  │  worker pods!   │ │  worker pods!   │ │  worker pods!   │          │ │
│  │  └─────────────────┘ └─────────────────┘ └─────────────────┘          │ │
│  │                                                                        │ │
│  └───────────────────────────────────────────────────────────────────────┘ │
│                                                                             │
│  kubectl ──────────────────────────────────────────────────────────────►   │
│  (commands go to the control-plane container)                               │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Key Insight

> **Kind creates Kubernetes nodes as Docker containers.**
>
> Inside each container, there's another container runtime (containerd) that runs your actual application pods. It's containers running containers!

### Why This Matters

| Concept     | Traditional K8s           | Kind                    |
| ----------- | ------------------------- | ----------------------- |
| Nodes       | Physical/Virtual Machines | Docker Containers       |
| Setup Time  | Hours to Days             | 30 Seconds              |
| Resources   | Many GB RAM per node      | Shared Docker resources |
| Network     | Real network              | Docker network          |
| Persistence | Disk                      | Container volumes       |

---

## How Kind Works

### Architecture Deep Dive

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         KIND ARCHITECTURE                                   │
│                                                                             │
│    ┌──────────────────────────────────────────────────────────────┐        │
│    │                    kind CLI Tool                              │        │
│    │  • Creates cluster configurations                             │        │
│    │  • Manages cluster lifecycle                                  │        │
│    │  • Loads images into clusters                                 │        │
│    └──────────────────────────────────────────────────────────────┘        │
│                               │                                             │
│                               ▼                                             │
│    ┌──────────────────────────────────────────────────────────────┐        │
│    │                    Docker Engine                              │        │
│    │  • Runs node containers                                       │        │
│    │  • Provides networking                                        │        │
│    │  • Manages volumes                                            │        │
│    └──────────────────────────────────────────────────────────────┘        │
│                               │                                             │
│           ┌───────────────────┼───────────────────┐                        │
│           ▼                   ▼                   ▼                        │
│    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐                   │
│    │ control-    │    │ worker      │    │ worker      │                   │
│    │ plane       │    │             │    │             │                   │
│    │             │    │             │    │             │                   │
│    │ ┌─────────┐ │    │ ┌─────────┐ │    │ ┌─────────┐ │                   │
│    │ │API      │ │    │ │         │ │    │ │         │ │                   │
│    │ │Server   │ │    │ │kubelet  │ │    │ │kubelet  │ │                   │
│    │ └─────────┘ │    │ │         │ │    │ │         │ │                   │
│    │ ┌─────────┐ │    │ └─────────┘ │    │ └─────────┘ │                   │
│    │ │Scheduler│ │    │ ┌─────────┐ │    │ ┌─────────┐ │                   │
│    │ └─────────┘ │    │ │contain- │ │    │ │contain- │ │                   │
│    │ ┌─────────┐ │    │ │erd      │ │    │ │erd      │ │                   │
│    │ │Control  │ │    │ └─────────┘ │    │ └─────────┘ │                   │
│    │ │Manager  │ │    │      │      │    │      │      │                   │
│    │ └─────────┘ │    │      ▼      │    │      ▼      │                   │
│    │ ┌─────────┐ │    │ ┌─────────┐ │    │ ┌─────────┐ │                   │
│    │ │etcd     │ │    │ │Your Pods│ │    │ │Your Pods│ │                   │
│    │ └─────────┘ │    │ └─────────┘ │    │ └─────────┘ │                   │
│    └─────────────┘    └─────────────┘    └─────────────┘                   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Container Layers Explained

```
Your TTG Worker Pod
         │
         ▼
    ┌─────────────────────────────────────┐
    │    containerd (inside kind node)    │  ◄── Runs your pods
    └─────────────────────────────────────┘
         │
         ▼
    ┌─────────────────────────────────────┐
    │    Docker Container (kind node)     │  ◄── The "node"
    └─────────────────────────────────────┘
         │
         ▼
    ┌─────────────────────────────────────┐
    │    Docker Engine (your machine)     │  ◄── Your Docker
    └─────────────────────────────────────┘
         │
         ▼
    ┌─────────────────────────────────────┐
    │    Linux Kernel                     │  ◄── Your OS
    └─────────────────────────────────────┘
```

### The Image Loading Process

When you run `kind load docker-image`:

```
1. Your Local Docker
   ┌─────────────────────┐
   │ ttg-worker:latest   │
   └─────────────────────┘
            │
            │  docker save (export as tar)
            ▼
2. Kind Node Container
   ┌─────────────────────────────────────┐
   │ ttg-cluster-worker                  │
   │                                     │
   │  ctr (containerd CLI) imports image │
   │                                     │
   │  ┌─────────────────────┐            │
   │  │ ttg-worker:latest   │ ◄── Now    │
   │  └─────────────────────┘    available│
   │                              inside  │
   └─────────────────────────────────────┘
```

---

## Kind vs Other Options

### Comparison Table

| Feature                 | Kind   | Minikube   | k3d    | Docker Desktop K8s |
| ----------------------- | ------ | ---------- | ------ | ------------------ |
| **Multi-node**          | ✅ Yes | ⚠️ Limited | ✅ Yes | ❌ No              |
| **Resource Usage**      | Low    | Medium     | Low    | High               |
| **Speed**               | Fast   | Slow       | Fast   | Medium             |
| **CI/CD Friendly**      | ✅ Yes | ❌ No      | ✅ Yes | ❌ No              |
| **Complexity**          | Low    | Medium     | Low    | Low                |
| **K8s Version Control** | ✅ Yes | ✅ Yes     | ✅ Yes | ❌ No              |
| **Windows/Mac/Linux**   | ✅ All | ✅ All     | ✅ All | ⚠️ Desktop only    |

### When to Use Kind

**Use Kind when:**

- ✅ You need multi-node clusters locally
- ✅ You're running CI/CD pipelines
- ✅ You want to test K8s features (like node affinity)
- ✅ You need to test against specific K8s versions
- ✅ You want fast cluster creation/deletion

**Consider alternatives when:**

- ⚠️ You need persistent storage that survives deletes → Use a cloud provider
- ⚠️ You need to expose services externally easily → Use Docker Desktop K8s
- ⚠️ You're new to K8s and want simplest setup → Use Docker Desktop K8s

---

## Installation

### Prerequisites

1. **Docker** (must be running)

   ```bash
   docker version
   ```

2. **kubectl** (Kubernetes CLI)
   ```bash
   kubectl version --client
   ```

### Install Kind

**Linux/Mac:**

```bash
# Download
curl -Lo ./kind https://kind.sigs.k8s.io/dl/v0.20.0/kind-linux-amd64

# Make executable
chmod +x ./kind

# Move to PATH
sudo mv ./kind /usr/local/bin/kind

# Verify
kind version
```

**Mac with Homebrew:**

```bash
brew install kind
```

**Windows:**

```powershell
choco install kind
# or
winget install Kubernetes.kind
```

### Verify Installation

```bash
# Check kind
kind version
# Output: kind v0.20.0 go1.20.4 linux/amd64

# Check Docker is running
docker ps

# Check kubectl
kubectl version --client
```

---

## Essential Commands

### Quick Reference Card

```bash
# ═══════════════════════════════════════════════════════════════
# CLUSTER MANAGEMENT
# ═══════════════════════════════════════════════════════════════

# Create a simple cluster
kind create cluster

# Create cluster with specific name
kind create cluster --name my-cluster

# Create cluster from config file
kind create cluster --config kind-config.yaml --name ttg-cluster

# List all clusters
kind get clusters

# Delete a cluster
kind delete cluster --name ttg-cluster

# Delete all clusters
kind delete clusters --all

# ═══════════════════════════════════════════════════════════════
# IMAGE MANAGEMENT
# ═══════════════════════════════════════════════════════════════

# Load a local image into cluster
kind load docker-image myimage:tag --name ttg-cluster

# Load multiple images
kind load docker-image img1:v1 img2:v2 --name ttg-cluster

# ═══════════════════════════════════════════════════════════════
# CLUSTER INFO
# ═══════════════════════════════════════════════════════════════

# Get cluster nodes (as Docker containers)
docker ps --filter "name=ttg-cluster"

# Get kubeconfig
kind get kubeconfig --name ttg-cluster

# Export kubeconfig to file
kind get kubeconfig --name ttg-cluster > kubeconfig.yaml

# ═══════════════════════════════════════════════════════════════
# DEBUGGING
# ═══════════════════════════════════════════════════════════════

# Exec into a node container
docker exec -it ttg-cluster-control-plane bash

# Check logs of a node
docker logs ttg-cluster-worker

# Check containerd images inside node
docker exec ttg-cluster-worker crictl images
```

### Command Cheat Sheet

| Task                   | Command                                       |
| ---------------------- | --------------------------------------------- |
| Create default cluster | `kind create cluster`                         |
| Create named cluster   | `kind create cluster --name NAME`             |
| Create from config     | `kind create cluster --config FILE`           |
| List clusters          | `kind get clusters`                           |
| Delete cluster         | `kind delete cluster --name NAME`             |
| Load image             | `kind load docker-image IMAGE --name CLUSTER` |
| Get kubeconfig         | `kind get kubeconfig --name NAME`             |
| Cluster info           | `kubectl cluster-info --context kind-NAME`    |

---

## Cluster Configuration

### Our TTG Cluster Config Explained

```yaml
# k8s/local/kind-config.yaml
kind: Cluster
apiVersion: kind.x-k8s.io/v1alpha4

# ─────────────────────────────────────────────────────────────
# NODES CONFIGURATION
# ─────────────────────────────────────────────────────────────
nodes:
  # The control-plane runs Kubernetes management components
  - role: control-plane
    # Optional: Pin to specific K8s version
    # image: kindest/node:v1.27.3

  # Worker nodes run your actual workloads
  - role: worker
    labels:
      ttg.io/node-type: compute # Custom label for targeting

  - role: worker
    labels:
      ttg.io/node-type: compute

  - role: worker
    labels:
      ttg.io/node-type: compute

# ─────────────────────────────────────────────────────────────
# NETWORKING (optional)
# ─────────────────────────────────────────────────────────────
networking:
  # Pod subnet (default is fine for most cases)
  podSubnet: "10.244.0.0/16"
  # Service subnet
  serviceSubnet: "10.96.0.0/12"
```

### Config Options Explained

```yaml
# EXAMPLE: Advanced Configuration
kind: Cluster
apiVersion: kind.x-k8s.io/v1alpha4

nodes:
  - role: control-plane
    # ──────────────────────────────────────────────────────────
    # EXTRA PORT MAPPINGS
    # Map ports from node to host (like docker -p)
    # ──────────────────────────────────────────────────────────
    extraPortMappings:
      # Expose NodePort service on host
      - containerPort: 30000
        hostPort: 30000
        protocol: TCP

    # ──────────────────────────────────────────────────────────
    # EXTRA MOUNTS
    # Mount host directories into node
    # ──────────────────────────────────────────────────────────
    extraMounts:
      - hostPath: /path/on/host
        containerPath: /path/in/node

  - role: worker
    # ──────────────────────────────────────────────────────────
    # LABELS
    # Add labels to nodes for pod scheduling
    # ──────────────────────────────────────────────────────────
    labels:
      environment: development
      node-type: compute

# ──────────────────────────────────────────────────────────────
# FEATURE GATES
# Enable/disable K8s alpha/beta features
# ──────────────────────────────────────────────────────────────
featureGates:
  EphemeralContainers: true

# ──────────────────────────────────────────────────────────────
# CONTAINERD CONFIG
# Custom containerd configuration
# ──────────────────────────────────────────────────────────────
containerdConfigPatches:
  - |-
    [plugins."io.containerd.grpc.v1.cri".registry.mirrors."localhost:5000"]
      endpoint = ["http://kind-registry:5000"]
```

### Creating Different Cluster Sizes

**Single Node (simplest):**

```yaml
kind: Cluster
apiVersion: kind.x-k8s.io/v1alpha4
nodes:
  - role: control-plane
```

**HA Control Plane (3 control-planes):**

```yaml
kind: Cluster
apiVersion: kind.x-k8s.io/v1alpha4
nodes:
  - role: control-plane
  - role: control-plane
  - role: control-plane
  - role: worker
  - role: worker
```

**Large Cluster (many workers):**

```yaml
kind: Cluster
apiVersion: kind.x-k8s.io/v1alpha4
nodes:
  - role: control-plane
  - role: worker
  - role: worker
  - role: worker
  - role: worker
  - role: worker
```

---

## Working with Images

### The Image Loading Problem

Docker images you build locally are **NOT automatically available** inside kind clusters. You must explicitly load them.

```
┌──────────────────────────────────────────────────────────────────────────┐
│                                                                          │
│   Your Terminal                    Kind Cluster                          │
│   ─────────────                    ────────────                          │
│   docker images                    docker exec node crictl images        │
│                                                                          │
│   ┌────────────────────┐          ┌────────────────────────────────┐    │
│   │ ttg-worker:latest  │   ???    │                                │    │
│   │ nginx:latest       │ ──────►  │  (empty, or different images)  │    │
│   │ postgres:15        │          │                                │    │
│   └────────────────────┘          └────────────────────────────────┘    │
│                                                                          │
│   These are SEPARATE image stores!                                       │
│                                                                          │
└──────────────────────────────────────────────────────────────────────────┘
```

### Solutions

**Option 1: kind load (Recommended for local dev)**

```bash
# Build locally
docker build -t ttg-worker:latest .

# Load into kind
kind load docker-image ttg-worker:latest --name ttg-cluster
```

**Option 2: Use a registry**

```bash
# Push to registry
docker push myregistry.io/ttg-worker:latest

# Pull inside cluster (needs imagePullPolicy)
# In your K8s manifest:
#   image: myregistry.io/ttg-worker:latest
#   imagePullPolicy: Always
```

**Option 3: Local registry (advanced)**

```bash
# Create a local registry
docker run -d -p 5000:5000 --name registry registry:2

# Connect kind to registry
# (requires special kind config)
```

### Image Pull Policy

In your K8s manifests, `imagePullPolicy` matters:

| Policy         | Behavior                                  |
| -------------- | ----------------------------------------- |
| `IfNotPresent` | Use local if exists (good for kind load)  |
| `Always`       | Always pull from registry (ignores local) |
| `Never`        | Only use local image, fail if not found   |

**For kind with loaded images:**

```yaml
containers:
  - name: worker
    image: ttg-worker:latest
    imagePullPolicy: IfNotPresent # ← Use the loaded image!
```

### Verifying Images are Loaded

```bash
# List images inside a kind node
docker exec ttg-cluster-worker crictl images

# Expected output:
# IMAGE                     TAG      SIZE
# docker.io/library/ttg-worker latest  186MB
```

---

## Networking

### How Kind Networking Works

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         DOCKER NETWORK                                  │
│                         (kind network)                                  │
│                                                                         │
│  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐     │
│  │ control-plane   │    │ worker          │    │ worker2         │     │
│  │ 172.21.0.3      │    │ 172.21.0.4      │    │ 172.21.0.5      │     │
│  │                 │    │                 │    │                 │     │
│  │  Pod Network:   │    │  Pod Network:   │    │  Pod Network:   │     │
│  │  10.244.0.0/24  │    │  10.244.1.0/24  │    │  10.244.2.0/24  │     │
│  └─────────────────┘    └─────────────────┘    └─────────────────┘     │
│           │                      │                      │               │
│           └──────────────────────┼──────────────────────┘               │
│                                  │                                      │
│                        CNI (Container Network Interface)                │
│                        Enables pod-to-pod communication                 │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### Accessing Services

**From your machine to kind:**

1. **NodePort** (simple, limited ports)

   ```yaml
   # In kind config, map ports
   extraPortMappings:
     - containerPort: 30000
       hostPort: 30000
   ```

2. **Port-forward** (most common for dev)

   ```bash
   kubectl port-forward svc/my-service 8080:80
   ```

3. **LoadBalancer** (requires metallb or similar)
   ```bash
   # Install metallb for LoadBalancer support
   kubectl apply -f https://raw.githubusercontent.com/metallb/metallb/v0.13.7/config/manifests/metallb-native.yaml
   ```

---

## Troubleshooting

### Common Issues and Solutions

#### Issue 1: "Cluster creation fails"

**Symptoms:**

```
Creating cluster "ttg-cluster" ...
 ✗ Ensuring node image (kindest/node:v1.27.3) 🖼
ERROR: failed to create cluster
```

**Solutions:**

```bash
# 1. Check Docker is running
docker ps

# 2. Check available disk space
df -h

# 3. Check Docker has enough resources
docker system df

# 4. Try cleaning up
docker system prune -a
kind delete clusters --all

# 5. Check Docker logs
journalctl -u docker.service -n 50
```

#### Issue 2: "Image not found in cluster"

**Symptoms:**

```
Warning  ErrImageNeverPull  Pod/xxx  Container image "ttg-worker:latest" is not present
```

**Solutions:**

```bash
# 1. Verify image is built locally
docker images | grep ttg-worker

# 2. Load into kind
kind load docker-image ttg-worker:latest --name ttg-cluster

# 3. Verify it's loaded
docker exec ttg-cluster-worker crictl images | grep ttg

# 4. Check your manifest uses correct imagePullPolicy
#    imagePullPolicy: IfNotPresent (not "Always"!)
```

#### Issue 3: "kubectl can't connect"

**Symptoms:**

```
The connection to the server localhost:8080 was refused
```

**Solutions:**

```bash
# 1. Check kubectl context
kubectl config current-context
# Should show: kind-ttg-cluster

# 2. Switch context if needed
kubectl config use-context kind-ttg-cluster

# 3. Verify cluster is running
kind get clusters
docker ps | grep ttg-cluster

# 4. Re-export kubeconfig
kind get kubeconfig --name ttg-cluster > ~/.kube/config
```

#### Issue 4: "Pods stuck in Pending"

**Symptoms:**

```
NAME                  READY   STATUS    RESTARTS   AGE
ttg-computation-0     0/1     Pending   0          5m
```

**Solutions:**

```bash
# 1. Check why it's pending
kubectl describe pod ttg-computation-0

# 2. Common reasons:
#    - "Insufficient cpu" → Reduce resource requests
#    - "0/4 nodes available" → Check node status
#    - "image can't be pulled" → Load image into kind

# 3. Check node resources
kubectl describe nodes | grep -A 10 "Allocated resources"
```

#### Issue 5: "Cluster is slow or unresponsive"

**Solutions:**

```bash
# 1. Check Docker resource allocation
docker stats

# 2. Reduce cluster size
# Edit kind-config.yaml to have fewer workers

# 3. Clean up completed pods
kubectl delete pods --field-selector=status.phase=Succeeded

# 4. Restart the cluster
kind delete cluster --name ttg-cluster
kind create cluster --config kind-config.yaml --name ttg-cluster
```

### Diagnostic Commands

```bash
# ═══════════════════════════════════════════════════════════════
# CLUSTER HEALTH
# ═══════════════════════════════════════════════════════════════

# Overall cluster info
kubectl cluster-info

# Node status
kubectl get nodes -o wide

# All resources
kubectl get all -A

# Events (recent activity)
kubectl get events --sort-by='.lastTimestamp' | tail -20

# ═══════════════════════════════════════════════════════════════
# NODE DEBUGGING
# ═══════════════════════════════════════════════════════════════

# Check node container logs
docker logs ttg-cluster-control-plane
docker logs ttg-cluster-worker

# Exec into node
docker exec -it ttg-cluster-control-plane bash

# Check kubelet logs inside node
docker exec ttg-cluster-worker journalctl -u kubelet -n 50

# ═══════════════════════════════════════════════════════════════
# POD DEBUGGING
# ═══════════════════════════════════════════════════════════════

# Describe pod (events, status)
kubectl describe pod POD_NAME

# Pod logs
kubectl logs POD_NAME

# Previous pod logs (if crashed)
kubectl logs POD_NAME --previous

# Exec into running pod
kubectl exec -it POD_NAME -- /bin/sh
```

---

## Best Practices

### 1. Name Your Clusters

```bash
# BAD: Default name
kind create cluster

# GOOD: Meaningful name
kind create cluster --name ttg-cluster
```

### 2. Use Config Files

```bash
# BAD: CLI options
kind create cluster --name x --config <(echo "nodes: ...")

# GOOD: Checked-in config file
kind create cluster --config k8s/local/kind-config.yaml --name ttg-cluster
```

### 3. Clean Up Resources

```bash
# After development session
kind delete cluster --name ttg-cluster

# Periodically clean Docker
docker system prune
```

### 4. Version Pin Everything

```yaml
# In kind-config.yaml
nodes:
  - role: control-plane
    image: kindest/node:v1.27.3 # ← Specific version!
```

### 5. Use imagePullPolicy: IfNotPresent

```yaml
# In your manifests
containers:
  - name: worker
    image: ttg-worker:latest
    imagePullPolicy: IfNotPresent # ← Crucial for kind load!
```

### 6. Script Everything

```bash
# Create repeatable scripts
./scripts/setup-local.sh   # Creates cluster, loads images
./scripts/cleanup-all.sh   # Deletes everything
```

---

## Quick Start for TTG Project

```bash
# 1. Create cluster
cd /home/xavierand_/Desktop/TTG
kind create cluster --config k8s/local/kind-config.yaml --name ttg-cluster

# 2. Build image
docker build -t ttg-worker:latest -f docker/Dockerfile .

# 3. Load image
kind load docker-image ttg-worker:latest --name ttg-cluster

# 4. Deploy
kubectl apply -f k8s/manifests/parallel-jobs.yaml

# 5. Watch
kubectl get pods -l job-name=ttg-computation -w

# 6. See logs
kubectl logs -l job-name=ttg-computation

# 7. Cleanup
kubectl delete job ttg-computation
kind delete cluster --name ttg-cluster
```

---

## Summary

| Concept              | What to Remember                       |
| -------------------- | -------------------------------------- |
| Kind = K8s IN Docker | Nodes are Docker containers            |
| Images need loading  | `kind load docker-image`               |
| imagePullPolicy      | Use `IfNotPresent` for local images    |
| Contexts matter      | `kubectl config use-context kind-NAME` |
| Always name clusters | `--name ttg-cluster`                   |
| Use config files     | Version-controlled and repeatable      |

---

_Document: KIND_EXPLAINED.md_
_Last Updated: 2026-01-27_
