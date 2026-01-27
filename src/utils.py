"""
TTG Distributed Computation - Utility Functions

Shared utilities for the distributed computation system.
"""

import os
import json
import hashlib
from datetime import datetime
from typing import Dict, List, Any, Optional


def get_worker_config() -> Dict[str, int]:
    """
    Get worker configuration from environment variables.

    Returns:
        Dictionary with worker configuration
    """
    return {
        'worker_id': int(os.getenv('WORKER_ID', '0')),
        'total_workers': int(os.getenv('TOTAL_WORKERS', '3')),
        'total_parameters': int(os.getenv('TOTAL_PARAMETERS', '10000')),
        'batch_size': int(os.getenv('BATCH_SIZE', '100')),
        'simulate_work_ms': int(os.getenv('SIMULATE_WORK_MS', '1'))
    }


def calculate_worker_range(worker_id: int, total_workers: int, total_parameters: int) -> tuple:
    """
    Calculate the parameter range for a specific worker.

    Args:
        worker_id: The worker's ID (0-indexed)
        total_workers: Total number of workers
        total_parameters: Total parameters to distribute

    Returns:
        Tuple of (start_index, end_index) - end is exclusive
    """
    params_per_worker = total_parameters // total_workers
    remainder = total_parameters % total_workers

    start = worker_id * params_per_worker
    end = start + params_per_worker

    # Last worker gets the remainder
    if worker_id == total_workers - 1:
        end += remainder

    return start, end


def aggregate_results(result_files: List[str]) -> Dict[str, Any]:
    """
    Aggregate results from multiple worker output files.

    Args:
        result_files: List of paths to worker result JSON files

    Returns:
        Aggregated results dictionary
    """
    all_results = []
    summaries = []

    for filepath in result_files:
        with open(filepath, 'r') as f:
            data = json.load(f)
            summaries.append(data.get('summary', {}))
            all_results.extend(data.get('results', []))

    # Sort by parameter ID
    all_results.sort(key=lambda x: x.get('param_id', 0))

    # Compute aggregates
    if all_results:
        values = [r['result'] for r in all_results]
        total_sum = sum(values)
        total_avg = total_sum / len(values)
        total_min = min(values)
        total_max = max(values)
    else:
        total_sum = total_avg = total_min = total_max = 0

    # Compute total duration
    total_duration = sum(s.get('duration_seconds', 0) for s in summaries)
    total_processed = sum(s.get('processed_count', 0) for s in summaries)

    return {
        'total_workers': len(summaries),
        'total_processed': total_processed,
        'total_duration_seconds': total_duration,
        'aggregates': {
            'sum': total_sum,
            'average': total_avg,
            'min': total_min,
            'max': total_max
        },
        'worker_summaries': summaries,
        'timestamp': datetime.utcnow().isoformat()
    }


def create_checksum(data: Any) -> str:
    """
    Create a checksum for data verification.

    Args:
        data: Data to checksum (will be JSON serialized)

    Returns:
        SHA256 hex digest
    """
    json_str = json.dumps(data, sort_keys=True)
    return hashlib.sha256(json_str.encode()).hexdigest()


def format_duration(seconds: float) -> str:
    """
    Format duration in human-readable format.

    Args:
        seconds: Duration in seconds

    Returns:
        Formatted string (e.g., "1h 23m 45s" or "45.3s")
    """
    if seconds < 60:
        return f"{seconds:.1f}s"
    elif seconds < 3600:
        mins = int(seconds // 60)
        secs = seconds % 60
        return f"{mins}m {secs:.0f}s"
    else:
        hours = int(seconds // 3600)
        mins = int((seconds % 3600) // 60)
        secs = seconds % 60
        return f"{hours}h {mins}m {secs:.0f}s"


def print_banner(text: str, char: str = "=", width: int = 60):
    """Print a banner with centered text."""
    print(char * width)
    print(text.center(width))
    print(char * width)
