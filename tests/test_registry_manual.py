# file: tests/test_registry_manual.py
"""
Tests for Registry logic (Manual Mode vs Remote).
"""

from cloudctl import config, registry


def test_get_registry_manual_override(monkeypatch):
    """Ensure manual 'orgs' block in config overrides everything."""
    # We mock the raw config to simulate a user having manually defined orgs
    monkeypatch.setattr(
        config, "load_raw_config", lambda: {"orgs": [{"name": "manual"}]}
    )

    reg = registry.get_registry()
    assert len(reg) == 1
    assert reg[0]["name"] == "manual"


def test_get_registry_remote_fallback(monkeypatch, mock_rich_console):
    """Ensure we fetch remote if no manual orgs are defined."""
    # 1. Setup config with a registry URL but NO local orgs
    monkeypatch.setattr(
        config,
        "load_raw_config",
        lambda: {"registry": {"url": "https://test.com/registry.json"}},
    )

    # 2. Mock the remote loader
    # The signature must match registry_loader.fetch_remote_registry(url, public_key)
    monkeypatch.setattr(
        "cloudctl.registry_loader.fetch_remote_registry",
        lambda url, public_key=None: [{"name": "remote"}],
    )

    reg = registry.get_registry()

    # 3. Assertions
    assert len(reg) == 1
    assert reg[0]["name"] == "remote"


def test_get_registry_default_fallback(monkeypatch):
    """Ensure we fall back to embedded defaults on error or empty config."""
    # Simulate a totally empty config file
    monkeypatch.setattr(config, "load_raw_config", lambda: {})

    reg = registry.get_registry()

    # Implementation should return a 'Manual Setup' entry when no sources exist
    assert reg[0]["name"] == "manual-setup-required"


def test_get_choices_logic(monkeypatch):
    """Test format of choices list used by the Setup Wizard UI."""
    # Mock the registry to return a well-formed entry
    mock_data = [
        {"name": "eng", "label": "Engineering", "description": "Main account list"}
    ]
    monkeypatch.setattr(registry, "get_registry", lambda: mock_data)

    choices = registry.get_choices()

    # 1. Verify Length
    assert len(choices) == 1

    # 2. Verify Formatting Parity
    # Implementation uses ' — [dim]' (em-dash) for Rich console formatting
    expected_display = "Engineering — [dim]Main account list[/]"
    assert choices[0]["name"] == expected_display

    # 3. Verify Value Mapping
    # The 'value' key must contain the full original dict for the wizard to process
    assert choices[0]["value"]["name"] == "eng"
