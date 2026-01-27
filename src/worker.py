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
    LOG_LEVEL: DEBUG, INFO, WARNING, ERROR (default: INFO)
    LOG_FORMAT: text, json (default: text)

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

# Import our logging infrastructure
from logging_config import (
    setup_logging,
    get_logger,
    LifecycleLogger,
    log_timing,
    log_batch_start,
    log_batch_complete,
    log_metric,
    print_banner,
    print_section,
    timed
)


# ═══════════════════════════════════════════════════════════════════════════
# CONSTANTS
# ═══════════════════════════════════════════════════════════════════════════

VERSION = "1.1.0"
PROJECT = "ttg-distributed-compute"


# ═══════════════════════════════════════════════════════════════════════════
# GRACEFUL SHUTDOWN HANDLER
# ═══════════════════════════════════════════════════════════════════════════

class GracefulKiller:
    """Handle graceful shutdown on SIGTERM/SIGINT"""
    kill_now = False

    def __init__(self, logger, lifecycle: LifecycleLogger):
        self.logger = logger
        self.lifecycle = lifecycle
        signal.signal(signal.SIGINT, self.exit_gracefully)
        signal.signal(signal.SIGTERM, self.exit_gracefully)
        self.logger.debug("Signal handlers registered for SIGINT and SIGTERM")

    def exit_gracefully(self, signum, frame):
        signal_name = signal.Signals(signum).name
        self.lifecycle.shutting_down(
            reason=f"Received {signal_name} (signal {signum})")
        self.kill_now = True


# ═══════════════════════════════════════════════════════════════════════════
# DISTRIBUTED WORKER CLASS
# ═══════════════════════════════════════════════════════════════════════════

