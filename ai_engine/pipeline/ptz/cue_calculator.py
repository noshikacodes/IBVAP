from typing import Tuple, Optional, Union, Dict, Any
import logging

from ai_engine.pipeline.ptz.types import PTZPosition, PTZConfig

logger = logging.getLogger("ibvap.ptz.cue")


class PTZCueCalculator:
    """
    Deterministic Spatial Threat -> PTZ Slew-to-Cue Coordinate Calculator.
    Maps pixel bounding boxes or spatial centroids into calibrated 3D Pan-Tilt-Zoom angles.
    """

    @staticmethod
    def calculate_cue(
        target_bbox_or_point: Union[Tuple[float, float, float, float], Tuple[float, float], list],
        frame_width: int = 640,
        frame_height: int = 480,
        config: Optional[PTZConfig] = None,
        severity: str = "HIGH"
    ) -> PTZPosition:
        """
        Calculates target (pan, tilt, zoom) from pixel coordinates.
        target_bbox_or_point: [x1, y1, x2, y2] or [cx, cy]
        """
        fw = max(1, frame_width)
        fh = max(1, frame_height)

        cfg = config or PTZConfig(camera_id="DEFAULT_PTZ")

        # 1. Determine centroid and relative size
        if len(target_bbox_or_point) == 4:
            x1, y1, x2, y2 = target_bbox_or_point
            cx = (x1 + x2) / 2.0
            cy = (y1 + y2) / 2.0
            bbox_w = max(1.0, x2 - x1)
            bbox_h = max(1.0, y2 - y1)
            area_ratio = (bbox_w * bbox_h) / (fw * fh)
        elif len(target_bbox_or_point) == 2:
            cx, cy = target_bbox_or_point
            area_ratio = 0.05
        else:
            cx, cy = fw / 2.0, fh / 2.0
            area_ratio = 0.05

        # 2. Normalize to [0.0, 1.0] (center of frame = 0.5, 0.5)
        norm_x = max(0.0, min(1.0, cx / fw))
        norm_y = max(0.0, min(1.0, cy / fh))

        # 3. Map normalized coordinates into camera physical pan/tilt bounds
        # norm_x = 0.0 -> pan_min (far left); norm_x = 1.0 -> pan_max (far right)
        pan_span = cfg.ptz_pan_max - cfg.ptz_pan_min
        target_pan = cfg.ptz_pan_min + (norm_x * pan_span)

        # norm_y = 0.0 (top of image) -> tilt_max (upwards); norm_y = 1.0 (bottom) -> tilt_min (downwards)
        tilt_span = cfg.ptz_tilt_max - cfg.ptz_tilt_min
        target_tilt = cfg.ptz_tilt_min + ((1.0 - norm_y) * tilt_span)

        # 4. Adaptive optical zoom calculation: smaller target -> higher zoom
        if area_ratio < 0.01:
            target_zoom = 6.0
        elif area_ratio < 0.04:
            target_zoom = 4.0
        elif area_ratio < 0.10:
            target_zoom = 2.5
        else:
            target_zoom = 1.2

        if severity.upper() == "CRITICAL":
            target_zoom = min(cfg.ptz_zoom_max, target_zoom * 1.5)

        raw_pos = PTZPosition(pan=target_pan, tilt=target_tilt, zoom=target_zoom)
        return raw_pos.clamp(
            pan_min=cfg.ptz_pan_min,
            pan_max=cfg.ptz_pan_max,
            tilt_min=cfg.ptz_tilt_min,
            tilt_max=cfg.ptz_tilt_max,
            zoom_min=cfg.ptz_zoom_min,
            zoom_max=cfg.ptz_zoom_max,
        )
