#!/bin/bash
#
# TTG Cleanup All Script
#
# Comprehensive cleanup of all TTG-related resources:
# - Kubernetes jobs and pods
# - Kind cluster
# - Docker images, containers, volumes
#
# Usage:
#   ./cleanup-all.sh              # Interactive cleanup
#   ./cleanup-all.sh --force      # Skip confirmations
#   ./cleanup-all.sh --dry-run    # Show what would be deleted
#   ./cleanup-all.sh --keep-image # Keep Docker image for faster rebuilds

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color
BOLD='\033[1m'

# Configuration
PROJECT_PREFIX="ttg"
KIND_CLUSTER_NAME="ttg-cluster"
IMAGE_NAME="ttg-worker"

# Parse arguments
FORCE=false
DRY_RUN=false
KEEP_IMAGE=false
KEEP_CLUSTER=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --force|-f)
            FORCE=true
            shift
            ;;
        --dry-run|-n)
            DRY_RUN=true
            shift
            ;;
        --keep-image)
            KEEP_IMAGE=true
            shift
            ;;
        --keep-cluster)
            KEEP_CLUSTER=true
            shift
            ;;
        -h|--help)
            echo "TTG Cleanup All Script"
            echo ""
            echo "Usage: $0 [options]"
            echo ""
            echo "Options:"
            echo "  --force, -f       Skip all confirmations"
            echo "  --dry-run, -n     Show what would be deleted without deleting"
            echo "  --keep-image      Keep Docker images (faster rebuilds)"
            echo "  --keep-cluster    Keep kind cluster running"
            echo "  -h, --help        Show this help message"
            echo ""
            echo "Examples:"
            echo "  $0                    # Interactive cleanup"
            echo "  $0 --force            # Delete everything without asking"
            echo "  $0 --dry-run          # Preview what will be deleted"
            echo "  $0 --force --keep-image  # Quick cleanup, keep image"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

# ═══════════════════════════════════════════════════════════════════════════
# UTILITY FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════

print_header() {
    echo ""
    echo -e "${BOLD}${BLUE}═══════════════════════════════════════════════════════════════════════${NC}"
    echo -e "${BOLD}${BLUE}  $1${NC}"
    echo -e "${BOLD}${BLUE}═══════════════════════════════════════════════════════════════════════${NC}"
}

print_step() {
    echo -e "\n${CYAN}>>> $1${NC}"
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

print_info() {
    echo -e "  $1"
}

confirm() {
    if [ "$FORCE" = true ]; then
        return 0
    fi
    
    local message="$1"
    read -p "$(echo -e "${YELLOW}$message [y/N]: ${NC}")" response
    case "$response" in
        [yY][eE][sS]|[yY]) 
            return 0
            ;;
        *)
            return 1
            ;;
    esac
}

execute() {
    local cmd="$1"
    local description="$2"
    
    if [ "$DRY_RUN" = true ]; then
        echo -e "  ${YELLOW}[DRY-RUN]${NC} Would execute: $cmd"
    else
        print_info "Executing: $cmd"
        eval "$cmd" 2>/dev/null || true
    fi
}

# ═══════════════════════════════════════════════════════════════════════════
# MAIN CLEANUP
# ═══════════════════════════════════════════════════════════════════════════

print_header "TTG CLEANUP - Starting"

if [ "$DRY_RUN" = true ]; then
    echo -e "${YELLOW}DRY-RUN MODE: No changes will be made${NC}"
fi

# ─────────────────────────────────────────────────────────────────────────────
# Step 1: Kubernetes Resources
# ─────────────────────────────────────────────────────────────────────────────

print_step "Step 1: Cleaning Kubernetes Resources"

