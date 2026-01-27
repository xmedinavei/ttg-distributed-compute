#!/bin/bash
#
# Deploy TTG workers to Kubernetes
#
# Usage:
#   ./deploy.sh                    # Deploy parallel jobs
#   ./deploy.sh --single           # Deploy single worker (for testing)
#   ./deploy.sh --workers 5        # Deploy with 5 workers
#   ./deploy.sh --params 100000    # Process 100K parameters

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
MANIFESTS_DIR="$PROJECT_ROOT/k8s/manifests"

# Defaults
MODE="parallel"
NUM_WORKERS=3
TOTAL_PARAMS=10000

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --single)
            MODE="single"
            shift
            ;;
        --workers)
            NUM_WORKERS="$2"
            shift 2
            ;;
        --params)
            TOTAL_PARAMS="$2"
            shift 2
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  TTG Kubernetes Deployment${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Check kubectl
if ! kubectl cluster-info &> /dev/null; then
    echo -e "${YELLOW}Error: Cannot connect to Kubernetes cluster${NC}"
    echo "Make sure your cluster is running and kubectl is configured."
    exit 1
fi

# Delete existing jobs
echo -e "${YELLOW}Cleaning up existing jobs...${NC}"
kubectl delete job ttg-computation --ignore-not-found=true 2>/dev/null || true
kubectl delete job ttg-worker-single --ignore-not-found=true 2>/dev/null || true

# Wait for pods to terminate
sleep 2

if [ "$MODE" = "single" ]; then
    echo -e "${GREEN}Deploying single worker...${NC}"
    kubectl apply -f "$MANIFESTS_DIR/worker-job.yaml"
    JOB_NAME="ttg-worker-single"
else
    echo -e "${GREEN}Deploying $NUM_WORKERS parallel workers...${NC}"
    
    # Create a temporary manifest with updated values
    TEMP_MANIFEST=$(mktemp)
    sed -e "s/completions: 3/completions: $NUM_WORKERS/" \
        -e "s/parallelism: 3/parallelism: $NUM_WORKERS/" \
        -e "s/TOTAL_WORKERS.*value: \"3\"/TOTAL_WORKERS\n              value: \"$NUM_WORKERS\"/" \
        -e "s/TOTAL_PARAMETERS.*value: \"10000\"/TOTAL_PARAMETERS\n              value: \"$TOTAL_PARAMS\"/" \
        "$MANIFESTS_DIR/parallel-jobs.yaml" > "$TEMP_MANIFEST"
    
    kubectl apply -f "$TEMP_MANIFEST"
    rm "$TEMP_MANIFEST"
    JOB_NAME="ttg-computation"
fi

echo ""
echo -e "${GREEN}✓ Deployment submitted${NC}"
echo ""
echo "Configuration:"
echo "  Mode:       $MODE"
echo "  Workers:    $NUM_WORKERS"
echo "  Parameters: $TOTAL_PARAMS"
echo ""

# Wait for pods to start
echo -e "${YELLOW}Waiting for pods to start...${NC}"
sleep 3

# Show status
echo ""
echo -e "${BLUE}Pod Status:${NC}"
kubectl get pods -l job-name=$JOB_NAME -o wide
echo ""

echo -e "${BLUE}To monitor progress:${NC}"
echo "  kubectl get pods -l job-name=$JOB_NAME -w"
echo "  kubectl logs -l job-name=$JOB_NAME --all-containers -f"
echo ""
echo -e "${BLUE}To see which node each pod runs on:${NC}"
echo "  kubectl get pods -l job-name=$JOB_NAME -o wide"
