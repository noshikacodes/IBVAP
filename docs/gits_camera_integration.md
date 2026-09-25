# IBVAP Live Public CCTV Integration Guide: GITS Camera 95366
**Camera**: [세종]운학터널(세종)-13|13 (Sejong-Pocheon Expressway Wunhak Tunnel, South Korea)  
**Provider**: 한국도로공사 (Korea Expressway Corporation) / Gyeonggi Intelligent Transport Systems (GITS)  
**GITS CCTV ID**: `95366`

---

## 1. Source URLs & Endpoints

### Official Web Portals
- **Official GITS Popup Page**:
  ```
  https://gits.gg.go.kr/web/popup/webCctvPopup.do?cctvId=95366
  ```
- **TrafficVision Live Cam Page**:
  ```
  https://trafficvision.live/?continent=Asia&camera=gits-95366
  ```

### Dynamic Stream Resolver Endpoint
The GITS web page issues an asynchronous HTTP GET request to:
```
http://gitsview.gg.go.kr/95366/<session_token>!hls
```
This endpoint dynamically returns the signed live HLS playlist URL.

### Active Public Stream Endpoint (HLS)
The resolved public stream endpoint follows this structure:
```
http://gitsview.gg.go.kr:8081/ex023/ex000000ggrh00000000000000TC0290824SD/playlist.m3u8?wmsAuthSign=<BASE64_TOKEN>
```
- **Token Format (`wmsAuthSign`)**: Base64 encoded query string containing:
  - `server_time`: Timestamp of token issuance (e.g. `9/1/2026 8:31:02 AM`)
  - `hash_value`: Cryptographic signature
  - `validminutes`: `120` (Token validity duration is 2 hours)
  - `id`: Stream identifier (`gyunggi#gg123live#95366`)
- **Sub-stream Variant**: `main_stream.m3u8`
- **Video Segments**: `3685322d07aa_main_seg<INDEX>.ts` (~2.0 seconds per segment)
- **CORS**: `Access-Control-Allow-Origin: *` is enabled on all playlists and TS segments.

---

## 2. Stream Protocol & Technical Specifications

| Parameter | Specification | Details / Measurements |
| :--- | :--- | :--- |
| **Stream Protocol** | **HLS (HTTP Live Streaming)** | Multi-variant `.m3u8` with MPEG-TS (`.ts`) segments |
| **Media Server Engine** | **Nimble Streamer (WMS)** | Reverse-proxied by Nginx at port `8081` |
| **Video Codec** | **H.264 / AVC** | High Profile, Level 3.0, `yuvj420p` (progressive) |
| **Stream Dimensions** | **720 x 480 (SD)** | 3:2 NTSC aspect ratio |
| **Nominal Framerate** | **30.0 FPS** | 60 packets per ~1.97s segment |
| **Average Bitrate** | **~1,070 kbps** | ~1.07 Mbps bandwidth consumption |
| **Audio Availability** | **None** | Pure video feed (no audio elementary stream) |
| **Approximate Latency** | **6 – 12 seconds** | Standard HLS window (3–5 segments buffered) |
| **Direct FFmpeg Consumption** | **YES** | Native support with standard `hls` demuxer |
| **Direct OpenCV Consumption** | **YES** | Native support via `cv2.VideoCapture(url, cv2.CAP_FFMPEG)` |

---

## 3. FFmpeg Commands

### A. Probe Stream Metadata (ffprobe)
```bash
ffprobe -v error -show_format -show_streams -print_format json "<RESOLVED_M3U8_URL>"
```

### B. Validate Frame Decoding (Decode 30 frames without saving)
```bash
ffmpeg -hide_banner -loglevel info -i "<RESOLVED_M3U8_URL>" -vframes 30 -f null -
```

### C. Transcode / Relay Stream to Local RTSP (MediaMTX)
Because the input is already encoded in H.264, FFmpeg can perform low-overhead stream passthrough using `-c:v copy`:
```bash
ffmpeg -hide_banner -loglevel error \
  -i "<RESOLVED_M3U8_URL>" \
  -c:v copy \
  -an \
  -f rtsp \
  -rtsp_transport tcp \
  rtsp://127.0.0.1:8554/ibvap-cam01
```

---

## 4. Python / OpenCV Code

