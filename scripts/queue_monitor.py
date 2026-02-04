#!/usr/bin/env python3
"""
TTG Queue Monitor - Real-time CLI monitoring for distributed computation.

This script provides a terminal-based dashboard showing:
  - Queue statistics (pending, claimed, total tasks)
  - Results statistics (completed chunks, total parameters)
  - Worker activity (detected from pending claims)
  - Processing throughput (params/sec)
  - Progress bar and ETA

Usage:
    # From project root, with Redis port-forwarded:
    kubectl port-forward pod/ttg-redis 6379:6379 &
    python scripts/queue_monitor.py

    # With custom refresh interval (default: 2 seconds)
    python scripts/queue_monitor.py --interval 1

    # With total parameters for progress tracking
    python scripts/queue_monitor.py --total-params 10000

    # Quiet mode (less output, good for logging)
    python scripts/queue_monitor.py --quiet

Requirements:
    pip install redis rich

Architecture:
    This script connects directly to Redis (via port-forward) and queries:
    - XINFO GROUPS ttg:tasks : Consumer group info
    - XLEN ttg:tasks : Total stream length
    - XLEN ttg:results : Results count
    - XPENDING ttg:tasks ttg-workers : Pending (claimed) tasks
    - HGETALL ttg:metadata : Job metadata (total_params, chunk_size, etc.)
"""

import argparse
import sys
import time
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, Tuple

try:
    import redis
except ImportError:
    print("ERROR: redis package not found. Install with: pip install redis")
    sys.exit(1)

try:
    from rich.console import Console
    from rich.live import Live
    from rich.table import Table
    from rich.panel import Panel
    from rich.progress import Progress, BarColumn, TextColumn, TimeRemainingColumn
    from rich.layout import Layout
    from rich.text import Text
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False
    print("WARNING: rich package not found. Using simple text output.")
    print("For better visuals, install with: pip install rich")