if kubectl cluster-info &> /dev/null 2>&1; then
    # Delete TTG jobs
    JOB_COUNT=$(kubectl get jobs -l app.kubernetes.io/part-of=ttg-distributed-compute --no-headers 2>/dev/null | wc -l || echo "0")
    if [ "$JOB_COUNT" -gt 0 ]; then
        print_info "Found $JOB_COUNT TTG job(s)"
        execute "kubectl delete jobs -l app.kubernetes.io/part-of=ttg-distributed-compute --ignore-not-found=true" "Delete TTG jobs"
    fi
    
    # Delete by name (fallback)
    execute "kubectl delete job ttg-computation --ignore-not-found=true" "Delete ttg-computation job"
    
    # Delete any orphaned pods
    POD_COUNT=$(kubectl get pods -l app.kubernetes.io/name=ttg-worker --no-headers 2>/dev/null | wc -l || echo "0")
    if [ "$POD_COUNT" -gt 0 ]; then
        print_info "Found $POD_COUNT TTG pod(s)"
        execute "kubectl delete pods -l app.kubernetes.io/name=ttg-worker --ignore-not-found=true" "Delete TTG pods"
    fi
    
    # Delete by job-name label (fallback)
    execute "kubectl delete pods -l job-name=ttg-computation --ignore-not-found=true" "Delete pods by job-name"
    
    print_success "Kubernetes resources cleaned"
else
    print_warning "Kubernetes cluster not reachable, skipping K8s cleanup"
fi

# ─────────────────────────────────────────────────────────────────────────────
# Step 2: Kind Cluster
# ─────────────────────────────────────────────────────────────────────────────

print_step "Step 2: Cleaning Kind Cluster"

if [ "$KEEP_CLUSTER" = true ]; then
    print_warning "Keeping kind cluster (--keep-cluster flag)"
else
    if command -v kind &> /dev/null; then
        CLUSTERS=$(kind get clusters 2>/dev/null | grep "^${KIND_CLUSTER_NAME}$" || true)
        if [ -n "$CLUSTERS" ]; then
            print_info "Found kind cluster: $KIND_CLUSTER_NAME"
            if confirm "Delete kind cluster '$KIND_CLUSTER_NAME'?"; then
                execute "kind delete cluster --name $KIND_CLUSTER_NAME" "Delete kind cluster"
                print_success "Kind cluster deleted"
            else
                print_warning "Skipped kind cluster deletion"
            fi
        else
            print_info "No TTG kind cluster found"
        fi
    else
        print_warning "kind not installed, skipping cluster cleanup"
    fi
fi

# ─────────────────────────────────────────────────────────────────────────────
# Step 3: Docker Containers
# ─────────────────────────────────────────────────────────────────────────────

print_step "Step 3: Cleaning Docker Containers"

# TTG named containers
TTG_CONTAINERS=$(docker ps -a --format "{{.Names}}" --filter "name=${PROJECT_PREFIX}-" 2>/dev/null || true)
if [ -n "$TTG_CONTAINERS" ]; then
    CONTAINER_COUNT=$(echo "$TTG_CONTAINERS" | wc -w)
    print_info "Found $CONTAINER_COUNT TTG container(s):"
    echo "$TTG_CONTAINERS" | while read container; do
        print_info "  - $container"
    done
    
    if confirm "Delete these containers?"; then
        for container in $TTG_CONTAINERS; do
            execute "docker rm -f $container" "Remove container $container"
        done
        print_success "TTG containers removed"
    fi
else
    print_info "No TTG containers found"
fi

# Kind cluster containers (if cluster was kept but we want to clean containers)
if [ "$KEEP_CLUSTER" = false ]; then
    KIND_CONTAINERS=$(docker ps -a --format "{{.Names}}" --filter "name=${KIND_CLUSTER_NAME}" 2>/dev/null || true)
    if [ -n "$KIND_CONTAINERS" ]; then
        print_info "Found orphaned kind containers"
        for container in $KIND_CONTAINERS; do
            execute "docker rm -f $container" "Remove container $container"
        done
    fi
fi

# ─────────────────────────────────────────────────────────────────────────────
# Step 4: Docker Images
# ─────────────────────────────────────────────────────────────────────────────

print_step "Step 4: Cleaning Docker Images"

if [ "$KEEP_IMAGE" = true ]; then
    print_warning "Keeping Docker images (--keep-image flag)"