### Minimal Standalone Consumer with Auto-Reconnection
```python
import os
import cv2
from ai_engine.pipeline.gits_resolver import resolve_gits_hls_url

# 1. Resolve fresh signed HLS URL
cctv_id = "95366"
stream_url, metadata = resolve_gits_hls_url(cctv_id)
print(f"Streaming from: {stream_url} (Valid {metadata.get('valid_minutes')} mins)")

# 2. Configure capture options
os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "timeout;5000000"
cap = cv2.VideoCapture(stream_url, cv2.CAP_FFMPEG)

frames_read = 0
try:
    while cap.isOpened() and frames_read < 30:
        ret, frame = cap.read()
        if not ret or frame is None:
            print("Stream interrupted. Re-resolving token and reconnecting...")
            cap.release()
            stream_url, _ = resolve_gits_hls_url(cctv_id)
            cap = cv2.VideoCapture(stream_url, cv2.CAP_FFMPEG)
            continue

        frames_read += 1
        h, w = frame.shape[:2]
        print(f"Received frame {frames_read}: {w}x{h}")
finally:
    cap.release()
```

---

## 5. Required Dependencies

The integration relies purely on standard library and existing IBVAP dependencies:
- **Python**: 3.10+
- **OpenCV**: `opencv-python>=4.8.0` (compiled with FFmpeg support, included in `.venv`)
- **NumPy**: `numpy>=1.24.0`
- **FFmpeg / ffprobe**: (optional, for CLI inspection and MediaMTX relay)

No external proprietary SDKs or credentials are required.

---

## 6. How to Start the IBVAP Live-Camera Pipeline

### Option 1: Run the Standalone Verification Script
Run the automated connectivity test (consumes 30 frames, logs telemetry, saves snapshot):
```bash
python scripts/test_gits_stream.py --cctv-id 95366 --frames 30
```
To test the automatic reconnection watchdog under simulated failure:
```bash
python scripts/test_gits_stream.py --cctv-id 95366 --frames 20 --simulate-reconnect
```

### Option 2: Run a Single Dedicated AI Engine Worker
Process the live CCTV camera through YOLOv8 object detection, ByteTrack tracking, and live video HUD:
```bash
python -m ai_engine.worker \
  --input "https://gits.gg.go.kr/web/popup/webCctvPopup.do?cctvId=95366" \
  --camera-id "CAM_SEJONG_95366" \
  --model "yolov8n.pt" \
  --skip-frames 2 \
  --output "mock_streams/output_gits_annotated.mp4"
```
*(Alternatively, `--input 95366` or `--input gits://95366` is supported directly).*

### Option 3: Run the Multi-Camera AI Supervisor (Production Daemon)
Start the multi-stream worker supervisor to run all configured streams in `mock_streams/streams.json` (including `CAM_SEJONG_95366`):
```bash
python -m ai_engine.stream_manager --config mock_streams/streams.json --interval 2.0
```

### Option 4: Full Multi-Service Docker Stack
```bash
docker compose up -d
```

---

## 7. Limitations & Licensing Considerations

1. **Session Expiration (120-Minute Token)**:
   - The GITS media server enforces token expiration every 120 minutes via `validminutes=120`.
   - **Mitigation**: `ai_engine.pipeline.gits_resolver` and `VideoReader` automatically catch stream stalls or disconnections and fetch a renewed signed token upon reconnection without restarting the AI pipeline.
2. **HLS Inherent Latency**:
   - Because HLS operates in discrete segments (~2-3 seconds per chunk with 3 segments buffered), the live stream is approximately 6 to 12 seconds delayed compared to wall-clock real time.
   - For real-time low-latency PTZ tracking, an RTSP or WebRTC feed is preferred; for border / traffic perimeter intrusion monitoring, this latency is within acceptable operational tolerance.
3. **Bandwidth & Rate Limiting**:
   - Bandwidth consumption is approximately 1.07 Mbps per active worker.
   - Reconnections should maintain exponential backoff (starting at 2.0s up to 10.0s) to avoid being rate-limited by GITS edge firewalls.
4. **Public Usage & Licensing**:
   - Source data is publicly provided by 한국도로공사 (Korea Expressway Corporation) and 경기도교통정보센터 (GITS) for public traffic and road condition monitoring.
   - Streams are strictly for observation, analytics, and safety monitoring. Commercial redistribution of raw footage without attribution may require formal licensing agreements with GITS.
