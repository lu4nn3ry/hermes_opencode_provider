# Hermes × OpenCode ACP Provider

Registers OpenCode as a Hermes model provider through the
[Agent Client Protocol](https://agentclientprotocol.com): Hermes drives the
`opencode acp` subprocess over stdio instead of an HTTP endpoint — the same
shape as the bundled `copilot-acp` provider, but as an out-of-tree plugin, so
no Hermes core edits are needed.

## Install

```bash
hermes plugins install lu4nn3ry/hermes_opencode_provider
```

Restart any long-running Hermes process (Desktop app, `hermes serve`,
gateway) so it imports the plugin. Then:

```bash
hermes model            # pick "OpenCode ACP"
# or pin it directly
hermes config set model.provider opencode-acp
hermes config set model.base_url acp://opencode
hermes config set model.default "opencode/muse-spark-1.3-contributor-free"
```

## Requirements

- OpenCode on `PATH` (`opencode --version`), or point one of the override
  env vars below at the binary.
- OpenCode authenticated (`opencode auth login` / `opencode auth list` shows
  at least one provider). `hermes auth status opencode-acp` reports
  structural availability (binary resolves); the subprocess owns real auth.

## Current config (verified 2026-10-16)

- Hermes Agent `v0.22.2` (stable), OpenCode `v2.0.30`,
  `@opencode-ai/plugin@1.18.33`.
- Hermes model: `provider: opencode-acp`, `base_url: acp://opencode`,
  live model `opencode/muse-spark-1.3-contributor-free`
  (fallback `opencode/big-pickle` — both advertised by `opencode models`).
- OpenCode auth: OpenAI (OAuth, stored), OpenRouter (stored),
  Anthropic + Nvidia (env keys).
- `~/.config/opencode/opencode.jsonc` is schema-only (`{}`); `cli.json`
  sets `session.permissions: autoaccept`, `session.thinking: hide`.
- Plugin lives in `$HERMES_HOME/plugins/model-providers/opencode-acp/`;
  after pulling, reinstall or restart Hermes so the new
  `fallback_models` take effect.

## Overrides

| Env var | Purpose | Default |
|---|---|---|
| `HERMES_OPENCODE_ACP_COMMAND` | Path to the `opencode` binary | `opencode` on `PATH` |
| `OPENCODE_CLI_PATH` | Fallback path to the `opencode` binary | — |
| `HERMES_OPENCODE_ACP_ARGS` | Override argv (shlex-split) | `acp` |

## How it works

`providers/__init__.py` discovers this directory (a `kind: model-provider`
plugin) and the profile's `create_client()` returns the bundled ACP stdio
shim (`agent.copilot_acp_client.CopilotACPClient`), which is protocol-generic:
`initialize` → `session/new` → `session/set_config_option` (model) →
`session/prompt`, with the `fs/read_text_file` / `fs/write_text_file`
bridge and permission requests answered. Because some agent-construction
paths (notably `-z`/`--oneshot` and mid-session `/model` switches) build the
client without launch kwargs — where the shim's built-in fallback only knows
the Copilot binary — `create_client()` self-resolves the OpenCode command and
args from the profile before constructing the client.

`fetch_models()` probes a short-lived authenticated ACP session and falls back
to `fallback_models` when the CLI is missing or the probe fails.
