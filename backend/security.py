import base64
import hashlib
import hmac
import json
import logging
from collections import defaultdict
from threading import RLock
from time import time

from fastapi import Header, HTTPException, WebSocket

from backend.config import (
    get_api_keys,
    get_free_daily_audio_minutes,
    get_jwt_secret,
    get_quota_limit,
    get_requests_per_minute,
    get_session_minutes,
    get_user_tiers,
    get_users,
    is_production,
)
from backend.store import get_quota_store, get_user_store

_sec_logger = logging.getLogger("anai_translator.security")


class UsageLimiter:
    def __init__(self):
        self.usage = defaultdict(list)
        self.minute_usage = defaultdict(list)
        self.audio_usage = defaultdict(list)
        self.billing_usage = defaultdict(lambda: {
            "http_requests": 0,
            "text_translations": 0,
            "audio_translations": 0,
            "streaming_segments": 0,
            "audio_seconds": 0.0,
            "errors": 0,
            "last_seen": 0.0,
        })
        self._lock = RLock()
        self._quota_seeded: set[str] = set()
        self._audio_seeded: set[str] = set()

    def reset(self) -> None:
        """Clear in-memory counters (test isolation)."""
        with self._lock:
            self.usage.clear()
            self.minute_usage.clear()
            self.audio_usage.clear()
            self.billing_usage = defaultdict(lambda: {
                "http_requests": 0,
                "text_translations": 0,
                "audio_translations": 0,
                "streaming_segments": 0,
                "audio_seconds": 0.0,
                "errors": 0,
                "last_seen": 0.0,
            })
            self._quota_seeded.clear()
            self._audio_seeded.clear()

    def _ensure_quota_seeded(self, identity: str) -> None:
        """Lazily hydrate hourly quota from DB on first access per identity."""
        if identity not in self._quota_seeded:
            qs = get_quota_store()
            if qs._available:
                qs.seed_requests(identity, self.usage)
            self._quota_seeded.add(identity)

    def _ensure_audio_seeded(self, identity: str) -> None:
        """Lazily hydrate daily audio quota from DB on first access per identity."""
        if identity not in self._audio_seeded:
            qs = get_quota_store()
            if qs._available:
                qs.seed_audio(identity, self.audio_usage)
            self._audio_seeded.add(identity)

    def check(self, identity: str) -> tuple[bool, int]:
        with self._lock:
            now = time()
            # Per-minute check (in-memory only — short window)
            minute_start = now - 60
            minute_requests = [ts for ts in self.minute_usage[identity] if ts >= minute_start]
            self.minute_usage[identity] = minute_requests
            if len(minute_requests) >= get_requests_per_minute():
                return False, 0
            minute_requests.append(now)
            self.minute_usage[identity] = minute_requests

            # Hourly check — seed from DB once per identity so restarts don't reset counts
            self._ensure_quota_seeded(identity)
            window_start = now - 3600
            requests = [ts for ts in self.usage[identity] if ts >= window_start]
            self.usage[identity] = requests
            limit = get_quota_limit()
            if len(requests) >= limit:
                return False, 0
            requests.append(now)
            self.usage[identity] = requests
            # Persist asynchronously (best-effort; never blocks the request)
            try:
                get_quota_store().record_request(identity, now)
            except Exception:
                pass
            return True, limit - len(requests)

    def check_audio_seconds(self, identity: str, seconds: float) -> tuple[bool, float]:
        with self._lock:
            # Check DB tier first, then fall back to env-var tiers
            us = get_user_store()
            tier = None
            if us.is_available() and us.has_any_users():
                tier = us.get_tier(identity)
            if tier is None:
                tier = get_user_tiers().get(identity, "free")
            if tier == "pro":
                return True, float("inf")

            now = time()
            day_start = now - 86400
            # Seed from DB once per identity so restarts don't reset daily audio usage
            self._ensure_audio_seeded(identity)
            records = [(ts, secs) for ts, secs in self.audio_usage[identity] if ts >= day_start]
            used = sum(secs for _, secs in records)
            limit = get_free_daily_audio_minutes() * 60
            if used + seconds > limit:
                self.audio_usage[identity] = records
                return False, max(0, limit - used)
            records.append((now, seconds))
            self.audio_usage[identity] = records
            try:
                get_quota_store().record_audio(identity, now, seconds)
            except Exception:
                pass
            return True, max(0, limit - used - seconds)

    def track(self, identity: str, metric: str, amount: float = 1) -> None:
        with self._lock:
            record = self.billing_usage[identity]
            record[metric] = record.get(metric, 0) + amount
            record["last_seen"] = time()

    def track_audio(self, identity: str, seconds: float, metric: str = "audio_translations") -> None:
        self.track(identity, metric, 1)
        self.track(identity, "audio_seconds", seconds)

    def snapshot(self) -> dict:
        with self._lock:
            now = time()
            return {
                identity: len([timestamp for timestamp in timestamps if timestamp >= now - 3600])
                for identity, timestamps in self.usage.items()
            }

    def audio_snapshot(self) -> dict:
        with self._lock:
            now = time()
            return {
                identity: round(sum(seconds for timestamp, seconds in records if timestamp >= now - 86400) / 60, 2)
                for identity, records in self.audio_usage.items()
            }

    def billing_snapshot(self) -> dict:
        with self._lock:
            return {
                identity: {
                    **record,
                    "audio_minutes": round(record.get("audio_seconds", 0) / 60, 2),
                }
                for identity, record in self.billing_usage.items()
            }


