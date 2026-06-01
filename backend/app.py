import logging
import os
import sys

import uvicorn

from backend.api import app
from backend.config import get_backend_host, get_backend_port, is_production

_log = logging.getLogger("anai_translator.app")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")


def _check_worker_safety() -> int:
    """Return the safe worker count and warn if misconfigured."""
    use_gpu = os.getenv("USE_GPU", "0") == "1"
    requested_workers = int(os.getenv("WORKERS", "1"))
    if use_gpu and requested_workers > 1:
        _log.warning(
            "USE_GPU=1 is incompatible with workers>1: GPU models cannot be shared across "
            "OS processes and each worker would load a separate model copy, exhausting VRAM. "
            "Forcing workers=1. Use horizontal pod scaling (separate containers) instead of "
            "increasing WORKERS when you need more throughput."
        )
        return 1
    if requested_workers > 1 and is_production():
        _log.warning(
            "workers=%d: each worker loads its own model copy. "
            "Ensure you have sufficient RAM/VRAM for %d independent model instances.",
            requested_workers, requested_workers,
        )
    return requested_workers


if __name__ == "__main__":
    workers = _check_worker_safety()
    uvicorn.run(
        "backend.api:app",
        host=get_backend_host(),
        port=get_backend_port(),
        reload=not is_production(),
        workers=workers,
        ws_ping_interval=20,
        ws_ping_timeout=20,
    )
