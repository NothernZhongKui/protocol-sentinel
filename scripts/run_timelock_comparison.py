#!/usr/bin/env python3
"""Run both actual Timelock fixtures and publish only verified evidence.

Successful classification replay does not authenticate EVM provenance.
"""

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import uuid
from pathlib import Path

from replay_build_compilation import (
    inject_build_output_mutation,
    verify_build_units,
)

from build_provenance import (
    capture_bundle,
    attach_evidence_build,
    verify_evidence_build,
)

from assemble_timelock_comparison import (
    OBS_FIELDS,
    SPEC_FIELDS,
)
from replay_timelock_comparison import replay
from validate_comparison_schema import (
    invalid_constant,
    load_document,
    unique_keys,
    validate_document,
)

ROOT = Path(__file__).resolve().parents[1]

RUNS = ROOT / "artifacts/demo/comparison-runs/c3"

SUITE = "TimelockComparisonEvidenceCaptureTest"

TESTS = {
    "ready": {
        "name": "test_CaptureRealTimelockComparison()",
        "property": "READY_UPGRADE_SUCCEEDS",
        "state": "Ready",
        "outer_success": True,
    },
    "waiting": {
        "name": "test_CaptureRealTimelockWaitingComparison()",
        "property": "NOT_READY_EXECUTION_REJECTED",
        "state": "Waiting",
        "outer_success": False,
    },
}

SOURCE_INPUTS = {
    "foundry.toml",
    "src/AuthorityProbe.sol",
    "src/ComparativeAuthorityProbe.sol",
    "src/TimelockAuthorityProbe.sol",
    "test/TimelockAuthorityIntegration.t.sol",
    "test/TimelockComparisonEvidenceCapture.t.sol",
    "scripts/assemble_timelock_comparison.py",
    "scripts/replay_timelock_comparison.py",
    "scripts/test_timelock_comparison_mutations.py",
    "scripts/run_timelock_comparison.py",
    "scripts/build_provenance.py",
    "scripts/replay_build_compilation.py",
    "scripts/validate_comparison_schema.py",
    "evidence/semantics/registry.json",
    "evidence/schema/comparison-1.0.schema.json",
}


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def git(*args, cwd=ROOT):
    return subprocess.check_output(
        ["git", *args],
        cwd=cwd,
        text=True,
    ).strip()


def strict_json(source):
    return json.loads(
        source,
        object_pairs_hook=unique_keys,
        parse_constant=invalid_constant,
    )


def producer_statuses(result):
    data = strict_json(result.stdout)

    tests = [
        (suite_name, test_name, item.get("status"))
        for suite_name, suite in data.items()
        for test_name, item in suite.get(
            "test_results", {}
        ).items()
    ]

    return tests


def verify_producer(result):
    tests = producer_statuses(result)

    expected = {
        (
            TESTS[name]["name"],
            "Success",
        )
        for name in TESTS
    }

    require(
        result.returncode == 0,
        f"Forge exited with code {result.returncode}",
    )

    require(
        len(tests) == 2,
        f"Expected exactly two producing tests: {tests}",
    )

    require(
        all(
            suite.endswith(":" + SUITE)
            for suite, _, _ in tests
        ),
        f"Unexpected Foundry suite: {tests}",
    )

    require(
        {(name, status) for _, name, status in tests}
        == expected,
        f"Required producing tests not successful: {tests}",
    )


def command(arguments, label):
    result = subprocess.run(
        arguments,
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=180,
    )

    if result.returncode != 0:
        raise RuntimeError(
            f"{label} failed:\n"
            + result.stderr[-3000:]
            + "\n"
            + result.stdout[-1000:]
        )

    return result


