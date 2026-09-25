import sys
import time
import argparse
from typing import List, Optional

from ai_engine.pipeline.config import InferenceConfig, DEFAULT_TARGET_CLASSES
from ai_engine.pipeline.inference_runner import InferencePipeline
from ai_engine.pipeline.stream_reader import VideoStreamError
from ai_engine.pipeline.detector import DetectorError


def parse_args(args: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="python -m ai_engine.worker",
        description="IBVAP AI Engine - Object Detection, Multi-Object Tracking, Spatial Rules & Alert Delivery"
    )

    parser.add_argument(
        "-i", "--input",
        required=True,
        help="Path to input video file (e.g., sample.mp4)"
    )
    parser.add_argument(
        "-o", "--output",
        default=None,
        help="Path for output annotated video file (default: None - live stream only)"
    )
    parser.add_argument(
        "-m", "--model",
        default="yolov8n.pt",
        help="YOLO model name or local weight path (default: yolov8n.pt)"
    )
    parser.add_argument(
        "--models-dir",
        default="ai_engine/models_weight",
        help="Directory to store/load model weights (default: ai_engine/models_weight)"
    )
    parser.add_argument(
        "-c", "--conf",
        type=float,
        default=0.40,
        help="Confidence threshold for detections between 0.0 and 1.0 (default: 0.40)"
    )
    parser.add_argument(
        "-s", "--imgsz",
        type=int,
        default=640,
        help="Inference image resolution (default: 640)"
    )
    parser.add_argument(
        "-d", "--device",
        default="cpu",
        help="Inference hardware device: 'cpu', 'cuda', 'cuda:0' (default: cpu)"
    )
    parser.add_argument(
        "--skip-frames",
        type=int,
        default=0,
        help="Process every N-th frame to accelerate throughput (default: 0 - process all frames)"
    )
    parser.add_argument(
        "--classes",
        default=None,
        help="Comma-separated target classes to filter (e.g. 'person,car,truck'). Default: all perimeter targets."
    )

    # Tracking Arguments (Phase 2B)
    parser.add_argument(
        "--tracking",
        action="store_true",
        default=True,
        help="Enable persistent multi-object tracking (enabled by default)"
    )
    parser.add_argument(
        "--no-tracking",
        action="store_true",
        help="Disable multi-object tracking and run detection-only"
    )
    parser.add_argument(
        "--tracker",
        default="bytetrack",
        choices=["bytetrack", "native"],
        help="Tracker algorithm implementation (default: bytetrack)"
    )
    parser.add_argument(
        "--max-trajectory-len",
        type=int,
        default=30,
        help="Maximum history center points retained per track (default: 30)"
    )
    parser.add_argument(
        "--max-lost-frames",
        type=int,
        default=15,
        help="Threshold of missed frames before expiring lost tracks (default: 15)"
    )
    parser.add_argument(
        "--no-trajectories",
        action="store_true",
        help="Disable visual rendering of trajectory trails on video"
    )

    # Spatial Rules Arguments (Phase 3A)
    parser.add_argument(
        "--spatial-rules",
        default=None,
        help="Path to JSON/YAML spatial rules configuration (virtual zones and tripwires)"
    )
    parser.add_argument(
        "--camera-id",
        default="CAM_01",
        help="Identifier of the camera/stream being evaluated (default: CAM_01)"
    )
    parser.add_argument(
        "--no-zones",
        action="store_true",
        help="Disable visual rendering of polygon zones and tripwires"
    )
    parser.add_argument(
        "--no-events",
        action="store_true",
        help="Disable visual rendering of alert banners on video"
    )

    # Alert Delivery Arguments (Phase 3B)
    parser.add_argument(
        "--publish-redis",
        action="store_true",
        help="Publish alerts to Redis Pub/Sub topic"
    )
    parser.add_argument(
        "--redis-url",
        default=None,
        help="Redis broker connection URL (e.g. redis://localhost:6379/0)"
    )
    parser.add_argument(
        "--redis-channel",
        default=None,
        help="Redis Pub/Sub alert channel (default: ibvap.alerts)"
    )
    parser.add_argument(
        "--alert-cooldown",
        type=float,
        default=15.0,
        help="Rate-limiting alert deduplication cooldown in seconds (default: 15.0)"
    )
    parser.add_argument(
        "--no-alerts",
        action="store_true",
        help="Disable Alert Engine processing and alert publishing"
    )
    # RTSP Ingestion Arguments (Phase 5A)
    parser.add_argument(
        "--reconnect-delay",
        type=float,
        default=2.0,
        help="Initial retry delay in seconds on RTSP stream dropout (default: 2.0)"
    )
    parser.add_argument(
        "--max-retries",
        type=int,
        default=5,
        help="Maximum reconnection attempts before aborting live stream (default: 5)"
    )

    # ANPR Arguments (Phase 5B)
    parser.add_argument(
        "--anpr",
        action="store_true",
        default=False,
        help="Enable Automatic Number Plate Recognition (ANPR) for detected vehicle tracks"
    )
    parser.add_argument(
        "--anpr-model",
        default="yolov8n_plate.pt",
        help="License plate detector YOLO weight filename (default: yolov8n_plate.pt)"
    )
    parser.add_argument(
        "--anpr-ocr",
        default="easyocr",
        help="OCR engine for license plate reading ('easyocr' / 'paddleocr', default: easyocr)"
    )
    parser.add_argument(
        "--anpr-conf",
        type=float,
        default=0.40,
        help="Minimum plate detection confidence threshold (default: 0.40)"
    )
    parser.add_argument(
        "--anpr-stride",
        type=int,
        default=3,
        help="Process ANPR on vehicle tracks every N frames (default: 3)"
    )
    parser.add_argument(
        "--anpr-votes",
        type=int,
        default=3,
        help="Required matching OCR readings before locking plate consensus (default: 3)"
    )

    # Face Recognition System (FRS) arguments (Phase 5C)
    parser.add_argument(
        "--frs",
        action="store_true",
        default=False,
        help="Enable Automatic Face Recognition System on tracked persons"
    )
    parser.add_argument(
        "--frs-gallery",
        type=str,
        default=None,
        help="Path to JSON file containing enrolled identity embeddings/profiles"
    )
    parser.add_argument(
        "--frs-thresh",
        type=float,
        default=0.65,
        help="Cosine similarity threshold for verified face matching (default: 0.65)"
    )
    parser.add_argument(
        "--frs-stride",
        type=int,
        default=3,
        help="Process face detection/recognition every N frames (default: 3)"
    )
    parser.add_argument(
        "--frs-votes",
        type=int,
        default=3,
        help="Required matching identity votes before locking track identity (default: 3)"
    )
    parser.add_argument(
        "--frs-min-size",
        type=int,
        default=32,
        help="Minimum face width/height in pixels to process (default: 32)"
    )
    parser.add_argument(
        "--frs-detector",
        type=str,
        default="yolov8n_face.pt",
        help="Face detector model filename in models_dir (default: yolov8n_face.pt)"
    )
    parser.add_argument(
        "--frs-recognizer",
        type=str,
        default="mobilefacenet_arcface.onnx",
        help="Face recognizer ONNX model filename in models_dir (default: mobilefacenet_arcface.onnx)"
    )

    return parser.parse_args(args)


