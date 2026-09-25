from typing import Dict, List, Optional, Tuple, Any, Callable
import threading
import time
try:
    import psutil
except ImportError:
    psutil = None

try:
    import torch
except ImportError:
    torch = None

DEFAULT_BUCKETS = (0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0)


class LabelValidator:
    """Sanitizes labels to prevent high cardinality and credential leakage."""
    FORBIDDEN_KEYS = {"password", "token", "secret", "auth", "url", "input_url", "uri"}

    @classmethod
    def sanitize_label_value(cls, val: Any) -> str:
        s = str(val).strip()
        # Redact any basic auth credentials if present
        if "://" in s and "@" in s:
            parts = s.split("://", 1)
            scheme = parts[0]
            rest = parts[1]
            if "@" in rest:
                s = f"{scheme}://***@{rest.split('@', 1)[1]}"
        # Bound length
        return s[:64].replace('"', '\\"').replace('\n', '')


def _format_labels(labels: Dict[str, Any]) -> str:
    if not labels:
        return ""
    sorted_pairs = sorted(labels.items())
    formatted = [
        f'{k}="{LabelValidator.sanitize_label_value(v)}"'
        for k, v in sorted_pairs
    ]
    return "{" + ",".join(formatted) + "}"


class BaseMetric:
    def __init__(self, name: str, description: str, label_names: Optional[List[str]] = None):
        self.name = name
        self.description = description
        self.label_names = set(label_names or [])
        self._lock = threading.Lock()

    def _validate_labels(self, labels: Optional[Dict[str, Any]]) -> Dict[str, str]:
        if not labels:
            return {}
        return {str(k): LabelValidator.sanitize_label_value(v) for k, v in labels.items()}


class Counter(BaseMetric):
    """Monotonically increasing cumulative metric."""

    def __init__(self, name: str, description: str, label_names: Optional[List[str]] = None):
        super().__init__(name, description, label_names)
        self._values: Dict[Tuple[Tuple[str, str], ...], float] = {}

    def inc(self, value: float = 1.0, labels: Optional[Dict[str, Any]] = None):
        if value < 0:
            raise ValueError("Counter increments must be non-negative")
        sanitized = self._validate_labels(labels)
        key = tuple(sorted(sanitized.items()))
        with self._lock:
            self._values[key] = self._values.get(key, 0.0) + value

    def get(self, labels: Optional[Dict[str, Any]] = None) -> float:
        sanitized = self._validate_labels(labels)
        key = tuple(sorted(sanitized.items()))
        with self._lock:
            return self._values.get(key, 0.0)

    def render(self) -> List[str]:
        lines = [
            f"# HELP {self.name} {self.description}",
            f"# TYPE {self.name} counter",
        ]
        with self._lock:
            for key, val in sorted(self._values.items()):
                label_str = _format_labels(dict(key))
                lines.append(f"{self.name}{label_str} {val}")
        return lines


class Gauge(BaseMetric):
    """Instantaneous metric value that can arbitrarily increase or decrease."""

    def __init__(self, name: str, description: str, label_names: Optional[List[str]] = None):
        super().__init__(name, description, label_names)
        self._values: Dict[Tuple[Tuple[str, str], ...], float] = {}

    def set(self, value: float, labels: Optional[Dict[str, Any]] = None):
        sanitized = self._validate_labels(labels)
        key = tuple(sorted(sanitized.items()))
        with self._lock:
            self._values[key] = float(value)

    def inc(self, value: float = 1.0, labels: Optional[Dict[str, Any]] = None):
        sanitized = self._validate_labels(labels)
        key = tuple(sorted(sanitized.items()))
        with self._lock:
            self._values[key] = self._values.get(key, 0.0) + value

    def dec(self, value: float = 1.0, labels: Optional[Dict[str, Any]] = None):
        sanitized = self._validate_labels(labels)
        key = tuple(sorted(sanitized.items()))
        with self._lock:
            self._values[key] = self._values.get(key, 0.0) - value

    def get(self, labels: Optional[Dict[str, Any]] = None) -> float:
        sanitized = self._validate_labels(labels)
        key = tuple(sorted(sanitized.items()))
        with self._lock:
            return self._values.get(key, 0.0)

    def render(self) -> List[str]:
        lines = [
            f"# HELP {self.name} {self.description}",
            f"# TYPE {self.name} gauge",
        ]
        with self._lock:
            for key, val in sorted(self._values.items()):
                label_str = _format_labels(dict(key))
                lines.append(f"{self.name}{label_str} {val}")
        return lines


