# Security

PluginManager edits a local Codex configuration file, so treat it as a local-only utility.

## Defaults

- The server binds to `127.0.0.1`.
- Runtime data and backups are written under `Data/`.
- Generated runtime files are ignored by Git.

## Recommendations

- Do not expose the dashboard on a public network.
- Review any generated backup before sharing logs or support bundles.
- Keep `~/.codex/config.toml` private if it contains local project paths or plugin settings you do not want to publish.

## Reporting

Open a GitHub issue with a minimal reproduction. Do not include secrets, private config files, or session logs.
