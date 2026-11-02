#!/usr/bin/env python3
"""Run Solidity observations and independently replay policy verdicts."""

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "artifacts/demo"

CASES = {
    "baseline": ("PASS", "NO_IMPLEMENTATION_REPLACEMENT", "NONE"),
    "risky": ("FAIL", "NO_IMPLEMENTATION_REPLACEMENT", "NONE"),
    "self-replacement": (
        "UNKNOWN", "NO_IMPLEMENTATION_REPLACEMENT",
        "SUCCESS_WITHOUT_REPLACEMENT"
    ),
    "self-call": ("FAIL", "NO_SUCCESSFUL_UPGRADE_CALL", "NONE"),
    "fixed": ("PASS", "NO_IMPLEMENTATION_REPLACEMENT", "NONE"),
}


def run(*args, env=None):
    subprocess.run(
        list(args),
        cwd=ROOT,
        env=env,
        check=True
    )


def main():
    OUTPUT.mkdir(parents=True, exist_ok=True)

    # Delete only the five generated matrix files, never the main witness.
    for name in CASES:
        path = OUTPUT / f"policy-replay-{name}.json"
        path.unlink(missing_ok=True)

    env = os.environ.copy()
    env["EXPORT_POLICY_MATRIX"] = "true"

    print("=== Generating fresh Solidity observations ===", flush=True)

    run(
        "forge", "test",
        "--match-contract", "PolicyReplayMatrixTest",
        "--match-test", "test_ExportPolicyReplayMatrix",
        "-vv",
        env=env
    )

    print("\n=== Checking independent policy replay ===", flush=True)

    for name, (expected, policy, reason) in CASES.items():
        path = OUTPUT / f"policy-replay-{name}.json"

        if not path.is_file():
            raise SystemExit(f"FAIL | Missing generated witness: {name}")

        data = json.loads(path.read_text(encoding="utf-8"))

        if data.get("schema_version") != "0.4":
            raise SystemExit(f"FAIL | Unexpected schema: {name}")

        if data.get("result") != expected:
            raise SystemExit(f"FAIL | Unexpected Solidity verdict: {name}")

        if data.get("policy_rule") != policy:
            raise SystemExit(f"FAIL | Unexpected policy: {name}")

        if data.get("reason") != reason:
            raise SystemExit(
                f"FAIL | Unexpected diagnostic reason: {name}"
            )

        run(
            sys.executable,
            str(ROOT / "scripts/replay_policy.py"),
            str(path)
        )

        print(f"PASS | {name}: {expected}", flush=True)

    print("\n=== Python controls ===", flush=True)

    run(
        sys.executable,
        str(ROOT / "scripts/replay_policy.py"),
        "--self-test",
        str(OUTPUT / "policy-replay-risky.json")
    )

    print("\nPASS | Solidity/Python matrix: 5/5")
    print("PASS | Replay controls: 13/13")
    print("Policy replay integration PASSED")


if __name__ == "__main__":
    main()
