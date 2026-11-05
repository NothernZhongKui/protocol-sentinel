#!/usr/bin/env python3
"""Offline, temporary-Git-repository checks for read-only Sentinel doctor."""

import io
import os
import subprocess
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from producer_config import read_config
from sentinel_doctor import inspect, main

CONFIG = """[sentinel]
config_version = "1"
route = "DIRECT_EOA_UUPS"

[producer]
id = "sample"
contract = "SampleProducerTest"
test = "test_Produce"
source = "test/SampleProducer.t.sol"
fixture_id = "sample-v1"
scenario_id = "0x" + "a" * 64
"""
# Use an actual TOML literal, not a Python expression.
CONFIG = CONFIG.replace('"0x" + "a" * 64', '"' + '0x' + 'a' * 64 + '"')


def git(cwd, *args):
    result = subprocess.run(
        ["git", *args], cwd=cwd, text=True, capture_output=True,
        check=False,
    )
    if result.returncode:
        raise AssertionError(f"git {args}: {result.stderr}")
    return result.stdout.strip()


def init(path):
    path.mkdir(parents=True)
    git(path, "init", "-q")
    git(path, "config", "user.name", "Doctor Tests")
    git(path, "config", "user.email", "doctor@example.invalid")


def commit(path, message):
    git(path, "add", "-A")
    git(path, "commit", "-q", "-m", message)


class DoctorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="sentinel-doctor-")
        self.addCleanup(self.temp.cleanup)
        base = Path(self.temp.name)
        self.tool_source = base / "tool-source"
        self.repo = base / "consumer"
        self.project = self.repo / "projects/demo"
        init(self.tool_source)
        (self.tool_source / "scripts").mkdir()
        (self.tool_source / "scripts/run_portable_direct.py").write_text(
            "# marker for pinned Sentinel fixture\n", encoding="utf-8"
        )
        commit(self.tool_source, "tool fixture")
        init(self.repo)
        self.project.mkdir(parents=True)
        (self.project / "test").mkdir()
        (self.project / "foundry.toml").write_text(
            '[profile.default]\nfs_permissions = [{ access = "read-write", path = "artifacts/sentinel/runs" }]\n',
            encoding="utf-8",
        )
        (self.repo / ".gitignore").write_text(
            "projects/demo/artifacts/sentinel/runs/\n", encoding="utf-8",
        )
        (self.project / "test/SampleProducer.t.sol").write_text(
            "// tracked fixture\n", encoding="utf-8",
        )
        (self.project / "sentinel.toml").write_text(CONFIG, encoding="utf-8")
        commit(self.repo, "consumer fixture")
        git(
            self.repo, "-c", "protocol.file.allow=always",
            "submodule", "add", "-q", str(self.tool_source),
            "projects/demo/lib/protocol-sentinel",
        )
        commit(self.repo, "pinned sentinel")
        self.tool = self.project / "lib/protocol-sentinel"
        self.solc = base / "solc-0.8.26"
        self.solc.write_text(
            "#!/bin/sh\nprintf '%s\\n' 'solc, the solidity compiler' 'Version: 0.8.26+commit.8a97fa7a.Linux.g++'\n",
            encoding="utf-8",
        )
        self.solc.chmod(0o755)

    def rows(self, solc=None):
        with patch("shutil.which", return_value="/fake/forge"):
            return inspect(
                self.project, self.tool, "sentinel.toml",
                self.solc if solc is None else solc,
            )

    def test_clean_nested_workspace_no_mutations(self):
        before = git(self.repo, "status", "--porcelain", "--untracked-files=all")
        rows = self.rows()
        self.assertEqual([], [x for x in rows if x[0] == "FAIL"], rows)
        self.assertTrue(any("gitlink verified" in x[1] for x in rows))
        self.assertTrue(any("tracked Git blobs" in x[1] for x in rows))
        self.assertTrue(any(x[0] == "DEFERRED" and "source closure" in x[1] for x in rows))
        self.assertEqual(before, git(self.repo, "status", "--porcelain", "--untracked-files=all"))
        self.assertFalse((self.project / "artifacts").exists())

    def test_missing_foundry_permission(self):
        (self.project / "foundry.toml").write_text("[profile.default]\n", encoding="utf-8")
        self.assertTrue(any(s == "FAIL" and "fs_permissions" in m for s, m in self.rows()))

    def test_dirty_producer_is_not_attested(self):
        (self.project / "test/SampleProducer.t.sol").write_text("// changed\n", encoding="utf-8")
        rows = self.rows()
        self.assertTrue(any(s == "WARN" and "changes" in m for s, m in rows))
        self.assertTrue(any(s == "FAIL" and "tracked" in m.lower() for s, m in rows))

    def test_missing_or_modified_tool_is_not_accepted(self):
        (self.tool / "untracked.py").write_text("# dirty\n", encoding="utf-8")
        rows = self.rows()
        self.assertTrue(any(s == "FAIL" and "gitlink" in m.lower() for s, m in rows))

    def test_missing_source_is_reported(self):
        (self.project / "test/SampleProducer.t.sol").unlink()
        self.assertTrue(any(s == "FAIL" and "source missing" in m for s, m in self.rows()))

    def test_unusable_solc_is_reported(self):
        rows = self.rows(solc=Path(self.temp.name) / "missing-solc")
        self.assertTrue(any(s == "FAIL" and "--solc" in m for s, m in rows))

    def test_ignored_output_required(self):
        (self.repo / ".gitignore").write_text("", encoding="utf-8")
        self.assertTrue(any(s == "FAIL" and "Git-ignored" in m for s, m in self.rows()))

    def test_invalid_producer_config_not_accepted(self):
        (self.project / "sentinel.toml").write_text(
            CONFIG.replace("DIRECT_EOA_UUPS", "UNSUPPORTED_ROUTE"), encoding="utf-8",
        )
        self.assertTrue(any(s == "FAIL" and "configuration" in m for s, m in self.rows()))

    def test_main_does_not_claim_ci_approval(self):
        output = io.StringIO()
        with patch("shutil.which", return_value="/fake/forge"), redirect_stdout(output):
            status = main([
                "--project", str(self.project),
                "--solc", str(self.solc),
            ])
        self.assertEqual(0, status, output.getvalue())
        self.assertIn("NOT A CI APPROVAL", output.getvalue())
        self.assertIn("NO KNOWN BLOCKERS", output.getvalue())

    def test_producer_parser_rejects_untrusted_extra_field(self):
        config = self.project / "sentinel.toml"
        config.write_text(CONFIG + '\nextra = "not allowed"\n', encoding="utf-8")
        with self.assertRaises(ValueError):
            read_config(config)


if __name__ == "__main__":
    unittest.main(verbosity=2)
