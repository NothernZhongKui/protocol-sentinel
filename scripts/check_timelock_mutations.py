#!/usr/bin/env python3
"""Isolated mutation tests for Protocol Sentinel v0.4-B."""

from dataclasses import dataclass
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "src/TimelockAuthorityProbe.sol"

EVAL = "test/TimelockAuthorityEvaluation.t.sol"
COMP = "test/TimelockAuthorityComparison.t.sol"
OBS = "test/TimelockAuthorityObserver.t.sol"


@dataclass(frozen=True)
class Mutation:
    name: str
    test_file: str
    test_name: str
    pattern: str
    replacement: str
    expected_matches: int = 1


MUTATIONS = [
    Mutation(
        "M01_wrong_ready_bitmap",
        EVAL,
        "test_WaitingWrongReadyBitmapIsUnknown",
        r"bytes32\(uint256\(4\)\)",
        "bytes32(uint256(2))",
    ),
    Mutation(
        "M02_ignore_open_executor_role",
        EVAL,
        "test_OpenExecutorRoleAccepted",
        r"obs\.executorHasRole\s*\|\|\s*obs\.openExecutorRole",
        "obs.executorHasRole",
    ),
    Mutation(
        "M03_ignore_predecessor",
        EVAL,
        "test_ReadyUnfinishedPredecessorIsPreparationError",
        (
            r"spec\.predecessor\s*!=\s*bytes32\(0\)"
            r"\s*&&\s*!obs\.predecessorDoneBefore"
        ),
        (
            "false && spec.predecessor != bytes32(0)"
            " && !obs.predecessorDoneBefore"
        ),
    ),
    Mutation(
        "M04_ignore_operation_identity",
        EVAL,
        "test_OperationIdMismatchIsUnknown",
        r"obs\.operationId\s*!=\s*_timelockOperationId\(spec\)",
        "(false && obs.operationId != _timelockOperationId(spec))",
        expected_matches=1,
    ),
    Mutation(
        "M05_ignore_upgrade_effect",
        EVAL,
        "test_ReadyOuterSuccessWithoutEffectFails",
        r"activeAfter\s*!=\s*spec\.candidate",
        "false && activeAfter != spec.candidate",
    ),
    Mutation(
        "M06_ignore_success_return_data",
        EVAL,
        "test_ReadyNonemptyOuterReturnDataIsUnknown",
        r"obs\.outerSuccess\s*&&\s*obs\.returnData\.length\s*!=\s*0",
        "false && obs.outerSuccess && obs.returnData.length != 0",
    ),
    Mutation(
        "M07_ignore_rescheduling",
        COMP,
        "test_RescheduledOperationIsIncomparable",
        r"beforeObs\.readyAt\s*!=\s*afterObs\.readyAt",
        "false && beforeObs.readyAt != afterObs.readyAt",
    ),
    Mutation(
        "M08_ignore_open_role_drift",
        COMP,
        "test_GovernanceRoleDriftIsIncomparable",
        (
            r"beforeObs\.openExecutorRole"
            r"\s*!=\s*afterObs\.openExecutorRole"
        ),
        "false",
    ),
    Mutation(
        "M09_allow_same_implementation",
        COMP,
        "test_SameImplementationIsIncomparable",
        (
            r"beforeStage\.expectedActiveImplementation"
            r"\s*==\s*afterStage\.expectedActiveImplementation"
        ),
        (
            "false && beforeStage.expectedActiveImplementation"
            " == afterStage.expectedActiveImplementation"
        ),
    ),
    Mutation(
        "M10_disable_snapshot_restoration",
        OBS,
        "test_ReadyRealExecutionAndSnapshotRestoration",
        (
            r"bool\s+restored\s*=\s*"
            r"vm\.revertToStateAndDelete\(\s*snapshotId\s*\)\s*;"
        ),
        "bool restored = true;",
    ),
]


def run_forge(workspace: Path, *args: str):
    return subprocess.run(
        ["forge", "test", *args],
        cwd=workspace,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )


