#!/bin/bash
#
# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║                    TTG DISTRIBUTED COMPUTATION DEMO                           ║
# ║                         Milestone 2: Queue Mode                               ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
#
# This script demonstrates the TTG distributed computation system with:
#   - Redis Streams message queue architecture
#   - Multiple parallel workers
#   - Fault tolerance (worker crash recovery)
#   - Real-time monitoring options
#
# USAGE:
#   ./scripts/run-demo.sh [OPTIONS]
#
# OPTIONS:
#   --scale small|medium    Set test scale (default: small)
#                          small:  1,000 params, 100 chunks, ~30s runtime
#                          medium: 10,000 params, 100 chunks, ~5min runtime
#
#   --workers N            Number of workers (default: 3)
#
#   --fault-demo           Include fault tolerance demonstration
#                          (kills a worker mid-processing)
#
#   --monitor cli|web|both|none    Monitoring mode (default: none)
#                          cli:  Terminal-based queue monitor
#                          web:  RedisInsight Web UI
#                          both: Both monitoring tools
#                          none: No monitoring
#
#   --skip-cleanup         Don't clean up after demo
#
#   --help                 Show this help message
#
# EXAMPLES:
#   # Quick demo with fault tolerance
#   ./scripts/run-demo.sh --scale small --fault-demo
#
#   # Full demo with monitoring
#   ./scripts/run-demo.sh --scale medium --fault-demo --monitor both
#
#   # Simple demo, no frills
#   ./scripts/run-demo.sh
#
# PREREQUISITES:
#   - Kind cluster 'ttg-sandbox' running
#   - Redis pod 'ttg-redis' deployed
#   - Docker image 'ttg-worker:v1.2.1' loaded into Kind
#
# ═══════════════════════════════════════════════════════════════════════════════

set -e

# ┌──────────────────────────────────────────────────────────────────────────────┐
# │                              CONFIGURATION                                    │
# └──────────────────────────────────────────────────────────────────────────────┘

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
MAGENTA='\033[0;35m'
NC='\033[0m' # No Color

# Default configuration
SCALE="small"
WORKERS=3
FAULT_DEMO=false
MONITOR_MODE="none"
SKIP_CLEANUP=false
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# ┌──────────────────────────────────────────────────────────────────────────────┐
# │                            HELPER FUNCTIONS                                   │
# └──────────────────────────────────────────────────────────────────────────────┘

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

show_help() {
    sed -n '2,/^# ═══════════════════════════════════════════════════════════════════════════════$/p' "$0" | grep "^#" | sed 's/^# //' | sed 's/^#//'
    exit 0
}

check_prerequisites() {
    print_step "Checking prerequisites..."
    
    # Check kubectl
    if ! command -v kubectl &> /dev/null; then
        print_error "kubectl not found. Please install kubectl."
        exit 1
    fi
    
    # Check Kind cluster
    if ! kubectl cluster-info --context kind-ttg-sandbox &> /dev/null; then
        print_error "Kind cluster 'ttg-sandbox' not found or not accessible."
        echo "  Run: kind create cluster --name ttg-sandbox --config k8s/local/kind-config.yaml"
        exit 1
    fi
    
    # Check Redis
    if ! kubectl get pod ttg-redis &> /dev/null; then
        print_error "Redis pod 'ttg-redis' not found."
        echo "  Run: kubectl apply -f k8s/manifests/redis.yaml"
        exit 1
    fi
    
    # Check Redis is ready
    if ! kubectl exec ttg-redis -- redis-cli PING &> /dev/null; then
        print_error "Redis is not responding."
        exit 1
    fi
    
    # Check Docker image
    if ! docker exec ttg-sandbox-control-plane crictl images 2>/dev/null | grep -q "ttg-worker.*v1.2.1"; then
        print_error "Docker image 'ttg-worker:v1.2.1' not loaded into Kind."
        echo "  Run: docker build -t ttg-worker:v1.2.1 -f docker/Dockerfile . && kind load docker-image ttg-worker:v1.2.1 --name ttg-sandbox"
        exit 1
    fi
    
    print_success "All prerequisites met!"
}

get_scale_config() {
    case "$SCALE" in
        small)
            TOTAL_PARAMS=1000
            CHUNK_SIZE=10
            SIMULATE_WORK_MS=100
            ;;
        medium)
            TOTAL_PARAMS=10000
            CHUNK_SIZE=100
            SIMULATE_WORK_MS=10
            ;;
        *)
            print_error "Unknown scale: $SCALE"
            exit 1
            ;;
    esac
    TOTAL_CHUNKS=$((TOTAL_PARAMS / CHUNK_SIZE))
}

# ┌──────────────────────────────────────────────────────────────────────────────┐
# │                            PARSE ARGUMENTS                                    │
# └──────────────────────────────────────────────────────────────────────────────┘

