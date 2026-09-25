import time
import os
import queue
import threading
from typing import Dict, Any, List, Optional, Set
from collections import defaultdict

from ai_engine.pipeline.config import InferenceConfig
from ai_engine.pipeline.stream_reader import VideoReader
from ai_engine.pipeline.detector import YOLODetector
from ai_engine.pipeline.tracker import MultiObjectTracker
from ai_engine.pipeline.spatial_rules import SpatialRulesEngine, PolygonZone, Tripwire
from ai_engine.pipeline.annotator import VideoAnnotator, VideoWriter
from ai_engine.pipeline.types import TrackedEntity, Detection, SpatialZoneEvent



class InferencePipeline:
    """
    Orchestrates the end-to-end video intelligence & alert pipeline:
    MP4 Video -> VideoReader -> YOLODetector -> MultiObjectTracker -> SpatialRulesEngine -> AlertEngine -> Redis/WebSockets -> VideoAnnotator -> VideoWriter -> Metrics Summary.
    """

    def __init__(self, config: InferenceConfig):
        self.config = config
        self.reader = VideoReader(
            video_path=self.config.input_path,
            skip_frames=self.config.skip_frames,
            reconnect_delay=self.config.reconnect_delay,
            max_retries=self.config.max_reconnect_retries
        )
        self.detector = YOLODetector(
            model_name_or_path=self.config.model_name_or_path,
            models_dir=self.config.models_dir,
            device=self.config.device,
            confidence_threshold=self.config.confidence_threshold,
            target_classes=self.config.target_classes,
            imgsz=self.config.imgsz
        )
        self.tracker = None
        if self.config.enable_tracking:
            self.tracker = MultiObjectTracker(
                iou_threshold=self.config.iou_threshold,
                max_lost_frames=self.config.max_lost_frames,
                max_trajectory_length=self.config.max_trajectory_length,
                min_hits=self.config.min_hits
            )

        # Load Spatial Rules if configured
        self.rules_engine: Optional[SpatialRulesEngine] = None
        if self.config.spatial_rules_path:
            self.rules_engine = SpatialRulesEngine.from_file(
                filepath=self.config.spatial_rules_path,
                fps=self.reader.fps
            )

        # Initialize Alert Engine
        self.alert_engine: Optional[Any] = None
        if self.config.enable_alert_engine:
            from backend.app.services.alert_engine import AlertEngine
            from backend.app.services.redis_bus import RedisEventBus

            event_bus = None
            if self.config.publish_redis:
                event_bus = RedisEventBus(
                    redis_url=self.config.redis_url,
                    channel=self.config.redis_channel
                )
            self.alert_engine = AlertEngine(
                event_bus=event_bus,
                cooldown_seconds=self.config.alert_cooldown_seconds,
                publish_to_redis=self.config.publish_redis
            )

        # Initialize ANPR Analyzer if configured (Phase 5B)
        self.anpr_analyzer: Optional[Any] = None
        if self.config.enable_anpr and self.config.enable_tracking:
            from ai_engine.pipeline.anpr import ANPRAnalyzer, PlateDetector, OCREngine
            plate_detector = PlateDetector(
                model_name_or_path=self.config.anpr_detector_model,
                models_dir=self.config.models_dir,
                device=self.config.device,
                confidence_threshold=self.config.anpr_min_conf
            )
            ocr_engine = OCREngine(
                engine_type=self.config.anpr_ocr_engine,
                language="en",
                use_gpu=self.config.device.startswith("cuda")
            )
            self.anpr_analyzer = ANPRAnalyzer(
                detector=plate_detector,
                ocr_engine=ocr_engine,
                min_confidence=self.config.anpr_min_conf,
                ocr_confidence=self.config.anpr_ocr_confidence,
                consensus_votes=self.config.anpr_consensus_votes,
                frame_stride=self.config.anpr_frame_stride,
                min_vehicle_size=self.config.anpr_min_vehicle_size,
                voting_window=self.config.anpr_voting_window_frames
            )

        # Initialize Face Analyzer if configured (Phase 5C)
        self.face_analyzer: Optional[Any] = None
        if self.config.enable_frs and self.config.enable_tracking:
            from ai_engine.pipeline.face import FaceAnalyzer, FaceDetector, FaceRecognizer
            det_path = os.path.join(self.config.models_dir, self.config.frs_detector_model) if not os.path.isabs(self.config.frs_detector_model) else self.config.frs_detector_model
            rec_path = os.path.join(self.config.models_dir, self.config.frs_recognizer_model) if not os.path.isabs(self.config.frs_recognizer_model) else self.config.frs_recognizer_model
            gal_path = self.config.frs_gallery_path
            if gal_path and not os.path.isabs(gal_path):
                gal_path = os.path.abspath(gal_path)

            face_detector = FaceDetector(
                model_path=det_path,
                device=self.config.device,
                confidence_threshold=self.config.frs_face_confidence,
                min_face_size=self.config.frs_min_face_size
            )
            face_recognizer = FaceRecognizer(
                model_path=rec_path,
                device=self.config.device,
                embedding_dimension=self.config.frs_embedding_dimension
            )
            self.face_analyzer = FaceAnalyzer(
                detector=face_detector,
                recognizer=face_recognizer,
                confidence_threshold=self.config.frs_face_confidence,
                match_threshold=self.config.frs_match_threshold,
                consensus_votes=self.config.frs_consensus_votes,
                frame_stride=self.config.frs_frame_stride,
                min_face_size=self.config.frs_min_face_size,
                voting_window=self.config.frs_voting_window_frames,
                unknown_enabled=self.config.frs_unknown_enabled,
                gallery_path=gal_path
            )

        # Initialize Traffic Counting & Analytics Engine
        self.traffic_counter: Optional[Any] = None
        if getattr(self.config, "enable_traffic_counting", True) and self.config.enable_tracking:
            from ai_engine.pipeline.traffic_counter import TrafficCountingEngine
            self.traffic_counter = TrafficCountingEngine(
                camera_id=self.config.camera_id,
                line_pt1=getattr(self.config, "traffic_line_pt1", (50.0, 360.0)),
                line_pt2=getattr(self.config, "traffic_line_pt2", (670.0, 360.0)),
                evidence_dir=getattr(self.config, "traffic_evidence_dir", "data/evidence"),
                save_evidence=getattr(self.config, "save_traffic_evidence", True)
            )

        self.annotator = VideoAnnotator(
            draw_telemetry=self.config.draw_telemetry,
            draw_trajectories=self.config.draw_trajectories,
            draw_zones=self.config.draw_zones,
            draw_events=self.config.draw_events
        )
        self.annotator.model_name = os.path.basename(self.config.model_name_or_path).replace(".pt", "").upper()

        # Dedicated non-blocking frame streamer queue
        self._frame_queue: queue.Queue = queue.Queue(maxsize=2)
        self._frame_relay_stop: bool = False
        self._frame_relay_thread: threading.Thread = threading.Thread(
            target=self._frame_relay_loop,
            daemon=True
        )
        self._frame_relay_thread.start()

    def _frame_relay_loop(self):
        import cv2
        import urllib.request
        while not self._frame_relay_stop:
            try:
                item = self._frame_queue.get(timeout=0.5)
                if item is None:
                    break
                cam_id, frm = item
                ret_jpg, jpg_buffer = cv2.imencode('.jpg', frm, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
                if ret_jpg:
                    req_frame = urllib.request.Request(
                        f"http://localhost:8000/api/v1/cameras/{cam_id}/frame",
                        data=jpg_buffer.tobytes(),
                        headers={"Content-Type": "image/jpeg"},
                        method="POST"
                    )
                    try:
                        urllib.request.urlopen(req_frame, timeout=0.8)
                    except Exception:
                        pass
                self._frame_queue.task_done()
            except queue.Empty:
                continue
            except Exception:
                pass

    def _push_annotated_frame(self, cam_id: str, frm: Any):
        try:
            if self._frame_queue.full():
                try:
                    self._frame_queue.get_nowait()
                except Exception:
                    pass
            self._frame_queue.put_nowait((cam_id, frm))
        except Exception:
            pass

    def run(self) -> Dict[str, Any]:
        """
        Executes detection, tracking, spatial rules evaluation, and alert dispatch over the input video.
        """
        mode_tags = []
        if self.detector:
            mode_tags.append("DETECTION")
        if self.config.enable_tracking:
            mode_tags.append(f"MOT ({self.config.tracker_type.upper()})")
        if self.anpr_analyzer:
            mode_tags.append("ANPR")
        if self.face_analyzer:
            mode_tags.append("FRS")
        if self.rules_engine:
            mode_tags.append("SPATIAL RULES")
        if self.alert_engine:
            mode_tags.append("ALERT ENGINE" + (" (REDIS)" if self.config.publish_redis else ""))
        mode_label = " + ".join(mode_tags)

        print(f"\n==================================================")
        print(f" [IBVAP AI Engine] Starting Video Pipeline ({mode_label})")
        print(f"==================================================")
        print(f" Input Video:          {self.config.input_path}")
        print(f" Output Video:         {self.config.output_path}")
        print(f" Video Resolution:     {self.reader.width}x{self.reader.height} @ {self.reader.fps:.1f} FPS")
        print(f" Total Frames:         {self.reader.total_frames}")
        print(f" Target Model:         {self.config.model_name_or_path} ({self.config.device.upper()})")
        print(f" Confidence Thresh:    {self.config.confidence_threshold:.2f}")
        print(f" Target Classes:       {', '.join(self.config.target_classes or ['ALL'])}")
        if self.config.enable_tracking:
            print(f" Max Trajectory Len:   {self.config.max_trajectory_length} points")
            print(f" Lost Track Threshold: {self.config.max_lost_frames} frames")
        if self.rules_engine:
            print(f" Spatial Config:       {self.config.spatial_rules_path}")
            print(f" Monitored Zones:      {len(self.rules_engine.zones)}")
            print(f" Monitored Tripwires:  {len(self.rules_engine.tripwires)}")
        if self.alert_engine:
            print(f" Alert Cooldown:       {self.alert_engine.cooldown_seconds:.1f}s")
            print(f" Redis Publishing:     {'ENABLED' if self.config.publish_redis else 'LOCAL/IN-MEMORY'}")
        print(f"==================================================\n")

        # Sync camera connection state to central FastAPI backend if online
        if self.config.camera_id:
            try:
                import urllib.request
                import json
                is_live_stream = str(self.config.input_path).lower().startswith(("rtsp://", "rtsps://", "http://", "https://")) or "95366" in str(self.config.input_path)
                stream_stat = "online" if is_live_stream else "simulated"
                status_payload = json.dumps({"status": stream_stat}).encode("utf-8")
                req = urllib.request.Request(
                    f"http://localhost:8000/api/v1/cameras/{self.config.camera_id}/status",
                    data=status_payload,
                    headers={"Content-Type": "application/json"},
                    method="PATCH"
                )
                urllib.request.urlopen(req, timeout=0.5)
            except Exception:
                pass

        writer = None  # Lazily created on first decoded frame using actual dimensions

        total_processed_frames = 0
        total_detections_count = 0
        detections_by_class: Dict[str, int] = defaultdict(int)
        all_tracks_history: Dict[int, TrackedEntity] = {}
        all_security_events: List[SpatialZoneEvent] = []
        all_anpr_events: List[Any] = []
        all_face_events: List[Any] = []
        all_produced_alerts: List[Any] = []
        events_by_type: Dict[str, int] = defaultdict(int)
        alerts_by_severity: Dict[str, int] = defaultdict(int)
        violator_track_ids: Set[int] = set()

        start_time = time.time()
        rolling_fps = 0.0

        try:
            for frame_idx, timestamp_sec, frame in self.reader.read_frames():
                frame_t0 = time.time()

                # Step 1: Run YOLO Object Detection
                use_native_yolo_track = self.config.enable_tracking and self.config.tracker_type == "native"
                detections = self.detector.detect(frame, track=use_native_yolo_track)
                total_detections_count += len(detections)

                for det in detections:
                    detections_by_class[det.class_name.value] += 1

                # Step 2: Multi-Object Tracking & Trajectory Association
                items_to_render = detections
                total_unique_tracks = 0

                active_tracks: List[TrackedEntity] = []
                if self.tracker is not None:
                    active_tracks = self.tracker.update(detections, frame)
                    items_to_render = active_tracks
                    total_unique_tracks = self.tracker.total_unique_tracks

                    for track in active_tracks:
                        all_tracks_history[track.track_id] = track

                # Step 3A: ANPR Plate Recognition (Phase 5B)
                current_frame_anpr_events = []
                if self.anpr_analyzer is not None and active_tracks:
                    current_frame_anpr_events = self.anpr_analyzer.process_tracks(
                        frame=frame,
                        tracks=active_tracks,
                        camera_id=self.config.camera_id,
                        frame_idx=frame_idx
                    )
                    for anpr_evt in current_frame_anpr_events:
                        all_anpr_events.append(anpr_evt)
                        if self.alert_engine is not None:
                            alt = self.alert_engine.process_anpr_event(anpr_evt, current_time=timestamp_sec)
                            if alt is not None:
                                all_produced_alerts.append(alt)
                                alerts_by_severity[alt.severity] += 1
                                print(
                                    f" 🏷️ [{alt.severity.upper()} ANPR ALERT] Frame {frame_idx:05d}: "
                                    f"Vehicle #{anpr_evt.track_id} ({anpr_evt.vehicle_class.upper()}) | "
                                    f"Plate: [{anpr_evt.plate_number}]"
                                )
                                try:
                                    import urllib.request
                                    import json
                                    payload_bytes = json.dumps(alt.to_dict(), default=str).encode("utf-8")
                                    req = urllib.request.Request(
                                        "http://localhost:8000/api/v1/alerts",
                                        data=payload_bytes,
                                        headers={"Content-Type": "application/json"},
                                        method="POST"
                                    )
                                    urllib.request.urlopen(req, timeout=0.5)
                                except Exception:
                                    pass

                # Step 3B: Face Recognition System (Phase 5C)
                current_frame_face_events = []
                if self.face_analyzer is not None and active_tracks:
                    current_frame_face_events = self.face_analyzer.process_tracks(
                        frame=frame,
                        tracks=active_tracks,
                        camera_id=self.config.camera_id,
                        frame_idx=frame_idx
                    )
                    for face_evt in current_frame_face_events:
                        all_face_events.append(face_evt)
                        if self.alert_engine is not None:
                            alt = self.alert_engine.process_face_event(face_evt, current_time=timestamp_sec)
                            if alt is not None:
                                all_produced_alerts.append(alt)
                                alerts_by_severity[alt.severity] += 1
                                print(
                                    f" 👤 [{alt.severity.upper()} FACE ALERT] Frame {frame_idx:05d}: "
                                    f"Person #{face_evt.track_id} | "
                                    f"Identity: [{face_evt.display_name}] (Sim: {face_evt.similarity * 100:.1f}%)"
                                )
                                try:
                                    import urllib.request
                                    import json
                                    payload_bytes = json.dumps(alt.to_dict(), default=str).encode("utf-8")
                                    req = urllib.request.Request(
                                        "http://localhost:8000/api/v1/alerts",
                                        data=payload_bytes,
                                        headers={"Content-Type": "application/json"},
                                        method="POST"
                                    )
                                    urllib.request.urlopen(req, timeout=0.5)
                                except Exception:
                                    pass

                # Step 3C: Traffic Line-Crossing & Unique Vehicle Counting
                current_frame_traffic_events = []
                if self.traffic_counter is not None and active_tracks:
                    from datetime import datetime
                    now_iso = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
                    current_frame_traffic_events = self.traffic_counter.process_tracks(
                        tracks=active_tracks,
                        frame=frame,
                        frame_idx=frame_idx,
                        timestamp_str=now_iso
                    )
                    for tr_evt in current_frame_traffic_events:
                        print(
                            f" 🚗 [TRAFFIC COUNT +1] Frame {frame_idx:05d}: "
                            f"{tr_evt.object_type.upper()} Track #{tr_evt.track_id} "
                            f"({tr_evt.direction}) -> Total {tr_evt.object_type}s: {self.traffic_counter.counted_totals[tr_evt.object_type]}"
                        )
                        # Dispatch crossing event to central FastAPI backend
                        try:
                            import urllib.request
                            import json
                            evt_payload = json.dumps(tr_evt.to_dict()).encode("utf-8")
                            req = urllib.request.Request(
                                f"http://localhost:8000/api/v1/cameras/{self.config.camera_id}/traffic-events",
                                data=evt_payload,
                                headers={"Content-Type": "application/json"},
                                method="POST"
                            )
                            urllib.request.urlopen(req, timeout=0.3)
                        except Exception:
                            pass

                # Step 4: Spatial Rules Evaluation
                current_frame_events: List[SpatialZoneEvent] = []
                if self.rules_engine is not None and active_tracks:
                    current_frame_events = self.rules_engine.evaluate(
                        tracks=active_tracks,
                        camera_id=self.config.camera_id,
                        frame_idx=frame_idx,
                        timestamp_sec=timestamp_sec
                    )
                    for evt in current_frame_events:
                        all_security_events.append(evt)
                        events_by_type[evt.rule_type] += 1
                        violator_track_ids.add(evt.track_id)

                    # Step 5: Spatial Alert Delivery & Deduplication
                    if self.alert_engine is not None and current_frame_events:
                        alerts = self.alert_engine.process_events_batch(
                            events=current_frame_events,
                            current_time=timestamp_sec
                        )
                        for alt in alerts:
                            all_produced_alerts.append(alt)
                            alerts_by_severity[alt.severity] += 1
                            print(
                                f" 🚨 [{alt.severity.upper()} ALERT] Frame {frame_idx:05d}: "
                                f"{alt.event_type.upper()} | Track #{alt.track_id} ({alt.object_class.upper()}) | "
                                f"{alt.message}"
                            )
                            # Forward alert to central FastAPI backend if reachable
                            try:
                                import urllib.request
                                import json
                                payload_bytes = json.dumps(alt.to_dict(), default=str).encode("utf-8")
                                req = urllib.request.Request(
                                    "http://localhost:8000/api/v1/alerts",
                                    data=payload_bytes,
                                    headers={"Content-Type": "application/json"},
                                    method="POST"
                                )
                                urllib.request.urlopen(req, timeout=0.5)
                            except Exception:
                                pass

                # Calculate instantaneous processing FPS
                frame_dt = time.time() - frame_t0
                if frame_dt > 0:
                    rolling_fps = 0.9 * rolling_fps + 0.1 * (1.0 / frame_dt) if rolling_fps > 0 else 1.0 / frame_dt

                # Step 6: Render Tactical Overlays
                if writer is None and self.config.save_annotated_video:
                    fh, fw = frame.shape[:2]
                    self.reader._width = fw
                    self.reader._height = fh
                    out_fps = max(1.0, self.reader.fps / (self.config.skip_frames + 1))
                    try:
                        writer = VideoWriter(
                            output_path=self.config.output_path,
                            fps=out_fps,
                            width=fw,
                            height=fh
                        )
                    except Exception as wex:
                        print(f" [WARN] VideoWriter deferred: {wex}")

                # Step 6: Render Tactical Visual Overlays & Live Frame Streaming
                zones_list = list(self.rules_engine.zones.values()) if self.rules_engine else None
                tripwires_list = list(self.rules_engine.tripwires.values()) if self.rules_engine else None
                counting_coords = self.traffic_counter.get_counting_line() if self.traffic_counter else None

                annotated_frame = self.annotator.annotate_frame(
                    frame=frame,
                    items=items_to_render,
                    zones=zones_list,
                    tripwires=tripwires_list,
                    events=current_frame_events,
                    frame_idx=frame_idx,
                    fps=rolling_fps,
                    total_tracks=total_unique_tracks if self.config.enable_tracking else None,
                    counting_line=counting_coords,
                    latency_ms=frame_dt * 1000.0,
                    traffic_counts=self.traffic_counter.counted_totals if self.traffic_counter else None
                )

                if writer is not None:
                    writer.write_frame(annotated_frame)

                # Push live annotated frame to central FastAPI streaming relay asynchronously
                self._push_annotated_frame(self.config.camera_id, annotated_frame)

                total_processed_frames += 1

                # Report real-time detection telemetry to backend
                if total_processed_frames % 2 == 0 or total_processed_frames == 1:
                    try:
                        import json
                        import urllib.request
                        telemetry_data = {
                            "camera_id": self.config.camera_id,
                            "frame_idx": frame_idx,
                            "fps": round(rolling_fps, 1),
                            "resolution": f"{self.reader.width}x{self.reader.height}",
                            "active_tracks": len(active_tracks) if self.config.enable_tracking else len(detections),
                            "total_unique_tracks": total_unique_tracks,
                            "status": "online",
                            "detections": [
                                {
                                    "track_id": getattr(item, "track_id", None),
                                    "class_name": item.class_name.value if hasattr(item.class_name, "value") else str(item.class_name),
                                    "confidence": round(item.confidence, 2),
                                    "bbox": [round(item.bbox.x1, 1), round(item.bbox.y1, 1), round(item.bbox.x2, 1), round(item.bbox.y2, 1)],
                                    "trajectory": getattr(item, "trajectory", [])[-15:],
                                }
                                for item in items_to_render
                            ],
                            "target_classes": list(set(
                                d.class_name.value if hasattr(d.class_name, "value") else str(d.class_name)
                                for d in detections
                            )),
                        }
                        if self.traffic_counter is not None:
                            telemetry_data["traffic"] = self.traffic_counter.get_telemetry_snapshot(active_tracks)
                        payload_bytes = json.dumps(telemetry_data).encode("utf-8")
                        req = urllib.request.Request(
                            f"http://localhost:8000/api/v1/cameras/{self.config.camera_id}/telemetry",
                            data=payload_bytes,
                            headers={"Content-Type": "application/json"},
                            method="POST"
                        )
                        urllib.request.urlopen(req, timeout=0.15)
                    except Exception:
                        pass

                # Console progress log
                if total_processed_frames % 20 == 0 or total_processed_frames == 1:
                    percent_str = ""
                    if self.reader.total_frames > 0:
                        pct = min(100.0, (frame_idx + 1) / self.reader.total_frames * 100)
                        percent_str = f" ({pct:.1f}%)"

                    track_info = f"Tracks: {len(items_to_render):02d} (Unique: {total_unique_tracks})" if self.config.enable_tracking else f"Detections: {len(detections):02d}"
                    alerts_info = f" | Alerts: {len(all_produced_alerts)}" if self.alert_engine else (f" | Events: {len(all_security_events)}" if self.rules_engine else "")
                    print(
                        f" Processing frame {frame_idx:05d}{percent_str} | "
                        f"{track_info}{alerts_info} | "
                        f"Speed: {rolling_fps:.1f} FPS"
                    )

        finally:
            if writer is not None:
                writer.release()

        elapsed_total = time.time() - start_time
        avg_processing_fps = total_processed_frames / elapsed_total if elapsed_total > 0 else 0.0

        unique_track_count = len(all_tracks_history)
        avg_track_length = 0.0
        max_track_length = 0
        if all_tracks_history:
            track_lengths = [len(t.trajectory) for t in all_tracks_history.values()]
            avg_track_length = sum(track_lengths) / len(track_lengths)
            max_track_length = max(track_lengths)

        active_tracks_final = len(self.tracker.active_tracks) if self.tracker else 0

        summary = {
            "status": "completed",
            "input_path": self.config.input_path,
            "output_path": self.config.output_path if self.config.save_annotated_video else None,
            "tracking_enabled": self.config.enable_tracking,
            "anpr_enabled": self.anpr_analyzer is not None,
            "frs_enabled": self.face_analyzer is not None,
            "spatial_rules_enabled": self.rules_engine is not None,
            "alert_engine_enabled": self.alert_engine is not None,
            "total_frames_processed": total_processed_frames,
            "total_detections": total_detections_count,
            "detections_by_class": dict(detections_by_class),
            "unique_tracks_count": unique_track_count,
            "active_tracks_count": active_tracks_final,
            "average_trajectory_length": round(avg_track_length, 1),
            "max_trajectory_length": max_track_length,
            "total_anpr_events": len(all_anpr_events),
            "recognized_plates": [e.plate_number for e in all_anpr_events],
            "total_face_events": len(all_face_events),
            "recognized_identities": [e.display_name for e in all_face_events],
            "total_security_events": len(all_security_events),
            "events_by_type": dict(events_by_type),
            "total_alerts_produced": len(all_produced_alerts),
            "alerts_by_severity": dict(alerts_by_severity),
            "unique_violator_tracks": len(violator_track_ids),
            "traffic_counts": self.traffic_counter.counted_totals if self.traffic_counter else {},
            "total_traffic_counted": sum(self.traffic_counter.counted_totals.values()) if self.traffic_counter else 0,
            "elapsed_seconds": round(elapsed_total, 2),
            "avg_fps": round(avg_processing_fps, 2),
            "resolution": f"{self.reader.width}x{self.reader.height}"
        }

        print(f"\n==================================================")
        print(f" [IBVAP AI Engine] Pipeline Execution Finished!")
        print(f" Processed Frames:     {total_processed_frames}")
        print(f" Total Detections:     {total_detections_count}")
        print(f" Detection Breakdown:  {dict(detections_by_class)}")
        if self.config.enable_tracking:
            print(f" Unique Tracks Count:  {unique_track_count}")
            print(f" Active Tracks Final:  {active_tracks_final}")
            print(f" Avg Trajectory Len:   {avg_track_length:.1f} frames/points (Max: {max_track_length})")
        if self.anpr_analyzer:
            print(f" ANPR Plates Resolved: {len(all_anpr_events)} ({[e.plate_number for e in all_anpr_events]})")
        if self.face_analyzer:
            print(f" FRS Faces Resolved:   {len(all_face_events)} ({[e.display_name for e in all_face_events]})")
        if self.rules_engine:
            print(f" Security Events:      {len(all_security_events)} ({dict(events_by_type)})")
        if self.alert_engine:
            print(f" Alerts Dispatched:    {len(all_produced_alerts)} ({dict(alerts_by_severity)})")
            print(f" Violator Track IDs:   {list(violator_track_ids)}")
        print(f" Elapsed Time:         {elapsed_total:.2f}s (Avg {avg_processing_fps:.1f} FPS)")
        if self.config.save_annotated_video:
            print(f" Saved Output:         {self.config.output_path}")
        print(f"==================================================\n")

        return summary