def main(args: Optional[List[str]] = None) -> int:
    parsed = parse_args(args)

    target_classes = None
    if parsed.classes:
        target_classes = [c.strip() for c in parsed.classes.split(",") if c.strip()]

    enable_tracking = True
    if parsed.no_tracking:
        enable_tracking = False

    try:
        config = InferenceConfig(
            input_path=parsed.input,
            output_path=parsed.output,
            model_name_or_path=parsed.model,
            models_dir=parsed.models_dir,
            confidence_threshold=parsed.conf,
            imgsz=parsed.imgsz,
            device=parsed.device,
            skip_frames=parsed.skip_frames,
            target_classes=target_classes,
            enable_tracking=enable_tracking,
            tracker_type=parsed.tracker,
            max_trajectory_length=parsed.max_trajectory_len,
            max_lost_frames=parsed.max_lost_frames,
            spatial_rules_path=parsed.spatial_rules,
            camera_id=parsed.camera_id,
            enable_alert_engine=not parsed.no_alerts,
            publish_redis=parsed.publish_redis,
            redis_url=parsed.redis_url,
            redis_channel=parsed.redis_channel,
            alert_cooldown_seconds=parsed.alert_cooldown,
            reconnect_delay=parsed.reconnect_delay,
            max_reconnect_retries=parsed.max_retries,
            draw_trajectories=not parsed.no_trajectories,
            draw_zones=not parsed.no_zones,
            draw_events=not parsed.no_events,
            enable_anpr=parsed.anpr,
            anpr_detector_model=parsed.anpr_model,
            anpr_ocr_engine=parsed.anpr_ocr,
            anpr_min_conf=parsed.anpr_conf,
            anpr_frame_stride=parsed.anpr_stride,
            anpr_consensus_votes=parsed.anpr_votes,
            enable_frs=parsed.frs,
            frs_detector_model=parsed.frs_detector,
            frs_recognizer_model=parsed.frs_recognizer,
            frs_match_threshold=parsed.frs_thresh,
            frs_frame_stride=parsed.frs_stride,
            frs_consensus_votes=parsed.frs_votes,
            frs_min_face_size=parsed.frs_min_size,
            frs_gallery_path=parsed.frs_gallery
        )

        while True:
            try:
                pipeline = InferencePipeline(config)
                summary = pipeline.run()
                print("\n[INFO] Inference cycle finished. Auto-restarting in 2s for continuous surveillance...", file=sys.stderr)
                time.sleep(2.0)
            except KeyboardInterrupt:
                print("\n[INFO] Inference worker stopped by user.", file=sys.stderr)
                break
            except Exception as loop_err:
                print(f"\n[WARNING] Pipeline cycle error: {loop_err}. Auto-restarting in 3s...", file=sys.stderr)
                time.sleep(3.0)
        return 0

    except (VideoStreamError, DetectorError, FileNotFoundError, ValueError) as e:
        print(f"\n[ERROR] IBVAP AI Engine: {str(e)}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\n[INFO] Inference aborted by user.", file=sys.stderr)
        return 130
    except Exception as e:
        print(f"\n[CRITICAL ERROR] Unexpected failure: {str(e)}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
