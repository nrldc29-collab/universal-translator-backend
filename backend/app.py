import uvicorn

from backend.api import app
from backend.config import get_backend_host, get_backend_port, is_production


if __name__ == "__main__":
    uvicorn.run(
        "backend.api:app",
        host=get_backend_host(),
        port=get_backend_port(),
        reload=not is_production(),
        workers=1,
        ws_ping_interval=20,
        ws_ping_timeout=20,
    )
