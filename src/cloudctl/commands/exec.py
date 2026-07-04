import json
import os
import subprocess
import sys
from cloudctl.commands.base import BaseCommand
from cloudctl.context_manager import load_context
from cloudctl.config import get_org
from cloudctl import exit_codes


class ExecCommand(BaseCommand):
    """
    Run a command with fresh credentials injected for the active context.

    Retrieves short-lived credentials from the appropriate cloud provider
    (AWS STS, Azure token, or GCP ADC) and passes them as environment
    variables to the child process.  Nothing is written to disk.

    Failure discipline (agent contract):
        * Every failure exits NON-ZERO with a documented code (see exit_codes)
          and prints an actionable message to STDERR.
        * The success path is untouched: the child owns stdout/stderr and its
          return code is propagated verbatim.
        * With ``--json-errors`` those failures print a single-line JSON object
          ``{"error": "...", "code": <int>}`` to STDERR instead of prose, so an
          agent can parse the reason without scraping formatted text.

    Examples:
        # Use active context (set by cloudctl switch)
        cloudctl exec -- terraform plan

        # Explicit org without changing shell context (safe for scripts)
        cloudctl exec --org prod -- aws s3 ls
        cloudctl exec --org fdr-gvc --account 111111111111 --role ReadOnly -- terraform show
    """

    def configure_parser(self, subparsers):
        parser = subparsers.add_parser(
            "exec",
            help="Run a command with cloud credentials (without changing shell context)",
        )
        parser.add_argument(
            "--org",
            dest="exec_org",
            help="Organisation to use (defaults to active context)",
        )
        parser.add_argument(
            "--account",
            dest="exec_account",
            help="Account/subscription/project ID (defaults to context)",
        )
        parser.add_argument(
            "--role",
            dest="exec_role",
            help="Role/permission-set (defaults to context)",
        )
        parser.add_argument(
            "--region",
            dest="exec_region",
            help="Region (defaults to context)",
        )
        parser.add_argument(
            "--json-errors",
            action="store_true",
            dest="json_errors",
            help="On failure, print a one-line JSON error object to stderr",
        )
        parser.add_argument("cmd", nargs="+", help="Command to execute")

    def _fail(self, prose: str, error: str, code: int) -> int:
        """Emit a failure and return its exit code.

        prose : Rich-markup message for humans (goes to self.console → stderr).
        error : plain, single-line message used for the JSON form.
        code  : the process exit code (also embedded in the JSON payload).
        """
        if self._json_errors:
            # One line, machine-parseable, on STDERR. Never Rich-decorated.
            sys.stderr.write(json.dumps({"error": error, "code": code}) + "\n")
        else:
            self.console.print(prose)
        return code

    def execute(self, args) -> int:
        # Whether failures should be emitted as JSON (opt-in, default prose).
        self._json_errors = bool(getattr(args, "json_errors", False))

        ctx = load_context()

        # --org flag bypasses active context entirely
        org_name = getattr(args, "exec_org", None) or (
            ctx.get("current_org", "") or ctx.get("org", "") if ctx else ""
        )
        account = getattr(args, "exec_account", None) or (
            ctx.get("account", "") if ctx else ""
        )
        role = getattr(args, "exec_role", None) or (ctx.get("role", "") if ctx else "")
        region = getattr(args, "exec_region", None) or (
            ctx.get("region", "") if ctx else ""
        )

        if not org_name:
            # No context and no --org: this is a missing-arguments condition.
            return self._fail(
                "[red]No org specified and no active context.[/]\n"
                "Run [bold]cloudctl switch <org>[/bold] first, or use: "
                "[bold]cloudctl exec --org <org> -- <command>[/bold]",
                "No org specified and no active context",
                exit_codes.USAGE,
            )

        # When --org is given without --account/--role, account/role must be
        # resolved. cloudctl is built for agentic use, so never hang on an
        # interactive picker in a non-interactive context: if there's no TTY,
        # fail fast with an actionable error instead. (exec itself takes no
        # --non-interactive flag — it is non-interactive by nature; a TTY is the
        # only thing that enables the picker.)
        if getattr(args, "exec_org", None) and not all([account, role]):
            try:
                org_data = get_org(org_name)
            except Exception:
                return self._fail(
                    f"[red]Org '{org_name}' not found in config.[/]",
                    f"Org '{org_name}' not found in config",
                    exit_codes.NOT_FOUND,
                )

            if not sys.stdin.isatty():
                return self._fail(
                    "[red]Incomplete 'exec' invocation in a non-interactive context.[/]\n"
                    "Provide all of --account, --role and --region explicitly, e.g.:\n"
                    "  [bold]cloudctl exec --org <org> --account <id> --role <role> "
                    "--region <region> -- <command>[/bold]",
                    "Incomplete exec invocation: --account, --role and --region required",
                    exit_codes.USAGE,
                )

            import cloudctl.interactive as _interactive

            account, role, region = _interactive.run_interactive_use(
                org_data, account or None, role or None, region or None
            )
            if not all([account, role, region]):
                return self._fail(
                    "[red]Incomplete selection; aborting.[/]",
                    "Incomplete account/role/region selection",
                    exit_codes.USAGE,
                )

        try:
            org_data = get_org(org_name)
        except Exception:
            return self._fail(
                f"[red]Org '{org_name}' not found in config.[/]",
                f"Org '{org_name}' not found in config",
                exit_codes.NOT_FOUND,
            )

        from cloudctl.providers import get_provider

        provider = get_provider(org_data)

        try:
            creds = provider.get_credentials(org_data, account, role, region)
        except SystemExit:
            # Providers raise SystemExit when the SSO session is missing/expired
            # (auth required) — surface that as the AUTH exit code.
            return self._fail(
                "[red]Authentication required:[/] no valid SSO session. "
                "Run [bold]cloudctl login <org>[/bold].",
                "Authentication required: no valid SSO session",
                exit_codes.AUTH,
            )
        except Exception as e:
            return self._fail(
                f"[red]Failed to get credentials:[/] {e}",
                f"Failed to get credentials: {e}",
                exit_codes.ERROR,
            )

        # Start from a clean slate: strip any credential env vars the parent
        # shell may have exported for a *different* provider/account (e.g. a
        # prior `switch`), so nothing stale leaks into the child. Then inject
        # only the freshly-vended credentials for this invocation. Without this,
        # `exec --org gcp-… -- terraform` would inherit stale AWS_* (including a
        # phantom AWS_PROFILE) from an earlier AWS context.
        _STALE = (
            "AWS_ACCESS_KEY_ID",
            "AWS_SECRET_ACCESS_KEY",
            "AWS_SESSION_TOKEN",
            "AWS_PROFILE",
            "AWS_REGION",
            "AWS_DEFAULT_REGION",
            "GOOGLE_OAUTH_ACCESS_TOKEN",
            "GOOGLE_CLOUD_PROJECT",
            "GOOGLE_APPLICATION_CREDENTIALS",
            "CLOUDSDK_CORE_PROJECT",
            "CLOUDSDK_AUTH_ACCESS_TOKEN",
            "GCLOUD_PROJECT",
            "ARM_ACCESS_TOKEN",
            "ARM_SUBSCRIPTION_ID",
            "ARM_TENANT_ID",
            "AZURE_SUBSCRIPTION_ID",
            "AZURE_TENANT_ID",
        )
        env = {k: v for k, v in os.environ.items() if k not in _STALE}
        env.update(creds)

        try:
            # Success path: the child owns stdout/stderr; propagate its code.
            result = subprocess.run(args.cmd, env=env)
            return result.returncode
        except FileNotFoundError:
            return self._fail(
                f"[red]Executable not found:[/] {args.cmd[0]}",
                f"Executable not found: {args.cmd[0]}",
                127,
            )
