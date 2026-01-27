#!/bin/bash
#
# Run worker locally (without Kubernetes) for testing
#
# Usage:
#   ./run-local.sh                        # Run single worker
#   ./run-local.sh --docker               # Run in Docker container
#   ./run-local.sh --params 1000          # Process 1000 parameters

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Defaults
USE_DOCKER=false
WORKER_ID=0
TOTAL_WORKERS=1
TOTAL_PARAMS=1000
SIMULATE_MS=1

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --docker)
            USE_DOCKER=true
            shift
            ;;
        --params)
            TOTAL_PARAMS="$2"
            shift 2
            ;;
        --simulate-ms)
            SIMULATE_MS="$2"
            shift 2
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

echo -e "${GREEN}Running TTG Worker Locally${NC}"
echo "  Parameters: $TOTAL_PARAMS"
echo "  Simulate:   ${SIMULATE_MS}ms per param"
echo ""

if [ "$USE_DOCKER" = true ]; then
    echo -e "${YELLOW}Running in Docker container...${NC}"
    docker run --rm \
        -e WORKER_ID=$WORKER_ID \
        -e TOTAL_WORKERS=$TOTAL_WORKERS \
        -e TOTAL_PARAMETERS=$TOTAL_PARAMS \
        -e SIMULATE_WORK_MS=$SIMULATE_MS \
        -e BATCH_SIZE=100 \
        ttg-worker:latest
else
    echo -e "${YELLOW}Running with Python...${NC}"
    cd "$PROJECT_ROOT"
    WORKER_ID=$WORKER_ID \
    TOTAL_WORKERS=$TOTAL_WORKERS \
    TOTAL_PARAMETERS=$TOTAL_PARAMS \
    SIMULATE_WORK_MS=$SIMULATE_MS \
    BATCH_SIZE=100 \
    python src/worker.py
fi
