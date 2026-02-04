#!/usr/bin/env python3
"""
TTG Result Aggregation Script
=============================
Reads all results from Redis ttg:results stream and computes aggregate statistics.

Usage:
    # With port-forward to different port (if 6379 is busy):
    kubectl port-forward pod/ttg-redis 16379:6379 &
    python scripts/aggregate_results.py --port 16379

    # Or run directly if 6379 is available:
    python scripts/aggregate_results.py

Author: TTG Team
Version: 1.2.0
"""

import argparse
import json
import os
import sys
from datetime import datetime
from typing import Any

# Add src to path for local imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description='Aggregate TTG computation results from Redis',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python scripts/aggregate_results.py
    python scripts/aggregate_results.py --host localhost --port 16379
    python scripts/aggregate_results.py --json
        """
    )
    parser.add_argument('--host', default='localhost',
                        help='Redis host (default: localhost)')
    parser.add_argument('--port', type=int, default=6379,
                        help='Redis port (default: 6379)')
    parser.add_argument('--json', action='store_true', help='Output as JSON')
    parser.add_argument('--verbose', '-v', action='store_true',
                        help='Show detailed per-chunk results')
    return parser.parse_args()


def aggregate_results(host: str = 'localhost', port: int = 6379, verbose: bool = False) -> dict[str, Any]:
    """
    Read all results from Redis and compute aggregate statistics.

    Returns a dictionary with:
    - total_params: Total parameters processed
    - total_chunks: Total chunks processed
    - grand_sum: Sum of all computed values
    - global_min: Minimum value across all chunks
    - global_max: Maximum value across all chunks  
    - overall_avg: Grand sum / total params
    - total_processing_time: Sum of all chunk durations
    - avg_chunk_time: Average time per chunk
    - throughput: Params per second
    - worker_distribution: Dict of worker_id -> chunks processed
    - first_result_at: Timestamp of first result
    - last_result_at: Timestamp of last result
    - wall_clock_time: Time from first to last result
    """
    try:
        import redis
    except ImportError:
        print("ERROR: redis package not installed. Run: pip install redis",
              file=sys.stderr)
        sys.exit(1)

    # Connect to Redis
    try:
        r = redis.Redis(host=host, port=port, decode_responses=True)
        r.ping()
    except redis.ConnectionError as e:
        print(
            f"ERROR: Cannot connect to Redis at {host}:{port}", file=sys.stderr)
        print(f"       Make sure port-forward is running:", file=sys.stderr)
        print(
            f"       kubectl port-forward pod/ttg-redis {port}:6379", file=sys.stderr)
        sys.exit(1)

    # Read all results from stream
    results = r.xrange('ttg:results', '-', '+')

    if not results:
        print("WARNING: No results found in ttg:results stream", file=sys.stderr)
        return {}

    # Initialize accumulators
    total_params = 0
    total_chunks = len(results)
    grand_sum = 0.0
    global_min = float('inf')
    global_max = float('-inf')
    total_processing_time = 0.0
    worker_chunks: dict[str, int] = {}
    timestamps: list[datetime] = []

    chunk_details = []

    for msg_id, data in results:
        chunk_id = data.get('chunk_id', 'unknown')
        worker_id = data.get('worker_id', 'unknown')
        duration = float(data.get('duration_seconds', 0))
        completed_at = data.get('completed_at', '')
        result_json = data.get('result_data', '{}')

        try:
            result_data = json.loads(result_json)
        except json.JSONDecodeError:
            result_data = {}

        # Extract values from result_data
        chunk_sum = result_data.get('sum', 0)
        chunk_count = result_data.get('count', 0)
        chunk_min = result_data.get('min', float('inf'))
        chunk_max = result_data.get('max', float('-inf'))
        chunk_avg = result_data.get('avg', 0)

        # Accumulate
        total_params += chunk_count
        grand_sum += chunk_sum
        global_min = min(global_min, chunk_min)
        global_max = max(global_max, chunk_max)
        total_processing_time += duration

        # Track worker distribution
        worker_chunks[worker_id] = worker_chunks.get(worker_id, 0) + 1

        # Parse timestamp
        if completed_at:
            try:
                ts = datetime.fromisoformat(
                    completed_at.replace('Z', '+00:00'))
                timestamps.append(ts)
            except ValueError:
                pass

        if verbose:
            chunk_details.append({
                'chunk_id': chunk_id,
                'worker_id': worker_id,
                'params': chunk_count,
                'sum': chunk_sum,
                'min': chunk_min,
                'max': chunk_max,
                'avg': chunk_avg,
                'duration': duration
            })

    # Compute derived stats
    overall_avg = grand_sum / total_params if total_params > 0 else 0
    avg_chunk_time = total_processing_time / \
        total_chunks if total_chunks > 0 else 0

    # Wall clock time
    first_result = min(timestamps) if timestamps else None
    last_result = max(timestamps) if timestamps else None
    wall_clock_seconds = (
        last_result - first_result).total_seconds() if first_result and last_result else 0

    # Effective throughput (wall clock based)
    effective_throughput = total_params / \
        wall_clock_seconds if wall_clock_seconds > 0 else 0

    # CPU throughput (sum of all worker times)
    cpu_throughput = total_params / \
        total_processing_time if total_processing_time > 0 else 0

    return {
        'timestamp': datetime.now().isoformat(),
        'redis_connection': f'{host}:{port}',
        'summary': {
            'total_params': total_params,
            'total_chunks': total_chunks,
            'grand_sum': round(grand_sum, 2),
            'global_min': round(global_min, 2) if global_min != float('inf') else None,
            'global_max': round(global_max, 2) if global_max != float('-inf') else None,
            'overall_avg': round(overall_avg, 4),
        },
        'timing': {
            'total_cpu_time_seconds': round(total_processing_time, 2),
            'avg_chunk_time_seconds': round(avg_chunk_time, 4),
            'wall_clock_seconds': round(wall_clock_seconds, 2),
            'first_result': first_result.isoformat() if first_result else None,
            'last_result': last_result.isoformat() if last_result else None,
        },
        'throughput': {
            'effective_params_per_second': round(effective_throughput, 2),
            'cpu_params_per_second': round(cpu_throughput, 2),
            'parallelism_factor': round(effective_throughput / cpu_throughput, 2) if cpu_throughput > 0 else 1,
        },
        'worker_distribution': worker_chunks,
        'chunk_details': chunk_details if verbose else [],
    }


def print_pretty_report(stats: dict[str, Any]) -> None:
    """Print a nicely formatted report."""
    if not stats:
        print("No results to display.")
        return

    summary = stats.get('summary', {})
    timing = stats.get('timing', {})
    throughput = stats.get('throughput', {})
    workers = stats.get('worker_distribution', {})

    print()
    print("╔" + "═" * 70 + "╗")
    print("║" + " TTG Queue Mode - Results Aggregation Report ".center(70) + "║")
    print("╠" + "═" * 70 + "╣")

    # Summary section
    print("║" + " 📊 COMPUTATION SUMMARY ".ljust(70) + "║")
    print("╠" + "─" * 70 + "╣")
    print(f"║  Total Parameters Processed:  {summary.get('total_params', 0):>12,}".ljust(
        71) + "║")
    print(f"║  Total Chunks Processed:      {summary.get('total_chunks', 0):>12,}".ljust(
        71) + "║")
    print(f"║  Grand Sum:                   {summary.get('grand_sum', 0):>12,.2f}".ljust(
        71) + "║")
    print(f"║  Global Min:                  {summary.get('global_min', 0):>12,.2f}".ljust(
        71) + "║")
    print(f"║  Global Max:                  {summary.get('global_max', 0):>12,.2f}".ljust(
        71) + "║")
    print(f"║  Overall Average:             {summary.get('overall_avg', 0):>12,.4f}".ljust(
        71) + "║")

    # Timing section
    print("╠" + "─" * 70 + "╣")
    print("║" + " ⏱️  TIMING METRICS ".ljust(70) + "║")
    print("╠" + "─" * 70 + "╣")
    print(f"║  Total CPU Time:              {timing.get('total_cpu_time_seconds', 0):>12,.2f} seconds".ljust(
        71) + "║")
    print(f"║  Average Chunk Time:          {timing.get('avg_chunk_time_seconds', 0):>12,.4f} seconds".ljust(
        71) + "║")
    print(f"║  Wall Clock Time:             {timing.get('wall_clock_seconds', 0):>12,.2f} seconds".ljust(
        71) + "║")
    print(
        f"║  First Result:                {str(timing.get('first_result', 'N/A'))[:25]:>25}".ljust(71) + "║")
    print(
        f"║  Last Result:                 {str(timing.get('last_result', 'N/A'))[:25]:>25}".ljust(71) + "║")

    # Throughput section
    print("╠" + "─" * 70 + "╣")
    print("║" + " 🚀 THROUGHPUT ANALYSIS ".ljust(70) + "║")
    print("╠" + "─" * 70 + "╣")
    print(
        f"║  Effective Throughput:        {throughput.get('effective_params_per_second', 0):>12,.2f} params/sec".ljust(71) + "║")
    print(
        f"║  CPU Throughput:              {throughput.get('cpu_params_per_second', 0):>12,.2f} params/sec".ljust(71) + "║")
    print(f"║  Parallelism Factor:          {throughput.get('parallelism_factor', 1):>12,.2f}x speedup".ljust(
        71) + "║")

    # Worker distribution
    print("╠" + "─" * 70 + "╣")
    print("║" + " 👷 WORKER DISTRIBUTION ".ljust(70) + "║")
    print("╠" + "─" * 70 + "╣")
    total_chunks = sum(workers.values())
    for worker_id, chunks in sorted(workers.items()):
        pct = (chunks / total_chunks * 100) if total_chunks > 0 else 0
        bar_len = int(pct / 5)  # 20 chars max
        bar = "█" * bar_len + "░" * (20 - bar_len)
        print(
            f"║  {worker_id:>10}: {chunks:>3} chunks ({pct:>5.1f}%) {bar}".ljust(71) + "║")

    print("╚" + "═" * 70 + "╝")
    print()


def main():
    args = parse_args()

    stats = aggregate_results(
        host=args.host,
        port=args.port,
        verbose=args.verbose
    )

    if args.json:
        print(json.dumps(stats, indent=2, default=str))
    else:
        print_pretty_report(stats)

        # Also show chunk details if verbose
        if args.verbose and stats.get('chunk_details'):
            print("\n📋 CHUNK DETAILS:")
            print("-" * 80)
            print(
                f"{'Chunk':<8} {'Worker':<12} {'Params':<8} {'Sum':<12} {'Duration':<10}")
            print("-" * 80)
            for chunk in stats['chunk_details']:
                print(
                    f"{chunk['chunk_id']:<8} {chunk['worker_id']:<12} {chunk['params']:<8} {chunk['sum']:<12.2f} {chunk['duration']:<10.4f}")


if __name__ == '__main__':
    main()
