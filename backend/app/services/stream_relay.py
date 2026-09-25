"""
IBVAP Stream Relay Manager
Dynamically manages RTSP stream relays between local synthetic demo loops
and external real IP/RTSP cameras for the 4 surveillance camera slots.
"""

import os
import sys
import shutil
import glob
import time
import subprocess
import threading
import logging
from typing import Dict, Optional, Any
from urllib.parse import urlparse

try:
    from ai_engine.pipeline.gits_resolver import is_gits_source, resolve_gits_hls_url
except ImportError:
    is_gits_source = lambda s: False
    resolve_gits_hls_url = None

logger = logging.getLogger("ibvap.stream_relay")

# Map of slot IDs to local MediaMTX paths and default demo video files
SLOT_CONFIGS = {
    "CAM_01": {"path": "ibvap-cam01", "demo_video": "mock_streams/cam01_gate.mp4"},
    "CAM_02": {"path": "ibvap-cam02", "demo_video": "mock_streams/cam02_corridor.mp4"},
    "CAM_03": {"path": "ibvap-cam03", "demo_video": "mock_streams/cam03_fence.mp4"},
    "CAM_04": {"path": "ibvap-cam04", "demo_video": "mock_streams/cam04_outpost.mp4"},
}


def normalize_slot_id(camera_id: str) -> Optional[str]:
    """Normalizes any camera ID format (CAM_01, CAM01, cam_01, CAMGATE, etc.) to canonical slot key."""
    if not camera_id:
        return None
    raw = camera_id.upper().strip()
    if raw in SLOT_CONFIGS:
        return raw
    clean = raw.replace("_", "").replace("-", "")
    if "01" in clean or clean == "CAM1" or clean == "CAMGATE":
        return "CAM_01"
    if "02" in clean or clean == "CAM2" or clean == "CAMPATROL":
        return "CAM_02"
    if "03" in clean or clean == "CAM3" or clean == "CAMFENCE":
        return "CAM_03"
    if "04" in clean or clean == "CAM4" or clean == "CAMOUTPOST04" or clean == "CAMOUTPOST":
        return "CAM_04"
    return None


def find_ffmpeg_executable() -> str:
    cmd = shutil.which("ffmpeg")
    if cmd:
        return cmd
    local_app_data = os.environ.get("LOCALAPPDATA", "")
    if local_app_data:
        matches = glob.glob(
            os.path.join(local_app_data, "Microsoft", "WinGet", "Packages", "*FFmpeg*", "**", "ffmpeg.exe"),
            recursive=True
        )
        if matches and os.path.exists(matches[0]):
            return matches[0]
    return "ffmpeg.exe"


def find_ffprobe_executable() -> str:
    cmd = shutil.which("ffprobe")
    if cmd:
        return cmd
    local_app_data = os.environ.get("LOCALAPPDATA", "")
    if local_app_data:
        matches = glob.glob(
            os.path.join(local_app_data, "Microsoft", "WinGet", "Packages", "*FFmpeg*", "**", "ffprobe.exe"),
            recursive=True
        )
        if matches and os.path.exists(matches[0]):
            return matches[0]
    ffmpeg_cmd = find_ffmpeg_executable()
    if os.path.isabs(ffmpeg_cmd):
        probe_path = os.path.join(os.path.dirname(ffmpeg_cmd), "ffprobe.exe" if os.name == "nt" else "ffprobe")
        if os.path.exists(probe_path):
            return probe_path
    return "ffprobe.exe"


def mask_rtsp_url(url: str) -> str:
    """Masks username and password in RTSP URL for safe logging/display."""
    if not url:
        return ""
    try:
        parsed = urlparse(url)
        if parsed.password or parsed.username:
            netloc = parsed.netloc
            user_info = ""
            if "@" in netloc:
                user_info, host_info = netloc.split("@", 1)
                masked_user_info = "***:***" if ":" in user_info else "***"
                netloc = f"{masked_user_info}@{host_info}"
            return parsed._replace(netloc=netloc).geturl()
    except Exception:
        pass
    return url


