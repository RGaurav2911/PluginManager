# PluginManager User Guide

## Requirements

- macOS, Linux, or Windows with Python 3.9+.
- Codex installed and run at least once so `~/.codex/config.toml` exists.

## Start the dashboard

From the repository root:

```bash
./run.sh
```

Open:

```text
http://127.0.0.1:8765
```

Use `Lean` for lowest token usage. Use `All` only when you need every plugin available.

After any plugin change, click `Restart Codex` for the change to load.

## Optional paths

By default, PluginManager reads `~/.codex/config.toml` and stores local runtime data under `Data/`.
You can override these paths:

```bash
PLUGIN_MANAGER_CONFIG_PATH=/path/to/config.toml ./run.sh
PLUGIN_MANAGER_CODEX_HOME=/path/to/.codex ./run.sh
PLUGIN_MANAGER_APP_ROOT=/path/to/PluginManager ./run.sh
PLUGIN_MANAGER_PORT=8770 ./run.sh
PLUGIN_MANAGER_HOST=127.0.0.1 ./run.sh
```

Keep `PLUGIN_MANAGER_HOST` on `127.0.0.1` unless you have reviewed the security implications of exposing a local config editor on your network.

## Data written locally

- `Data/backups/`: timestamped config backups before every plugin change.
- `Data/runtime/`: audit events, project inference cache, and the generated restart script.

These files are intentionally ignored by Git.
