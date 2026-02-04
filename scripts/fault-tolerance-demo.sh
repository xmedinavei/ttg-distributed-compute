#!/bin/bash
#
# TTG Fault Tolerance Demo Script
#
# This script demonstrates the automatic fault tolerance feature of the
# TTG distributed computation system. It:
#   1. Deploys a slow computation job with 3 workers
#   2. Monitors progress
#   3. Kills a worker mid-processing
#   4. Shows that surviving workers recover the stale tasks
#   5. Verifies all data was processed
#
# Usage:
#   ./scripts/fault-tolerance-demo.sh
#
# Prerequisites:
#   - Kind cluster "ttg-sandbox" running
#   - Redis pod "ttg-redis" running
#   - Docker image ttg-worker:v1.2.1 loaded

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Configuration
TOTAL_PARAMS=1000
CHUNK_SIZE=10
TOTAL_CHUNKS=$((TOTAL_PARAMS / CHUNK_SIZE))
SIMULATE_WORK_MS=100  # 100ms per param = 1 second per chunk
EXPECTED_TIME_PER_CHUNK=1  # seconds
STALE_THRESHOLD=30  # seconds before task considered stale

echo ""
echo -e "${CYAN}╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║       TTG Fault Tolerance Demo - Milestone 2.3              ║${NC}"
echo -e "${CYAN}╚══════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${BLUE}Configuration:${NC}"
echo "  • Total Parameters: $TOTAL_PARAMS"
echo "  • Chunk Size: $CHUNK_SIZE"
echo "  • Total Chunks: $TOTAL_CHUNKS"
echo "  • Simulated Work: ${SIMULATE_WORK_MS}ms per param (~1s per chunk)"
echo "  • Stale Threshold: ${STALE_THRESHOLD}s (time before recovery)"
echo ""

# Step 1: Clean up any existing job
echo -e "${YELLOW}[Step 1/6] Cleaning up previous runs...${NC}"
kubectl delete job ttg-fault-demo 2>/dev/null || true
kubectl exec ttg-redis -- redis-cli DEL ttg:tasks ttg:results ttg:metadata >/dev/null 2>&1 || true
echo "  ✓ Cleanup complete"
sleep 1

# Step 2: Deploy the job
echo ""
echo -e "${YELLOW}[Step 2/6] Deploying fault tolerance demo job (3 workers)...${NC}"
kubectl apply -f k8s/manifests/parallel-jobs-fault-demo.yaml >/dev/null
echo "  ✓ Job deployed"
sleep 2

# Step 3: Wait for workers to start
echo ""
echo -e "${YELLOW}[Step 3/6] Waiting for workers to start processing...${NC}"
for i in {1..10}; do
    PODS=$(kubectl get pods -l ttg.io/mode=fault-demo --no-headers 2>/dev/null | grep -c "Running" || echo "0")
    if [ "$PODS" -ge "3" ]; then
        echo "  ✓ All 3 workers are running"
        break
    fi
    echo "  Waiting... ($PODS/3 workers running)"
    sleep 2
done

# Step 4: Monitor initial progress
echo ""
echo -e "${YELLOW}[Step 4/6] Monitoring initial progress...${NC}"
sleep 3  # Let workers get some work done

# Get initial status
RESULTS=$(kubectl exec ttg-redis -- redis-cli XLEN ttg:results 2>/dev/null || echo "0")
echo "  Initial chunks completed: $RESULTS / $TOTAL_CHUNKS"

# Get pods and select one to kill
PODS=$(kubectl get pods -l ttg.io/mode=fault-demo --no-headers -o custom-columns=":metadata.name" 2>/dev/null)
TARGET_POD=$(echo "$PODS" | head -1)

echo ""
echo -e "${RED}[Step 5/6] 💀 KILLING WORKER: $TARGET_POD${NC}"
echo ""
echo -e "  ${CYAN}Before kill:${NC}"
kubectl exec ttg-redis -- redis-cli XPENDING ttg:tasks ttg-workers 2>/dev/null | head -10
echo ""

# Kill the worker
kubectl delete pod "$TARGET_POD" --force --grace-period=0 2>/dev/null || true
echo ""
echo -e "  ${RED}✓ Worker $TARGET_POD killed!${NC}"

