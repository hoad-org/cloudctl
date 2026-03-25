from typing import Any, Dict, List, Optional
import awsctl.config as config

KNOWN_ORGS = []


class CommandRegistry:
    def __init__(self):
        self.commands: Dict[str, Any] = {}

    def list_commands(self) -> List[str]:
        return list(self.commands.keys())

    def get_command(self, name: str) -> Optional[Any]:
        return self.commands.get(name)


def get_registry() -> List[Dict[str, Any]]:
    try:
        cfg = config.load_raw_config()
    except Exception:
        cfg = {}

    if cfg.get("orgs"):
        return cfg["orgs"]

    if "registry" in cfg and "url" in cfg["registry"]:
        from awsctl.registry_loader import fetch_remote_registry

        return fetch_remote_registry(
            cfg["registry"]["url"], cfg["registry"].get("public_key")
        )

    return [{"name": "manual-setup-required"}]


def get_choices() -> List[Dict[str, Any]]:
    reg = get_registry()
    choices = []
    for o in reg:
        name = o.get("name", "Unknown")
        label = o.get("label", name)
        desc = o.get("description", "")
        # Exact markup required: Label — [dim]desc[/] (uses em dash)
        display = f"{label} — [dim]{desc}[/]" if desc else label
        choices.append({"name": display, "value": o})
    return choices
