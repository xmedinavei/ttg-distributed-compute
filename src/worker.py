#!/usr/bin/env python3
"""
TTG Distributed Worker

This worker processes a range of parameters as part of a distributed computation.
Each worker instance is responsible for processing a specific "slice" of the total work.

Environment Variables:
    WORKER_ID: Unique identifier for this worker (0, 1, 2, ...)
    TOTAL_WORKERS: Total number of workers in the cluster
    TOTAL_PARAMETERS: Total number of parameters to process (default: 10000)
    BATCH_SIZE: Number of parameters to process per batch (default: 100)
    SIMULATE_WORK_MS: Milliseconds to simulate per parameter (default: 1)

Example:
    With 3 workers and 9000 parameters:
    - Worker 0: processes parameters 0-2999
    - Worker 1: processes parameters 3000-5999
    - Worker 2: processes parameters 6000-8999
"""

import os
import sys
import time
import json
import signal
import hashlib
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional


class GracefulKiller:
    """Handle graceful shutdown on SIGTERM/SIGINT"""
    kill_now = False

    def __init__(self):
        signal.signal(signal.SIGINT, self.exit_gracefully)
        signal.signal(signal.SIGTERM, self.exit_gracefully)

    def exit_gracefully(self, signum, frame):
        print(
            f"\n[WORKER] Received shutdown signal ({signum}). Finishing current batch...")
        self.kill_now = True


