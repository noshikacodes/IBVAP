"""
IBVAP Multi-Stream Publisher Supervisor (Local Demo)
Launches and monitors 4 independent FFmpeg RTSP publishers in real-time loops:
- CAM_01 -> rtsp://localhost:8554/ibvap-cam01
- CAM_02 -> rtsp://localhost:8554/ibvap-cam02
- CAM_03 -> rtsp://localhost:8554/ibvap-cam03
- CAM_04 -> rtsp://localhost:8554/ibvap-cam04
- LEGACY -> rtsp://localhost:8554/ibvap-demo
"""

import sys
import os
sys.path.insert(0, os.path.abspath("."))
import time
import shutil
import glob
import subprocess
from typing import List, Dict


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


STREAM_SPECS = [
    {"cam": "CAM_01", "file": "mock_streams/cam01_gate.mp4", "path": "ibvap-cam01"},
    {"cam": "CAM_02", "file": "mock_streams/cam02_corridor.mp4", "path": "ibvap-cam02"},
    {"cam": "CAM_03", "file": "mock_streams/cam03_fence.mp4", "path": "ibvap-cam03"},
    {"cam": "CAM_04", "file": "mock_streams/cam04_outpost.mp4", "path": "ibvap-cam04"},
    {"cam": "LEGACY", "file": "mock_streams/sample_patrol.mp4", "path": "ibvap-demo"},
]


def start_publisher(ffmpeg_exe: str, spec: Dict[str, str]) -> subprocess.Popen:
    rtsp_url = f"rtsp://localhost:8554/{spec['path']}"
    cmd = [
        ffmpeg_exe,
        "-hide_banner",
        "-loglevel", "error",
        "-re",
        "-stream_loop", "-1",
        "-i", os.path.abspath(spec["file"]),
        "-c:v", "libx264",
        "-preset", "ultrafast",
        "-tune", "zerolatency",
        "-pix_fmt", "yuv420p",
        "-r", "15",
        "-f", "rtsp",
        "-rtsp_transport", "tcp",
        rtsp_url
    ]
    print(f"[{spec['cam']}] Starting stream publisher: {spec['file']} -> {rtsp_url}")
    return subprocess.Popen(cmd)


def main():
    ffmpeg_exe = find_ffmpeg_executable()
    print("==================================================")
    print(" IBVAP 4-Camera Tactical Stream Publisher Runner")
    print(f" FFmpeg Binary: {ffmpeg_exe}")
    print("==================================================")

    # Ensure all video files exist
    from mock_streams.generate_demo_streams import main as gen_main
    missing = any(not os.path.exists(s["file"]) for s in STREAM_SPECS)
    if missing:
        print("[!] Generating missing video files...")
        gen_main()

    processes: List[Dict] = []
    for spec in STREAM_SPECS:
        if os.path.exists(spec["file"]):
            proc = start_publisher(ffmpeg_exe, spec)
            processes.append({"spec": spec, "proc": proc})

    print(f"\n[OK] {len(processes)} RTSP stream publishers active and looping.\n")

    try:
        while True:
            time.sleep(2)
            for item in processes:
                proc = item["proc"]
                if proc.poll() is not None:
                    # Restart dead process
                    print(f"[RESTART] {item['spec']['cam']} exited ({proc.returncode}). Restarting...")
                    item["proc"] = start_publisher(ffmpeg_exe, item["spec"])
    except KeyboardInterrupt:
        print("\nStopping all stream publishers...")
        for item in processes:
            item["proc"].terminate()


if __name__ == "__main__":
    main()