while [[ $# -gt 0 ]]; do
    case $1 in
        --scale)
            SCALE="$2"
            shift 2
            ;;
        --workers)
            WORKERS="$2"
            shift 2
            ;;
        --fault-demo)
            FAULT_DEMO=true
            shift
            ;;
        --monitor)
            MONITOR_MODE="$2"
            shift 2
            ;;
        --skip-cleanup)
            SKIP_CLEANUP=true
            shift
            ;;
        --help|-h)
            show_help
            ;;
        *)
            print_error "Unknown option: $1"
            echo "Use --help for usage information."
            exit 1
            ;;
    esac
done

# ┌──────────────────────────────────────────────────────────────────────────────┐
# │                               MAIN DEMO                                       │
# └──────────────────────────────────────────────────────────────────────────────┘

print_header "TTG Distributed Computation Demo - Milestone 2"

echo -e "${MAGENTA}Configuration:${NC}"
get_scale_config
echo "  • Scale: $SCALE"
echo "  • Total Parameters: $TOTAL_PARAMS"
echo "  • Chunk Size: $CHUNK_SIZE"
echo "  • Total Chunks: $TOTAL_CHUNKS"
echo "  • Workers: $WORKERS"
echo "  • Simulated Work: ${SIMULATE_WORK_MS}ms per param"
echo "  • Fault Demo: $FAULT_DEMO"
echo "  • Monitor Mode: $MONITOR_MODE"
echo ""

check_prerequisites

# ────────────────────────────────────────────────────────────────────────────────
# Step 1: Clean up previous runs
# ────────────────────────────────────────────────────────────────────────────────
print_header "Step 1: Preparing Environment"

print_step "Cleaning up previous demo resources..."
kubectl delete pod -l ttg.io/mode=fault-demo-standalone 2>/dev/null || true
kubectl delete pod -l ttg.io/mode=fault-test 2>/dev/null || true
kubectl delete job -l ttg.io/project=distributed-compute 2>/dev/null || true
sleep 2

print_step "Clearing Redis queues..."
kubectl exec ttg-redis -- redis-cli FLUSHALL > /dev/null
print_success "Environment ready!"

# ────────────────────────────────────────────────────────────────────────────────
# Step 2: Start monitoring (if requested)
# ────────────────────────────────────────────────────────────────────────────────
MONITOR_PIDS=()

if [[ "$MONITOR_MODE" == "cli" || "$MONITOR_MODE" == "both" ]]; then
    print_header "Step 2: Starting CLI Monitor"
    print_step "Starting Redis port-forward..."
    kubectl port-forward pod/ttg-redis 6379:6379 &>/dev/null &
    MONITOR_PIDS+=($!)
    sleep 2
    
    print_info "CLI Monitor will be started in a new terminal."
    print_info "Run this command in another terminal:"
    echo ""
    echo -e "  ${CYAN}python ${PROJECT_DIR}/scripts/queue_monitor.py --total-params $TOTAL_PARAMS${NC}"
    echo ""
    read -p "Press Enter when ready to continue..."
fi

if [[ "$MONITOR_MODE" == "web" || "$MONITOR_MODE" == "both" ]]; then
    print_header "Step 2: Starting RedisInsight Web UI"
    
    # Check if RedisInsight is deployed
    if ! kubectl get pod redis-insight &>/dev/null; then
        print_step "Deploying RedisInsight..."
        kubectl apply -f "$PROJECT_DIR/k8s/manifests/redis-insight.yaml"
        sleep 10
    fi
    
    print_step "Starting RedisInsight port-forward..."
    kubectl port-forward pod/redis-insight 8001:8001 &>/dev/null &
    MONITOR_PIDS+=($!)
    sleep 2
    
    print_info "RedisInsight is available at: ${CYAN}http://localhost:8001${NC}"
    print_info "First-time setup:"
    echo "  1. Click 'Add Redis Database'"
    echo "  2. Host: ttg-redis, Port: 6379"
    echo "  3. Name: TTG Demo"
    echo "  4. Click 'Add Redis Database'"
    echo ""
    read -p "Press Enter when ready to continue..."
fi

# ────────────────────────────────────────────────────────────────────────────────
# Step 3: Deploy Workers
# ────────────────────────────────────────────────────────────────────────────────
print_header "Step 3: Deploying $WORKERS Workers"

# Generate worker manifests dynamically
for i in $(seq 0 $((WORKERS - 1))); do
    cat << EOF | kubectl apply -f - >/dev/null
apiVersion: v1
kind: Pod
metadata:
  name: ttg-worker-$i
  labels:
    app.kubernetes.io/name: ttg-worker
    ttg.io/project: distributed-compute
    ttg.io/mode: fault-demo-standalone
    ttg.io/worker-id: "$i"
