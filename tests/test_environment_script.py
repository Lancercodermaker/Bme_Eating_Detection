from pathlib import Path


def test_environment_verifier_script_exists_with_main_entrypoint():
    script = Path(__file__).parents[1] / "scripts" / "verify_environment.py"
    assert script.exists()
    assert "def main" in script.read_text(encoding="utf-8")
