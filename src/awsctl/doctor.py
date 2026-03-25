from . import aws, utils

is_wsl = utils.is_wsl


def check_aws_version() -> bool:
    return aws.run_aws(["--version"]).get("returncode") == 0


def check_shell_integration() -> bool:
    return True


def check_wsl_performance() -> bool:
    return True


def check_permissions() -> bool:
    return True


def run_diagnostics():
    check_aws_version()
    check_shell_integration()
