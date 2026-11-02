#!/usr/bin/env python3
"""Mutation testing for the v0.4 comparison core.

All mutations run in a disposable Foundry project.
The original repository is never modified.
"""

import json
import shutil
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

SOURCE = ROOT / "src/ComparativeAuthorityProbe.sol"
TEST = ROOT / "test/ComparativeAuthorityProbe.t.sol"


def replace_once(source, old, new):
    count = source.count(old)

    if count != 1:
        raise RuntimeError(
            f"Mutation anchor found {count} times: {old[:60]}"
        )

    return source.replace(old, new, 1)


def remove_actor_binding(source):
    before, separator, after = source.partition(
        "function _directScenarioKey("
    )

    if not separator:
        raise RuntimeError("Scenario key function not found")

    after = replace_once(
        after,
        "spec.actor,",
        "address(0),",
    )

    return before + separator + after


def mutations():
    return [
        (
            "M01 | Hide new violation",
            "test_PassToFail",
            lambda s: replace_once(
                s,
                ": ComparisonVerdict.CHANGED_TO_VIOLATION;",
                ": ComparisonVerdict.STILL_SATISFIED;",
            ),
        ),
        (
            "M02 | Hide restored restriction",
            "test_FailToPass",
            lambda s: replace_once(
                s,
                "? ComparisonVerdict.CHANGED_TO_SATISFIED",
                "? ComparisonVerdict.STILL_VIOLATED",
            ),
        ),
        (
            "M03 | Ignore transaction origin",
            "test_WrongOriginIsIncomparable",
            lambda s: replace_once(
                s,
                "obs.txOrigin == spec.actor",
                "true",
            ),
        ),
        (
            "M04 | Compare raw storage word",
            "test_UpperBitsIgnoredForAddressBinding",
            lambda s: replace_once(
                s,
                "actualBefore != beforeStage.expectedActiveImplementation",
                (
                    "beforeStage.observation.implementationBefore"
                    " != bytes32(uint256(uint160(actualBefore)))"
                ),
            ),
        ),
        (
            "M05 | Fabricate PASS on stage mismatch",
            "test_StageMismatchRetainsRealFail",
            lambda s: replace_once(
                s,
                "result.reason = ComparisonReason.STAGE_BINDING_MISMATCH;",
                (
                    "result.reason = ComparisonReason.STAGE_BINDING_MISMATCH;\n"
                    "            result.beforeEvaluation = "
                    "_decision(PolicyStatus.PASS, PolicyReason.NONE);"
                ),
            ),
        ),
        (
            "M06 | Hide UNKNOWN",
            "test_UnknownBefore",
            lambda s: replace_once(
                s,
                "result.verdict = ComparisonVerdict.INDETERMINATE;",
                "result.verdict = ComparisonVerdict.STILL_SATISFIED;",
            ),
        ),
        (
            "M07 | Ignore identical implementations",
            "test_UpperBitsCannotFakeVersionChange",
            lambda s: replace_once(
                s,
                "result.reason = ComparisonReason.SAME_IMPLEMENTATION_STAGE;",
                "result.reason = ComparisonReason.NONE;",
            ),
        ),
        (
            "M08 | Remove actor from scenario key",
            "test_ScenarioKeyBindsPolicy",
            remove_actor_binding,
        ),
    ]


def execute(project, test_name):
    command = [
        "forge", "test",
        "--json",
        "--threads", "1",
        "--match-path", "test/ComparativeAuthorityProbe.t.sol",
        "--match-test", test_name,
    ]

    completed = subprocess.run(
        command,
        cwd=project,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )

    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"Forge did not return valid test JSON for {test_name}\n"
            f"stderr: {completed.stderr[-1500:]}\n"
            f"stdout: {completed.stdout[-1500:]}"
        ) from exc

    matches = []

    for suite in payload.values():
        if not isinstance(suite, dict):
            continue

        results = suite.get("test_results", {})

        if not isinstance(results, dict):
            continue

        for name, result in results.items():
            if name.startswith(test_name + "("):
                matches.append(result)

    if len(matches) != 1:
        raise RuntimeError(
            f"Expected exactly one executed test {test_name}, "
            f"found {len(matches)}"
        )

    return completed.returncode, matches[0].get("status")


def main():
    original = SOURCE.read_text(encoding="utf-8")

    if not TEST.exists():
        raise RuntimeError("Comparison unit tests not found")

    with tempfile.TemporaryDirectory(
        prefix="sentinel-mutation-"
    ) as temporary:
        project = Path(temporary)

        (project / "src").mkdir()
        (project / "test").mkdir()

        shutil.copy2(
            ROOT / "foundry.toml",
            project / "foundry.toml",
        )

        shutil.copy2(
            ROOT / "src/AuthorityProbe.sol",
            project / "src/AuthorityProbe.sol",
        )

        shutil.copy2(
            SOURCE,
            project / "src/ComparativeAuthorityProbe.sol",
        )

        shutil.copy2(
            TEST,
            project / "test/ComparativeAuthorityProbe.t.sol",
        )

        (project / "lib").symlink_to(
            (ROOT / "lib").resolve(),
            target_is_directory=True,
        )

        mutable_source = (
            project / "src/ComparativeAuthorityProbe.sol"
        )

        cases = mutations()

        print("=== Mutation testing ===", flush=True)

        detected = 0

        for label, test_name, mutate in cases:
            # Verify the original test succeeds.
            mutable_source.write_text(
                original,
                encoding="utf-8",
            )

            baseline_code, baseline_status = execute(
                project,
                test_name,
            )

            if baseline_code != 0 or baseline_status != "Success":
                raise RuntimeError(
                    f"Baseline failed: {label}, {baseline_status}"
                )

            # Apply exactly one deliberate defect.
            mutated = mutate(original)

            if mutated == original:
                raise RuntimeError(
                    f"Mutation did not change source: {label}"
                )

            mutable_source.write_text(
                mutated,
                encoding="utf-8",
            )

            code, status = execute(
                project,
                test_name,
            )

            if code != 0 and status == "Failure":
                detected += 1
                print(
                    f"DETECTED | {label}",
                    flush=True,
                )
            else:
                raise RuntimeError(
                    f"Mutant survived or was not executed: "
                    f"{label} | status={status} | exit={code}"
                )

        print()
        print(f"MUTATION SCORE: {detected}/{len(cases)}")
        print("PASS | All deliberate defects detected")


if __name__ == "__main__":
    main()
