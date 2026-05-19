"""
HTTP smoke test script for STT server.

This script performs basic smoke testing on the True Streaming STT HTTP endpoints
to verify the server is responding correctly. It checks health, models, usage, and
metrics endpoints for proper responses and required data.

Environment Variables:
    STT_BASE_URL: Base URL of the STT server (default: http://localhost:8000)
    STT_API_KEY: API key for authenticated endpoints (default: change-this-long-random-secret)

Usage:
    python smoke_test_http.py

Example:
    STT_BASE_URL=http://localhost:8000 STT_API_KEY=your-key python smoke_test_http.py
"""
import json
import logging
import os
import sys
from typing import Tuple
from urllib.request import Request, urlopen

BASE_URL = os.getenv("STT_BASE_URL", "http://localhost:8000")
API_KEY = os.getenv("STT_API_KEY", "change-this-long-random-secret")
HTTP_OK = 200

logger = logging.getLogger(__name__)


def get(path: str, auth: bool = False) -> Tuple[int, str]:
    """
    Perform an HTTP GET request to the specified path.
    
    Args:
        path: API endpoint path (e.g., "/health")
        auth: Whether to include Authorization header (default: False)
        
    Returns:
        Tuple of (status_code, response_body)
        
    Raises:
        Exception: If the HTTP request fails
    """
    headers = {}

    if auth:
        headers["Authorization"] = f"Bearer {API_KEY}"

    req = Request(f"{BASE_URL}{path}", headers=headers)

    logger.debug(f"GET {BASE_URL}{path} (auth={auth})")

    with urlopen(req, timeout=10) as response:
        status = response.status
        body = response.read().decode("utf-8")
        logger.debug(f"Response: status={status}, body_length={len(body)}")
        return status, body


def assert_json_endpoint(path: str, required_keys: list[str], auth: bool = False) -> None:
    """
    Assert that a JSON endpoint returns 200 and contains required keys.
    
    Args:
        path: API endpoint path
        required_keys: List of required JSON keys in the response
        auth: Whether to include Authorization header (default: False)
        
    Raises:
        AssertionError: If status is not 200 or required keys are missing
    """
    status, body = get(path, auth=auth)

    if status != HTTP_OK:
        logger.error(f"{path} returned status {status}")
        raise AssertionError(f"{path} returned status {status}")

    data = json.loads(body)

    for key in required_keys:
        if key not in data:
            logger.error(f"{path} missing key: {key}")
            raise AssertionError(f"{path} missing key: {key}")

    logger.info(f"PASS {path}")
    print(f"PASS {path}")


def assert_text_endpoint(path: str, required_text: list[str], auth: bool = False) -> None:
    """
    Assert that a text endpoint returns 200 and contains required text.
    
    Args:
        path: API endpoint path
        required_text: List of required text strings in the response
        auth: Whether to include Authorization header (default: False)
        
    Raises:
        AssertionError: If status is not 200 or required text is missing
    """
    status, body = get(path, auth=auth)

    if status != HTTP_OK:
        logger.error(f"{path} returned status {status}")
        raise AssertionError(f"{path} returned status {status}")

    for text in required_text:
        if text not in body:
            logger.error(f"{path} missing text: {text}")
            raise AssertionError(f"{path} missing text: {text}")

    logger.info(f"PASS {path}")
    print(f"PASS {path}")


def main() -> int:
    """
    Main entry point for the smoke test.
    
    Runs smoke tests against key HTTP endpoints to verify server health
    and proper response formatting.
    
    Returns:
        Exit code (0 for success, 1 for failure)
    """
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    
    logger.info(f"Starting smoke tests against {BASE_URL}")

    try:
        assert_json_endpoint(
            "/health",
            ["status", "app", "sample_rate", "channels", "frame_ms"],
        )

        assert_json_endpoint(
            "/v1/models",
            ["object", "data"],
        )

        assert_json_endpoint(
            "/v1/usage",
            [
                "active_connections",
                "sessions_started",
                "sessions_closed",
                "audio_bytes_received",
            ],
            auth=True,
        )

        assert_text_endpoint(
            "/metrics",
            [
                "stt_active_connections",
                "stt_sessions_started_total",
                "stt_audio_frames_received_total",
            ],
            auth=True,
        )

    except Exception as exc:
        logger.error(f"FAIL smoke tests: {exc}")
        print(f"FAIL smoke tests: {exc}")
        return 1

    logger.info("All smoke tests passed.")
    print("All smoke tests passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
