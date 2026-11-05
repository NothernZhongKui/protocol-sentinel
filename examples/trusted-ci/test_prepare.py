#!/usr/bin/env python3
"""Offline adversarial controls for the protected-base CI preflight."""

import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from prepare import PreparationError, prepare


def git(root, *args):
    p = subprocess.run(["git", *args], cwd=root, text=True, capture_output=True)
    if p.returncode:
        raise AssertionError(f"git {args}: {p.stderr}")
    return p.stdout.strip()


def init(path):
    path.mkdir(parents=True)
    git(path, "init", "-q")
    git(path, "config", "user.name", "Trusted CI Test")
    git(path, "config", "user.email", "ci@example.invalid")


def commit(path, msg):
    git(path, "add", "-A")
    git(path, "commit", "-q", "-m", msg)


class TrustedPreparationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="trusted-ci-preflight-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.tool_repo = self.root / "tool-src"
        self.base = self.root / "trusted-base"
        self.consumer = self.root / "consumer"
        self.output = self.root / "runtime-policy.toml"
        init(self.tool_repo)
        (self.tool_repo / "scripts").mkdir()
        (self.tool_repo / "scripts/run_workspace_direct.py").write_text(
            "# pinned Sentinel candidate entrypoint\n", encoding="utf-8")
        commit(self.tool_repo, "tool")
        self.tool_sha = git(self.tool_repo, "rev-parse", "HEAD")

        init(self.consumer)
        (self.consumer / "foundry.toml").write_text(
            "[profile.default]\n", encoding="utf-8")
        commit(self.consumer, "foundry fixture")
        git(self.consumer, "-c", "protocol.file.allow=always",
            "submodule", "add", "-q", str(self.tool_repo), "lib/protocol-sentinel")
        commit(self.consumer, "pin tool")
        self.consumer_sha = git(self.consumer, "rev-parse", "HEAD")

        init(self.base)
        (self.base / "policy").mkdir()
        self.policy = self.base / "policy/trusted-policy.toml"
        self.policy.write_text(
            '[policy]\n'
            'version = "2"\n'
            'repository = "owner/consumer"\n'
            'consumer_repository = "owner/consumer"\n'
            'consumer_commit = "' + "0" * 40 + '"\n'
            'workspace = "."\n'
            'workflow = ".github/workflows/sentinel-gate.yml"\n'
            'tool_commit = "' + self.tool_sha + '"\n\n'
            '[[required_scenario]]\n'
            'id = "upgrade"\n'
            'scenario_id = "0x' + "a" * 64 + '"\n'
            'route = "DIRECT_EOA_UUPS"\n'
            'source = "test/Producer.t.sol"\n'
            'contract = "ProducerTest"\n'
            'test = "test_Produce"\n'
            'fixture_id = "v1-to-v2"\n',
            encoding="utf-8",
        )
        commit(self.base, "trusted policy")
        self.base_sha = git(self.base, "rev-parse", "HEAD")
        self.env = {
            "GITHUB_REPOSITORY": "owner/consumer",
            "GITHUB_WORKFLOW_REF": "owner/consumer/.github/workflows/sentinel-gate.yml@refs/pull/1/merge",
            "GITHUB_RUN_ID": "4242",
            "GITHUB_RUN_ATTEMPT": "1",
        }

    def execute(self, *, output=None, base_sha=None, env=None):
        return prepare(self.base, self.consumer, self.policy,
                       self.output if output is None else output,
                       self.base_sha if base_sha is None else base_sha,
                       self.env if env is None else env)

    def test_success_exact_gitlink_and_current_commit(self):
        result = self.execute()
        self.assertEqual(result["consumer_sha"], self.consumer_sha)
        self.assertEqual(result["tool_sha"], self.tool_sha)
        self.assertIn(self.consumer_sha, self.output.read_text())
        self.assertNotIn('consumer_commit = "' + "0" * 40 + '"',
                         self.output.read_text())
        self.assertEqual(git(self.consumer, "status", "--porcelain"), "")
        self.assertEqual(git(self.base, "status", "--porcelain"), "")

    def test_reject_overwrite(self):
        self.execute()
        with self.assertRaisesRegex(PreparationError, "overwrite"):
            self.execute()

    def test_reject_modified_base_policy(self):
        self.policy.write_text(self.policy.read_text() + "\n# altered")
        with self.assertRaisesRegex(PreparationError, "Protected base checkout"):
            self.execute()

    def test_reject_untrusted_tool_checkout(self):
        tool = self.consumer / "lib/protocol-sentinel"
        (tool / "scripts/run_workspace_direct.py").write_text("# modified")
        with self.assertRaisesRegex(PreparationError, "Installed Sentinel checkout modified"):
            self.execute()

    def test_reject_changed_candidate_gitlink(self):
        tool = self.consumer / "lib/protocol-sentinel"
        git(tool, "config", "user.name", "CI Test")
        git(tool, "config", "user.email", "ci@example.invalid")
        (tool / "new.txt").write_text("changed")
        commit(tool, "unapproved tool revision")
        commit(self.consumer, "candidate swaps Sentinel revision")
        with self.assertRaisesRegex(PreparationError, "gitlink not approved"):
            self.execute()

    def test_reject_wrong_base_revision(self):
        with self.assertRaisesRegex(PreparationError, "base checkout SHA"):
            self.execute(base_sha="f" * 40)

    def test_reject_wrong_workflow_context(self):
        env = dict(self.env)
        env["GITHUB_WORKFLOW_REF"] = "owner/consumer/.github/workflows/other.yml@refs/heads/main"
        with self.assertRaisesRegex(PreparationError, "workflow identity"):
            self.execute(env=env)

    def test_reject_policy_in_candidate_checkout(self):
        with self.assertRaisesRegex(PreparationError, "outside protected base"):
            self.execute(output=self.consumer / "unsafe-policy.toml")

    def test_reject_symlinked_policy_destination(self):
        redirect = self.root / "redirect"
        redirect.symlink_to(self.consumer, target_is_directory=True)
        with self.assertRaisesRegex(PreparationError, "outside protected base"):
            self.execute(output=redirect / "policy.toml")


if __name__ == "__main__":
    unittest.main(verbosity=2)
