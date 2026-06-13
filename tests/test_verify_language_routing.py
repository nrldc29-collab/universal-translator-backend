from scripts.verify_language_routing import main


def test_verify_language_routing_script_passes():
    assert main() == 0