spec:
  restartPolicy: Never
  containers:
  - name: worker
    image: ttg-worker:v1.2.1
    imagePullPolicy: Never
    env:
    - name: WORKER_ID
      value: "$i"
    - name: POD_NAME
      valueFrom:
        fieldRef:
          fieldPath: metadata.name
    - name: HOSTNAME
      valueFrom:
        fieldRef:
          fieldPath: metadata.name
    - name: REDIS_HOST
      value: "ttg-redis"
    - name: REDIS_PORT
      value: "6379"
    - name: USE_QUEUE
      value: "true"
    - name: QUEUE_STREAM
      value: "ttg:tasks"
    - name: RESULTS_STREAM
      value: "ttg:results"
    - name: CONSUMER_GROUP
      value: "ttg-workers"
    - name: TOTAL_PARAMETERS
      value: "$TOTAL_PARAMS"
    - name: CHUNK_SIZE
      value: "$CHUNK_SIZE"
    - name: SIMULATE_WORK_MS
      value: "$SIMULATE_WORK_MS"
    - name: IDLE_TIMEOUT_SECONDS
      value: "180"
    - name: STALE_CHECK_INTERVAL_SECONDS
      value: "15"
    - name: STALE_THRESHOLD_MS
      value: "30000"
    - name: SKIP_ENQUEUE
      value: "false"
    resources:
      requests:
        memory: "128Mi"
        cpu: "100m"
      limits:
        memory: "256Mi"
        cpu: "300m"
EOF
    echo -e "  ${GREEN}✓${NC} Worker $i deployed"
done

print_step "Waiting for workers to start..."
sleep 5

# Verify workers are running
RUNNING=$(kubectl get pods -l ttg.io/mode=fault-demo-standalone --no-headers 2>/dev/null | grep -c "Running" || echo "0")
if [[ "$RUNNING" -lt "$WORKERS" ]]; then
    print_error "Only $RUNNING/$WORKERS workers are running"
    kubectl get pods -l ttg.io/mode=fault-demo-standalone
    exit 1
fi
print_success "All $WORKERS workers are running!"

# ────────────────────────────────────────────────────────────────────────────────
# Step 4: Monitor Progress
# ────────────────────────────────────────────────────────────────────────────────
print_header "Step 4: Processing Tasks"

START_TIME=$(date +%s)
PREV_RESULTS=0

echo ""
while true; do
    RESULTS=$(kubectl exec ttg-redis -- redis-cli XLEN ttg:results 2>/dev/null || echo "0")
    PENDING=$(kubectl exec ttg-redis -- redis-cli XPENDING ttg:tasks ttg-workers 2>/dev/null | head -1 || echo "0")
    CURRENT_TIME=$(date +%s)
    ELAPSED=$((CURRENT_TIME - START_TIME))
    
    # Calculate progress
    PCT=$((RESULTS * 100 / TOTAL_CHUNKS))
    FILLED=$((PCT / 5))
    EMPTY=$((20 - FILLED))
    BAR=$(printf '█%.0s' $(seq 1 $FILLED 2>/dev/null) 2>/dev/null || echo "")
    SPACE=$(printf '░%.0s' $(seq 1 $EMPTY 2>/dev/null) 2>/dev/null || echo "")
    
    # Calculate throughput
    if [[ $ELAPSED -gt 0 ]]; then
        THROUGHPUT=$((RESULTS * CHUNK_SIZE / ELAPSED))
    else
        THROUGHPUT=0
    fi
    
    printf "\r  [${BAR}${SPACE}] ${RESULTS}/${TOTAL_CHUNKS} chunks (${PCT}%%) | ${THROUGHPUT} params/sec | ${ELAPSED}s    "
    
    # Check if complete
    if [[ "$RESULTS" -ge "$TOTAL_CHUNKS" ]]; then
        echo ""
        echo ""
        print_success "All $TOTAL_CHUNKS chunks completed in ${ELAPSED}s!"
        break
    fi
    
    # Fault demo - kill a worker at 30% progress
    if [[ "$FAULT_DEMO" == "true" && "$RESULTS" -ge "$((TOTAL_CHUNKS * 30 / 100))" && "$RESULTS" -lt "$((TOTAL_CHUNKS * 40 / 100))" ]]; then
        echo ""
        echo ""
        print_header "💀 FAULT INJECTION: Killing Worker 1"
        
        # Check if worker-1 exists and is running
        if kubectl get pod ttg-worker-1 &>/dev/null; then
            echo -e "  ${RED}Simulating worker crash...${NC}"
            kubectl delete pod ttg-worker-1 --force --grace-period=0 2>/dev/null || true
            
            echo ""
            echo -e "  ${YELLOW}Worker 1 has been killed!${NC}"
            echo "  The surviving workers will continue processing."
            echo "  If worker-1 had pending tasks, they will be recovered after stale threshold (30s)."
            echo ""
            
            FAULT_DEMO="done"  # Only do this once
            sleep 2
        fi
    fi
    
    # Timeout after 10 minutes
    if [[ $ELAPSED -gt 600 ]]; then
        echo ""
        print_error "Timeout after 10 minutes"
        break
    fi
    
    PREV_RESULTS=$RESULTS
    sleep 2
