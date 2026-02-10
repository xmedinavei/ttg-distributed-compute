#!/bin/bash
#
# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║               TTG SAFE CLEANUP SCRIPT                                         ║
# ║                                                                               ║
# ║  ⚠️  THIS SCRIPT ONLY TOUCHES TTG RESOURCES - NOTHING ELSE                   ║
# ║                                                                               ║
# ║  PROTECTED:                                                                   ║
# ║  • All Docker containers not explicitly tagged with 'ttg'                    ║
# ║  • All Docker images not tagged with 'ttg-worker'                            ║
# ║  • MongoDB containers (local2874, etc.)                                      ║
# ║  • Any system containers                                                      ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
#
# USAGE:
#   ./scripts/cleanup-ttg.sh [OPTIONS]
#
# OPTIONS:
#   --all           Clean TTG Kubernetes demo resources only
#   --pods          Remove TTG pods/jobs only
#   --redis         Clear Redis queue data in ttg-redis only
#   --rabbitmq      Purge TTG RabbitMQ queues only
#   --dry-run       Show what would be deleted (no changes)
#   --force         Skip confirmation prompts
#   --help          Show this help
#
# EXAMPLES:
#   # Preview what would be deleted
#   ./scripts/cleanup-ttg.sh --all --dry-run
#
#   # Quick cleanup of demo pods
#   ./scripts/cleanup-ttg.sh --pods --force
#
#   # Full cleanup with confirmation
#   ./scripts/cleanup-ttg.sh --all
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

# Options
CLEAN_CLUSTER=false
CLEAN_PODS=false
CLEAN_REDIS=false
CLEAN_IMAGES=false
DRY_RUN=false
FORCE=false

# Safety patterns - resources we WILL touch
TTG_CLUSTER_NAME="ttg-sandbox"
TTG_POD_LABELS=(
    "ttg.io/project=distributed-compute"
)
TTG_JOB_LABELS=(
    "ttg.io/project=distributed-compute"
)
PURGE_RABBITMQ=false

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

print_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
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

print_dry_run() {
    echo -e "${MAGENTA}[DRY-RUN]${NC} $1"
}

show_help() {
    sed -n '2,/^# ═══════════════════════════════════════════════════════════════════════════════$/p' "$0" | grep "^#" | sed 's/^# //' | sed 's/^#//'
    exit 0
}

confirm_action() {
    if [[ "$FORCE" == "true" ]]; then
        return 0
    fi
    
    echo ""
    echo -e "${YELLOW}┌─────────────────────────────────────────────────────────────────────────────┐${NC}"
    echo -e "${YELLOW}│ CONFIRMATION REQUIRED                                                       │${NC}"
    echo -e "${YELLOW}└─────────────────────────────────────────────────────────────────────────────┘${NC}"
    echo ""
    read -p "Are you sure you want to proceed? (yes/no): " response
    if [[ "$response" != "yes" ]]; then
        echo "Aborted."
        exit 0
    fi
}

# ┌──────────────────────────────────────────────────────────────────────────────┐
# │                          SAFETY VERIFICATION                                  │
# └──────────────────────────────────────────────────────────────────────────────┘

show_protected_resources() {
    print_header "🛡️  PROTECTED RESOURCES (will NOT be touched)"
    
    echo -e "  ${GREEN}Docker Containers:${NC}"
    docker ps --format "    • {{.Names}} ({{.Image}})" | grep -v "ttg-sandbox\|ttg-worker" | head -10 || echo "    (none found)"
    
    echo ""
    echo -e "  ${GREEN}Docker Images (non-TTG):${NC}"
    docker images --format "    • {{.Repository}}:{{.Tag}}" | grep -v "ttg-worker\|kindest" | head -10 || echo "    (none found)"
    
    echo ""
    echo -e "  ${CYAN}These resources are SAFE and will NOT be modified.${NC}"
    echo ""
}

