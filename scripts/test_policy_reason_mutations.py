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

        def replay(data):
            nonlocal counter
            counter += 1

            path = Path(temp) / f"case-{counter}.json"
            path.write_text(
                json.dumps(data, indent=2),
                encoding="utf-8"
            )

            return subprocess.run(
                [sys.executable, str(REPLAY), str(path)],
                cwd=ROOT,
                capture_output=True,
                text=True
            )

        def must_accept(name, data):
            result = replay(data)

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
        legacy.pop("reason")

        must_accept("Legacy JSON without reason", legacy)

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

        # Existing status integrity must also remain enforced.
        must_reject(
            "Tampered status",
            changed(risky, result="PASS"),
            "FAIL | Policy replay mismatch"
        )

    print()
    print("PASS | Positive controls: 3/3")
    print("PASS | Negative controls: 9/9")
    print("Policy reason mutation tests PASSED")


if __name__ == "__main__":
    main()
