#!/bin/bash
#
# TTG one-command demo runner (Redis or RabbitMQ backend).
# Safety-first: this script only manipulates TTG-labeled Kubernetes resources.

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
MAGENTA='\033[0;35m'
NC='\033[0m'

SCALE="small"
WORKERS=3
FAULT_DEMO=false
MONITOR_MODE="none"
SKIP_CLEANUP=false
BACKEND="redis"
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CLUSTER_NAME="ttg-sandbox"
IMAGE_TAG="ttg-worker:v1.3.0"
RUN_ID="$(date +%s)"
MONITOR_PIDS=()

print_header() {
    echo ""
    echo -e "${CYAN}╔══════════════════════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${CYAN}║${NC} $1"
    echo -e "${CYAN}╚══════════════════════════════════════════════════════════════════════════════╝${NC}"
    echo ""
}
print_step() { echo -e "${YELLOW}▶ $1${NC}"; }
print_success() { echo -e "${GREEN}✓ $1${NC}"; }
print_error() { echo -e "${RED}✗ $1${NC}"; }
print_info() { echo -e "${BLUE}ℹ $1${NC}"; }

show_help() {
    cat <<EOF
Usage: ./scripts/run-demo.sh [OPTIONS]

Options:
  --backend redis|rabbitmq    Queue backend (default: redis)
  --scale small|medium        Workload scale (default: small)
  --workers N                 Worker count (default: 3)
  --fault-demo                Kill one worker at ~30% progress
  --monitor cli|web|both|none Monitoring mode (default: none)
  --skip-cleanup              Keep resources after demo
  --help                      Show this help
EOF
}

get_scale_config() {
    case "$SCALE" in
        small) TOTAL_PARAMS=1000; CHUNK_SIZE=10; SIMULATE_WORK_MS=100 ;;
        medium) TOTAL_PARAMS=10000; CHUNK_SIZE=100; SIMULATE_WORK_MS=10 ;;
        *) print_error "Unknown scale: $SCALE"; exit 1 ;;
    esac
    TOTAL_CHUNKS=$((TOTAL_PARAMS / CHUNK_SIZE))
}

queue_label_selector() {
    if [[ "$BACKEND" == "rabbitmq" ]]; then
        echo "ttg.io/project=distributed-compute,ttg.io/queue-backend=rabbitmq,ttg.io/run-id=$RUN_ID"
    else
        echo "ttg.io/project=distributed-compute,ttg.io/queue-backend=redis,ttg.io/run-id=$RUN_ID"
    fi
}

check_prerequisites() {
    print_step "Checking prerequisites..."
    command -v kubectl >/dev/null || { print_error "kubectl not found"; exit 1; }
    command -v kind >/dev/null || { print_error "kind not found"; exit 1; }
    command -v docker >/dev/null || { print_error "docker not found"; exit 1; }

    if ! kubectl cluster-info --context "kind-${CLUSTER_NAME}" >/dev/null 2>&1; then
        print_error "Kind cluster '${CLUSTER_NAME}' not accessible"
        echo "Run: kind create cluster --name ${CLUSTER_NAME} --config k8s/local/kind-config.yaml"
        exit 1
    fi

    if [[ "$BACKEND" == "rabbitmq" ]]; then
        kubectl apply -f "$PROJECT_DIR/k8s/manifests/rabbitmq.yaml" >/dev/null
        kubectl wait --for=condition=ready pod/ttg-rabbitmq --timeout=120s >/dev/null
        kubectl exec ttg-rabbitmq -- rabbitmq-diagnostics -q ping >/dev/null
    else
        kubectl apply -f "$PROJECT_DIR/k8s/manifests/redis.yaml" >/dev/null
        kubectl wait --for=condition=ready pod/ttg-redis --timeout=120s >/dev/null
        kubectl exec ttg-redis -- redis-cli PING >/dev/null
    fi

    docker build -t "$IMAGE_TAG" -f "$PROJECT_DIR/docker/Dockerfile" "$PROJECT_DIR" >/dev/null
    kind load docker-image "$IMAGE_TAG" --name "$CLUSTER_NAME" >/dev/null
    print_success "Prerequisites ready"
}

