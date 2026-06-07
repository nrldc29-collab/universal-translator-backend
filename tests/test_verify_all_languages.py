from scripts.verify_all_languages import main


def test_verify_all_languages_script_passes():
    assert main() == 0
