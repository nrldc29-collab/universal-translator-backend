from backend.security import UsageLimiter


def test_connection_burst_limit(monkeypatch):
    monkeypatch.setenv("REQUESTS_PER_MINUTE", "3")
    monkeypatch.setenv("QUOTA_REQUESTS_PER_HOUR", "5")
    limiter = UsageLimiter()

    for _ in range(3):
        allowed, _ = limiter.check_connection("user-b")
        assert allowed is True

    allowed, _ = limiter.check_connection("user-b")
    assert allowed is False
    # Connection checks should not consume hourly HTTP quota.
    assert limiter.snapshot().get("user-b", 0) == 0
    allowed, remaining = limiter.check("user-c")
    assert allowed is True
    assert remaining == 4


def test_usage_limiter_returns_snapshot_copies(monkeypatch):
    monkeypatch.setenv("REQUESTS_PER_MINUTE", "5")
    monkeypatch.setenv("QUOTA_REQUESTS_PER_HOUR", "5")
    limiter = UsageLimiter()

    allowed, remaining = limiter.check("user-a")
    limiter.track("user-a", "http_requests")

    assert allowed is True
    assert remaining == 4
    assert limiter.snapshot()["user-a"] == 1
    assert limiter.billing_snapshot()["user-a"]["http_requests"] == 1
