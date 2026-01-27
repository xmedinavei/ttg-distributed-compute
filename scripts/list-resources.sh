#!/bin/bash
#
# TTG List Resources Script
#
# Shows all TTG-related Docker and Kubernetes resources
# Helps identify what belongs to the TTG project
#
# Usage:
#   ./list-resources.sh           # Show all TTG resources
#   ./list-resources.sh --docker  # Docker resources only
#   ./list-resources.sh --k8s     # Kubernetes resources only

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color
BOLD='\033[1m'

# Project prefix
PROJECT_PREFIX="ttg"

# Parse arguments
SHOW_DOCKER=true
SHOW_K8S=true

while [[ $# -gt 0 ]]; do
    case $1 in
        --docker)
            SHOW_K8S=false
            shift
            ;;
        --k8s|--kubernetes)
            SHOW_DOCKER=false
            shift
            ;;
        -h|--help)
            echo "Usage: $0 [--docker|--k8s]"
            echo ""
            echo "Options:"
            echo "  --docker    Show only Docker resources"
            echo "  --k8s       Show only Kubernetes resources"
            echo "  -h, --help  Show this help message"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

print_header() {
    echo ""
    echo -e "${BOLD}${BLUE}═══════════════════════════════════════════════════════════════════════${NC}"
    echo -e "${BOLD}${BLUE}  $1${NC}"
    echo -e "${BOLD}${BLUE}═══════════════════════════════════════════════════════════════════════${NC}"
}

print_subheader() {
    echo ""
    echo -e "${CYAN}─── $1 ───${NC}"
}

print_none() {
    echo -e "  ${YELLOW}(none found)${NC}"
}

# ═══════════════════════════════════════════════════════════════════════════
# DOCKER RESOURCES
# ═══════════════════════════════════════════════════════════════════════════

if [ "$SHOW_DOCKER" = true ]; then
    print_header "DOCKER RESOURCES"
    
    # Docker Images
    print_subheader "Docker Images (ttg-*)"
    TTG_IMAGES=$(docker images --format "table {{.Repository}}\t{{.Tag}}\t{{.ID}}\t{{.Size}}\t{{.CreatedSince}}" | grep -E "^ttg-|^REPOSITORY" || true)
    if [ -n "$TTG_IMAGES" ] && [ $(echo "$TTG_IMAGES" | wc -l) -gt 1 ]; then
        echo "$TTG_IMAGES"
    else
        print_none
    fi
    
    # Kind node images
    print_subheader "Kind Node Images (kindest/node)"
    KIND_IMAGES=$(docker images --format "table {{.Repository}}\t{{.Tag}}\t{{.ID}}\t{{.Size}}" | grep -E "^kindest|^REPOSITORY" || true)
    if [ -n "$KIND_IMAGES" ] && [ $(echo "$KIND_IMAGES" | wc -l) -gt 1 ]; then
        echo "$KIND_IMAGES"
    else
        print_none
    fi
    
    # Docker Containers
    print_subheader "Docker Containers (ttg-*)"
    TTG_CONTAINERS=$(docker ps -a --format "table {{.Names}}\t{{.Image}}\t{{.Status}}\t{{.CreatedAt}}" --filter "name=${PROJECT_PREFIX}" 2>/dev/null || true)
    if [ -n "$TTG_CONTAINERS" ] && [ $(echo "$TTG_CONTAINERS" | wc -l) -gt 1 ]; then
        echo "$TTG_CONTAINERS"
    else
        print_none
    fi
    
    # Kind cluster containers
    print_subheader "Kind Cluster Containers"
    KIND_CONTAINERS=$(docker ps -a --format "table {{.Names}}\t{{.Image}}\t{{.Status}}" --filter "name=ttg-cluster" 2>/dev/null || true)
    if [ -n "$KIND_CONTAINERS" ] && [ $(echo "$KIND_CONTAINERS" | wc -l) -gt 1 ]; then
        echo "$KIND_CONTAINERS"
    else
        print_none
    fi
    
    # Docker Volumes
    print_subheader "Docker Volumes (ttg-*)"
    TTG_VOLUMES=$(docker volume ls --format "table {{.Name}}\t{{.Driver}}" | grep -E "^ttg-|^VOLUME" || true)
    if [ -n "$TTG_VOLUMES" ] && [ $(echo "$TTG_VOLUMES" | wc -l) -gt 1 ]; then
        echo "$TTG_VOLUMES"
    else
        print_none
    fi
    
    # Docker Networks
    print_subheader "Docker Networks (ttg-* or kind)"
    TTG_NETWORKS=$(docker network ls --format "table {{.Name}}\t{{.Driver}}\t{{.Scope}}" | grep -E "^ttg-|^kind|^NAME" || true)
    if [ -n "$TTG_NETWORKS" ] && [ $(echo "$TTG_NETWORKS" | wc -l) -gt 1 ]; then
        echo "$TTG_NETWORKS"
    else
        print_none
    fi
    
    # Kind clusters
    print_subheader "Kind Clusters"
    if command -v kind &> /dev/null; then
        KIND_CLUSTERS=$(kind get clusters 2>/dev/null || echo "")
        if [ -n "$KIND_CLUSTERS" ]; then
            echo "$KIND_CLUSTERS" | while read cluster; do
                echo -e "  ${GREEN}●${NC} $cluster"
            done
        else
            print_none
        fi
    else
        echo -e "  ${YELLOW}kind not installed${NC}"
    fi
    
    # Docker disk usage
    print_subheader "Docker Disk Usage Summary"
    docker system df 2>/dev/null || echo "  Unable to get disk usage"
