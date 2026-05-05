import base64
import hashlib
import hmac
import json
from collections import defaultdict
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

    def check(self, identity: str) -> tuple[bool, int]:
        now = time()
        minute_start = now - 60
        minute_requests = [timestamp for timestamp in self.minute_usage[identity] if timestamp >= minute_start]
        self.minute_usage[identity] = minute_requests
        if len(minute_requests) >= get_requests_per_minute():
            return False, 0
        minute_requests.append(now)

        window_start = now - 3600
        requests = [timestamp for timestamp in self.usage[identity] if timestamp >= window_start]
        self.usage[identity] = requests
        limit = get_quota_limit()
        if len(requests) >= limit:
            return False, 0
        requests.append(now)
        return True, limit - len(requests)

    def check_audio_seconds(self, identity: str, seconds: float) -> tuple[bool, float]:
        tier = get_user_tiers().get(identity, "free")
        if tier == "pro":
            return True, float("inf")

        now = time()
        day_start = now - 86400
        records = [(timestamp, used_seconds) for timestamp, used_seconds in self.audio_usage[identity] if timestamp >= day_start]
        used = sum(used_seconds for timestamp, used_seconds in records)
        limit = get_free_daily_audio_minutes() * 60
        if used + seconds > limit:
            self.audio_usage[identity] = records
            return False, max(0, limit - used)
        records.append((now, seconds))
        self.audio_usage[identity] = records
        return True, max(0, limit - used - seconds)

    def track(self, identity: str, metric: str, amount: float = 1) -> None:
        record = self.billing_usage[identity]
        record[metric] = record.get(metric, 0) + amount
        record["last_seen"] = time()

    def track_audio(self, identity: str, seconds: float, metric: str = "audio_translations") -> None:
        self.track(identity, metric, 1)
        self.track(identity, "audio_seconds", seconds)

    def snapshot(self) -> dict:
        now = time()
        return {
            identity: len([timestamp for timestamp in timestamps if timestamp >= now - 3600])
            for identity, timestamps in self.usage.items()
        }

    def audio_snapshot(self) -> dict:
        now = time()
        return {
            identity: round(sum(seconds for timestamp, seconds in records if timestamp >= now - 86400) / 60, 2)
            for identity, records in self.audio_usage.items()
        }

    def billing_snapshot(self) -> dict:
        return {
            identity: {
                **record,
                "audio_minutes": round(record.get("audio_seconds", 0) / 60, 2),
            }
            for identity, record in self.billing_usage.items()
        }


usage_limiter = UsageLimiter()


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
    signing_input = f"{header_b64}.{payload_b64}"
    expected = hmac.new(get_jwt_secret().encode("utf-8"), signing_input.encode("ascii"), hashlib.sha256).digest()
    try:
        actual = _b64url_decode(signature_b64)
        header = json.loads(_b64url_decode(header_b64))
        payload = json.loads(_b64url_decode(payload_b64))
    except Exception:
        return None
    if header.get("alg") != "HS256" or header.get("typ") != "JWT":
        return None
    if not hmac.compare_digest(actual, expected):
        return None
    if int(payload.get("exp", 0)) < int(time()):
        return None
    subject = payload.get("sub")
    return subject if isinstance(subject, str) and subject else None


def authenticate_user(username: str, password: str) -> str:
    users = get_users()
    expected_password = users.get(username)
    if not expected_password or not hmac.compare_digest(expected_password, password):
        raise HTTPException(status_code=401, detail="Invalid username or password.")
    return create_jwt(username)


def extract_bearer_token(value: str | None) -> str | None:
    if not value:
        return None
    scheme, _, token = value.partition(" ")
    if scheme.lower() == "bearer" and token.strip():
        return token.strip()
    return value.strip()


def authenticate_http(
    authorization: str | None = Header(default=None),
    x_api_key: str | None = Header(default=None),
) -> str:
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
        raise HTTPException(status_code=401, detail="Invalid or missing credentials.")

    allowed, remaining = usage_limiter.check(identity)
    if not allowed:
        raise HTTPException(status_code=429, detail="Quota exceeded.")
    return identity


async def authenticate_websocket(websocket: WebSocket) -> tuple[bool, str]:
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
        await websocket.close(code=1008, reason="Invalid or missing credentials.")
        return False, "anonymous"

    allowed, remaining = usage_limiter.check(identity)
    if not allowed:
        await websocket.close(code=1008, reason="Quota exceeded.")
        return False, identity
    return True, identity
