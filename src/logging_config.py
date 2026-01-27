#!/usr/bin/env python3
"""
TTG Logging Configuration Module

Provides structured, configurable logging for distributed workers.
Supports both human-readable and JSON formats for log aggregation.

Features:
    - Configurable log levels via LOG_LEVEL environment variable
    - JSON structured logging via LOG_FORMAT=json
    - Automatic context injection (worker_id, hostname, timestamp)
    - Performance timing utilities
    - Lifecycle event helpers

Environment Variables:
    LOG_LEVEL: DEBUG, INFO, WARNING, ERROR, CRITICAL (default: INFO)
    LOG_FORMAT: text, json (default: text)
    LOG_INCLUDE_TIMESTAMP: true/false (default: true)

Usage:
    from logging_config import setup_logging, get_logger
    
    setup_logging(worker_id=0)
    logger = get_logger(__name__)
    logger.info("Processing started", extra={"batch_id": 1})
"""

import os
import sys
import json
import logging
import time
from datetime import datetime, timezone
from functools import wraps
from typing import Any, Dict, Optional, Callable
from contextlib import contextmanager


# ═══════════════════════════════════════════════════════════════════════════
# CUSTOM LOG FORMATTER - JSON FORMAT
# ═══════════════════════════════════════════════════════════════════════════

class JSONFormatter(logging.Formatter):
    """
    Formats log records as JSON for structured logging.

    Output format:
    {
        "timestamp": "2026-01-27T12:00:00.000000+00:00",
        "level": "INFO",
        "logger": "worker",
        "message": "Processing batch",
        "worker_id": 0,
        "hostname": "ttg-computation-0-xxx",
        "extra": {"batch_id": 1, "progress": 0.5}
    }
    """

    def __init__(self, worker_id: int = 0, hostname: str = None):
        super().__init__()
        self.worker_id = worker_id
        self.hostname = hostname or os.getenv('HOSTNAME', 'unknown')

    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'worker_id': self.worker_id,
            'hostname': self.hostname,
        }

        # Add any extra fields
        if hasattr(record, 'extra_data'):
            log_data['extra'] = record.extra_data

        # Add exception info if present
        if record.exc_info:
            log_data['exception'] = self.formatException(record.exc_info)

        # Add location info for debug
        if record.levelno <= logging.DEBUG:
            log_data['location'] = {
                'file': record.filename,
                'line': record.lineno,
                'function': record.funcName
            }

        return json.dumps(log_data, default=str)


# ═══════════════════════════════════════════════════════════════════════════
# CUSTOM LOG FORMATTER - TEXT FORMAT
# ═══════════════════════════════════════════════════════════════════════════

class TextFormatter(logging.Formatter):
    """
    Formats log records as human-readable text with worker context.

    Output format:
    [2026-01-27 12:00:00] [INFO ] [WORKER-0] [worker] Processing batch | batch_id=1
    """

    # ANSI color codes for terminal output
    COLORS = {
        'DEBUG': '\033[36m',     # Cyan
        'INFO': '\033[32m',      # Green
        'WARNING': '\033[33m',   # Yellow
        'ERROR': '\033[31m',     # Red
        'CRITICAL': '\033[35m',  # Magenta
        'RESET': '\033[0m'       # Reset
    }

    def __init__(self, worker_id: int = 0, use_colors: bool = True, include_timestamp: bool = True):
        super().__init__()
        self.worker_id = worker_id
        self.use_colors = use_colors and sys.stdout.isatty()
        self.include_timestamp = include_timestamp

    def format(self, record: logging.LogRecord) -> str:
        parts = []

        # Timestamp
        if self.include_timestamp:
            timestamp = datetime.now(timezone.utc).strftime(
                '%Y-%m-%d %H:%M:%S.%f')[:-3]
            parts.append(f"[{timestamp}]")

        # Level with color
        level = record.levelname.ljust(5)
        if self.use_colors:
            color = self.COLORS.get(record.levelname, '')
            reset = self.COLORS['RESET']
            parts.append(f"{color}[{level}]{reset}")
        else:
            parts.append(f"[{level}]")

        # Worker ID
        parts.append(f"[WORKER-{self.worker_id}]")

        # Logger name (shortened)
        logger_name = record.name.split('.')[-1][:12].ljust(12)
        parts.append(f"[{logger_name}]")

        # Message
        parts.append(record.getMessage())

        # Extra data as key=value pairs
        if hasattr(record, 'extra_data') and record.extra_data:
            extra_str = ' | ' + \
                ', '.join(f"{k}={v}" for k, v in record.extra_data.items())
            parts.append(extra_str)

        # Exception
        if record.exc_info:
            parts.append('\n' + self.formatException(record.exc_info))

        return ' '.join(parts)


