"""
IBVAP Local RTSP Video Stream Publisher (Development Utility)

Publishes an MP4 video (or loops a benchmark video) to a local MediaMTX RTSP relay server
to simulate real-time IP CCTV cameras for software-defined ingestion.
"""

import sys
import os
import glob
import argparse
import subprocess
import shutil


def find_ffmpeg_executable() -> str:
    """Finds ffmpeg executable from PATH or WinGet packages."""
    cmd = shutil.which("ffmpeg")
    if cmd:
        return cmd

    # Check Windows WinGet package location
    local_app_data = os.environ.get("LOCALAPPDATA", "")
    if local_app_data:
        pattern = os.path.join(
            local_app_data,
            "Microsoft", "WinGet", "Packages",
            "*FFmpeg*", "**", "ffmpeg.exe"
        )
        matches = glob.glob(pattern, recursive=True)
        if matches and os.path.exists(matches[0]):
            return matches[0]

    return "ffmpeg"


def parse_args():
    parser = argparse.ArgumentParser(
        description="Publish local video file to MediaMTX as an RTSP stream in a loop."
    )
    parser.add_argument(
        "-i", "--input",
        default="mock_streams/sample_patrol.mp4",
        help="Path to video file to stream (default: mock_streams/sample_patrol.mp4)"
    )
    parser.add_argument(
        "-u", "--url",
        default="rtsp://localhost:8554/ibvap-demo",
        help="Target MediaMTX RTSP stream URL (default: rtsp://localhost:8554/ibvap-demo)"
    )
    parser.add_argument(
        "--fps",
        type=int,
        default=15,
        help="Target stream frame rate (default: 15)"
    )
    parser.add_argument(
        "--loop",
        action="store_true",
        default=True,
        help="Loop video indefinitely (default: True)"
    )
    return parser.parse_args()


def main():
    args = parse_args()
    input_path = os.path.abspath(args.input)
    ffmpeg_exe = find_ffmpeg_executable()

    if not os.path.exists(input_path):
        print(f"[ERROR] Source video file not found: {input_path}", file=sys.stderr)
        return 1

    print("==================================================")
    print(" [IBVAP Stream Publisher] MediaMTX RTSP Relay")
    print("==================================================")
    print(f" Source Video:   {input_path}")
    print(f" RTSP Target:    {args.url}")
    print(f" Target FPS:     {args.fps}")
    print(f" FFmpeg Binary:  {ffmpeg_exe}")
    print(f" Looping:        {'Enabled' if args.loop else 'Disabled'}")
    print("==================================================\n")

    ffmpeg_cmd = [
        ffmpeg_exe,
        "-re",  # Read input at native frame rate
    ]
    if args.loop:
        ffmpeg_cmd.extend(["-stream_loop", "-1"])

    ffmpeg_cmd.extend([
        "-i", input_path,
        "-c:v", "libx264",
        "-preset", "ultrafast",
        "-tune", "zerolatency",
        "-pix_fmt", "yuv420p",
        "-r", str(args.fps),
        "-f", "rtsp",
        "-rtsp_transport", "tcp",
        args.url
    ])

    cmd_str = " ".join(ffmpeg_cmd)
    print("Executing stream publishing command:")
    print(f"  {cmd_str}\n")

    try:
        proc = subprocess.run(ffmpeg_cmd)
        return proc.returncode
    except FileNotFoundError:
        print(f"[ERROR] '{ffmpeg_exe}' executable not found.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