done

# ────────────────────────────────────────────────────────────────────────────────
# Step 5: Results Summary
# ────────────────────────────────────────────────────────────────────────────────
print_header "Step 5: Results Summary"

END_TIME=$(date +%s)
TOTAL_TIME=$((END_TIME - START_TIME))
FINAL_RESULTS=$(kubectl exec ttg-redis -- redis-cli XLEN ttg:results 2>/dev/null || echo "0")
FINAL_PENDING=$(kubectl exec ttg-redis -- redis-cli XPENDING ttg:tasks ttg-workers 2>/dev/null | head -1 | tr -d '[:space:]' || echo "0")

# Count running and completed workers (handle empty results gracefully)
POD_LIST=$(kubectl get pods -l ttg.io/mode=fault-demo-standalone --no-headers 2>/dev/null || echo "")
if [[ -n "$POD_LIST" ]]; then
    RUNNING_WORKERS=$(echo "$POD_LIST" | grep -c "Running" 2>/dev/null) || RUNNING_WORKERS=0
    COMPLETED_WORKERS=$(echo "$POD_LIST" | grep -c "Completed" 2>/dev/null) || COMPLETED_WORKERS=0
else
    RUNNING_WORKERS=0
    COMPLETED_WORKERS=0
fi

echo -e "  ${CYAN}Workload:${NC}"
echo "    • Total Parameters: $TOTAL_PARAMS"
echo "    • Total Chunks: $TOTAL_CHUNKS"
echo "    • Chunk Size: $CHUNK_SIZE"
echo ""
echo -e "  ${CYAN}Results:${NC}"
echo "    • Chunks Completed: $FINAL_RESULTS / $TOTAL_CHUNKS"
echo "    • Pending Tasks: $FINAL_PENDING"
echo "    • Total Time: ${TOTAL_TIME}s"
if [[ $TOTAL_TIME -gt 0 ]]; then
    echo "    • Throughput: $((TOTAL_PARAMS / TOTAL_TIME)) params/sec"
fi
echo ""
echo -e "  ${CYAN}Workers:${NC}"
echo "    • Running: $RUNNING_WORKERS"
echo "    • Completed: $COMPLETED_WORKERS"
if [[ "$FAULT_DEMO" == "done" ]]; then
    echo "    • Killed (fault demo): 1"
fi
echo ""

if [[ "$FINAL_RESULTS" -ge "$TOTAL_CHUNKS" && "$FINAL_PENDING" -eq "0" ]]; then
    echo -e "  ${GREEN}╔════════════════════════════════════════════════════════════╗${NC}"
    echo -e "  ${GREEN}║                    DEMO SUCCESSFUL! ✓                      ║${NC}"
    echo -e "  ${GREEN}╚════════════════════════════════════════════════════════════╝${NC}"
    if [[ "$FAULT_DEMO" == "done" ]]; then
        echo ""
        echo "  Despite killing a worker, all tasks were completed!"
        echo "  This demonstrates the fault tolerance of the queue architecture."
    fi
else
    echo -e "  ${RED}Demo completed with issues - check logs for details${NC}"
fi

# ────────────────────────────────────────────────────────────────────────────────
# Step 6: Cleanup
# ────────────────────────────────────────────────────────────────────────────────
if [[ "$SKIP_CLEANUP" != "true" ]]; then
    echo ""
    read -p "Press Enter to clean up demo resources (or Ctrl+C to keep them)..."
    
    print_header "Step 6: Cleaning Up"
    
    print_step "Stopping port-forwards..."
    for pid in "${MONITOR_PIDS[@]}"; do
        kill $pid 2>/dev/null || true
    done
    
    print_step "Deleting worker pods..."
    kubectl delete pod -l ttg.io/mode=fault-demo-standalone --wait=false 2>/dev/null || true
    
    print_step "Clearing Redis queues..."
    kubectl exec ttg-redis -- redis-cli FLUSHALL > /dev/null 2>&1 || true
    
    print_success "Cleanup complete!"
fi

echo ""
echo "════════════════════════════════════════════════════════════════════════════════"
echo ""
echo "Thank you for watching the TTG Distributed Computation Demo!"
echo ""
echo "For more information:"
echo "  • Documentation: docs/guides/QUEUE_MODE_GUIDE.md"
echo "  • Architecture: docs/tracking/PROJECT_OVERVIEW.md"
echo "  • Safe cleanup:  ./scripts/cleanup-ttg.sh"
echo ""
