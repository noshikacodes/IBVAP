import sys
import time
import signal
import argparse
import logging
from typing import Optional, List

from ai_engine.stream_manager.manager import StreamManager
from ai_engine.stream_manager.types import mask_credentials

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [%(name)s]: %(message)s"
)
logger = logging.getLogger("ibvap.stream_manager.cli")


def parse_args(args: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="python -m ai_engine.stream_manager",
        description="IBVAP AI Engine - Multi-Stream Worker Supervisor & Camera Process Orchestrator"
    )
    parser.add_argument(
        "-c", "--config",
        default="mock_streams/streams.json",
        help="Path to JSON file containing camera stream definitions (default: mock_streams/streams.json)"
    )
    parser.add_argument(
        "--max-streams",
        type=int,
        default=8,
        help="Maximum simultaneous active stream worker processes (default: 8)"
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=2.0,
        help="Supervisor monitoring and telemetry interval in seconds (default: 2.0)"
    )
    return parser.parse_args(args)


def main(args: Optional[List[str]] = None) -> int:
    parsed = parse_args(args)

    manager = StreamManager(
        max_streams=parsed.max_streams,
        initial_backoff=1.0,
        max_backoff=30.0,
        max_restart_attempts=10,
        stable_period_seconds=30.0
    )

    # Setup clean signal termination
    def _signal_handler(sig, frame):
        logger.info("Received termination signal (%s). Shutting down all stream workers...", sig)
        manager.stop_all(timeout=3.0)
        sys.exit(0)

    signal.signal(signal.SIGINT, _signal_handler)
    signal.signal(signal.SIGTERM, _signal_handler)

    print("=" * 60)
    print(" [IBVAP StreamManager] Starting Multi-Stream AI Supervisor")
    print(f" Config File:       {parsed.config}")
    print(f" Max Streams Limit: {parsed.max_streams}")
    print(f" Monitor Interval:  {parsed.interval}s")
    print("=" * 60)

    loaded = manager.load_from_json(parsed.config, autostart=True)
    if loaded == 0:
        logger.warning("No valid active streams loaded from %s. Exiting.", parsed.config)
        return 1

    manager.start_monitoring(interval=parsed.interval)

    try:
        while True:
            time.sleep(parsed.interval * 5)
            # Periodic summary logging
            statuses = manager.get_all_status()
            summary_parts = [f"{s.camera_id}:{s.state.value}(PID:{s.process_id or '-'})" for s in statuses]
            logger.info("Streams Health Snapshot: %s", " | ".join(summary_parts))
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received.")
    finally:
        manager.stop_all()

    return 0


if __name__ == "__main__":
    sys.exit(main())
