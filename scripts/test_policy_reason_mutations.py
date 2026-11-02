#!/usr/bin/env python3
"""Negative controls for independently replayed policy reasons."""

import copy
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPLAY = ROOT / "scripts/replay_policy.py"
OUTPUT = ROOT / "artifacts/demo"


def load(name):
    path = OUTPUT / f"policy-replay-{name}.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    return data


def changed(data, **updates):
    result = copy.deepcopy(data)
    result.update(updates)
    return result


def main():
    risky = load("risky")
    unknown = load("self-replacement")

    assert risky["result"] == "FAIL"
    assert risky["reason"] == "NONE"

    assert unknown["result"] == "UNKNOWN"
    assert unknown["reason"] == "SUCCESS_WITHOUT_REPLACEMENT"

    with tempfile.TemporaryDirectory(
        prefix="sentinel-policy-reasons-"
    ) as temp:
        counter = 0

        def replay(data, allow_legacy=False):
            nonlocal counter
            counter += 1

            path = Path(temp) / f"case-{counter}.json"
            path.write_text(
                json.dumps(data, indent=2),
                encoding="utf-8"
            )

            command = [sys.executable, str(REPLAY)]
            if allow_legacy:
                command.append("--allow-legacy")
            command.append(str(path))

            return subprocess.run(
                command,
                cwd=ROOT,
                capture_output=True,
                text=True
            )

        def must_accept(name, data, allow_legacy=False):
            result = replay(data, allow_legacy=allow_legacy)

            if result.returncode != 0:
                raise AssertionError(
                    f"{name} unexpectedly rejected:\n"
                    f"{result.stdout}\n{result.stderr}"
                )

            print(f"PASS | Accepted: {name}")

        def must_reject(name, data, marker):
            result = replay(data)
            output = result.stdout + result.stderr

            if result.returncode == 0 or marker not in output:
                raise AssertionError(
                    f"{name} was not correctly rejected:\n{output}"
                )

            print(f"PASS | Rejected: {name}")

        # Positive controls.
        must_accept("Original FAIL / NONE", risky)
        must_accept(
            "Original UNKNOWN / SUCCESS_WITHOUT_REPLACEMENT",
            unknown
        )

        # Previous evidence format remains supported.
        legacy = copy.deepcopy(risky)
        legacy["schema_version"] = "0.2"
        legacy.pop("reason")
        legacy.pop("target_valid_at_observation")

        must_accept("Legacy JSON without reason", legacy, allow_legacy=True)

        legacy_03 = copy.deepcopy(risky)
        legacy_03["schema_version"] = "0.3"
        legacy_03.pop("target_valid_at_observation")

        must_accept("Legacy schema 0.3 with reason", legacy_03, allow_legacy=True)

        missing_reason = copy.deepcopy(risky)
        missing_reason.pop("reason")

        must_reject(
            "Missing reason in schema 0.4",
            missing_reason,
            "FAIL | Policy reason missing"
        )

        missing_target = copy.deepcopy(risky)
        missing_target.pop("target_valid_at_observation")

        must_reject(
            "Missing target validity in schema 0.4",
            missing_target,
            "FAIL | Target validity missing"
        )

        must_reject(
            "Invalid target validity type",
            changed(risky, target_valid_at_observation="true"),
            "ERROR | Invalid boolean field: target_valid_at_observation"
        )

        # Negative controls: correct verdict, falsified reason.
        cases = [
            (
                "Wrong reason on FAIL",
                changed(risky, reason="INVALID_SLOT")
            ),
            (
                "Wrong reason on UNKNOWN",
                changed(unknown, reason="NONE")
            ),
            (
                "Invented reason",
                changed(risky, reason="NOT_A_REAL_REASON")
            ),
            (
                "Empty reason",
                changed(risky, reason="")
            ),
            (
                "Numeric reason",
                changed(risky, reason=123)
            ),
            (
                "Null reason",
                changed(risky, reason=None)
            ),
            (
                "Object instead of reason",
                changed(risky, reason={"status": "NONE"})
            ),
        ]

        for name, data in cases:
            must_reject(
                name,
                data,
                "FAIL | Policy reason mismatch"
            )

        # Attacker changes observation and adjusts status,
        # but leaves an inconsistent reason.
        context_mutation = changed(
            risky,
            expected_target="0x" + "00" * 20,
            result="UNKNOWN",
            reason="NONE"
        )

        must_reject(
            "Manipulated context with matching status",
            context_mutation,
            "FAIL | Policy reason mismatch"
        )

        # Target validity changes must invalidate recorded decisions.
        must_reject(
            "False target flag on recorded FAIL",
            changed(risky, target_valid_at_observation=False),
            "FAIL | Policy replay mismatch"
        )

        must_reject(
            "False target flag on recorded UNKNOWN",
            changed(unknown, target_valid_at_observation=False),
            "FAIL | Policy reason mismatch"
        )

        must_reject(
            "Adjusted status but inconsistent target reason",
            changed(
                risky,
                target_valid_at_observation=False,
                result="UNKNOWN"
            ),
            "FAIL | Policy reason mismatch"
        )

        # Existing status integrity must also remain enforced.
        must_reject(
            "Tampered status",
            changed(risky, result="PASS"),
            "FAIL | Policy replay mismatch"
        )

    print()
    print("PASS | Positive controls: 4/4")
    print("PASS | Negative controls: 15/15")
    print("Policy reason mutation tests PASSED")


if __name__ == "__main__":
    main()
