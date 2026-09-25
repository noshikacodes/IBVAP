import sys
import os
import urllib.request
import json

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


def test_metrics_endpoint():
    print("Testing GET http://127.0.0.1:8000/metrics ...")
    try:
        req = urllib.request.Request("http://127.0.0.1:8000/metrics")
        with urllib.request.urlopen(req, timeout=3.0) as resp:
            content_type = resp.headers.get("Content-Type", "")
            data = resp.read().decode("utf-8")
            status = resp.status

            print(f"Status Code: {status}")
            print(f"Content-Type: {content_type}")
            assert status == 200, f"Expected 200, got {status}"
            assert "version=0.0.4" in content_type, f"Unexpected Content-Type: {content_type}"
            assert "ibvap_http_requests_total" in data, "Missing ibvap_http_requests_total metric"
            assert "ibvap_system_cpu_usage_percent" in data, "Missing ibvap_system_cpu_usage_percent metric"
            assert "ibvap_camera_fps" in data, "Missing ibvap_camera_fps metric"
            print("Successfully verified /metrics endpoint content!\n")
            print("Sample metrics snippet:")
            for line in data.splitlines()[:20]:
                print(f"  {line}")
    except Exception as e:
        print(f"Direct localhost request error: {e}")
        # Test directly with FastAPI TestClient
        print("Testing via FastAPI TestClient fallback...")
        from fastapi.testclient import TestClient
        from backend.main import app
        client = TestClient(app)
        res = client.get("/metrics")
        assert res.status_code == 200
        assert "ibvap_http_requests_total" in res.text
        print("TestClient verification succeeded!")

if __name__ == "__main__":
    test_metrics_endpoint()
