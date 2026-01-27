# Azure AKS Guide: Complete Setup and Analysis

## For the TTG Distributed Computation Project

_A comprehensive guide to deploying on Azure Kubernetes Service (AKS) with pros/cons analysis, cost breakdown, and step-by-step instructions._

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Local (kind) vs Azure (AKS) Comparison](#local-kind-vs-azure-aks-comparison)
3. [When to Use AKS](#when-to-use-aks)
4. [Cost Analysis](#cost-analysis)
5. [Prerequisites](#prerequisites)
6. [Step-by-Step Setup](#step-by-step-setup)
7. [Configuration Options](#configuration-options)
8. [Security Best Practices](#security-best-practices)
9. [Monitoring & Observability](#monitoring--observability)
10. [Cost Optimization](#cost-optimization)
11. [Cleanup & Cost Control](#cleanup--cost-control)
12. [Troubleshooting](#troubleshooting)

---

## Executive Summary

### What is Azure AKS?

**Azure Kubernetes Service (AKS)** is Microsoft's managed Kubernetes offering. Azure handles:

- Control plane management (free!)
- Automatic upgrades
- Security patches
- Scaling infrastructure
- Integration with Azure services

### Quick Decision Matrix

| Factor              | Local (kind)             | Azure AKS                 |
| ------------------- | ------------------------ | ------------------------- |
| **Cost**            | Free                     | ~$0.05-0.10/hour per node |
| **Setup Time**      | 5 min                    | 15-20 min                 |
| **Scalability**     | Limited by local machine | Virtually unlimited       |
| **Production-like** | No                       | Yes                       |
| **Best For**        | Learning, testing, dev   | Staging, production       |

### Recommendation

```
MILESTONE 1 (Setup/Learning):
  ✅ Use Local (kind) - Free, fast, great for learning

MILESTONE 2+ (Scale Testing):
  ✅ Use Azure AKS - Test with real scale, network latency

PRODUCTION:
  ✅ Use Azure AKS - Managed, scalable, production-ready
```

---

## Local (kind) vs Azure (AKS) Comparison

### Detailed Pros and Cons

#### Local (kind)

| Pros ✅                                       | Cons ❌                                                  |
| --------------------------------------------- | -------------------------------------------------------- |
| **Free** - No cloud costs                     | **Limited resources** - Constrained by local machine     |
| **Fast setup** - 2-5 minutes                  | **Not production-like** - Single machine simulation      |
| **Works offline** - No internet needed        | **No real network latency** - All local                  |
| **Great for learning** - Safe experimentation | **Can't test true scaling** - Limited to local resources |
| **Easy reset** - Delete and recreate quickly  | **No cloud integrations** - No Azure services            |
| **CI/CD friendly** - Easy to automate         | **Difficult to share** - Only on your machine            |

#### Azure AKS

| Pros ✅                                          | Cons ❌                                        |
| ------------------------------------------------ | ---------------------------------------------- |
| **Production-like** - Real multi-node cluster    | **Costs money** - Pay for compute resources    |
| **Scalable** - Add nodes as needed               | **Longer setup** - 15-20 minutes               |
| **Real networking** - True latency and bandwidth | **Requires Azure account** - Need subscription |
| **Azure integrations** - ACR, Monitor, KeyVault  | **Internet required** - Cloud dependency       |
| **Managed control plane** - Azure handles it     | **More complex** - More moving parts           |
| **Team access** - Share with colleagues          | **Cleanup required** - Remember to delete      |
| **Auto-scaling** - Scale on demand               | **Learning curve** - More configuration        |

### Feature Comparison

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    FEATURE COMPARISON                                    │
├───────────────────────────┬─────────────────┬───────────────────────────┤
│ Feature                   │ Local (kind)    │ Azure AKS                 │
├───────────────────────────┼─────────────────┼───────────────────────────┤
│ Multi-node cluster        │ ✅ Simulated    │ ✅ Real VMs               │
│ Container registry        │ ⚠️ Local only   │ ✅ ACR (Azure Container)  │
│ Persistent storage        │ ⚠️ Local disk   │ ✅ Azure Disks/Files      │
│ Load balancing            │ ⚠️ Limited      │ ✅ Azure Load Balancer    │
│ Auto-scaling              │ ❌ Manual       │ ✅ Cluster autoscaler     │
│ Monitoring                │ ⚠️ Manual setup │ ✅ Azure Monitor          │
│ RBAC / Security           │ ⚠️ Basic        │ ✅ Azure AD integration   │
│ Network policies          │ ⚠️ Limited      │ ✅ Full support           │
│ Secrets management        │ ⚠️ K8s secrets  │ ✅ Azure Key Vault        │
│ CI/CD integration         │ ✅ Good         │ ✅ Excellent              │
│ Production readiness      │ ❌ No           │ ✅ Yes                    │
└───────────────────────────┴─────────────────┴───────────────────────────┘
```

---

## When to Use AKS

### Decision Tree

```
                    START
                      │
                      ▼
          ┌─────────────────────┐
          │ Learning K8s?       │
          │ First time setup?   │
          └─────────┬───────────┘
                    │
            ┌───────┴───────┐
            │               │
           YES              NO
            │               │
            ▼               ▼
      ┌──────────┐   ┌─────────────────┐
      │ Use kind │   │ Testing at      │
      │ (local)  │   │ scale (>10      │
      └──────────┘   │ workers)?       │
                     └────────┬────────┘
                              │
                      ┌───────┴───────┐
                      │               │
                     YES              NO
                      │               │
                      ▼               ▼
                ┌──────────┐   ┌─────────────────┐
                │ Use AKS  │   │ Sharing with    │
                │          │   │ team?           │
                └──────────┘   └────────┬────────┘
                                        │
                                ┌───────┴───────┐
                                │               │
                               YES              NO
                                │               │
                                ▼               ▼
                          ┌──────────┐   ┌──────────┐
                          │ Use AKS  │   │ Use kind │
                          └──────────┘   │ (local)  │
                                         └──────────┘
```

### Specific Scenarios

| Scenario                    | Recommendation | Reason                    |
| --------------------------- | -------------- | ------------------------- |
| Learning K8s concepts       | Local (kind)   | Free, fast, safe          |
| First milestone (3 workers) | Local (kind)   | Sufficient for validation |
| Testing 50+ workers         | Azure AKS      | Need real multi-node      |
| Team collaboration          | Azure AKS      | Shared access             |
| CI/CD pipeline              | Either         | Both work well            |
| Production deployment       | Azure AKS      | Production-ready          |
| Demo to stakeholders        | Azure AKS      | Real environment          |
| Budget: $0                  | Local (kind)   | Free                      |
| Quick iteration             | Local (kind)   | Faster feedback           |

---

## Cost Analysis

### AKS Pricing Model

```
┌─────────────────────────────────────────────────────────────────────────┐
│                      AKS COST STRUCTURE                                 │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌─────────────────────────────────────┐                               │
│  │         CONTROL PLANE               │                               │
│  │     (API Server, etcd, etc.)        │                               │
│  │                                     │                               │
│  │            💵 FREE                  │                               │
│  │    (Azure manages this for you)     │                               │
│  └─────────────────────────────────────┘                               │
│                                                                         │
│  ┌─────────────────────────────────────┐                               │
│  │         WORKER NODES                │                               │
│  │     (VMs that run your pods)        │                               │
│  │                                     │                               │
│  │      💵 YOU PAY FOR THESE           │                               │
│  │    (Based on VM size and count)     │                               │
│  └─────────────────────────────────────┘                               │
│                                                                         │
│  ┌─────────────────────────────────────┐                               │
│  │      ADDITIONAL SERVICES            │                               │
│  │                                     │                               │
│  │  • Container Registry (ACR)         │                               │
│  │  • Storage (disks, files)           │                               │
│  │  • Networking (Load Balancer, IP)   │                               │
│  │  • Monitoring (Azure Monitor)       │                               │
│  │                                     │                               │
│  │      💵 PAY AS YOU USE              │                               │
│  └─────────────────────────────────────┘                               │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### VM Size Options for TTG Project

| VM Size             | vCPUs | RAM   | Cost/hour\* | Best For           |
| ------------------- | ----- | ----- | ----------- | ------------------ |
| **Standard_B2s**    | 2     | 4 GB  | ~$0.05      | Testing (cheapest) |
| **Standard_B2ms**   | 2     | 8 GB  | ~$0.08      | Light workloads    |
| **Standard_D2s_v3** | 2     | 8 GB  | ~$0.10      | General purpose    |
| **Standard_D4s_v3** | 4     | 16 GB | ~$0.19      | Heavier workloads  |
| **Standard_D8s_v3** | 8     | 32 GB | ~$0.38      | Compute-intensive  |
| **Standard_F4s_v2** | 4     | 8 GB  | ~$0.17      | CPU-optimized      |

\*Prices are approximate and vary by region. Check [Azure Pricing Calculator](https://azure.microsoft.com/pricing/calculator/).

### Cost Scenarios for TTG Project

#### Scenario 1: Testing (First Milestone)

```
Configuration:
  - 3 nodes × Standard_B2s
  - ACR Basic tier
  - No load balancer

Cost Breakdown:
  Nodes:    3 × $0.05/hr = $0.15/hour
  ACR:      $0.17/day (Basic)
  Total:    ~$0.17/hour = ~$4/day

If running 8 hours for testing:
  Total: ~$1.50/day
```

#### Scenario 2: Scale Testing (50 workers)

```
Configuration:
  - 10 nodes × Standard_D4s_v3
  - ACR Standard tier
  - Load balancer

Cost Breakdown:
  Nodes:    10 × $0.19/hr = $1.90/hour
  ACR:      $0.67/day (Standard)
  LB:       ~$0.03/hour
  Total:    ~$2/hour = ~$48/day

If running for 4 hours of testing:
  Total: ~$8
```

#### Scenario 3: Full Scale (1000 workers)

```
Configuration:
  - 100 nodes × Standard_D8s_v3
  - ACR Premium tier
  - Multiple load balancers

Cost Breakdown:
  Nodes:    100 × $0.38/hr = $38/hour
  ACR:      $1.67/day (Premium)
  LB:       ~$0.10/hour
  Total:    ~$38/hour = ~$912/day

This is why testing at full scale should be brief!
```

### Cost-Saving Tips

1. **Use B-series VMs** for testing (cheapest)
2. **Stop cluster when not using** (`az aks stop`)
3. **Use Spot instances** for fault-tolerant workloads (60-90% cheaper)
4. **Delete unused resources** (ACR images, disks)
5. **Right-size nodes** based on actual usage
6. **Set budget alerts** in Azure

---

## Prerequisites

### Required Tools

```bash
# 1. Azure CLI (az)
# Install: https://docs.microsoft.com/en-us/cli/azure/install-azure-cli

# Linux (Ubuntu/Debian)
curl -sL https://aka.ms/InstallAzureCLIDeb | sudo bash

# macOS
brew install azure-cli

# Verify
az --version

# 2. kubectl (already have from local setup)
kubectl version --client

# 3. Docker (already have)
docker --version
```

### Azure Account Setup

```bash
# Login to Azure (opens browser)
az login

# List subscriptions
az account list --output table

# Set active subscription
az account set --subscription "Your Subscription Name or ID"

# Verify
az account show
```

---

## Step-by-Step Setup

### Quick Setup (Using Script)

```bash
cd /home/xavierand_/Desktop/TTG
chmod +x k8s/azure/setup-aks.sh
./k8s/azure/setup-aks.sh
```

### Manual Setup (Detailed)

#### Step 1: Set Variables

```bash
# Configuration
RESOURCE_GROUP="ttg-sandbox-rg"
LOCATION="eastus"
CLUSTER_NAME="ttg-sandbox-aks"
NODE_COUNT=3
NODE_VM_SIZE="Standard_B2s"
ACR_NAME="ttgsandboxacr$(date +%s)"  # Must be globally unique
```

#### Step 2: Create Resource Group

```bash
az group create \
  --name $RESOURCE_GROUP \
  --location $LOCATION

# Verify
az group show --name $RESOURCE_GROUP --output table
```

#### Step 3: Create AKS Cluster

```bash
# Create cluster (takes 5-10 minutes)
az aks create \
  --resource-group $RESOURCE_GROUP \
  --name $CLUSTER_NAME \
  --node-count $NODE_COUNT \
  --node-vm-size $NODE_VM_SIZE \
  --generate-ssh-keys \
  --enable-managed-identity

# Get credentials for kubectl
az aks get-credentials \
  --resource-group $RESOURCE_GROUP \
  --name $CLUSTER_NAME \
  --overwrite-existing

# Verify
kubectl get nodes
```

#### Step 4: Create Container Registry (ACR)

```bash
# Create ACR
az acr create \
  --resource-group $RESOURCE_GROUP \
  --name $ACR_NAME \
  --sku Basic

# Attach ACR to AKS (allows pulling images)
az aks update \
  --resource-group $RESOURCE_GROUP \
  --name $CLUSTER_NAME \
  --attach-acr $ACR_NAME

# Verify
az acr list --resource-group $RESOURCE_GROUP --output table
```

#### Step 5: Build and Push Image

```bash
# Login to ACR
az acr login --name $ACR_NAME

# Build and push (using ACR build - no local Docker needed)
az acr build \
  --registry $ACR_NAME \
  --image ttg-worker:latest \
  --file docker/Dockerfile \
  .

# Verify
az acr repository list --name $ACR_NAME --output table
```

#### Step 6: Update Manifests

Edit `k8s/manifests/parallel-jobs.yaml`:

```yaml
# Change this line:
image: ttg-worker:latest

# To:
image: <your-acr-name>.azurecr.io/ttg-worker:latest
```

#### Step 7: Deploy

```bash
# Deploy the jobs
kubectl apply -f k8s/manifests/parallel-jobs.yaml

# Watch pods
kubectl get pods -w

# Check logs
kubectl logs -l job-name=ttg-computation --all-containers
```

---

## Configuration Options

### Cluster Configuration

```bash
# Scale nodes up/down
az aks scale \
  --resource-group $RESOURCE_GROUP \
  --name $CLUSTER_NAME \
  --node-count 5

# Enable cluster autoscaler
az aks update \
  --resource-group $RESOURCE_GROUP \
  --name $CLUSTER_NAME \
  --enable-cluster-autoscaler \
  --min-count 1 \
  --max-count 10
```

### Node Pool Options

```bash
# Add a dedicated node pool for computation
az aks nodepool add \
  --resource-group $RESOURCE_GROUP \
  --cluster-name $CLUSTER_NAME \
  --name computepool \
  --node-count 3 \
  --node-vm-size Standard_D4s_v3 \
  --labels workload=compute

# Use node selector in manifests
spec:
  nodeSelector:
    workload: compute
```

### Spot Instances (Save 60-90%)

```bash
# Add spot node pool for cost savings
az aks nodepool add \
  --resource-group $RESOURCE_GROUP \
  --cluster-name $CLUSTER_NAME \
  --name spotpool \
  --priority Spot \
  --eviction-policy Delete \
  --spot-max-price -1 \
  --node-count 3 \
  --node-vm-size Standard_D4s_v3

# Note: Spot instances can be evicted anytime!
# Good for: Fault-tolerant, stateless workloads
# Bad for: Critical workloads that can't restart
```

---

## Security Best Practices

### 1. Use Managed Identity

```bash
# Already enabled in our setup
--enable-managed-identity
```

### 2. Enable Azure AD Integration

```bash
# For team access control
az aks update \
  --resource-group $RESOURCE_GROUP \
  --name $CLUSTER_NAME \
  --enable-aad
```

### 3. Network Policies

```yaml
# Example: Restrict worker pod network access
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: worker-network-policy
spec:
  podSelector:
    matchLabels:
      app: ttg
  policyTypes:
    - Egress
  egress:
    - {} # Allow all egress (customize as needed)
```

### 4. Use Azure Key Vault for Secrets

```bash
# Enable Key Vault secrets provider
az aks enable-addons \
  --resource-group $RESOURCE_GROUP \
  --name $CLUSTER_NAME \
  --addons azure-keyvault-secrets-provider
```

---

## Monitoring & Observability

### Enable Azure Monitor

```bash
# Enable monitoring addon
az aks enable-addons \
  --resource-group $RESOURCE_GROUP \
  --name $CLUSTER_NAME \
  --addons monitoring
```

### View in Azure Portal

1. Go to Azure Portal
2. Navigate to your AKS cluster
3. Click "Insights" for monitoring dashboard

### Basic kubectl Monitoring

```bash
# Node resources
kubectl top nodes

# Pod resources
kubectl top pods

# Events
kubectl get events --sort-by='.lastTimestamp'

# Logs
kubectl logs -l job-name=ttg-computation --all-containers -f
```

---

## Cost Optimization

### 1. Stop Cluster When Not Using

```bash
# Stop (deallocates all nodes - no compute charges)
az aks stop \
  --resource-group $RESOURCE_GROUP \
  --name $CLUSTER_NAME

# Start when needed
az aks start \
  --resource-group $RESOURCE_GROUP \
  --name $CLUSTER_NAME

# Note: Control plane charges may still apply minimally
```

### 2. Use Budget Alerts

```bash
# Create a budget (via Azure CLI or Portal)
az consumption budget create \
  --budget-name ttg-budget \
  --amount 50 \
  --time-grain Monthly \
  --category Cost \
  --resource-group $RESOURCE_GROUP
```

### 3. Right-Size Recommendations

```bash
# View advisor recommendations
az advisor recommendation list \
  --resource-group $RESOURCE_GROUP
```

---

## Cleanup & Cost Control

### Stop Cluster (Pause Billing)

```bash
# Stops all nodes, keeps configuration
az aks stop \
  --resource-group $RESOURCE_GROUP \
  --name $CLUSTER_NAME

# Restart later
az aks start \
  --resource-group $RESOURCE_GROUP \
  --name $CLUSTER_NAME
```

### Delete Everything

```bash
# Delete entire resource group (ALL resources!)
az group delete \
  --name $RESOURCE_GROUP \
  --yes \
  --no-wait

# Verify deletion
az group show --name $RESOURCE_GROUP  # Should error
```

### Clean Up Specific Resources

```bash
# Delete just the cluster
az aks delete \
  --resource-group $RESOURCE_GROUP \
  --name $CLUSTER_NAME \
  --yes

# Delete ACR
az acr delete \
  --resource-group $RESOURCE_GROUP \
  --name $ACR_NAME \
  --yes

# Delete old images from ACR
az acr repository delete \
  --name $ACR_NAME \
  --image ttg-worker:old-tag \
  --yes
```

---

## Troubleshooting

### Common Issues

#### Issue: "az: command not found"

```bash
# Install Azure CLI
curl -sL https://aka.ms/InstallAzureCLIDeb | sudo bash
```

#### Issue: "Not authorized" / Permission denied

```bash
# Re-login
az logout
az login

# Check subscription
az account show
```

#### Issue: Cluster creation fails

```bash
# Check quotas
az vm list-usage --location eastus --output table

# Try different region
az aks create ... --location westus2
```

#### Issue: Can't pull images from ACR

```bash
# Re-attach ACR
az aks update \
  --resource-group $RESOURCE_GROUP \
  --name $CLUSTER_NAME \
  --attach-acr $ACR_NAME

# Verify attachment
az aks check-acr \
  --resource-group $RESOURCE_GROUP \
  --name $CLUSTER_NAME \
  --acr $ACR_NAME.azurecr.io
```

#### Issue: Pods stuck in Pending

```bash
# Check events
kubectl describe pod <pod-name>

# Check node resources
kubectl describe nodes | grep -A 5 "Allocated resources"

# Scale up if needed
az aks scale \
  --resource-group $RESOURCE_GROUP \
  --name $CLUSTER_NAME \
  --node-count 5
```

---

## Quick Reference Commands

```bash
# ========== CLUSTER MANAGEMENT ==========
az aks get-credentials -g $RG -n $CLUSTER    # Configure kubectl
az aks stop -g $RG -n $CLUSTER               # Stop (save money)
az aks start -g $RG -n $CLUSTER              # Start
az aks scale -g $RG -n $CLUSTER -c 5         # Scale nodes
az aks delete -g $RG -n $CLUSTER --yes       # Delete

# ========== CONTAINER REGISTRY ==========
az acr login -n $ACR                         # Login
az acr build -r $ACR -t image:tag .          # Build & push
az acr repository list -n $ACR               # List images

# ========== MONITORING ==========
kubectl get nodes                             # List nodes
kubectl top nodes                             # Node resources
kubectl top pods                              # Pod resources
kubectl logs -l app=ttg --all-containers     # View logs

# ========== COST MANAGEMENT ==========
az group delete -n $RG --yes --no-wait       # Delete all
az consumption usage list                     # View usage
```

---

## Summary

### Key Takeaways

1. **Start with local (kind)** for learning and first milestone
2. **Use AKS** when you need real scale, team access, or production
3. **Always stop/delete** clusters when not using to save costs
4. **B-series VMs** are cheapest for testing
5. **Set budget alerts** to avoid surprise bills
6. **Use spot instances** for up to 90% savings on fault-tolerant workloads

### Recommended Path

```
Week 1: Local (kind)
├── Learn K8s concepts
├── Test with 3 workers
└── Validate worker code

Week 2-3: Azure AKS (testing)
├── Test with 10-50 workers
├── Validate scaling behavior
└── Tune resource limits

Week 4+: Azure AKS (production)
├── Full scale deployment
├── Monitoring enabled
└── Cost-optimized configuration
```

---

_Last Updated: 2026-01-26_
_Document: AZURE_AKS_GUIDE.md_
