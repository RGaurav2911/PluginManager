#!/usr/bin/env python3
from __future__ import annotations

import datetime as dt
import json
import os
import re
import shutil
import shlex
import subprocess
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any


APP_ROOT = Path(os.environ.get("PLUGIN_MANAGER_APP_ROOT", Path(__file__).resolve().parents[2]))
CODEX_HOME = Path(os.environ.get("PLUGIN_MANAGER_CODEX_HOME", Path.home() / ".codex"))
CONFIG_PATH = Path(os.environ.get("PLUGIN_MANAGER_CONFIG_PATH", CODEX_HOME / "config.toml"))
SESSION_DIR = CODEX_HOME / "sessions"
ARCHIVED_DIR = CODEX_HOME / "archived_sessions"
LOCAL_BACKUP_DIR = APP_ROOT / "Data" / "backups"
RUNTIME_DIR = APP_ROOT / "Data" / "runtime"
PROJECT_MAP_PATH = RUNTIME_DIR / "project_plugin_map.json"
AUDIT_PATH = RUNTIME_DIR / "audit.jsonl"
RESTART_SCRIPT_PATH = RUNTIME_DIR / "restart_codex.sh"
RESTART_LOG_PATH = Path("/tmp/codex-restart.log")


PLUGIN_DESCRIPTIONS = {
    "documents": "Creates, edits, reviews, and verifies Word and DOCX document artifacts.",
    "spreadsheets": "Creates, edits, analyzes, and verifies spreadsheet and CSV/XLSX artifacts.",
    "presentations": "Creates and edits PowerPoint/PPTX presentation decks.",
    "gmail": "Searches, summarizes, drafts, sends, and organizes Gmail through the connector.",
    "drive": "Works with Google Drive, Docs, Sheets, and Slides through the connector.",
    "remotion": "Builds programmatic videos and animations with Remotion.",
    "hyperframes": "Builds HTML-based video compositions, captions, voiceovers, and animations.",
    "canva": "Creates and edits Canva visual assets when the Canva connector is available.",
    "computer": "Controls local macOS apps visually through Computer Use.",
    "browser": "Controls the Codex in-app browser for local web testing and screenshots.",
    "chrome": "Controls the user's Chrome browser for logged-in websites and existing sessions.",
}

PLUGIN_ALIASES = {
    "documents@openai-primary-runtime": "documents",
    "spreadsheets@openai-primary-runtime": "spreadsheets",
    "presentations@openai-primary-runtime": "presentations",
    "gmail@openai-curated": "gmail",
    "google-drive@openai-curated": "drive",
    "remotion@openai-curated": "remotion",
    "hyperframes@openai-curated": "hyperframes",
    "canva@openai-curated": "canva",
    "computer-use@openai-bundled": "computer",
    "browser@openai-bundled": "browser",
    "chrome@openai-bundled": "chrome",
}

PROFILES = {
    "lean": set(),
    "all": {"__all__"},
    "login-work": {"chrome", "gmail", "drive"},
    "browser-work": {"browser"},
    "gmail": {"gmail"},
    "drive": {"drive"},
    "media": {"browser", "hyperframes", "remotion", "canva"},
    "desktop-control": {"computer", "chrome"},
}

TOOL_PLUGIN_HINTS = {
    "_send_email": "gmail",
    "_search_emails": "gmail",
    "_search_email_ids": "gmail",
    "_create_draft": "gmail",
    "click": "chrome",
    "press_key": "computer",
    "type_text": "computer",
    "set_value": "computer",
    "get_app_state": "computer",
    "view_image": "computer",
    "js": "browser",
    "imagegen": "canva",
}

KEYWORD_PLUGIN_HINTS = {
    "gmail": "gmail",
    "email": "gmail",
    "inbox": "gmail",
    "google sheet": "drive",
    "google docs": "drive",
    "google drive": "drive",
    "linkedin": "chrome",
    "inmail": "chrome",
    "chrome": "chrome",
    "localhost": "browser",
    "browser": "browser",
    "computer use": "computer",
    "desktop": "computer",
    "docx": "documents",
    "word": "documents",
    "xlsx": "spreadsheets",
    "spreadsheet": "spreadsheets",
    "ppt": "presentations",
    "deck": "presentations",
    "slides": "presentations",
    "remotion": "remotion",
    "hyperframes": "hyperframes",
    "canva": "canva",
    "video": "hyperframes",
}


@dataclass
class PluginBlock:
    plugin_id: str
    short_name: str
    enabled: bool