usage_limiter = UsageLimiter()
WEBSOCKET_AUTH_RELEASE = "anonymous-ws-v3"


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + padding)


def create_jwt(username: str) -> str:
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {"sub": username, "iat": int(time()), "exp": int(time() + get_session_minutes() * 60)}
    signing_input = ".".join([
        _b64url_encode(json.dumps(header, separators=(",", ":")).encode("utf-8")),
        _b64url_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8")),
    ])
    signature = hmac.new(get_jwt_secret().encode("utf-8"), signing_input.encode("ascii"), hashlib.sha256).digest()
    return f"{signing_input}.{_b64url_encode(signature)}"


def verify_jwt(token: str | None) -> str | None:
    if not token or token.count(".") != 2:
        return None
    header_b64, payload_b64, signature_b64 = token.split(".")
    try:
        signing_input = f"{header_b64}.{payload_b64}"
        signing_bytes = signing_input.encode("ascii")
        actual = _b64url_decode(signature_b64)
        header = json.loads(_b64url_decode(header_b64))
        payload = json.loads(_b64url_decode(payload_b64))
    except (ValueError, json.JSONDecodeError, TypeError):
        return None
    expected = hmac.new(get_jwt_secret().encode("utf-8"), signing_bytes, hashlib.sha256).digest()
    if header.get("alg") != "HS256" or header.get("typ") != "JWT":
        return None
    if not hmac.compare_digest(actual, expected):
        return None
    try:
        expires_at = int(payload.get("exp", 0))
    except (TypeError, ValueError):
        return None
    if expires_at < int(time()):
        return None
    subject = payload.get("sub")
    return subject if isinstance(subject, str) and subject else None


def authenticate_user(username: str, password: str) -> str:
    """Authenticate against DB users (when DATA_DIR is set) or env-var USERS."""
    us = get_user_store()
    if us.is_available() and us.has_any_users():
        if not us.verify_user(username, password):
            raise HTTPException(status_code=401, detail="Invalid username or password.")
    else:
        users = get_users()
        expected_password = users.get(username)
        if not expected_password or not hmac.compare_digest(expected_password, password):
            raise HTTPException(status_code=401, detail="Invalid username or password.")
    return create_jwt(username)


def extract_bearer_token(value):
    if not value:
        return None
    scheme, _, token = value.partition(" ")
    if scheme.lower() == "bearer" and token.strip():
        return token.strip()
    return value.strip()


def authenticate_http(
    authorization=Header(default=None),
    x_api_key=Header(default=None),
):
    bearer_token = extract_bearer_token(authorization)
    jwt_identity = verify_jwt(bearer_token)
    keys = get_api_keys()
    if jwt_identity:
        identity = jwt_identity
    elif not keys and not is_production():
        identity = "dev"
    elif x_api_key in keys:
        identity = x_api_key or "anonymous"
    else:
        identity = "anonymous"
    allowed, remaining = usage_limiter.check(identity)
    if not allowed:
        raise HTTPException(status_code=429, detail="Quota exceeded.")
    return identity


async def authenticate_websocket(websocket):
    token = (
        websocket.query_params.get("token")
        or websocket.query_params.get("access_token")
        or extract_bearer_token(websocket.headers.get("authorization"))
        or websocket.headers.get("x-api-key")
    )
    jwt_identity = verify_jwt(extract_bearer_token(token))
    keys = get_api_keys()
    if jwt_identity:
        identity = jwt_identity
    elif not keys and not is_production():
        identity = "dev"
    elif token in keys:
        identity = token or "anonymous"
    else:
        identity = "anonymous"
    identity = str(identity or "anonymous")[:128]
    if identity == "anonymous":
        return True, identity
    allowed, remaining = usage_limiter.check(identity)
    if not allowed:
        await websocket.close(code=1008, reason="Quota exceeded.")
        return False, identity
    return True, identity
