from backend.ailang_pipeline import coalesce_agent_text, usable_agent_text


def test_usable_agent_text_rejects_json_stubs():
    assert not usable_agent_text('{"people": [], "places": []}', "hello")
    assert not usable_agent_text("[AI:fast] prompt", "hello")
    assert usable_agent_text("hello there", "hello")


def test_coalesce_agent_text_falls_back_on_stub():
    assert coalesce_agent_text('{"pueblo": []}', "Hola") == "Hola"
    assert coalesce_agent_text("Bonjour", "Hello") == "Bonjour"