class HistogramTimer:
    def __init__(self, histogram: 'Histogram', labels: Optional[Dict[str, Any]] = None):
        self.histogram = histogram
        self.labels = labels
        self.start_time = 0.0

    def __enter__(self):
        self.start_time = time.perf_counter()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        duration = time.perf_counter() - self.start_time
        self.histogram.observe(duration, self.labels)


class Histogram(BaseMetric):
    """Tracks the statistical distribution of observed values (e.g. request/inference latencies)."""

    def __init__(
        self,
        name: str,
        description: str,
        label_names: Optional[List[str]] = None,
        buckets: Tuple[float, ...] = DEFAULT_BUCKETS,
    ):
        super().__init__(name, description, label_names)
        self.buckets = tuple(sorted(buckets))
        self._counts: Dict[Tuple[Tuple[str, str], ...], int] = {}
        self._sums: Dict[Tuple[Tuple[str, str], ...], float] = {}
        self._bucket_counts: Dict[Tuple[Tuple[str, str], ...], Dict[float, int]] = {}

    def observe(self, value: float, labels: Optional[Dict[str, Any]] = None):
        sanitized = self._validate_labels(labels)
        key = tuple(sorted(sanitized.items()))
        with self._lock:
            self._counts[key] = self._counts.get(key, 0) + 1
            self._sums[key] = self._sums.get(key, 0.0) + value

            if key not in self._bucket_counts:
                self._bucket_counts[key] = {b: 0 for b in self.buckets}

            for b in self.buckets:
                if value <= b:
                    self._bucket_counts[key][b] += 1

    def time(self, labels: Optional[Dict[str, Any]] = None) -> HistogramTimer:
        return HistogramTimer(self, labels)

    def render(self) -> List[str]:
        lines = [
            f"# HELP {self.name} {self.description}",
            f"# TYPE {self.name} histogram",
        ]
        with self._lock:
            for key in sorted(self._counts.keys()):
                base_labels = dict(key)
                b_counts = self._bucket_counts[key]
                for b in self.buckets:
                    b_lbls = dict(base_labels)
                    b_lbls["le"] = str(b)
                    lines.append(f"{self.name}_bucket{_format_labels(b_lbls)} {b_counts[b]}")
                
                inf_lbls = dict(base_labels)
                inf_lbls["le"] = "+Inf"
                lines.append(f"{self.name}_bucket{_format_labels(inf_lbls)} {self._counts[key]}")
                lines.append(f"{self.name}_sum{_format_labels(base_labels)} {self._sums[key]}")
                lines.append(f"{self.name}_count{_format_labels(base_labels)} {self._counts[key]}")
        return lines


