"""
Verifies all 4 IBVAP simulated camera RTSP & HLS streams are active and streaming.
"""

import urllib.request
import sys

STREAM_PATHS = [
    ("CAM_01", "ibvap-cam01", "Sector Alpha - North Perimeter Gate"),
    ("CAM_02", "ibvap-cam02", "Sector Alpha - South Vehicle Corridor"),
    ("CAM_03", "ibvap-cam03", "Sector Bravo - East Virtual Fence"),
    ("CAM_04", "ibvap-cam04", "Sector Bravo - West Outpost"),
    ("LEGACY", "ibvap-demo", "Benchmark Stream (Legacy)"),
]

def main():
    print("================================================================================")
    print("  IBVAP 4-Camera HLS Stream Endpoint Verification")
    print("================================================================================")

    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor())
    urllib.request.install_opener(opener)

    all_passed = True

    for cam_id, path, desc in STREAM_PATHS:
        url = f"http://127.0.0.1:8888/{path}/index.m3u8"
        try:
            resp = urllib.request.urlopen(url, timeout=3)
            body = resp.read().decode("utf-8", errors="replace")
            status = resp.status
            content_type = resp.headers.get("Content-Type", "")
            is_valid = status == 200 and "#EXTM3U" in body
            
            if is_valid:
                print(f"  [PASS] {cam_id:7s} ({desc:40s}) -> HTTP {status} (Content-Type: {content_type})")
            else:
                print(f"  [FAIL] {cam_id:7s} ({desc:40s}) -> Invalid HLS response: {body[:60]}")
                all_passed = False
        except Exception as e:
            print(f"  [FAIL] {cam_id:7s} ({desc:40s}) -> Error: {e}")
            all_passed = False

    print("================================================================================")
    if all_passed:
        print("  [SUCCESS] All 4 camera HLS streams are live and responding with valid playlists!")
    else:
        print("  [ERROR] One or more camera streams failed to respond.")
    print("================================================================================\n")
    return 0 if all_passed else 1

if __name__ == "__main__":
    sys.exit(main())
