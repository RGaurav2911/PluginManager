# PluginManager

PluginManager is a local dashboard for managing Codex plugins and understanding which projects consume plugin-heavy workflows and tokens.

It reads your local Codex config, shows available plugins, lets you toggle them with backups, applies common plugin profiles, and infers project-to-plugin usage from Codex session history.

## Features

- Toggle Codex plugins from a local web dashboard.
- Create a timestamped backup before every config change.
- Apply profiles such as lean, browser work, login work, media, and all plugins.
- Infer project plugin needs from trusted projects, session tool calls, keywords, and observed token usage.
- Review recent local audit events.
- Restart Codex manually after config changes.

## Safety model

- The server binds to `127.0.0.1` only.
- Plugin changes are never applied without first backing up the current config.
- Codex is not restarted automatically after a toggle; restart is an explicit button.
- Runtime data and backups stay local under `Data/` and are ignored by Git.

## Requirements

- Python 3.9 or newer.
- Codex installed and run at least once so `~/.codex/config.toml` exists.

No third-party Python packages are required.

## Quick start

```bash
git clone https://github.com/RGaurav2911/PluginManager.git
cd PluginManager
chmod +x run.sh
./run.sh
```

Then open:

```text
http://127.0.0.1:8765
```

## Configuration

PluginManager uses these default paths:

- Codex config: `~/.codex/config.toml`
- Codex sessions: `~/.codex/sessions`
- Archived sessions: `~/.codex/archived_sessions`
- Local backups: `Data/backups/`
- Local runtime cache and audit log: `Data/runtime/`

You can override paths with environment variables:

```bash
PLUGIN_MANAGER_CONFIG_PATH=/path/to/config.toml ./run.sh
PLUGIN_MANAGER_CODEX_HOME=/path/to/.codex ./run.sh
PLUGIN_MANAGER_APP_ROOT=/path/to/PluginManager ./run.sh
PLUGIN_MANAGER_PORT=8770 ./run.sh
PLUGIN_MANAGER_HOST=127.0.0.1 ./run.sh
```

Keep `PLUGIN_MANAGER_HOST` on `127.0.0.1` unless you have reviewed the security implications of exposing a local config editor on your network.

## Testing

```bash
python3 -m unittest discover -s Evaluations/tests
```

## Repository layout

```text
Execution/backend/      Python standard-library API server and plugin logic
Execution/frontend/     Static dashboard UI
Documentation/          User-facing docs
Directives/             Product/design notes
Evaluations/tests/      Unit tests
Evaluations/fixtures/   Sample config fixtures
Data/                   Local runtime folders; generated contents are ignored
```

## Publishing notes

Before pushing a public copy, replace `YOUR_USERNAME` in the clone URL above and choose the final GitHub repository name. Generated files under `Data/backups/` and `Data/runtime/` should remain untracked.
