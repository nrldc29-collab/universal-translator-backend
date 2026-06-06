from backend.observability import Observability
from backend.security import create_jwt, verify_jwt


def test_verify_jwt_rejects_malformed_non_ascii_token():
    assert verify_jwt("abc.é.def") is None


def test_verify_jwt_accepts_created_token(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", "test-secret")
    token = create_jwt("user-a")

    assert verify_jwt(token) == "user-a"


def test_record_event_truncates_sensitive_text_fields(tmp_path):
    observability = Observability()
    observability.events_path = tmp_path / "events.jsonl"
    long_text = "patient needs emergency dialysis " * 5

    observability.record_event("mobile_stream_checkpoint", source_text=long_text)

    line = observability.events_path.read_text(encoding="utf-8").strip()
    assert "patient needs emergency" in line
    assert long_text not in line
    assert "chars)" in line


def test_prometheus_tolerates_invalid_gpu_env(monkeypatch, tmp_path):
    monkeypatch.setenv("GPU_MEMORY_USED_MB", "bad")
    monkeypatch.setenv("GPU_UTILIZATION_PERCENT", "bad")
    observability = Observability()
    observability.events_path = tmp_path / "events.jsonl"

    output = observability.prometheus()

    assert "anai_translator_gpu_memory_used_mb 0.0" in output
    assert "anai_translator_gpu_utilization_percent 0.0" in output
