"""Prompt templates for NAIA pipeline stages."""

from pathlib import Path

TEMPLATE_DIR = Path(__file__).parent


def load_template(name: str) -> str:
    """Load a prompt template by name."""
    template_path = TEMPLATE_DIR / f"{name}.txt"
    if not template_path.exists():
        raise FileNotFoundError(f"Template not found: {name}")
    return template_path.read_text()


def format_template(name: str, **kwargs: str) -> str:
    """Format a template with the provided keyword arguments."""
    template = load_template(name)
    return template.format(**kwargs)
