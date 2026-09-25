"""
IBVAP Pipeline - GITS Public CCTV Stream Resolver
Resolves public live traffic camera endpoints from the Gyeonggi Intelligent
Transport Systems (GITS) and Korea Expressway Corporation network (e.g. Camera 95366).

Handles dynamic tokenized HLS playlists (wmsAuthSign) with automatic expiration tracking.
"""

import re
import ssl
import base64
import logging
import urllib.request
from typing import Optional, Tuple, Dict, Any
from urllib.parse import urlparse, parse_qs

logger = logging.getLogger("ibvap.pipeline.gits_resolver")

GITS_POPUP_BASE = "https://gits.gg.go.kr/web/popup/webCctvPopup.do?cctvId="
GITS_ID_PATTERN = re.compile(r"^(?:gits[://\-_]*)?(\d{4,7})$", re.IGNORECASE)
GITS_RESOLVER_GET_PATTERN = re.compile(r"""\$\.get\(\s*['"]//([^'"]+!hls)['"]""", re.IGNORECASE)


class GITSResolutionError(Exception):
    """Raised when resolving a GITS live CCTV camera stream fails."""
    pass


def is_gits_source(source: Any) -> bool:
    """
    Determines whether the provided source string or URI represents a GITS camera.
    Recognizes:
      - 'gits://95366'
      - 'gits-95366'
      - '95366' (4-7 digit numeric ID)
      - 'https://gits.gg.go.kr/web/popup/webCctvPopup.do?cctvId=95366'
      - 'https://trafficvision.live/?continent=Asia&camera=gits-95366'
    """
    if not source or not isinstance(source, str):
        return False

    s = source.strip()
    if GITS_ID_PATTERN.match(s):
        return True

    if "cctvid=" in s.lower() and "gits" in s.lower():
        return True

    if "trafficvision.live" in s.lower() and "gits-" in s.lower():
        return True

    return False


def extract_gits_cctv_id(source: str) -> Optional[str]:
    """
    Extracts the numerical GITS CCTV identifier from various URL and URI forms.
    """
    if not source or not isinstance(source, str):
        return None

    s = source.strip()
    match = GITS_ID_PATTERN.match(s)
    if match:
        return match.group(1)

    # URL query parameter parsing
    try:
        parsed = urlparse(s)
        qs = parse_qs(parsed.query)
        if "cctvId" in qs:
            return qs["cctvId"][0]
        if "cctvid" in qs:
            return qs["cctvid"][0]
        if "camera" in qs:
            cam_val = qs["camera"][0]
            m = re.search(r"gits-(\d+)", cam_val, re.IGNORECASE)
            if m:
                return m.group(1)
    except Exception:
        pass

    # Regex search fallback
    fallback = re.search(r"(?:cctvId=|gits[-_/])(\d{4,7})", s, re.IGNORECASE)
    if fallback:
        return fallback.group(1)

    return None


def parse_wms_auth_sign(m3u8_url: str) -> Dict[str, Any]:
    """
    Decodes and parses the wmsAuthSign parameter from a resolved playlist URL.
    Example query param: wmsAuthSign=c2VydmVyX3RpbWU9...
    """
    meta: Dict[str, Any] = {
        "valid_minutes": 120,
        "server_time": None,
        "stream_id": None
    }
    try:
        parsed = urlparse(m3u8_url)
        qs = parse_qs(parsed.query)
        if "wmsAuthSign" in qs:
            sign_b64 = qs["wmsAuthSign"][0]
            # Add padding if needed
            padded = sign_b64 + "=" * (-len(sign_b64) % 4)
            decoded = base64.b64decode(padded).decode("utf-8", errors="ignore")
            sign_params = parse_qs(decoded)

            if "validminutes" in sign_params:
                meta["valid_minutes"] = int(sign_params["validminutes"][0])
            if "server_time" in sign_params:
                meta["server_time"] = sign_params["server_time"][0]
            if "id" in sign_params:
                meta["stream_id"] = sign_params["id"][0]
    except Exception as e:
        logger.debug("Could not parse wmsAuthSign metadata: %s", e)

    return meta


def resolve_gits_hls_url(source: str, timeout: float = 10.0) -> Tuple[str, Dict[str, Any]]:
    """
    Resolves the live HLS (.m3u8) playlist URL for a GITS camera.
    Returns:
        Tuple of (resolved_m3u8_url, metadata_dict)
    Raises:
        GITSResolutionError if the camera ID cannot be extracted or resolved.
    """
    cctv_id = extract_gits_cctv_id(source)
    if not cctv_id:
        raise GITSResolutionError(f"Cannot extract valid GITS CCTV ID from source: {source}")

    popup_url = f"{GITS_POPUP_BASE}{cctv_id}"
    logger.info("Resolving GITS live camera CCTV_ID=%s via %s", cctv_id, popup_url)

    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
        "Accept": "*/*",
        "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
    }

    try:
        req = urllib.request.Request(popup_url, headers=headers)
        with urllib.request.urlopen(req, context=ctx, timeout=timeout) as resp:
            html = resp.read().decode("utf-8", errors="replace")
    except Exception as e:
        raise GITSResolutionError(f"Failed to fetch GITS CCTV popup for ID {cctv_id}: {e}") from e

    match = GITS_RESOLVER_GET_PATTERN.search(html)
    if not match:
        raise GITSResolutionError(
            f"Could not locate HLS stream resolver endpoint in GITS page for camera {cctv_id}."
        )

    endpoint_path = match.group(1)
    endpoint_url = f"http://{endpoint_path}"
    logger.debug("Fetching dynamic signed playlist from endpoint: %s", endpoint_url)

    try:
        req2 = urllib.request.Request(
            endpoint_url,
            headers={**headers, "Referer": popup_url}
        )
        with urllib.request.urlopen(req2, context=ctx, timeout=timeout) as resp:
            m3u8_url = resp.read().decode("utf-8", errors="replace").strip()
    except Exception as e:
        raise GITSResolutionError(f"Failed to obtain signed HLS URL from {endpoint_url}: {e}") from e

    if not m3u8_url.startswith("http"):
        raise GITSResolutionError(f"Invalid resolved playlist URL: {m3u8_url}")

    metadata = parse_wms_auth_sign(m3u8_url)
    metadata["cctv_id"] = cctv_id
    metadata["popup_url"] = popup_url
    metadata["endpoint_url"] = endpoint_url

    logger.info(
        "Successfully resolved GITS Camera %s HLS URL (Token valid for %d minutes)",
        cctv_id, metadata.get("valid_minutes", 120)
    )
    return m3u8_url, metadata
