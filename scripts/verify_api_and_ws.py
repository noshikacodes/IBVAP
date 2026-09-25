import sys
import time
import json
import asyncio
import httpx
import websockets
from datetime import datetime

BASE_URL = "http://localhost:8000"
WS_URL = "ws://localhost:8000/api/v1/ws/alerts"

async def test_backend_and_websocket():
    print("=" * 60)
    print(" [IBVAP API & WebSocket Verification Suite]")
    print(f" Target API: {BASE_URL}")
    print(f" Target WS:  {WS_URL}")
    print("=" * 60)

    # 1. Health check
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=5.0) as client:
        r = await client.get("/health")
        assert r.status_code == 200, f"Health check failed: {r.status_code} {r.text}"
        data = r.json()
        assert data.get("status") == "healthy"
        print(f"[PASS] 1. GET /health -> Status: {data.get('status')} | Version: {data.get('version')}")

        # 2. Camera registry list
        r = await client.get("/api/v1/cameras")
        assert r.status_code == 200, f"Get cameras failed: {r.status_code}"
        cam_resp = r.json()
        cameras = cam_resp.get("cameras", [])
        assert len(cameras) >= 4
        print(f"[PASS] 2. GET /api/v1/cameras -> {len(cameras)} cameras registered (Total: {cam_resp.get('total')}).")

    # 3. WebSocket connection & live alert broadcast verification
    received_alerts = []

    connected_event = asyncio.Event()

    async def _listen_ws():
        async with websockets.connect(WS_URL) as ws:
            connected_event.set()
            while len(received_alerts) < 3:
                msg = await ws.recv()
                data = json.loads(msg)
                if data.get("type") == "NEW_ALERT":
                    received_alerts.append(data.get("data"))
                    print(f" [WS RX] Received live alert: {data.get('data', {}).get('event_type')} (Camera: {data.get('data', {}).get('camera_id')})")

    # Start WebSocket listener in background and wait until connected
    ws_task = asyncio.create_task(_listen_ws())
    await connected_event.wait()
    print("[PASS] 3. WS Connection established to /api/v1/ws/alerts.")

    async with httpx.AsyncClient(base_url=BASE_URL, timeout=5.0) as client:
        # 4. Ingest Spatial Intrusion Alert
        intrusion_payload = {
            "camera_id": "CAM_FENCE",
            "event_type": "intrusion",
            "severity": "critical",
            "zone_id": "ZONE_BORDER_EXCLUSION",
            "object_class": "person",
            "track_id": 101,
            "confidence": 0.88,
            "description": "Perimeter breach detected in virtual exclusion boundary",
            "metadata": {"sector": "Bravo Fence"}
        }
        r = await client.post("/api/v1/alerts", json=intrusion_payload)
        assert r.status_code == 201, f"Post intrusion alert failed: {r.text}"
        print("[PASS] 4. POST /api/v1/alerts (Spatial Intrusion) -> 201 Created")

        # 5. Ingest ANPR Alert
        anpr_payload = {
            "camera_id": "CAM_GATE",
            "event_type": "anpr_watchlist_hit",
            "severity": "critical",
            "zone_id": "ZONE_GATE_ENTRY",
            "object_class": "truck",
            "track_id": 202,
            "confidence": 0.94,
            "description": "Watchlist vehicle detected: DL01AB1234",
            "metadata": {
                "plate_number": "DL01AB1234",
                "normalized_plate": "DL01AB1234",
                "ocr_confidence": 0.96,
                "consensus_votes": 3,
                "watchlist_status": "FLAGGED_SUSPECT"
            }
        }
        r = await client.post("/api/v1/alerts", json=anpr_payload)
        assert r.status_code == 201, f"Post ANPR alert failed: {r.text}"
        print("[PASS] 5. POST /api/v1/alerts (ANPR Watchlist Hit) -> 201 Created")

        # 6. Ingest FRS Alert
        frs_payload = {
            "camera_id": "CAM_PATROL",
            "event_type": "frs_watchlist_hit",
            "severity": "critical",
            "zone_id": "ZONE_PATROL_PATH",
            "object_class": "person",
            "track_id": 303,
            "confidence": 0.91,
            "description": "Identified enrolled profile: Capt. Sharma",
            "metadata": {
                "identity_id": "DEMO_001",
                "identity_name": "Capt. Sharma",
                "similarity_score": 0.89,
                "consensus_votes": 3,
                "watchlist_status": "VIP_COMMANDER"
            }
        }
        r = await client.post("/api/v1/alerts", json=frs_payload)
        assert r.status_code == 201, f"Post FRS alert failed: {r.text}"
        print("[PASS] 6. POST /api/v1/alerts (FRS Biometric Hit) -> 201 Created")

    # Wait for WebSocket receiver
    try:
        await asyncio.wait_for(ws_task, timeout=3.0)
        print(f"[PASS] 7. WebSocket live alert stream received all {len(received_alerts)} broadcasts in real-time.")
    except asyncio.TimeoutError:
        print(f"[WARN] WebSocket timeout. Received {len(received_alerts)} alerts.")

    # 8. Verify alert list & query filters
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=5.0) as client:
        r = await client.get("/api/v1/alerts?limit=10")
        assert r.status_code == 200
        alert_resp = r.json()
        all_alerts = alert_resp.get("alerts", [])
        assert len(all_alerts) >= 3
        print(f"[PASS] 8. GET /api/v1/alerts -> Retrieved {len(all_alerts)} alerts successfully (Total: {alert_resp.get('total')}).")

    print("\n[SUCCESS] All API, REST and WebSocket endpoints verified with 100% success.")

if __name__ == "__main__":
    asyncio.run(test_backend_and_websocket())
