#!/bin/bash
#
# TTG Local Kubernetes Setup Script
# Creates a local Kubernetes cluster using kind for testing distributed computation
#
# Prerequisites:
#   - Docker installed and running
#   - kind installed (https://kind.sigs.k8s.io/docs/user/quick-start/#installation)
#   - kubectl installed
#
# Usage:
#   chmod +x setup-local.sh
#   ./setup-local.sh
#

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
CLUSTER_NAME="ttg-sandbox"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
KIND_CONFIG="$SCRIPT_DIR/kind-config.yaml"

# Functions
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

check_command() {
    if ! command -v $1 &> /dev/null; then
        print_error "$1 is not installed!"
        echo "Please install $1 first."
        echo "See: $2"
        exit 1
    fi
    print_success "$1 is installed"
}

# Main Script
print_header "TTG Kubernetes Sandbox Setup"

echo "This script will:"
echo "  1. Check prerequisites (Docker, kind, kubectl)"
echo "  2. Create a multi-node Kubernetes cluster"
echo "  3. Build and load the worker Docker image"
echo "  4. Verify the cluster is ready"
echo ""

# Step 1: Check prerequisites
print_header "Step 1: Checking Prerequisites"

print_step "Checking Docker..."
check_command "docker" "https://docs.docker.com/get-docker/"

# Check Docker is running
if ! docker info &> /dev/null; then
    print_error "Docker is not running!"
    echo "Please start Docker and try again."
    echo "  Linux: sudo systemctl start docker"
    echo "  macOS: Open Docker Desktop"
    exit 1
fi
print_success "Docker is running"

print_step "Checking kind..."
check_command "kind" "https://kind.sigs.k8s.io/docs/user/quick-start/#installation"

print_step "Checking kubectl..."
check_command "kubectl" "https://kubernetes.io/docs/tasks/tools/"

# Step 2: Check for existing cluster
print_header "Step 2: Preparing Cluster"

if kind get clusters 2>/dev/null | grep -q "^${CLUSTER_NAME}$"; then
    print_warning "Cluster '${CLUSTER_NAME}' already exists!"
    read -p "Do you want to delete it and create a new one? (y/N) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        print_step "Deleting existing cluster..."
        kind delete cluster --name ${CLUSTER_NAME}
        print_success "Existing cluster deleted"
    else
        print_step "Keeping existing cluster. Skipping creation..."
        SKIP_CREATE=true
    fi
fi

# Step 3: Create cluster
if [ "$SKIP_CREATE" != "true" ]; then
    print_header "Step 3: Creating Kubernetes Cluster"

    print_step "Creating cluster with 1 control-plane + 3 workers..."
    print_warning "This may take 2-5 minutes..."
    echo ""

    if [ -f "$KIND_CONFIG" ]; then
        kind create cluster --name ${CLUSTER_NAME} --config ${KIND_CONFIG}
    else
        print_error "Kind config not found at: $KIND_CONFIG"
        print_step "Creating cluster with default config..."
        kind create cluster --name ${CLUSTER_NAME}
    fi

    print_success "Cluster created!"
fi

# Step 4: Configure kubectl
print_header "Step 4: Configuring kubectl"

print_step "Setting kubectl context..."
kubectl config use-context kind-${CLUSTER_NAME}
print_success "kubectl configured for cluster: ${CLUSTER_NAME}"

# Step 5: Verify cluster
print_header "Step 5: Verifying Cluster"

print_step "Checking nodes..."
echo ""
kubectl get nodes -o wide
echo ""

NODE_COUNT=$(kubectl get nodes --no-headers | wc -l)
if [ "$NODE_COUNT" -ge 4 ]; then
    print_success "All $NODE_COUNT nodes are present (1 control-plane + 3 workers)"
else
    print_warning "Expected 4 nodes, found $NODE_COUNT"
fi

print_step "Checking node readiness..."
READY_COUNT=$(kubectl get nodes --no-headers | grep -c "Ready")
if [ "$READY_COUNT" -eq "$NODE_COUNT" ]; then
    print_success "All nodes are Ready"
else
    print_warning "$READY_COUNT of $NODE_COUNT nodes are Ready"
    echo "Waiting for nodes to be ready..."
    kubectl wait --for=condition=Ready nodes --all --timeout=120s
fi

# Step 6: Build and load worker image
print_header "Step 6: Building Worker Image"

DOCKERFILE="$PROJECT_ROOT/docker/Dockerfile"
if [ -f "$DOCKERFILE" ]; then
    print_step "Building Docker image: ttg-worker:latest"
    docker build -t ttg-worker:latest -f "$DOCKERFILE" "$PROJECT_ROOT"
    print_success "Image built"

    print_step "Loading image into kind cluster..."
    kind load docker-image ttg-worker:latest --name ${CLUSTER_NAME}
    print_success "Image loaded into cluster"
else
    print_warning "Dockerfile not found at: $DOCKERFILE"
    print_warning "Skipping image build. You can build it later with:"
    echo "  docker build -t ttg-worker:latest -f docker/Dockerfile ."
    echo "  kind load docker-image ttg-worker:latest --name ${CLUSTER_NAME}"
fi

# Step 7: Summary
print_header "Setup Complete! 🎉"

echo "Cluster Information:"
echo "  Name:     ${CLUSTER_NAME}"
echo "  Context:  kind-${CLUSTER_NAME}"
echo "  Nodes:    $NODE_COUNT"
echo ""
echo "Useful commands:"
echo "  kubectl get nodes              # List nodes"
echo "  kubectl get pods               # List pods"
echo "  kubectl get jobs               # List jobs"
echo "  kubectl logs <pod-name>        # View pod logs"
echo ""
echo "To deploy worker jobs:"
echo "  kubectl apply -f k8s/manifests/parallel-jobs.yaml"
echo ""
echo "To delete the cluster when done:"
echo "  kind delete cluster --name ${CLUSTER_NAME}"
echo ""

print_success "Your Kubernetes sandbox is ready!"
