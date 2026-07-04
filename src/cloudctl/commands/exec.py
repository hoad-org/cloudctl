import json
import os
import subprocess
import sys
from cloudctl.commands.base import BaseCommand
from cloudctl.context_manager import load_context
from cloudctl.config import get_org
from cloudctl.providers.base import ProviderCredentialError
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
        cloudctl run -- terraform plan

        # Explicit org without changing shell context (safe for scripts)
        cloudctl run --org prod -- aws s3 ls
        cloudctl run --org fdr-gvc --account 111111111111 --role ReadOnly -- terraform show
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

    @staticmethod
    def _prose_for(e: "ProviderCredentialError") -> str:
        """Render a human-facing (Rich-markup) prose line for a classified
        provider credential error, keyed off its exit code so the label matches
        the faithful cause (AUTH/DENIED/NOT_FOUND/…) rather than a blanket
        'no valid SSO session'."""
        label = {
            exit_codes.AUTH: "Authentication required",
            exit_codes.DENIED: "Access denied",
            exit_codes.NOT_FOUND: "Not found",
        }.get(e.code, "Failed to get credentials")
        return f"[red]{label}:[/] {e.message}"

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
                "[bold]cloudctl run --org <org> -- <command>[/bold]",
                "No org specified and no active context",
                exit_codes.USAGE,
            )

        # Resolve the org (and provider) up front: the provider decides whether
        # --role is even meaningful (AWS: required credential selector;
        # GCP/Azure: a no-op). We must know the provider before we can render a
        # correct completeness check or a provider-aware error.
        try:
            org_data = get_org(org_name)
        except Exception:
            return self._fail(
                f"[red]Org '{org_name}' not found in config.[/]",
                f"Org '{org_name}' not found in config",
                exit_codes.NOT_FOUND,
            )

        provider_name = (
            org_data.get("provider", "aws") if isinstance(org_data, dict) else "aws"
        )

        # --role is provider-aware. AWS SSO REQUIRES a permission-set (--role) to
        # vend credentials; GCP/Azure have no runtime role assumption, so --role
        # is a no-op there and a missing role must NEVER block the command.
        role_required = provider_name == "aws"

        # When --org is given without the resolvable bits, they must be filled in.
        # cloudctl is built for agentic use, so never hang on an interactive
        # picker in a non-interactive context: if there's no TTY, fail fast with
        # an actionable, provider-aware error instead. (run/exec takes no
        # --non-interactive flag — it is non-interactive by nature; a TTY is the
        # only thing that enables the picker.)
        _needs_resolution = not account or (role_required and not role)
        if getattr(args, "exec_org", None) and _needs_resolution:
            if not sys.stdin.isatty():
                if role_required and not role:
                    return self._fail(
                        "[red]AWS requires --role.[/] Run "
                        "[bold]cloudctl roles --org "
                        f"{org_name} --account <A>[/bold] to list them "
                        "(GCP/Azure don't use --role). Provide --account, --role "
                        "and --region explicitly, e.g.:\n"
                        "  [bold]cloudctl run --org <org> --account <id> --role "
                        "<role> --region <region> -- <command>[/bold]",
                        "AWS requires --role; run 'cloudctl roles --org "
                        f"{org_name} --account <A>' to list them",
                        exit_codes.USAGE,
                    )
                return self._fail(
                    "[red]Incomplete 'run' invocation in a non-interactive "
                    "context.[/]\n"
                    "Provide --account (and --region) explicitly, e.g.:\n"
                    "  [bold]cloudctl run --org <org> --account <id> "
                    "--region <region> -- <command>[/bold]",
                    "Incomplete run invocation: --account (and --region) required",
                    exit_codes.USAGE,
                )

            import cloudctl.interactive as _interactive

            account, role, region = _interactive.run_interactive_use(
                org_data, account or None, role or None, region or None
            )
            # For AWS, account+role+region are all required; for GCP/Azure a
            # missing role does not block (role is a no-op there).
            _incomplete = not account or not region or (role_required and not role)
            if _incomplete:
                return self._fail(
                    "[red]Incomplete selection; aborting.[/]",
                    "Incomplete account/role/region selection",
                    exit_codes.USAGE,
                )

        from cloudctl.providers import get_provider

        provider = get_provider(org_data)

        # AWS with no role at this point (e.g. from context) is a teachable
        # failure: it cannot vend credentials without a permission-set.
        if role_required and not role:
            return self._fail(
                "[red]AWS requires --role.[/] Run "
                f"[bold]cloudctl roles --org {org_name} --account "
                f"{account or '<A>'}[/bold] to list them "
                "(GCP/Azure don't use --role).",
                "AWS requires --role; run 'cloudctl roles --org "
                f"{org_name} --account {account or '<A>'}' to list them",
                exit_codes.USAGE,
            )

        # Azure bare-`az` safety: cloudctl cannot inject an identity into the
        # bare `az` CLI without service-principal config — `az` always uses its
        # ambient `az login`. Warn loudly (never let it silently run under an
        # unknown identity) and, to at least pin the target, inject
        # `--subscription <account>` into the invocation when the subscription
        # is known. When SP creds ARE present, az_uses_injected_identity is True
        # and the injected AZURE_CLIENT_* env does the work — no warning.
        if (
            provider_name == "azure"
            and args.cmd
            and args.cmd[0] == "az"
            and not provider.az_uses_injected_identity(org_data)
        ):
            sys.stderr.write(
                "cloudctl: WARNING — bare `az` runs under your ambient `az login`, "
                "NOT the cloudctl-injected identity. cloudctl cannot inject an "
                "identity into the bare `az` CLI without service-principal config "
                "(client_id + client_secret + tenant_id in the org).\n"
            )
            if account and "--subscription" not in args.cmd:
                # Pin the target subscription so at least the account is explicit.
                args.cmd = [args.cmd[0], "--subscription", account] + list(
                    args.cmd[1:]
                )
                sys.stderr.write(
                    f"cloudctl: pinned target with --subscription {account}.\n"
                )

        try:
            creds = provider.get_credentials(org_data, account, role, region)
        except ProviderCredentialError as e:
            # FAITHFUL ERRORS: the provider classified the REAL cause and handed
            # up its code + message. A Forbidden now exits 4 (DENIED) with the
            # real reason instead of being flattened to "no valid SSO session"/2.
            prose = self._prose_for(e)
            return self._fail(prose, e.message, e.code)
        except SystemExit:
            # Defensive: a provider that still raises SystemExit (missing/expired
            # session) is surfaced as AUTH rather than an opaque crash.
            return self._fail(
                "[red]Authentication required:[/] no valid session. "
                "Run [bold]cloudctl login <org>[/bold].",
                "Authentication required: no valid session",
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
