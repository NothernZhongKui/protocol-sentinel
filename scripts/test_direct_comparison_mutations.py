#!/usr/bin/env python3
"""C2 mutation controls for completed direct evidence."""

import copy
import json
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

from validate_comparison_schema import (
    load_document,
    validate_document,
)

from replay_direct_comparison import (
    ReplayMismatch,
    canonical_call,
    compare,
    evaluate,
    replay,
)

from run_direct_comparison import (
    TEST_NAME,
    verify_producer,
    verify_run_identity,
)


class DirectMutationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.baseline = load_document(sys.argv[1])

    def record(self):
        return copy.deepcopy(self.baseline)

    def rejected(self, document):
        with self.assertRaises(ValueError):
            replay(document)

    def test_baseline_replays(self):
        result = replay(self.record())

        self.assertEqual(result["schema"], "VALID")
        self.assertEqual(
            result["classification_replay"], "MATCH"
        )
        self.assertEqual(
            result["comparison"], "CHANGED_TO_VIOLATION"
        )

    def test_forged_results_are_rejected(self):
        mutations = [
            (
                "verdict",
                lambda d: d["comparison"].update(
                    verdict="STILL_SATISFIED"
                ),
            ),
            (
                "comparison reason",
                lambda d: d["comparison"].update(
                    reason="SCENARIO_MISMATCH"
                ),
            ),
            (
                "before evaluation reason",
                lambda d: d["stages"]["before"][
                    "evaluation"
                ].update(reason="CONTEXT_MISMATCH"),
            ),
            (
                "after evaluation status",
                lambda d: d["stages"]["after"][
                    "evaluation"
                ].update(status="PASS"),
            ),
            (
                "scenario key",
                lambda d: d["comparison"].update(
                    scenarioKey="0x" + "00" * 32
                ),
            ),
            (
                "canonical calldata",
                lambda d: d["scenario"]["derived"].update(
                    canonicalCalldata="0xdeadbeef"
                ),
            ),
            (
                "raw actor with stale evaluation",
                lambda d: d["stages"]["before"][
                    "observation"
                ].update(actor="0x" + "ff" * 20),
            ),
            (
                "raw execution with stale evaluation",
                lambda d: d["stages"]["before"][
                    "observation"
                ].update(success=True),
            ),
        ]

        for name, change in mutations:
            with self.subTest(name=name):
                doc = self.record()
                change(doc)
                self.rejected(doc)

    def test_observed_mismatch_can_replay_incomparable(self):
        doc = self.record()
        spec = doc["scenario"]["spec"]

        doc["stages"]["before"]["observation"]["actor"] = (
            "0x" + "ff" * 20
        )

        # Never repair the observation. Independently
        # recompute the classification for the altered input.
        calldata = canonical_call(spec)

        evaluations = {}

        for name in ("before", "after"):
            stage = doc["stages"][name]

            evaluation = evaluate(
                spec,
                stage["observation"],
                calldata,
            )

            stage["evaluation"] = evaluation
            evaluations[name] = evaluation

        verdict, reason = compare(
            spec,
            doc["stages"],
            evaluations,
            calldata,
        )

        doc["comparison"]["verdict"] = verdict
        doc["comparison"]["reason"] = reason

        self.assertTrue(validate_document(doc))

        result = replay(doc)

        self.assertEqual(
            result["comparison"], "INCOMPARABLE"
        )
        self.assertEqual(
            result["comparison_reason"], "SCENARIO_MISMATCH"
        )
        self.assertEqual(
            result["before"]["status"], "UNKNOWN"
        )

    def test_multiple_defects_preserve_frozen_precedence(self):
        doc = self.record()
        spec = doc["scenario"]["spec"]
        before = doc["stages"]["before"]
        obs = before["observation"]

        # Three simultaneous defects in the same observation.
        # Solidity evaluates INVALID_SLOT before CONTEXT_MISMATCH
        # and before the later candidate-validity check.
        obs["observedSlot"] = "0x" + "00" * 32
        obs["actor"] = "0x" + "ff" * 20
        obs["candidateValidAtObservation"] = False

        # Also introduce a wrong stage binding.
        # SCENARIO_MISMATCH must take precedence.
        before["expectedActiveImplementation"] = spec["candidate"]

        calldata = canonical_call(spec)

        evaluations = {}

        for name in ("before", "after"):
            stage = doc["stages"][name]

            evaluation = evaluate(
                spec,
                stage["observation"],
                calldata,
            )

            stage["evaluation"] = evaluation
            evaluations[name] = evaluation

        verdict, reason = compare(
            spec,
            doc["stages"],
            evaluations,
            calldata,
        )

        self.assertEqual(
            evaluations["before"],
            {"status": "UNKNOWN", "reason": "INVALID_SLOT"},
        )

        self.assertEqual(
            (verdict, reason),
            ("INCOMPARABLE", "SCENARIO_MISMATCH"),
        )

        doc["comparison"]["verdict"] = verdict
        doc["comparison"]["reason"] = reason

        report = replay(doc)

        self.assertEqual(report["classification_replay"], "MATCH")
        self.assertEqual(report["before"]["reason"], "INVALID_SLOT")
        self.assertEqual(
            report["comparison_reason"],
            "SCENARIO_MISMATCH",
        )

    def test_upper_storage_bits_preserve_semantics(self):
        doc = self.record()

        for name in ("before", "after"):
            obs = doc["stages"][name]["observation"]

            original = int(
                obs["implementationBefore"], 16
            )

            obs["implementationBefore"] = (
                "0x" + format(
                    original | (1 << 200),
                    "064x",
                )
            )

        result = replay(doc)

        self.assertEqual(
            result["comparison"], "CHANGED_TO_VIOLATION"
        )

    def test_hex_case_is_semantically_irrelevant(self):
        doc = self.record()

        value = doc["comparison"]["scenarioKey"]

        doc["comparison"]["scenarioKey"] = (
            "0x" + value[2:].upper()
        )

        self.assertEqual(
            replay(doc)["classification_replay"], "MATCH"
        )

    def test_producer_status_fail_closed(self):
        suite = (
            "test/DirectComparisonEvidenceCapture.t.sol:"
            "DirectComparisonEvidenceCaptureTest"
        )

        for status, exit_code, accepted in [
            ("Success", 0, True),
            ("Failure", 1, False),
            ("Skipped", 0, False),
            ("Success", 1, False),
        ]:
            with self.subTest(status=status, exit=exit_code):
                result = SimpleNamespace(
                    returncode=exit_code,
                    stdout=json.dumps({
                        suite: {
                            "test_results": {
                                TEST_NAME: {"status": status}
                            }
                        }
                    }),
                )

                if accepted:
                    verify_producer(result)
                else:
                    with self.assertRaises(RuntimeError):
                        verify_producer(result)

    def test_wrong_producer_suite_rejected(self):
        result = SimpleNamespace(
            returncode=0,
            stdout=json.dumps({
                "test/Wrong.t.sol:WrongContractTest": {
                    "test_results": {
                        TEST_NAME: {"status": "Success"}
                    }
                }
            }),
        )

        with self.assertRaises(RuntimeError):
            verify_producer(result)

    def test_missing_producer_rejected(self):
        result = SimpleNamespace(
            returncode=0,
            stdout=json.dumps({
                "test/Other.t.sol:OtherTest": {
                    "test_results": {}
                }
            }),
        )

        with self.assertRaises(RuntimeError):
            verify_producer(result)

    def test_run_identity_mismatch_rejected(self):
        doc = self.record()

        actual = doc["provenance"]["runId"]
        verify_run_identity(doc, actual)

        with self.assertRaises(RuntimeError):
            verify_run_identity(doc, "f" * 32)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit(
            "Usage: test_direct_comparison_mutations.py evidence.json"
        )

    unittest.main(argv=[sys.argv[0]], verbosity=2)