# ═══════════════════════════════════════════════════════════════════════════
# CUSTOM LOG FILTER - EXTRA DATA INJECTION
# ═══════════════════════════════════════════════════════════════════════════

class ExtraDataFilter(logging.Filter):
    """
    Filter that processes the 'extra' parameter and adds it to the record.
    This allows: logger.info("message", extra={"key": "value"})
    """

    def filter(self, record: logging.LogRecord) -> bool:
        # Extract 'extra' dict if passed via extra parameter
        if hasattr(record, 'extra'):
            record.extra_data = record.extra
        elif not hasattr(record, 'extra_data'):
            record.extra_data = {}
        return True


# ═══════════════════════════════════════════════════════════════════════════
# LOGGING SETUP
# ═══════════════════════════════════════════════════════════════════════════

_configured = False
_worker_id = 0


def setup_logging(
    worker_id: int = None,
    level: str = None,
    format_type: str = None,
    include_timestamp: bool = None
) -> None:
    """
    Configure the logging system for the worker.

    Args:
        worker_id: Worker identifier (default: from WORKER_ID env var)
        level: Log level (default: from LOG_LEVEL env var or INFO)
        format_type: 'text' or 'json' (default: from LOG_FORMAT env var or text)
        include_timestamp: Include timestamp in text format (default: from LOG_INCLUDE_TIMESTAMP or True)

    Example:
        setup_logging(worker_id=0, level='DEBUG', format_type='json')
    """
    global _configured, _worker_id

    # Get configuration from environment or parameters
    _worker_id = worker_id if worker_id is not None else int(
        os.getenv('WORKER_ID', '0'))
    log_level = (level or os.getenv('LOG_LEVEL', 'INFO')).upper()
    log_format = format_type or os.getenv('LOG_FORMAT', 'text').lower()
    include_ts = include_timestamp if include_timestamp is not None else os.getenv(
        'LOG_INCLUDE_TIMESTAMP', 'true').lower() == 'true'

    # Convert level string to logging constant
    numeric_level = getattr(logging, log_level, logging.INFO)

    # Get root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)

    # Remove existing handlers
    root_logger.handlers.clear()

    # Create handler for stdout
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(numeric_level)

    # Add filter for extra data
    handler.addFilter(ExtraDataFilter())

    # Set formatter based on format type
    if log_format == 'json':
        formatter = JSONFormatter(worker_id=_worker_id)
    else:
        formatter = TextFormatter(
            worker_id=_worker_id,
            include_timestamp=include_ts
        )

    handler.setFormatter(formatter)
    root_logger.addHandler(handler)

    _configured = True


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance.

    Args:
        name: Logger name (typically __name__)

    Returns:
        Configured logger instance

    Example:
        logger = get_logger(__name__)
        logger.info("Hello")
    """
    if not _configured:
        setup_logging()
    return logging.getLogger(name)


# ═══════════════════════════════════════════════════════════════════════════
# LIFECYCLE EVENT LOGGING
# ═══════════════════════════════════════════════════════════════════════════

class LifecycleLogger:
    """
    Helper for logging standardized lifecycle events.

    Events:
        - STARTING: Worker initialization
        - INITIALIZED: Configuration loaded
        - RUNNING: Processing started
        - PROGRESS: Batch progress update
        - COMPLETED: Successful completion
        - FAILED: Error occurred
        - SHUTTING_DOWN: Graceful shutdown initiated
    """

    def __init__(self, logger: logging.Logger):
        self.logger = logger
        self.start_time = None

    def starting(self, **context):
        """Log worker starting event."""
        self.start_time = time.time()
        self.logger.info(
            "🚀 LIFECYCLE: STARTING",
            extra={'event': 'STARTING', 'lifecycle': True, **context}
        )

    def initialized(self, config: Dict[str, Any]):
        """Log worker initialized with configuration."""
        self.logger.info(
            "✅ LIFECYCLE: INITIALIZED",
            extra={'event': 'INITIALIZED', 'lifecycle': True, 'config': config}
        )

    def running(self, total_work: int):
        """Log worker entering running state."""
        self.logger.info(
            f"▶️  LIFECYCLE: RUNNING - Processing {total_work} items",
            extra={'event': 'RUNNING', 'lifecycle': True,
                   'total_work': total_work}
        )

    def progress(self, current: int, total: int, **metrics):
        """Log progress update."""
        percent = (current / total * 100) if total > 0 else 0
        self.logger.info(
            f"📊 LIFECYCLE: PROGRESS - {current}/{total} ({percent:.1f}%)",
            extra={'event': 'PROGRESS', 'lifecycle': True, 'current': current,
                   'total': total, 'percent': percent, **metrics}
        )

    def completed(self, summary: Dict[str, Any]):
        """Log successful completion."""
        duration = time.time() - self.start_time if self.start_time else 0
        self.logger.info(
            f"🎉 LIFECYCLE: COMPLETED - Duration: {duration:.2f}s",
            extra={'event': 'COMPLETED', 'lifecycle': True,
                   'duration_seconds': duration, 'summary': summary}
        )

    def failed(self, error: str, **context):
        """Log failure event."""
        duration = time.time() - self.start_time if self.start_time else 0
        self.logger.error(
            f"❌ LIFECYCLE: FAILED - {error}",
            extra={'event': 'FAILED', 'lifecycle': True,
                   'error': error, 'duration_seconds': duration, **context}
        )

    def shutting_down(self, reason: str = "signal received"):
        """Log graceful shutdown."""
        self.logger.warning(
            f"🛑 LIFECYCLE: SHUTTING_DOWN - {reason}",
            extra={'event': 'SHUTTING_DOWN',
                   'lifecycle': True, 'reason': reason}
        )


# ═══════════════════════════════════════════════════════════════════════════
# PERFORMANCE TIMING UTILITIES
# ═══════════════════════════════════════════════════════════════════════════

@contextmanager
def log_timing(logger: logging.Logger, operation: str, level: int = logging.DEBUG):
    """
    Context manager for timing and logging operations.

    Usage:
        with log_timing(logger, "database_query"):
            result = db.query(...)

    Output:
        [DEBUG] ⏱️  database_query completed in 0.123s
    """
    start = time.perf_counter()
    try:
        yield
    finally:
        elapsed = time.perf_counter() - start
        logger.log(
            level,
            f"⏱️  {operation} completed in {elapsed:.3f}s",
            extra={'operation': operation,
                   'duration_seconds': elapsed, 'timing': True}
        )


def timed(operation_name: str = None, level: int = logging.DEBUG):
    """
    Decorator for timing function execution.

    Usage:
        @timed("compute_batch")
        def process_batch(data):
            ...

        @timed()  # Uses function name
        def my_function():
            ...
    """
    def decorator(func: Callable) -> Callable:
        name = operation_name or func.__name__

        @wraps(func)
        def wrapper(*args, **kwargs):
            logger = get_logger(func.__module__)
            start = time.perf_counter()
            try:
                result = func(*args, **kwargs)
                elapsed = time.perf_counter() - start
                logger.log(
                    level,
                    f"⏱️  {name} completed in {elapsed:.3f}s",
                    extra={'operation': name, 'duration_seconds': elapsed,
                           'timing': True, 'status': 'success'}
                )
                return result
            except Exception as e:
                elapsed = time.perf_counter() - start
                logger.log(
                    logging.ERROR,
                    f"⏱️  {name} failed after {elapsed:.3f}s: {e}",
                    extra={'operation': name, 'duration_seconds': elapsed,
                           'timing': True, 'status': 'error', 'error': str(e)}
                )
                raise

        return wrapper
    return decorator


# ═══════════════════════════════════════════════════════════════════════════
# STRUCTURED LOG HELPERS
# ═══════════════════════════════════════════════════════════════════════════

def log_batch_start(logger: logging.Logger, batch_id: int, start: int, end: int, **extra):
    """Log batch processing start."""
    logger.debug(
        f"📦 Batch {batch_id} starting: items {start}-{end}",
        extra={'batch_id': batch_id, 'batch_start': start,
               'batch_end': end, 'batch_event': 'start', **extra}
    )


def log_batch_complete(logger: logging.Logger, batch_id: int, items_processed: int, duration: float, **extra):
    """Log batch processing completion."""
    rate = items_processed / duration if duration > 0 else 0
    logger.debug(
        f"✓ Batch {batch_id} complete: {items_processed} items in {duration:.3f}s ({rate:.1f}/s)",
        extra={'batch_id': batch_id, 'items_processed': items_processed,
               'duration_seconds': duration, 'rate_per_second': rate, 'batch_event': 'complete', **extra}
    )


def log_metric(logger: logging.Logger, name: str, value: float, unit: str = None, **tags):
    """Log a metric value for monitoring."""
    msg = f"📈 METRIC: {name}={value}"
    if unit:
        msg += f" {unit}"
    logger.info(
        msg,
        extra={'metric_name': name, 'metric_value': value,
               'metric_unit': unit, 'metric': True, **tags}
    )


# ═══════════════════════════════════════════════════════════════════════════
# BANNER PRINTING
# ═══════════════════════════════════════════════════════════════════════════

def print_banner(title: str, info: Dict[str, Any], width: int = 70):
    """
    Print a formatted banner to stdout (bypasses logging).

    Usage:
        print_banner("TTG Worker Starting", {"worker_id": 0, "version": "1.0.0"})
    """
    border = "═" * width
    print(f"\n╔{border}╗")
    print(f"║ {title.center(width - 2)} ║")
    print(f"╠{border}╣")
    for key, value in info.items():
        line = f"  {key}: {value}"
        print(f"║{line.ljust(width)}║")
    print(f"╚{border}╝\n")


def print_section(title: str, width: int = 60):
    """Print a section divider."""
    print(f"\n{'─' * width}")
    print(f"  {title}")
    print(f"{'─' * width}")


# ═══════════════════════════════════════════════════════════════════════════
# MODULE SELF-TEST
# ═══════════════════════════════════════════════════════════════════════════

if __name__ == '__main__':
    # Demo the logging system
    print("=" * 60)
    print("TTG Logging Configuration - Demo")
    print("=" * 60)

    # Setup logging
    setup_logging(worker_id=0, level='DEBUG', format_type='text')

    # Get logger
    logger = get_logger('demo')

    # Test different log levels
    print("\n--- Log Levels ---")
    logger.debug("This is a debug message", extra={'debug_data': 123})
    logger.info("This is an info message", extra={'status': 'ok'})
    logger.warning("This is a warning message")
    logger.error("This is an error message", extra={'error_code': 500})

    # Test lifecycle logger
    print("\n--- Lifecycle Events ---")
    lifecycle = LifecycleLogger(logger)
    lifecycle.starting(version='1.0.0')
    lifecycle.initialized({'workers': 3, 'params': 1000})
    lifecycle.running(total_work=1000)
    lifecycle.progress(500, 1000, batch_id=5)
    lifecycle.completed({'processed': 1000, 'duration': 5.5})

    # Test timing
    print("\n--- Timing ---")
    with log_timing(logger, "example_operation", level=logging.INFO):
        time.sleep(0.1)

    # Test banner
    print("\n--- Banner ---")
    print_banner("TTG Worker", {
        'Worker ID': 0,
        'Version': '1.0.0',
        'Timestamp': datetime.now(timezone.utc).isoformat()
    })

    # Test JSON format
    print("\n--- JSON Format ---")
    setup_logging(worker_id=0, level='INFO', format_type='json')
    logger = get_logger('json_demo')
    logger.info("JSON formatted log", extra={'key': 'value', 'count': 42})

    print("\n" + "=" * 60)
    print("Demo complete!")