safe_prepare_environment() {
    print_header "Step 1: Prepare Environment (TTG-only)"
    print_step "Cleaning previous TTG demo workers by strict labels"
    kubectl delete pod -l "ttg.io/project=distributed-compute,ttg.io/queue-backend=$BACKEND" --wait=false >/dev/null 2>&1 || true
    kubectl delete job -l "ttg.io/project=distributed-compute,ttg.io/queue-backend=$BACKEND" --wait=false >/dev/null 2>&1 || true

    if [[ "$BACKEND" == "rabbitmq" ]]; then
        print_step "Purging TTG RabbitMQ queues only"
        kubectl exec ttg-rabbitmq -- rabbitmqctl purge_queue ttg.tasks >/dev/null 2>&1 || true
        kubectl exec ttg-rabbitmq -- rabbitmqctl purge_queue ttg.tasks.retry >/dev/null 2>&1 || true
        kubectl exec ttg-rabbitmq -- rabbitmqctl purge_queue ttg.tasks.dlq >/dev/null 2>&1 || true
        kubectl exec ttg-rabbitmq -- rabbitmqctl purge_queue ttg.results >/dev/null 2>&1 || true
    else
        print_step "Clearing TTG Redis DB (ttg-redis pod only)"
        kubectl exec ttg-redis -- redis-cli FLUSHALL >/dev/null
    fi
    sleep 1
    print_success "Environment ready"
}

start_monitoring() {
    if [[ "$MONITOR_MODE" == "none" ]]; then
        return
    fi

    print_header "Step 2: Monitoring Setup"
    if [[ "$BACKEND" == "rabbitmq" ]]; then
        if [[ "$MONITOR_MODE" == "cli" || "$MONITOR_MODE" == "both" ]]; then
            print_info "Run in another terminal:"
            echo "  ./scripts/rabbitmq_monitor.sh --watch 2"
        fi
        if [[ "$MONITOR_MODE" == "web" || "$MONITOR_MODE" == "both" ]]; then
            kubectl port-forward pod/ttg-rabbitmq 15672:15672 >/dev/null 2>&1 &
            MONITOR_PIDS+=($!)
            sleep 2
            print_info "RabbitMQ UI: http://localhost:15672 (guest/guest)"
        fi
    else
        if [[ "$MONITOR_MODE" == "cli" || "$MONITOR_MODE" == "both" ]]; then
            kubectl port-forward pod/ttg-redis 6379:6379 >/dev/null 2>&1 &
            MONITOR_PIDS+=($!)
            sleep 2
            print_info "Run in another terminal:"
            echo "  python3 $PROJECT_DIR/scripts/queue_monitor.py --total-params $TOTAL_PARAMS"
        fi
        if [[ "$MONITOR_MODE" == "web" || "$MONITOR_MODE" == "both" ]]; then
            kubectl apply -f "$PROJECT_DIR/k8s/manifests/redis-insight.yaml" >/dev/null
            kubectl port-forward pod/redis-insight 8001:8001 >/dev/null 2>&1 &
            MONITOR_PIDS+=($!)
            sleep 2
            print_info "RedisInsight: http://localhost:8001"
        fi
    fi
}

deploy_workers() {
    print_header "Step 3: Deploy $WORKERS Workers ($BACKEND)"
    for i in $(seq 0 $((WORKERS - 1))); do
        cat <<EOF | kubectl apply -f - >/dev/null
apiVersion: v1
kind: Pod
metadata:
  name: ttg-worker-${BACKEND}-${RUN_ID}-${i}
  labels:
    app.kubernetes.io/name: ttg-worker
    ttg.io/project: distributed-compute
    ttg.io/mode: live-demo
    ttg.io/worker-id: "$i"
    ttg.io/queue-backend: "$BACKEND"
    ttg.io/run-id: "$RUN_ID"
spec:
  restartPolicy: Never
  containers:
  - name: worker
    image: $IMAGE_TAG
    imagePullPolicy: IfNotPresent
    env:
    - name: WORKER_ID
      value: "$i"
    - name: USE_QUEUE
      value: "true"
    - name: QUEUE_BACKEND
      value: "$BACKEND"
    - name: REDIS_HOST
      value: "ttg-redis"
    - name: REDIS_PORT
      value: "6379"
    - name: RABBITMQ_HOST
      value: "ttg-rabbitmq"
    - name: RABBITMQ_PORT
      value: "5672"
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
    resources:
      requests: { memory: "128Mi", cpu: "100m" }
      limits: { memory: "256Mi", cpu: "300m" }
EOF
        print_success "Worker $i deployed"
    done
}