class QueueMonitor:
    """
    Monitor Redis Streams queue for TTG distributed computation.

    Connects to Redis and periodically queries stream statistics
    to provide real-time visibility into job progress.
    """

    def __init__(
        self,
        redis_host: str = "localhost",
        redis_port: int = 6379,
        stream_name: str = "ttg:tasks",
        results_stream: str = "ttg:results",
        consumer_group: str = "ttg-workers",
        metadata_key: str = "ttg:metadata"
    ):
        """
        Initialize monitor with Redis connection parameters.

        Args:
            redis_host: Redis server hostname
            redis_port: Redis server port
            stream_name: Name of the task stream
            results_stream: Name of the results stream
            consumer_group: Consumer group name
            metadata_key: Key for job metadata hash
        """
        self.redis_client = redis.Redis(
            host=redis_host,
            port=redis_port,
            decode_responses=True
        )
        self.stream_name = stream_name
        self.results_stream = results_stream
        self.consumer_group = consumer_group
        self.metadata_key = metadata_key

        # Tracking for throughput calculation
        self.start_time: Optional[float] = None
        self.last_completed: int = 0
        self.last_check_time: float = 0
        self.throughput_samples: list = []  # Rolling average

    def ping(self) -> bool:
        """Check Redis connectivity."""
        try:
            return self.redis_client.ping()
        except redis.ConnectionError:
            return False

    def get_metadata(self) -> Dict[str, Any]:
        """
        Get job metadata from Redis.

        Returns:
            Dict with total_parameters, chunk_size, total_chunks, job_id, etc.
        """
        try:
            data = self.redis_client.hgetall(self.metadata_key)
            return {
                "total_parameters": int(data.get("total_parameters", 0)),
                "chunk_size": int(data.get("chunk_size", 100)),
                "total_chunks": int(data.get("total_chunks", 0)),
                "job_id": data.get("job_id", "unknown"),
                "created_at": data.get("created_at", ""),
            }
        except (redis.RedisError, ValueError):
            return {
                "total_parameters": 0,
                "chunk_size": 100,
                "total_chunks": 0,
                "job_id": "unknown",
                "created_at": "",
            }

    def get_stream_stats(self) -> Dict[str, int]:
        """
        Get task stream statistics.

        Returns:
            Dict with:
                - stream_length: Total messages in stream
                - pending: Messages claimed but not ACK'd
                - consumers: Number of active consumers
                - delivered: Messages delivered to consumers
        """
        stats = {
            "stream_length": 0,
            "pending": 0,
            "consumers": 0,
            "delivered": 0,
            "lag": 0,
        }

        try:
            # Stream length
            stats["stream_length"] = self.redis_client.xlen(self.stream_name)

            # Consumer group info
            groups = self.redis_client.xinfo_groups(self.stream_name)
            for group in groups:
                if group.get("name") == self.consumer_group:
                    stats["pending"] = group.get("pending", 0)
                    stats["consumers"] = group.get("consumers", 0)
                    stats["lag"] = group.get("lag", 0)
                    break

            # Detailed pending info (for worker breakdown)
            pending_info = self.redis_client.xpending(
                self.stream_name,
                self.consumer_group
            )
            if pending_info and pending_info.get("pending"):
                stats["pending"] = pending_info["pending"]

        except redis.ResponseError:
            # Stream or group doesn't exist yet
            pass
        except redis.RedisError as e:
            print(f"Redis error: {e}")

        return stats

    def get_results_stats(self) -> Dict[str, int]:
        """
        Get results stream statistics.

        Returns:
            Dict with:
                - completed_chunks: Number of result messages
                - total_params_processed: Sum of parameters processed
        """
        stats = {
            "completed_chunks": 0,
            "total_params_processed": 0,
        }

        try:
            # Results stream length = completed chunks
            stats["completed_chunks"] = self.redis_client.xlen(
                self.results_stream)

            # For params processed, we'd need to read results
            # This is approximate: completed_chunks * chunk_size
            metadata = self.get_metadata()
            stats["total_params_processed"] = (
                stats["completed_chunks"] * metadata["chunk_size"]
            )

        except redis.ResponseError:
            pass
        except redis.RedisError as e:
            print(f"Redis error: {e}")

        return stats

    def get_worker_breakdown(self) -> Dict[str, int]:
        """
        Get per-worker pending task counts.

        Returns:
            Dict mapping consumer_name -> pending_count
        """
        workers = {}

        try:
            pending_detail = self.redis_client.xpending_range(
                self.stream_name,
                self.consumer_group,
                min="-",
                max="+",
                count=1000  # Get up to 1000 pending messages
            )

            for entry in pending_detail:
                consumer = entry.get("consumer", "unknown")
                workers[consumer] = workers.get(consumer, 0) + 1

        except redis.ResponseError:
            pass
        except redis.RedisError:
            pass

        return workers

    def calculate_throughput(self, completed: int) -> float:
        """
        Calculate rolling throughput (params/sec).

        Uses a rolling window of samples for smooth display.
        """
        current_time = time.time()

        if self.last_check_time > 0 and completed > self.last_completed:
            time_delta = current_time - self.last_check_time
            params_delta = completed - self.last_completed

            if time_delta > 0:
                sample = params_delta / time_delta
                self.throughput_samples.append(sample)

                # Keep last 10 samples for rolling average
                if len(self.throughput_samples) > 10:
                    self.throughput_samples.pop(0)

        self.last_completed = completed
        self.last_check_time = current_time

        if self.throughput_samples:
            return sum(self.throughput_samples) / len(self.throughput_samples)
        return 0.0

    def get_all_stats(self) -> Dict[str, Any]:
        """
        Gather all monitoring statistics.

        Returns:
            Comprehensive dict with all queue, results, and throughput stats.
        """
        metadata = self.get_metadata()
        stream_stats = self.get_stream_stats()
        results_stats = self.get_results_stats()
        workers = self.get_worker_breakdown()

        completed = results_stats["total_params_processed"]
        throughput = self.calculate_throughput(completed)

        # Calculate progress
        total = metadata["total_parameters"]
        progress_pct = (completed / total * 100) if total > 0 else 0

        # Estimate ETA
        eta_seconds = None
        if throughput > 0 and total > completed:
            remaining = total - completed
            eta_seconds = remaining / throughput

        return {
            "metadata": metadata,
            "stream": stream_stats,
            "results": results_stats,
            "workers": workers,
            "throughput": throughput,
            "progress_pct": progress_pct,
            "eta_seconds": eta_seconds,
            "timestamp": datetime.now().isoformat(),
        }


def format_time(seconds: Optional[float]) -> str:
    """Format seconds as human-readable time."""
    if seconds is None:
        return "N/A"
    if seconds < 60:
        return f"{seconds:.0f}s"
    elif seconds < 3600:
        minutes = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{minutes}m {secs}s"
    else:
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        return f"{hours}h {minutes}m"


def simple_display(stats: Dict[str, Any]) -> None:
    """Simple text-based display (fallback when rich not available)."""
    meta = stats["metadata"]
    stream = stats["stream"]
    results = stats["results"]

    print("\n" + "=" * 60)
    print(f"  TTG Queue Monitor - {stats['timestamp'][:19]}")
    print("=" * 60)
    print(f"\n  Job ID: {meta['job_id']}")
    print(f"  Total Parameters: {meta['total_parameters']:,}")
    print(f"  Chunk Size: {meta['chunk_size']}")
    print(f"\n  QUEUE STATUS:")
    print(f"    Stream Length: {stream['stream_length']}")
    print(f"    Pending (in progress): {stream['pending']}")
    print(f"    Active Workers: {stream['consumers']}")
    print(f"\n  RESULTS:")
    print(f"    Completed Chunks: {results['completed_chunks']}")
    print(f"    Params Processed: {results['total_params_processed']:,}")
    print(f"\n  PROGRESS: {stats['progress_pct']:.1f}%")
    print(f"  Throughput: {stats['throughput']:.1f} params/sec")
    print(f"  ETA: {format_time(stats['eta_seconds'])}")

    if stats["workers"]:
        print(f"\n  WORKERS:")
        for worker, count in stats["workers"].items():
            print(f"    {worker}: {count} pending")

    print("\n" + "=" * 60)


