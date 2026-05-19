"""Frontend serving helpers used by `backend.api`.

The backend can serve the React/Vite PWA in one of three modes:

* **Embedded** — files in `frontend/dist/` are served directly when
  `SERVE_FRONTEND_DIST=1` (used in the Railway/Docker bundle).
* **Local proxy** — in local dev, the FastAPI process forwards requests
  to the `vite` dev server so a single origin can be used.
* **Launcher** — when the upstream vite is not reachable, return a
  static HTML page with a deep link to the configured frontend URL.

These helpers were extracted from `backend.api` to keep that module
focused on route declarations. `backend.api` re-exports them under
their original underscore-prefixed names.
"""

from __future__ import annotations

import json
from html import escape
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request as UrlRequest, urlopen

from fastapi import Request, Response
from fastapi.responses import FileResponse, HTMLResponse

from backend.api_helpers import HOP_BY_HOP_HEADERS
from backend.config import (
    get_frontend_dist_dir,
    get_frontend_url,
    get_serve_frontend_dist,
)


def local_frontend_url(request: Request) -> str:
    """Return the frontend URL, rewritten for LAN/localhost dev when needed."""

    frontend_url = get_frontend_url()
    if frontend_url == "http://127.0.0.1:5173":
        host = request.headers.get("host", "").split(":", 1)[0]
        if host in {"localhost", "127.0.0.1"} or host.startswith(("192.168.", "10.", "172.")):
            return f"{request.url.scheme}://{host}:5173"
    return frontend_url


def frontend_dist_dir() -> Path:
    dist_dir = Path(get_frontend_dist_dir())
    if not dist_dir.is_absolute():
        dist_dir = Path.cwd() / dist_dir
    return dist_dir


def frontend_index_path() -> Path | None:
    index_path = frontend_dist_dir() / "index.html"
    if get_serve_frontend_dist() and index_path.is_file():
        return index_path
    return None


def frontend_asset_path(full_path: str) -> Path | None:
    """Resolve a request path to a file inside the dist dir, or None."""

    try:
        dist_dir = frontend_dist_dir().resolve()
        asset_path = (dist_dir / full_path).resolve()
    except OSError:
        return None

    if asset_path.is_file() and (asset_path == dist_dir or dist_dir in asset_path.parents):
        return asset_path
    return None


def embedded_frontend_response(full_path: str = "") -> FileResponse | None:
    """Return a FileResponse for an embedded asset, or None when not embedded."""

    index_path = frontend_index_path()
    if not index_path:
        return None

    if full_path:
        asset_path = frontend_asset_path(full_path)
        if asset_path:
            return FileResponse(asset_path)

    return FileResponse(index_path)


def frontend_launcher(frontend_url: str) -> HTMLResponse:
    """Static fallback page that redirects to the running frontend."""

    frontend_href = escape(frontend_url, quote=True)
    frontend_js = json.dumps(frontend_url)
    return HTMLResponse(f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <meta http-equiv="refresh" content="0; url={frontend_href}" />
    <title>Opening Anai Translator</title>
    <style>
      body {{
        margin: 0;
        min-height: 100vh;
        display: grid;
        place-items: center;
        font-family: system-ui, sans-serif;
        background: #03050a;
        color: #f8fafc;
      }}
      main {{
        width: min(520px, calc(100vw - 32px));
        border: 1px solid rgba(103, 232, 249, .28);
        border-radius: 24px;
        padding: 24px;
        background: #07111f;
        box-shadow: 0 20px 60px rgba(0, 0, 0, .35), 0 0 42px rgba(34, 211, 238, .12);
      }}
      a {{
        display: inline-flex;
        margin-top: 12px;
        min-height: 48px;
        align-items: center;
        justify-content: center;
        padding: 0 18px;
        border-radius: 999px;
        background: linear-gradient(135deg, #67e8f9, #2dd4bf);
        color: #03050a;
        font-weight: 800;
        text-decoration: none;
      }}
    </style>
  </head>
  <body>
    <main>
      <h1>Opening Anai Translator...</h1>
      <p>If it does not open automatically, use the button below.</p>
      <a href="{frontend_href}">Open app</a>
    </main>
    <script>window.location.replace({frontend_js});</script>
  </body>
</html>""")


def frontend_proxy_response(content: bytes, status_code: int, upstream_headers) -> Response:
    """Build a FastAPI Response from a forwarded urllib response."""

    headers = {}
    media_type = None
    for name, value in upstream_headers.items():
        lower_name = name.lower()
        if lower_name == "content-type":
            media_type = value
        elif lower_name not in HOP_BY_HOP_HEADERS:
            headers[name] = value
    return Response(content=content, status_code=status_code, media_type=media_type, headers=headers)


def proxy_frontend(request: Request, full_path: str = "") -> Response:
    """Forward a request to the local vite dev server, falling back to a launcher."""

    frontend_url = local_frontend_url(request).rstrip("/")
    path = quote(full_path, safe="/@._-")
    upstream_url = f"{frontend_url}/{path}" if path else f"{frontend_url}/"
    if request.url.query:
        upstream_url = f"{upstream_url}?{request.url.query}"

    try:
        upstream_request = UrlRequest(upstream_url, headers={"User-Agent": "AnaiTranslatorLocalProxy/1.0"})
        with urlopen(upstream_request, timeout=8) as upstream:
            return frontend_proxy_response(upstream.read(), upstream.status, upstream.headers)
    except HTTPError as exc:
        return frontend_proxy_response(exc.read(), exc.code, exc.headers)
    except URLError:
        return frontend_launcher(frontend_url)


__all__ = [
    "local_frontend_url",
    "frontend_dist_dir",
    "frontend_index_path",
    "frontend_asset_path",
    "embedded_frontend_response",
    "frontend_launcher",
    "frontend_proxy_response",
    "proxy_frontend",
]
