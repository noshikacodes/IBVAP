#!/usr/bin/env python3
"""
IBVAP Live Camera Stream Verification Script - GITS Public CCTV (ID: 95366)
[세종]운학터널(세종)-13|13 (Sejong-Pocheon Expressway Wunhak Tunnel)

Performs a short live stream connectivity and ingestion test using OpenCV,
with dynamic HLS URL resolution, token renewal, and automatic reconnection.
"""

import os
import sys
import time
import argparse
import logging
from typing import Optional

import cv2
import numpy as np

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from ai_engine.pipeline.gits_resolver import (
    resolve_gits_hls_url,
    extract_gits_cctv_id,
    GITSResolutionError,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [%(name)s]: %(message)s"
)
logger = logging.getLogger("test_gits_stream")


def parse_args():
    parser = argparse.ArgumentParser(
        description="IBVAP Live Public CCTV Stream Connectivity & Frame Ingestion Test"
    )
    parser.add_argument(
        "--cctv-id",
        default="95366",
        help="GITS Camera ID or URL (default: 95366 - [세종]운학터널(세종)-13|13)"
    )
    parser.add_argument(
        "--frames",
        type=int,
        default=30,
        help="Number of frames to consume in the test (default: 30)"
    )
    parser.add_argument(
        "--show",
        action="store_true",
        help="Open an OpenCV display window (requires desktop GUI environment)"
    )
    parser.add_argument(
        "--snapshot",
        default=None,
        help="Output path for verification JPEG snapshot (default: mock_streams/gits_{id}_snapshot.jpg)"
    )
    parser.add_argument(
        "--simulate-reconnect",
        action="store_true",
        help="Simulate a mid-stream disconnection to demonstrate automatic reconnection"
    )
    args = parser.parse_args()
    if args.snapshot is None:
        c_id = extract_gits_cctv_id(args.cctv_id) or "stream"
        args.snapshot = f"mock_streams/gits_{c_id}_snapshot.jpg"
    return args


class LiveStreamIngestor:
    """
    Robust live stream consumer with automatic URL resolution and reconnection logic.
    """

    def __init__(self, source: str, max_retries: int = 5, reconnect_delay: float = 2.0):
        self.source = source
        self.max_retries = max_retries
        self.reconnect_delay = reconnect_delay
        self.current_url: Optional[str] = None
        self.metadata = {}
        self.cap: Optional[cv2.VideoCapture] = None
        self.reconnect_count = 0

    def connect(self) -> bool:
        """Resolves HLS stream URL and opens cv2.VideoCapture with optimized flags."""
        logger.info("Resolving live stream URL for source: %s", self.source)
        try:
            self.current_url, self.metadata = resolve_gits_hls_url(self.source)
            logger.info(
                "Resolved HLS Endpoint: %s (Token validity: %d minutes)",
                self.current_url, self.metadata.get("valid_minutes", 120)
            )
        except GITSResolutionError as e:
            logger.error("Stream resolution failed: %s", e)
            return False

        # Configure OpenCV FFmpeg capture timeout for live HLS streams
        os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "timeout;5000000"
        if self.cap is not None:
            self.cap.release()

        self.cap = cv2.VideoCapture(self.current_url, cv2.CAP_FFMPEG)
        if not self.cap.isOpened():
            logger.error("Failed to open OpenCV VideoCapture on URL.")
            return False

        w = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        h = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        reported_fps = self.cap.get(cv2.CAP_PROP_FPS)
        logger.info("Stream opened successfully: %dx%d (reported FPS: %.1f)", w, h, reported_fps)
        return True

    def reconnect(self) -> bool:
        """Automatic reconnection with token refresh and exponential backoff."""
        delay = self.reconnect_delay
        for attempt in range(1, self.max_retries + 1):
            self.reconnect_count += 1
            logger.warning(
                "Reconnecting to live stream (Attempt %d/%d) in %.1fs...",
                attempt, self.max_retries, delay
            )
            time.sleep(delay)
            if self.connect():
                logger.info("Reconnection successful on attempt %d.", attempt)
                return True
            delay = min(delay * 1.5, 10.0)

        logger.error("Max reconnection retries (%d) exceeded.", self.max_retries)
        return False

    def close(self):
        if self.cap is not None:
            self.cap.release()
            self.cap = None


def main():
    args = parse_args()

    print("=" * 70)
    print("  IBVAP Live Public CCTV Ingestion Test")
    print(f"  Target Source:      {args.cctv_id}")
    print(f"  Target Frames:      {args.frames}")
    print(f"  Snapshot Path:      {args.snapshot}")
    print("=" * 70)

    ingestor = LiveStreamIngestor(args.cctv_id)
    if not ingestor.connect():
        print("[ERROR] Could not connect to target live stream. Aborting.", file=sys.stderr)
        return 1

    frames_read = 0
    start_time = time.perf_counter()
    snapshot_saved = False
    simulated_disconnect_done = False

    try:
        while frames_read < args.frames:
            ret, frame = ingestor.cap.read()

            # Test simulation of mid-stream interruption
            if args.simulate_reconnect and not simulated_disconnect_done and frames_read == 10:
                print("\n[SIMULATION] Forcing stream disconnection to test auto-reconnect...")
                ingestor.cap.release()
                ret = False
                simulated_disconnect_done = True

            if not ret or frame is None:
                logger.warning("Frame read failed. Triggering automatic reconnection...")
                if not ingestor.reconnect():
                    print("[ERROR] Reconnection failed. Aborting.", file=sys.stderr)
                    return 2
                continue

            frames_read += 1
            h, w = frame.shape[:2]

            # Save snapshot of first clean frame
            if not snapshot_saved and args.snapshot:
                os.makedirs(os.path.dirname(os.path.abspath(args.snapshot)), exist_ok=True)
                # Overlay test metadata
                vis_frame = frame.copy()
                cv2.putText(
                    vis_frame,
                    f"IBVAP CCTV TEST: CAM {args.cctv_id} | {w}x{h} | {time.strftime('%Y-%m-%d %H:%M:%S')}",
                    (20, 30),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.6,
                    (0, 255, 0),
                    2,
                    cv2.LINE_AA
                )
                cv2.imwrite(args.snapshot, vis_frame)
                snapshot_saved = True
                logger.info("Verification snapshot saved -> %s", args.snapshot)

            # Optional GUI display
            if args.show:
                cv2.imshow(f"IBVAP Live Camera - {args.cctv_id}", frame)
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    print("User interrupted display window.")
                    break

            if frames_read % 10 == 0 or frames_read == args.frames:
                elapsed = max(time.perf_counter() - start_time, 0.001)
                effective_fps = frames_read / elapsed
                print(f" [PROGRESS] Consumed {frames_read}/{args.frames} frames ({effective_fps:.1f} FPS, {w}x{h})")

    except KeyboardInterrupt:
        print("\nTest cancelled by user.")
    finally:
        ingestor.close()
        if args.show:
            cv2.destroyAllWindows()

    total_elapsed = max(time.perf_counter() - start_time, 0.001)
    overall_fps = frames_read / total_elapsed

    print("\n" + "=" * 70)
    print("  TEST SUMMARY & METRICS")
    print(f"  Total Frames Consumed: {frames_read}")
    print(f"  Total Elapsed Time:    {total_elapsed:.2f} seconds")
    print(f"  Effective Ingestion:   {overall_fps:.2f} FPS")
    print(f"  Total Reconnections:   {ingestor.reconnect_count}")
    print(f"  Snapshot Output:       {args.snapshot if snapshot_saved else 'None'}")
    print("  Status:                SUCCESS (Stream is healthy and consumable)")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    sys.exit(main())