def create_rich_display(stats: Dict[str, Any], total_params_override: Optional[int] = None) -> Panel:
    """Create rich formatted display panel."""
    meta = stats["metadata"]
    stream = stats["stream"]
    results = stats["results"]

    total_params = total_params_override or meta["total_parameters"]
    completed = results["total_params_processed"]

    # Main stats table
    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column("Label", style="cyan")
    table.add_column("Value", style="green")

    # Job info
    table.add_row("Job ID", meta["job_id"])
    table.add_row("Total Params", f"{total_params:,}")
    table.add_row("Chunk Size", str(meta["chunk_size"]))
    table.add_row("", "")

    # Queue status
    table.add_row("📥 Stream Length", str(stream["stream_length"]))
    table.add_row("⏳ Pending", str(stream["pending"]))
    table.add_row("👷 Active Workers", str(stream["consumers"]))
    table.add_row("", "")

    # Results
    table.add_row("✅ Completed Chunks", str(results["completed_chunks"]))
    table.add_row("✅ Params Processed", f"{completed:,}")
    table.add_row("", "")

    # Progress
    progress_pct = (completed / total_params * 100) if total_params > 0 else 0
    progress_bar = "█" * int(progress_pct / 5) + "░" * \
        (20 - int(progress_pct / 5))
    table.add_row("📊 Progress", f"[{progress_bar}] {progress_pct:.1f}%")
    table.add_row("🚀 Throughput", f"{stats['throughput']:.1f} params/sec")
    table.add_row("⏱️ ETA", format_time(stats["eta_seconds"]))

    # Workers section
    if stats["workers"]:
        table.add_row("", "")
        table.add_row("👷 Workers", "")
        for worker, count in sorted(stats["workers"].items()):
            # Truncate worker name for display
            short_name = worker[-20:] if len(worker) > 20 else worker
            table.add_row(f"  {short_name}", f"{count} pending")

    # Create panel with timestamp
    timestamp = datetime.now().strftime("%H:%M:%S")
    return Panel(
        table,
        title=f"[bold blue]TTG Queue Monitor[/bold blue]",
        subtitle=f"[dim]Updated: {timestamp} | Press Ctrl+C to exit[/dim]",
        border_style="blue"
    )


def run_monitor(
    redis_host: str = "localhost",
    redis_port: int = 6379,
    interval: float = 2.0,
    total_params: Optional[int] = None,
    quiet: bool = False
) -> None:
    """
    Run the queue monitor.

    Args:
        redis_host: Redis server hostname
        redis_port: Redis server port
        interval: Refresh interval in seconds
        total_params: Override total parameters for progress calculation
        quiet: Use simple text output
    """
    monitor = QueueMonitor(redis_host=redis_host, redis_port=redis_port)

    # Check connectivity
    print(f"Connecting to Redis at {redis_host}:{redis_port}...")
    if not monitor.ping():
        print(f"ERROR: Cannot connect to Redis at {redis_host}:{redis_port}")
        print("\nMake sure Redis is port-forwarded:")
        print("  kubectl port-forward pod/ttg-redis 6379:6379")
        sys.exit(1)
    print("Connected!\n")

    # Use simple display if rich not available or quiet mode
    if not RICH_AVAILABLE or quiet:
        try:
            while True:
                stats = monitor.get_all_stats()
                simple_display(stats)
                time.sleep(interval)
        except KeyboardInterrupt:
            print("\nMonitor stopped.")
            return

    # Rich live display
    console = Console()

    try:
        with Live(console=console, refresh_per_second=1, screen=True) as live:
            while True:
                stats = monitor.get_all_stats()
                panel = create_rich_display(stats, total_params)
                live.update(panel)
                time.sleep(interval)
    except KeyboardInterrupt:
        console.print("\n[yellow]Monitor stopped.[/yellow]")


def main():
    parser = argparse.ArgumentParser(
        description="TTG Queue Monitor - Real-time distributed computation monitoring"
    )
    parser.add_argument(
        "--host",
        default="localhost",
        help="Redis host (default: localhost)"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=6379,
        help="Redis port (default: 6379)"
    )
    parser.add_argument(
        "--interval", "-i",
        type=float,
        default=2.0,
        help="Refresh interval in seconds (default: 2.0)"
    )
    parser.add_argument(
        "--total-params", "-t",
        type=int,
        default=None,
        help="Override total parameters for progress tracking"
    )
    parser.add_argument(
        "--quiet", "-q",
        action="store_true",
        help="Use simple text output (no rich formatting)"
    )

    args = parser.parse_args()

    run_monitor(
        redis_host=args.host,
        redis_port=args.port,
        interval=args.interval,
        total_params=args.total_params,
        quiet=args.quiet
    )


if __name__ == "__main__":
    main()
