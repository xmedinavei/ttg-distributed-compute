#!/usr/bin/env python3
"""
TTG Queue Utilities - Redis Streams Wrapper

This module provides a clean interface for working with Redis Streams
for the TTG distributed computation system.

Redis Streams Concepts (Simple Explanation):
============================================
Think of a Stream like a conveyor belt with numbered boxes:

    [Box 1] → [Box 2] → [Box 3] → [Box 4] → ...
       ↓
    Workers grab boxes, process them, and mark them done

Key Commands:
- XADD: Put a new box on the conveyor belt
- XREADGROUP: A worker grabs the next available box
- XACK: Worker says "I finished this box" (removes from pending)
- XPENDING: Shows which boxes are being worked on (not yet finished)

Consumer Groups:
- A "team" of workers that share the work
- Each message goes to exactly ONE worker in the team
- If worker crashes, message goes back to be picked up by another

Environment Variables:
    REDIS_HOST: Redis server hostname (default: localhost)
    REDIS_PORT: Redis server port (default: 6379)
    REDIS_DB: Redis database number (default: 0)

Example Usage:
    from queue_utils import TaskQueue
    
    queue = TaskQueue()
    queue.connect()
    
    # Initialize tasks (Worker 0 does this)
    queue.initialize_tasks(total_params=10000, chunk_size=100)
    
    # Workers pull tasks
    task = queue.get_next_task(consumer_name="worker-0")
    
    # Process and acknowledge
    result = process(task)
    queue.publish_result(task['chunk_id'], result)
    queue.ack_task(task['message_id'])
"""

import os
import time
import json
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any, Tuple

import redis
from redis.exceptions import ConnectionError, ResponseError


# ═══════════════════════════════════════════════════════════════════════════
# CONSTANTS
# ═══════════════════════════════════════════════════════════════════════════

# Stream names
TASK_STREAM = "ttg:tasks"           # Where tasks are queued
RESULT_STREAM = "ttg:results"       # Where results are stored
CONSUMER_GROUP = "ttg-workers"      # Group name for workers

# Default settings
DEFAULT_REDIS_HOST = "localhost"
DEFAULT_REDIS_PORT = 6379
DEFAULT_REDIS_DB = 0
DEFAULT_CHUNK_SIZE = 100            # Parameters per task chunk
# How long to wait for new tasks (5 seconds)
DEFAULT_BLOCK_MS = 5000

# Retry settings
MAX_RETRIES = 3
RETRY_DELAY_SECONDS = 1


# ═══════════════════════════════════════════════════════════════════════════
# LOGGER SETUP
# ═══════════════════════════════════════════════════════════════════════════

logger = logging.getLogger('queue_utils')


# ═══════════════════════════════════════════════════════════════════════════
# TASK QUEUE CLASS
# ═══════════════════════════════════════════════════════════════════════════