class DistributedWorker:
    """
    A distributed worker that processes a portion of the total parameters.

    The work is divided evenly among all workers based on their worker_id.
    """

    def __init__(self):
        # Initialize logging first
        self.worker_id = int(os.getenv('WORKER_ID', '0'))
        setup_logging(worker_id=self.worker_id)

        self.logger = get_logger('worker')
        self.lifecycle = LifecycleLogger(self.logger)

        # Log starting
        self.lifecycle.starting(version=VERSION, project=PROJECT)

        # Read configuration from environment
        self.total_workers = int(os.getenv('TOTAL_WORKERS', '3'))
        self.total_parameters = int(os.getenv('TOTAL_PARAMETERS', '10000'))
        self.batch_size = int(os.getenv('BATCH_SIZE', '100'))
        self.simulate_work_ms = int(os.getenv('SIMULATE_WORK_MS', '1'))
        self.hostname = os.getenv('HOSTNAME', 'unknown')
        self.pod_name = os.getenv('POD_NAME', self.hostname)
        self.node_name = os.getenv('NODE_NAME', 'unknown')

        # Calculate this worker's range
        self.start_param, self.end_param = self._calculate_range()
        self.params_count = self.end_param - self.start_param

        # Statistics
        self.processed_count = 0
        self.results: List[Dict[str, Any]] = []
        self.start_time: Optional[float] = None
        self.end_time: Optional[float] = None
        self.batch_times: List[float] = []

        # Graceful shutdown handler
        self.killer = GracefulKiller(self.logger, self.lifecycle)

        # Log initialized with full config
        config = {
            'worker_id': self.worker_id,
            'total_workers': self.total_workers,
            'total_parameters': self.total_parameters,
            'batch_size': self.batch_size,
            'simulate_work_ms': self.simulate_work_ms,
            'range_start': self.start_param,
            'range_end': self.end_param,
            'params_to_process': self.params_count,
            'hostname': self.hostname,
            'pod_name': self.pod_name,
            'node_name': self.node_name
        }
        self.lifecycle.initialized(config)

        # Log config details at debug level
        self.logger.debug(
            f"Work range calculated: {self.start_param} to {self.end_param - 1}")
        self.logger.debug(
            f"Expected batches: {(self.params_count + self.batch_size - 1) // self.batch_size}")

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
            self.logger.debug(
                f"Last worker: adding {remainder} remainder params")

        return start, end

    @timed("compute_parameter", level=10)  # DEBUG level
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

    def _process_batch(self, batch_id: int, batch_start: int, batch_end: int) -> List[Dict[str, Any]]:
        """Process a batch of parameters."""
        batch_size = batch_end - batch_start
        log_batch_start(self.logger, batch_id, batch_start,
                        batch_end, expected_items=batch_size)

        batch_start_time = time.perf_counter()
        batch_results = []

        for param_id in range(batch_start, batch_end):
            if self.killer.kill_now:
                self.logger.warning(
                    f"Shutdown requested during batch {batch_id}, processed {len(batch_results)}/{batch_size}",
                    extra={'batch_id': batch_id, 'partial': True}
                )
                break

            result = self._compute_parameter(param_id)
            batch_results.append(result)
            self.processed_count += 1

        batch_duration = time.perf_counter() - batch_start_time
        self.batch_times.append(batch_duration)

        log_batch_complete(
            self.logger,
            batch_id,
            len(batch_results),
            batch_duration,
            batch_start=batch_start,
            batch_end=batch_end
        )

        return batch_results

    def run(self) -> Dict[str, Any]:
        """
        Execute the worker's computation task.

        Returns:
            Summary of the worker's execution including results and statistics
        """
        self.start_time = time.time()

        # Print startup banner
        print_banner(f"TTG Worker {self.worker_id} Starting", {
            'Version': VERSION,
            'Worker ID': self.worker_id,
            'Total Workers': self.total_workers,
            'Parameters Range': f"{self.start_param} - {self.end_param - 1}",
            'Parameters Count': self.params_count,
            'Batch Size': self.batch_size,
            'Simulate Work': f"{self.simulate_work_ms}ms/param",
            'Hostname': self.hostname,
            'Node': self.node_name,
            'Timestamp': datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')
        })

        # Log entering running state
        self.lifecycle.running(total_work=self.params_count)

        # Process in batches
        total_to_process = self.params_count
        current = self.start_param
        batch_id = 0

        while current < self.end_param and not self.killer.kill_now:
            batch_end = min(current + self.batch_size, self.end_param)

            # Process batch
            batch_results = self._process_batch(batch_id, current, batch_end)
            self.results.extend(batch_results)

            # Progress report
            self.lifecycle.progress(
                self.processed_count,
                total_to_process,
                batch_id=batch_id,
                current_param=current,
                rate=self.processed_count /
                (time.time() - self.start_time) if self.start_time else 0
            )

            current = batch_end
            batch_id += 1

        self.end_time = time.time()

        # Generate summary
        summary = self._generate_summary()

        # Log completion or interruption
        if summary['status'] == 'completed':
            self.lifecycle.completed(summary)
        else:
            self.lifecycle.failed(
                "Interrupted by shutdown signal", summary=summary)

        # Print completion section
        print_section(f"Worker {self.worker_id} - Execution Complete")

        # Log metrics
        log_metric(self.logger, 'processed_count',
                   self.processed_count, 'params')
        log_metric(self.logger, 'duration',
                   summary['duration_seconds'], 'seconds')
        log_metric(self.logger, 'throughput',
                   summary['params_per_second'], 'params/sec')

        if self.batch_times:
            avg_batch_time = sum(self.batch_times) / len(self.batch_times)
            log_metric(self.logger, 'avg_batch_time',
                       avg_batch_time, 'seconds')

        # Print sample results
        if self.results:
            self.logger.info("Sample results (first 3):")
            for r in self.results[:3]:
                self.logger.info(f"  param_{r['param_id']}: {r['result']:.4f}")
            if len(self.results) > 6:
                self.logger.info("  ...")
            self.logger.info("Sample results (last 3):")
            for r in self.results[-3:]:
                self.logger.info(f"  param_{r['param_id']}: {r['result']:.4f}")

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

        # Compute batch statistics
        batch_stats = {}
        if self.batch_times:
            batch_stats = {
                'total_batches': len(self.batch_times),
                'avg_batch_time': sum(self.batch_times) / len(self.batch_times),
                'min_batch_time': min(self.batch_times),
                'max_batch_time': max(self.batch_times)
            }

        return {
            'worker_id': self.worker_id,
            'status': 'completed' if not self.killer.kill_now else 'interrupted',
            'version': VERSION,
            'hostname': self.hostname,
            'pod_name': self.pod_name,
            'node_name': self.node_name,
            'range_start': self.start_param,
            'range_end': self.end_param,
            'processed_count': self.processed_count,
            'expected_count': self.params_count,
            'duration_seconds': duration,
            'params_per_second': self.processed_count / duration if duration > 0 else 0,
            'start_time': datetime.fromtimestamp(self.start_time).isoformat() if self.start_time else None,
            'end_time': datetime.fromtimestamp(self.end_time).isoformat() if self.end_time else None,
            'batch_stats': batch_stats,
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
            with log_timing(self.logger, f"save_results to {filepath}"):
                with open(filepath, 'w') as f:
                    json.dump(output, f, indent=2)
            self.logger.info(f"Results saved to: {filepath}", extra={
                             'filepath': filepath})
        except Exception as e:
            self.logger.error(f"Failed to save results to {filepath}: {e}", extra={
                              'filepath': filepath, 'error': str(e)})


# ═══════════════════════════════════════════════════════════════════════════
# MAIN ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════════

def main():
    """Main entry point."""
    # Get worker ID for early logging
    worker_id = int(os.getenv('WORKER_ID', '0'))

    # Setup logging before anything else
    setup_logging(worker_id=worker_id)
    logger = get_logger('main')

    # Log startup
    logger.info("=" * 70)
    logger.info(f"TTG Distributed Worker v{VERSION}")
    logger.info(f"Timestamp: {datetime.now(timezone.utc).isoformat()}")
    logger.info(f"Hostname: {os.getenv('HOSTNAME', 'unknown')}")
    logger.info(f"Pod: {os.getenv('POD_NAME', 'unknown')}")
    logger.info(f"Node: {os.getenv('NODE_NAME', 'unknown')}")
    logger.info("=" * 70)

    try:
        # Create and run worker
        with log_timing(logger, "worker_total_execution"):
            worker = DistributedWorker()
            summary = worker.run()

        # Optionally save results to file
        save_output = os.getenv('SAVE_OUTPUT', 'false').lower() == 'true'
        if save_output:
            worker.save_results()

        # Print final JSON summary (useful for aggregation)
        logger.info("=" * 70)
        logger.info("FINAL SUMMARY (JSON):")
        logger.info("=" * 70)
        print(json.dumps(summary, indent=2))

        # Exit with appropriate code
        if summary['status'] == 'completed':
            logger.info(f"Worker {worker_id} exiting successfully (code 0)")
            sys.exit(0)
        else:
            logger.warning(
                f"Worker {worker_id} exiting due to interruption (code 1)")
            sys.exit(1)

    except Exception as e:
        logger.error(
            f"Worker {worker_id} failed with exception: {e}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    main()
