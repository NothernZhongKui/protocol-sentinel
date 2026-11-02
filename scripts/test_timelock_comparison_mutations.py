#!/usr/bin/env python3
"""Frozen Timelock semantics: adversarial and precedence controls.

Synthetic mutations test classification, not execution authenticity.
"""

import copy
import sys
import unittest
from pathlib import Path

from eth_abi import encode

from validate_comparison_schema import (
    load_document,
    validate_document,
)

from replay_timelock_comparison import (
    InvalidPreparation,
    ReplayMismatch,
    compare,
    evaluate,
    identities,
    replay,
    selector,
)


class TimelockMutationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.baseline = load_document(sys.argv[1])

    def document(self):
        return copy.deepcopy(self.baseline)

    def classify(self, doc):
        """Recompute classifications for a changed synthetic input.

        Assert expected outputs separately in every test.
        """
        spec = doc["scenario"]["spec"]
        derived = identities(
            spec,
            doc["scenario"]["scenarioId"],
        )

        evaluations = {}

        for name in ("before", "after"):
            stage = doc["stages"][name]

            result = evaluate(
                spec,
                stage["observation"],
                derived,
            )

            stage["evaluation"] = result
            evaluations[name] = result

        verdict, reason = compare(
            spec,
            doc["stages"],
            evaluations,
            derived,
        )

        doc["comparison"]["verdict"] = verdict
        doc["comparison"]["reason"] = reason

        self.assertTrue(validate_document(doc))

        return replay(doc)

    def update_identity(self, doc):
        """Update declared derivatives, never observed values."""
        scenario = doc["scenario"]

        derived = identities(
            scenario["spec"],
            scenario["scenarioId"],
        )

        for key in (
            "innerCalldata",
            "outerCalldata",
            "operationId",
        ):
            scenario["derived"][key] = (
                "0x" + derived[key].hex()
            )

        doc["comparison"]["scenarioKey"] = (
            "0x" + derived["scenarioKey"].hex()
        )

        return derived

    def test_real_baseline(self):
        result = replay(self.document())

        self.assertEqual(result["classification_replay"], "MATCH")
        self.assertEqual(result["before"]["status"], "PASS")
        self.assertEqual(result["after"]["status"], "PASS")
        self.assertEqual(
            result["comparison"], "STILL_SATISFIED"
        )

    def test_forged_claims_rejected(self):
        changes = [
            lambda d: d["comparison"].update(
                verdict="CHANGED_TO_VIOLATION"
            ),
            lambda d: d["comparison"].update(
                reason="PREPARATION_MISMATCH"
            ),
            lambda d: d["comparison"].update(
                scenarioKey="0x" + "ff" * 32
            ),
            lambda d: d["scenario"]["derived"].update(
                operationId="0x" + "ff" * 32
            ),
            lambda d: d["stages"]["before"][
                "evaluation"
            ].update(reason="INCOMPLETE_EVIDENCE"),
            lambda d: d["stages"]["after"][
                "observation"
            ].update(operationId="0x" + "ff" * 32),
        ]

        for index, change in enumerate(changes):
            with self.subTest(mutation=index):
                doc = self.document()
                change(doc)

                with self.assertRaises(ReplayMismatch):
                    replay(doc)

    def test_context_precedes_missing_evidence(self):
        doc = self.document()
        obs = doc["stages"]["before"]["observation"]

        obs["outerTarget"] = "0x" + "ff" * 20
        obs["proxyCodeObserved"] = False
        obs["executorEOAValid"] = False

        result = self.classify(doc)

        self.assertEqual(
            result["before"],
            {
                "status": "UNKNOWN",
                "reason": "CONTEXT_MISMATCH",
            },
        )

        self.assertEqual(
            result["comparison"], "INCOMPARABLE"
        )

        self.assertEqual(
            result["comparison_reason"],
            "SCENARIO_MISMATCH",
        )

    def test_missing_evidence_precedes_invalid_executor(self):
        doc = self.document()
        obs = doc["stages"]["before"]["observation"]

        obs["proxyCodeObserved"] = False
        obs["executorEOAValid"] = False

        # Governance preparation is unchanged.
        result = self.classify(doc)

        self.assertEqual(
            result["before"]["reason"],
            "INCOMPLETE_EVIDENCE",
        )
        self.assertEqual(
            result["comparison"],
            "INDETERMINATE",
        )
        self.assertEqual(
            result["comparison_reason"],
            "INDETERMINATE_POLICY",
        )

    def test_preparation_drift_precedes_indeterminate(self):
        doc = self.document()
        obs = doc["stages"]["before"]["observation"]

        obs["proxyCodeObserved"] = False
        obs["executorEOAValid"] = False

        # Different observed governance roles between stages.
        obs["executorHasRole"] = False
        obs["openExecutorRole"] = False

        result = self.classify(doc)

        self.assertEqual(
            result["before"],
            {
                "status": "UNKNOWN",
                "reason": "INCOMPLETE_EVIDENCE",
            },
        )
        self.assertEqual(
            result["comparison"],
            "INCOMPARABLE",
        )
        self.assertEqual(
            result["comparison_reason"],
            "PREPARATION_MISMATCH",
        )

    def test_inconsistent_timing_precedes_role_failure(self):
        doc = self.document()
        obs = doc["stages"]["before"]["observation"]

        obs["readyAt"] = str(
            int(obs["observedTimestamp"]) + 1
        )

        obs["executorHasRole"] = False
        obs["openExecutorRole"] = False

        result = self.classify(doc)

        self.assertEqual(
            result["before"],
            {
                "status": "UNKNOWN",
                "reason": "INCONSISTENT_TIMING",
            },
        )

        self.assertEqual(
            result["comparison_reason"],
            "PREPARATION_MISMATCH",
        )

    def test_wrong_state_precedes_executor_failure(self):
        doc = self.document()
        obs = doc["stages"]["before"]["observation"]

        obs["operationStateBefore"] = "Waiting"
        obs["readyAt"] = str(
            int(obs["observedTimestamp"]) + 100
        )

        obs["executorEOAValid"] = False
        obs["executorHasRole"] = False

        with self.assertRaises(InvalidPreparation) as caught:
            replay(doc)

        self.assertEqual(
            caught.exception.failure,
            "WRONG_OPERATION_STATE",
        )

    def test_ineligible_executor_is_preparation_not_fail(self):
        doc = self.document()
        obs = doc["stages"]["before"]["observation"]

        obs["executorHasRole"] = False
        obs["openExecutorRole"] = False

        with self.assertRaises(InvalidPreparation) as caught:
            replay(doc)

        self.assertEqual(
            caught.exception.failure,
            "INELIGIBLE_EXECUTOR",
        )

    def test_schedule_drift_incomparable(self):
        doc = self.document()
        before = doc["stages"]["before"]["observation"]
        after = doc["stages"]["after"]["observation"]

        changed = int(before["readyAt"]) + 100

        after["readyAt"] = str(changed)
        after["observedTimestamp"] = str(
            max(changed, int(after["observedTimestamp"]))
        )

        result = self.classify(doc)

        self.assertEqual(result["before"]["status"], "PASS")
        self.assertEqual(result["after"]["status"], "PASS")

        self.assertEqual(
            result["comparison"], "INCOMPARABLE"
        )

        self.assertEqual(
            result["comparison_reason"],
            "PREPARATION_MISMATCH",
        )

    def test_eligible_executor_role_drift_incomparable(self):
        doc = self.document()
        obs = doc["stages"]["after"]["observation"]

        obs["executorHasRole"] = False
        obs["openExecutorRole"] = True

        result = self.classify(doc)

        self.assertEqual(result["before"]["status"], "PASS")
        self.assertEqual(result["after"]["status"], "PASS")

        self.assertEqual(
            result["comparison_reason"],
            "PREPARATION_MISMATCH",
        )

    def predecessor_document(self):
        doc = self.document()

        spec = doc["scenario"]["spec"]
        spec["predecessor"] = "0x" + "11" * 32

        derived = self.update_identity(doc)

        for name in ("before", "after"):
            obs = doc["stages"][name]["observation"]

            obs["predecessor"] = spec["predecessor"]
            obs["operationId"] = (
                "0x" + derived["operationId"].hex()
            )
            obs["outerCallData"] = (
                "0x" + derived["outerCalldata"].hex()
            )

            obs["predecessorStateObserved"] = True
            obs["predecessorDoneBefore"] = True

        return doc

    def test_completed_predecessor_semantics(self):
        doc = self.predecessor_document()

        result = self.classify(doc)

        self.assertEqual(
            result["comparison"], "STILL_SATISFIED"
        )

    def test_unfinished_predecessor_aborts(self):
        doc = self.predecessor_document()

        doc["stages"]["before"]["observation"][
            "predecessorDoneBefore"
        ] = False

        with self.assertRaises(InvalidPreparation) as caught:
            replay(doc)

        self.assertEqual(
            caught.exception.failure,
            "UNFINISHED_PREDECESSOR",
        )

    def test_unobserved_predecessor_is_unknown(self):
        doc = self.predecessor_document()

        doc["stages"]["before"]["observation"][
            "predecessorStateObserved"
        ] = False

        result = self.classify(doc)

        self.assertEqual(
            result["before"]["reason"],
            "INCOMPLETE_EVIDENCE",
        )
        self.assertEqual(
            result["comparison"],
            "INDETERMINATE",
        )

    def waiting_document(self):
        """Synthetic Waiting evidence for classification testing."""
        doc = self.document()
        spec = doc["scenario"]["spec"]

        spec["property"] = "NOT_READY_EXECUTION_REJECTED"

        derived = self.update_identity(doc)

        timestamps = [
            int(doc["stages"][name]["observation"][
                "observedTimestamp"
            ])
            for name in ("before", "after")
        ]

        future_ready_at = str(max(timestamps) + 604800)

        expected_revert = selector(
            "TimelockUnexpectedOperationState(bytes32,bytes32)"
        ) + encode(
            ["bytes32", "bytes32"],
            [
                derived["operationId"],
                (4).to_bytes(32, "big"),
            ],
        )

        for name in ("before", "after"):
            obs = doc["stages"][name]["observation"]

            obs["operationStateBefore"] = "Waiting"
            obs["readyAt"] = future_ready_at

            obs["outerSuccess"] = False
            obs["operationDoneBefore"] = False
            obs["operationDoneAfter"] = False

            obs["returnData"] = "0x" + expected_revert.hex()
            obs["implementationAfter"] = (
                obs["implementationBefore"]
            )

        return doc

    def test_waiting_exact_rejection_semantics(self):
        doc = self.waiting_document()

        result = self.classify(doc)

        self.assertEqual(
            result["before"],
            {"status": "PASS", "reason": "NONE"},
        )

        self.assertEqual(
            result["after"],
            {"status": "PASS", "reason": "NONE"},
        )

        self.assertEqual(
            result["comparison"], "STILL_SATISFIED"
        )

    def test_waiting_wrong_revert_is_unknown(self):
        doc = self.waiting_document()

        doc["stages"]["before"]["observation"][
            "returnData"
        ] = "0xdeadbeef"

        result = self.classify(doc)

        self.assertEqual(
            result["before"],
            {
                "status": "UNKNOWN",
                "reason": "UNEXPECTED_REVERT",
            },
        )

        self.assertEqual(
            result["comparison"], "INDETERMINATE"
        )


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit(
            "Usage: test_timelock_comparison_mutations.py "
            "evidence.json"
        )

    unittest.main(argv=[sys.argv[0]], verbosity=2)
