#!/usr/bin/env python3
"""Regression tests for policy evidence schema boundaries."""

import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from replay_policy import evaluate_detailed

ROOT = Path(__file__).resolve().parents[1]
REPLAY = ROOT / "scripts/replay_policy.py"
BASELINE = ROOT / "artifacts/demo/policy-replay-baseline.json"


class SchemaBoundaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.baseline = json.loads(BASELINE.read_text())

        assert cls.baseline["schema_version"] == "0.4"
        assert cls.baseline["result"] == "PASS"

    def replay(self, data, allow_legacy=False):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "witness.json"
            path.write_text(json.dumps(data))

            command = [sys.executable, str(REPLAY)]
            if allow_legacy:
                command.append("--allow-legacy")
            command.append(str(path))

            return subprocess.run(
                command,
                capture_output=True,
                text=True,
                cwd=ROOT,
            )

    def test_reject_v03_with_v04_target_field(self):
        data = copy.deepcopy(self.baseline)
        data["schema_version"] = "0.3"
        data["target_valid_at_observation"] = False

        result = self.replay(data, allow_legacy=True)
        output = result.stdout + result.stderr

        self.assertNotEqual(result.returncode, 0)
        self.assertIn(
            "Target validity field incompatible with legacy schema",
            output,
        )

        with self.assertRaisesRegex(
            ValueError,
            "Target validity field incompatible with legacy schema",
        ):
            evaluate_detailed(data, allow_legacy=True)

    def test_reject_v02_with_v04_target_field(self):
        data = copy.deepcopy(self.baseline)
        data["schema_version"] = "0.2"
        data["target_valid_at_observation"] = False
        data.pop("reason")

        result = self.replay(data, allow_legacy=True)
        output = result.stdout + result.stderr

        self.assertNotEqual(result.returncode, 0)
        self.assertIn(
            "Target validity field incompatible with legacy schema",
            output,
        )

        with self.assertRaisesRegex(
            ValueError,
            "Target validity field incompatible with legacy schema",
        ):
            evaluate_detailed(data, allow_legacy=True)

    def test_legacy_requires_explicit_opt_in(self):
        for version in ("0.2", "0.3"):
            with self.subTest(version=version):
                data = copy.deepcopy(self.baseline)
                data["schema_version"] = version
                data.pop("target_valid_at_observation")

                if version == "0.2":
                    data.pop("reason")

                result = self.replay(data)
                output = result.stdout + result.stderr

                self.assertNotEqual(result.returncode, 0)
                self.assertIn(
                    "Legacy schema requires --allow-legacy",
                    output,
                )

                with self.assertRaisesRegex(
                    ValueError,
                    "Legacy schema requires --allow-legacy",
                ):
                    evaluate_detailed(data)

    def test_reject_v02_with_reason_field(self):
        data = copy.deepcopy(self.baseline)
        data["schema_version"] = "0.2"
        data.pop("target_valid_at_observation")

        result = self.replay(data, allow_legacy=True)
        output = result.stdout + result.stderr

        self.assertNotEqual(result.returncode, 0)
        self.assertIn(
            "Reason field incompatible with schema 0.2",
            output,
        )

        with self.assertRaisesRegex(
            ValueError,
            "Reason field incompatible with schema 0.2",
        ):
            evaluate_detailed(data, allow_legacy=True)

    def test_direct_api_rejects_unknown_schema(self):
        data = copy.deepcopy(self.baseline)
        data["schema_version"] = "9.9"

        with self.assertRaises(ValueError):
            evaluate_detailed(data)

    def test_current_schema_classifies_invalid_target(self):
        data = copy.deepcopy(self.baseline)
        data["target_valid_at_observation"] = False
        data["result"] = "UNKNOWN"
        data["reason"] = "INVALID_TARGET"

        result = self.replay(data)

        self.assertEqual(
            result.returncode, 0,
            result.stdout + result.stderr,
        )

    def test_genuine_legacy_witnesses_remain_readable(self):
        for version in ("0.2", "0.3"):
            with self.subTest(version=version):
                data = copy.deepcopy(self.baseline)
                data["schema_version"] = version
                data.pop("target_valid_at_observation")

                if version == "0.2":
                    data.pop("reason")

                result = self.replay(data, allow_legacy=True)

                self.assertEqual(
                    result.returncode, 0,
                    result.stdout + result.stderr,
                )


if __name__ == "__main__":
    unittest.main(verbosity=2)