class MetricsRegistry:
    """Thread-safe centralized Prometheus Metrics Registry for IBVAP."""

    def __init__(self):
        self._lock = threading.Lock()
        self._metrics: Dict[str, BaseMetric] = {}
        self._init_standard_metrics()

    def _init_standard_metrics(self):
        # 1. Camera & Stream Telemetry
        self.camera_fps = self.gauge(
            "ibvap_camera_fps",
            "Current frame rate of surveillance camera stream",
            ["camera_id"]
        )
        self.camera_frames_received = self.counter(
            "ibvap_camera_frames_received_total",
            "Total video frames ingested by camera pipeline",
            ["camera_id"]
        )
        self.camera_frames_dropped = self.counter(
            "ibvap_camera_frames_dropped_total",
            "Total video frames dropped due to backpressure or decode errors",
            ["camera_id"]
        )
        self.camera_connection_state = self.gauge(
            "ibvap_camera_connection_state",
            "Camera stream connection status (1 for active state, 0 otherwise)",
            ["camera_id", "state"]
        )
        self.camera_reconnects = self.counter(
            "ibvap_camera_reconnects_total",
            "Total reconnection attempts for camera stream",
            ["camera_id"]
        )
        self.camera_stream_stalls = self.counter(
            "ibvap_camera_stream_stalls_total",
            "Total watchdog stall events detected on camera stream",
            ["camera_id"]
        )

        # 2. AI Inference & Tracking Telemetry
        self.yolo_latency = self.histogram(
            "ibvap_yolo_inference_latency_seconds",
            "Latency of YOLO object detection model forward pass",
            ["model", "device"],
            buckets=(0.005, 0.01, 0.02, 0.035, 0.05, 0.1, 0.25, 0.5, 1.0)
        )
        self.yolo_detections = self.counter(
            "ibvap_yolo_detections_total",
            "Total objects detected by class and camera",
            ["camera_id", "class_name"]
        )
        self.bytetrack_latency = self.histogram(
            "ibvap_bytetrack_latency_seconds",
            "Latency of ByteTrack multi-object tracking association step",
            ["camera_id"],
            buckets=(0.001, 0.003, 0.005, 0.01, 0.025, 0.05)
        )
        self.bytetrack_active_tracks = self.gauge(
            "ibvap_bytetrack_active_tracks",
            "Current number of actively tracked entities in video stream",
            ["camera_id"]
        )

        # 3. ANPR & FRS Pipeline Telemetry
        self.anpr_processed = self.counter(
            "ibvap_anpr_processed_total",
            "Total license plate crops analyzed by ANPR OCR engine",
            ["camera_id", "status"]
        )
        self.anpr_latency = self.histogram(
            "ibvap_anpr_latency_seconds",
            "Latency of ANPR plate detection and EasyOCR processing",
            ["camera_id"],
            buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.0)
        )
        self.anpr_watchlist_matches = self.counter(
            "ibvap_anpr_watchlist_matches_total",
            "Total license plate matches against security watchlists",
            ["camera_id"]
        )

        self.frs_processed = self.counter(
            "ibvap_frs_processed_total",
            "Total face crops processed by biometric recognition pipeline",
            ["camera_id", "match_status"]
        )
        self.frs_latency = self.histogram(
            "ibvap_frs_latency_seconds",
            "Latency of FaceNet embedding extraction and gallery matching",
            ["camera_id"],
            buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0)
        )
        self.frs_gallery_size = self.gauge(
            "ibvap_frs_gallery_size",
            "Total registered identities in biometric face gallery"
        )

        # 4. Spatial Rules & PTZ Slew-to-Cue
        self.spatial_evaluations = self.counter(
            "ibvap_spatial_evaluations_total",
            "Total spatial geofence and tripwire boundary checks",
            ["camera_id", "rule_type"]
        )
        self.spatial_breaches = self.counter(
            "ibvap_spatial_breaches_total",
            "Total perimeter security boundary violations detected",
            ["camera_id", "rule_type", "severity"]
        )
        self.spatial_latency = self.histogram(
            "ibvap_spatial_latency_seconds",
            "Latency of spatial geometry calculations and temporal tracking",
            ["camera_id"],
            buckets=(0.0005, 0.001, 0.002, 0.005, 0.01, 0.025)
        )

        self.ptz_commands = self.counter(
            "ibvap_ptz_commands_total",
            "Total PTZ slew-to-cue and manual positioning commands issued",
            ["camera_id", "driver_type", "command_type"]
        )
        self.ptz_latency = self.histogram(
            "ibvap_ptz_latency_seconds",
            "Response latency for PTZ driver execution and acknowledgement",
            ["camera_id"],
            buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0)
        )

        # 5. Security Alerts & Tactical Incidents
        self.alerts_created = self.counter(
            "ibvap_alerts_created_total",
            "Total security alerts generated by Alert Engine",
            ["camera_id", "event_type", "severity"]
        )
        self.incidents_created = self.counter(
            "ibvap_incidents_created_total",
            "Total tactical incidents opened in incident management ledger",
            ["severity"]
        )
        self.incident_dispatches = self.counter(
            "ibvap_incident_dispatches_total",
            "Total multi-agency tactical dispatches executed",
            ["agency", "status"]
        )

        # 6. HTTP API & System Resources
        self.http_requests = self.counter(
            "ibvap_http_requests_total",
            "Total HTTP REST API requests handled by FastAPI backend",
            ["method", "endpoint", "status_code"]
        )
        self.http_request_duration = self.histogram(
            "ibvap_http_request_duration_seconds",
            "HTTP request processing latency",
            ["method", "endpoint"],
            buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5)
        )
        self.worker_processes_active = self.gauge(
            "ibvap_worker_processes_active",
            "Current number of managed AI worker subprocesses running"
        )
        self.worker_restarts = self.counter(
            "ibvap_worker_restarts_total",
            "Total worker supervisor crash recoveries and restarts",
            ["camera_id"]
        )

        self.system_cpu_usage = self.gauge(
            "ibvap_system_cpu_usage_percent",
            "Total system CPU utilization percentage"
        )
        self.system_memory_usage = self.gauge(
            "ibvap_system_memory_usage_bytes",
            "System memory consumption in bytes"
        )
        self.system_gpu_usage = self.gauge(
            "ibvap_system_gpu_usage_percent",
            "GPU hardware utilization percentage (fallback to 0 if CPU only)",
            ["gpu_index"]
        )

    def counter(self, name: str, description: str, label_names: Optional[List[str]] = None) -> Counter:
        with self._lock:
            if name not in self._metrics:
                self._metrics[name] = Counter(name, description, label_names)
            return self._metrics[name]  # type: ignore

    def gauge(self, name: str, description: str, label_names: Optional[List[str]] = None) -> Gauge:
        with self._lock:
            if name not in self._metrics:
                self._metrics[name] = Gauge(name, description, label_names)
            return self._metrics[name]  # type: ignore

    def histogram(
        self,
        name: str,
        description: str,
        label_names: Optional[List[str]] = None,
        buckets: Tuple[float, ...] = DEFAULT_BUCKETS,
    ) -> Histogram:
        with self._lock:
            if name not in self._metrics:
                self._metrics[name] = Histogram(name, description, label_names, buckets)
            return self._metrics[name]  # type: ignore

    def collect_system_metrics(self):
        """Samples hardware performance metrics safely with graceful CPU-only fallback."""
        try:
            if psutil is not None:
                cpu_percent = psutil.cpu_percent(interval=None)
                self.system_cpu_usage.set(cpu_percent)

                mem = psutil.virtual_memory()
                self.system_memory_usage.set(mem.used)
            else:
                self.system_cpu_usage.set(0.0)
                self.system_memory_usage.set(0.0)

            # GPU Check
            if torch is not None and torch.cuda.is_available():
                for i in range(torch.cuda.device_count()):
                    # Memory usage ratio as GPU proxy
                    allocated = torch.cuda.memory_allocated(i)
                    total = torch.cuda.get_device_properties(i).total_memory
                    gpu_util = (allocated / total) * 100.0 if total > 0 else 0.0
                    self.system_gpu_usage.set(gpu_util, {"gpu_index": str(i)})
            else:
                self.system_gpu_usage.set(0.0, {"gpu_index": "none"})
        except Exception:
            pass

    def render_prometheus_text(self) -> str:
        """Renders complete registry in official Prometheus v0.0.4 text format."""
        self.collect_system_metrics()
        lines: List[str] = []
        with self._lock:
            for metric in self._metrics.values():
                lines.extend(metric.render())
                lines.append("")
        return "\n".join(lines)


# Global singleton registry
metrics_registry = MetricsRegistry()
