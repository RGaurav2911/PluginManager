from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "Execution" / "backend" / "plugin_manager.py"
spec = importlib.util.spec_from_file_location("plugin_manager", MODULE_PATH)
manager = importlib.util.module_from_spec(spec)
assert spec and spec.loader
sys.modules["plugin_manager"] = manager
spec.loader.exec_module(manager)


SAMPLE_CONFIG = """
model = "gpt-5.5"

[plugins."gmail@openai-curated"]
enabled = false

[plugins."chrome@openai-bundled"]
enabled = true

[plugins."browser@openai-bundled"]
enabled = false

[plugins."computer-use@openai-bundled"]
enabled = false

[projects."/Users/example/LeadFinder"]
trust_level = "trusted"

[projects."/Users/example/App"]
trust_level = "trusted"
""".lstrip()


class PluginManagerTests(unittest.TestCase):
    def test_plugin_blocks(self) -> None:
        blocks = manager.plugin_blocks(SAMPLE_CONFIG)
        states = {block.short_name: block.enabled for block in blocks}
        self.assertEqual(states["gmail"], False)
        self.assertEqual(states["chrome"], True)
        self.assertEqual(states["browser"], False)
        self.assertEqual(states["computer"], False)

    def test_trusted_projects(self) -> None:
        projects = manager.trusted_projects(SAMPLE_CONFIG)
        self.assertEqual(projects, ["/Users/example/LeadFinder", "/Users/example/App"])

    def test_set_plugins_creates_backup_and_updates_config(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            config = temp / "config.toml"
            config.write_text(SAMPLE_CONFIG, encoding="utf-8")
            old_config = manager.CONFIG_PATH
            old_backup = manager.LOCAL_BACKUP_DIR
            old_audit = manager.AUDIT_PATH
            try:
                manager.CONFIG_PATH = config
                manager.LOCAL_BACKUP_DIR = temp / "backups"
                manager.AUDIT_PATH = temp / "audit.jsonl"
                result = manager.set_plugins({"gmail"}, "test")
                text = config.read_text(encoding="utf-8")
                self.assertIn('[plugins."gmail@openai-curated"]\nenabled = true', text)
                self.assertIn('[plugins."chrome@openai-bundled"]\nenabled = false', text)
                self.assertTrue(Path(result["backup"]).exists())
                self.assertTrue(result["restartRequired"])
            finally:
                manager.CONFIG_PATH = old_config
                manager.LOCAL_BACKUP_DIR = old_backup
                manager.AUDIT_PATH = old_audit

    def test_project_plugin_description(self) -> None:
        text = manager.project_plugin_description("/Users/example/LeadFinder", "chrome")
        self.assertIn("logged-in browser work", text)


if __name__ == "__main__":
    unittest.main()
