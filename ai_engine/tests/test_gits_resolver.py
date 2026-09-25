"""
Unit Tests for GITS Public CCTV Stream Resolver and VideoReader Integration
"""

import unittest
from unittest.mock import patch, MagicMock
import io
import urllib.error

from ai_engine.pipeline.gits_resolver import (
    is_gits_source,
    extract_gits_cctv_id,
    parse_wms_auth_sign,
    resolve_gits_hls_url,
    GITSResolutionError,
)
from ai_engine.pipeline.stream_reader import VideoReader


class TestGITSResolver(unittest.TestCase):

    def test_is_gits_source_formats(self):
        # Valid GITS IDs and URLs
        self.assertTrue(is_gits_source("95366"))
        self.assertTrue(is_gits_source("gits://95366"))
        self.assertTrue(is_gits_source("gits-95366"))
        self.assertTrue(is_gits_source("https://gits.gg.go.kr/web/popup/webCctvPopup.do?cctvId=95366"))
        self.assertTrue(is_gits_source("https://trafficvision.live/?continent=Asia&camera=gits-95366"))

        # Invalid or non-GITS sources
        self.assertFalse(is_gits_source("sample.mp4"))
        self.assertFalse(is_gits_source("rtsp://admin:pass@192.168.1.50/live"))
        self.assertFalse(is_gits_source("http://example.com/stream.m3u8"))
        self.assertFalse(is_gits_source(""))
        self.assertFalse(is_gits_source(None))

    def test_extract_gits_cctv_id(self):
        self.assertEqual(extract_gits_cctv_id("95366"), "95366")
        self.assertEqual(extract_gits_cctv_id("gits://95366"), "95366")
        self.assertEqual(extract_gits_cctv_id("gits-95366"), "95366")
        self.assertEqual(
            extract_gits_cctv_id("https://gits.gg.go.kr/web/popup/webCctvPopup.do?cctvId=95366"),
            "95366"
        )
        self.assertEqual(
            extract_gits_cctv_id("https://trafficvision.live/?continent=Asia&camera=gits-95366"),
            "95366"
        )
        self.assertIsNone(extract_gits_cctv_id("rtsp://10.0.0.1/live"))

    def test_parse_wms_auth_sign(self):
        # Base64 encoded: server_time=9/1/2026 8:00:00 AM&validminutes=120&id=test_stream
        import base64
        raw = "server_time=9/1/2026 8:00:00 AM&validminutes=120&id=test_stream"
        b64 = base64.b64encode(raw.encode()).decode()
        url = f"http://gitsview.gg.go.kr:8081/live/playlist.m3u8?wmsAuthSign={b64}"

        meta = parse_wms_auth_sign(url)
        self.assertEqual(meta["valid_minutes"], 120)
        self.assertEqual(meta["stream_id"], "test_stream")
        self.assertEqual(meta["server_time"], "9/1/2026 8:00:00 AM")

    @patch("urllib.request.urlopen")
    def test_resolve_gits_hls_url_mocked(self, mock_urlopen):
        # Mock first response: HTML with $.get("//gitsview.gg.go.kr/95366/mocktoken!hls")
        mock_html = """
        <html>
        <script>
            $.get("//gitsview.gg.go.kr/95366/mocktoken!hls", function(jqXHR){
                var hls = new Hls();
            });
        </script>
        </html>
        """
        # Mock second response: resolved HLS URL
        mock_m3u8 = "http://gitsview.gg.go.kr:8081/live/playlist.m3u8?wmsAuthSign=c2VydmVyX3RpbWU9dGVzdCZ2YWxpZG1pbnV0ZXM9MTIw"

        resp1 = MagicMock()
        resp1.read.return_value = mock_html.encode("utf-8")
        resp1.__enter__.return_value = resp1

        resp2 = MagicMock()
        resp2.read.return_value = mock_m3u8.encode("utf-8")
        resp2.__enter__.return_value = resp2

        mock_urlopen.side_effect = [resp1, resp2]

        url, meta = resolve_gits_hls_url("95366")
        self.assertEqual(url, mock_m3u8)
        self.assertEqual(meta["cctv_id"], "95366")
        self.assertEqual(meta["valid_minutes"], 120)

    def test_resolve_gits_hls_url_invalid_id(self):
        with self.assertRaises(GITSResolutionError):
            resolve_gits_hls_url("invalid_non_numeric_source")

    @patch("urllib.request.urlopen")
    def test_resolve_gits_hls_missing_pattern(self, mock_urlopen):
        resp = MagicMock()
        resp.read.return_value = b"<html><body>No camera stream here</body></html>"
        resp.__enter__.return_value = resp
        mock_urlopen.return_value = resp

        with self.assertRaises(GITSResolutionError):
            resolve_gits_hls_url("95366")

    @patch("ai_engine.pipeline.stream_reader.resolve_gits_hls_url")
    def test_video_reader_gits_initialization(self, mock_resolve):
        mock_resolve.return_value = (
            "http://gitsview.gg.go.kr:8081/live/playlist.m3u8?wmsAuthSign=xyz",
            {"cctv_id": "95366", "valid_minutes": 120}
        )

        reader = VideoReader("gits://95366")
        self.assertTrue(reader.is_gits_stream)
        self.assertTrue(reader.is_network_stream)
        self.assertEqual(reader.masked_path, "GITS(95366)")
        self.assertTrue(reader.video_path.startswith("http"))


if __name__ == "__main__":
    unittest.main()
