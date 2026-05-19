from backend.security import UsageLimiter


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
