from typing import Any, Dict

from .base import CloudProvider
from .aws import AwsProvider
from .azure import AzureProvider
from .gcp import GcpProvider

_REGISTRY: Dict[str, type] = {
    "aws": AwsProvider,
    "azure": AzureProvider,
    "gcp": GcpProvider,
}


def get_provider(org: Dict[str, Any]) -> CloudProvider:
    """
    Return the CloudProvider instance for the given org config dict.

    The 'provider' key defaults to 'aws' so existing configs without
    an explicit provider continue to work without modification.
    """
    name = org.get("provider", "aws") if isinstance(org, dict) else "aws"
    cls = _REGISTRY.get(name)
    if cls is None:
        supported = ", ".join(sorted(_REGISTRY))
        raise ValueError(
            f"Unknown cloud provider {name!r}. " f"Supported values: {supported}"
        )
    return cls()


__all__ = [
    "CloudProvider",
    "AwsProvider",
    "AzureProvider",
    "GcpProvider",
    "get_provider",
]
