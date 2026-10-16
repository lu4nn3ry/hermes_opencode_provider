"""OpenCode ACP provider profile.

OpenCode (`opencode acp`) speaks the Agent Client Protocol over stdio, so this
is an external-process provider like ``copilot-acp``: it drives a subprocess
rather than an OpenAI-over-HTTP endpoint, and supplies its own client via
:meth:`ProviderProfile.create_client`.

Dropped into ``$HERMES_HOME/plugins/model-providers/opencode-acp/`` so it needs
no core edits. ACP is vendor-neutral, so the ACP stdio shim shipped with
``copilot-acp`` (``agent.copilot_acp_client.CopilotACPClient``) drives OpenCode
unchanged.
"""

from typing import Any

from providers import register_provider
from providers.base import ProviderProfile


class OpenCodeACPProfile(ProviderProfile):
    """OpenCode ACP — external stdio process, no REST models endpoint."""

    def _resolve_command(self) -> str:
        """Binary to spawn: explicit env override, else the profile default.

        Mirrors ``agent.copilot_acp_client._resolve_command`` for our own env
        names. Needed because some agent-construction paths (notably the
        ``-z``/``--oneshot`` runner) build the client without launch kwargs,
        and the shim's built-in fallback only knows the Copilot env vars.
        """
        import os

        from hermes_cli.auth_external_process import resolve_external_process_command

        for var in self.process_command_env_vars:
            override = os.getenv(var, "").strip()
            if override:
                return resolve_external_process_command(override) or override
        return resolve_external_process_command(self.process_command) or self.process_command

    def _resolve_args(self) -> list[str]:
        """Argv tail: explicit env override (shlex-split), else the default."""
        import os
        import shlex

        raw = os.getenv(self.process_args_env_var, "").strip() if self.process_args_env_var else ""
        return shlex.split(raw) if raw else list(self.process_args)

    def create_client(self, **client_kwargs: Any) -> Any:
        """Build the ACP stdio shim rather than an HTTP client."""
        from agent.copilot_acp_client import CopilotACPClient

        kwargs = dict(client_kwargs)
        # Callers that go through credential resolution (CLI chat, auxiliary
        # tasks) already pass command/args; the --oneshot runner does not.
        if not (kwargs.get("acp_command") or kwargs.get("command")):
            kwargs["command"] = self._resolve_command()
        if not (kwargs.get("acp_args") or kwargs.get("args")):
            kwargs["args"] = self._resolve_args()
        return CopilotACPClient(**kwargs)

    def fetch_models(
        self, *, api_key: str | None = None, base_url: str | None = None, timeout: float = 15.0
    ) -> list[str] | None:
        """Enabled models advertised by a short-lived OpenCode ACP session.

        ``api_key`` / ``base_url`` are ignored: the subprocess owns auth. None
        when the CLI is missing, refuses ``acp``, or the probe fails/times out —
        callers fall back to ``fallback_models``.
        """
        from hermes_cli.auth import resolve_external_process_provider_credentials

        try:
            creds = resolve_external_process_provider_credentials(self.name)
            if not str(creds.get("base_url") or "").startswith("acp://"):
                return None
            client = self.create_client(
                api_key=creds.get("api_key"), base_url=creds.get("base_url"),
                command=creds.get("command"), args=creds.get("args"))
            return client.list_models(timeout_seconds=timeout) or None
        except Exception:
            # Missing CLI (AuthError), refused `acp` / failed spawn (RuntimeError),
            # probe timeout — the base fetch_models contract is "None if failed".
            return None


opencode_acp = OpenCodeACPProfile(
    name="opencode-acp",
    aliases=("opencode_acp",),
    display_name="OpenCode ACP",
    description="OpenCode via ACP subprocess (opencode acp)",
    api_mode="chat_completions",  # ACP subprocess uses chat_completions routing
    env_vars=(),  # Managed by the ACP subprocess
    base_url="acp://opencode",  # ACP internal scheme
    auth_type="external_process",
    # How to launch the CLI. Overridable via the env vars below.
    process_command="opencode",
    process_args=("acp",),
    process_command_env_vars=("HERMES_OPENCODE_ACP_COMMAND", "OPENCODE_CLI_PATH"),
    process_args_env_var="HERMES_OPENCODE_ACP_ARGS",
    # Shown in pickers only when the live subprocess probe fails.
    fallback_models=("opencode/big-pickle",),
)

register_provider(opencode_acp)