show_ttg_resources() {
    print_header "🎯 TTG RESOURCES (will be cleaned)"
    
    local found_any=false
    
    # Kind cluster
    echo -e "  ${YELLOW}Kind Cluster:${NC}"
    if kind get clusters 2>/dev/null | grep -q "^${TTG_CLUSTER_NAME}$"; then
        echo "    • $TTG_CLUSTER_NAME"
        found_any=true
    else
        echo "    (none found)"
    fi
    
    # Kubernetes pods
    if kubectl cluster-info --context kind-$TTG_CLUSTER_NAME &>/dev/null 2>&1; then
        echo ""
        echo -e "  ${YELLOW}Kubernetes Pods:${NC}"
        local pods=$(kubectl get pods --no-headers 2>/dev/null | awk '{print $1}' || echo "")
        if [[ -n "$pods" ]]; then
            echo "$pods" | while read pod; do
                echo "    • $pod"
            done
            found_any=true
        else
            echo "    (none found)"
        fi
        
        echo ""
        echo -e "  ${YELLOW}Kubernetes Jobs:${NC}"
        local jobs=$(kubectl get jobs --no-headers 2>/dev/null | awk '{print $1}' || echo "")
        if [[ -n "$jobs" ]]; then
            echo "$jobs" | while read job; do
                echo "    • $job"
            done
            found_any=true
        else
            echo "    (none found)"
        fi
    fi
    
    # Kind-related containers (informational only)
    echo ""
    echo -e "  ${YELLOW}Kind Docker Containers:${NC}"
    local kind_containers=$(docker ps -a --format "{{.Names}}" | grep "$TTG_CLUSTER_NAME" || echo "")
    if [[ -n "$kind_containers" ]]; then
        echo "$kind_containers" | while read c; do
            echo "    • $c"
        done
        found_any=true
    else
        echo "    (none found)"
    fi
    
    echo ""
    
    if [[ "$found_any" == "false" ]]; then
        print_success "No TTG resources found - nothing to clean!"
        exit 0
    fi
}

# ┌──────────────────────────────────────────────────────────────────────────────┐
# │                            CLEANUP FUNCTIONS                                  │
# └──────────────────────────────────────────────────────────────────────────────┘

clean_pods() {
    print_header "Cleaning TTG Pods and Jobs"
    
    if ! kubectl cluster-info --context kind-$TTG_CLUSTER_NAME &>/dev/null 2>&1; then
        print_warning "Kind cluster not accessible - skipping pod cleanup"
        return
    fi
    
    # Delete pods by label
    for label in "${TTG_POD_LABELS[@]}"; do
        if [[ "$DRY_RUN" == "true" ]]; then
            pods=$(kubectl get pods -l "$label" --no-headers 2>/dev/null | awk '{print $1}' || echo "")
            if [[ -n "$pods" ]]; then
                echo "$pods" | while read pod; do
                    print_dry_run "Would delete pod: $pod"
                done
            fi
        else
            kubectl delete pods -l "$label" --wait=false 2>/dev/null || true
        fi
    done
    
    # Delete jobs by label
    for label in "${TTG_JOB_LABELS[@]}"; do
        if [[ "$DRY_RUN" == "true" ]]; then
            jobs=$(kubectl get jobs -l "$label" --no-headers 2>/dev/null | awk '{print $1}' || echo "")
            if [[ -n "$jobs" ]]; then
                echo "$jobs" | while read job; do
                    print_dry_run "Would delete job: $job"
                done
            fi
        else
            kubectl delete jobs -l "$label" --wait=false 2>/dev/null || true
        fi
    done
    
    if [[ "$DRY_RUN" != "true" ]]; then
        print_success "Pods and jobs cleaned!"
    fi
}

clean_redis() {
    print_header "Cleaning Redis Data"
    
    if ! kubectl cluster-info --context kind-$TTG_CLUSTER_NAME &>/dev/null 2>&1; then
        print_warning "Kind cluster not accessible - skipping Redis cleanup"
        return
    fi
    
    if ! kubectl get pod ttg-redis &>/dev/null 2>&1; then
        print_warning "Redis pod not found - skipping"
        return
    fi
    
    if [[ "$DRY_RUN" == "true" ]]; then
        print_dry_run "Would clear all Redis data (FLUSHALL)"
        
        # Show what data exists
        echo ""
        echo "  Current Redis data:"
        echo "    • ttg:tasks: $(kubectl exec ttg-redis -- redis-cli XLEN ttg:tasks 2>/dev/null || echo "0") messages"
        echo "    • ttg:results: $(kubectl exec ttg-redis -- redis-cli XLEN ttg:results 2>/dev/null || echo "0") messages"
    else
        kubectl exec ttg-redis -- redis-cli FLUSHALL > /dev/null 2>&1 || true
        print_success "Redis data cleared!"
    fi
}

