import os
from typing import List, Dict, Tuple, Optional, Union, Any
import cv2
import numpy as np

from ai_engine.pipeline.types import (
    Detection,
    TrackedEntity,
    SpatialZoneEvent,
    SpatialEventType,
    ObjectClass,
)
from ai_engine.pipeline.spatial_rules import PolygonZone, Tripwire


# BGR Color definitions for high visibility in tactical monitoring
CLASS_COLORS: Dict[ObjectClass, Tuple[int, int, int]] = {
    ObjectClass.HUMAN: (0, 230, 64),       # Bright Green
    ObjectClass.PERSON: (0, 230, 64),      # Bright Green
    ObjectClass.CAR: (255, 178, 50),       # Blue / Amber
    ObjectClass.VEHICLE: (255, 178, 50),   # Blue / Amber
    ObjectClass.TRUCK: (255, 100, 0),      # Dark Blue
    ObjectClass.BUS: (200, 200, 0),        # Teal / Cyan
    ObjectClass.MOTORCYCLE: (0, 165, 255), # Orange
    ObjectClass.VESSEL: (255, 0, 200),     # Magenta
    ObjectClass.BOAT: (255, 0, 200),       # Magenta
    ObjectClass.BICYCLE: (180, 255, 50),   # Lime
    ObjectClass.UNKNOWN: (128, 128, 128)   # Grey
}

EVENT_COLORS: Dict[SpatialEventType, Tuple[int, int, int]] = {
    SpatialEventType.INTRUSION: (0, 0, 255),         # Bright Red
    SpatialEventType.TRIPWIRE_CROSSING: (0, 140, 255),# Hot Orange
    SpatialEventType.LOITERING: (0, 215, 255),       # Amber / Gold
    SpatialEventType.ZONE_EXIT: (180, 180, 180),     # Grey
}


