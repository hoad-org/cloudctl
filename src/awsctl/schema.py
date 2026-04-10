"""
awsctl.schema — org configuration validation.

Validates orgs.yaml content at load time, giving actionable error messages
rather than cryptic KeyError/AttributeError traces at runtime.
"""
from __future__ import annotations

from typing import Any, Dict, List

PROVIDERS = {"aws", "azure", "gcp"}

AWS_PARTITIONS: Dict[str, Dict[str, Any]] = {
    "aws": {
        "display": "AWS Commercial",
        "regions": [
            "us-east-1",
            "us-east-2",
            "us-west-1",
            "us-west-2",
            "eu-west-1",
            "eu-west-2",
            "eu-west-3",
            "eu-central-1",
            "eu-north-1",
            "eu-south-1",
            "ap-southeast-1",
            "ap-southeast-2",
            "ap-southeast-3",
            "ap-northeast-1",
            "ap-northeast-2",
            "ap-northeast-3",
            "ap-south-1",
            "ap-east-1",
            "sa-east-1",
            "ca-central-1",
            "ca-west-1",
            "me-south-1",
            "me-central-1",
            "af-south-1",
            "il-central-1",
        ],
        "sso_domain": ".awsapps.com",
        "console": "https://console.aws.amazon.com/",
    },
    "aws-us-gov": {
        "display": "AWS GovCloud (US)",
        "regions": ["us-gov-east-1", "us-gov-west-1"],
        "sso_domain": ".awsapps-us-gov.com",
        "console": "https://us-gov-home.console.amazonaws-us-gov.com/",
    },
    "aws-cn": {
        "display": "AWS China",
        "regions": ["cn-north-1", "cn-northwest-1"],
        "sso_domain": ".amazonaws.cn",
        "console": "https://console.amazonaws.cn/",
        "note": "IAM Identity Center not available; uses IAM long-term access keys",
    },
}


def partition_from_sso_url(sso_url: str) -> str:
    """Infer AWS partition from an SSO start URL."""
    if not sso_url:
        return "aws"
    url = sso_url.lower()
    if "amazonaws-us-gov.com" in url or "awsapps-us-gov.com" in url:
        return "aws-us-gov"
    if ".cn" in url or "amazonaws.cn" in url:
        return "aws-cn"
    return "aws"


def validate_org(org: Dict[str, Any]) -> List[str]:
    """Validate a single org dict. Returns list of error strings (empty = valid)."""
    errors: List[str] = []
    name = org.get("name", "")
    label = f"org '{name}'" if name else "unnamed org"

    if not name:
        errors.append(f"{label}: 'name' is required")

    provider = org.get("provider", "aws")
    if provider not in PROVIDERS:
        errors.append(
            f"{label}: 'provider' must be one of {sorted(PROVIDERS)}, got '{provider}'"
        )
        return errors  # remaining checks are provider-specific

    if provider == "aws":
        if not org.get("sso_start_url"):
            errors.append(f"{label}: AWS org requires 'sso_start_url'")
        if not org.get("sso_region"):
            errors.append(f"{label}: AWS org requires 'sso_region'")

        partition = org.get("partition", "aws")
        if partition not in AWS_PARTITIONS:
            errors.append(
                f"{label}: 'partition' must be one of {sorted(AWS_PARTITIONS)}, got '{partition}'"
            )
        else:
            sso_url = org.get("sso_start_url", "")
            inferred = partition_from_sso_url(sso_url)
            if sso_url and inferred != partition:
                errors.append(
                    f"{label}: SSO URL suggests partition '{inferred}' "
                    f"but 'partition' field is '{partition}'"
                )
            partition_regions = set(AWS_PARTITIONS[partition]["regions"])
            for r in org.get("allowed_regions", []):
                if r not in partition_regions:
                    errors.append(
                        f"{label}: region '{r}' is not valid for partition '{partition}'"
                    )

    elif provider == "azure":
        if not org.get("tenant_id"):
            errors.append(f"{label}: Azure org requires 'tenant_id'")

    elif provider == "gcp":
        if not org.get("default_project"):
            errors.append(f"{label}: GCP org requires 'default_project'")

    return errors


def validate_orgs_config(data: Dict[str, Any]) -> List[str]:
    """Validate the full orgs.yaml dict. Returns all errors across all orgs."""
    if not isinstance(data, dict):
        return ["orgs.yaml: expected a YAML mapping at the top level"]

    errors: List[str] = []
    orgs = data.get("orgs", [])
    if not isinstance(orgs, list):
        errors.append("orgs.yaml: 'orgs' must be a list")
        return errors

    seen: set = set()
    for org in orgs:
        if not isinstance(org, dict):
            errors.append("orgs.yaml: each entry in 'orgs' must be a mapping")
            continue
        errors.extend(validate_org(org))
        name = org.get("name")
        if name:
            if name in seen:
                errors.append(f"orgs.yaml: duplicate org name '{name}'")
            seen.add(name)

    enabled = data.get("enabled_orgs", [])
    if enabled:
        org_names = {o.get("name") for o in orgs if isinstance(o, dict)}
        for n in enabled or []:
            if n not in org_names:
                errors.append(f"orgs.yaml: enabled_orgs references unknown org '{n}'")

    return errors