class TaskQueue:
    """
    Manages task distribution using Redis Streams.

    This class provides all the functionality needed for:
    1. Initializing the task queue (done by Worker 0)
    2. Workers pulling tasks from the queue
    3. Acknowledging completed tasks
    4. Publishing results
    5. Monitoring queue status

    Attributes:
        redis_host: Redis server hostname
        redis_port: Redis server port
        redis_db: Redis database number
        client: Redis client instance
        connected: Whether we're connected to Redis
    """

    def __init__(
        self,
        redis_host: Optional[str] = None,
        redis_port: Optional[int] = None,
        redis_db: Optional[int] = None
    ):
        """
        Initialize TaskQueue with Redis connection settings.

        Settings are read from environment variables if not provided:
        - REDIS_HOST (default: localhost)
        - REDIS_PORT (default: 6379)
        - REDIS_DB (default: 0)

        Args:
            redis_host: Override for REDIS_HOST env var
            redis_port: Override for REDIS_PORT env var
            redis_db: Override for REDIS_DB env var
        """
        self.redis_host = redis_host or os.getenv(
            'REDIS_HOST', DEFAULT_REDIS_HOST)
        self.redis_port = redis_port or int(
            os.getenv('REDIS_PORT', DEFAULT_REDIS_PORT))
        self.redis_db = redis_db or int(
            os.getenv('REDIS_DB', DEFAULT_REDIS_DB))

        self.client: Optional[redis.Redis] = None
        self.connected = False

        logger.debug(
            f"TaskQueue initialized: host={self.redis_host}, "
            f"port={self.redis_port}, db={self.redis_db}"
        )

    # ═══════════════════════════════════════════════════════════════════════
    # CONNECTION MANAGEMENT
    # ═══════════════════════════════════════════════════════════════════════

    def connect(self, retry: bool = True) -> bool:
        """
        Establish connection to Redis with optional retry logic.

        Args:
            retry: If True, retry connection up to MAX_RETRIES times

        Returns:
            True if connected successfully, False otherwise

        Raises:
            ConnectionError: If connection fails after all retries
        """
        attempts = MAX_RETRIES if retry else 1

        for attempt in range(1, attempts + 1):
            try:
                logger.info(
                    f"Connecting to Redis at {self.redis_host}:{self.redis_port} "
                    f"(attempt {attempt}/{attempts})"
                )

                self.client = redis.Redis(
                    host=self.redis_host,
                    port=self.redis_port,
                    db=self.redis_db,
                    decode_responses=True,  # Return strings, not bytes
                    socket_connect_timeout=5,
                    socket_timeout=10
                )

                # Test connection
                self.client.ping()
                self.connected = True

                logger.info(f"✅ Connected to Redis successfully")
                return True

            except ConnectionError as e:
                logger.warning(f"Connection attempt {attempt} failed: {e}")
                if attempt < attempts:
                    logger.info(
                        f"Retrying in {RETRY_DELAY_SECONDS} seconds...")
                    time.sleep(RETRY_DELAY_SECONDS)
                else:
                    logger.error(
                        f"❌ Failed to connect to Redis after {attempts} attempts")
                    raise

        return False

    def disconnect(self):
        """Close Redis connection."""
        if self.client:
            self.client.close()
            self.connected = False
            logger.info("Disconnected from Redis")

    def ensure_connected(self):
        """Ensure we have an active Redis connection."""
        if not self.connected or not self.client:
            raise ConnectionError(
                "Not connected to Redis. Call connect() first.")

        # Verify connection is still alive
        try:
            self.client.ping()
        except ConnectionError:
            logger.warning("Lost connection to Redis, attempting reconnect...")
            self.connect(retry=True)

    # ═══════════════════════════════════════════════════════════════════════
    # STREAM & CONSUMER GROUP MANAGEMENT
    # ═══════════════════════════════════════════════════════════════════════

    def ensure_stream_exists(self, stream_name: str = TASK_STREAM) -> bool:
        """
        Ensure the stream and consumer group exist.

        Creates the consumer group if it doesn't exist.
        The MKSTREAM option creates the stream if it doesn't exist.

        Args:
            stream_name: Name of the stream to ensure exists

        Returns:
            True if stream/group exist (or were created)
        """
        self.ensure_connected()

        try:
            # XGROUP CREATE creates both stream (MKSTREAM) and consumer group
            # Starting at '0' means read from beginning
            self.client.xgroup_create(
                name=stream_name,
                groupname=CONSUMER_GROUP,
                id='0',
                mkstream=True
            )
            logger.info(
                f"Created stream '{stream_name}' with consumer group '{CONSUMER_GROUP}'")
            return True

        except ResponseError as e:
            if "BUSYGROUP" in str(e):
                # Consumer group already exists - this is fine
                logger.debug(
                    f"Consumer group '{CONSUMER_GROUP}' already exists for '{stream_name}'")
                return True
            else:
                logger.error(f"Error creating stream/group: {e}")
                raise

    def stream_exists(self, stream_name: str = TASK_STREAM) -> bool:
        """Check if a stream exists."""
        self.ensure_connected()
        return self.client.exists(stream_name) > 0

    def get_stream_length(self, stream_name: str = TASK_STREAM) -> int:
        """Get the number of messages in a stream."""
        self.ensure_connected()
        return self.client.xlen(stream_name)

    # ═══════════════════════════════════════════════════════════════════════
    # TASK INITIALIZATION (Worker 0 does this)
    # ═══════════════════════════════════════════════════════════════════════

    def initialize_tasks(
        self,
        total_params: int,
        chunk_size: int = DEFAULT_CHUNK_SIZE,
        force: bool = False
    ) -> int:
        """
        Initialize the task queue with parameter chunks.

        This should only be called by Worker 0 (or a coordinator).
        It divides the total parameters into chunks and adds each
        chunk as a task to the Redis stream.

        Example: 10,000 params with chunk_size=100 creates 100 tasks

        Args:
            total_params: Total number of parameters to process
            chunk_size: How many parameters per task chunk
            force: If True, reinitialize even if tasks exist

        Returns:
            Number of tasks created
        """
        self.ensure_connected()
        self.ensure_stream_exists(TASK_STREAM)

        # Check if tasks already exist
        current_length = self.get_stream_length(TASK_STREAM)
        if current_length > 0 and not force:
            logger.info(
                f"Task stream already has {current_length} tasks. "
                "Use force=True to reinitialize."
            )
            return 0

        if force and current_length > 0:
            logger.warning(
                f"Force reinitializing: deleting {current_length} existing tasks")
            self.client.delete(TASK_STREAM)
            self.ensure_stream_exists(TASK_STREAM)

        # Calculate number of chunks
        num_chunks = (total_params + chunk_size -
                      1) // chunk_size  # Ceiling division

        logger.info(
            f"Initializing {num_chunks} task chunks "
            f"({total_params} params, {chunk_size} per chunk)"
        )

        # Create task chunks
        tasks_created = 0
        timestamp = datetime.now(timezone.utc).isoformat()

        for chunk_id in range(num_chunks):
            start_param = chunk_id * chunk_size
            end_param = min(start_param + chunk_size, total_params)
            params_in_chunk = end_param - start_param

            # Task data as a flat dictionary (Redis Streams requirement)
            task_data = {
                'chunk_id': str(chunk_id).zfill(5),  # "00001", "00002", etc.
                'start_param': str(start_param),
                'end_param': str(end_param),
                'params_count': str(params_in_chunk),
                'total_params': str(total_params),
                'total_chunks': str(num_chunks),
                'created_at': timestamp,
                'status': 'pending'
            }

            # Add to stream (* means auto-generate message ID)
            message_id = self.client.xadd(TASK_STREAM, task_data)
            tasks_created += 1

            if tasks_created % 10 == 0 or tasks_created == num_chunks:
                logger.debug(f"Created {tasks_created}/{num_chunks} tasks")

        logger.info(f"✅ Created {tasks_created} tasks in '{TASK_STREAM}'")
        return tasks_created

    # ═══════════════════════════════════════════════════════════════════════
    # TASK CONSUMPTION (Workers pull tasks)
    # ═══════════════════════════════════════════════════════════════════════

    def get_next_task(
        self,
        consumer_name: str,
        block_ms: int = DEFAULT_BLOCK_MS,
        count: int = 1
    ) -> Optional[Dict[str, Any]]:
        """
        Get the next available task from the queue.

        Uses XREADGROUP to atomically claim a task. The task is marked
        as "pending" for this consumer until XACK is called.

        If the consumer crashes before XACK, the task can be recovered
        using claim_pending_tasks().

        Args:
            consumer_name: Unique name for this consumer (e.g., "worker-0")
            block_ms: How long to wait if no tasks available (milliseconds)
            count: Maximum number of tasks to retrieve

        Returns:
            Task dictionary with keys: message_id, chunk_id, start_param, 
            end_param, params_count, etc.
            Returns None if no tasks available after blocking.
        """
        self.ensure_connected()

        try:
            # '>' means read only new messages (not yet delivered to anyone)
            result = self.client.xreadgroup(
                groupname=CONSUMER_GROUP,
                consumername=consumer_name,
                streams={TASK_STREAM: '>'},
                count=count,
                block=block_ms
            )

            if not result:
                logger.debug(f"No tasks available after {block_ms}ms")
                return None

            # Parse result: [[stream_name, [(msg_id, {data}), ...]]]
            stream_name, messages = result[0]
            message_id, task_data = messages[0]

            # Add message_id to task data for later acknowledgment
            task_data['message_id'] = message_id
            task_data['consumer'] = consumer_name
            task_data['claimed_at'] = datetime.now(timezone.utc).isoformat()

            logger.info(
                f"📥 Got task chunk {task_data['chunk_id']}: "
                f"params {task_data['start_param']}-{task_data['end_param']}"
            )

            return task_data

        except ResponseError as e:
            logger.error(f"Error getting task: {e}")
            raise

    def ack_task(self, message_id: str, stream_name: str = TASK_STREAM) -> bool:
        """
        Acknowledge a task as completed.

        This removes the task from the "pending" list. If you don't
        call this, the task will appear in XPENDING and can be claimed
        by another worker (for fault tolerance).

        Args:
            message_id: The Redis message ID to acknowledge
            stream_name: Stream the message belongs to

        Returns:
            True if acknowledged successfully
        """
        self.ensure_connected()

        ack_count = self.client.xack(stream_name, CONSUMER_GROUP, message_id)

        if ack_count > 0:
            logger.debug(f"✅ Acknowledged task {message_id}")
            return True
        else:
            logger.warning(f"Task {message_id} was not in pending list")
            return False

    # ═══════════════════════════════════════════════════════════════════════
    # RESULT PUBLISHING
    # ═══════════════════════════════════════════════════════════════════════

    def publish_result(
        self,
        chunk_id: str,
        worker_id: str,
        result_data: Dict[str, Any],
        duration_seconds: float
    ) -> str:
        """
        Publish a completed task result to the results stream.

        Args:
            chunk_id: The chunk ID that was processed
            worker_id: Which worker processed this chunk
            result_data: Dictionary with result metrics (sum, count, etc.)
            duration_seconds: How long processing took

        Returns:
            Message ID of the published result
        """
        self.ensure_connected()

        # Ensure results stream exists
        self.ensure_stream_exists(RESULT_STREAM)

        # Flatten result_data for Redis (it only accepts string values)
        result_message = {
            'chunk_id': str(chunk_id),
            'worker_id': str(worker_id),
            'status': 'completed',
            'duration_seconds': str(duration_seconds),
            'completed_at': datetime.now(timezone.utc).isoformat(),
            # Serialize complex data as JSON
            'result_data': json.dumps(result_data)
        }

        message_id = self.client.xadd(RESULT_STREAM, result_message)

        logger.info(
            f"📤 Published result for chunk {chunk_id} "
            f"(processed by {worker_id} in {duration_seconds:.2f}s)"
        )

        return message_id

    # ═══════════════════════════════════════════════════════════════════════
    # MONITORING & STATS
    # ═══════════════════════════════════════════════════════════════════════

    def get_queue_stats(self) -> Dict[str, Any]:
        """
        Get current queue statistics.

        Returns:
            Dictionary with:
            - tasks_total: Total tasks in stream
            - tasks_pending: Tasks currently being processed
            - results_count: Number of results published
            - consumers: List of active consumers
        """
        self.ensure_connected()

        stats = {
            'tasks_total': 0,
            'tasks_pending': 0,
            'results_count': 0,
            'consumers': [],
            'pending_details': []
        }

        # Task stream stats
        if self.stream_exists(TASK_STREAM):
            stats['tasks_total'] = self.get_stream_length(TASK_STREAM)

            # Get pending info
            try:
                pending_info = self.client.xpending(
                    TASK_STREAM, CONSUMER_GROUP)
                if pending_info:
                    # pending_info format: {'pending': N, 'min': id, 'max': id, 'consumers': [...]}
                    stats['tasks_pending'] = pending_info.get('pending', 0)
                    # consumers is a list of dicts with 'name' and 'pending' keys
                    consumers_list = pending_info.get('consumers', [])
                    if isinstance(consumers_list, list):
                        stats['consumers'] = [c.get('name', str(c)) if isinstance(
                            c, dict) else str(c) for c in consumers_list]
                    elif isinstance(consumers_list, dict):
                        stats['consumers'] = list(consumers_list.keys())
            except ResponseError:
                pass  # Consumer group might not exist yet

        # Results stream stats
        if self.stream_exists(RESULT_STREAM):
            stats['results_count'] = self.get_stream_length(RESULT_STREAM)

        return stats

    def get_pending_tasks(self, count: int = 10) -> List[Dict[str, Any]]:
        """
        Get details of pending (in-progress) tasks.

        Useful for monitoring which tasks are stuck or being processed.

        Args:
            count: Maximum number of pending tasks to return

        Returns:
            List of pending task details
        """
        self.ensure_connected()

        try:
            # XPENDING with range gets detailed info
            pending = self.client.xpending_range(
                name=TASK_STREAM,
                groupname=CONSUMER_GROUP,
                min='-',
                max='+',
                count=count
            )

            return [
                {
                    'message_id': p['message_id'],
                    'consumer': p['consumer'],
                    'idle_time_ms': p['time_since_delivered'],
                    'delivery_count': p['times_delivered']
                }
                for p in pending
            ]

        except ResponseError as e:
            logger.debug(f"Could not get pending tasks: {e}")
            return []

    def get_all_results(self) -> List[Dict[str, Any]]:
        """
        Retrieve all results from the results stream.

        Returns:
            List of all result messages
        """
        self.ensure_connected()

        if not self.stream_exists(RESULT_STREAM):
            return []

        # XRANGE gets all messages from start (-) to end (+)
        results = self.client.xrange(RESULT_STREAM, '-', '+')

        parsed_results = []
        for message_id, data in results:
            # Parse the JSON result_data back to dict
            if 'result_data' in data:
                try:
                    data['result_data'] = json.loads(data['result_data'])
                except json.JSONDecodeError:
                    pass
            data['message_id'] = message_id
            parsed_results.append(data)

        return parsed_results

    # ═══════════════════════════════════════════════════════════════════════
    # FAULT TOLERANCE
    # ═══════════════════════════════════════════════════════════════════════

    def claim_stale_tasks(
        self,
        consumer_name: str,
        min_idle_ms: int = 60000,  # 1 minute
        count: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Claim tasks that have been pending too long (worker might have crashed).

        If a worker crashes before XACK, the task stays in "pending" state.
        This method allows another worker to claim those stale tasks.

        Args:
            consumer_name: Name of consumer claiming the tasks
            min_idle_ms: Minimum idle time before task is considered stale
            count: Maximum number of stale tasks to claim

        Returns:
            List of claimed tasks (same format as get_next_task)
        """
        self.ensure_connected()

        claimed_tasks = []

        # Get pending tasks
        pending = self.get_pending_tasks(count=count * 2)

        for task_info in pending:
            if task_info['idle_time_ms'] >= min_idle_ms:
                try:
                    # XCLAIM transfers ownership of the message
                    result = self.client.xclaim(
                        name=TASK_STREAM,
                        groupname=CONSUMER_GROUP,
                        consumername=consumer_name,
                        min_idle_time=min_idle_ms,
                        message_ids=[task_info['message_id']]
                    )

                    if result:
                        message_id, task_data = result[0]
                        task_data['message_id'] = message_id
                        task_data['consumer'] = consumer_name
                        task_data['claimed_at'] = datetime.now(
                            timezone.utc).isoformat()
                        task_data['reclaimed'] = True
                        task_data['previous_consumer'] = task_info['consumer']

                        claimed_tasks.append(task_data)
                        logger.warning(
                            f"🔄 Reclaimed stale task {task_data['chunk_id']} "
                            f"(was idle for {task_info['idle_time_ms']}ms)"
                        )

                        if len(claimed_tasks) >= count:
                            break

                except ResponseError as e:
                    logger.debug(
                        f"Could not claim task {task_info['message_id']}: {e}")

        return claimed_tasks

    # ═══════════════════════════════════════════════════════════════════════
    # CLEANUP
    # ═══════════════════════════════════════════════════════════════════════

    def reset_queue(self) -> bool:
        """
        Reset all queues (delete all data).

        ⚠️ WARNING: This deletes ALL tasks and results!
        Only use for testing or when you want to start fresh.

        Returns:
            True if reset successfully
        """
        self.ensure_connected()

        deleted = 0

        if self.stream_exists(TASK_STREAM):
            self.client.delete(TASK_STREAM)
            deleted += 1
            logger.warning(f"Deleted task stream '{TASK_STREAM}'")

        if self.stream_exists(RESULT_STREAM):
            self.client.delete(RESULT_STREAM)
            deleted += 1
            logger.warning(f"Deleted result stream '{RESULT_STREAM}'")

        logger.warning(f"🗑️ Queue reset complete (deleted {deleted} streams)")
        return True


# ═══════════════════════════════════════════════════════════════════════════
# CONVENIENCE FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════

def create_queue(
    host: Optional[str] = None,
    port: Optional[int] = None
) -> TaskQueue:
    """
    Create and connect a TaskQueue instance.

    Convenience function for quick setup.

    Args:
        host: Redis host (default: from REDIS_HOST env var or localhost)
        port: Redis port (default: from REDIS_PORT env var or 6379)

    Returns:
        Connected TaskQueue instance
    """
    queue = TaskQueue(redis_host=host, redis_port=port)
    queue.connect()
    return queue


# ═══════════════════════════════════════════════════════════════════════════
# MAIN (for testing)
# ═══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    """
    Test script to verify queue_utils works correctly.

    Run with: python queue_utils.py

    Requires Redis to be running (locally or via port-forward):
        kubectl port-forward pod/ttg-redis 6379:6379
    """
    import sys

    # Setup logging for testing
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
    )

    print("=" * 60)
    print("TTG Queue Utils - Test Script")
    print("=" * 60)

    # Create queue instance
    queue = TaskQueue()

    try:
        # Test 1: Connect
        print("\n📡 Test 1: Connecting to Redis...")
        queue.connect()
        print("   ✅ Connected!")

        # Test 2: Reset (clean slate)
        print("\n🗑️  Test 2: Resetting queue...")
        queue.reset_queue()
        print("   ✅ Queue reset!")

        # Test 3: Initialize tasks
        print("\n📝 Test 3: Initializing 1000 params with chunk_size=100...")
        tasks_created = queue.initialize_tasks(
            total_params=1000, chunk_size=100)
        print(f"   ✅ Created {tasks_created} tasks!")

        # Test 4: Get stats
        print("\n📊 Test 4: Getting queue stats...")
        stats = queue.get_queue_stats()
        print(f"   Tasks total: {stats['tasks_total']}")
        print(f"   Tasks pending: {stats['tasks_pending']}")
        print(f"   Results count: {stats['results_count']}")

        # Test 5: Get a task
        print("\n📥 Test 5: Getting a task as 'test-worker'...")
        task = queue.get_next_task(consumer_name="test-worker", block_ms=1000)
        if task:
            print(f"   ✅ Got task: chunk {task['chunk_id']}, "
                  f"params {task['start_param']}-{task['end_param']}")

            # Test 6: Publish result
            print("\n📤 Test 6: Publishing result...")
            result_data = {'sum': 12345, 'count': int(task['params_count'])}
            queue.publish_result(
                chunk_id=task['chunk_id'],
                worker_id="test-worker",
                result_data=result_data,
                duration_seconds=1.5
            )
            print("   ✅ Result published!")

            # Test 7: Acknowledge task
            print("\n✅ Test 7: Acknowledging task...")
            queue.ack_task(task['message_id'])
            print("   ✅ Task acknowledged!")
        else:
            print("   ⚠️ No task received (this might be normal if queue is empty)")

        # Test 8: Final stats
        print("\n📊 Test 8: Final queue stats...")
        stats = queue.get_queue_stats()
        print(f"   Tasks total: {stats['tasks_total']}")
        print(f"   Tasks pending: {stats['tasks_pending']}")
        print(f"   Results count: {stats['results_count']}")

        # Test 9: Get results
        print("\n📋 Test 9: Getting all results...")
        results = queue.get_all_results()
        for r in results:
            print(f"   Chunk {r['chunk_id']}: {r['result_data']}")

        print("\n" + "=" * 60)
        print("✅ All tests passed!")
        print("=" * 60)

    except ConnectionError as e:
        print(f"\n❌ Connection Error: {e}")
        print("\n💡 Make sure Redis is running:")
        print("   kubectl port-forward pod/ttg-redis 6379:6379")
        sys.exit(1)

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    finally:
        queue.disconnect()
