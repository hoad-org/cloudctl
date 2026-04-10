"""Tests for awsctl.schema — org config validation and partition support."""

from awsctl import schema


class TestPartitionFromSsoUrl:
    def test_commercial_url(self):
        assert schema.partition_from_sso_url("https://d-abc.awsapps.com/start") == "aws"

    def test_govcloud_url(self):
        assert (
            schema.partition_from_sso_url("https://d-abc.awsapps-us-gov.com/start")
            == "aws-us-gov"
        )

    def test_govcloud_amazonaws_us_gov(self):
        assert (
            schema.partition_from_sso_url(
                "https://portal.sso.us-gov-west-1.amazonaws-us-gov.com/start"
            )
            == "aws-us-gov"
        )

    def test_china_url(self):
        assert (
            schema.partition_from_sso_url(
                "https://portal.sso.cn-north-1.amazonaws.cn/start"
            )
            == "aws-cn"
        )

    def test_empty_url(self):
        assert schema.partition_from_sso_url("") == "aws"


class TestValidateOrg:
    def test_valid_aws_org(self):
        org = {
            "name": "prod",
            "provider": "aws",
            "partition": "aws",
            "sso_start_url": "https://d-abc.awsapps.com/start",
            "sso_region": "us-east-1",
            "allowed_regions": ["us-east-1", "us-west-2"],
        }
        assert schema.validate_org(org) == []

    def test_missing_name(self):
        errors = schema.validate_org({"provider": "aws"})
        assert any("name" in e for e in errors)

    def test_invalid_provider(self):
        errors = schema.validate_org({"name": "test", "provider": "gke"})
        assert any("provider" in e for e in errors)

    def test_aws_missing_sso_url(self):
        errors = schema.validate_org(
            {"name": "test", "provider": "aws", "sso_region": "us-east-1"}
        )
        assert any("sso_start_url" in e for e in errors)

    def test_aws_missing_sso_region(self):
        errors = schema.validate_org(
            {
                "name": "test",
                "provider": "aws",
                "sso_start_url": "https://d.awsapps.com/start",
            }
        )
        assert any("sso_region" in e for e in errors)

    def test_invalid_partition(self):
        errors = schema.validate_org(
            {
                "name": "test",
                "provider": "aws",
                "sso_start_url": "https://d.awsapps.com/start",
                "sso_region": "us-east-1",
                "partition": "aws-fake",
            }
        )
        assert any("partition" in e for e in errors)

    def test_partition_url_mismatch(self):
        errors = schema.validate_org(
            {
                "name": "test",
                "provider": "aws",
                "sso_start_url": "https://d.awsapps-us-gov.com/start",
                "sso_region": "us-gov-west-1",
                "partition": "aws",  # wrong — should be aws-us-gov
            }
        )
        assert any("partition" in e for e in errors)

    def test_govcloud_region_in_commercial_partition(self):
        errors = schema.validate_org(
            {
                "name": "test",
                "provider": "aws",
                "sso_start_url": "https://d.awsapps.com/start",
                "sso_region": "us-east-1",
                "partition": "aws",
                "allowed_regions": [
                    "us-gov-east-1"
                ],  # GovCloud region in commercial partition
            }
        )
        assert any("us-gov-east-1" in e for e in errors)

    def test_govcloud_org_valid(self):
        org = {
            "name": "gov-prod",
            "provider": "aws",
            "partition": "aws-us-gov",
            "sso_start_url": "https://d-abc.awsapps-us-gov.com/start",
            "sso_region": "us-gov-west-1",
            "allowed_regions": ["us-gov-east-1", "us-gov-west-1"],
        }
        assert schema.validate_org(org) == []

    def test_azure_missing_tenant(self):
        errors = schema.validate_org({"name": "test", "provider": "azure"})
        assert any("tenant_id" in e for e in errors)

    def test_gcp_missing_project(self):
        errors = schema.validate_org({"name": "test", "provider": "gcp"})
        assert any("default_project" in e for e in errors)

    def test_gcp_valid(self):
        errors = schema.validate_org(
            {"name": "gcp-test", "provider": "gcp", "default_project": "my-project"}
        )
        assert errors == []


class TestValidateOrgsConfig:
    def test_valid_config(self):
        data = {
            "orgs": [
                {
                    "name": "prod",
                    "provider": "aws",
                    "sso_start_url": "https://d.awsapps.com/start",
                    "sso_region": "us-east-1",
                },
            ],
            "enabled_orgs": ["prod"],
        }
        assert schema.validate_orgs_config(data) == []

    def test_not_a_dict(self):
        errors = schema.validate_orgs_config(["list", "not", "dict"])
        assert errors

    def test_orgs_not_a_list(self):
        errors = schema.validate_orgs_config({"orgs": "should-be-list"})
        assert errors

    def test_duplicate_org_names(self):
        data = {
            "orgs": [
                {
                    "name": "prod",
                    "provider": "aws",
                    "sso_start_url": "https://d.awsapps.com/start",
                    "sso_region": "us-east-1",
                },
                {"name": "prod", "provider": "azure", "tenant_id": "abc"},
            ]
        }
        errors = schema.validate_orgs_config(data)
        assert any("duplicate" in e for e in errors)

    def test_enabled_orgs_unknown_ref(self):
        data = {
            "orgs": [
                {
                    "name": "real-org",
                    "provider": "aws",
                    "sso_start_url": "https://d.awsapps.com/start",
                    "sso_region": "us-east-1",
                }
            ],
            "enabled_orgs": ["real-org", "ghost-org"],
        }
        errors = schema.validate_orgs_config(data)
        assert any("ghost-org" in e for e in errors)

    def test_empty_orgs_is_valid(self):
        assert schema.validate_orgs_config({"orgs": []}) == []


class TestAwsPartitions:
    def test_all_partitions_present(self):
        assert "aws" in schema.AWS_PARTITIONS
        assert "aws-us-gov" in schema.AWS_PARTITIONS
        assert "aws-cn" in schema.AWS_PARTITIONS

    def test_govcloud_regions(self):
        regions = schema.AWS_PARTITIONS["aws-us-gov"]["regions"]
        assert "us-gov-east-1" in regions
        assert "us-gov-west-1" in regions
        # Must not contain commercial regions
        assert "us-east-1" not in regions

    def test_china_regions(self):
        regions = schema.AWS_PARTITIONS["aws-cn"]["regions"]
        assert "cn-north-1" in regions
        assert "cn-northwest-1" in regions
        assert "us-east-1" not in regions