def ensure_dirs() -> None:
    LOCAL_BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)


def read_config() -> str:
    if not CONFIG_PATH.exists():
        raise FileNotFoundError(
            f"Codex config not found at {CONFIG_PATH}. Set PLUGIN_MANAGER_CONFIG_PATH "
            "or run Codex once to create ~/.codex/config.toml."
        )
    return CONFIG_PATH.read_text(encoding="utf-8")


def plugin_blocks(text: str | None = None) -> list[PluginBlock]:
    text = read_config() if text is None else text
    blocks = []
    pattern = re.compile(r'\[plugins\."([^"]+)"\]\n(.*?)(?=\n\[|\Z)', re.S)
    for match in pattern.finditer(text):
        plugin_id, body = match.groups()
        enabled_match = re.search(r"^enabled\s*=\s*(true|false)", body, re.M)
        short_name = PLUGIN_ALIASES.get(plugin_id, plugin_id.split("@")[0])
        blocks.append(
            PluginBlock(
                plugin_id=plugin_id,
                short_name=short_name,
                enabled=enabled_match.group(1) == "true" if enabled_match else False,
            )
        )
    return blocks


def trusted_projects(text: str | None = None) -> list[str]:
    text = read_config() if text is None else text
    return re.findall(r'\[projects\."([^"]+)"\]', text)


def backup_config(reason: str) -> Path:
    ensure_dirs()
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = LOCAL_BACKUP_DIR / f"config.{stamp}.{reason}.toml"
    shutil.copy2(CONFIG_PATH, backup)
    return backup


def audit(event: str, payload: dict[str, Any]) -> None:
    ensure_dirs()
    row = {
        "timestamp": dt.datetime.now(dt.timezone.utc).isoformat(),
        "event": event,
        "payload": payload,
    }
    with AUDIT_PATH.open("a", encoding="utf-8") as file:
        file.write(json.dumps(row, ensure_ascii=False) + "\n")


def set_plugins(enabled_short_names: set[str], reason: str) -> dict[str, Any]:
    text = read_config()
    backup = backup_config(reason)
    missing = []

    def replace(match: re.Match[str]) -> str:
        plugin_id, body = match.groups()
        short_name = PLUGIN_ALIASES.get(plugin_id, plugin_id.split("@")[0])
        value = "true" if short_name in enabled_short_names else "false"
        if re.search(r"^enabled\s*=", body, re.M):
            body = re.sub(r"^enabled\s*=\s*(true|false)", f"enabled = {value}", body, flags=re.M)
        else:
            body = f"enabled = {value}\n{body}"
        return f'[plugins."{plugin_id}"]\n{body}'

    pattern = re.compile(r'\[plugins\."([^"]+)"\]\n(.*?)(?=\n\[|\Z)', re.S)
    new_text = pattern.sub(replace, text)
    seen = {block.short_name for block in plugin_blocks(text)}
    for name in enabled_short_names:
        if name not in seen:
            missing.append(name)
    CONFIG_PATH.write_text(new_text, encoding="utf-8")
    audit("plugins_updated", {"enabled": sorted(enabled_short_names), "backup": str(backup), "missing": missing})
    return {"backup": str(backup), "missing": missing, "restartRequired": True}


def toggle_plugin(short_name: str, enabled: bool) -> dict[str, Any]:
    current = {block.short_name for block in plugin_blocks() if block.enabled}
    if enabled:
        current.add(short_name)
    else:
        current.discard(short_name)
    return set_plugins(current, f"toggle-{short_name}")


def apply_profile(profile: str) -> dict[str, Any]:
    if profile not in PROFILES:
        raise ValueError(f"Unknown profile: {profile}")
    available = {block.short_name for block in plugin_blocks()}
    enabled = available if "__all__" in PROFILES[profile] else {name for name in PROFILES[profile] if name in available}
    result = set_plugins(enabled, f"profile-{profile}")
    result["profile"] = profile
    return result


def session_files() -> list[Path]:
    files = []
    if SESSION_DIR.exists():
        files.extend(SESSION_DIR.glob("**/*.jsonl"))
    if ARCHIVED_DIR.exists():
        files.extend(ARCHIVED_DIR.glob("*.jsonl"))
    return sorted(set(files))


def project_text_sample(project: str) -> str:
    snippets = []
    for name in ("AGENTS.md", "CLAUDE.md", "README.md", "package.json", "pyproject.toml"):
        path = Path(project) / name
        if path.exists() and path.is_file():
            try:
                snippets.append(path.read_text(encoding="utf-8", errors="ignore")[:20000])
            except OSError:
                pass
    return "\n".join(snippets).lower()


