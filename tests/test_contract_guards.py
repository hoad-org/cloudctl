import cloudctl.aws as aws
import cloudctl.core as core
import cloudctl.sso_cache as sso_cache
import cloudctl.utils as utils


def test_aws_internal_contract():
    """Ensure internal symbols used by test mocks are exposed."""
    assert hasattr(aws, "_config_file_lock")
    assert hasattr(aws, "_check_unsafe_config")
    assert hasattr(aws, "_configparser_write")


def test_core_reexport_contract():
    """Ensure core provides stable re-export points for tests."""
    assert hasattr(core, "load_active_sso_token")
    assert hasattr(core, "get_orgs_path")
    assert hasattr(core, "AWS_DIR")


def test_cache_internal_contract():
    """Ensure sso_cache internal helpers exist."""
    assert hasattr(sso_cache, "_parse_timestamp")


def test_utils_interception_contract():
    """Ensure console is un-bound and interceptable."""
    # Tests rely on utils.console being the primary intercept point
    assert hasattr(utils, "console")
