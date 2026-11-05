#!/usr/bin/env python3
"""Negative controls for presentation-only v0.6 trusted workspace summaries."""

import json
import tempfile
import unittest
from pathlib import Path

from render_workspace_summary import render, main

RUN = "a" * 32
BASE = {"repository": "owner/consumer", "sha": "b" * 40,
        "github_run_id": "12345", "attempt": "1"}


def write(path, content):
    path.write_text(json.dumps(content, sort_keys=True), encoding="utf-8")


class SummaryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="sentinel-summary-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / RUN
        self.root.mkdir()
        self.verification = {
            "schema": "VALID", "classification_replay": "MATCH",
            "build_replay": "ISOLATED_COMPILER_OUTPUT_MATCH",
            "build_provenance": "VERIFIED_V2",
            "publication": "COMPLETED",
            "run_id": RUN, "ci_decision": "PASS",
            "comparison": "STILL_SATISFIED",
            "before": {"status": "PASS", "reason": "NONE"},
            "after": {"status": "PASS", "reason": "NONE"},
        }
        self.gate = {
            "format": "protocol-sentinel-ci-gate-v2",
            "verification": "FRESH_VERIFIED_WORKSPACE_EVIDENCE",
            "sentinel_run_id": RUN,
            "decision": "PASS",
            "ci_context": {
                "GITHUB_REPOSITORY": BASE["repository"],
                "GITHUB_SHA": BASE["sha"],
                "GITHUB_RUN_ID": BASE["github_run_id"],
                "GITHUB_RUN_ATTEMPT": BASE["attempt"],
            },
            "scenarios": [{"id": "direct_upgrade", "verdict": "STILL_SATISFIED"}],
        }
        self.evidence = {
            "provenance": {"runId": RUN},
            "comparison": {"verdict": "STILL_SATISFIED"},
            "stages": {
                "before": {"evaluation": {"status": "PASS", "reason": "NONE"}},
                "after": {"evaluation": {"status": "PASS", "reason": "NONE"}},
            },
        }
        self.save()

    def save(self):
        write(self.root / "verification.json", self.verification)
        write(self.root / "ci-gate.json", self.gate)
        write(self.root / "evidence.json", self.evidence)

    def view(self, code=0, path=None, **opts):
        return render(self.root if path is None else path, code, **(BASE | opts))

    def test_safe_pass(self):
        text = self.view()
        self.assertIn("CI DECISION: PASS", text)
        self.assertIn("STILL_SATISFIED", text)
        self.assertNotIn("VERIFICATION FAILED", text)

    def test_verified_block_is_not_green(self):
        self.verification["ci_decision"] = "BLOCK"
        self.verification["comparison"] = "CHANGED_TO_VIOLATION"
        self.verification["after"] = {"status": "FAIL", "reason": "NONE"}
        self.gate["decision"] = "BLOCK"
        self.gate["scenarios"][0]["verdict"] = "CHANGED_TO_VIOLATION"
        self.evidence["comparison"]["verdict"] = "CHANGED_TO_VIOLATION"
        self.evidence["stages"]["after"]["evaluation"] = {"status": "FAIL", "reason": "NONE"}
        self.save()
        text = self.view(2)
        self.assertIn("CI DECISION: BLOCK", text)
        self.assertIn("Upgraded | FAIL", text)
        self.assertNotIn("VERIFICATION FAILED", text)

    def test_failed_current_attempt_never_selects_previous_pass(self):
        self.assertIn("CI DECISION: PASS", self.view(0))
        text = render(None, 2, **(BASE | {"attempt": "2"}))
        self.assertIn("VERIFICATION FAILED", text)
        self.assertNotIn("CI DECISION: PASS", text)

    def test_stale_pass_from_prior_attempt_rejected(self):
        text = self.view(0, attempt="2")
        self.assertIn("VERIFICATION FAILED", text)
        self.assertNotIn("CI DECISION: PASS", text)

    def test_stale_pass_with_current_failed_exit_rejected(self):
        self.assertIn("VERIFICATION FAILED", self.view(2))

    def test_wrong_checkout_sha_rejected(self):
        self.assertIn("VERIFICATION FAILED", self.view(0, sha="c" * 40))

    def test_tampered_stage_rejected(self):
        self.evidence["stages"]["after"]["evaluation"]["status"] = "FAIL"
        self.save()
        self.assertIn("VERIFICATION FAILED", self.view())

    def test_missing_gate_rejected(self):
        (self.root / "ci-gate.json").unlink()
        self.assertIn("VERIFICATION FAILED", self.view())

    def test_replaced_scenario_is_rejected(self):
        self.gate["scenarios"][0]["verdict"] = "CHANGED_TO_VIOLATION"
        self.save()
        self.assertIn("VERIFICATION FAILED", self.view())

    def test_summary_writer_does_not_change_gate_exit(self):
        summary = Path(self.tmp.name) / "summary.md"
        argv = [
            "--run-dir", str(self.root), "--runner-exit", "2",
            "--repository", BASE["repository"], "--sha", BASE["sha"],
            "--github-run-id", BASE["github_run_id"],
            "--attempt", BASE["attempt"],
            "--summary-path", str(summary),
        ]
        status = main(argv)
        self.assertEqual(status, 0)
        self.assertIn("VERIFICATION FAILED", summary.read_text())
        self.assertNotIn("CI DECISION: PASS", summary.read_text())


if __name__ == "__main__":
    unittest.main(verbosity=2)