get_results_count() {
    if [[ "$BACKEND" == "rabbitmq" ]]; then
        kubectl exec ttg-rabbitmq -- rabbitmqctl list_queues name messages 2>/dev/null | awk '$1=="ttg.results"{print $2+0}' || echo 0
    else
        kubectl exec ttg-redis -- redis-cli XLEN ttg:results 2>/dev/null || echo 0
    fi
}

monitor_progress() {
    print_header "Step 4: Processing Tasks"
    local selector
    selector="$(queue_label_selector)"
    START_TIME=$(date +%s)
    local fault_done=false
    local last_results=0
    local empty_worker_checks=0

    while true; do
        RESULTS=$(get_results_count | tail -n1 | tr -d '\r[:space:]')
        [[ -z "$RESULTS" ]] && RESULTS=$last_results
        if [[ "$RESULTS" -lt "$last_results" ]]; then
            # RabbitMQ CLI can transiently fail; keep monotonic display.
            RESULTS=$last_results
        fi
        last_results=$RESULTS
        ELAPSED=$(( $(date +%s) - START_TIME ))
        PCT=$(( RESULTS * 100 / TOTAL_CHUNKS ))
        FILLED=$(( PCT / 5 ))
        EMPTY=$(( 20 - FILLED ))
        BAR=$(printf '█%.0s' $(seq 1 $FILLED 2>/dev/null) 2>/dev/null || true)
        SPACE=$(printf '░%.0s' $(seq 1 $EMPTY 2>/dev/null) 2>/dev/null || true)
        THROUGHPUT=0
        if [[ $ELAPSED -gt 0 ]]; then THROUGHPUT=$(( RESULTS * CHUNK_SIZE / ELAPSED )); fi
        printf "\r  [${BAR}${SPACE}] ${RESULTS}/${TOTAL_CHUNKS} chunks (${PCT}%%) | ${THROUGHPUT} params/sec | ${ELAPSED}s   "

        if [[ "$RESULTS" -ge "$TOTAL_CHUNKS" ]]; then
            echo ""
            print_success "Completed $RESULTS/$TOTAL_CHUNKS chunks in ${ELAPSED}s"
            break
        fi

        local active_workers
        active_workers=$(kubectl get pods -l "$selector" --no-headers 2>/dev/null | awk '$3=="Running"{count++} END {print count+0}')
        if [[ "$active_workers" -eq 0 ]]; then
            empty_worker_checks=$((empty_worker_checks + 1))
            if [[ "$empty_worker_checks" -ge 3 ]]; then
                echo ""
                print_error "No active workers found for this run. Stopping monitor."
                break
            fi
        else
            empty_worker_checks=0
        fi

        if [[ "$FAULT_DEMO" == "true" && "$fault_done" == "false" && "$RESULTS" -ge "$((TOTAL_CHUNKS * 30 / 100))" ]]; then
            echo ""
            print_header "Fault Injection (TTG-only)"
            local victim
            victim="$(kubectl get pods -l "$selector" --no-headers | awk 'NR==2{print $1}')"
            if [[ -n "$victim" ]]; then
                print_step "Deleting worker pod: $victim"
                kubectl delete pod "$victim" --force --grace-period=0 >/dev/null 2>&1 || true
                fault_done=true
                print_info "Fault injected. Remaining workers should continue."
            fi
        fi

        if [[ "$ELAPSED" -gt 900 ]]; then
            echo ""
            print_error "Timeout after 15 minutes"
            break
        fi
        sleep 2
    done
}

