#!/usr/bin/env python3
"""Regression tests: summary must never promote stale Evidence to a green check."""

import json
import tempfile
import unittest
from pathlib import Path

from render_workspace_summary import main, render

REPO = "NothernZhongKui/protocol-sentinel"
SHA = "a" * 40
RUN = "b" * 32
CI_ID = "234"
CONTEXT = {
    "GITHUB_REPOSITORY": REPO,
    "GITHUB_SHA": SHA,
    "GITHUB_RUN_ID": CI_ID,
    "GITHUB_RUN_ATTEMPT": "2",
}


class SummaryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="sentinel-summary-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.completed = self.root / "completed"
        self.completed.mkdir()
        self.run = self.completed / RUN
        self.run.mkdir()
        self.verification = {
            "publication": "COMPLETED",
            "schema": "VALID",
            "classification_replay": "MATCH",
            "build_replay": "ISOLATED_COMPILER_OUTPUT_MATCH",
            "build_provenance": "VERIFIED_V2",
            "run_id": RUN,
            "ci_decision": "PASS",
            "comparison": "STILL_SATISFIED",
            "before": {"status": "PASS", "reason": "NONE"},
            "after": {"status": "PASS", "reason": "NONE"},
        }
        self.gate = {
            "format": "protocol-sentinel-ci-gate-v2",
            "verification": "FRESH_VERIFIED_WORKSPACE_EVIDENCE",
            "sentinel_run_id": RUN,
            "ci_context": dict(CONTEXT),
            "decision": "PASS",
            "scenarios": [{"id": "my_upgrade", "verdict": "STILL_SATISFIED"}],
        }
        self.evidence = {
            "provenance": {"runId": RUN},
            "comparison": {"verdict": "STILL_SATISFIED"},
            "stages": {
                "before": {"evaluation": dict(self.verification["before"])},
                "after": {"evaluation": dict(self.verification["after"])},
            },
        }
        self.write()

    def write(self):
        for filename, doc in (
            ("verification.json", self.verification),
            ("ci-gate.json", self.gate),
            ("evidence.json", self.evidence),
        ):
            (self.run / filename).write_text(json.dumps(doc), encoding="utf-8")

    def render(self, run=None, exit_code=0, *, attempt="2"):
        return render(
            self.run if run is None else run, exit_code,
            repository=REPO, sha=SHA, github_run_id=CI_ID, attempt=attempt,
        )

    def test_pass_current_run(self):
        output = self.render()
        self.assertIn("CI DECISION: PASS", output)
        self.assertIn("STILL_SATISFIED", output)
        self.assertNotIn("VERIFICATION FAILED", output)

    def test_block_current_run_with_matching_exit(self):
        self.verification.update({
            "before": {"status": "PASS", "reason": "NONE"},
            "after": {"status": "FAIL", "reason": "NONE"},
            "ci_decision": "BLOCK",
            "comparison": "CHANGED_TO_VIOLATION",
        })
        self.gate.update({
            "decision": "BLOCK",
            "scenarios": [{"id": "my_upgrade", "verdict": "CHANGED_TO_VIOLATION"}],
        })
        self.evidence["comparison"]["verdict"] = "CHANGED_TO_VIOLATION"
        self.evidence["stages"]["after"]["evaluation"]["status"] = "FAIL"
        self.write()
        output = self.render(exit_code=2)
        self.assertIn("CI DECISION: BLOCK", output)
        self.assertIn("CHANGED_TO_VIOLATION", output)
        self.assertIn("| Upgraded | FAIL |", output)

    def test_stale_previous_pass_not_used_after_current_failure(self):
        # The previous PASS is deliberately present on disk. A failed current
        # attempt has no completed path: never glob the previous directory.
        output = self.render(run=False, exit_code=2)
        self.assertIn("VERIFICATION FAILED", output)
        self.assertNotIn("CI DECISION: PASS", output)
        self.assertNotIn(RUN, output)

    def test_prior_attempt_does_not_match_current_context(self):
        output = self.render(attempt="3")
        self.assertIn("VERIFICATION FAILED", output)
        self.assertNotIn("CI DECISION: PASS", output)

    def test_exit_code_cannot_disagree_with_decision(self):
        output = self.render(exit_code=2)
        self.assertIn("VERIFICATION FAILED", output)
        self.assertNotIn("CI DECISION: PASS", output)

    def test_tampered_comparison_is_not_shown_as_verified(self):
        self.evidence["comparison"]["verdict"] = "CHANGED_TO_VIOLATION"
        self.write()
        self.assertIn("VERIFICATION FAILED", self.render())

    def test_missing_gate_is_not_shown_as_verified(self):
        (self.run / "ci-gate.json").unlink()
        self.assertIn("VERIFICATION FAILED", self.render())

    def test_cli_writes_summary_without_changing_gate_exit(self):
        output_path = self.root / "summary.md"
        status = main([
            "--runner-exit", "2",
            "--repository", REPO, "--sha", SHA,
            "--github-run-id", CI_ID, "--attempt", "2",
            "--summary-path", str(output_path),
        ])
        self.assertEqual(status, 0)
        self.assertIn("VERIFICATION FAILED", output_path.read_text())
        self.assertNotIn("CI DECISION: PASS", output_path.read_text())


if __name__ == "__main__":
    unittest.main(verbosity=2)
