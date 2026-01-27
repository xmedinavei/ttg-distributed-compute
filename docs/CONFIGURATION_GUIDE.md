# Configuration Guide: Scaling Workers and Parameters

## For the TTG Distributed Computation Project

*A guide explaining when and how to modify the number of workers, parameters, and resources for each milestone.*

---

## Table of Contents

1. [Configuration Overview](#configuration-overview)
2. [Milestone-Based Configuration](#milestone-based-configuration)
3. [Configurable Parameters](#configurable-parameters)
4. [How to Modify Configuration](#how-to-modify-configuration)
5. [Scaling Strategies](#scaling-strategies)
6. [Resource Tuning](#resource-tuning)
7. [Performance Profiling](#performance-profiling)
8. [Common Configurations](#common-configurations)

---

## Configuration Overview

### What Can Be Configured?

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    CONFIGURABLE ELEMENTS                                │
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │  WORKER CONFIGURATION (k8s/manifests/parallel-jobs.yaml)       │   │
│  │                                                                 │   │
│  │  • completions: 3        # How many workers total              │   │
│  │  • parallelism: 3        # How many run simultaneously         │   │
│  │  • TOTAL_WORKERS: "3"    # Passed to worker code               │   │
│  │  • TOTAL_PARAMETERS: "10000"  # Total params to process       │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │  RESOURCE CONFIGURATION                                         │   │
│  │                                                                 │   │
│  │  • requests.cpu: "100m"      # Minimum CPU guaranteed          │   │
│  │  • requests.memory: "128Mi"  # Minimum RAM guaranteed          │   │
│  │  • limits.cpu: "500m"        # Maximum CPU allowed             │   │
│  │  • limits.memory: "256Mi"    # Maximum RAM allowed             │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │  WORKER BEHAVIOR (Environment Variables)                        │   │
│  │                                                                 │   │
│  │  • BATCH_SIZE: "500"         # Progress report frequency       │   │
│  │  • SIMULATE_WORK_MS: "1"     # Simulated computation time      │   │
│  │  • SAVE_OUTPUT: "false"      # Whether to save results to file │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │  CLUSTER CONFIGURATION                                          │   │
│  │                                                                 │   │
│  │  • Number of nodes (kind-config.yaml or AKS scale)             │   │
│  │  • Node sizes (AKS VM sizes)                                   │   │
│  │  • Node labels for targeting                                    │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### Do You Need to Modify Configuration Now?

**Short answer: NO, not for Milestone 1.**

The current configuration is designed for the first milestone:
- 3 workers ✅
- 10,000 test parameters ✅
- Resource limits to prevent resource hogging ✅

**You'll need to modify configuration when:**
- Testing at larger scale (Milestone 2+)
- Your actual algorithm has different resource needs
- Moving to production with real 10M parameters

---

## Milestone-Based Configuration

### Milestone 1: Sandbox Setup (Current)

**Goal**: Prove the distributed architecture works

```yaml
# RECOMMENDED CONFIGURATION (current)
completions: 3
parallelism: 3
TOTAL_WORKERS: "3"
TOTAL_PARAMETERS: "10000"      # Small for fast testing
SIMULATE_WORK_MS: "1"          # Quick simulation

resources:
  requests:
    cpu: "100m"
    memory: "128Mi"
  limits:
    cpu: "500m"
    memory: "256Mi"
```

**Why these values?**
- 3 workers: Proves distribution across nodes
- 10K params: Fast testing (~10 seconds)
- Low resources: Won't impact other apps

**When to move on:**
- ✅ All 3 workers complete successfully
- ✅ Work is distributed across different nodes
- ✅ Each worker processes its assigned range

---

### Milestone 2: Scale Testing

**Goal**: Validate behavior with more workers and data

```yaml
# RECOMMENDED CONFIGURATION
completions: 10
parallelism: 10
TOTAL_WORKERS: "10"
TOTAL_PARAMETERS: "100000"     # 100K parameters
SIMULATE_WORK_MS: "1"

resources:
  requests:
    cpu: "200m"
    memory: "256Mi"
  limits:
    cpu: "1000m"               # 1 CPU core max
    memory: "512Mi"
```

**Prerequisites:**
- Need more nodes (at least 5-10)
- Consider using Azure AKS for real multi-node testing

**When to move on:**
- ✅ All 10 workers complete successfully
- ✅ Linear speedup observed (10x faster than 1 worker)
- ✅ No resource contention issues

---

### Milestone 3: Integration with Real Algorithm

**Goal**: Replace placeholder computation with actual algorithm

```yaml
# WILL DEPEND ON YOUR ALGORITHM
completions: 10
parallelism: 10
TOTAL_WORKERS: "10"
TOTAL_PARAMETERS: "1000000"    # 1M parameters
SIMULATE_WORK_MS: "0"          # Disable simulation, use real algo

resources:
  requests:
    cpu: "500m"                # Adjust based on profiling
    memory: "512Mi"            # Adjust based on profiling
  limits:
    cpu: "2000m"               # 2 CPU cores max
    memory: "2Gi"              # 2GB RAM max
```

**Requirements:**
- Profile your actual algorithm first
- Understand CPU vs memory characteristics
- Test with subset before full scale

---

### Milestone 4: Production Scale

**Goal**: Process all 10M parameters efficiently

```yaml
# PRODUCTION CONFIGURATION (example)
completions: 100
parallelism: 100
TOTAL_WORKERS: "100"
TOTAL_PARAMETERS: "10000000"   # 10M parameters

resources:
  requests:
    cpu: "1000m"               # Based on profiling
    memory: "1Gi"              # Based on profiling
  limits:
    cpu: "4000m"               # 4 CPU cores max
    memory: "4Gi"              # 4GB RAM max
```

**Considerations:**
- Need significant cluster resources
- Consider using Azure AKS with autoscaling
- Implement checkpointing for fault tolerance
- Add proper monitoring and alerting

---

## Configurable Parameters

### Worker Count Parameters

| Parameter | Location | Description | Example |
|-----------|----------|-------------|---------|
| `completions` | Job YAML | Total number of successful completions needed | `3`, `10`, `100` |
| `parallelism` | Job YAML | Max concurrent pods | Usually same as completions |
| `TOTAL_WORKERS` | Env var | Tells worker code how many peers exist | Must match completions |

**Relationship:**
```
completions = parallelism = TOTAL_WORKERS (for our use case)

Work Distribution:
  Worker 0: params 0 to (TOTAL_PARAMETERS / TOTAL_WORKERS)
  Worker 1: params ... to ...
  Worker N: params ... to TOTAL_PARAMETERS
```

### Data Size Parameters

| Parameter | Location | Description | Example |
|-----------|----------|-------------|---------|
| `TOTAL_PARAMETERS` | Env var | Total parameters to process | `10000`, `1000000`, `10000000` |
| `BATCH_SIZE` | Env var | How often to report progress | `100`, `1000`, `10000` |

**Guidelines:**
```
BATCH_SIZE recommendation:
  - Total < 10K:   BATCH_SIZE = 100
  - Total < 100K:  BATCH_SIZE = 1000
  - Total < 1M:    BATCH_SIZE = 10000
  - Total >= 1M:   BATCH_SIZE = 100000

This gives reasonable progress updates without log spam.
```

### Resource Parameters

| Parameter | Location | Description | Example |
|-----------|----------|-------------|---------|
| `requests.cpu` | Job YAML | Minimum CPU guaranteed | `100m`, `500m`, `1000m` |
| `requests.memory` | Job YAML | Minimum RAM guaranteed | `128Mi`, `512Mi`, `1Gi` |
| `limits.cpu` | Job YAML | Maximum CPU allowed | `500m`, `2000m`, `4000m` |
| `limits.memory` | Job YAML | Maximum RAM allowed | `256Mi`, `1Gi`, `4Gi` |

**Units:**
```
CPU:
  100m = 0.1 CPU cores
  1000m = 1 CPU core
  1 = 1 CPU core (same as 1000m)

Memory:
  128Mi = 128 MiB (mebibytes)
  1Gi = 1 GiB (gibibyte) = 1024 MiB
  1G = 1 GB (gigabyte) = 1000 MB
```

---

## How to Modify Configuration

### Method 1: Edit YAML Directly

```bash
# Edit the manifest
nano k8s/manifests/parallel-jobs.yaml

# Apply changes
kubectl delete job ttg-computation  # Delete existing
kubectl apply -f k8s/manifests/parallel-jobs.yaml
```

### Method 2: Use the Deploy Script

```bash
# The deploy script accepts parameters
./scripts/deploy.sh --workers 10 --params 100000
```

### Method 3: Use kubectl with Environment Variables

```bash
# Override at runtime (for quick tests)
kubectl delete job ttg-computation

cat <<EOF | kubectl apply -f -
apiVersion: batch/v1
kind: Job
metadata:
  name: ttg-computation
spec:
  completions: 5
  parallelism: 5
  completionMode: Indexed
  template:
    spec:
      restartPolicy: Never
      containers:
        - name: worker
          image: ttg-worker:latest
          imagePullPolicy: IfNotPresent
          env:
            - name: WORKER_ID
              valueFrom:
                fieldRef:
                  fieldPath: metadata.annotations['batch.kubernetes.io/job-completion-index']
            - name: TOTAL_WORKERS
              value: "5"
            - name: TOTAL_PARAMETERS
              value: "50000"
            - name: BATCH_SIZE
              value: "1000"
            - name: SIMULATE_WORK_MS
              value: "1"
          resources:
            requests:
              cpu: "100m"
              memory: "128Mi"
            limits:
              cpu: "500m"
              memory: "256Mi"
EOF
```

### Method 4: Create Multiple Manifest Files

```bash
# Create different configs for different scenarios
k8s/manifests/
├── parallel-jobs-small.yaml    # 3 workers, 10K params
├── parallel-jobs-medium.yaml   # 10 workers, 100K params
├── parallel-jobs-large.yaml    # 50 workers, 1M params
└── parallel-jobs-prod.yaml     # 100 workers, 10M params

# Use the appropriate one
kubectl apply -f k8s/manifests/parallel-jobs-medium.yaml
```

---

## Scaling Strategies

### Strategy 1: Linear Scaling

Double workers = half the time (ideally)

```
Workers | Time (theoretical) | Actual (with overhead)
--------|-------------------|----------------------
1       | 100 seconds       | 100 seconds
3       | 33 seconds        | 35 seconds
10      | 10 seconds        | 12 seconds
100     | 1 second          | 5 seconds
```

**Why "actual" is higher:**
- Scheduling overhead
- Network latency
- Resource contention
- Pod startup time

### Strategy 2: Node-Based Scaling

Match workers to available nodes for best performance.

```yaml
# Rule of thumb:
# workers = (available_nodes × pods_per_node)

# Example with 3 nodes, 2 pods each:
completions: 6
parallelism: 6
```

### Strategy 3: Resource-Based Scaling

Calculate based on cluster capacity.

```bash
# Check cluster capacity
kubectl describe nodes | grep -A 5 "Allocatable:"

# Example output:
#   cpu: 4
#   memory: 16Gi

# If each worker needs 500m CPU:
# Max workers per node = 4000m / 500m = 8 workers
# 3 nodes = 24 max workers (leaving room for system pods)
```

---

## Resource Tuning

### How to Profile Your Algorithm

```python
# Add profiling to worker.py
import cProfile
import pstats

def profile_computation():
    profiler = cProfile.Profile()
    profiler.enable()
    
    # Your computation here
    for i in range(1000):
        result = your_algorithm(i)
    
    profiler.disable()
    stats = pstats.Stats(profiler)
    stats.sort_stats('cumulative')
    stats.print_stats(10)

# Run locally first
profile_computation()
```

### Monitor Resource Usage

```bash
# After deploying, watch resource usage
kubectl top pods -l job-name=ttg-computation

# Example output:
# NAME                     CPU(cores)   MEMORY(bytes)
# ttg-computation-0-xxx    127m         89Mi
# ttg-computation-1-xxx    143m         92Mi
# ttg-computation-2-xxx    138m         87Mi
```

### Tuning Guidelines

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    RESOURCE TUNING GUIDELINES                           │
│                                                                         │
│  OBSERVED USAGE          RECOMMENDATION                                 │
│  ─────────────────────   ──────────────────────────────────────────    │
│  CPU < 50% of limit      Reduce CPU request/limit                       │
│  CPU hitting limit       Increase CPU limit (may slow down)             │
│  Memory < 50% of limit   Reduce memory request/limit                    │
│  Memory hitting limit    Increase memory limit (OOM risk otherwise)     │
│  Pod evicted (OOM)       Significantly increase memory limit            │
│  Pod pending forever     Reduce requests (too high for cluster)         │
│                                                                         │
│  TYPICAL STARTING POINTS:                                               │
│  ─────────────────────────────────────────────────────────────────     │
│  Light computation:      cpu: 100m-500m,   memory: 128Mi-256Mi         │
│  Medium computation:     cpu: 500m-2000m,  memory: 512Mi-2Gi           │
│  Heavy computation:      cpu: 2000m-8000m, memory: 2Gi-8Gi             │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Performance Profiling

### Local Profiling First

Before deploying to K8s, test locally:

```bash
# Activate virtual environment
source .venv/bin/activate

# Run with profiling
time WORKER_ID=0 TOTAL_WORKERS=1 TOTAL_PARAMETERS=1000 python src/worker.py

# Note the duration and resource usage
```

### Kubernetes Profiling

```bash
# Deploy and time
time kubectl apply -f k8s/manifests/parallel-jobs.yaml
kubectl wait --for=condition=complete job/ttg-computation --timeout=300s

# Check durations from logs
kubectl logs -l job-name=ttg-computation --all-containers | grep "Duration:"
```

### Scaling Test Matrix

Run this matrix to understand your scaling characteristics:

| Workers | Parameters | Expected Time | Actual Time | Efficiency |
|---------|------------|---------------|-------------|------------|
| 1 | 10,000 | baseline | ___ sec | 100% |
| 3 | 10,000 | baseline/3 | ___ sec | ___% |
| 3 | 30,000 | baseline | ___ sec | ___% |
| 10 | 100,000 | baseline | ___ sec | ___% |

---

## Common Configurations

### Configuration: Quick Test

```yaml
# For rapid iteration during development
completions: 3
parallelism: 3
env:
  - name: TOTAL_PARAMETERS
    value: "1000"
  - name: SIMULATE_WORK_MS
    value: "0"  # No delay
resources:
  limits:
    cpu: "100m"
    memory: "128Mi"
```

### Configuration: Realistic Test

```yaml
# For testing with realistic timing
completions: 3
parallelism: 3
env:
  - name: TOTAL_PARAMETERS
    value: "10000"
  - name: SIMULATE_WORK_MS
    value: "10"  # 10ms per param = ~33 sec per worker
resources:
  limits:
    cpu: "500m"
    memory: "256Mi"
```

### Configuration: Scale Test

```yaml
# For testing scalability
completions: 20
parallelism: 20
env:
  - name: TOTAL_PARAMETERS
    value: "100000"
  - name: BATCH_SIZE
    value: "5000"
resources:
  limits:
    cpu: "1000m"
    memory: "512Mi"
```

### Configuration: Production

```yaml
# For actual production workload
completions: 100
parallelism: 100
env:
  - name: TOTAL_PARAMETERS
    value: "10000000"
  - name: BATCH_SIZE
    value: "100000"
  - name: SIMULATE_WORK_MS
    value: "0"  # Use real algorithm
  - name: SAVE_OUTPUT
    value: "true"  # Save results
resources:
  requests:
    cpu: "1000m"
    memory: "1Gi"
  limits:
    cpu: "4000m"
    memory: "4Gi"
```

---

## Summary: When to Change What

| Milestone | Workers | Parameters | Resources | Notes |
|-----------|---------|------------|-----------|-------|
| 1 (Setup) | 3 | 10K | Low | **Current - don't change** |
| 2 (Scale) | 10-50 | 100K-1M | Medium | After M1 validated |
| 3 (Integration) | 10-50 | Based on algo | **Profile first** | After real algo integrated |
| 4 (Production) | 50-1000 | 10M | Based on profiling | After all testing complete |

### Golden Rule

```
Don't optimize prematurely!

1. Make it work (Milestone 1)
2. Make it right (Milestone 2-3)
3. Make it fast (Milestone 4)
```

---

*Last Updated: 2026-01-26*
*Document: CONFIGURATION_GUIDE.md*
