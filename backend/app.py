"""Entry-point for ``python -m backend.app``."""
import logging
import os

import uvicorn

from backend.config import get_backend_host, get_backend_port, is_production

_log = logging.getLogger("anai_translator.app")


def _check_worker_safety() -> int:
    use_gpu = os.getenv("USE_GPU", "0") == "1"
    requested_workers = int(os.getenv("WORKERS", "1"))
    if use_gpu and requested_workers > 1:
        _log.warning("USE_GPU=1 incompatible with workers>1. Forcing workers=1.")
        return 1
    return requested_workers


if __name__ == "__main__":
    workers = _check_worker_safety()
    host = get_backend_host()
    port = get_backend_port()
    _log.info("Starting Anai Translator on %s:%s (workers=%s)", host, port, workers)
    uvicorn.run(
        "backend.api:app",
        host=host,
        port=port,
        reload=not is_production(),
        workers=workers,
        ws_ping_interval=20,
        ws_ping_timeout=20,
    )
