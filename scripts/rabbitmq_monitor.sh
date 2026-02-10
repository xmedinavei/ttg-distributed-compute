#!/bin/bash
#
# RabbitMQ queue monitor for TTG demos.
#
# Usage:
#   ./scripts/rabbitmq_monitor.sh
#   ./scripts/rabbitmq_monitor.sh --watch 2

set -e

WATCH_SECONDS=0

while [[ $# -gt 0 ]]; do
    case $1 in
        --watch)
            WATCH_SECONDS="$2"
            shift 2
            ;;
        *)
            echo "Unknown option: $1"
            echo "Usage: $0 [--watch SECONDS]"
            exit 1
            ;;
    esac
done

print_snapshot() {
    echo "============================================================"
    echo "RabbitMQ Queue Snapshot - $(date -u +"%Y-%m-%d %H:%M:%S UTC")"
    echo "============================================================"
    kubectl exec ttg-rabbitmq -- rabbitmqctl list_queues name messages consumers messages_ready messages_unacknowledged
    echo
}

if [[ "$WATCH_SECONDS" -gt 0 ]]; then
    while true; do
        clear
        print_snapshot
        sleep "$WATCH_SECONDS"
    done
else
    print_snapshot
fi