def infer_project_plugins() -> list[dict[str, Any]]:
    projects = set(trusted_projects())
    tool_counts: dict[str, Counter[str]] = defaultdict(Counter)
    token_counts: Counter[str] = Counter()
    evidence: dict[str, dict[str, list[str]]] = defaultdict(lambda: defaultdict(list))

    for file_path in session_files():
        cwd = ""
        latest_tokens = 0
        try:
            with file_path.open("r", encoding="utf-8") as file:
                for line in file:
                    item = json.loads(line)
                    payload = item.get("payload") or {}
                    if item.get("type") == "session_meta" and payload.get("cwd"):
                        cwd = payload["cwd"]
                        projects.add(cwd)
                    if item.get("type") == "event_msg" and (payload.get("info") or {}).get("total_token_usage"):
                        latest_tokens = payload["info"]["total_token_usage"].get("total_tokens", latest_tokens)
                    if item.get("type") == "response_item" and payload.get("type") == "function_call" and cwd:
                        tool = payload.get("name") or "unknown"
                        tool_counts[cwd][tool] += 1
        except (OSError, json.JSONDecodeError):
            continue
        if cwd and latest_tokens:
            token_counts[cwd] += latest_tokens

    rows = []
    for project in sorted(projects):
        plugin_scores = Counter()
        project_evidence: dict[str, list[str]] = defaultdict(list)
        for tool, count in tool_counts[project].items():
            plugin = TOOL_PLUGIN_HINTS.get(tool)
            if plugin:
                plugin_scores[plugin] += count * 3
                project_evidence[plugin].append(f"{tool} used {count} times")

        text = project_text_sample(project)
        for keyword, plugin in KEYWORD_PLUGIN_HINTS.items():
            hits = text.count(keyword)
            if hits:
                plugin_scores[plugin] += min(hits, 10)
                project_evidence[plugin].append(f"keyword '{keyword}' found {hits} times")

        plugins = []
        for plugin, score in plugin_scores.most_common():
            confidence = "high" if score >= 30 else "medium" if score >= 8 else "low"
            plugins.append({
                "name": plugin,
                "confidence": confidence,
                "score": score,
                "description": project_plugin_description(project, plugin),
                "evidence": project_evidence[plugin][:5],
            })
        rows.append({
            "project": project,
            "plugins": plugins,
            "toolCounts": dict(tool_counts[project].most_common(12)),
            "tokenUsage": token_counts[project],
        })

    PROJECT_MAP_PATH.write_text(json.dumps(rows, indent=2), encoding="utf-8")
    audit("project_map_refreshed", {"projectCount": len(rows)})
    return rows


def project_plugin_description(project: str, plugin: str) -> str:
    name = Path(project).name or project
    descriptions = {
        "gmail": f"In {name}, this is likely used for inbox checks, reply drafting, email search, or send logging.",
        "drive": f"In {name}, this is likely used for Google Drive, Docs, Sheets, or shared file workflows.",
        "chrome": f"In {name}, this is likely used for logged-in browser work such as LinkedIn or authenticated web tasks.",
        "browser": f"In {name}, this is likely used for local web app testing, screenshots, or browser automation.",
        "computer": f"In {name}, this is likely used for visual desktop control, app-state checks, or fallback automation.",
        "documents": f"In {name}, this is likely used for Word or DOCX artifact work.",
        "spreadsheets": f"In {name}, this is likely used for CSV/XLSX analysis or spreadsheet artifacts.",
        "presentations": f"In {name}, this is likely used for slide deck or PPTX work.",
        "remotion": f"In {name}, this is likely used for React-based video generation.",
        "hyperframes": f"In {name}, this is likely used for HTML video composition or animation work.",
        "canva": f"In {name}, this is likely used for Canva design asset creation or editing.",
    }
    return descriptions.get(plugin, f"In {name}, this plugin appears relevant based on project evidence.")


def load_project_map(refresh: bool = False) -> list[dict[str, Any]]:
    ensure_dirs()
    if refresh or not PROJECT_MAP_PATH.exists():
        return infer_project_plugins()
    return json.loads(PROJECT_MAP_PATH.read_text(encoding="utf-8"))