print_summary() {
    print_header "Step 5: Summary"
    local selector
    selector="$(queue_label_selector)"
    local final_results
    final_results="$(get_results_count | tail -n1 | tr -d '\r[:space:]')"
    local total_time=$(( $(date +%s) - START_TIME ))
    local pods
    pods="$(kubectl get pods -l "$selector" --no-headers 2>/dev/null || true)"
    local running completed
    running=$(echo "$pods" | awk '$3=="Running"{count++} END {print count+0}')
    completed=$(echo "$pods" | awk '$3=="Completed"{count++} END {print count+0}')
    [[ -z "$running" ]] && running=0
    [[ -z "$completed" ]] && completed=0

    echo "  Backend: $BACKEND"
    echo "  Total params: $TOTAL_PARAMS"
    echo "  Chunks: $final_results/$TOTAL_CHUNKS"
    echo "  Time: ${total_time}s"
    if [[ "$total_time" -gt 0 ]]; then
        echo "  Throughput: $((TOTAL_PARAMS / total_time)) params/sec"
    fi
    echo "  Workers running: $running, completed: $completed"
}

cleanup_demo() {
    local selector
    selector="$(queue_label_selector)"
    print_header "Step 6: Cleanup (Strict TTG-only)"
    print_step "Stopping monitor port-forwards"
    for pid in "${MONITOR_PIDS[@]}"; do kill "$pid" >/dev/null 2>&1 || true; done

    print_step "Deleting TTG demo worker pods only"
    kubectl delete pod -l "$selector" --wait=false >/dev/null 2>&1 || true

    if [[ "$BACKEND" == "rabbitmq" ]]; then
        print_step "Purging TTG RabbitMQ queues only"
        kubectl exec ttg-rabbitmq -- rabbitmqctl purge_queue ttg.tasks >/dev/null 2>&1 || true
        kubectl exec ttg-rabbitmq -- rabbitmqctl purge_queue ttg.tasks.retry >/dev/null 2>&1 || true
        kubectl exec ttg-rabbitmq -- rabbitmqctl purge_queue ttg.tasks.dlq >/dev/null 2>&1 || true
        kubectl exec ttg-rabbitmq -- rabbitmqctl purge_queue ttg.results >/dev/null 2>&1 || true
    else
        print_step "Clearing TTG Redis queue data (ttg-redis only)"
        kubectl exec ttg-redis -- redis-cli FLUSHALL >/dev/null 2>&1 || true
    fi
    print_success "Cleanup complete. Non-TTG Docker resources untouched."
}

while [[ $# -gt 0 ]]; do
    case $1 in
        --backend) BACKEND="$2"; shift 2 ;;
        --scale) SCALE="$2"; shift 2 ;;
        --workers) WORKERS="$2"; shift 2 ;;
        --fault-demo) FAULT_DEMO=true; shift ;;
        --monitor) MONITOR_MODE="$2"; shift 2 ;;
        --skip-cleanup) SKIP_CLEANUP=true; shift ;;
        --help|-h) show_help; exit 0 ;;
        *) print_error "Unknown option: $1"; show_help; exit 1 ;;
    esac
done

if [[ "$BACKEND" != "redis" && "$BACKEND" != "rabbitmq" ]]; then
    print_error "Invalid backend: $BACKEND"
    exit 1
fi

print_header "TTG Distributed Computation Demo"
get_scale_config
echo -e "${MAGENTA}Configuration:${NC}"
echo "  • Backend: $BACKEND"
echo "  • Scale: $SCALE"
echo "  • Workers: $WORKERS"
echo "  • Parameters: $TOTAL_PARAMS"
echo "  • Chunk size: $CHUNK_SIZE"
echo "  • Monitor: $MONITOR_MODE"
echo "  • Fault demo: $FAULT_DEMO"

check_prerequisites
safe_prepare_environment
start_monitoring
deploy_workers
monitor_progress
print_summary

if [[ "$SKIP_CLEANUP" != "true" ]]; then
    read -r -p "Press Enter to cleanup TTG demo resources..."
    cleanup_demo
fi

echo ""
echo "Demo finished."
echo "Docs: docs/guides/DEMO_GUIDE.md"