class DistributedWorker:
    """
    A distributed worker that processes a portion of the total parameters.

    The work is divided evenly among all workers based on their worker_id.
    """

    def __init__(self):
        # Read configuration from environment
        self.worker_id = int(os.getenv('WORKER_ID', '0'))
        self.total_workers = int(os.getenv('TOTAL_WORKERS', '3'))
        self.total_parameters = int(os.getenv('TOTAL_PARAMETERS', '10000'))
        self.batch_size = int(os.getenv('BATCH_SIZE', '100'))
        self.simulate_work_ms = int(os.getenv('SIMULATE_WORK_MS', '1'))

        # Calculate this worker's range
        self.start_param, self.end_param = self._calculate_range()

        # Statistics
        self.processed_count = 0
        self.results: List[Dict[str, Any]] = []
        self.start_time: Optional[float] = None
        self.end_time: Optional[float] = None

        # Graceful shutdown handler
        self.killer = GracefulKiller()

    def _calculate_range(self) -> tuple:
        """
        Calculate the parameter range for this worker.

        Uses integer division to evenly distribute work.
        The last worker gets any remainder.
        """
        params_per_worker = self.total_parameters // self.total_workers
        remainder = self.total_parameters % self.total_workers

        start = self.worker_id * params_per_worker
        end = start + params_per_worker

        # Last worker gets the remainder
        if self.worker_id == self.total_workers - 1:
            end += remainder

        return start, end

    def _compute_parameter(self, param_id: int) -> Dict[str, Any]:
        """
        Process a single parameter and return the result.

        This is a PLACEHOLDER computation. Replace with your actual algorithm.

        Current implementation:
        - Simulates work with a configurable delay
        - Computes a hash-based "result" for demonstration

        Args:
            param_id: The parameter index to process

        Returns:
            Dictionary with parameter ID and computed result
        """
        # Simulate computation time
        if self.simulate_work_ms > 0:
            time.sleep(self.simulate_work_ms / 1000.0)

        # Placeholder computation: compute a hash-based value
        # REPLACE THIS WITH YOUR ACTUAL ALGORITHM
        input_string = f"param_{param_id}_worker_{self.worker_id}"
        hash_result = hashlib.sha256(input_string.encode()).hexdigest()[:16]

        # Simulate some numerical result based on parameter
        numerical_result = (param_id * 7 + 13) % 1000 + \
            float(f"0.{param_id % 100}")

        return {
            'param_id': param_id,
            'result': numerical_result,
            'hash': hash_result,
            'worker_id': self.worker_id,
            'timestamp': datetime.now(timezone.utc).isoformat()
        }

    def _process_batch(self, batch_start: int, batch_end: int) -> List[Dict[str, Any]]:
        """Process a batch of parameters."""
        batch_results = []
        for param_id in range(batch_start, batch_end):
            if self.killer.kill_now:
                print(
                    f"[WORKER {self.worker_id}] Shutdown requested, stopping batch early")
                break

            result = self._compute_parameter(param_id)
            batch_results.append(result)
            self.processed_count += 1

        return batch_results

    def run(self) -> Dict[str, Any]:
        """
        Execute the worker's computation task.

        Returns:
            Summary of the worker's execution including results and statistics
        """
        self.start_time = time.time()

        # Print startup information
        print("=" * 60)
        print(f"[WORKER {self.worker_id}] Starting Distributed Computation")
        print("=" * 60)
        print(f"  Worker ID:        {self.worker_id}")
        print(f"  Total Workers:    {self.total_workers}")
        print(f"  Total Parameters: {self.total_parameters}")
        print(f"  My Range:         {self.start_param} - {self.end_param - 1}")
        print(f"  Parameters Count: {self.end_param - self.start_param}")
        print(f"  Batch Size:       {self.batch_size}")
        print(f"  Simulate Work:    {self.simulate_work_ms}ms per param")
        print("=" * 60)
        print()

        # Process in batches
        total_to_process = self.end_param - self.start_param
        current = self.start_param

        while current < self.end_param and not self.killer.kill_now:
            batch_end = min(current + self.batch_size, self.end_param)

            # Process batch
            batch_results = self._process_batch(current, batch_end)
            self.results.extend(batch_results)

            # Progress report
            progress = (self.processed_count / total_to_process) * 100
            print(f"[WORKER {self.worker_id}] Progress: {self.processed_count}/{total_to_process} "
                  f"({progress:.1f}%) - Batch {current}-{batch_end-1} complete")

            current = batch_end

        self.end_time = time.time()

        # Generate summary
        summary = self._generate_summary()

        # Print completion
        print()
        print("=" * 60)
        print(f"[WORKER {self.worker_id}] Computation Complete!")
        print("=" * 60)
        print(f"  Processed:      {self.processed_count} parameters")
        print(f"  Duration:       {summary['duration_seconds']:.2f} seconds")
        print(
            f"  Throughput:     {summary['params_per_second']:.1f} params/sec")
        print(f"  Status:         {summary['status']}")
        print("=" * 60)

        # Print sample results (first 3 and last 3)
        if self.results:
            print("\nSample Results (first 3):")
            for r in self.results[:3]:
                print(f"  param_{r['param_id']}: {r['result']:.4f}")
            if len(self.results) > 6:
                print("  ...")
            print("Sample Results (last 3):")
            for r in self.results[-3:]:
                print(f"  param_{r['param_id']}: {r['result']:.4f}")

        return summary

    def _generate_summary(self) -> Dict[str, Any]:
        """Generate execution summary."""
        duration = (self.end_time - self.start_time) if self.end_time else 0

        # Compute aggregate statistics
        if self.results:
            results_values = [r['result'] for r in self.results]
            result_sum = sum(results_values)
            result_avg = result_sum / len(results_values)
            result_min = min(results_values)
            result_max = max(results_values)
        else:
            result_sum = result_avg = result_min = result_max = 0

        return {
            'worker_id': self.worker_id,
            'status': 'completed' if not self.killer.kill_now else 'interrupted',
            'range_start': self.start_param,
            'range_end': self.end_param,
            'processed_count': self.processed_count,
            'expected_count': self.end_param - self.start_param,
            'duration_seconds': duration,
            'params_per_second': self.processed_count / duration if duration > 0 else 0,
            'start_time': datetime.fromtimestamp(self.start_time).isoformat() if self.start_time else None,
            'end_time': datetime.fromtimestamp(self.end_time).isoformat() if self.end_time else None,
            'aggregates': {
                'sum': result_sum,
                'average': result_avg,
                'min': result_min,
                'max': result_max
            }
        }

    def save_results(self, filepath: str = None):
        """
        Save results to a JSON file.

        Args:
            filepath: Optional path to save results. 
                     Defaults to /output/worker_{id}_results.json
        """
        if filepath is None:
            # Default to /output directory (can be mounted as volume)
            os.makedirs('/output', exist_ok=True)
            filepath = f'/output/worker_{self.worker_id}_results.json'

        output = {
            'summary': self._generate_summary(),
            'results': self.results
        }

        try:
            with open(filepath, 'w') as f:
                json.dump(output, f, indent=2)
            print(f"\n[WORKER {self.worker_id}] Results saved to: {filepath}")
        except Exception as e:
            print(
                f"\n[WORKER {self.worker_id}] Warning: Could not save results to {filepath}: {e}")


def main():
    """Main entry point."""
    print(f"\n{'#' * 60}")
    print(f"# TTG Distributed Worker - Starting")
    print(f"# Timestamp: {datetime.now(timezone.utc).isoformat()}")
    print(f"# Hostname: {os.getenv('HOSTNAME', 'unknown')}")
    print(f"{'#' * 60}\n")

    try:
        # Create and run worker
        worker = DistributedWorker()
        summary = worker.run()

        # Optionally save results to file
        save_output = os.getenv('SAVE_OUTPUT', 'false').lower() == 'true'
        if save_output:
            worker.save_results()

        # Print final JSON summary (useful for aggregation)
        print("\n[WORKER] Final Summary (JSON):")
        print(json.dumps(summary, indent=2))

        # Exit with appropriate code
        if summary['status'] == 'completed':
            sys.exit(0)
        else:
            sys.exit(1)

    except Exception as e:
        print(f"\n[WORKER] ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