else
    # TTG images
    TTG_IMAGES=$(docker images --format "{{.Repository}}:{{.Tag}}" | grep "^${IMAGE_NAME}:" || true)
    if [ -n "$TTG_IMAGES" ]; then
        IMAGE_COUNT=$(echo "$TTG_IMAGES" | wc -w)
        print_info "Found $IMAGE_COUNT TTG image(s):"
        echo "$TTG_IMAGES" | while read image; do
            print_info "  - $image"
        done
        
        if confirm "Delete these images?"; then
            for image in $TTG_IMAGES; do
                execute "docker rmi $image" "Remove image $image"
            done
            print_success "TTG images removed"
        fi
    else
        print_info "No TTG images found"
    fi
fi

# ─────────────────────────────────────────────────────────────────────────────
# Step 5: Docker Volumes
# ─────────────────────────────────────────────────────────────────────────────

print_step "Step 5: Cleaning Docker Volumes"

TTG_VOLUMES=$(docker volume ls --format "{{.Name}}" | grep "^${PROJECT_PREFIX}-" 2>/dev/null || true)
if [ -n "$TTG_VOLUMES" ]; then
    VOLUME_COUNT=$(echo "$TTG_VOLUMES" | wc -w)
    print_info "Found $VOLUME_COUNT TTG volume(s):"
    echo "$TTG_VOLUMES" | while read volume; do
        print_info "  - $volume"
    done
    
    if confirm "Delete these volumes?"; then
        for volume in $TTG_VOLUMES; do
            execute "docker volume rm $volume" "Remove volume $volume"
        done
        print_success "TTG volumes removed"
    fi
else
    print_info "No TTG volumes found"
fi

# ─────────────────────────────────────────────────────────────────────────────
# Step 6: Docker Networks
# ─────────────────────────────────────────────────────────────────────────────

print_step "Step 6: Cleaning Docker Networks"

TTG_NETWORKS=$(docker network ls --format "{{.Name}}" | grep "^${PROJECT_PREFIX}-" 2>/dev/null || true)
if [ -n "$TTG_NETWORKS" ]; then
    NETWORK_COUNT=$(echo "$TTG_NETWORKS" | wc -w)
    print_info "Found $NETWORK_COUNT TTG network(s)"
    
    if confirm "Delete these networks?"; then
        for network in $TTG_NETWORKS; do
            execute "docker network rm $network" "Remove network $network"
        done
        print_success "TTG networks removed"
    fi
else
    print_info "No TTG networks found"
fi

# ─────────────────────────────────────────────────────────────────────────────
# Step 7: Docker System Prune (optional)
# ─────────────────────────────────────────────────────────────────────────────

print_step "Step 7: Docker System Cleanup (Optional)"

if [ "$DRY_RUN" = false ] && confirm "Run docker system prune to clean dangling resources?"; then
    execute "docker system prune -f" "Prune dangling resources"
    print_success "Docker system pruned"
else
    print_info "Skipped docker system prune"
fi

# ═══════════════════════════════════════════════════════════════════════════
# SUMMARY
# ═══════════════════════════════════════════════════════════════════════════

print_header "CLEANUP COMPLETE"

echo ""
if [ "$DRY_RUN" = true ]; then
    echo -e "${YELLOW}This was a dry-run. No changes were made.${NC}"
    echo -e "Run without ${BOLD}--dry-run${NC} to actually delete resources."
else
    echo -e "${GREEN}All TTG resources have been cleaned up!${NC}"
fi

echo ""
echo "Current state:"
echo "  Kind clusters:  $(kind get clusters 2>/dev/null | wc -l || echo "0")"
echo "  TTG images:     $(docker images --format "{{.Repository}}" | grep -c "^${IMAGE_NAME}" 2>/dev/null || echo "0")"
echo "  TTG containers: $(docker ps -a --format "{{.Names}}" | grep -c "^${PROJECT_PREFIX}" 2>/dev/null || echo "0")"
echo ""