def backups() -> list[dict[str, Any]]:
    ensure_dirs()
    rows = []
    for path in sorted(LOCAL_BACKUP_DIR.glob("config.*.toml"), reverse=True):
        rows.append({
            "name": path.name,
            "path": str(path),
            "size": path.stat().st_size,
            "modified": dt.datetime.fromtimestamp(path.stat().st_mtime).isoformat(),
        })
    return rows


def restore_backup(name: str) -> dict[str, Any]:
    choices = backups()
    if not choices:
        raise ValueError("No backups available")
    selected = choices[0] if name == "latest" else next((item for item in choices if item["name"] == name), None)
    if not selected:
        raise ValueError(f"Backup not found: {name}")
    safety = backup_config("before-restore")
    shutil.copy2(selected["path"], CONFIG_PATH)
    audit("backup_restored", {"restored": selected["path"], "safetyBackup": str(safety)})
    return {"restored": selected, "safetyBackup": str(safety), "restartRequired": True}


def audit_events(limit: int = 100) -> list[dict[str, Any]]:
    if not AUDIT_PATH.exists():
        return []
    lines = AUDIT_PATH.read_text(encoding="utf-8").splitlines()[-limit:]
    rows = []
    for line in lines:
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            pass
    return list(reversed(rows))


def restart_script() -> str:
    log_path = shlex.quote(str(RESTART_LOG_PATH))
    return f"""#!/usr/bin/env bash
set +e

LOG={log_path}

{{
  echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] Codex restart requested"
  sleep 1

  osascript <<'OSA'
on clickIfExists(buttonName)
  tell application "System Events"
    if not (exists process "Codex") then return false
    tell process "Codex"
      repeat with targetWindow in windows
        try
          if exists button buttonName of targetWindow then
            click button buttonName of targetWindow
            return true
          end if
        end try
      end repeat
    end tell
  end tell
  return false
end clickIfExists

try
  ignoring application responses
    tell application "Codex" to quit
  end ignoring
end try

repeat 24 times
  try
    if clickIfExists("Quit") then exit repeat
    if clickIfExists("OK") then exit repeat
    if clickIfExists("Continue") then exit repeat
    if clickIfExists("Close") then exit repeat
    if clickIfExists("Yes") then exit repeat
  end try
  delay 0.5
end repeat
OSA

  for i in {{1..24}}; do
    if ! pgrep -x "Codex" >/dev/null 2>&1; then
      break
    fi
    sleep 0.5
  done

  if pgrep -x "Codex" >/dev/null 2>&1; then
    echo "Codex still running after quit confirmation attempt; terminating."
    pkill -x "Codex"
    sleep 1
  fi

  open -a "Codex"

  for i in {{1..20}}; do
    if pgrep -x "Codex" >/dev/null 2>&1; then
      echo "Codex relaunched."
      exit 0
    fi
    sleep 0.5
  done

  echo "Codex relaunch was requested, but the process was not observed."
  exit 1
}} >> "$LOG" 2>&1
"""


def restart_codex(dry_run: bool = False) -> dict[str, Any]:
    ensure_dirs()
    script = restart_script()
    RESTART_SCRIPT_PATH.write_text(script, encoding="utf-8")
    RESTART_SCRIPT_PATH.chmod(0o700)
    command = f"nohup {shlex.quote(str(RESTART_SCRIPT_PATH))} >/dev/null 2>&1 &"
    audit("restart_requested", {
        "dryRun": dry_run,
        "script": str(RESTART_SCRIPT_PATH),
        "log": str(RESTART_LOG_PATH),
    })
    if not dry_run:
        subprocess.Popen(command, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return {
        "scheduled": not dry_run,
        "script": str(RESTART_SCRIPT_PATH),
        "log": str(RESTART_LOG_PATH),
    }


def state(refresh_projects: bool = False) -> dict[str, Any]:
    blocks = plugin_blocks()
    enabled = [block.short_name for block in blocks if block.enabled]
    available = {block.short_name for block in blocks}
    profile_view = {
        name: sorted(available if "__all__" in values else values)
        for name, values in PROFILES.items()
    }
    return {
        "configPath": str(CONFIG_PATH),
        "plugins": [{
            "id": block.plugin_id,
            "name": block.short_name,
            "enabled": block.enabled,
            "description": PLUGIN_DESCRIPTIONS.get(block.short_name, "Codex plugin."),
        } for block in blocks],
        "enabledPlugins": enabled,
        "profiles": profile_view,
        "projects": load_project_map(refresh=refresh_projects),
        "backups": backups(),
        "audit": audit_events(40),
    }