fi

# ═══════════════════════════════════════════════════════════════════════════
# KUBERNETES RESOURCES
# ═══════════════════════════════════════════════════════════════════════════

if [ "$SHOW_K8S" = true ]; then
    print_header "KUBERNETES RESOURCES"
    
    # Check if kubectl is available and cluster is reachable
    if ! command -v kubectl &> /dev/null; then
        echo -e "  ${YELLOW}kubectl not installed${NC}"
    elif ! kubectl cluster-info &> /dev/null; then
        echo -e "  ${YELLOW}Kubernetes cluster not reachable${NC}"
    else
        # Current context
        print_subheader "Current Context"
        kubectl config current-context 2>/dev/null || echo "  No context set"
        
        # Nodes
        print_subheader "Cluster Nodes"
        kubectl get nodes -o wide 2>/dev/null || print_none
        
        # TTG Jobs
        print_subheader "TTG Jobs"
        TTG_JOBS=$(kubectl get jobs -l app.kubernetes.io/part-of=ttg-distributed-compute -o wide 2>/dev/null || true)
        if [ -n "$TTG_JOBS" ]; then
            echo "$TTG_JOBS"
        else
            # Fallback to name-based search
            kubectl get jobs --field-selector metadata.name=ttg-computation -o wide 2>/dev/null || print_none
        fi
        
        # TTG Pods
        print_subheader "TTG Pods"
        TTG_PODS=$(kubectl get pods -l app.kubernetes.io/name=ttg-worker -o wide 2>/dev/null || true)
        if [ -n "$TTG_PODS" ]; then
            echo "$TTG_PODS"
        else
            # Fallback to job-name label
            kubectl get pods -l job-name=ttg-computation -o wide 2>/dev/null || print_none
        fi
        
        # Pod distribution across nodes
        print_subheader "Pod Distribution by Node"
        kubectl get pods -l app.kubernetes.io/name=ttg-worker -o jsonpath='{range .items[*]}{.metadata.name}{"\t"}{.spec.nodeName}{"\n"}{end}' 2>/dev/null || \
        kubectl get pods -l job-name=ttg-computation -o jsonpath='{range .items[*]}{.metadata.name}{"\t"}{.spec.nodeName}{"\n"}{end}' 2>/dev/null || \
        print_none
        
        # Recent events
        print_subheader "Recent Events (last 10)"
        kubectl get events --sort-by='.lastTimestamp' 2>/dev/null | tail -10 || print_none
    fi
fi

# ═══════════════════════════════════════════════════════════════════════════
# SUMMARY
# ═══════════════════════════════════════════════════════════════════════════

print_header "SUMMARY"

echo ""
echo -e "  ${BOLD}Docker:${NC}"
DOCKER_IMAGE_COUNT=$(docker images --format "{{.Repository}}" | grep -c "^ttg-" 2>/dev/null || echo "0")
DOCKER_CONTAINER_COUNT=$(docker ps -a --format "{{.Names}}" | grep -c "^ttg" 2>/dev/null || echo "0")
KIND_CLUSTER_COUNT=$(kind get clusters 2>/dev/null | wc -l || echo "0")
echo "    TTG Images:     $DOCKER_IMAGE_COUNT"
echo "    TTG Containers: $DOCKER_CONTAINER_COUNT"
echo "    Kind Clusters:  $KIND_CLUSTER_COUNT"

if [ "$SHOW_K8S" = true ] && kubectl cluster-info &> /dev/null 2>&1; then
    echo ""
    echo -e "  ${BOLD}Kubernetes:${NC}"
    K8S_JOB_COUNT=$(kubectl get jobs -l app.kubernetes.io/part-of=ttg-distributed-compute --no-headers 2>/dev/null | wc -l || echo "0")
    K8S_POD_COUNT=$(kubectl get pods -l app.kubernetes.io/name=ttg-worker --no-headers 2>/dev/null | wc -l || echo "0")
    echo "    TTG Jobs: $K8S_JOB_COUNT"
    echo "    TTG Pods: $K8S_POD_COUNT"
fi

echo ""
echo -e "${GREEN}Done!${NC}"
