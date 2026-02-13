#!/bin/bash
#
# RabbitMQ queue monitor for TTG demos.
# Shows queue status AND per-worker progress.
#
# Usage:
#   ./scripts/rabbitmq_monitor.sh              # single snapshot
#   ./scripts/rabbitmq_monitor.sh --watch       # auto-refresh every 2s (default)
#   ./scripts/rabbitmq_monitor.sh --watch 5     # auto-refresh every 5s

set -e

WATCH_SECONDS=0

while [[ $# -gt 0 ]]; do
    case $1 in
        --watch)
            # --watch with optional interval: default 2 seconds
            if [[ -n "$2" ]] && [[ "$2" =~ ^[0-9]+$ ]]; then
                WATCH_SECONDS="$2"
                shift 2
            else
                WATCH_SECONDS=2
                shift 1
            fi
            ;;
        *)
            echo "Unknown option: $1"
            echo "Usage: $0 [--watch [SECONDS]]"
            exit 1
            ;;
    esac
done

# Colors
CYAN='\033[0;36m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BOLD='\033[1m'
DIM='\033[2m'
NC='\033[0m'

print_snapshot() {
    local results=0
    local total_tasks=0
    local ready=0
    local unacked=0

    echo -e "${CYAN}╔══════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${CYAN}║${NC}${BOLD} TTG RabbitMQ Monitor ${NC}${DIM}- $(date -u +"%Y-%m-%d %H:%M:%S UTC")${NC}"
    echo -e "${CYAN}╚══════════════════════════════════════════════════════════════╝${NC}"
    echo ""

    # ── Queue Status ──
    echo -e "  ${BOLD}QUEUE STATUS${NC}"
    echo -e "  ${DIM}─────────────────────────────────────────────────────────${NC}"

    # Fetch raw output and filter to only ttg.* queue lines (skip all headers/info)
    local queue_data
    queue_data=$(kubectl exec ttg-rabbitmq -- rabbitmqctl list_queues name messages consumers messages_ready messages_unacknowledged 2>/dev/null | grep "^ttg\." || true)

    if [[ -z "$queue_data" ]]; then
        echo -e "  ${RED}No TTG queues found (RabbitMQ unreachable or queues not declared)${NC}"
        echo ""
        return
    fi

    printf "  ${DIM}%-22s %8s %10s %8s %8s${NC}\n" "Queue" "Msgs" "Consumers" "Ready" "Unacked"
    echo -e "  ${DIM}─────────────────────────────────────────────────────────${NC}"

    while IFS=$'\t' read -r name msgs consumers msgs_ready msgs_unacked; do
        # Clean up values
        msgs=$(echo "$msgs" | tr -d '[:space:]')
        consumers=$(echo "$consumers" | tr -d '[:space:]')
        msgs_ready=$(echo "$msgs_ready" | tr -d '[:space:]')
        msgs_unacked=$(echo "$msgs_unacked" | tr -d '[:space:]')

        # Track key values
        case "$name" in
            ttg.results)  results=$((msgs + 0)) ;;
            ttg.tasks)    total_tasks=$((msgs + 0)); ready=$((msgs_ready + 0)); unacked=$((msgs_unacked + 0)) ;;
        esac

        # Color based on queue type
        local color="$NC"
        case "$name" in
            ttg.results)     color="$GREEN" ;;
            ttg.tasks)       color="$YELLOW" ;;
            ttg.tasks.retry) [[ "$msgs" != "0" ]] && color="$YELLOW" || color="$DIM" ;;
            ttg.tasks.dlq)   [[ "$msgs" != "0" ]] && color="$RED" || color="$DIM" ;;
        esac

        printf "  ${color}%-22s %8s %10s %8s %8s${NC}\n" "$name" "$msgs" "$consumers" "$msgs_ready" "$msgs_unacked"
    done <<< "$queue_data"

    echo ""

    # ── Progress Bar ──
    local total_chunks=100
    if [[ "$results" -gt 0 || "$total_tasks" -gt 0 ]]; then
        total_chunks=$((results + total_tasks))
    fi

    if [[ "$total_chunks" -gt 0 ]]; then
        local pct=$((results * 100 / total_chunks))
        local filled=$((pct / 5))
        local empty=$((20 - filled))
        local bar=""
        for ((i=0; i<filled; i++)); do bar+="█"; done
        for ((i=0; i<empty; i++)); do bar+="░"; done

        local status_color="$YELLOW"
        [[ "$pct" -ge 100 ]] && status_color="$GREEN"

        echo -e "  ${BOLD}PROGRESS${NC}"
        echo -e "  ${DIM}─────────────────────────────────────────────────────────${NC}"
        echo -e "  ${status_color}[${bar}] ${results}/${total_chunks} chunks (${pct}%)${NC}"

        if [[ "$unacked" -gt 0 ]]; then
            echo -e "  ${DIM}Processing now: ${unacked} chunks in flight${NC}"
        fi
        echo ""
    fi

    # ── Worker Status (only ttg-worker-* pods, not infrastructure) ──
    echo -e "  ${BOLD}WORKER STATUS${NC}"
    echo -e "  ${DIM}─────────────────────────────────────────────────────────${NC}"

    local worker_pods
    worker_pods=$(kubectl get pods --no-headers 2>/dev/null | grep "^ttg-worker-" || true)

    if [[ -z "$worker_pods" ]]; then
        echo -e "  ${DIM}No TTG worker pods found${NC}"
    else
        local running=0
        local completed=0
        local failed=0
        local total_pods=0

        while read -r pod_name pod_ready pod_status pod_restarts pod_age; do
            total_pods=$((total_pods + 1))
            local icon=""
            local color="$NC"

            case "$pod_status" in
                Running)
                    icon="▶"
                    color="$GREEN"
                    running=$((running + 1))
                    ;;
                Completed)
                    icon="✓"
                    color="$DIM"
                    completed=$((completed + 1))
                    ;;
                Error|CrashLoopBackOff|OOMKilled)
                    icon="✗"
                    color="$RED"
                    failed=$((failed + 1))
                    ;;
                *)
                    icon="?"
                    color="$YELLOW"
                    ;;
            esac

            # Get the node the worker is on
            local node
            node=$(kubectl get pod "$pod_name" -o jsonpath='{.spec.nodeName}' 2>/dev/null || echo "unknown")

            printf "  ${color}%s %-45s %-12s %s${NC}\n" "$icon" "$pod_name" "$pod_status" "$node"
        done <<< "$worker_pods"

        echo ""
        echo -e "  ${DIM}Total: ${total_pods} pods | ${NC}${GREEN}Running: ${running}${NC} ${DIM}| Completed: ${completed}${NC}${RED}$([ "$failed" -gt 0 ] && echo " | Failed: ${failed}")${NC}"
    fi

    echo ""

    # ── Fault Events (detect killed workers from CURRENT demo run only) ──
    # Extract the run ID from current worker pods (e.g. "1770776579" from "ttg-worker-rabbitmq-1770776579-0")
    local current_run_id=""
    if [[ -n "$worker_pods" ]]; then
        current_run_id=$(echo "$worker_pods" | head -1 | awk '{print $1}' | grep -oP 'ttg-worker-rabbitmq-\K[0-9]+' || true)
    fi

    if [[ -n "$current_run_id" ]]; then
        local kill_events
        kill_events=$(kubectl get events --field-selector reason=Killing --no-headers 2>/dev/null | grep "ttg-worker-.*${current_run_id}" || true)

        if [[ -n "$kill_events" ]]; then
            echo -e "  ${RED}${BOLD}⚠ FAULT EVENTS${NC}"
            echo -e "  ${DIM}─────────────────────────────────────────────────────────${NC}"

            while read -r evt_last evt_type evt_reason evt_object evt_message; do
                # evt_object is like "pod/ttg-worker-rabbitmq-xxx-1"
                local pod_name="${evt_object#pod/}"
                echo -e "  ${RED}✗ ${pod_name}${NC} — killed ${evt_last} ago"
            done <<< "$kill_events"

            # Check if work still completed despite the kill
            if [[ "$results" -gt 0 && "$total_tasks" -eq 0 ]]; then
                echo -e "  ${GREEN}${BOLD}✓ FAULT TOLERANT${NC}${GREEN} — all ${results} chunks completed despite worker failure${NC}"
            elif [[ "$total_tasks" -gt 0 ]]; then
                echo -e "  ${YELLOW}⏳ Recovery in progress — ${results} done, ${total_tasks} remaining${NC}"
            fi
            echo ""
        fi
    fi

    # ── Worker Logs Summary (last progress/completion line per worker) ──
    if [[ -n "$worker_pods" ]]; then
        local has_logs=false
        while read -r pod_name pod_ready pod_status pod_restarts pod_age; do
            if [[ "$pod_status" == "Running" || "$pod_status" == "Completed" ]]; then
                local last_progress
                last_progress=$(kubectl logs "$pod_name" --tail=10 2>/dev/null | grep -iE "progress|completed|processed|chunk|param" | tail -1 || true)
                if [[ -n "$last_progress" ]]; then
                    if [[ "$has_logs" == "false" ]]; then
                        echo -e "  ${BOLD}LATEST WORKER OUTPUT${NC}"
                        echo -e "  ${DIM}─────────────────────────────────────────────────────────${NC}"
                        has_logs=true
                    fi
                    # Extract short pod name (last segment after last -)
                    local short_name="${pod_name##*-}"
                    echo -e "  ${DIM}[worker-${short_name}]${NC} ${last_progress}"
                fi
            fi
        done <<< "$worker_pods"
        [[ "$has_logs" == "true" ]] && echo ""
    fi
}

if [[ "$WATCH_SECONDS" -gt 0 ]]; then
    while true; do
        clear
        print_snapshot
        echo -e "  ${DIM}Refreshing every ${WATCH_SECONDS}s · Press Ctrl+C to exit${NC}"
        sleep "$WATCH_SECONDS"
    done
else
    print_snapshot
fi