clean_cluster() {
    print_warning "Cluster deletion is disabled in strict cleanup mode."
}

clean_images() {
    print_warning "Docker image cleanup is disabled in strict cleanup mode."
}

clean_rabbitmq() {
    print_header "Purging TTG RabbitMQ Queues"
    if ! kubectl cluster-info --context kind-$TTG_CLUSTER_NAME &>/dev/null 2>&1; then
        print_warning "Kind cluster not accessible - skipping RabbitMQ cleanup"
        return
    fi
    if ! kubectl get pod ttg-rabbitmq &>/dev/null 2>&1; then
        print_warning "RabbitMQ pod not found - skipping"
        return
    fi
    if [[ "$DRY_RUN" == "true" ]]; then
        print_dry_run "Would purge queues: ttg.tasks, ttg.tasks.retry, ttg.tasks.dlq, ttg.results"
    else
        kubectl exec ttg-rabbitmq -- rabbitmqctl purge_queue ttg.tasks >/dev/null 2>&1 || true
        kubectl exec ttg-rabbitmq -- rabbitmqctl purge_queue ttg.tasks.retry >/dev/null 2>&1 || true
        kubectl exec ttg-rabbitmq -- rabbitmqctl purge_queue ttg.tasks.dlq >/dev/null 2>&1 || true
        kubectl exec ttg-rabbitmq -- rabbitmqctl purge_queue ttg.results >/dev/null 2>&1 || true
        print_success "RabbitMQ queues purged!"
    fi
}

# ┌──────────────────────────────────────────────────────────────────────────────┐
# │                            PARSE ARGUMENTS                                    │
# └──────────────────────────────────────────────────────────────────────────────┘

if [[ $# -eq 0 ]]; then
    show_help
fi

while [[ $# -gt 0 ]]; do
    case $1 in
        --all)
            CLEAN_PODS=true
            CLEAN_REDIS=true
            PURGE_RABBITMQ=true
            shift
            ;;
        --pods)
            CLEAN_PODS=true
            shift
            ;;
        --redis)
            CLEAN_REDIS=true
            shift
            ;;
        --rabbitmq)
            PURGE_RABBITMQ=true
            shift
            ;;
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --force)
            FORCE=true
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
# │                               MAIN CLEANUP                                    │
# └──────────────────────────────────────────────────────────────────────────────┘

print_header "🧹 TTG Safe Cleanup"

if [[ "$DRY_RUN" == "true" ]]; then
    echo -e "  ${MAGENTA}╔════════════════════════════════════════════════════════════╗${NC}"
    echo -e "  ${MAGENTA}║               DRY-RUN MODE - NO CHANGES WILL BE MADE       ║${NC}"
    echo -e "  ${MAGENTA}╚════════════════════════════════════════════════════════════╝${NC}"
    echo ""
fi

# Show what's protected first
show_protected_resources

# Show what will be cleaned
show_ttg_resources

# Confirm before proceeding (unless dry-run)
if [[ "$DRY_RUN" != "true" ]]; then
    confirm_action
fi

# Execute cleanup in proper order
if [[ "$CLEAN_REDIS" == "true" ]]; then
    clean_redis
fi

if [[ "$PURGE_RABBITMQ" == "true" ]]; then
    clean_rabbitmq
fi

if [[ "$CLEAN_PODS" == "true" ]]; then
    clean_pods
fi

# Final summary
echo ""
if [[ "$DRY_RUN" == "true" ]]; then
    echo -e "${MAGENTA}════════════════════════════════════════════════════════════════════════════════${NC}"
    echo ""
    echo -e "  ${MAGENTA}DRY-RUN COMPLETE${NC}"
    echo "  No changes were made. Run without --dry-run to execute cleanup."
else
    echo -e "${GREEN}════════════════════════════════════════════════════════════════════════════════${NC}"
    echo ""
    print_success "TTG Cleanup Complete!"
    echo ""
    echo "  Your non-TTG Docker resources remain untouched."
fi
echo ""