# Step 6: Monitor recovery
echo ""
echo -e "${YELLOW}[Step 6/6] Monitoring fault recovery...${NC}"
echo ""
echo "  The surviving workers will detect stale tasks and recover them."
echo "  This may take up to ${STALE_THRESHOLD}s (stale threshold)."
echo ""

# Monitor until complete or timeout
TIMEOUT=180  # 3 minutes max
START_TIME=$(date +%s)
PREV_RESULTS=0

while true; do
    CURRENT_TIME=$(date +%s)
    ELAPSED=$((CURRENT_TIME - START_TIME))
    
    if [ $ELAPSED -gt $TIMEOUT ]; then
        echo -e "${RED}  Timeout after ${TIMEOUT}s${NC}"
        break
    fi
    
    RESULTS=$(kubectl exec ttg-redis -- redis-cli XLEN ttg:results 2>/dev/null || echo "0")
    PENDING=$(kubectl exec ttg-redis -- redis-cli XPENDING ttg:tasks ttg-workers 2>/dev/null | head -1 || echo "0")
    
    # Progress bar
    PCT=$((RESULTS * 100 / TOTAL_CHUNKS))
    FILLED=$((PCT / 5))
    EMPTY=$((20 - FILLED))
    BAR=$(printf '█%.0s' $(seq 1 $FILLED 2>/dev/null) 2>/dev/null || echo "")
    SPACE=$(printf '░%.0s' $(seq 1 $EMPTY 2>/dev/null) 2>/dev/null || echo "")
    
    echo -ne "\r  [${BAR}${SPACE}] ${RESULTS}/${TOTAL_CHUNKS} chunks (${PCT}%) | Pending: ${PENDING} | Elapsed: ${ELAPSED}s    "
    
    if [ "$RESULTS" -ge "$TOTAL_CHUNKS" ]; then
        echo ""
        echo ""
        echo -e "${GREEN}  ✓ ALL CHUNKS COMPLETED!${NC}"
        break
    fi
    
    PREV_RESULTS=$RESULTS
    sleep 2
done

# Final summary
echo ""
echo -e "${CYAN}════════════════════════════════════════════════════════════════${NC}"
echo -e "${CYAN}                    DEMO RESULTS SUMMARY                         ${NC}"
echo -e "${CYAN}════════════════════════════════════════════════════════════════${NC}"
echo ""

FINAL_RESULTS=$(kubectl exec ttg-redis -- redis-cli XLEN ttg:results 2>/dev/null || echo "0")
FINAL_PENDING=$(kubectl exec ttg-redis -- redis-cli XPENDING ttg:tasks ttg-workers 2>/dev/null | head -1 || echo "0")

echo -e "  Total Chunks Expected:  ${TOTAL_CHUNKS}"
echo -e "  Total Chunks Completed: ${GREEN}${FINAL_RESULTS}${NC}"
echo -e "  Tasks Still Pending:    ${FINAL_PENDING}"
echo ""

if [ "$FINAL_RESULTS" -eq "$TOTAL_CHUNKS" ] && [ "$FINAL_PENDING" -eq "0" ]; then
    echo -e "  ${GREEN}✓ FAULT TOLERANCE TEST PASSED!${NC}"
    echo ""
    echo "  Despite killing a worker mid-processing, all tasks were"
    echo "  recovered by the surviving workers using Redis XCLAIM."
    echo ""
    echo "  Key Features Demonstrated:"
    echo "    • Automatic stale task detection"
    echo "    • XCLAIM-based task recovery"
    echo "    • Zero data loss"
    echo "    • No manual intervention required"
else
    echo -e "  ${RED}✗ Test incomplete - check logs${NC}"
fi

echo ""
echo -e "${CYAN}════════════════════════════════════════════════════════════════${NC}"
echo ""
echo "To see recovery logs:"
echo "  kubectl logs -l ttg.io/mode=fault-demo | grep -i 'FAULT\|RECOVERY\|claimed'"
echo ""
echo "To clean up:"
echo "  kubectl delete job ttg-fault-demo"
echo ""
