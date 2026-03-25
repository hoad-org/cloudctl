from .. import config, core, utils


def run_wizard() -> bool:
    utils.console.print("Welcome to the awsctl Setup Wizard!")
    try:
        _ = config.get_orgs_path(ensure=True)
        if core.cmd_config_sync() != 0:
            utils.console.print("Failed to sync profiles")
            return False
        return True
    except Exception as e:
        utils.console.print(f"Wizard failed: {e}")
        return False