def make_workspace(destination: Path):
    shutil.copy2(
        ROOT / "foundry.toml",
        destination / "foundry.toml",
    )

    shutil.copytree(ROOT / "src", destination / "src")

    test_directory = destination / "test"
    test_directory.mkdir()

    for relative_path in {EVAL, COMP, OBS}:
        source = ROOT / relative_path
        target = destination / relative_path
        shutil.copy2(source, target)

    # Dependencies are read through a symlink.
    # No vendor sources are modified.
    (destination / "lib").symlink_to(
        (ROOT / "lib").resolve(),
        target_is_directory=True,
    )


def apply_mutation(original: str, mutation: Mutation) -> str:
    matches = re.findall(
        mutation.pattern,
        original,
        flags=re.MULTILINE,
    )

    if len(matches) != mutation.expected_matches:
        raise RuntimeError(
            f"{mutation.name}: expected "
            f"{mutation.expected_matches} mutation anchors, "
            f"found {len(matches)}"
        )

    modified, count = re.subn(
        mutation.pattern,
        lambda _: mutation.replacement,
        original,
        count=1,
        flags=re.MULTILINE,
    )

    if count != 1 or modified == original:
        raise RuntimeError(
            f"{mutation.name}: mutation was not applied"
        )

    return modified


def mutation_was_detected(output: str, test_name: str) -> bool:
    # A compilation error is not counted as a killed mutation.
    compilation_errors = (
        "Compiler run failed",
        "Compilation failed",
        "Error: Compilation",
    )

    if any(marker in output for marker in compilation_errors):
        return False

    return (
        test_name in output
        and re.search(r"\[FAIL(?::|\])", output) is not None
    )


def main():
    original = SOURCE.read_text()

    print("=== Protocol Sentinel v0.4-B Mutation Testing ===")
    print("Original source:", SOURCE)
    print("Mutations:", len(MUTATIONS))
    print()

    with tempfile.TemporaryDirectory(
        prefix="sentinel-v04b-mutations-"
    ) as temporary:
        workspace = Path(temporary)
        make_workspace(workspace)

        isolated_source = workspace / "src/TimelockAuthorityProbe.sol"

        print("=== Baseline: unmodified source ===")

        baseline = run_forge(
            workspace,
            "--match-path",
            "test/TimelockAuthority*.t.sol",
        )

        if baseline.returncode != 0:
            print(baseline.stdout[-6000:])
            print("FAIL | Isolated baseline did not pass")
            return 1

        print("PASS | Isolated baseline is green")
        print()

        killed = 0
        survived = []
        errors = []

        for index, mutation in enumerate(MUTATIONS, start=1):
            print(
                f"[{index:02d}/{len(MUTATIONS):02d}] "
                f"{mutation.name}"
            )

            try:
                mutated = apply_mutation(original, mutation)
            except RuntimeError as exc:
                print("  ERROR |", exc)
                errors.append(mutation.name)
                continue

            # Replace only the disposable copy.
            isolated_source.write_text(mutated)

            result = run_forge(
                workspace,
                "--match-path",
                mutation.test_file,
                "--match-test",
                mutation.test_name,
                "-vv",
            )

            if result.returncode == 0:
                print("  SURVIVED | Regression test passed")
                survived.append(mutation.name)

            elif mutation_was_detected(
                result.stdout,
                mutation.test_name,
            ):
                print("  KILLED | Regression test detected mutation")
                killed += 1

            else:
                print("  ERROR | Test did not fail as expected")
                print(result.stdout[-3500:])
                errors.append(mutation.name)

        # Restore disposable source before the temporary directory
        # is removed. The real repository was never modified.
        isolated_source.write_text(original)

    print()
    print("=== Mutation Summary ===")
    print(f"Killed:   {killed}/{len(MUTATIONS)}")
    print(f"Survived: {len(survived)}")
    print(f"Errors:   {len(errors)}")

    if survived:
        print("Survivors:", ", ".join(survived))

    if errors:
        print("Errors:", ", ".join(errors))

    if killed != len(MUTATIONS):
        print("FAIL | Mutation suite incomplete")
        return 1

    print("PASS | All designed mutations detected")
    print("PASS | Original repository source untouched")
    return 0


if __name__ == "__main__":
    sys.exit(main())
