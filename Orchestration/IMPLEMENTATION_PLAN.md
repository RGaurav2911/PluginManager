# Implementation Plan

## V1

- Python standard-library backend served from `Execution/backend/app.py`.
- Static frontend served from `Execution/frontend/`.
- Runtime data under `Data/runtime/`.
- Backups under `Data/backups/` plus existing Codex backup directory.
- Tests under `Evaluations/tests/`.

## User Flow

1. Start server.
2. Open `http://127.0.0.1:8765`.
3. Review plugin and project inference.
4. Toggle plugins or apply profile.
5. Click restart when ready.
6. Return to lean mode after plugin-heavy work.
