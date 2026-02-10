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
import random
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

VERSION = "1.3.0"  # Updated for Milestone 3 foundation
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
# QUEUE-BASED WORKER CLASS (Milestone 2)
# ═══════════════════════════════════════════════════════════════════════════

class QueueWorker:
    """
    Queue-based worker that pulls tasks from a configured queue backend.

    Unlike DistributedWorker (which calculates a fixed range at startup),
    QueueWorker dynamically pulls tasks from a Redis queue. This provides:

    1. **Fault Tolerance**: If a worker crashes, its task returns to the queue
    2. **Load Balancing**: Fast workers automatically get more tasks
    3. **Elastic Scaling**: Add/remove workers without reconfiguration

    Lifecycle:
    1. Connect to Redis
    2. If Worker 0 AND stream empty: initialize all task chunks
    3. Loop: pull task → process → publish result → acknowledge
    4. If no tasks for IDLE_TIMEOUT_SECONDS: exit gracefully

    Environment Variables:
        WORKER_ID: Unique worker identifier (0, 1, 2, ...)
        QUEUE_BACKEND: redis|rabbitmq (default: redis)
        REDIS_HOST: Redis hostname (default: ttg-redis for K8s)
        REDIS_PORT: Redis port (default: 6379)
        RABBITMQ_HOST: RabbitMQ hostname (default: ttg-rabbitmq)
        RABBITMQ_PORT: RabbitMQ port (default: 5672)
        TOTAL_PARAMETERS: Total params to process (default: 10000)
        CHUNK_SIZE: Parameters per task chunk (default: 100)
        IDLE_TIMEOUT_SECONDS: Exit after this many seconds of no tasks (default: 30)
        SIMULATE_WORK_MS: Milliseconds to simulate per parameter (default: 1)
        SIMULATE_FAULT_RATE: Probability (0.0-1.0) a chunk fails for testing retry/DLQ (default: 0.0)
    """

    def __init__(self):
        """Initialize the QueueWorker."""
        # Initialize logging first
        self.worker_id = int(os.getenv('WORKER_ID', '0'))
        setup_logging(worker_id=self.worker_id)

        self.logger = get_logger('queue_worker')
        self.lifecycle = LifecycleLogger(self.logger)

        # Log starting
        self.lifecycle.starting(version=VERSION, project=PROJECT)

        # Read configuration from environment
        self.total_parameters = int(os.getenv('TOTAL_PARAMETERS', '10000'))
        self.chunk_size = int(os.getenv('CHUNK_SIZE', '100'))
        self.idle_timeout_seconds = int(
            os.getenv('IDLE_TIMEOUT_SECONDS', '30'))
        self.simulate_work_ms = int(os.getenv('SIMULATE_WORK_MS', '1'))
        self.hostname = os.getenv('HOSTNAME', 'unknown')
        self.pod_name = os.getenv('POD_NAME', self.hostname)
        self.node_name = os.getenv('NODE_NAME', 'unknown')

        # Fault simulation: probabilistic task failure for testing retry/DLQ
        # Set SIMULATE_FAULT_RATE=0.1 to fail ~10% of tasks (0.0 = disabled)
        self.simulate_fault_rate = float(
            os.getenv('SIMULATE_FAULT_RATE', '0.0'))

        # Queue backend settings (phased migration: Redis remains fallback)
        self.queue_backend = os.getenv('QUEUE_BACKEND', 'redis').strip().lower()

        # Redis connection settings
        self.redis_host = os.getenv('REDIS_HOST', 'ttg-redis')
        self.redis_port = int(os.getenv('REDIS_PORT', '6379'))
        self.rabbitmq_host = os.getenv('RABBITMQ_HOST', 'ttg-rabbitmq')
        self.rabbitmq_port = int(os.getenv('RABBITMQ_PORT', '5672'))

        # Statistics
        self.chunks_processed = 0
        self.params_processed = 0
        self.start_time: Optional[float] = None
        self.end_time: Optional[float] = None

        # Queue client (initialized in run())
        self.queue = None

        # Graceful shutdown handler
        self.killer = GracefulKiller(self.logger, self.lifecycle)

        # Consumer name for queue backend
        self.consumer_name = f"worker-{self.worker_id}"

        # Stale task recovery settings (Fault Tolerance)
        # - Check for stale tasks periodically
        # - Tasks idle for threshold duration are considered stale
        self.stale_check_interval_seconds = int(
            os.environ.get("STALE_CHECK_INTERVAL_SECONDS", "30"))
        self.stale_threshold_ms = int(os.environ.get(
            "STALE_THRESHOLD_MS", "60000"))  # Default 60 seconds
        self.last_stale_check_time = 0.0  # Will be set in _process_tasks

        # Log initialized
        config = {
            'worker_id': self.worker_id,
            'mode': 'queue',
            'queue_backend': self.queue_backend,
            'redis_host': self.redis_host,
            'redis_port': self.redis_port,
            'rabbitmq_host': self.rabbitmq_host,
            'rabbitmq_port': self.rabbitmq_port,
            'total_parameters': self.total_parameters,
            'chunk_size': self.chunk_size,
            'idle_timeout_seconds': self.idle_timeout_seconds,
            'simulate_work_ms': self.simulate_work_ms,
            'consumer_name': self.consumer_name,
            'hostname': self.hostname,
            'pod_name': self.pod_name,
            'node_name': self.node_name,
            'simulate_fault_rate': self.simulate_fault_rate
        }
        self.lifecycle.initialized(config)

    def _connect_to_queue_backend(self) -> bool:
        """
        Establish connection to configured queue backend.

        Returns:
            True if connected successfully
        """
        if self.queue_backend == "rabbitmq":
            from rabbitmq_queue import RabbitMQTaskQueue

            self.queue = RabbitMQTaskQueue(
                rabbitmq_host=self.rabbitmq_host,
                rabbitmq_port=self.rabbitmq_port,
            )
            self.logger.info(
                f"Connecting to RabbitMQ at {self.rabbitmq_host}:{self.rabbitmq_port}..."
            )
            return self.queue.connect(retry=True)

        # Default backend: Redis
        from queue_utils import TaskQueue

        self.queue = TaskQueue(
            redis_host=self.redis_host,
            redis_port=self.redis_port
        )
        self.logger.info(
            f"Connecting to Redis at {self.redis_host}:{self.redis_port}..."
        )
        return self.queue.connect(retry=True)

    def _maybe_initialize_tasks(self):
        """
        Initialize task queue if this is Worker 0 and the queue is empty.

        Only Worker 0 should initialize tasks to avoid race conditions.
        Other workers wait briefly for initialization to complete.
        """
        stream_length = self.queue.get_stream_length()

        if self.worker_id == 0:
            if stream_length == 0:
                self.logger.info(
                    f"Worker 0: Initializing task queue with {self.total_parameters} params "
                    f"(chunk_size={self.chunk_size})"
                )
                tasks_created = self.queue.initialize_tasks(
                    total_params=self.total_parameters,
                    chunk_size=self.chunk_size
                )
                self.logger.info(f"✅ Created {tasks_created} task chunks")
            else:
                self.logger.info(
                    f"Worker 0: Task queue already has {stream_length} tasks, skipping init"
                )
        else:
            # Non-zero workers: wait a moment for Worker 0 to initialize
            if stream_length == 0:
                self.logger.info(
                    f"Worker {self.worker_id}: Queue empty, waiting for Worker 0 to initialize..."
                )
                time.sleep(2)  # Brief wait for Worker 0

    def _compute_parameter(self, param_id: int) -> Dict[str, Any]:
        """
        Process a single parameter and return the result.

        This is the same computation as DistributedWorker for consistency.

        Args:
            param_id: The parameter index to process

        Returns:
            Dictionary with parameter ID and computed result
        """
        # Simulate computation time
        if self.simulate_work_ms > 0:
            time.sleep(self.simulate_work_ms / 1000.0)

        # Placeholder computation: compute a hash-based value
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

    def _process_chunk(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process all parameters in a task chunk.

        Args:
            task: Task dictionary with start_param, end_param, etc.

        Returns:
            Result summary for the chunk
        """
        chunk_id = task['chunk_id']
        start_param = int(task['start_param'])
        end_param = int(task['end_param'])
        params_count = end_param - start_param

        self.logger.info(
            f"📦 Processing chunk {chunk_id}: params {start_param}-{end_param} "
            f"({params_count} params)"
        )

        # Fault simulation: raise an error with configured probability.
        # This exercises the nack_task → retry → DLQ path for RabbitMQ
        # and the stale-task recovery path for Redis.
        if self.simulate_fault_rate > 0 and random.random() < self.simulate_fault_rate:
            raise RuntimeError(
                f"Simulated fault on chunk {chunk_id} "
                f"(SIMULATE_FAULT_RATE={self.simulate_fault_rate})"
            )

        chunk_start_time = time.perf_counter()
        results = []
        result_sum = 0

        for param_id in range(start_param, end_param):
            if self.killer.kill_now:
                self.logger.warning(
                    f"Shutdown requested during chunk {chunk_id}, "
                    f"processed {len(results)}/{params_count}"
                )
                break

            result = self._compute_parameter(param_id)
            results.append(result)
            result_sum += result['result']
            self.params_processed += 1

        chunk_duration = time.perf_counter() - chunk_start_time

        # Build result summary
        result_summary = {
            'sum': result_sum,
            'count': len(results),
            'min': min(r['result'] for r in results) if results else 0,
            'max': max(r['result'] for r in results) if results else 0,
            'avg': result_sum / len(results) if results else 0
        }

        self.logger.info(
            f"✅ Chunk {chunk_id} complete: {len(results)} params in {chunk_duration:.2f}s "
            f"(sum={result_sum:.2f})"
        )

        return {
            'chunk_id': chunk_id,
            'params_processed': len(results),
            'duration_seconds': chunk_duration,
            'result_summary': result_summary,
            'interrupted': self.killer.kill_now
        }

    def _check_and_claim_stale_tasks(self) -> int:
        """
        Check for and claim tasks that have been pending too long.

        This is the core FAULT TOLERANCE feature. When a worker crashes:
        1. Its in-progress tasks remain in Redis's Pending Entry List (PEL)
        2. Other workers periodically check for these "stale" tasks
        3. After the stale threshold (60s), a worker can claim and reprocess them
        4. This ensures no work is lost, even if workers crash

        How it works:
        - Called periodically (every 30s) during the main processing loop
        - Uses XCLAIM to transfer ownership of stale tasks
        - Stale = idle in PEL for > stale_threshold_ms (60000ms = 60s)
        - Each call claims up to 5 stale tasks

        Returns:
            Number of stale tasks claimed and processed
        """
        current_time = time.time()

        # Only check every stale_check_interval_seconds
        if current_time - self.last_stale_check_time < self.stale_check_interval_seconds:
            return 0

        self.last_stale_check_time = current_time

        # Claim stale tasks
        try:
            claimed_tasks = self.queue.claim_stale_tasks(
                consumer_name=self.consumer_name,
                min_idle_ms=self.stale_threshold_ms,
                count=5  # Claim up to 5 at a time
            )

            if not claimed_tasks:
                return 0

            self.logger.info(
                f"🔄 FAULT RECOVERY: Claimed {len(claimed_tasks)} stale task(s) "
                f"from crashed worker(s)"
            )

            # Process each claimed task
            for task in claimed_tasks:
                if self.killer.kill_now:
                    break

                previous_consumer = task.get('previous_consumer', 'unknown')
                self.logger.warning(
                    f"🔄 Processing recovered task {task['chunk_id']} "
                    f"(was assigned to {previous_consumer})"
                )

                # Process the chunk
                result = self._process_chunk(task)
                self.chunks_processed += 1

                # Publish result
                self.queue.publish_result(
                    chunk_id=task['chunk_id'],
                    worker_id=self.consumer_name,
                    result_data=result['result_summary'],
                    duration_seconds=result['duration_seconds']
                )

                # Acknowledge
                self.queue.ack_task(task['message_id'])

                self.logger.info(
                    f"✅ FAULT RECOVERY: Successfully recovered task {task['chunk_id']}"
                )

            return len(claimed_tasks)

        except Exception as e:
            self.logger.error(f"Error checking stale tasks: {e}")
            return 0

    def _process_tasks(self) -> Dict[str, Any]:
        """
        Main loop: pull tasks, process them, publish results, acknowledge.

        Continues until:
        - No tasks available for IDLE_TIMEOUT_SECONDS
        - Shutdown signal received

        Returns:
            Execution summary
        """
        # Calculate how many empty reads = timeout
        # get_next_task blocks for 5000ms (5s) by default
        block_time_seconds = 5
        max_empty_reads = max(
            1, self.idle_timeout_seconds // block_time_seconds)

        consecutive_empty = 0

        self.logger.info(
            f"Starting task consumption loop "
            f"(idle timeout: {self.idle_timeout_seconds}s = {max_empty_reads} empty reads)"
        )

        # Initialize stale check timer
        self.last_stale_check_time = time.time()

        while not self.killer.kill_now:
            # ═══════════════════════════════════════════════════════════════
            # FAULT TOLERANCE: Check for stale tasks from crashed workers
            # ═══════════════════════════════════════════════════════════════
            stale_recovered = self._check_and_claim_stale_tasks()
            if stale_recovered > 0:
                # Reset empty counter since we did work
                consecutive_empty = 0

            # Try to get next task
            task = self.queue.get_next_task(
                consumer_name=self.consumer_name,
                block_ms=block_time_seconds * 1000
            )

            if task is None:
                consecutive_empty += 1
                self.logger.debug(
                    f"No task received ({consecutive_empty}/{max_empty_reads} empty reads)"
                )

                # Before giving up, check if there are pending (stale) tasks
                # that might need recovery from crashed workers
                if consecutive_empty >= max_empty_reads:
                    # Force a stale check before exiting
                    self.last_stale_check_time = 0  # Force check now
                    stale_recovered = self._check_and_claim_stale_tasks()
                    if stale_recovered > 0:
                        consecutive_empty = 0  # Keep going!
                        continue

                    self.logger.info(
                        f"No tasks for {self.idle_timeout_seconds}s, assuming queue is empty"
                    )
                    break
                continue

            # Got a task! Reset empty counter
            consecutive_empty = 0

            try:
                # Process the chunk
                result = self._process_chunk(task)
                self.chunks_processed += 1

                # Publish result
                self.queue.publish_result(
                    chunk_id=task['chunk_id'],
                    worker_id=self.consumer_name,
                    result_data=result['result_summary'],
                    duration_seconds=result['duration_seconds']
                )

                # Acknowledge task
                self.queue.ack_task(task['message_id'])
            except Exception as task_error:
                # RabbitMQ backend supports retry + DLQ via nack_task.
                # Redis backend keeps task pending for stale-task recovery.
                self.logger.error(
                    f"Task {task.get('chunk_id', 'unknown')} failed: {task_error}",
                    exc_info=True
                )
                if hasattr(self.queue, "nack_task"):
                    self.queue.nack_task(
                        message_id=task['message_id'],
                        task_data=task,
                        reason=str(task_error),
                    )
                continue

            # Log progress
            stats = self.queue.get_queue_stats()
            self.logger.info(
                f"📊 Progress: {stats['results_count']} chunks done, "
                f"{stats['tasks_total'] - stats['results_count']} remaining, "
                f"{stats['tasks_pending']} in-progress"
            )

        # Generate summary
        return self._generate_summary()

    def _generate_summary(self) -> Dict[str, Any]:
        """Generate execution summary."""
        duration = (self.end_time - self.start_time) if self.end_time else 0

        # Get final queue stats
        queue_stats = {}
        if self.queue and self.queue.connected:
            queue_stats = self.queue.get_queue_stats()

        return {
            'worker_id': self.worker_id,
            'mode': 'queue',
            'queue_backend': self.queue_backend,
            'status': 'completed' if not self.killer.kill_now else 'interrupted',
            'chunks_processed': self.chunks_processed,
            'params_processed': self.params_processed,
            'duration_seconds': round(duration, 2),
            'params_per_second': round(self.params_processed / duration, 2) if duration > 0 else 0,
            'chunks_per_second': round(self.chunks_processed / duration, 2) if duration > 0 else 0,
            'consumer_name': self.consumer_name,
            'redis_host': self.redis_host,
            'rabbitmq_host': self.rabbitmq_host,
            'hostname': self.hostname,
            'node_name': self.node_name,
            'queue_stats': queue_stats
        }

    def run(self) -> Dict[str, Any]:
        """
        Execute the queue-based worker.

        Returns:
            Execution summary dictionary
        """
        self.start_time = time.time()

        # Print startup banner
        print_banner(f"TTG Queue Worker {self.worker_id} Starting", {
            'Version': VERSION,
            'Mode': f"Queue ({self.queue_backend})",
            'Worker ID': self.worker_id,
            'Queue Backend': self.queue_backend,
            'Redis': f"{self.redis_host}:{self.redis_port}",
            'RabbitMQ': f"{self.rabbitmq_host}:{self.rabbitmq_port}",
            'Total Parameters': self.total_parameters,
            'Chunk Size': self.chunk_size,
            'Idle Timeout': f"{self.idle_timeout_seconds}s",
            'Simulate Work': f"{self.simulate_work_ms}ms/param",
            'Hostname': self.hostname,
            'Node': self.node_name,
            'Timestamp': datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')
        })

        try:
            # Step 1: Connect to queue backend
            self._connect_to_queue_backend()

            # Step 2: Maybe initialize tasks (Worker 0 only)
            self._maybe_initialize_tasks()

            # Step 3: Log running state
            self.lifecycle.running(
                total_work=f"{self.total_parameters} params (queue mode)")

            # Step 4: Process tasks until done
            summary = self._process_tasks()

        except Exception as e:
            self.logger.error(f"Worker failed: {e}", exc_info=True)
            self.end_time = time.time()
            summary = self._generate_summary()
            summary['status'] = 'failed'
            summary['error'] = str(e)
            return summary

        finally:
            # Disconnect from Redis
            if self.queue:
                self.queue.disconnect()

        self.end_time = time.time()
        summary = self._generate_summary()

        # Log completion
        if summary['status'] == 'completed':
            self.lifecycle.completed(summary)
        else:
            self.lifecycle.failed(
                "Interrupted by shutdown signal", summary=summary)

        # Print completion section
        print_section(f"Queue Worker {self.worker_id} - Execution Complete")

        # Log metrics
        log_metric(self.logger, 'chunks_processed',
                   self.chunks_processed, 'chunks')
        log_metric(self.logger, 'params_processed',
                   self.params_processed, 'params')
        log_metric(self.logger, 'duration',
                   summary['duration_seconds'], 'seconds')
        log_metric(self.logger, 'throughput',
                   summary['params_per_second'], 'params/sec')

        return summary


# ═══════════════════════════════════════════════════════════════════════════
# MAIN ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════════

def main():
    """
    Main entry point.

    Supports two modes based on USE_QUEUE environment variable:
    - USE_QUEUE=false (default): Static range partitioning (Milestone 1)
    - USE_QUEUE=true: Redis Streams queue mode (Milestone 2)
    """
    # Get config for early logging
    worker_id = int(os.getenv('WORKER_ID', '0'))
    use_queue = os.getenv('USE_QUEUE', 'false').lower() == 'true'
    queue_backend = os.getenv('QUEUE_BACKEND', 'redis').lower()

    # Setup logging before anything else
    setup_logging(worker_id=worker_id)
    logger = get_logger('main')

    # Log startup
    logger.info("=" * 70)
    logger.info(f"TTG Distributed Worker v{VERSION}")
    if use_queue:
        logger.info(f"Mode: QUEUE ({queue_backend})")
    else:
        logger.info("Mode: STATIC (Range Partitioning)")
    logger.info(f"Timestamp: {datetime.now(timezone.utc).isoformat()}")
    logger.info(f"Hostname: {os.getenv('HOSTNAME', 'unknown')}")
    logger.info(f"Pod: {os.getenv('POD_NAME', 'unknown')}")
    logger.info(f"Node: {os.getenv('NODE_NAME', 'unknown')}")
    logger.info("=" * 70)

    try:
        # Create appropriate worker based on mode
        with log_timing(logger, "worker_total_execution"):
            if use_queue:
                logger.info("Starting in QUEUE mode (Milestone 2+)")
                worker = QueueWorker()
            else:
                logger.info("Starting in STATIC mode (Milestone 1)")
                worker = DistributedWorker()

            summary = worker.run()

        # Optionally save results to file (static mode only)
        if not use_queue:
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
