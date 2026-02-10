#!/usr/bin/env python3
"""
RabbitMQ queue backend for TTG queue mode.

This module mirrors the TaskQueue methods used by QueueWorker so we can
switch queue backends with QUEUE_BACKEND=redis|rabbitmq.
"""

import json
import logging
import os
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import pika
from pika.exceptions import AMQPConnectionError


logger = logging.getLogger("rabbitmq_queue")

# Queue/exchange defaults
TASK_EXCHANGE = "ttg.tasks.exchange"
TASK_QUEUE = "ttg.tasks"
TASK_ROUTING_KEY = "ttg.tasks"
RETRY_EXCHANGE = "ttg.retry.exchange"
RETRY_QUEUE = "ttg.tasks.retry"
RETRY_ROUTING_KEY = "ttg.tasks.retry"
DLQ_EXCHANGE = "ttg.dlq.exchange"
DLQ_QUEUE = "ttg.tasks.dlq"
DLQ_ROUTING_KEY = "ttg.tasks.dlq"

RESULT_EXCHANGE = "ttg.results.exchange"
RESULT_QUEUE = "ttg.results"
RESULT_ROUTING_KEY = "ttg.results"

MAX_RETRIES = 3
RETRY_DELAY_SECONDS = 2


class RabbitMQTaskQueue:
    """RabbitMQ implementation of queue operations used by QueueWorker."""

    def __init__(self, rabbitmq_host: Optional[str] = None, rabbitmq_port: Optional[int] = None):
        self.rabbitmq_host = rabbitmq_host or os.getenv("RABBITMQ_HOST", "ttg-rabbitmq")
        self.rabbitmq_port = rabbitmq_port or int(os.getenv("RABBITMQ_PORT", "5672"))
        self.rabbitmq_user = os.getenv("RABBITMQ_USER", "guest")
        self.rabbitmq_password = os.getenv("RABBITMQ_PASSWORD", "guest")
        self.rabbitmq_vhost = os.getenv("RABBITMQ_VHOST", "/")

        self.task_queue = os.getenv("RABBITMQ_TASK_QUEUE", TASK_QUEUE)
        self.result_queue = os.getenv("RABBITMQ_RESULT_QUEUE", RESULT_QUEUE)

        self.retry_queue = os.getenv("RABBITMQ_RETRY_QUEUE", RETRY_QUEUE)
        self.dlq_queue = os.getenv("RABBITMQ_DLQ_QUEUE", DLQ_QUEUE)

        self.max_retries = int(os.getenv("RABBITMQ_MAX_RETRIES", str(MAX_RETRIES)))
        self.retry_delay_ms = int(os.getenv("RABBITMQ_RETRY_DELAY_MS", "5000"))

        self.connection: Optional[pika.BlockingConnection] = None
        self.channel: Optional[pika.adapters.blocking_connection.BlockingChannel] = None
        self.connected = False

    def _ensure_connected(self) -> None:
        if not self.connected or self.connection is None or self.channel is None:
            raise RuntimeError("Not connected to RabbitMQ. Call connect() first.")

    def _connection_params(self) -> pika.ConnectionParameters:
        credentials = pika.PlainCredentials(self.rabbitmq_user, self.rabbitmq_password)
        heartbeat = int(os.getenv("RABBITMQ_HEARTBEAT_SECONDS", "30"))
        blocked_timeout = int(os.getenv("RABBITMQ_BLOCKED_TIMEOUT_SECONDS", "60"))
        return pika.ConnectionParameters(
            host=self.rabbitmq_host,
            port=self.rabbitmq_port,
            virtual_host=self.rabbitmq_vhost,
            credentials=credentials,
            heartbeat=heartbeat,
            blocked_connection_timeout=blocked_timeout,
        )

    def connect(self, retry: bool = True) -> bool:
        attempts = 3 if retry else 1
        for attempt in range(1, attempts + 1):
            try:
                logger.info(
                    "Connecting to RabbitMQ at %s:%s (attempt %s/%s)",
                    self.rabbitmq_host,
                    self.rabbitmq_port,
                    attempt,
                    attempts,
                )
                self.connection = pika.BlockingConnection(self._connection_params())
                self.channel = self.connection.channel()
                self.channel.basic_qos(prefetch_count=1)
                self.connected = True
                self._declare_topology()
                logger.info("✅ Connected to RabbitMQ")
                return True
            except AMQPConnectionError as exc:
                logger.warning("RabbitMQ connection attempt failed: %s", exc)
                if attempt < attempts:
                    time.sleep(RETRY_DELAY_SECONDS)
                else:
                    raise
        return False

    def disconnect(self) -> None:
        if self.connection and self.connection.is_open:
            self.connection.close()
        self.connection = None
        self.channel = None
        self.connected = False
        logger.info("Disconnected from RabbitMQ")

    def _declare_topology(self) -> None:
        self._ensure_connected()

        # Task path
        self.channel.exchange_declare(exchange=TASK_EXCHANGE, exchange_type="direct", durable=True)
        self.channel.queue_declare(queue=self.task_queue, durable=True)
        self.channel.queue_bind(queue=self.task_queue, exchange=TASK_EXCHANGE, routing_key=TASK_ROUTING_KEY)

        # Retry path (TTL then back to main task queue)
        self.channel.exchange_declare(exchange=RETRY_EXCHANGE, exchange_type="direct", durable=True)
        self.channel.queue_declare(
            queue=self.retry_queue,
            durable=True,
            arguments={
                "x-message-ttl": self.retry_delay_ms,
                "x-dead-letter-exchange": TASK_EXCHANGE,
                "x-dead-letter-routing-key": TASK_ROUTING_KEY,
            },
        )
        self.channel.queue_bind(queue=self.retry_queue, exchange=RETRY_EXCHANGE, routing_key=RETRY_ROUTING_KEY)

        # Dead-letter path
        self.channel.exchange_declare(exchange=DLQ_EXCHANGE, exchange_type="direct", durable=True)
        self.channel.queue_declare(queue=self.dlq_queue, durable=True)
        self.channel.queue_bind(queue=self.dlq_queue, exchange=DLQ_EXCHANGE, routing_key=DLQ_ROUTING_KEY)

        # Results path
        self.channel.exchange_declare(exchange=RESULT_EXCHANGE, exchange_type="direct", durable=True)
        self.channel.queue_declare(queue=self.result_queue, durable=True)
        self.channel.queue_bind(queue=self.result_queue, exchange=RESULT_EXCHANGE, routing_key=RESULT_ROUTING_KEY)

    def get_stream_length(self) -> int:
        self._ensure_connected()
        queue = self.channel.queue_declare(queue=self.task_queue, durable=True, passive=True)
        return int(queue.method.message_count)

    def initialize_tasks(self, total_params: int, chunk_size: int = 100, force: bool = False) -> int:
        self._ensure_connected()
        if force:
            self.channel.queue_purge(self.task_queue)
            self.channel.queue_purge(self.result_queue)
            self.channel.queue_purge(self.retry_queue)
            self.channel.queue_purge(self.dlq_queue)

        current_tasks = self.get_stream_length()
        if current_tasks > 0 and not force:
            logger.info("Task queue already contains %s tasks. Skipping initialization.", current_tasks)
            return 0

        num_chunks = (total_params + chunk_size - 1) // chunk_size
        created_at = datetime.now(timezone.utc).isoformat()

        for chunk_id in range(num_chunks):
            start_param = chunk_id * chunk_size
            end_param = min(start_param + chunk_size, total_params)
            params_in_chunk = end_param - start_param
            task_data = {
                "chunk_id": str(chunk_id).zfill(5),
                "start_param": str(start_param),
                "end_param": str(end_param),
                "params_count": str(params_in_chunk),
                "total_params": str(total_params),
                "total_chunks": str(num_chunks),
                "created_at": created_at,
                "status": "pending",
                "retry_count": 0,
            }
            self.channel.basic_publish(
                exchange=TASK_EXCHANGE,
                routing_key=TASK_ROUTING_KEY,
                body=json.dumps(task_data),
                properties=pika.BasicProperties(
                    content_type="application/json",
                    delivery_mode=2,
                    message_id=task_data["chunk_id"],
                ),
            )

        logger.info("✅ Created %s tasks in RabbitMQ queue '%s'", num_chunks, self.task_queue)
        return num_chunks

    def get_next_task(self, consumer_name: str, block_ms: int = 5000, count: int = 1) -> Optional[Dict[str, Any]]:
        del consumer_name, count  # Not needed with RabbitMQ basic_get
        self._ensure_connected()

        deadline = time.time() + (block_ms / 1000.0)
        while time.time() < deadline:
            method, properties, body = self.channel.basic_get(queue=self.task_queue, auto_ack=False)
            if method is not None and body is not None:
                task = json.loads(body.decode("utf-8"))
                task["message_id"] = str(method.delivery_tag)
                task["_delivery_tag"] = method.delivery_tag
                task["_properties"] = properties.headers or {}
                return task
            time.sleep(0.2)
        return None

    def ack_task(self, message_id: str) -> bool:
        self._ensure_connected()
        try:
            self.channel.basic_ack(delivery_tag=int(message_id))
            return True
        except Exception as exc:
            logger.warning("Failed to ack RabbitMQ message %s: %s", message_id, exc)
            return False

    def nack_task(self, message_id: str, task_data: Dict[str, Any], reason: str) -> bool:
        """
        Retry or dead-letter a failed task, then ACK the original message.
        """
        self._ensure_connected()
        retry_count = int(task_data.get("retry_count", 0))
        updated = dict(task_data)
        updated["retry_count"] = retry_count + 1
        updated["last_error"] = reason
        updated["failed_at"] = datetime.now(timezone.utc).isoformat()

        if retry_count < self.max_retries:
            self.channel.basic_publish(
                exchange=RETRY_EXCHANGE,
                routing_key=RETRY_ROUTING_KEY,
                body=json.dumps(updated),
                properties=pika.BasicProperties(
                    content_type="application/json",
                    delivery_mode=2,
                    message_id=str(updated.get("chunk_id", "")),
                    headers={"retry_count": updated["retry_count"], "last_error": reason},
                ),
            )
            logger.warning(
                "Task %s failed, sent to retry queue (%s/%s): %s",
                updated.get("chunk_id"),
                updated["retry_count"],
                self.max_retries,
                reason,
            )
        else:
            updated["status"] = "dead_lettered"
            self.channel.basic_publish(
                exchange=DLQ_EXCHANGE,
                routing_key=DLQ_ROUTING_KEY,
                body=json.dumps(updated),
                properties=pika.BasicProperties(
                    content_type="application/json",
                    delivery_mode=2,
                    message_id=str(updated.get("chunk_id", "")),
                    headers={"retry_count": updated["retry_count"], "final_error": reason},
                ),
            )
            logger.error("Task %s moved to DLQ after retries: %s", updated.get("chunk_id"), reason)

        return self.ack_task(message_id)

    def publish_result(
        self,
        chunk_id: str,
        worker_id: str,
        result_data: Dict[str, Any],
        duration_seconds: float,
    ) -> str:
        self._ensure_connected()
        result_message = {
            "chunk_id": str(chunk_id),
            "worker_id": str(worker_id),
            "status": "completed",
            "duration_seconds": str(duration_seconds),
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "result_data": json.dumps(result_data),
        }
        self.channel.basic_publish(
            exchange=RESULT_EXCHANGE,
            routing_key=RESULT_ROUTING_KEY,
            body=json.dumps(result_message),
            properties=pika.BasicProperties(
                content_type="application/json",
                delivery_mode=2,
                message_id=str(chunk_id),
            ),
        )
        return str(chunk_id)

    def claim_stale_tasks(self, consumer_name: str, min_idle_ms: int = 60000, count: int = 10) -> List[Dict[str, Any]]:
        del consumer_name, min_idle_ms, count
        # RabbitMQ handles in-flight task redelivery on consumer disconnect.
        return []

    def get_queue_stats(self) -> Dict[str, Any]:
        self._ensure_connected()

        task_info = self.channel.queue_declare(queue=self.task_queue, durable=True, passive=True)
        result_info = self.channel.queue_declare(queue=self.result_queue, durable=True, passive=True)
        retry_info = self.channel.queue_declare(queue=self.retry_queue, durable=True, passive=True)
        dlq_info = self.channel.queue_declare(queue=self.dlq_queue, durable=True, passive=True)

        return {
            "backend": "rabbitmq",
            "tasks_total": int(task_info.method.message_count),
            "tasks_pending": 0,
            "results_count": int(result_info.method.message_count),
            "retry_count": int(retry_info.method.message_count),
            "dead_letter_count": int(dlq_info.method.message_count),
            "consumers": [f"{int(task_info.method.consumer_count)} active consumer(s)"],
        }
