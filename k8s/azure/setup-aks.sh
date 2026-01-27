#!/bin/bash
#
# TTG Azure AKS Setup Script
# Creates an AKS cluster with 3 worker nodes for distributed computation
#
# Prerequisites:
#   - Azure CLI installed (az)
#   - Logged into Azure (az login)
#   - Subscription selected
#
# Usage:
#   chmod +x setup-aks.sh
#   ./setup-aks.sh
#
# Cost Estimate:
#   3x Standard_B2s nodes ≈ $0.15/hour ≈ $108/month
#   Stop cluster when not using to save costs!

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# ============================================
# CONFIGURATION - Customize these values
# ============================================
RESOURCE_GROUP="ttg-sandbox-rg"
LOCATION="eastus"                    # Change to your preferred region
CLUSTER_NAME="ttg-sandbox-aks"
NODE_COUNT=3                         # Number of worker nodes
NODE_VM_SIZE="Standard_B2s"          # VM size (B2s is cheap for testing)
ACR_NAME="ttgsandboxacr$(date +%s)"  # Unique ACR name (appends timestamp)

# ============================================
# Functions
# ============================================
print_header() {
    echo ""
    echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"
    echo -e "${BLUE}  $1${NC}"
    echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"
    echo ""
}

print_step() {
    echo -e "${GREEN}▶ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

# ============================================
# Main Script
# ============================================
print_header "TTG Azure AKS Setup"

echo "This script will create:"
echo "  • Resource Group: $RESOURCE_GROUP"
echo "  • AKS Cluster:    $CLUSTER_NAME ($NODE_COUNT nodes)"
echo "  • Container Registry: $ACR_NAME"
echo "  • Location:       $LOCATION"
echo ""
print_warning "Estimated cost: ~\$0.15/hour for 3 nodes"
echo ""

read -p "Continue? (y/N) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Aborted."
    exit 0
fi

# Step 1: Check Azure CLI
print_header "Step 1: Checking Prerequisites"

if ! command -v az &> /dev/null; then
    print_error "Azure CLI (az) is not installed!"
    echo "Install from: https://docs.microsoft.com/en-us/cli/azure/install-azure-cli"
    exit 1
fi
print_success "Azure CLI is installed"

# Check if logged in
if ! az account show &> /dev/null; then
    print_warning "Not logged into Azure. Opening browser for login..."
    az login
fi
print_success "Logged into Azure"

# Show current subscription
echo ""
echo "Current subscription:"
az account show --query "{Name:name, ID:id}" -o table
echo ""

# Step 2: Create Resource Group
print_header "Step 2: Creating Resource Group"

if az group show --name $RESOURCE_GROUP &> /dev/null; then
    print_warning "Resource group '$RESOURCE_GROUP' already exists"
else
    print_step "Creating resource group..."
    az group create --name $RESOURCE_GROUP --location $LOCATION -o table
    print_success "Resource group created"
fi

# Step 3: Create AKS Cluster
print_header "Step 3: Creating AKS Cluster"

if az aks show --resource-group $RESOURCE_GROUP --name $CLUSTER_NAME &> /dev/null; then
    print_warning "AKS cluster '$CLUSTER_NAME' already exists"
else
    print_step "Creating AKS cluster (this takes 5-10 minutes)..."
    print_warning "Please wait..."
    
    az aks create \
        --resource-group $RESOURCE_GROUP \
        --name $CLUSTER_NAME \
        --node-count $NODE_COUNT \
        --node-vm-size $NODE_VM_SIZE \
        --generate-ssh-keys \
        --enable-managed-identity \
        --no-wait
    
    # Wait for cluster to be ready
    print_step "Waiting for cluster to be ready..."
    az aks wait --resource-group $RESOURCE_GROUP --name $CLUSTER_NAME --created --timeout 1200
    
    print_success "AKS cluster created"
fi

# Step 4: Get Credentials
print_header "Step 4: Configuring kubectl"

print_step "Getting cluster credentials..."
az aks get-credentials --resource-group $RESOURCE_GROUP --name $CLUSTER_NAME --overwrite-existing

print_success "kubectl configured"

# Step 5: Create ACR
print_header "Step 5: Creating Container Registry"

# Make ACR name lowercase and remove special chars
ACR_NAME=$(echo "$ACR_NAME" | tr '[:upper:]' '[:lower:]' | tr -cd '[:alnum:]')

if az acr show --name $ACR_NAME --resource-group $RESOURCE_GROUP &> /dev/null; then
    print_warning "Container Registry '$ACR_NAME' already exists"
else
    print_step "Creating Azure Container Registry..."
    az acr create \
        --resource-group $RESOURCE_GROUP \
        --name $ACR_NAME \
        --sku Basic \
        -o table
    print_success "ACR created: $ACR_NAME"
fi

# Attach ACR to AKS
print_step "Attaching ACR to AKS cluster..."
az aks update \
    --resource-group $RESOURCE_GROUP \
    --name $CLUSTER_NAME \
    --attach-acr $ACR_NAME

print_success "ACR attached to AKS"

# Step 6: Verify
print_header "Step 6: Verification"

print_step "Checking nodes..."
kubectl get nodes -o wide

NODE_READY=$(kubectl get nodes --no-headers | grep -c "Ready")
echo ""
if [ "$NODE_READY" -eq "$NODE_COUNT" ]; then
    print_success "All $NODE_COUNT nodes are Ready"
else
    print_warning "$NODE_READY of $NODE_COUNT nodes are Ready"
fi

# Step 7: Summary
print_header "Setup Complete! 🎉"

echo "Cluster Information:"
echo "  Resource Group:  $RESOURCE_GROUP"
echo "  Cluster Name:    $CLUSTER_NAME"
echo "  Node Count:      $NODE_COUNT"
echo "  Container Registry: $ACR_NAME.azurecr.io"
echo ""
echo "Build and push your image:"
echo "  az acr login --name $ACR_NAME"
echo "  docker build -t $ACR_NAME.azurecr.io/ttg-worker:latest -f docker/Dockerfile ."
echo "  docker push $ACR_NAME.azurecr.io/ttg-worker:latest"
echo ""
echo "Update manifests to use ACR image:"
echo "  image: $ACR_NAME.azurecr.io/ttg-worker:latest"
echo ""
echo "Cost management:"
echo "  Stop cluster:  az aks stop --resource-group $RESOURCE_GROUP --name $CLUSTER_NAME"
echo "  Start cluster: az aks start --resource-group $RESOURCE_GROUP --name $CLUSTER_NAME"
echo "  Delete all:    az group delete --name $RESOURCE_GROUP --yes --no-wait"
echo ""

# Save configuration for later
CONFIG_FILE="$(dirname "$0")/aks-config.env"
cat > "$CONFIG_FILE" << EOF
# AKS Configuration - Generated $(date)
RESOURCE_GROUP="$RESOURCE_GROUP"
CLUSTER_NAME="$CLUSTER_NAME"
ACR_NAME="$ACR_NAME"
LOCATION="$LOCATION"
NODE_COUNT="$NODE_COUNT"
EOF

print_success "Configuration saved to: $CONFIG_FILE"