class StreamRelayManager:
    """
    Thread-safe supervisor for camera stream relays.
    Maintains active FFmpeg processes per camera slot.
    """

    def __init__(self):
        self._processes: Dict[str, subprocess.Popen] = {}
        self._slot_modes: Dict[str, str] = {slot: "simulated" for slot in SLOT_CONFIGS}
        self._lock = threading.Lock()
        self._ffmpeg_exe = find_ffmpeg_executable()
        self._ffprobe_exe = find_ffprobe_executable()

    def get_slot_mode(self, camera_id: str) -> str:
        norm_id = normalize_slot_id(camera_id) or camera_id
        with self._lock:
            return self._slot_modes.get(norm_id, "simulated")

    def start_demo_relay(self, camera_id: str) -> bool:
        """Starts looping synthetic demo video for the given camera slot."""
        norm_id = normalize_slot_id(camera_id)
        if not norm_id or norm_id not in SLOT_CONFIGS:
            return False

        cfg = SLOT_CONFIGS[norm_id]
        video_path = os.path.abspath(cfg["demo_video"])
        rtsp_target = f"rtsp://127.0.0.1:8554/{cfg['path']}"

        if not os.path.exists(video_path):
            # Try to generate demo streams if missing
            try:
                from mock_streams.generate_demo_streams import main as gen_main
                gen_main()
            except Exception as e:
                logger.error(f"Failed to generate demo streams: {e}")

        with self._lock:
            self._stop_slot_process(norm_id)

            cmd = [
                self._ffmpeg_exe,
                "-hide_banner",
                "-loglevel", "error",
                "-re",
                "-stream_loop", "-1",
                "-i", video_path,
                "-c:v", "libx264",
                "-preset", "ultrafast",
                "-tune", "zerolatency",
                "-pix_fmt", "yuv420p",
                "-r", "15",
                "-an",
                "-f", "rtsp",
                "-rtsp_transport", "tcp",
                rtsp_target
            ]

            try:
                proc = subprocess.Popen(cmd)
                self._processes[norm_id] = proc
                self._slot_modes[norm_id] = "simulated"
                logger.info(f"[{norm_id}] Started synthetic demo relay -> {rtsp_target}")
                return True
            except Exception as e:
                logger.error(f"[{norm_id}] Failed to start demo relay: {e}")
                return False

    def start_real_camera_relay(
        self,
        camera_id: str,
        rtsp_url: str,
        username: Optional[str] = None,
        password: Optional[str] = None
    ) -> bool:
        """
        Connects to a remote real IP camera/phone RTSP source and relays it
        to the local MediaMTX slot path (e.g. /ibvap-cam01).
        """
        norm_id = normalize_slot_id(camera_id)
        if not norm_id or norm_id not in SLOT_CONFIGS:
            return False

        cfg = SLOT_CONFIGS[norm_id]
        rtsp_target = f"rtsp://127.0.0.1:8554/{cfg['path']}"

        clean_url = rtsp_url.strip() if rtsp_url else ""
        if not clean_url:
            return False

        # Check if source is GITS camera or HLS stream
        is_gits = is_gits_source(clean_url)
        if is_gits and resolve_gits_hls_url:
            try:
                resolved_url, _ = resolve_gits_hls_url(clean_url)
                clean_url = resolved_url
            except Exception as e:
                logger.error(f"[{norm_id}] Failed to resolve GITS stream: {e}")
                return False

        parsed = urlparse(clean_url)
        scheme = (parsed.scheme or "").lower()
        is_hls = ".m3u8" in clean_url.lower()

        if not is_hls and scheme not in ("rtsp", "rtsps", "http", "https"):
            logger.warning(f"[{norm_id}] Rejected relay request with invalid scheme: {scheme}")
            return False

        # Reject bare HTTP web UI addresses without a stream path
        if scheme in ("http", "https") and not is_hls and (not parsed.path or parsed.path in ("/", "")):
            logger.warning(f"[{norm_id}] Rejected bare HTTP UI address: {clean_url}")
            return False

        # Inject credentials into RTSP URL if supplied separately
        full_source_url = clean_url
        if username and password and "@" not in clean_url and parsed.netloc:
            netloc = f"{username}:{password}@{parsed.netloc}"
            full_source_url = parsed._replace(netloc=netloc).geturl()

        masked = mask_rtsp_url(full_source_url)
        logger.info(f"[{norm_id}] Initiating real camera relay: {masked} -> {rtsp_target}")

        with self._lock:
            self._stop_slot_process(norm_id)

            # Build FFmpeg command depending on source scheme
            if scheme in ("rtsp", "rtsps") or is_hls:
                cmd = [
                    self._ffmpeg_exe,
                    "-hide_banner",
                    "-loglevel", "error",
                ]
                if not is_hls and scheme in ("rtsp", "rtsps"):
                    cmd.extend(["-rtsp_transport", "tcp"])
                cmd.extend([
                    "-i", full_source_url,
                    "-c:v", "copy",  # Fast zero-reencoding passthrough for standard H.264 RTSP & HLS
                    "-an",
                    "-f", "rtsp",
                    "-rtsp_transport", "tcp",
                    rtsp_target
                ])
            else:
                # HTTP MJPEG or video stream input -> transcode to H.264 for MediaMTX
                cmd = [
                    self._ffmpeg_exe,
                    "-hide_banner",
                    "-loglevel", "error",
                    "-i", full_source_url,
                    "-c:v", "libx264",
                    "-preset", "ultrafast",
                    "-tune", "zerolatency",
                    "-pix_fmt", "yuv420p",
                    "-r", "15",
                    "-an",
                    "-f", "rtsp",
                    "-rtsp_transport", "tcp",
                    rtsp_target
                ]

            try:
                proc = subprocess.Popen(cmd)
                self._processes[norm_id] = proc
                self._slot_modes[norm_id] = "real"
                logger.info(f"[{norm_id}] Real camera relay active ({proc.pid}) -> {rtsp_target}")
                return True
            except Exception as e:
                logger.error(f"[{norm_id}] Failed to start real camera relay: {e}")
                return False

    def _stop_slot_process(self, camera_id: str) -> None:
        """Stops active process for a camera slot."""
        proc = self._processes.get(camera_id)
        if proc:
            try:
                proc.terminate()
                proc.wait(timeout=1.5)
            except Exception:
                try:
                    proc.kill()
                    proc.wait(timeout=1.0)
                except Exception:
                    pass
            self._processes.pop(camera_id, None)

    def stop_all(self) -> None:
        """Stops all active FFmpeg processes across all slots cleanly."""
        with self._lock:
            for slot in list(self._processes.keys()):
                self._stop_slot_process(slot)

    def test_rtsp_connection(
        self,
        rtsp_url: str,
        username: Optional[str] = None,
        password: Optional[str] = None,
        timeout_seconds: float = 3.0
    ) -> Dict[str, Any]:
        """
        Tests connection to an external RTSP stream using ffprobe.
        Measures latency, resolution, FPS, and codec without hanging.
        """
        clean_url = rtsp_url.strip() if rtsp_url else ""
        if not clean_url:
            return {
                "reachable": False,
                "status": "error",
                "protocol": "RTSP",
                "error_reason": "No stream URL provided."
            }

        # Check if source is GITS camera or HLS stream
        is_gits = is_gits_source(clean_url)
        if is_gits and resolve_gits_hls_url:
            try:
                resolved_url, meta = resolve_gits_hls_url(clean_url)
                clean_url = resolved_url
            except Exception as e:
                return {
                    "reachable": False,
                    "status": "error",
                    "protocol": "HLS",
                    "latency_ms": None,
                    "masked_url": mask_rtsp_url(clean_url),
                    "error_reason": f"Failed to resolve GITS camera stream: {e}"
                }

        parsed = urlparse(clean_url)
        scheme = (parsed.scheme or "").lower()
        is_hls = ".m3u8" in clean_url.lower()

        # Reject HTTP / HTTPS addresses or non-RTSP URLs if not HLS
        if scheme in ("http", "https") and not is_hls:
            return {
                "reachable": False,
                "status": "error",
                "protocol": "HTTP",
                "latency_ms": None,
                "masked_url": mask_rtsp_url(clean_url),
                "error_reason": (
                    "HTTP Web UI address detected (not an RTSP or HLS stream). "
                    "Do NOT enter http://PHONE_IP:8080. "
                    "For Android IP Webcam app, use rtsp://PHONE_IP:8080/h264_pcm.sdp or rtsp://PHONE_IP:8080/h264_ulaw.sdp."
                )
            }

        if not is_hls and scheme not in ("rtsp", "rtsps"):
            return {
                "reachable": False,
                "status": "error",
                "protocol": scheme.upper() if scheme else "UNKNOWN",
                "error_reason": "Invalid URL scheme: stream protocol must start with rtsp://, rtsps://, or be an HLS stream (.m3u8/GITS)"
            }

        full_source_url = clean_url
        if username and password and "@" not in clean_url and parsed.netloc:
            netloc = f"{username}:{password}@{parsed.netloc}"
            full_source_url = parsed._replace(netloc=netloc).geturl()

        masked = mask_rtsp_url(full_source_url)
        start_t = time.perf_counter()

        probe_timeout_us = str(int(timeout_seconds * 1000000))
        probe_cmd = [
            self._ffprobe_exe,
            "-v", "error",
        ]
        if not is_hls and scheme in ("rtsp", "rtsps"):
            probe_cmd.extend(["-rtsp_transport", "tcp"])
        probe_cmd.extend([
            "-timeout", probe_timeout_us,
            "-analyzeduration", "1000000",
            "-probesize", "1000000",
            "-select_streams", "v:0",
            "-show_entries", "stream=width,height,codec_name,r_frame_rate",
            "-of", "default=noprint_wrappers=1:nokey=0",
            full_source_url
        ])

        try:
            proc = subprocess.run(
                probe_cmd,
                capture_output=True,
                text=True,
                timeout=timeout_seconds + 0.5
            )
            elapsed_ms = round((time.perf_counter() - start_t) * 1000, 1)

            if proc.returncode == 0 and proc.stdout:
                output = proc.stdout
                width, height, codec, fps = None, None, None, None
                for line in output.splitlines():
                    if line.startswith("width="):
                        try:
                            width = int(line.split("=")[1])
                        except Exception:
                            pass
                    elif line.startswith("height="):
                        try:
                            height = int(line.split("=")[1])
                        except Exception:
                            pass
                    elif line.startswith("codec_name="):
                        codec = line.split("=")[1].strip()
                    elif line.startswith("r_frame_rate="):
                        rate_str = line.split("=")[1].strip()
                        if "/" in rate_str:
                            try:
                                num, den = rate_str.split("/")
                                fps = round(float(num) / max(float(den), 1.0), 1)
                            except Exception:
                                pass

                # Valid video stream confirmed
                if width and height and codec:
                    return {
                        "reachable": True,
                        "status": "online",
                        "protocol": scheme.upper(),
                        "codec": codec,
                        "resolution": f"{width}x{height}",
                        "fps": fps or 30.0,
                        "latency_ms": elapsed_ms,
                        "relay_status": "ACTIVE",
                        "hls_status": "READY",
                        "masked_url": masked,
                        "error_reason": None
                    }
                else:
                    return {
                        "reachable": False,
                        "status": "offline",
                        "protocol": scheme.upper(),
                        "latency_ms": elapsed_ms,
                        "masked_url": masked,
                        "error_reason": "No video stream detected in probe response."
                    }
            else:
                err_msg = proc.stderr.strip() if proc.stderr else "Stream unreachable or codec unknown"
                # Strip raw passwords/credentials from error output if present
                if password:
                    err_msg = err_msg.replace(password, "***")
                if username:
                    err_msg = err_msg.replace(username, "***")

                # Categorize error reason clearly
                err_lower = err_msg.lower()
                if "connection refused" in err_lower or "10061" in err_lower:
                    reason = "Phone RTSP endpoint is unreachable from this machine (connection refused: target IP or port unreachable)."
                elif "401" in err_lower or "unauthorized" in err_lower or "authentication" in err_lower:
                    reason = "RTSP authentication failed: Invalid username or password."
                elif "404" in err_lower or "not found" in err_lower:
                    reason = "Stream path not found on camera (for IP Webcam, verify endpoint: /h264_pcm.sdp or /h264_ulaw.sdp)."
                elif "server returned 400" in err_lower:
                    reason = "Bad request: Target device rejected the RTSP connection."
                elif "invalid data found" in err_lower:
                    reason = "Invalid stream data: Target endpoint does not output a valid video stream."
                else:
                    reason = err_msg[:180] or "Phone RTSP endpoint is unreachable from this machine."

                return {
                    "reachable": False,
                    "status": "offline",
                    "protocol": scheme.upper(),
                    "latency_ms": elapsed_ms,
                    "masked_url": masked,
                    "error_reason": reason
                }
        except subprocess.TimeoutExpired:
            elapsed_ms = round((time.perf_counter() - start_t) * 1000, 1)
            return {
                "reachable": False,
                "status": "offline",
                "protocol": scheme.upper() if scheme else "RTSP",
                "latency_ms": elapsed_ms,
                "masked_url": masked,
                "error_reason": f"Phone RTSP endpoint is unreachable from this machine (connection timed out after {timeout_seconds}s)."
            }
        except Exception as e:
            return {
                "reachable": False,
                "status": "error",
                "protocol": scheme.upper() if scheme else "RTSP",
                "masked_url": masked,
                "error_reason": str(e)[:180]
            }


# Global singleton instance
stream_relay_manager = StreamRelayManager()

import atexit
atexit.register(stream_relay_manager.stop_all)

