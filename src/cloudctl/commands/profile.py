"""
Profile command — save, load, delete, and manage named contexts.

Allows users to work with saved profiles (account/role/region combos).

IMPORTANT: Profiles are for HUMAN convenience only.
Agents should NOT use profiles — they should use explicit cloudctl switch with --non-interactive.

Commands:
    cloudctl profile save <name>        Save current context as a named profile
    cloudctl profile load <name>        Load a profile and switch context
    cloudctl profile list               List all saved profiles
    cloudctl profile show <name>        Show details of a profile
    cloudctl profile delete <name>      Delete a profile
    cloudctl profile set-default <name> Set default profile (auto-load on init)
    cloudctl profile clear-default      Clear default profile
    cloudctl profile export             Export profiles to file for backup
    cloudctl profile import             Import profiles from backup file
    cloudctl profile validate           Validate all profiles
"""

from .. import utils


def cmd_profile_save(args) -> int:
    """
    Save current context as a named profile.

    Usage:
        cloudctl profile save <name>
        cloudctl profile save <name> --org <org> --account <id> --role <role> --region <region>
    """
    utils.console.print("[yellow]⚠️  Profiles are for humans.[/]")
    utils.console.print(
        "[yellow]Agents should use: cloudctl switch --org X --account Y --role Z --non-interactive[/]"
    )
    utils.console.print()

    if not args.name:
        utils.console.print("[red]✗ Profile name required[/]")
        utils.console.print("  cloudctl profile save <name>")
        return 1

    # Feature not yet implemented
    utils.console.print("[yellow]Profile feature is coming soon.[/]")
    return 0


def cmd_profile_load(args) -> int:
    """
    Load a profile and switch to its context.

    Usage:
        cloudctl profile load <name>
    """
    utils.console.print("[yellow]⚠️  Profiles are for humans.[/]")
    utils.console.print(
        "[yellow]Agents should use: cloudctl switch --org X --account Y --role Z --non-interactive[/]"
    )
    utils.console.print()

    if not args.name:
        utils.console.print("[red]✗ Profile name required[/]")
        utils.console.print("  cloudctl profile load <name>")
        return 1

    # Feature not yet implemented
    utils.console.print("[yellow]Profile feature is coming soon.[/]")
    return 0


def cmd_profile_list(args) -> int:
    """
    List all saved profiles.

    Usage:
        cloudctl profile list
    """
    utils.console.print("[yellow]⚠️  Profiles are for humans.[/]")
    utils.console.print(
        "[yellow]Agents should use: cloudctl switch --org X --account Y --role Z --non-interactive[/]"
    )
    utils.console.print()

    utils.console.print("[yellow]Profile feature is coming soon.[/]")
    return 0


def cmd_profile_show(args) -> int:
    """
    Show details of a specific profile.

    Usage:
        cloudctl profile show <name>
    """
    utils.console.print("[yellow]⚠️  Profiles are for humans.[/]")
    utils.console.print(
        "[yellow]Agents should use: cloudctl switch --org X --account Y --role Z --non-interactive[/]"
    )
    utils.console.print()

    if not args.name:
        utils.console.print("[red]✗ Profile name required[/]")
        utils.console.print("  cloudctl profile show <name>")
        return 1

    utils.console.print("[yellow]Profile feature is coming soon.[/]")
    return 0


def cmd_profile_delete(args) -> int:
    """
    Delete a profile.

    Usage:
        cloudctl profile delete <name>
        cloudctl profile delete <name> --force
    """
    utils.console.print("[yellow]⚠️  Profiles are for humans.[/]")
    utils.console.print(
        "[yellow]Agents should use: cloudctl switch --org X --account Y --role Z --non-interactive[/]"
    )
    utils.console.print()

    if not args.name:
        utils.console.print("[red]✗ Profile name required[/]")
        utils.console.print("  cloudctl profile delete <name>")
        return 1

    utils.console.print("[yellow]Profile feature is coming soon.[/]")
    return 0


def cmd_profile_set_default(args) -> int:
    """
    Set a profile as the default (auto-loaded on shell init).

    Usage:
        cloudctl profile set-default <name>
    """
    utils.console.print("[yellow]⚠️  Profiles are for humans.[/]")
    utils.console.print(
        "[yellow]Agents should use: cloudctl switch --org X --account Y --role Z --non-interactive[/]"
    )
    utils.console.print()

    if not args.name:
        utils.console.print("[red]✗ Profile name required[/]")
        utils.console.print("  cloudctl profile set-default <name>")
        return 1

    utils.console.print("[yellow]Profile feature is coming soon.[/]")
    return 0


def cmd_profile_clear_default(args) -> int:
    """
    Clear the default profile.

    Usage:
        cloudctl profile clear-default
    """
    utils.console.print("[yellow]⚠️  Profiles are for humans.[/]")
    utils.console.print(
        "[yellow]Agents should use: cloudctl switch --org X --account Y --role Z --non-interactive[/]"
    )
    utils.console.print()

    utils.console.print("[yellow]Profile feature is coming soon.[/]")
    return 0


def cmd_profile_export(args) -> int:
    """
    Export profiles to a JSON file for backup or sharing.

    Usage:
        cloudctl profile export --output backup.json
    """
    utils.console.print(
        "[yellow]⚠️  Warning: Profiles are local-only (not portable).[/]"
    )
    utils.console.print(
        "[yellow]Exported file contains NO credentials (safe to share).[/]"
    )
    utils.console.print(
        "[yellow]Do not use for agent automation — use explicit args instead.[/]"
    )
    utils.console.print()

    utils.console.print("[yellow]Profile feature is coming soon.[/]")
    return 0


def cmd_profile_import(args) -> int:
    """
    Import profiles from a JSON backup file.

    Usage:
        cloudctl profile import backup.json
    """
    utils.console.print("[yellow]⚠️  Profiles are for humans.[/]")
    utils.console.print(
        "[yellow]Agents should use: cloudctl switch --org X --account Y --role Z --non-interactive[/]"
    )
    utils.console.print()

    utils.console.print("[yellow]Profile feature is coming soon.[/]")
    return 0


def cmd_profile_validate(args) -> int:
    """
    Validate all profiles (check credentials and configuration).

    Usage:
        cloudctl profile validate
    """
    utils.console.print("[yellow]⚠️  Profiles are for humans.[/]")
    utils.console.print(
        "[yellow]Agents should use: cloudctl switch --org X --account Y --role Z --non-interactive[/]"
    )
    utils.console.print()

    utils.console.print("[yellow]Profile feature is coming soon.[/]")
    return 0
