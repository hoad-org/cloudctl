"""Tests for CloudCTL pricing module."""

import pytest
from datetime import datetime

from cloudctl.pricing import (
    PricingCalculator,
    PricingResult,
    format_pricing_result,
)


class TestPricingCalculator:
    """Test PricingCalculator functionality."""

    def test_calculator_init(self):
        """Test calculator initialization."""
        calc = PricingCalculator()
        assert calc is not None
        assert isinstance(calc.cache, dict)

    def test_estimate_aws_ec2(self):
        """Test AWS EC2 cost estimation."""
        calc = PricingCalculator()
        result = calc.estimate_cost(
            provider="aws",
            component_type="ec2",
            config={"vcpu": 2, "memory_gb": 4},
            region="us-east-1",
        )

        assert result.provider == "aws"
        assert result.component_type == "ec2"
        assert result.currency == "USD"
        assert result.monthly_cost > 0
        assert result.annual_cost == result.monthly_cost * 12
        assert result.region == "us-east-1"
        assert result.details["vcpu"] == 2
        assert result.details["memory_gb"] == 4

    def test_estimate_aws_s3(self):
        """Test AWS S3 cost estimation."""
        calc = PricingCalculator()
        result = calc.estimate_cost(
            provider="aws",
            component_type="s3",
            config={"storage_gb": 100, "requests_per_day": 1000},
            region="us-west-2",
        )

        assert result.provider == "aws"
        assert result.component_type == "s3"
        assert result.monthly_cost > 0
        assert result.region == "us-west-2"

    def test_estimate_aws_rds(self):
        """Test AWS RDS cost estimation."""
        calc = PricingCalculator()
        result = calc.estimate_cost(
            provider="aws",
            component_type="rds",
            config={"vcpu": 2, "memory_gb": 4, "storage_gb": 20},
            region="eu-west-1",
        )

        assert result.provider == "aws"
        assert result.component_type == "rds"
        assert result.monthly_cost > 0
        assert result.details["storage_gb"] == 20

    def test_invalid_provider(self):
        """Test error handling for invalid provider."""
        calc = PricingCalculator()

        with pytest.raises(ValueError, match="Unsupported provider"):
            calc.estimate_cost(
                provider="invalid",
                component_type="ec2",
                config={},
            )

    def test_case_insensitive_provider(self):
        """Test case-insensitive provider handling."""
        calc = PricingCalculator()
        result = calc.estimate_cost(
            provider="AWS",
            component_type="ec2",
            config={"vcpu": 1, "memory_gb": 1},
        )

        assert result.provider == "aws"

    def test_case_insensitive_component(self):
        """Test case-insensitive component handling."""
        calc = PricingCalculator()
        result = calc.estimate_cost(
            provider="aws",
            component_type="EC2",
            config={"vcpu": 1, "memory_gb": 1},
        )

        assert result.component_type == "ec2"

    def test_compare_providers(self):
        """Test comparing costs across providers."""
        calc = PricingCalculator()
        results = calc.compare_providers(
            component_type="ec2",
            config={"vcpu": 2, "memory_gb": 4},
            region="us-east-1",
        )

        assert len(results) > 0
        # Results should be sorted by cost (cheapest first)
        for i in range(len(results) - 1):
            assert results[i].monthly_cost <= results[i + 1].monthly_cost

    def test_currency_support(self):
        """Test different currency support."""
        calc = PricingCalculator()

        for currency in ["USD", "EUR", "GBP"]:
            result = calc.estimate_cost(
                provider="aws",
                component_type="ec2",
                config={"vcpu": 1, "memory_gb": 1},
                currency=currency,
            )
            assert result.currency == currency

    def test_period_months(self):
        """Test period-based cost calculation."""
        calc = PricingCalculator()

        result_1m = calc.estimate_cost(
            provider="aws",
            component_type="ec2",
            config={"vcpu": 1, "memory_gb": 1},
            period_months=1,
        )

        result_12m = calc.estimate_cost(
            provider="aws",
            component_type="ec2",
            config={"vcpu": 1, "memory_gb": 1},
            period_months=12,
        )

        # Annual cost should be higher than monthly
        assert result_12m.annual_cost >= result_1m.annual_cost


class TestPricingResult:
    """Test PricingResult dataclass."""

    def test_pricing_result_creation(self):
        """Test creating a pricing result."""
        result = PricingResult(
            provider="aws",
            component_type="ec2",
            monthly_cost=50.0,
            annual_cost=600.0,
            currency="USD",
            region="us-east-1",
            details={"vcpu": 2},
            calculated_at=datetime.now(),
        )

        assert result.provider == "aws"
        assert result.monthly_cost == 50.0
        assert result.annual_cost == 600.0

    def test_pricing_result_annual_cost_calculation(self):
        """Test annual cost is 12x monthly."""
        monthly = 50.0
        result = PricingResult(
            provider="aws",
            component_type="ec2",
            monthly_cost=monthly,
            annual_cost=monthly * 12,
            currency="USD",
            region="us-east-1",
            details={},
            calculated_at=datetime.now(),
        )

        assert result.annual_cost == monthly * 12


class TestFormatPricingResult:
    """Test formatting pricing results."""

    def test_format_basic(self):
        """Test basic formatting."""
        result = PricingResult(
            provider="aws",
            component_type="ec2",
            monthly_cost=50.0,
            annual_cost=600.0,
            currency="USD",
            region="us-east-1",
            details={"vcpu": 2},
            calculated_at=datetime.now(),
        )

        output = format_pricing_result(result)
        assert "aws" in output.lower()
        assert "ec2" in output
        assert "$50.00" in output
        assert "$600.00" in output

    def test_format_verbose(self):
        """Test verbose formatting."""
        result = PricingResult(
            provider="aws",
            component_type="ec2",
            monthly_cost=50.0,
            annual_cost=600.0,
            currency="USD",
            region="us-east-1",
            details={"vcpu": 2, "memory_gb": 4},
            calculated_at=datetime.now(),
        )

        output = format_pricing_result(result, verbose=True)
        assert "Details" in output
        assert "vcpu" in output.lower() or "memory" in output.lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
