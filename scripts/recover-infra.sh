#!/bin/bash
#
# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║               TTG INFRASTRUCTURE RECOVERY SCRIPT                              ║
# ║                                                                               ║
# ║  Use this script to quickly restore TTG infrastructure after:                ║
# ║  • Docker Desktop restart                                                     ║
# ║  • System reboot                                                              ║
# ║  • Kind containers stopped                                                    ║
# ║  • Redis/RedisInsight pods deleted                                            ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
#
# USAGE:
#   ./scripts/recover-infra.sh
#
# ═══════════════════════════════════════════════════════════════════════════════

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

print_header() {
    echo ""
    echo -e "${CYAN}╔══════════════════════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${CYAN}║${NC} $1"
    echo -e "${CYAN}╚══════════════════════════════════════════════════════════════════════════════╝${NC}"
    echo ""
}

print_step() {
    echo -e "${YELLOW}▶ $1${NC}"
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ $1${NC}"
}

# ────────────────────────────────────────────────────────────────────────────────
# Step 1: Check if Kind cluster exists
# ────────────────────────────────────────────────────────────────────────────────
print_header "TTG Infrastructure Recovery"

print_step "Checking Kind cluster status..."

if ! kind get clusters 2>/dev/null | grep -q "^ttg-sandbox$"; then
    print_error "Kind cluster 'ttg-sandbox' not found."
    echo ""
    echo "  To create the cluster, run:"
    echo -e "    ${CYAN}./k8s/local/setup-local.sh${NC}"
    echo ""
    exit 1
fi

# ────────────────────────────────────────────────────────────────────────────────
# Step 2: Check if Kind containers are running
# ────────────────────────────────────────────────────────────────────────────────
print_step "Checking Kind Docker containers..."

STOPPED_CONTAINERS=$(docker ps -a --filter "name=ttg-sandbox" --filter "status=exited" --format "{{.Names}}" | tr '\n' ' ')

if [[ -n "$STOPPED_CONTAINERS" ]]; then
    print_info "Found stopped containers: $STOPPED_CONTAINERS"
    print_step "Restarting Kind containers..."
    
    docker start ttg-sandbox-control-plane ttg-sandbox-worker ttg-sandbox-worker2 ttg-sandbox-worker3 2>/dev/null || true
    
    print_info "Waiting for Kubernetes API to become ready..."
    sleep 10
    
    # Verify API is accessible
    if kubectl cluster-info --context kind-ttg-sandbox &>/dev/null; then
        print_success "Kubernetes API is ready!"
    else
        print_error "Kubernetes API not responding. Try waiting longer or check Docker."
        exit 1
    fi
    
    # Wait for CoreDNS to be ready (critical for service discovery)
    print_step "Waiting for CoreDNS to be ready (required for service discovery)..."
    kubectl wait --for=condition=ready pods -l k8s-app=kube-dns -n kube-system --timeout=60s &>/dev/null || true
    sleep 5  # Extra buffer for DNS propagation
    print_success "CoreDNS is ready!"
else
    RUNNING_CONTAINERS=$(docker ps --filter "name=ttg-sandbox" --format "{{.Names}}" | wc -l)
    if [[ "$RUNNING_CONTAINERS" -ge 4 ]]; then
        print_success "Kind containers are already running!"
    else
        print_error "Kind containers not found. Cluster may need to be recreated."
        echo ""
        echo "  To create the cluster, run:"
        echo -e "    ${CYAN}./k8s/local/setup-local.sh${NC}"
        echo ""
        exit 1
    fi
fi

# ────────────────────────────────────────────────────────────────────────────────
# Step 3: Check nodes are ready
# ────────────────────────────────────────────────────────────────────────────────
print_step "Verifying Kubernetes nodes..."

kubectl wait --for=condition=ready nodes --all --timeout=60s &>/dev/null || true

NODE_COUNT=$(kubectl get nodes --no-headers 2>/dev/null | grep -c "Ready" || echo "0")
if [[ "$NODE_COUNT" -ge 4 ]]; then
    print_success "All $NODE_COUNT nodes are ready!"
else
    print_error "Only $NODE_COUNT nodes ready. Expected 4."
    kubectl get nodes
    exit 1
fi

# ────────────────────────────────────────────────────────────────────────────────
# Step 4: Deploy/verify Redis
# ────────────────────────────────────────────────────────────────────────────────
print_step "Checking Redis pod..."

if kubectl get pod ttg-redis &>/dev/null; then
    if kubectl exec ttg-redis -- redis-cli PING &>/dev/null; then
        print_success "Redis is already running and responding!"
    else
        print_info "Redis pod exists but not responding. Redeploying..."
        kubectl delete pod ttg-redis --ignore-not-found=true
        kubectl apply -f "$PROJECT_DIR/k8s/manifests/redis.yaml"
        kubectl wait --for=condition=ready pod/ttg-redis --timeout=60s
        print_success "Redis redeployed and ready!"
    fi
else
    print_info "Redis not found. Deploying..."
    kubectl apply -f "$PROJECT_DIR/k8s/manifests/redis.yaml"
    kubectl wait --for=condition=ready pod/ttg-redis --timeout=60s
    print_success "Redis deployed and ready!"
fi

# ────────────────────────────────────────────────────────────────────────────────
# Step 5: Deploy/verify RedisInsight (optional)
# ────────────────────────────────────────────────────────────────────────────────
print_step "Checking RedisInsight pod..."

if kubectl get pod redis-insight &>/dev/null; then
    print_success "RedisInsight is already deployed!"
else
    print_info "RedisInsight not found. Deploying..."
    kubectl apply -f "$PROJECT_DIR/k8s/manifests/redis-insight.yaml" 2>/dev/null || true
    print_success "RedisInsight deployed!"
fi

# ────────────────────────────────────────────────────────────────────────────────
# Step 6: Verify Docker image
# ────────────────────────────────────────────────────────────────────────────────
print_step "Checking Docker image in Kind cluster..."

if docker exec ttg-sandbox-control-plane crictl images 2>/dev/null | grep -q "ttg-worker.*v1.2.1"; then
    print_success "Docker image ttg-worker:v1.2.1 is loaded!"
else
    print_info "Docker image not found in cluster. Loading..."
    if docker images | grep -q "ttg-worker.*v1.2.1"; then
        kind load docker-image ttg-worker:v1.2.1 --name ttg-sandbox
        print_success "Image loaded into Kind cluster!"
    else
        print_error "Image ttg-worker:v1.2.1 not found locally."
        echo ""
        echo "  Build the image first:"
        echo -e "    ${CYAN}./scripts/build.sh --version 1.2.1 --load-kind${NC}"
        echo ""
        exit 1
    fi
fi

# ────────────────────────────────────────────────────────────────────────────────
# Summary
# ────────────────────────────────────────────────────────────────────────────────
echo ""
echo -e "${GREEN}════════════════════════════════════════════════════════════════════════════════${NC}"
echo ""
print_success "TTG Infrastructure Recovery Complete!"
echo ""
echo "  Current status:"
kubectl get pods --no-headers 2>/dev/null | awk '{print "    • " $1 ": " $3}'
echo ""
echo "  You can now run the demo:"
echo -e "    ${CYAN}./scripts/run-demo.sh --scale small --fault-demo${NC}"
echo ""
