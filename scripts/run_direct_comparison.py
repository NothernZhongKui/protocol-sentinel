#!/usr/bin/env python3
"""Fresh Foundry capture -> assembly -> replay -> atomic publication.

The completed run is locally verified, not cryptographically attested.
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

from validate_comparison_schema import (
    load_document,
    unique_keys,
    invalid_constant,
    validate_document,
)

ROOT = Path(__file__).resolve().parents[1]

RUNS = ROOT / "artifacts/demo/comparison-runs"

TEST_NAME = "test_CaptureRealDirectComparison()"

EXPECTED_INPUTS = {
    "foundry.toml",
    "src/AuthorityProbe.sol",
    "src/ComparativeAuthorityProbe.sol",
    "test/DirectComparisonEvidenceCapture.t.sol",
    "test/fixtures/RoleVaultVersions.sol",
    "evidence/semantics/registry.json",
    "evidence/schema/comparison-1.0.schema.json",
    "scripts/assemble_direct_comparison.py",
    "scripts/replay_direct_comparison.py",
    "scripts/validate_comparison_schema.py",
    "scripts/run_direct_comparison.py",
}


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def git(*args):
    return subprocess.check_output(
        ["git", *args],
        cwd=ROOT,
        text=True,
    ).strip()


def strict_json(source):
    return json.loads(
        source,
        object_pairs_hook=unique_keys,
        parse_constant=invalid_constant,
    )


def verify_producer(result):
    data = strict_json(result.stdout)

    tests = [
        (suite_name, name, item.get("status"))
        for suite_name, suite in data.items()
        for name, item in suite.get("test_results", {}).items()
    ]

    require(
        result.returncode == 0,
        f"Forge exited with code {result.returncode}",
    )

    require(
        len(tests) == 1
        and tests[0][0].endswith(
            ":DirectComparisonEvidenceCaptureTest"
        )
        and tests[0][1:] == (TEST_NAME, "Success"),
        f"Required producing test not successful: {tests}",
    )

    return data


def verify_local_source_context(evidence):
    provenance = evidence["provenance"]

    require(
        provenance["sourceCommit"] == git("rev-parse", "HEAD"),
        "Source commit does not match checkout",
    )

    inputs = provenance["sourceInputs"]
    paths = [entry["path"] for entry in inputs]

    require(
        len(paths) == len(set(paths)),
        "Duplicate source manifest paths",
    )

    require(
        set(paths) == EXPECTED_INPUTS,
        "Source input manifest is incomplete or unexpected",
    )

    for entry in inputs:
        path = ROOT / entry["path"]

        actual = hashlib.sha256(
            path.read_bytes()
        ).hexdigest()

        require(
            actual.lower() == entry["sha256"].lower(),
            f"Source hash mismatch: {entry['path']}",
        )

    require(
        provenance["workingTreeClean"] ==
        (not bool(git("status", "--porcelain"))),
        "Working-tree cleanliness claim changed",
    )


def check_lossless(raw, document):
    """Verify exact preservation of all raw capture fields."""

    scenario = document["scenario"]
    spec = scenario["spec"]
    comparison = document["comparison"]

    expected = {
        "format": "protocol-sentinel-direct-capture-v1",
        "chain_id": document["environment"]["chainId"],
        "scenario_id": scenario["scenarioId"],
        "actor": spec["actor"],
        "target": spec["target"],
        "candidate": spec["candidate"],
        "expected_revert": spec["expectedRevert"],
        "policy": spec["policy"],
        "canonical_calldata": scenario["derived"]["canonicalCalldata"],
        "comparison_scenario_key": comparison["scenarioKey"],
        "comparison_verdict": comparison["verdict"],
        "comparison_reason": comparison["reason"],
    }

    for name in ("before", "after"):
        stage = document["stages"][name]

        expected[f"{name}_expectedActiveImplementation"] = (
            stage["expectedActiveImplementation"]
        )

        for field, value in stage["observation"].items():
            expected[f"{name}_{field}"] = value

        expected[f"{name}_status"] = stage["evaluation"]["status"]
        expected[f"{name}_reason"] = stage["evaluation"]["reason"]

    require(
        set(raw) == set(expected),
        "Lossless capture field set mismatch",
    )

    for field, value in expected.items():
        require(
            type(raw[field]) is type(value) and raw[field] == value,
            f"Lossless mismatch: {field}",
        )


def verify_run_identity(document, run_id):
    require(
        document["provenance"]["runId"] == run_id,
        "Evidence run ID does not match runner",
    )


def run_command(arguments, label):
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


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--inject-postwrite-failure",
        action="store_true",
        help="Negative control: Foundry writes then fails",
    )

    parser.add_argument(
        "--inject-assembly-mutation",
        action="store_true",
    )
    args = parser.parse_args()

    run_id = uuid.uuid4().hex

    staging = RUNS / ".staging" / run_id
    completed = RUNS / "completed" / run_id

    staging.mkdir(parents=True, exist_ok=False)

    capture = staging / "raw-capture.json"
    evidence_path = staging / "evidence.json"
    forge_path = staging / "forge-results.json"
    report_path = staging / "verification.json"

    env = os.environ.copy()

    env["EXPORT_DIRECT_CAPTURE"] = "true"

    # The producer writes only into this invocation's
    # freshly created staging directory.
    env["DIRECT_COMPARISON_CAPTURE_PATH"] = str(
        capture.relative_to(ROOT)
    )

    env["DIRECT_COMPARISON_FAIL_AFTER_WRITE"] = (
        "true" if args.inject_postwrite_failure else "false"
    )

    command = [
        "forge",
        "test",
        "--json",
        "--threads",
        "1",
        "--match-contract",
        "DirectComparisonEvidenceCaptureTest",
        "--match-test",
        "test_CaptureRealDirectComparison",
    ]

    print("=== Fresh Foundry producer ===", flush=True)
    print("Run:", run_id, flush=True)

    try:
        result = subprocess.run(
            command,
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
            timeout=180,
        )

        forge_path.write_text(
            result.stdout,
            encoding="utf-8",
        )

        if args.inject_postwrite_failure:
            try:
                results = strict_json(result.stdout)

                statuses = [
                    item.get("status")
                    for suite in results.values()
                    for name, item in suite.get(
                        "test_results", {}
                    ).items()
                    if name == TEST_NAME
                ]
            except (ValueError, TypeError):
                statuses = []

            require(
                capture.is_file(),
                "Fault injection did not create a capture",
            )

            require(
                result.returncode != 0
                and len(statuses) == 1
                and statuses[0] != "Success",
                "Fault injection did not fail its producing test",
            )

            require(
                not completed.exists(),
                "Failed run was unexpectedly published",
            )

            shutil.rmtree(staging)

            print(
                "PASS | File written, producing test failed",
                flush=True,
            )
            print(
                "PASS | No completed evidence published",
                flush=True,
            )
            return

        verified_forge = verify_producer(result)

        require(
            capture.is_file(),
            "Fresh capture was not created",
        )

        require(
            capture.stat().st_size > 0,
            "Fresh capture is empty",
        )

        print("PASS | Required Foundry test", flush=True)

        print("=== Assemble Evidence 1.0 ===", flush=True)

        run_command(
            [
                sys.executable,
                "scripts/assemble_direct_comparison.py",
                str(capture),
                "--output",
                str(evidence_path),
                "--run-id",
                run_id,
            ],
            "Evidence assembly",
        )

        require(
            evidence_path.is_file(),
            "Assembler did not produce evidence",
        )

        document = load_document(evidence_path)

        if args.inject_assembly_mutation:
            observation = document["stages"]["after"]["observation"]
            require(
                observation["candidateValidAtObservation"] is True,
                "Unexpected mutation baseline",
            )
            observation["candidateValidAtObservation"] = False
            evidence_path.write_text(
                json.dumps(document, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            document = load_document(evidence_path)

        validate_document(document)
        check_lossless(load_document(capture), document)

        print("PASS | Schema and lossless capture", flush=True)

        print("=== Independent classification replay ===", flush=True)

        replay_result = run_command(
            [
                sys.executable,
                "scripts/replay_direct_comparison.py",
                str(evidence_path),
            ],
            "Independent Python replay",
        )

        report = strict_json(replay_result.stdout)

        require(
            report.get("schema") == "VALID",
            "Schema was not validated",
        )

        require(
            report.get("classification_replay") == "MATCH",
            "Classification replay mismatch",
        )

        print("PASS | Classification MATCH", flush=True)

        print("=== Verify local source context ===", flush=True)

        verify_local_source_context(document)

        print("PASS | Source hashes match local checkout", flush=True)

        # A replay match is not a claim that execution
        # provenance has been authenticated.
        report["source_context"] = "MATCHED_LOCAL_CHECKOUT"
        report["execution_provenance"] = "UNAUTHENTICATED"
        report["producer_test"] = "Success"
        report["run_id"] = run_id
        report["publication"] = "COMPLETED"

        verify_run_identity(document, run_id)

        report_path.write_text(
            json.dumps(report, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

        require(
            {p.name for p in staging.iterdir()} == {
                "raw-capture.json",
                "evidence.json",
                "forge-results.json",
                "verification.json",
            },
            "Unexpected published artifact set",
        )

        require(
            not completed.exists(),
            "Publication destination already exists",
        )

        completed.parent.mkdir(parents=True, exist_ok=True)

        # Staging and completion are on the same filesystem.
        # A completed directory appears only after all checks.
        staging.rename(completed)

        print()
        print(json.dumps(report, indent=2))
        print()
        print("COMPLETED:", completed, flush=True)

    except Exception:
        print(
            "RUN FAILED | No completed evidence published",
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
