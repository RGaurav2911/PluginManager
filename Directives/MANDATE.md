# PluginManager Mandate

PluginManager is a local-only dashboard for managing Codex plugin usage with lower token overhead.

## Goals

- Show all Codex plugins found in `~/.codex/config.toml`.
- Toggle plugins without manually editing config files.
- Group plugins by trusted Codex project using automated inference.
- Explain each plugin generically and per project.
- Create a backup before every config mutation.
- Require an explicit one-click restart after plugin changes.

## Non-Negotiables

- Bind the server to `127.0.0.1` only.
- Never restart Codex automatically after a toggle.
- Never edit config without creating a backup.
- Keep the UI restrained, clear, and Apple-inspired.
- Keep the app local-first and safe for public reuse.
