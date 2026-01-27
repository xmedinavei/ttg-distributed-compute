#!/bin/bash
#
# Clean up TTG Kubernetes resources
#
# Usage:
#   ./cleanup.sh           # Delete jobs and pods
#   ./cleanup.sh --all     # Delete everything including cluster

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

DELETE_CLUSTER=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --all)
            DELETE_CLUSTER=true
            shift
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

echo -e "${YELLOW}Cleaning up TTG resources...${NC}"

# Delete jobs
echo "Deleting jobs..."
kubectl delete job ttg-computation --ignore-not-found=true 2>/dev/null || true
kubectl delete job ttg-worker-single --ignore-not-found=true 2>/dev/null || true

# Delete any stray pods with our labels
echo "Deleting pods..."
kubectl delete pods -l app=ttg --ignore-not-found=true 2>/dev/null || true

echo -e "${GREEN}✓ Kubernetes resources cleaned up${NC}"

# Optionally delete the entire cluster
if [ "$DELETE_CLUSTER" = true ]; then
    echo ""
    echo -e "${RED}WARNING: This will delete the entire kind cluster!${NC}"
    read -p "Are you sure? (y/N) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo "Deleting kind cluster..."
        kind delete cluster --name ttg-sandbox
        echo -e "${GREEN}✓ Cluster deleted${NC}"
    fi
fi

echo ""
echo "Done!"