def check_source_context(doc, run_id):
    provenance = doc["provenance"]

    require(
        provenance["runId"] == run_id,
        "Mismatched evidence run ID",
    )

    require(
        provenance["sourceCommit"]
        == git("rev-parse", "HEAD"),
        "Source commit mismatch",
    )

    require(
        provenance["workingTreeClean"]
        == (not bool(git("status", "--porcelain"))),
        "Working-tree status mismatch",
    )

    entries = provenance["sourceInputs"]
    paths = [entry["path"] for entry in entries]

    require(
        len(paths) == len(set(paths)),
        "Duplicate manifest paths",
    )

    require(
        set(paths) == SOURCE_INPUTS,
        "Source manifest mismatch",
    )

    for entry in entries:
        name = entry["path"]

        actual = hashlib.sha256(
            (ROOT / name).read_bytes()
        ).hexdigest()

        require(
            actual.lower() == entry["sha256"].lower(),
            f"Source hash mismatch: {name}",
        )

    dependencies = doc["environment"][
        "dependencyRevisions"
    ]

    for key, directory in (
        (
            "openzeppelinContracts",
            "lib/openzeppelin-contracts",
        ),
        (
            "openzeppelinContractsUpgradeable",
            "lib/openzeppelin-contracts-upgradeable",
        ),
    ):
        require(
            dependencies[key] == git(
                "rev-parse", "HEAD",
                cwd=ROOT / directory,
            ),
            f"Dependency revision mismatch: {key}",
        )


def check_lossless(raw_capture, doc):
    spec = doc["scenario"]["spec"]

    for name, original_name in SPEC_FIELDS.items():
        require(
            spec[name] == raw_capture[original_name],
            f"Changed declared field: {name}",
        )

    for name in ("before", "after"):
        stage = doc["stages"][name]
        observation = stage["observation"]

        require(
            set(observation) == set(OBS_FIELDS),
            f"Observation field set mismatch: {name}",
        )

        for field in OBS_FIELDS:
            require(
                observation[field]
                == raw_capture[f"{name}_{field}"],
                f"Changed observation: {name}.{field}",
            )

        require(
            stage["evaluation"] == {
                "status": raw_capture[f"{name}_status"],
                "reason": raw_capture[f"{name}_reason"],
            },
            f"Changed Solidity evaluation: {name}",
        )

        require(
            stage["expectedActiveImplementation"]
            == raw_capture[
                f"{name}_expectedActiveImplementation"
            ],
            f"Changed stage binding: {name}",
        )

    require(
        doc["scenario"]["scenarioId"]
        == raw_capture["scenario_id"],
        "Scenario ID changed",
    )

    for field, source in (
        ("innerCalldata", "inner_calldata"),
        ("outerCalldata", "outer_calldata"),
        ("operationId", "operation_id"),
    ):
        require(
            doc["scenario"]["derived"][field]
            == raw_capture[source],
            f"Changed derived field: {field}",
        )

    for field, source in (
        ("scenarioKey", "comparison_scenario_key"),
        ("verdict", "comparison_verdict"),
        ("reason", "comparison_reason"),
    ):
        require(
            doc["comparison"][field]
            == raw_capture[source],
            f"Changed Solidity comparison: {field}",
        )


