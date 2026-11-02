#!/usr/bin/env python3
"""Offline regression tests: no Foundry or Ethereum RPC required."""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from verify_fork_results import (
    ForkResultError,
    REQUIRED_TESTS,
    load_results,
    validate_results,
)

VALIDATOR = Path(__file__).with_name(
    "verify_fork_results.py"
)

SUITE = (
    "test/Adapter8004MainnetFork.t.sol:"
    "Adapter8004MainnetForkTest"
)


def valid_payload():
    return {
        SUITE: {
            "test_results": {
                name: {"status": "Success"}
                for name in REQUIRED_TESTS
            }
        }
    }


class ForkResultValidatorTests(unittest.TestCase):
    def test_required_names_are_pinned(self):
        self.assertEqual(REQUIRED_TESTS, {
            "testFork_NonOwnerCannotUpgrade()",
            "testFork_OwnerUpgradeDetectedAndRestored()",
            "testFork_HistoricalOwnerCanActuallyUpgrade()",
            "testFork_OutsiderAuthorityRegressionPassFailPass()",
        })

    def test_four_successful_tests(self):
        statuses = validate_results(valid_payload())
        self.assertEqual(len(statuses), 4)
        self.assertTrue(
            all(s == "Success" for s in statuses.values())
        )

    def test_empty_forge_output(self):
        with self.assertRaises(ForkResultError):
            validate_results({})

    def test_zero_test_results(self):
        payload = valid_payload()
        payload[SUITE]["test_results"] = {}

        with self.assertRaises(ForkResultError):
            validate_results(payload)

    def test_missing_required_regression_test(self):
        payload = valid_payload()

        del payload[SUITE]["test_results"][
            "testFork_OutsiderAuthorityRegressionPassFailPass()"
        ]

        with self.assertRaises(ForkResultError):
            validate_results(payload)

    def test_skipped_required_test(self):
        payload = valid_payload()

        name = "testFork_NonOwnerCannotUpgrade()"
        payload[SUITE]["test_results"][name]["status"] = "Skipped"

        with self.assertRaises(ForkResultError):
            validate_results(payload)

    def test_failed_required_test(self):
        payload = valid_payload()

        name = "testFork_OwnerUpgradeDetectedAndRestored()"
        payload[SUITE]["test_results"][name]["status"] = "Failure"

        with self.assertRaises(ForkResultError):
            validate_results(payload)

    def test_additional_failed_test(self):
        payload = valid_payload()

        payload[SUITE]["test_results"]["testFork_Extra()"] = {
            "status": "Failure"
        }

        with self.assertRaises(ForkResultError):
            validate_results(payload)

    def test_additional_successful_test(self):
        payload = valid_payload()

        payload[SUITE]["test_results"]["testFork_Extra()"] = {
            "status": "Success"
        }

        self.assertEqual(len(validate_results(payload)), 4)

    def test_duplicate_matching_suites(self):
        payload = valid_payload()
        payload["other/Example.sol:Adapter8004MainnetForkTest"] = {
            "test_results": {}
        }

        with self.assertRaises(ForkResultError):
            validate_results(payload)

    def test_malformed_structure(self):
        with self.assertRaises(ForkResultError):
            validate_results([])

        with self.assertRaises(ForkResultError):
            validate_results({SUITE: {"test_results": None}})

    def test_invalid_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "broken.json"
            path.write_text("{invalid", encoding="utf-8")

            with self.assertRaises(ForkResultError):
                load_results(path)

    def test_duplicate_json_keys(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "duplicate.json"
            path.write_text(
                '{"test_results":{}, "test_results":{}}',
                encoding="utf-8",
            )

            with self.assertRaises(ForkResultError):
                load_results(path)

    def test_cli_accepts_valid_results(self):
        self._check_cli(valid_payload(), 0)

    def test_cli_rejects_zero_tests(self):
        self._check_cli({SUITE: {"test_results": {}}}, 1)

    def _check_cli(self, payload, expected_returncode):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "results.json"
            path.write_text(
                json.dumps(payload),
                encoding="utf-8",
            )

            result = subprocess.run(
                [sys.executable, str(VALIDATOR), str(path)],
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(
                result.returncode,
                expected_returncode,
                result.stdout + result.stderr,
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
