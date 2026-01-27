# Kubernetes Setup Guide

This guide provides step-by-step instructions to set up your Kubernetes sandbox environment.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Option A: Local Setup with kind](#option-a-local-setup-with-kind-recommended)
3. [Option B: Azure AKS Setup](#option-b-azure-aks-setup)
4. [Verification Steps](#verification-steps)
5. [Troubleshooting](#troubleshooting)

---

## Prerequisites

Before starting, ensure you have these installed:

### Required Tools

| Tool                     | Purpose            | Installation                                                                      |
| ------------------------ | ------------------ | --------------------------------------------------------------------------------- |
| **Docker**               | Container runtime  | [Install Docker](https://docs.docker.com/get-docker/)                             |
| **kubectl**              | Kubernetes CLI     | [Install kubectl](https://kubernetes.io/docs/tasks/tools/)                        |
| **kind** (Option A)      | Local K8s clusters | See below                                                                         |
| **Azure CLI** (Option B) | Azure management   | [Install Azure CLI](https://docs.microsoft.com/en-us/cli/azure/install-azure-cli) |

### Check Docker Installation

```bash
# Verify Docker is running
docker --version
docker ps  # Should not error

# If Docker is not running:
sudo systemctl start docker
# Or on macOS: Open Docker Desktop
```

### Install kubectl

```bash
# Linux (Ubuntu/Debian)
curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"
chmod +x kubectl
sudo mv kubectl /usr/local/bin/

# macOS
brew install kubectl

# Windows (with chocolatey)
choco install kubernetes-cli

# Verify installation
kubectl version --client
```

---

## Option A: Local Setup with kind (Recommended)

### What is kind?

**kind** (Kubernetes IN Docker) runs Kubernetes clusters using Docker containers as nodes. Perfect for:

- Local development
- Testing
- CI/CD pipelines

### Step 1: Install kind

```bash
# Linux (amd64)
curl -Lo ./kind https://kind.sigs.k8s.io/dl/v0.20.0/kind-linux-amd64
chmod +x ./kind
sudo mv ./kind /usr/local/bin/kind

# Linux (arm64)
curl -Lo ./kind https://kind.sigs.k8s.io/dl/v0.20.0/kind-linux-arm64
chmod +x ./kind
sudo mv ./kind /usr/local/bin/kind

# macOS (Intel)
brew install kind
# OR
curl -Lo ./kind https://kind.sigs.k8s.io/dl/v0.20.0/kind-darwin-amd64
chmod +x ./kind
sudo mv ./kind /usr/local/bin/kind

# macOS (Apple Silicon)
curl -Lo ./kind https://kind.sigs.k8s.io/dl/v0.20.0/kind-darwin-arm64
chmod +x ./kind
sudo mv ./kind /usr/local/bin/kind

# Windows (PowerShell)
curl.exe -Lo kind-windows-amd64.exe https://kind.sigs.k8s.io/dl/v0.20.0/kind-windows-amd64
Move-Item .\kind-windows-amd64.exe c:\some-dir-in-your-PATH\kind.exe

# Verify installation
kind --version
```

### Step 2: Create Multi-Node Cluster

We'll create a cluster with:

- 1 control plane node (the "brain")
- 3 worker nodes (where our jobs run)

```bash
# Navigate to project directory
cd /home/xavierand_/Desktop/TTG

# Create cluster using our config
kind create cluster --name ttg-sandbox --config k8s/local/kind-config.yaml

# This takes 2-5 minutes...
```

### Step 3: Verify Cluster

```bash
# Check cluster info
kubectl cluster-info --context kind-ttg-sandbox

# List all nodes (should see 4: 1 control-plane + 3 workers)
kubectl get nodes

# Expected output:
# NAME                        STATUS   ROLES           AGE   VERSION
# ttg-sandbox-control-plane   Ready    control-plane   1m    v1.27.3
# ttg-sandbox-worker          Ready    <none>          1m    v1.27.3
# ttg-sandbox-worker2         Ready    <none>          1m    v1.27.3
# ttg-sandbox-worker3         Ready    <none>          1m    v1.27.3
```

### Step 4: Load Docker Image

kind uses its own container registry. We need to load our worker image:

```bash
# Build the worker image
docker build -t ttg-worker:latest -f docker/Dockerfile .

# Load into kind cluster
kind load docker-image ttg-worker:latest --name ttg-sandbox

# Verify image is available
docker exec -it ttg-sandbox-control-plane crictl images | grep ttg-worker
```

### Quick Start Script

Use our automated setup script:

```bash
cd /home/xavierand_/Desktop/TTG
chmod +x k8s/local/setup-local.sh
./k8s/local/setup-local.sh
```

---

## Option B: Azure AKS Setup

### What is Azure AKS?

Azure Kubernetes Service (AKS) is a managed Kubernetes offering. Azure handles:

- Control plane management
- Automatic upgrades
- Scaling
- Monitoring

### Step 1: Login to Azure

```bash
# Login (opens browser)
az login

# Set subscription (if you have multiple)
az account list --output table
az account set --subscription "Your Subscription Name"
```

### Step 2: Create Resource Group

```bash
# Variables (customize these)
RESOURCE_GROUP="ttg-sandbox-rg"
LOCATION="eastus"  # Or: westus, westeurope, etc.

# Create resource group
az group create --name $RESOURCE_GROUP --location $LOCATION
```

### Step 3: Create AKS Cluster

```bash
# Variables
CLUSTER_NAME="ttg-sandbox-aks"
NODE_COUNT=3  # Number of worker nodes

# Create AKS cluster (takes 5-10 minutes)
az aks create \
  --resource-group $RESOURCE_GROUP \
  --name $CLUSTER_NAME \
  --node-count $NODE_COUNT \
  --node-vm-size Standard_B2s \
  --generate-ssh-keys \
  --enable-managed-identity

# Get credentials (configures kubectl)
az aks get-credentials \
  --resource-group $RESOURCE_GROUP \
  --name $CLUSTER_NAME
```

### Step 4: Verify Cluster

```bash
# Check nodes
kubectl get nodes

# Expected output:
# NAME                                STATUS   ROLES   AGE   VERSION
# aks-nodepool1-12345678-vmss000000   Ready    agent   5m    v1.27.7
# aks-nodepool1-12345678-vmss000001   Ready    agent   5m    v1.27.7
# aks-nodepool1-12345678-vmss000002   Ready    agent   5m    v1.27.7
```

### Step 5: Create Azure Container Registry (ACR)

For AKS, we need a container registry to store our images:

```bash
# Variables
ACR_NAME="ttgsandboxacr"  # Must be globally unique, lowercase

# Create ACR
az acr create \
  --resource-group $RESOURCE_GROUP \
  --name $ACR_NAME \
  --sku Basic

# Attach ACR to AKS (allows AKS to pull images)
az aks update \
  --resource-group $RESOURCE_GROUP \
  --name $CLUSTER_NAME \
  --attach-acr $ACR_NAME
```

### Step 6: Build and Push Image

```bash
# Login to ACR
az acr login --name $ACR_NAME

# Build and push using ACR
az acr build \
  --registry $ACR_NAME \
  --image ttg-worker:latest \
  --file docker/Dockerfile \
  .

# Or build locally and push
docker build -t $ACR_NAME.azurecr.io/ttg-worker:latest -f docker/Dockerfile .
docker push $ACR_NAME.azurecr.io/ttg-worker:latest
```

### Step 7: Update Image Reference

When using AKS, update the image reference in your Kubernetes manifests:

```yaml
# Change FROM:
image: ttg-worker:latest

# Change TO:
image: ttgsandboxacr.azurecr.io/ttg-worker:latest
```

### Cost Management

⚠️ **Important**: AKS incurs costs!

Estimated costs for 3 x Standard_B2s nodes:

- ~$0.05/hour per node = $0.15/hour total
- ~$108/month if running 24/7

**To minimize costs:**

```bash
# Stop cluster when not using (keeps config, stops billing for nodes)
az aks stop --resource-group $RESOURCE_GROUP --name $CLUSTER_NAME

# Start cluster when needed
az aks start --resource-group $RESOURCE_GROUP --name $CLUSTER_NAME

# Delete everything when done
az group delete --name $RESOURCE_GROUP --yes --no-wait
```

### Quick Start Script

Use our automated AKS setup script:

```bash
cd /home/xavierand_/Desktop/TTG
chmod +x k8s/azure/setup-aks.sh
./k8s/azure/setup-aks.sh
```

---

## Verification Steps

After setup (either option), verify everything works:

### 1. Check Nodes

```bash
kubectl get nodes -o wide

# All nodes should show STATUS: Ready
```

### 2. Check System Pods

```bash
kubectl get pods -n kube-system

# All pods should be Running
```

### 3. Run Test Pod

```bash
# Run a test pod
kubectl run test-pod --image=nginx --restart=Never

# Check it's running
kubectl get pods

# Delete test pod
kubectl delete pod test-pod
```

### 4. Check Cluster Resources

```bash
# See allocatable resources per node
kubectl describe nodes | grep -A 5 "Allocatable:"
```

---

## Troubleshooting

### Common Issues

#### Issue: "Cannot connect to Docker daemon"

```bash
# Linux: Start Docker
sudo systemctl start docker
sudo usermod -aG docker $USER
# Log out and log back in

# macOS: Start Docker Desktop application
```

#### Issue: "kind create cluster" hangs

```bash
# Check Docker resources (needs at least 4GB RAM for kind)
docker info | grep -i memory

# Delete any failed clusters
kind delete cluster --name ttg-sandbox

# Try again with verbose logging
kind create cluster --name ttg-sandbox --config k8s/local/kind-config.yaml --verbosity 9
```

#### Issue: "kubectl: command not found"

```bash
# Add to PATH
export PATH=$PATH:/usr/local/bin

# Make permanent (add to ~/.bashrc or ~/.zshrc)
echo 'export PATH=$PATH:/usr/local/bin' >> ~/.bashrc
source ~/.bashrc
```

#### Issue: "nodes are NotReady"

```bash
# Check node details
kubectl describe node <node-name>

# Check kubelet logs (for kind)
docker logs ttg-sandbox-control-plane

# Wait a few minutes - nodes might still be initializing
```

#### Issue: Image not found when deploying

```bash
# For kind - make sure image is loaded
kind load docker-image ttg-worker:latest --name ttg-sandbox

# Check images in kind
docker exec -it ttg-sandbox-control-plane crictl images

# For AKS - check ACR login
az acr login --name $ACR_NAME
az acr repository list --name $ACR_NAME
```

#### Issue: Pods stuck in "Pending"

```bash
# Check why
kubectl describe pod <pod-name>

# Usually resource constraints - check node resources
kubectl describe nodes | grep -A 10 "Allocated resources"
```

### Getting Help

```bash
# General cluster info
kubectl cluster-info dump

# Events (shows recent cluster events)
kubectl get events --sort-by='.lastTimestamp'

# Pod logs
kubectl logs <pod-name>

# Describe resources for detailed info
kubectl describe <resource-type> <resource-name>
```

---

## Switching Between Clusters

If you have both local and AKS clusters:

```bash
# List all contexts
kubectl config get-contexts

# Switch to local (kind)
kubectl config use-context kind-ttg-sandbox

# Switch to AKS
kubectl config use-context ttg-sandbox-aks

# Verify current context
kubectl config current-context
```

---

## Next Steps

Once your cluster is running:

1. **Build the worker image**: See [../docker/Dockerfile](../docker/Dockerfile)
2. **Deploy jobs**: See [../k8s/manifests/](../k8s/manifests/)
3. **Run your first distributed computation**: See [../README.md](../README.md)

---

_Last Updated: 2026-01-26_
