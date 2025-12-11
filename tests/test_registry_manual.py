# file: tests/test_registry_manual.py
"""
Tests for Registry logic (Manual Mode vs Remote).
"""

from awsctl import config, registry


def test_get_registry_manual_override(monkeypatch):
    """Ensure manual 'orgs' block in config overrides everything."""
    monkeypatch.setattr(
        config, "load_raw_config", lambda: {"orgs": [{"name": "manual"}]}
    )

    reg = registry.get_registry()
    assert len(reg) == 1
    assert reg[0]["name"] == "manual"


def test_get_registry_remote_fallback(monkeypatch):
    """Ensure we fetch remote if no manual orgs are defined."""
    # Config has registry URL but no local orgs
    monkeypatch.setattr(
        config, "load_raw_config", lambda: {"registry": {"url": "https://test"}}
    )

    # Mock loader
    monkeypatch.setattr(
        "awsctl.registry_loader.fetch_remote_registry",
        lambda u, public_key: [{"name": "remote"}],
    )

    reg = registry.get_registry()
    assert reg[0]["name"] == "remote"


def test_get_registry_default_fallback(monkeypatch):
    """Ensure we fall back to embedded defaults on error or empty config."""
    monkeypatch.setattr(config, "load_raw_config", lambda: {})

    reg = registry.get_registry()
    assert reg[0]["name"] == "manual-setup-required"


def test_get_choices_logic(monkeypatch):
    """Test format of choices list."""
    monkeypatch.setattr(
        registry,
        "get_registry",
        lambda: [{"name": "a", "label": "A", "description": "desc"}],
    )

    choices = registry.get_choices()
    assert len(choices) == 1
    assert choices[0]["name"] == "A — [dim]desc[/]"
    assert choices[0]["value"]["name"] == "a"
