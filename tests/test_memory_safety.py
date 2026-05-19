from backend.profile_memory import ProfileMemory
from backend.speakers import SpeakerMemory


def test_profile_memory_returns_independent_lists(tmp_path):
    memory = ProfileMemory(str(tmp_path / "profiles.json"))

    profile = memory.get("user-a")
    profile["history"].append({"type": "text"})

    assert memory.get("user-a")["history"] == []


def test_profile_memory_atomic_save_and_reload(tmp_path):
    path = tmp_path / "profiles.json"
    memory = ProfileMemory(str(path))

    memory.save("user-a", {"preferred_languages": ["en", "es"], "history": [{"type": "text"}]})
    reloaded = ProfileMemory(str(path))

    assert reloaded.get("user-a")["preferred_languages"] == ["en", "es"]
    assert reloaded.get("user-a")["history"] == [{"type": "text"}]


def test_speaker_memory_returns_history_copy():
    memory = SpeakerMemory()
    memory.add_message("A", "hello")

    context = memory.get_context("A")
    context["history"].append("mutated")

    assert memory.get_context("A")["history"] == ["hello"]
