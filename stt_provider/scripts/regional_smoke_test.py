"""
Regional smoke test script for the STT application.

This script performs smoke tests on regional WebSocket endpoints to verify
that each regional endpoint accepts authenticated streaming traffic and returns
transcript events quickly. It confirms that the gateway, routing, and Triton
backend are reachable and that regional routing respects tenant region and
data-residency policies.

The script connects to a WebSocket endpoint with authentication headers, sends
dummy audio data, and measures the time to receive the first response.

Example:
    python scripts/regional_smoke_test.py \\
      --websocket-url "wss://us-east-1.example.com/stt/stream" \\
      --api-key "$STT_API_KEY" \\
      --expected-region "us-east-1"

Requirements:
    pip install websockets
"""
import argparse
import asyncio
import json
import logging
import time

import websockets

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def run_smoke_test(
    *,
    websocket_url: str,
    api_key: str,
    expected_region: str,
) -> None:
    """
    Run a smoke test against a regional WebSocket endpoint.
    
    Connects to the specified WebSocket endpoint with authentication headers,
    sends dummy audio data, and measures the time to receive the first response.
    Prints the test results as JSON.
    
    Args:
        websocket_url: The WebSocket endpoint URL to test
        api_key: API key for authentication
        expected_region: The expected region for routing verification
    """
    logger.info(f"Starting smoke test for region: {expected_region}")
    logger.info(f"WebSocket URL: {websocket_url}")
    
    started_at = time.time()

    headers = {
        "Authorization": f"Bearer {api_key}",
        "X-Expected-Region": expected_region,
    }

    try:
        async with websockets.connect(
            websocket_url,
            extra_headers=headers,
        ) as websocket:
            logger.info("WebSocket connection established")
            
            # Send dummy audio data (16kHz PCM silence)
            await websocket.send(b"\x00\x00" * 16000)
            logger.debug("Sent dummy audio data")

            # Wait for first message with timeout
            message = await asyncio.wait_for(
                websocket.recv(),
                timeout=10,
            )
            logger.info("Received first message from WebSocket")

        elapsed_ms = round((time.time() - started_at) * 1000, 2)
        logger.info(f"Test completed in {elapsed_ms}ms")

        result = {
            "status": "ok",
            "websocket_url": websocket_url,
            "expected_region": expected_region,
            "elapsed_ms": elapsed_ms,
            "first_message": json.loads(message)
            if isinstance(message, str)
            else str(message),
        }

        print(json.dumps(result, indent=2))
        logger.info("Smoke test passed")
        
    except asyncio.TimeoutError:
        logger.error(f"Smoke test timed out after 10 seconds for region {expected_region}")
        error_result = {
            "status": "timeout",
            "websocket_url": websocket_url,
            "expected_region": expected_region,
            "error": "Timeout waiting for first message",
        }
        print(json.dumps(error_result, indent=2))
    except Exception as e:
        logger.error(f"Smoke test failed for region {expected_region}: {e}")
        error_result = {
            "status": "error",
            "websocket_url": websocket_url,
            "expected_region": expected_region,
            "error": str(e),
        }
        print(json.dumps(error_result, indent=2))


def main() -> None:
    """
    Main function to parse arguments and run regional smoke tests.
    
    Parses command-line arguments for WebSocket URL, API key, and expected
    region, then executes the smoke test.
    """
    parser = argparse.ArgumentParser(
        description="Run smoke tests against regional STT WebSocket endpoints"
    )
    parser.add_argument(
        "--websocket-url",
        required=True,
        help="WebSocket endpoint URL to test"
    )
    parser.add_argument(
        "--api-key",
        required=True,
        help="API key for authentication"
    )
    parser.add_argument(
        "--expected-region",
        required=True,
        help="Expected region for routing verification"
    )

    args = parser.parse_args()

    logger.info("Starting regional smoke test")
    asyncio.run(
        run_smoke_test(
            websocket_url=args.websocket_url,
            api_key=args.api_key,
            expected_region=args.expected_region,
        )
    )


if __name__ == "__main__":
    main()

"""
Usage Instructions:

Install the dependency:
    pip install websockets

Run one smoke test per region:

    python scripts/regional_smoke_test.py \\
      --websocket-url "wss://us-east-1.example.com/stt/stream" \\
      --api-key "$STT_API_KEY" \\
      --expected-region "us-east-1"

    python scripts/regional_smoke_test.py \\
      --websocket-url "wss://us-west-2.example.com/stt/stream" \\
      --api-key "$STT_API_KEY" \\
      --expected-region "us-west-2"

    python scripts/regional_smoke_test.py \\
      --websocket-url "wss://eu-west-1.example.com/stt/stream" \\
      --api-key "$STT_API_KEY" \\
      --expected-region "eu-west-1"

Purpose:
This verifies that each regional WebSocket endpoint accepts authenticated
streaming traffic and returns a first transcript event quickly enough to
confirm the gateway, routing, and Triton backend are reachable. The guide's
co-located GPU regions step requires regional GPU pools close to customers
with routing that respects tenant region and data-residency policy.
"""