class VideoAnnotator:
    """
    Renders military/C2-style bounding boxes, labels, persistent track IDs,
    trajectory history trails, polygon geofences, tripwires, live security event badges,
    and telemetry HUD overlays on video frames.
    """

    def __init__(
        self,
        draw_telemetry: bool = True,
        draw_trajectories: bool = True,
        draw_zones: bool = True,
        draw_events: bool = True
    ):
        self.draw_telemetry = draw_telemetry
        self.draw_trajectories = draw_trajectories
        self.draw_zones = draw_zones
        self.draw_events = draw_events

    def annotate_frame(
        self,
        frame: np.ndarray,
        items: Union[List[Detection], List[TrackedEntity]],
        zones: Optional[List[PolygonZone]] = None,
        tripwires: Optional[List[Tripwire]] = None,
        events: Optional[List[SpatialZoneEvent]] = None,
        frame_idx: int = 0,
        fps: float = 0.0,
        total_tracks: Optional[int] = None,
        extra_info: Optional[str] = None,
        counting_line: Optional[List[List[float]]] = None,
        latency_ms: float = 0.0,
        traffic_counts: Optional[Dict[str, int]] = None
    ) -> np.ndarray:
        """
        Draws spatial geofences, tripwires, counting line, moving trajectories,
        bounding boxes, center dots, track IDs, and tactical HUD overlays.
        """
        if frame is None or frame.size == 0:
            return frame

        annotated = frame.copy()
        height, width = annotated.shape[:2]

        # ----------------------------------------------------
        # 0. Draw Virtual Counting Line Across Roadway
        # ----------------------------------------------------
        if counting_line and len(counting_line) == 2:
            cp1 = (int(round(counting_line[0][0])), int(round(counting_line[0][1])))
            cp2 = (int(round(counting_line[1][0])), int(round(counting_line[1][1])))
            # Glowing underlay
            cv2.line(annotated, cp1, cp2, (255, 180, 0), 4, lineType=cv2.LINE_AA)
            # Core dashed line
            cv2.line(annotated, cp1, cp2, (255, 255, 0), 2, lineType=cv2.LINE_AA)
            cv2.circle(annotated, cp1, 5, (255, 255, 0), -1)
            cv2.circle(annotated, cp2, 5, (255, 255, 0), -1)
            mid_cx = (cp1[0] + cp2[0]) // 2
            mid_cy = max(20, (cp1[1] + cp2[1]) // 2 - 8)
            cv2.rectangle(annotated, (mid_cx - 85, mid_cy - 14), (mid_cx + 85, mid_cy + 4), (15, 23, 42), -1)
            cv2.rectangle(annotated, (mid_cx - 85, mid_cy - 14), (mid_cx + 85, mid_cy + 4), (255, 220, 0), 1)
            cv2.putText(
                annotated,
                "VIRTUAL COUNTING LINE",
                (mid_cx - 78, mid_cy - 2),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.36,
                (255, 255, 0),
                1,
                lineType=cv2.LINE_AA
            )

        # ----------------------------------------------------
        # 1. Draw Polygon Zones (Virtual Fences)
        # ----------------------------------------------------
        if self.draw_zones and zones:
            zone_overlay = annotated.copy()
            for zone in zones:
                if not zone.enabled or len(zone.polygon) < 3:
                    continue

                pts = np.array([zone.polygon], dtype=np.int32)
                cv2.fillPoly(zone_overlay, pts, (0, 40, 160))
                cv2.polylines(annotated, pts, isClosed=True, color=(0, 70, 255), thickness=2, lineType=cv2.LINE_AA)

                label_x = int(zone.polygon[0][0])
                label_y = max(20, int(zone.polygon[0][1]) - 8)
                cv2.putText(
                    annotated,
                    f"ZONE: {zone.name.upper()}",
                    (label_x, label_y),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.42,
                    (0, 140, 255),
                    1,
                    lineType=cv2.LINE_AA
                )

            cv2.addWeighted(zone_overlay, 0.25, annotated, 0.75, 0, annotated)

        # ----------------------------------------------------
        # 2. Draw Tripwires
        # ----------------------------------------------------
        if self.draw_zones and tripwires:
            for tw in tripwires:
                if not tw.enabled:
                    continue
                p1 = (int(round(tw.pt1[0])), int(round(tw.pt1[1])))
                p2 = (int(round(tw.pt2[0])), int(round(tw.pt2[1])))

                cv2.line(annotated, p1, p2, (0, 220, 255), 2, lineType=cv2.LINE_AA)
                cv2.circle(annotated, p1, 5, (0, 180, 255), -1)
                cv2.circle(annotated, p2, 5, (0, 180, 255), -1)

                mid_x = (p1[0] + p2[0]) // 2
                mid_y = max(20, (p1[1] + p2[1]) // 2 - 8)
                cv2.putText(
                    annotated,
                    f"TRIPWIRE: {tw.name.upper()} ({tw.direction.value})",
                    (mid_x, mid_y),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.40,
                    (0, 220, 255),
                    1,
                    lineType=cv2.LINE_AA
                )

        # ----------------------------------------------------
        # 3. Draw Moving Trajectory Trails (underneath bounding boxes)
        # ----------------------------------------------------
        if self.draw_trajectories:
            for item in items:
                if isinstance(item, TrackedEntity) and len(item.trajectory) > 1:
                    color = CLASS_COLORS.get(item.class_name, (0, 255, 255))
                    pts = item.trajectory[-20:]  # Draw last 20 movement steps
                    for i in range(1, len(pts)):
                        pt1 = (int(round(pts[i - 1][0])), int(round(pts[i - 1][1])))
                        pt2 = (int(round(pts[i][0])), int(round(pts[i][1])))
                        # Fading trail line thickness
                        cv2.line(annotated, pt1, pt2, color, 2, lineType=cv2.LINE_AA)
                        cv2.circle(annotated, pt1, 2, color, -1)
                    if pts:
                        last_pt = (int(round(pts[-1][0])), int(round(pts[-1][1])))
                        cv2.circle(annotated, last_pt, 4, (255, 255, 255), -1)

        # ----------------------------------------------------
        # 4. Draw Bounding Boxes, Labels, and Center Dots
        # ----------------------------------------------------
        for item in items:
            bbox = item.bbox if isinstance(item, Detection) else item.current_bbox
            x1, y1, x2, y2 = bbox.as_int_xyxy()

            # Clamp coordinates
            x1 = max(0, min(width - 1, x1))
            y1 = max(0, min(height - 1, y1))
            x2 = max(0, min(width - 1, x2))
            y2 = max(0, min(height - 1, y2))

            color = CLASS_COLORS.get(item.class_name, (0, 255, 255))

            # Draw main bounding box
            cv2.rectangle(annotated, (x1, y1), (x2, y2), color, 2, lineType=cv2.LINE_AA)

            # Center contact point dot
            cx = (x1 + x2) // 2
            cy = (y1 + y2) // 2
            cv2.circle(annotated, (cx, cy), 3, (0, 255, 255), -1)
            cv2.circle(annotated, (cx, y2), 4, (0, 255, 0), -1)  # Bottom contact point

            # Draw tactical corner brackets
            corner_len = min(15, max(5, int((x2 - x1) * 0.15)))
            cv2.line(annotated, (x1, y1), (x1 + corner_len, y1), (255, 255, 255), 2)
            cv2.line(annotated, (x1, y1), (x1, y1 + corner_len), (255, 255, 255), 2)
            cv2.line(annotated, (x2, y1), (x2 - corner_len, y1), (255, 255, 255), 2)
            cv2.line(annotated, (x2, y1), (x2, y1 + corner_len), (255, 255, 255), 2)
            cv2.line(annotated, (x1, y2), (x1 + corner_len, y2), (255, 255, 255), 2)
            cv2.line(annotated, (x1, y2), (x1, y2 - corner_len), (255, 255, 255), 2)
            cv2.line(annotated, (x2, y2), (x2 - corner_len, y2), (255, 255, 255), 2)
            cv2.line(annotated, (x2, y2), (x2, y2 - corner_len), (255, 255, 255), 2)

            # Build label text: e.g. "CAR 0.92 | ID: 17"
            cls_str = item.raw_class_name.upper() if item.raw_class_name else "OBJECT"
            conf_str = f"{item.confidence:.2f}"
            id_str = f" | ID: {item.track_id}" if item.track_id is not None else ""
            label = f"{cls_str} {conf_str}{id_str}"

            font = cv2.FONT_HERSHEY_SIMPLEX
            font_scale = 0.42
            font_thickness = 1
            (text_w, text_h), baseline = cv2.getTextSize(label, font, font_scale, font_thickness)

            # Background badge
            badge_y1 = max(0, y1 - text_h - 6)
            badge_y2 = max(text_h + 6, y1)
            badge_x2 = min(width, x1 + text_w + 8)

            cv2.rectangle(annotated, (x1, badge_y1), (badge_x2, badge_y2), color, -1)
            cv2.putText(
                annotated,
                label,
                (x1 + 4, badge_y2 - 4),
                font,
                font_scale,
                (0, 0, 0),
                font_thickness,
                lineType=cv2.LINE_AA
            )

        # ----------------------------------------------------
        # 5. Draw C2 Tactical Telemetry HUD Overlay
        # ----------------------------------------------------
        if self.draw_telemetry:
            # Top Bar Ribbon
            hud_bg = annotated.copy()
            cv2.rectangle(hud_bg, (0, 0), (width, 32), (10, 15, 26), -1)
            cv2.addWeighted(hud_bg, 0.75, annotated, 0.25, 0, annotated)
            cv2.line(annotated, (0, 32), (width, 32), (30, 41, 59), 1)

            # Top HUD Text
            cv2.circle(annotated, (14, 16), 4, (0, 0, 255), -1)
            model_tag = getattr(self, "model_name", "YOLO26s")
            hud_left = f"LIVE | MODEL: {model_tag} | TRACKER: BYTETRACK | {width}x{height}"
            cv2.putText(annotated, hud_left, (24, 21), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (0, 255, 200), 1, lineType=cv2.LINE_AA)

            lat_str = f"{latency_ms:.0f}ms" if latency_ms > 0 else "<50ms"
            hud_right = f"FPS: {fps:.1f} | LATENCY: {lat_str} | TRACKS: {len(items)}"
            (rw, _), _ = cv2.getTextSize(hud_right, cv2.FONT_HERSHEY_SIMPLEX, 0.42, 1)
            cv2.putText(annotated, hud_right, (width - rw - 10, 21), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (56, 189, 248), 1, lineType=cv2.LINE_AA)

        return annotated


class VideoWriter:
    """
    OpenCV VideoWriter wrapper with automatic directory creation and codec fallback.
    """

    def __init__(
        self,
        output_path: str,
        fps: float,
        width: int,
        height: int,
        codec: str = "mp4v"
    ):
        self.output_path = os.path.abspath(output_path)
        self.fps = float(fps)
        self.width = int(width)
        self.height = int(height)
        self.codec = codec
        self._writer: Optional[cv2.VideoWriter] = None

        os.makedirs(os.path.dirname(self.output_path), exist_ok=True)
        self._initialize_writer()

    def _initialize_writer(self) -> None:
        fourcc = cv2.VideoWriter_fourcc(*self.codec)
        self._writer = cv2.VideoWriter(
            self.output_path,
            fourcc,
            self.fps,
            (self.width, self.height)
        )

        if not self._writer.isOpened():
            fallback_codec = "avc1" if self.codec != "avc1" else "XVID"
            fourcc = cv2.VideoWriter_fourcc(*fallback_codec)
            self._writer = cv2.VideoWriter(
                self.output_path,
                fourcc,
                self.fps,
                (self.width, self.height)
            )

        if not self._writer.isOpened():
            raise RuntimeError(
                f"Failed to create video writer for output path '{self.output_path}' with codec '{self.codec}'."
            )

    def write_frame(self, frame: np.ndarray) -> None:
        if self._writer is None:
            raise RuntimeError("VideoWriter is closed.")
        self._writer.write(frame)

    def release(self) -> None:
        if self._writer is not None:
            self._writer.release()
            self._writer = None

    def __enter__(self) -> "VideoWriter":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.release()
