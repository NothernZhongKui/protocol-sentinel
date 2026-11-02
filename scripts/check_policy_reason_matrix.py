#!/usr/bin/env python3
"""Compare Solidity and Python diagnostics on the same observations."""

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "artifacts/demo"

CASES = {
    "invalid-slot": "INVALID_SLOT",
    "context-mismatch": "CONTEXT_MISMATCH",
    "noncanonical-calldata": "NON_CANONICAL_CALLDATA",
    "invalid-candidate": "INVALID_CANDIDATE",
    "unexpected-revert": "UNEXPECTED_REVERT",
    "success-no-replacement": "SUCCESS_WITHOUT_REPLACEMENT",
}


def main():
    OUTPUT.mkdir(parents=True, exist_ok=True)

    # Remove stale observations before generating new ones.
    for name in CASES:
        (OUTPUT / f"policy-reason-{name}.json").unlink(
            missing_ok=True
        )

    env = os.environ.copy()
    env["EXPORT_POLICY_REASON_MATRIX"] = "true"

    print("=== Generate fresh Solidity diagnostics ===", flush=True)

    subprocess.run(
        [
            "forge", "test",
            "--match-path", "test/PolicyDiagnostics.t.sol",
            "--match-test", "test_ExportDiagnosticReasonMatrix",
            "-vv",
        ],
        cwd=ROOT,
        env=env,
        check=True,
    )

    print("\n=== Independent Python comparison ===", flush=True)

    for name, expected_reason in CASES.items():
        path = OUTPUT / f"policy-reason-{name}.json"

        if not path.is_file():
            raise SystemExit(f"FAIL | Missing evidence: {name}")

        data = json.loads(path.read_text(encoding="utf-8"))

        expected = {
            "schema_version": "0.3",
            "policy_rule": "NO_IMPLEMENTATION_REPLACEMENT",
            "result": "UNKNOWN",
            "reason": expected_reason,
        }

        for field, value in expected.items():
            if data.get(field) != value:
                raise SystemExit(
                    f"FAIL | {name}: unexpected {field}"
                )

        # Replay recomputes both status and reason independently.
        subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts/replay_policy.py"),
                str(path),
            ],
            cwd=ROOT,
            check=True,
        )

        print(
            f"PASS | {name}: UNKNOWN / {expected_reason}",
            flush=True,
        )

    print()
    print(f"PASS | Solidity/Python diagnostics: {len(CASES)}/6")
    print("Independent diagnostic matrix PASSED")


if __name__ == "__main__":
    main()
