#!/usr/bin/env python3
"""Offline end-to-end generator checks using a real pinned local Git submodule."""

import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


def git(path, *args):
    result = subprocess.run(
        ["git", *args], cwd=path, capture_output=True, text=True, check=False,
    )
    if result.returncode:
        raise AssertionError(f"git {args}: {result.stderr}")
    return result.stdout.strip()


def init_repo(path):
    path.mkdir(parents=True)
    git(path, "init", "-q")
    git(path, "config", "user.name", "Scaffold Test")
    git(path, "config", "user.email", "scaffold@example.invalid")


def commit(path, message):
    git(path, "add", "-A")
    git(path, "commit", "-q", "-m", message)


class InitTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="sentinel-init-")
        self.addCleanup(self.tmp.cleanup)
        base = Path(self.tmp.name)
        tool_source = base / "sentinel-src"
        self.repo = base / "consumer"
        self.project = self.repo / "projects/demo"
        init_repo(tool_source)
        scripts = tool_source / "scripts"
        scripts.mkdir()
        current = Path(__file__).resolve().parent
        for name in (
            "sentinel.py", "sentinel_init.py", "sentinel_doctor.py",
            "workspace_context.py", "source_closure.py", "producer_config.py",
        ):
            shutil.copy2(current / name, scripts / name)
        (scripts / "run_portable_direct.py").write_text(
            "# tool identity marker\n", encoding="utf-8",
        )
        commit(tool_source, "pinned generator source")

        init_repo(self.repo)
        (self.project / "test").mkdir(parents=True)
        (self.project / "test/.gitkeep").write_text("", encoding="utf-8")
        (self.project / "foundry.toml").write_text(
            "[profile.default]\n", encoding="utf-8",
        )
        commit(self.repo, "consumer fixture")
        git(
            self.repo, "-c", "protocol.file.allow=always",
            "submodule", "add", "-q", str(tool_source),
            "projects/demo/lib/protocol-sentinel",
        )
        commit(self.repo, "pin Sentinel tool")
        self.cli = self.project / "lib/protocol-sentinel/scripts/sentinel.py"

    def command(self, *extra):
        return subprocess.run(
            [sys.executable, "-B", str(self.cli), "init",
             "--route", "direct-uups", "--project", str(self.project), *extra],
            capture_output=True, text=True, check=False,
        )

    def test_dry_run_creates_nothing_and_index_unchanged(self):
        head = git(self.repo, "status", "--porcelain")
        result = self.command("--dry-run")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("WOULD CREATE", result.stdout)
        self.assertEqual(head, git(self.repo, "status", "--porcelain"))
        self.assertFalse((self.project / "sentinel.toml").exists())
        self.assertFalse((self.project / "test/SentinelAuthorityProducer.t.sol").exists())

    def test_created_fixture_is_incomplete_and_consistent(self):
        result = self.command()
        self.assertEqual(result.returncode, 0, result.stderr)
        code = (self.project / "test/SentinelAuthorityProducer.t.sol").read_text()
        config = (self.project / "sentinel.toml").read_text()
        self.assertIn("revert SentinelFixtureIncomplete();", code)
        self.assertIn("test_ProduceSentinelAuthorityComparison()", code)
        self.assertIn("SCENARIO_ID", code)
        self.assertIn("test_ProduceSentinelAuthorityComparison", config)
        self.assertIn('"0x' + "0" * 63 + '1"', config)
        self.assertFalse((self.project / "artifacts").exists())

    def test_repeat_invocation_is_refused_without_changes(self):
        self.assertEqual(self.command().returncode, 0)
        source = self.project / "test/SentinelAuthorityProducer.t.sol"
        original = source.read_bytes()
        retry = self.command()
        self.assertNotEqual(retry.returncode, 0)
        self.assertIn("Refusing to overwrite", retry.stderr)
        self.assertEqual(original, source.read_bytes())

    def test_existing_config_collision_does_not_write_source(self):
        (self.project / "sentinel.toml").write_text("# existing\n")
        result = self.command()
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.project / "test/SentinelAuthorityProducer.t.sol").exists())

    def test_missing_test_directory_fails_without_side_effects(self):
        (self.project / "test/.gitkeep").unlink()
        (self.project / "test").rmdir()
        result = self.command()
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.project / "sentinel.toml").exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