def verify_fixture(label, raw_path, evidence_path, run_id):
    fixture = TESTS[label]

    raw_capture = load_document(raw_path)
    document = load_document(evidence_path)

    validate_document(document)
    check_lossless(raw_capture, document)
    check_source_context(document, run_id)

    verify_evidence_build(
        document,
        evidence_path.parent / "build",
        ROOT,
        run_id,
        "test/TimelockComparisonEvidenceCapture.t.sol",
        "python3.12 scripts/run_timelock_comparison.py",
    )

    require(
        document["route"] == "OZ_TIMELOCK_SINGLE",
        "Wrong evidence route",
    )

    require(
        document["scenario"]["spec"]["property"]
        == fixture["property"],
        f"Wrong fixture property: {label}",
    )

    require(
        document["environment"]["chainId"]
        == raw_capture["chain_id"],
        "Chain ID changed",
    )

    result = replay(document)

    require(
        result["classification_replay"] == "MATCH",
        f"Replay mismatch: {label}",
    )

    require(
        result["before"] == {
            "status": "PASS",
            "reason": "NONE",
        }
        and result["after"] == {
            "status": "PASS",
            "reason": "NONE",
        },
        f"Unexpected stage evaluations: {label}",
    )

    require(
        result["comparison"] == "STILL_SATISFIED"
        and result["comparison_reason"] == "NONE",
        f"Unexpected comparison: {label}",
    )

    before = document["stages"]["before"]["observation"]
    after = document["stages"]["after"]["observation"]

    for observation in (before, after):
        require(
            observation["operationStateBefore"]
            == fixture["state"],
            f"Unexpected operation state: {label}",
        )

        require(
            observation["outerSuccess"]
            is fixture["outer_success"],
            f"Unexpected execution result: {label}",
        )

    require(
        before["operationId"] == after["operationId"],
        "Stage operation IDs differ",
    )

    require(
        before["readyAt"] == after["readyAt"],
        "Stage scheduling differs",
    )

    require(
        before["implementationBefore"]
        != after["implementationBefore"],
        "Active implementations did not change",
    )

    return {
        "schema": "VALID",
        "classification_replay": "MATCH",
        "before": result["before"],
        "after": result["after"],
        "comparison": result["comparison"],
        "comparison_reason": result["comparison_reason"],
        "property": fixture["property"],
        "operation_state": fixture["state"],
    }


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--inject-postwrite-failure",
        action="store_true",
    )

    parser.add_argument(
        "--inject-build-replay-mutation",
        action="store_true",
    )
    args = parser.parse_args()

    run_id = uuid.uuid4().hex

    staging = RUNS / ".staging" / run_id
    completed = RUNS / "completed" / run_id

    staging.mkdir(parents=True, exist_ok=False)

    raw_paths = {
        label: staging / f"{label}-raw.json"
        for label in TESTS
    }

    evidence_paths = {
        label: staging / f"{label}-evidence.json"
        for label in TESTS
    }

    forge_file = staging / "forge-results.json"
    report_file = staging / "verification.json"
    fresh_info = staging / ".fresh-build-info"
    forge_out = staging / ".forge-out"
    forge_cache = staging / ".forge-cache"
    build_bundle = staging / "build"

    env = os.environ.copy()

    env.update({
        "EXPORT_ROUTED_CAPTURE": "true",
        "EXPORT_ROUTED_WAITING_CAPTURE": "true",
        "ROUTED_COMPARISON_CAPTURE_PATH":
            str(raw_paths["ready"].relative_to(ROOT)),
        "ROUTED_WAITING_CAPTURE_PATH":
            str(raw_paths["waiting"].relative_to(ROOT)),
        "ROUTED_WAITING_FAIL_AFTER_WRITE":
            "true" if args.inject_postwrite_failure else "false",
    })

    forge_command = [
        "forge",
        "test",
        "--json",
        "--threads",
        "1",
        "--force",
        "--build-info",
        "--build-info-path",
        str(fresh_info),
        "--out",
        str(forge_out),
        "--cache-path",
        str(forge_cache),
        "--match-contract",
        SUITE,
        "--match-test",
        "test_CaptureRealTimelock",
    ]

    print("=== C3 Foundry producers ===", flush=True)
    print("Run:", run_id, flush=True)

    try:
        producer = subprocess.run(
            forge_command,
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
            timeout=300,
        )

        forge_file.write_text(
            producer.stdout,
            encoding="utf-8",
        )

        if args.inject_postwrite_failure:
            statuses = producer_statuses(producer)

            require(
                raw_paths["waiting"].is_file(),
                "Waiting post-write failure produced no file",
            )

            require(
                producer.returncode != 0,
                "Fault injection did not fail Forge",
            )

            require(
                any(
                    name == TESTS["waiting"]["name"]
                    and status != "Success"
                    for _, name, status in statuses
                ),
                "Waiting producing test did not fail",
            )

            require(
                not completed.exists(),
                "Failed run was published",
            )

            shutil.rmtree(staging)

            print(
                "PASS | Waiting wrote JSON then failed",
                flush=True,
            )

            print(
                "PASS | No completed evidence published",
                flush=True,
            )

            return

        verify_producer(producer)

        capture_bundle(
            fresh_info,
            build_bundle,
            ROOT,
            run_id,
            "test/TimelockComparisonEvidenceCapture.t.sol",
        )

        for path in (fresh_info, forge_out, forge_cache):
            if path.exists():
                shutil.rmtree(path)

        print("PASS | Fresh Timelock compiler inputs", flush=True)

        print(
            "PASS | Both producing tests succeeded",
            flush=True,
        )

        for label in TESTS:
            require(
                raw_paths[label].is_file(),
                f"Missing fresh {label} capture",
            )

        print("=== Assemble and replay both scenarios ===",
              flush=True)

        reports = {}

        for label in TESTS:
            command(
                [
                    sys.executable,
                    "scripts/assemble_timelock_comparison.py",
                    str(raw_paths[label]),
                    "--output",
                    str(evidence_paths[label]),
                    "--run-id",
                    run_id,
                ],
                f"{label} assembly",
            )

            document = load_document(evidence_paths[label])

            attach_evidence_build(
                document,
                build_bundle,
                ROOT,
                run_id,
                "test/TimelockComparisonEvidenceCapture.t.sol",
                "python3.12 scripts/run_timelock_comparison.py",
            )

            evidence_paths[label].write_text(
                json.dumps(
                    document, indent=2, sort_keys=True
                ) + chr(10),
                encoding="utf-8",
            )

            reports[label] = verify_fixture(
                label,
                raw_paths[label],
                evidence_paths[label],
                run_id,
            )

            print(
                f"PASS | {label.upper()} schema, mapping, "
                "replay and local source hashes",
                flush=True,
            )

        # An already-completed artifact must not be accepted
        # without rerunning this independent mutation suite.
        command(
            [
                sys.executable,
                "scripts/test_timelock_comparison_mutations.py",
                str(evidence_paths["ready"]),
            ],
            "C3 adversarial matrix",
        )

        print("PASS | C3 adversarial matrix", flush=True)

        if args.inject_build_replay_mutation:
            inject_build_output_mutation(build_bundle)

        verify_build_units(build_bundle)
        print("PASS | Independent Solidity build replay", flush=True)

        report = {
            "run_id": run_id,
            "producer_tests": {
                label: "Success" for label in TESTS
            },
            "fixtures": reports,
            "source_context": "MATCHED_LOCAL_CHECKOUT",
            "build_provenance": "LOCAL_INPUTS_VERIFIED",
            "build_replay": "NORMALIZED_OUTPUT_MATCH",
            "execution_provenance": "UNAUTHENTICATED",
            "mutation_tests": "PASS",
            "publication": "COMPLETED",
        }

        report_file.write_text(
            json.dumps(
                report,
                indent=2,
                sort_keys=True,
            ) + "\n",
            encoding="utf-8",
        )

        expected_files = {
            "ready-raw.json",
            "waiting-raw.json",
            "ready-evidence.json",
            "waiting-evidence.json",
            "forge-results.json",
            "verification.json",
            "build",
        }

        require(
            {path.name for path in staging.iterdir()}
            == expected_files,
            "Unexpected artifact set",
        )

        require(
            not completed.exists(),
            "Completed destination already exists",
        )

        completed.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        # Same-filesystem atomic directory rename.
        staging.rename(completed)

        print()
        print(json.dumps(report, indent=2))
        print()
        print("COMPLETED:", completed, flush=True)

    except Exception:
        print(
            "RUN FAILED | Nothing published",
            file=sys.stderr,
        )
        print(
            "Diagnostic staging:",
            staging,
            file=sys.stderr,
        )
        raise


if __name__ == "__main__":
    main()
